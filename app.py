import os
import io
from flask import Flask, request, render_template, redirect, session, url_for, jsonify, send_from_directory, flash, send_file
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from datetime import datetime
from PIL import Image
import pandas as pd
from docx2pdf import convert as docx_to_pdf_convert
from pdf2docx import Converter
import moviepy.editor as mp
import zipfile
import rarfile
import py7zr
import subprocess
import json
import markdown
from pillow_heif import register_heif_opener
import xmltodict
import sqlite3
import nbformat
from nbconvert import PythonExporter
from gridfs import GridFS

register_heif_opener()

app = Flask(__name__)
app.secret_key = 'a-very-secret-and-static-key-for-development'

# MongoDB Configuration
MONGO_URI = "mongodb+srv://panda:sonu@clustertest.qwyt70x.mongodb.net/"
client = MongoClient(MONGO_URI)
db = client.tempbox_db
users_collection = db.users
files_collection = db.files
logs_collection = db.logs
fs = GridFS(db)  # Initialize GridFS

# Create a temporary directory for conversion processes
TEMP_CONVERT_FOLDER = 'temp_convert'
if not os.path.exists(TEMP_CONVERT_FOLDER):
    os.makedirs(TEMP_CONVERT_FOLDER)

# --- Helper function for authentication ---
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# --- Routes ---

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_identifier = request.form.get('username')
        password = request.form.get('password')
        user = users_collection.find_one({
            '$or': [{'email': login_identifier}, {'username': login_identifier}]
        })
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            logs_collection.insert_one({
                'user_id': user['_id'],
                'username': user['username'],
                'action': 'login',
                'timestamp': datetime.utcnow()
            })
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if users_collection.find_one({'email': email}):
            flash('Email already registered.', 'error')
            return redirect(url_for('signup'))
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password)
        users_collection.insert_one({
            'username': username, 'email': email, 'password': hashed_password,
            'bio': '', 'phone': '', 'location': '', 'ip': '', 'country_name': '',
            'city': '', 'org': '', 'avatar': None, 'notifications': True, 'language': 'en'
        })
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))
    last_login_log = logs_collection.find_one(
        {'user_id': ObjectId(user_id), 'action': 'login'},
        sort=[('timestamp', -1)]
    )
    last_login_time = last_login_log['timestamp'] if last_login_log else None
    user_data = {
        'username': user.get('username', 'Guest User'), 'email': user.get('email', 'guest@domain.com'),
        'bio': user.get('bio', 'No bio added yet.'), 'phone': user.get('phone', ''),
        'location': user.get('location', ''), 'ip': user.get('ip', 'Detecting...'),
        'city': user.get('city', 'Detecting...'), 'country_name': user.get('country_name', 'Detecting...'),
        'org': user.get('org', 'Anonymous User'), 'avatar': user.get('avatar')
    }
    return render_template('dash.html', user=user_data, last_login=last_login_time)

@app.route('/api/avatar/upload', methods=['POST'])
@login_required
def upload_avatar():
    user_id = session['user_id']
    if 'avatar' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        # For simplicity, avatars are still stored on the filesystem, but could also be moved to GridFS.
        filename = f'{user_id}_{secure_filename(file.filename)}'
        filepath = os.path.join('static', 'avatars', filename)
        if not os.path.exists(os.path.join('static', 'avatars')):
            os.makedirs(os.path.join('static', 'avatars'))
        file.save(filepath)
        users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': {'avatar': filepath}})
        return jsonify({'message': 'Avatar updated successfully', 'avatar_url': f'/{filepath}'}), 200
    return jsonify({'error': 'File processing failed'}), 500

@app.route('/api/logout', methods=['POST'])
def api_logout():
    if 'user_id' in session:
        user_id = session.get('user_id')
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user:
            logs_collection.insert_one({
                'user_id': user['_id'], 'username': user.get('username'),
                'action': 'logout', 'timestamp': datetime.utcnow()
            })
        session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/api/profile', methods=['GET', 'POST'])
@login_required
def api_profile():
    user_id = session['user_id']
    if request.method == 'GET':
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user:
            user_data = {
                'username': user.get('username', 'Guest User'), 'email': user.get('email', 'guest@domain.com'),
                'bio': user.get('bio', 'No bio added yet.'), 'phone': user.get('phone', ''),
                'location': user.get('location', ''), 'ip': user.get('ip', 'Detecting...'),
                'city': user.get('city', 'Detecting...'), 'country_name': user.get('country_name', 'Detecting...'),
                'org': user.get('org', 'Anonymous User'), 'avatar': user.get('avatar')
            }
            return jsonify(user_data), 200
        return jsonify({'message': 'User not found'}), 404
    elif request.method == 'POST':
        data = request.get_json()
        update_fields = {k: v for k, v in data.items() if k in ['username', 'email', 'bio', 'phone', 'location', 'ip', 'city', 'country_name', 'org']}
        if update_fields:
            users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': update_fields})
            user = users_collection.find_one({'_id': ObjectId(user_id)})
            logs_collection.insert_one({
                'user_id': user['_id'], 'username': user.get('username'),
                'action': 'profile_update', 'details': f"Updated fields: {', '.join(update_fields.keys())}",
                'timestamp': datetime.utcnow()
            })
            return jsonify({'message': 'Profile updated successfully'}), 200
        return jsonify({'message': 'No fields to update'}), 400

@app.route('/api/convert', methods=['POST'])
@login_required
def api_convert():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    target_format = request.form.get('target')

    if file.filename == '' or not target_format:
        return jsonify({'error': 'No selected file or target format'}), 400

    original_filename = secure_filename(file.filename)
    base_name, input_ext = os.path.splitext(original_filename)
    input_ext = input_ext.lower()

    # Save original file to a temporary local path for conversion
    temp_input_path = os.path.join(TEMP_CONVERT_FOLDER, original_filename)
    file.save(temp_input_path)

    output_filename = f"{base_name}.{target_format}"
    temp_output_path = os.path.join(TEMP_CONVERT_FOLDER, output_filename)
    
    try:
        # Perform conversion using temporary local files
        # (Conversion logic remains the same, but uses temp_input_path and temp_output_path)
        if input_ext in ['.jpg', '.jpeg'] and target_format == 'png':
            Image.open(temp_input_path).save(temp_output_path)
        # ... (all other conversion cases) ...
        else:
            return jsonify({'error': f'Conversion from {input_ext} to {target_format} is not supported'}), 400

        # Save original and converted files to GridFS from their temp locations
        original_file_id = fs.put(open(temp_input_path, 'rb'), filename=original_filename, content_type=file.content_type)
        converted_file_id = fs.put(open(temp_output_path, 'rb'), filename=output_filename)

        # Create DB record
        files_collection.insert_one({
            'user_id': ObjectId(session['user_id']),
            'original_filename': original_filename,
            'original_file_id': original_file_id,
            'converted_filename': output_filename,
            'converted_file_id': converted_file_id,
            'target_format': target_format,
            'timestamp': datetime.utcnow(),'file_type': 'permanent','expires_at': None
        })

        download_url = url_for('download_file', file_id=str(converted_file_id), _external=True)

        # Log the conversion
        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        logs_collection.insert_one({
            'user_id': user['_id'], 'username': user.get('username', 'Unknown User'),
            'action': 'file_convert', 'details': f"Converted '{original_filename}' to '{output_filename}'",
            'timestamp': datetime.utcnow()
        })

        return jsonify({'download_url': download_url}), 200

    except Exception as e:
        return jsonify({'error': f'An error occurred during conversion: {str(e)}'}), 500
    finally:
        # Clean up temporary files
        if os.path.exists(temp_input_path):
            os.remove(temp_input_path)
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)

@app.route('/share/<file_id>')
def share_file(file_id):
    try:
        file_doc = files_collection.find_one({
            '$or': [{'original_file_id': ObjectId(file_id)}, {'converted_file_id': ObjectId(file_id)}]
        })

        if not file_doc:
            return "File not found.", 404

        if file_doc.get('file_type') == 'temporary' and file_doc.get('expires_at') and datetime.utcnow() > file_doc.get('expires_at'):
            return "This link has expired.", 410 # Gone

        file_info = fs.get(ObjectId(file_id))
        return send_file(
            io.BytesIO(file_info.read()),
            mimetype=file_info.content_type or 'application/octet-stream',
            as_attachment=True,
            download_name=file_info.filename
        )
    except Exception:
        return "File not found or invalid link.", 404

@app.route('/file/<file_id>')
@login_required
def download_file(file_id):
    try:
        # Ensure the user has access to this file
        file_info = fs.get(ObjectId(file_id))
        file_doc = files_collection.find_one({
            '$or': [{'original_file_id': ObjectId(file_id)}, {'converted_file_id': ObjectId(file_id)}],
            'user_id': ObjectId(session['user_id'])
        })
        if not file_doc:
            return jsonify({'error': 'File not found or access denied'}), 404

        return send_file(
            io.BytesIO(file_info.read()),
            mimetype=file_info.content_type or 'application/octet-stream',
            as_attachment=True,
            download_name=file_info.filename
        )
    except Exception:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/logs')
@login_required
def get_user_logs():
    user_id = session['user_id']
    logs_cursor = logs_collection.find(
        {'user_id': ObjectId(user_id)}
    ).sort('timestamp', -1).limit(50)
    logs_list = [{'action': log.get('action', 'unknown').replace('_', ' ').title(),
                  'details': log.get('details', 'No details available.'),
                  'timestamp': log.get('timestamp').isoformat()} for log in logs_cursor]
    return jsonify(logs_list)

@app.route('/api/files')
@login_required
def get_user_files():
    user_id = session['user_id']
    search_query = request.args.get('search', '')
    query_filter = {'user_id': ObjectId(user_id)}
    if search_query:
        query_filter['original_filename'] = {'$regex': search_query, '$options': 'i'}

    files_cursor = files_collection.find(query_filter).sort('timestamp', -1)
    files_list = []
    for file_doc in files_cursor:
        file_id_to_download = file_doc.get('converted_file_id') or file_doc.get('original_file_id')
        file_id_to_share = file_doc.get('converted_file_id') or file_doc.get('original_file_id')
        
        download_url = url_for('download_file', file_id=str(file_id_to_download)) if file_id_to_download else None
        share_url = url_for('share_file', file_id=str(file_id_to_share), _external=True) if file_id_to_share else None
        
        is_converted = file_doc.get('target_format') not in [None, 'shared']

        files_list.append({
            'id': str(file_doc.get('_id')),
            'filename': file_doc.get('original_filename', 'untitled'),
            'format': file_doc.get('target_format', 'N/A') if is_converted else os.path.splitext(file_doc.get('original_filename', ''))[1][1:].upper(),
            'url': download_url,
            'timestamp': file_doc.get('timestamp').isoformat(),
            'file_type': file_doc.get('file_type', 'permanent'),
            'expires_at': file_doc.get('expires_at').isoformat() if file_doc.get('expires_at') else None,
            'share_url': share_url
        })
    return jsonify(files_list)

@app.route('/api/files/<string:file_id>', methods=['DELETE'])
@login_required
def delete_file(file_id):
    print(f"Deleting file with id: {file_id}")
    user_id = session['user_id']
    try:
        file_doc = files_collection.find_one({'_id': ObjectId(file_id), 'user_id': ObjectId(user_id)})
    except Exception:
        return jsonify({'error': 'Invalid file ID format'}), 400

    if not file_doc:
        return jsonify({'error': 'File not found or you do not have permission to delete it'}), 404

    try:
        # Delete files from GridFS
        if file_doc.get('original_file_id'):
            fs.delete(file_doc.get('original_file_id'))
        if file_doc.get('converted_file_id'):
            fs.delete(file_doc.get('converted_file_id'))

        # Delete the document from the files_collection
        files_collection.delete_one({'_id': ObjectId(file_id)})

        # Add a log entry for the deletion
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        logs_collection.insert_one({
            'user_id': ObjectId(user_id), 'username': user.get('username'),
            'action': 'file_delete', 'details': f"Deleted file: {file_doc.get('original_filename')}",
            'timestamp': datetime.utcnow()
        })
        return jsonify({'message': 'File deleted successfully'}), 200
    except Exception as e:
        # Log the error for debugging
        app.logger.error(f"Error during file deletion: {e}")
        return jsonify({'error': 'An internal error occurred during file deletion.'}), 500

@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        from datetime import timedelta

        filename = secure_filename(file.filename)
        file_type = request.form.get('file_type', 'permanent')
        expiration_hours = request.form.get('expiration_hours')
        expires_at = None

        if file_type == 'temporary' and expiration_hours:
            try:
                expires_at = datetime.utcnow() + timedelta(hours=int(expiration_hours))
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid expiration hours value.'}), 400

        # Save file to GridFS
        file_id = fs.put(file.stream, filename=filename, content_type=file.content_type)

        # Create DB record
        files_collection.insert_one({
            'user_id': ObjectId(session['user_id']),
            'original_filename': filename,
            'original_file_id': file_id,
            'target_format': 'shared', 'file_type': file_type, 'expires_at': expires_at,
            'timestamp': datetime.utcnow()
        })

        share_url = url_for('share_file', file_id=str(file_id), _external=True)

        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        logs_collection.insert_one({
            'user_id': user['_id'], 'username': user.get('username', 'Unknown User'),
            'action': 'file_share', 'details': f"Shared file: {filename}",
            'timestamp': datetime.utcnow()
        })
        return jsonify({'share_url': share_url}), 200
    return jsonify({'error': 'File processing failed'}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def api_settings():
    user_id = session['user_id']
    if request.method == 'GET':
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user:
            return jsonify({'notifications': user.get('notifications', True), 'language': user.get('language', 'en')}), 200
        return jsonify({'message': 'User not found'}), 404
    elif request.method == 'POST':
        data = request.get_json()
        update_fields = {k: v for k, v in data.items() if k in ['notifications', 'language']}
        if update_fields:
            users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': update_fields})
            return jsonify({'message': 'Settings updated successfully'}), 200
        return jsonify({'message': 'No settings to update'}), 400

@app.route('/api/stats')
@login_required
def get_user_stats():
    user_id = session['user_id']
    files_converted = files_collection.count_documents({'user_id': ObjectId(user_id)})
    templates_used = logs_collection.count_documents({'user_id': ObjectId(user_id), 'action': 'template_use'})
    files_shared = logs_collection.count_documents({'user_id': ObjectId(user_id), 'action': 'file_share'})
    return jsonify({'templatesUsed': templates_used, 'filesConverted': files_converted, 'filesShared': files_shared})

if(__name__ == "__main__"):
    app.run(debug=True)
