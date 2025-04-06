from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from features.audio_download import download_audio
from features.audio_split import split_audio
from features.audio_merge import merge_audio
from features.read_csv import read_csv
import time
from ai.ai_main import generate_ai
from features.download_video import download_highest_quality
from features.download_audio import download_highest_quality_audio

app = Flask(__name__)
# Enable CORS for all routes
CORS(app)

# Clear the temp directory and its subfolders
def clear_temp():
    temp_dir = os.path.join(os.getcwd(), "temp")
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            os.remove(os.path.join(root, file))


def time_to_seconds(time_str):
    """Convert MM:SS or SS format to seconds."""
    if ':' in time_str:
        minutes, seconds = map(int, time_str.split(':'))
        return minutes * 60 + seconds
    return int(time_str)

@app.route("/process-array", methods=["POST"])
def process_array():
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
    
    # Clear previous temp files
    clear_temp()
  
    # Download audio and store filenames
    names = []
    for i, item in enumerate(url_start_end):
        url = item[0]
        download_audio(url, name=str(i))
        names.append(str(i))

    # Split audio files based on start and end times
    for name in names:
        index = int(name)
        start = url_start_end[index][1]
        end = url_start_end[index][2]
        split_audio(f"temp/{name}.m4a", start, end)

    # Merge audio files
    merged_file_path = merge_audio([f"temp/split/{name}.mp3" for name in names])
    
    return jsonify({
        "message": "Audio processing complete! Merged file is ready.",
        "merged_file_path": f"http://localhost:5000/{merged_file_path}"
    })

@app.route("/process-csv", methods=["POST"])
def process_csv():
    # Check if file part exists in the request
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    
    # Check if user submitted an empty file
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Clear previous temp files
    clear_temp()
    
    # Create csv directory if it doesn't exist
    os.makedirs("csv", exist_ok=True)
    
    # Save the uploaded file temporarily
    temp_csv_path = "csv/temp_upload.csv"
    file.save(temp_csv_path)
    
    # Read CSV file
    try:
        url_start_end = read_csv(temp_csv_path)
        
        # Download audio and store filenames
        names = []
        for data in url_start_end:
            url = data[0]
            download_audio(url, name=str(url_start_end.index(data)))
            names.append(str(url_start_end.index(data)))

        # Split audio files based on start and end times
        for name in names:
            index = int(name)
            start = url_start_end[index][1]
            end = url_start_end[index][2]
            split_audio(f"temp/{name}.m4a", start, end)

        # Merge audio files
        merged_file_path = merge_audio([f"temp/split/{name}.mp3" for name in names])
        
        # Optionally remove the temporary CSV file
        os.remove(temp_csv_path)
        
        return jsonify({"message": "Audio processing complete! Merged file is ready.",
                        "merged_file_path": f"http://localhost:5000/{merged_file_path}"})
    except Exception as e:
        return jsonify({"error": f"Error processing CSV: {str(e)}"}), 500


@app.route("/generate-ai", methods=["POST"])
def ai_generation():
    data = request.get_json()
    if not data or not data.get("prompt"):
        return jsonify({"error": "Invalid input. Expected a prompt."}), 400
    
    try:
        # Clear previous temp files
        clear_temp()
        prompt = data["prompt"]
        filepath = generate_ai(prompt)
        return jsonify({"message": "AI content generated successfully!",
                        "filepath": f"http://localhost:5000/{filepath}"})
        
       
    except Exception as e:
        return jsonify({"error": f"Error generating AI content: {str(e)}"}), 500


@app.route("/download-video", methods=["POST"])
def download_video():
    data = request.get_json()
    if not data or not data.get("url"):
        return jsonify({"error": "Invalid input. Expected a URL."}), 400
    
    url = data["url"]
    path = "static/video_dl"
    
    try:
        # Clear previous temp files
        clear_temp()
        
        # Download video and audio
        path = download_highest_quality(url, path)
        
        return jsonify({"message": "Video downloaded successfully!",
                        "filepath": f"http://localhost:5000/{path}"})
    except Exception as e:
        return jsonify({"error": f"Error downloading video: {str(e)}"}), 500

@app.route("/download-audio", methods=["POST"])
def audio_download():
    data = request.get_json()
    if not data or not data.get("url"):
        return jsonify({"error": "Invalid input. Expected a URL."}), 400
    
    url = data["url"]
    path = "static/audio_dl"
    
    try:
        # Clear previous temp files
        clear_temp()
        
        # Download video and audio
        path = download_highest_quality_audio(url, path)
        
        return jsonify({"message": "Audio downloaded successfully!",
                        "filepath": f"http://localhost:5000/{path}"})
    except Exception as e:
        return jsonify({"error": f"Error downloading audio: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)
