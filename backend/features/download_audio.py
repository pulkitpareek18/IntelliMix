import os
import moviepy.editor
from pytubefix import YouTube
from tqdm import tqdm
import re
import uuid

def sanitize_filename(filename):
    """Sanitize the filename to remove characters that might cause issues."""
    # Replace problematic characters with underscore
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", filename)
    # Limit filename length
    if len(sanitized) > 100:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:100] + ext
    return sanitized

def download_highest_quality_audio(url, path):
    try:
        def progress_callback(stream, data_chunk, bytes_remaining):
            pbar.update(len(data_chunk) // 10 ** 6)

        yt = YouTube(url)
        yt.register_on_progress_callback(progress_callback)
        streams = yt.streams

        # Get the highest bitrate audio stream (mp4 format)
        audio_stream = streams.filter(progressive=False, type="audio", file_extension="mp4")
        audio_stream = audio_stream.order_by("abr").desc().first()
        
        # Generate safer filenames
        video_title = sanitize_filename(yt.title)
        unique_id = str(uuid.uuid4())[:8]  # Add a unique ID to avoid conflicts
        
        # Create a sanitized filename
        audio_filename = f"{video_title}-{audio_stream.abr}.mp4"
        final_filename = sanitize_filename(audio_filename)
        
        # Ensure the directory exists
        os.makedirs(path, exist_ok=True)

        # Check if the file already exists
        if final_filename in os.listdir(path):
            print(f"Already available: {final_filename}")
            return f"static/audio_dl/{final_filename}"

        print(f"Downloading: {video_title} ({audio_stream.abr})")
        pbar = tqdm(total=audio_stream.filesize // 10 ** 6, unit="MB")

        # Download audio stream
        audio_stream.download(output_path=path, filename=final_filename)
        pbar.close()

        print(f"Downloaded: {final_filename}")
        return f"static/audio_dl/{final_filename}"

    except Exception as e:
        print(f"Error occurred: {e}")
        return None