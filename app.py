import os
from flask import Flask, request, render_template, redirect, session, url_for, jsonify, send_from_directory, flash
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId # To work with MongoDB's default _id
from datetime import datetime, timedelta
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

register_heif_opener()


app = Flask(__name__)
# A static secret key is required to keep sessions persistent across server restarts.
# The previous key `os.urandom(24)` generated a new key on each restart, invalidating all sessions.
# In a production environment, this should be loaded from an environment variable for security.
app.secret_key = 'a-very-secret-and-static-key-for-development'

# MongoDB Configuration
MONGO_URI = "mongodb+srv://panda:sonu@clustertest.qwyt70x.mongodb.net/" # Replace with your MongoDB connection string if different
client = MongoClient(MONGO_URI)
db = client.tempbox_db # Your database name
users_collection = db.users # Collection for users
files_collection = db.files # Collection for files (for converter, etc.)
logs_collection = db.logs # Collection for logs

# TTL index to auto-delete expired files from MongoDB
files_collection.create_index('expires_at', expireAfterSeconds=0)
# Create an 'uploads' directory if it doesn't exist
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)



# --- Helper function for authentication ---
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__ # Preserve original function name for Flask
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
        login_identifier = request.form.get('username') # Correctly get 'username' from the form
        password = request.form.get('password')

        # Allow user to log in with either their email or username for better UX
        user = users_collection.find_one({
            '$or': [{'email': login_identifier}, {'username': login_identifier}]
        })

        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id']) # Store user ID in session
            # --- Add Login Log ---
            logs_collection.insert_one({
                'user_id': user['_id'],
                'username': user['username'],
                'action': 'login',
                'timestamp': datetime.utcnow()
            })
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'error') # Use flash to show error message
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
            'username': username,
            'email': email,
            'password': hashed_password,
            'bio': '',
            'phone': '',
            'location': '',
            'ip': '', # Will be updated by frontend on dashboard load
            'country_name': '',
            'city': '',
            'org': '',
            'avatar': None,
            'notifications': True,
            'language': 'en'
        })
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login')) # Redirect to login after successful signup
    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    if not user:
        session.pop('user_id', None) # Clear invalid session
        return redirect(url_for('login'))

    # Fetch the last login time from the logs
    last_login_log = logs_collection.find_one(
        {'user_id': ObjectId(user_id), 'action': 'login'},
        sort=[('timestamp', -1)]
    )
    last_login_time = last_login_log['timestamp'] if last_login_log else None

    # Pass user data and last login time to the dashboard template
    user_data = {
        'username': user.get('username', 'Guest User'),
        'email': user.get('email', 'guest@domain.com'),
        'bio': user.get('bio', 'No bio added yet.'),
        'phone': user.get('phone', ''),
        'location': user.get('location', ''),
        'ip': user.get('ip', 'Detecting...'),
        'city': user.get('city', 'Detecting...'),
        'country_name': user.get('country_name', 'Detecting...'),
        'org': user.get('org', 'Anonymous User'),
        'avatar': user.get('avatar')
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
        filename = f'{user_id}_{file.filename}'
        filepath = os.path.join('static', 'avatars', filename)
        file.save(filepath)

        # Update user's avatar in the database
        users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': {'avatar': filepath}})

        return jsonify({'message': 'Avatar updated successfully', 'avatar_url': f'/{filepath}'}), 200
    
    return jsonify({'error': 'File processing failed'}), 500

@app.route('/api/logout', methods=['POST'])
def api_logout():
    if 'user_id' in session:
        user_id = session.get('user_id')
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user:
            # --- Add Logout Log ---
            logs_collection.insert_one({
                'user_id': user['_id'],
                'username': user.get('username'),
                'action': 'logout',
                'timestamp': datetime.utcnow()
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
            # Exclude sensitive data like password hash
            user_data = {
                'username': user.get('username', 'Guest User'),
                'email': user.get('email', 'guest@domain.com'),
                'bio': user.get('bio', 'No bio added yet.'),
                'phone': user.get('phone', ''),
                'location': user.get('location', ''),
                'ip': user.get('ip', 'Detecting...'),
                'city': user.get('city', 'Detecting...'),
                'country_name': user.get('country_name', 'Detecting...'),
                'org': user.get('org', 'Anonymous User'),
                'avatar': user.get('avatar')
            }
            return jsonify(user_data), 200
        return jsonify({'message': 'User not found'}), 404
    elif request.method == 'POST':
        data = request.get_json() # Expect JSON data from frontend
        update_fields = {}
        if 'username' in data:
            update_fields['username'] = data['username']
        if 'email' in data:
            update_fields['email'] = data['email']
        if 'bio' in data:
            update_fields['bio'] = data['bio']
        if 'phone' in data:
            update_fields['phone'] = data['phone']
        if 'location' in data:
            update_fields['location'] = data['location']
        # IP info is updated by frontend's ipapi.co call, not directly by user form
        # But we can allow the backend to store it if the frontend sends it
        if 'ip' in data:
            update_fields['ip'] = data['ip']
        if 'city' in data:
            update_fields['city'] = data['city']
        if 'country_name' in data:
            update_fields['country_name'] = data['country_name']
        if 'org' in data:
            update_fields['org'] = data['org']

        if update_fields:
            users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': update_fields})
            user = users_collection.find_one({'_id': ObjectId(user_id)}) # Get updated user for log
            # --- Add Profile Update Log ---
            logs_collection.insert_one({
                'user_id': user['_id'],
                'username': user.get('username'),
                'action': 'profile_update',
                'details': f"Updated fields: {', '.join(update_fields.keys())}",
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

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and target_format:
        original_filename = file.filename
        base_name, input_ext = os.path.splitext(original_filename)
        input_ext = input_ext.lower()

        filepath = os.path.join(UPLOAD_FOLDER, original_filename)
        file.save(filepath)

        output_filename = f"{base_name}.{target_format}"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        
        try:
            # Image conversions
            if input_ext in ['.jpg', '.jpeg'] and target_format == 'png':
                Image.open(filepath).save(output_path)
            elif input_ext in ['.jpg', '.jpeg'] and target_format == 'pdf':
                Image.open(filepath).convert('RGB').save(output_path)
            elif input_ext == '.png' and target_format == 'jpg':
                Image.open(filepath).convert('RGB').save(output_path)
            # PDF/DOCX conversions
            elif input_ext == '.pdf' and target_format == 'docx':
                cv = Converter(filepath)
                cv.convert(output_path, start=0, end=None)
                cv.close()
            elif input_ext == '.docx' and target_format == 'pdf':
                docx_to_pdf_convert(filepath, output_path)
            elif input_ext == '.pdf' and target_format == 'jpg':
                # Requires PyMuPDF (fitz)
                import fitz
                doc = fitz.open(filepath)
                page = doc.load_page(0) # first page
                pix = page.get_pixmap()
                pix.save(output_path)
            elif input_ext == '.pdf' and target_format == 'txt':
                import fitz
                doc = fitz.open(filepath)
                text = ""
                for page in doc:
                    text += page.get_text()
                with open(output_path, "w", encoding="utf-8") as text_file:
                    text_file.write(text)
            # CSV/XLSX conversions
            elif input_ext == '.csv' and target_format == 'xlsx':
                pd.read_csv(filepath).to_excel(output_path, index=False)
            elif input_ext == '.xlsx' and target_format == 'csv':
                pd.read_excel(filepath).to_csv(output_path, index=False)
            # Text to PDF
            elif input_ext == '.txt' and target_format == 'pdf':
                # Using markdown conversion as a simple way
                with open(filepath, 'r') as f:
                    text = f.read()
                html = markdown.markdown(text)
                # Requires weasyprint
                from weasyprint import HTML
                HTML(string=html).write_pdf(output_path)
            # HTML to PDF
            elif input_ext == '.html' and target_format == 'pdf':
                from weasyprint import HTML
                HTML(filepath).write_pdf(output_path)
            # Audio/Video conversions
            elif input_ext == '.mp4' and target_format == 'mp3':
                mp.VideoFileClip(filepath).audio.write_audiofile(output_path)
            elif input_ext == '.mp3' and target_format == 'wav':
                mp.AudioFileClip(filepath).write_audiofile(output_path)
            elif input_ext == '.wav' and target_format == 'mp3':
                mp.AudioFileClip(filepath).write_audiofile(output_path)
            elif input_ext == '.mp4' and target_format == 'mkv':
                # This is more of a container change, can be done with moviepy
                clip = mp.VideoFileClip(filepath)
                clip.write_videofile(output_path, codec='copy')
            elif input_ext == '.mov' and target_format == 'mp4':
                clip = mp.VideoFileClip(filepath)
                clip.write_videofile(output_path)
            # Archive conversions
            elif input_ext == '.zip' and target_format == 'rar':
                # Note: rarfile can read but not write rar files. This is a placeholder.
                # Creating rar archives requires the proprietary rar utility.
                # We will simulate by just re-zipping it.
                with zipfile.ZipFile(filepath, 'r') as zip_ref:
                    zip_ref.extractall(output_path + "_temp")
                # This part is non-functional without rar command line tool
                # subprocess.run(['rar', 'a', output_path, output_path + "_temp"])
                return jsonify({'error': 'Conversion from zip to rar is not supported'}), 501
            elif input_ext == '.rar' and target_format == 'zip':
                with rarfile.RarFile(filepath) as opened_rar:
                    with zipfile.ZipFile(output_path, 'w') as zip_file:
                        for file_info in opened_rar.infolist():
                            zip_file.writestr(file_info.filename, opened_rar.read(file_info.filename))
            elif input_ext == '.7z' and target_format == 'zip':
                with py7zr.SevenZipFile(filepath, mode='r') as z:
                    z.extractall(path=output_path + "_temp")
                with zipfile.ZipFile(output_path, 'w') as zipf:
                    for root, _, files in os.walk(output_path + "_temp"):
                        for file in files:
                            zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), output_path + "_temp"))
            # Code conversions
            elif input_ext == '.py' and target_format == 'exe':
                # This is a complex operation and might not be suitable for a web server
                # It's platform dependent and slow.
                return jsonify({'error': 'py to exe conversion is too complex for this service'}), 501
            elif input_ext == '.ts' and target_format == 'js':
                # Requires typescript compiler `tsc` to be in PATH
                subprocess.run(['tsc', filepath, '--outFile', output_path], check=True)
            elif input_ext == '.scss' and target_format == 'css':
                # Requires `libsass`
                import sass
                with open(filepath, 'r') as scss_file:
                    css = sass.compile(string=scss_file.read())
                with open(output_path, 'w') as css_file:
                    css_file.write(css)
            # Data format conversions
            elif input_ext == '.json' and target_format == 'csv':
                pd.read_json(filepath).to_csv(output_path, index=False)
            elif input_ext == '.csv' and target_format == 'json':
                pd.read_csv(filepath).to_json(output_path, orient='records')
            # Misc conversions
            elif input_ext == '.md' and target_format == 'pdf':
                with open(filepath, 'r') as f:
                    html_text = markdown.markdown(f.read())
                from weasyprint import HTML
                HTML(string=html_text).write_pdf(output_path)
            elif input_ext == '.svg' and target_format == 'png':
                # Requires cairosvg
                import cairosvg
                cairosvg.svg2png(url=filepath, write_to=output_path)
            elif input_ext == '.heic' and target_format == 'jpg':
                Image.open(filepath).convert('RGB').save(output_path)
            elif input_ext == '.xml' and target_format == 'json':
                with open(filepath) as xml_file:
                    data_dict = xmltodict.parse(xml_file.read())
                with open(output_path, 'w') as json_file:
                    json.dump(data_dict, json_file, indent=4)
            elif input_ext == '.sqlite' and target_format == 'csv':
                conn = sqlite3.connect(filepath)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                # This will convert only the first table to a csv
                if tables:
                    table_name = tables[0][0]
                    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
                    df.to_csv(output_path, index=False)
                conn.close()
            elif input_ext == '.ipynb' and target_format == 'py':
                with open(filepath) as f:
                    nb = nbformat.read(f, as_version=4)
                exporter = PythonExporter()
                source, _ = exporter.from_notebook_node(nb)
                with open(output_path, 'w') as f:
                    f.write(source)
            else:
                return jsonify({'error': f'Conversion from {input_ext} to {target_format} is not supported'}), 400

        except Exception as e:
            return jsonify({'error': f'An error occurred during conversion: {str(e)}'}), 500

        download_url = url_for('download_converted_file', filename=output_filename, _external=True)

        files_collection.insert_one({
            'user_id': ObjectId(session['user_id']),
            'original_filename': original_filename,
            'converted_filename': output_filename,
            'target_format': target_format,
            'converted_url': download_url,
            'timestamp': datetime.utcnow(),
        })

        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        logs_collection.insert_one({
            'user_id': user['_id'],
            'username': user.get('username', 'Unknown User'),
            'action': 'file_convert',
            'details': f"Converted '{original_filename}' to '{output_filename}'",
            'timestamp': datetime.utcnow()
        })

        return jsonify({'download_url': download_url}), 200

    return jsonify({'error': 'File processing failed'}), 500

# Route to serve converted files (for demonstration)
@app.route('/downloads/<filename>')
@login_required
def download_converted_file(filename):  #####
    # In a real app, you'd check if the user has permission to download this file
    # and serve it from a secure location.
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/api/logs')
@login_required
def get_user_logs():
    user_id = session['user_id']
    
    # Fetch logs for the current user, sorted by most recent first
    logs_cursor = logs_collection.find(
        {'user_id': ObjectId(user_id)}
    ).sort('timestamp', -1).limit(50) # Limit to the last 50 logs for performance

    logs_list = []
    for log in logs_cursor:
        logs_list.append({
            'action': log.get('action', 'unknown').replace('_', ' ').title(),
            'details': log.get('details', 'No details available.'),
            'timestamp': log.get('timestamp').isoformat() # Convert datetime to ISO string for JSON
        })
    return jsonify(logs_list)

@app.route('/api/files')
@login_required
def get_user_files():
    user_id = session['user_id']
    search_query = request.args.get('search', '')

    # Base query to only get files for the logged-in user
    query_filter = {'user_id': ObjectId(user_id)}

    # If a search query is provided, add a case-insensitive regex search on the filename
    if search_query:
        query_filter['original_filename'] = {'$regex': search_query, '$options': 'i'}

    # Fetch files for the current user, sorted by most recent first
    files_cursor = files_collection.find(
        query_filter
    ).sort('timestamp', -1)

    files_list = []
    for file_doc in files_cursor:
        files_list.append({
            'id': str(file_doc.get('_id')),
            'filename': file_doc.get('original_filename', 'untitled'),
            'format': file_doc.get('target_format', 'N/A'),
            'url': file_doc.get('converted_url'),
            'timestamp': file_doc.get('timestamp').isoformat(),
            'file_type': file_doc.get('file_type', 'permanent'),
            'expires_at': file_doc.get('expires_at').isoformat() if file_doc.get('expires_at') else None
        })
    return jsonify(files_list)

@app.route('/api/files/<string:file_id>', methods=['DELETE'])
@login_required
def delete_file(file_id):
    user_id = session['user_id']

    # Find the file document to ensure it belongs to the user
    try:
        file_doc = files_collection.find_one({
            '_id': ObjectId(file_id),
            'user_id': ObjectId(user_id)
        })
    except Exception: # Catches invalid ObjectId format
        return jsonify({'error': 'Invalid file ID format'}), 400

    if not file_doc:
        return jsonify({'error': 'File not found or you do not have permission to delete it'}), 404

    # 1. Delete the physical file from the 'uploads' folder
    filename = file_doc.get('original_filename')
    if filename:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            os.remove(filepath)

    # 2. Delete the document from the files_collection
    files_collection.delete_one({'_id': ObjectId(file_id)})

    # 3. Add a log entry for the deletion
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    logs_collection.insert_one({
        'user_id': ObjectId(user_id),
        'username': user.get('username'),
        'action': 'file_delete',
        'details': f"Deleted file: {filename}",
        'timestamp': datetime.utcnow()
    })

    return jsonify({'message': 'File deleted successfully'}), 200

@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    expiry_hours = request.form.get('expiry_hours', type=float, default=None)

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        filename = file.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        expires_at = None
        if expiry_hours:
            expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)

        download_url = url_for('download_converted_file', filename=filename, _external=True)

        files_collection.insert_one({
            'user_id': ObjectId(session['user_id']),
            'original_filename': filename,
            'target_format': 'shared',
            'converted_url': download_url,
            'timestamp': datetime.utcnow(),
            'expires_at': expires_at,
            'file_type': 'temporary' if expiry_hours else 'permanent'
        })

        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        logs_collection.insert_one({
            'user_id': user['_id'],
            'username': user.get('username', 'Unknown User'),
            'action': 'file_share',
            'details': f"Shared file: {filename} (Expires in {expiry_hours or '∞'} hrs)",
            'timestamp': datetime.utcnow()
        })

        return jsonify({'download_url': download_url, 'expires_at': expires_at}), 200
    return jsonify({'error': 'File processing failed'}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def api_settings():
    user_id = session['user_id']
    if request.method == 'GET':
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if user:
            return jsonify({
                'notifications': user.get('notifications', True),
                'language': user.get('language', 'en')
            }), 200
        return jsonify({'message': 'User not found'}), 404
    elif request.method == 'POST':
        data = request.get_json()
        update_fields = {}
        if 'notifications' in data:
            update_fields['notifications'] = data['notifications']
        if 'language' in data:
            update_fields['language'] = data['language']
        
        if update_fields:
            users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': update_fields})
            return jsonify({'message': 'Settings updated successfully'}), 200
        return jsonify({'message': 'No settings to update'}), 400

@app.route('/api/stats')
@login_required
def get_user_stats():
    user_id = session['user_id']

    # Count files converted by the user
    files_converted = files_collection.count_documents({'user_id': ObjectId(user_id)})

    # For templates used and files shared, we need to add logging or tracking for these events.
    # For now, let's simulate these stats.
    templates_used = logs_collection.count_documents({'user_id': ObjectId(user_id), 'action': 'template_use'})
    files_shared = logs_collection.count_documents({'user_id': ObjectId(user_id), 'action': 'file_share'})

    return jsonify({
        'templatesUsed': templates_used,
        'filesConverted': files_converted,
        'filesShared': files_shared
    })

def remove_expired_files():
    now = datetime.utcnow()
    expired_files = files_collection.find({'expires_at': {'$lt': now}})
    for file_doc in expired_files:
        filepath = os.path.join(UPLOAD_FOLDER, file_doc['original_filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        files_collection.delete_one({'_id': file_doc['_id']})
        print(f"Deleted expired file: {file_doc['original_filename']}")

scheduler = BackgroundScheduler()
scheduler.add_job(remove_expired_files, 'interval', hours=1)
scheduler.start()

if(__name__ == "__main__"):
    app.run(debug=True)
