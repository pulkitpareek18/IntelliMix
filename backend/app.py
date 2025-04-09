from flask import Flask, request, jsonify, url_for, session
from flask_cors import CORS
import os
import time
import json
from functools import wraps
from features.audio_download import download_audio
from features.audio_split import split_audio
from features.audio_merge import merge_audio
from features.read_csv import read_csv
from ai.ai_main import generate_ai
from features.download_video import download_highest_quality
from features.download_audio import download_highest_quality_audio
from session_manager import SessionManager
from flask import send_file

app = Flask(__name__)
# Use a fixed secret key instead of a random one to ensure consistency across restarts
app.secret_key = 'intellimix-fixed-secret-key'  # Replace with a strong fixed key in production
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 300  # 5 minutes in seconds
app.config['SESSION_COOKIE_SAMESITE'] = 'None'  # or 'None' if your frontend is on a different domain
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True

# Update CORS settings to ensure cookies are handled correctly
CORS(app, 
     supports_credentials=True,
     resources={r"/*": {"origins": "*"}},  # Replace with your frontend domain in production 
     expose_headers=["Content-Disposition"],
     allow_headers=["Content-Type", "Authorization"])

# Initialize session manager
session_manager = SessionManager()

# Session management middleware
def with_session(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check if session exists, create if it doesn't
        if 'session_id' not in session:
            session['session_id'] = session_manager.create_session()
        
        # Add session_id to the function's keyword arguments
        kwargs['session_id'] = session['session_id']
        return f(*args, **kwargs)
    return decorated

# Function to get the base URL
def get_base_url():
    """Get the base URL dynamically based on the request environment"""
    if request.environ.get('HTTP_X_FORWARDED_HOST'):
        host = request.environ['HTTP_X_FORWARDED_HOST']
        protocol = request.environ.get('HTTP_X_FORWARDED_PROTO', 'http')
        return f"{protocol}://{host}"
    else:
        return request.host_url.rstrip('/')

# Session-aware file operations
def get_session_path(session_id, relative_path):
    """Convert a relative path to a session-specific absolute path"""
    session_dir = session_manager.get_session_dir(session_id)
    if not session_dir:
        raise Exception("Invalid session")
    return os.path.join(session_dir, relative_path)

def time_to_seconds(time_str):
    """Convert MM:SS or SS format to seconds."""
    if ':' in time_str:
        minutes, seconds = map(int, time_str.split(':'))
        return minutes * 60 + seconds
    return int(time_str)

@app.route("/process-array", methods=["POST"])
@with_session
def process_array(session_id):
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
    
    # Extract parameters from JSON body and convert times to seconds
    urls = data.get("urls", [])
    url_start_end = [
        [item.get("url"), time_to_seconds(item.get("start")), time_to_seconds(item.get("end"))] 
        for item in urls
    ]
    
    # Validate the input
    if not url_start_end:
        return jsonify({"error": "No URLs provided"}), 400
    
    # Clear previous temp files for this session
    session_manager.clear_session_temp(session_id)
    session_manager.clear_session_output(session_id)
    
    # Get session-specific paths
    temp_dir = get_session_path(session_id, "temp")
    temp_split_dir = get_session_path(session_id, "temp/split")
    
    # Download audio and store filenames
    names = []
    for i, item in enumerate(url_start_end):
        url = item[0]
        # Use session-specific temp directory
        download_audio(url, name=str(i), output_dir=temp_dir)
        names.append(str(i))

    # Split audio files based on start and end times
    for name in names:
        index = int(name)
        start = url_start_end[index][1]
        end = url_start_end[index][2]
        # Use session-specific temp directory
        split_audio(f"{temp_dir}/{name}.m4a", start, end, output_dir=temp_split_dir)

    # Merge audio files with session-specific paths
    split_files = [f"{temp_split_dir}/{name}.mp3" for name in names]
    output_dir = get_session_path(session_id, "static/output")
    merged_file_path = merge_audio(split_files, output_dir=output_dir)
    
    # Generate a URL that includes the session ID for retrieval
    file_url = f"{get_base_url()}/files/{session_id}/{os.path.basename(merged_file_path)}"
    
    return jsonify({
        "message": "Audio processing complete! Merged file is ready.",
        "merged_file_path": file_url,
        "session_id": session_id
    })

@app.route("/process-csv", methods=["POST"])
@with_session
def process_csv(session_id):
    # Check if file part exists in the request
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    
    # Check if user submitted an empty file
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Clear previous files for this session
    session_manager.clear_session_temp(session_id)
    session_manager.clear_session_output(session_id)
    
    # Get session-specific paths
    csv_dir = get_session_path(session_id, "csv")
    temp_dir = get_session_path(session_id, "temp")
    temp_split_dir = get_session_path(session_id, "temp/split")
    
    # Save the uploaded file to session's CSV directory
    temp_csv_path = os.path.join(csv_dir, "temp_upload.csv")
    file.save(temp_csv_path)
    
    try:
        url_start_end = read_csv(temp_csv_path)
        
        # Download audio and store filenames
        names = []
        for data in url_start_end:
            url = data[0]
            idx = url_start_end.index(data)
            # Use session-specific temp directory
            download_audio(url, name=str(idx), output_dir=temp_dir)
            names.append(str(idx))

        # Split audio files based on start and end times
        for name in names:
            index = int(name)
            start = url_start_end[index][1]
            end = url_start_end[index][2]
            # Use session-specific paths
            split_audio(f"{temp_dir}/{name}.m4a", start, end, output_dir=temp_split_dir)

        # Merge audio files with session-specific paths
        split_files = [f"{temp_split_dir}/{name}.mp3" for name in names]
        output_dir = get_session_path(session_id, "static/output")
        merged_file_path = merge_audio(split_files, output_dir=output_dir)
        
        # Generate a URL that includes the session ID for retrieval
        file_url = f"{get_base_url()}/files/{session_id}/{os.path.basename(merged_file_path)}"
        
        return jsonify({
            "message": "Audio processing complete! Merged file is ready.",
            "merged_file_path": file_url,
            "session_id": session_id
        })
    
    except Exception as e:
        return jsonify({"error": f"Error processing CSV: {str(e)}"}), 500

@app.route("/generate-ai", methods=["POST"])
@with_session
def ai_generation(session_id):
    data = request.get_json()
    if not data or not data.get("prompt"):
        return jsonify({"error": "Invalid input. Expected a prompt."}), 400
    
    try:
        # Clear previous files for this session
        session_manager.clear_session_temp(session_id)
        session_manager.clear_session_output(session_id)
        
        # Get session directory
        session_dir = session_manager.get_session_dir(session_id)
        
        prompt = data["prompt"]
        # Pass session directory to generate_ai for session-specific work
        filepath = generate_ai(prompt, session_dir=session_dir)
        
        # Generate a URL that includes the session ID for retrieval
        file_url = f"{get_base_url()}/files/{session_id}/{os.path.basename(filepath)}"
        
        return jsonify({
            "message": "AI content generated successfully!",
            "filepath": file_url,
            "session_id": session_id
        })
        
    except Exception as e:
        return jsonify({"error": f"Error generating AI content: {str(e)}"}), 500

@app.route("/download-video", methods=["POST"])
@with_session
def download_video(session_id):
    data = request.get_json()
    if not data or not data.get("url"):
        return jsonify({"error": "Invalid input. Expected a URL."}), 400
    
    url = data["url"]
    output_dir = get_session_path(session_id, "static/video_dl")
    
    try:
        # Clear previous files for this session
        session_manager.clear_session_temp(session_id)
        session_manager.clear_session_output(session_id)
        
        # Download video to session-specific directory
        path = download_highest_quality(url, output_dir)
        
        # Generate URL for accessing the file
        filename = os.path.basename(path)
        file_url = f"{get_base_url()}/files/{session_id}/{filename}"
        
        return jsonify({
            "message": "Video downloaded successfully!",
            "filepath": file_url,
            "session_id": session_id
        })
    
    except Exception as e:
        return jsonify({"error": f"Error downloading video: {str(e)}"}), 500

@app.route("/download-audio", methods=["POST"])
@with_session
def audio_download(session_id):
    data = request.get_json()
    if not data or not data.get("url"):
        return jsonify({"error": "Invalid input. Expected a URL."}), 400
    
    url = data["url"]
    output_dir = get_session_path(session_id, "static/audio_dl")
    
    try:
        # Clear previous files for this session
        session_manager.clear_session_temp(session_id)
        session_manager.clear_session_output(session_id)
        
        # Download audio to session-specific directory
        path = download_highest_quality_audio(url, output_dir)
        
        # Generate URL for accessing the file
        filename = os.path.basename(path)
        file_url = f"{get_base_url()}/files/{session_id}/{filename}"
        
        return jsonify({
            "message": "Audio downloaded successfully!",
            "filepath": file_url,
            "session_id": session_id
        })
    
    except Exception as e:
        return jsonify({"error": f"Error downloading audio: {str(e)}"}), 500

# Serve files from session directories
@app.route("/files/<session_id>/<filename>")
def serve_file(session_id, filename):
    session_dir = session_manager.get_session_dir(session_id)
    if not session_dir:
        return jsonify({"error": "Invalid session"}), 404
    
    # Look for the file in various output directories
    possible_paths = [
        os.path.join(session_dir, "static", "output", filename),
        os.path.join(session_dir, "static", "audio_dl", filename),
        os.path.join(session_dir, "static", "video_dl", filename)
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return send_file(path)
    
    return jsonify({"error": "File not found"}), 404













@app.route("/debug/session", methods=["GET"])
def debug_session():
    """Debug endpoint to check current session"""
    if 'session_id' in session:
        session_id = session['session_id']
        session_dir = session_manager.get_session_dir(session_id)
        return jsonify({
            "session_id": session_id,
            "has_directory": session_dir is not None,
            "all_keys_in_session": list(session.keys())
        })
    else:
        return jsonify({
            "message": "No session_id in session",
            "all_keys_in_session": list(session.keys())
        })

@app.route("/debug/new-session", methods=["GET"])
def debug_new_session():
    """Force create a new session for testing"""
    if 'session_id' in session:
        old_session_id = session['session_id']
        session.pop('session_id')
    else:
        old_session_id = None
    
    session['session_id'] = session_manager.create_session()
    
    return jsonify({
        "message": "New session created",
        "old_session_id": old_session_id,
        "new_session_id": session['session_id']
    })

@app.route("/debug/all-sessions", methods=["GET"])
def debug_all_sessions():
    """List all active sessions (admin only)"""
    return jsonify({
        "active_sessions_count": len(session_manager.sessions),
        "session_ids": list(session_manager.sessions.keys())
    })















if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)