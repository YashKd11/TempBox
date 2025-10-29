import os
from flask import Flask, request, render_template, redirect, session, url_for, jsonify, send_from_directory, flash
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId # To work with MongoDB's default _id
from datetime import datetime

app = Flask(__name__)
# A static secret key is required to keep sessions persistent across server restarts.
# The previous key `os.urandom(24)` generated a new key on each restart, invalidating all sessions.
# In a production environment, this should be loaded from an environment variable for security.
app.secret_key = 'a-very-secret-and-static-key-for-development'

# MongoDB Configuration
MONGO_URI = "mongodb+srv://:@clustertest.qwyt70x.mongodb.net/" # Replace with your MongoDB connection string if different
client = MongoClient(MONGO_URI)
db = client.tempbox_db # Your database name
users_collection = db.users # Collection for users
files_collection = db.files # Collection for files (for converter, etc.)
logs_collection = db.logs # Collection for logs
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
            'avatar': None
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
    target_format = request.form.get('target', 'server')

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        # For a real application, you'd save the file securely,
        # perform conversion (e.g., using libraries like Pillow for images,
        # or external tools for other formats), and then return a download link.
        # For this example, we'll just simulate saving and returning a dummy URL.

        filename = file.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # Simulate conversion and generate a download URL
        # In a real scenario, this would be a link to the converted file
        # and the conversion would happen here.
        download_url = url_for('download_converted_file', filename=filename, _external=True)

        # You might want to store metadata about the conversion in files_collection
        files_collection.insert_one({
            'user_id': ObjectId(session['user_id']),
            'original_filename': filename,
            'target_format': target_format,
            'converted_url': download_url,
            'timestamp': datetime.utcnow()
        })

        user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        # --- Add File Convert Log ---
        logs_collection.insert_one({
            'user_id': user['_id'],
            'username': user.get('username', 'Unknown User'),
            'action': 'file_convert',
            'details': f"Converted '{filename}' to '{target_format}'",
            'timestamp': datetime.utcnow()
        })

        return jsonify({'download_url': download_url}), 200
    return jsonify({'error': 'File processing failed'}), 500

# Route to serve converted files (for demonstration)
@app.route('/downloads/<filename>')
@login_required
def download_converted_file(filename):
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

if(__name__ == "__main__"):
    app.run(debug=True)
