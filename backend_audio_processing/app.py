from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from features.audio_download import download_audio
from features.audio_split import split_audio
from features.audio_merge import merge_audio
from features.read_csv import read_csv

app = Flask(__name__)
# Enable CORS for all routes
CORS(app)

# Clear the temp directory and its subfolders
def clear_temp():
    temp_dir = os.path.join(os.getcwd(), "temp")
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            os.remove(os.path.join(root, file))


@app.route("/process-array", methods=["POST"])
def process_array():
    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({"error": "Invalid input. Expected a nested array."}), 400

    # Clear previous temp files
    clear_temp()

    # Download audio and store filenames
    names = []
    for item in data:
        url, start, end = item
        download_audio(url, name=str(data.index(item)))
        names.append(str(data.index(item)))

    # Split audio files based on start and end times
    for name in names:
        index = int(name)
        start = data[index][1]
        end = data[index][2]
        split_audio(f"temp/{name}.m4a", start, end)

    # Merge audio files
    merge_audio([f"temp/split/{name}.mp3" for name in names])
    return jsonify({"message": "Audio processing complete! Merged file is ready."})


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


if __name__ == "__main__":
    app.run(debug=True)
