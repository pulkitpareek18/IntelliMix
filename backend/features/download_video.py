import os
import moviepy.editor
from pytubefix import YouTube
from tqdm import tqdm
import re
import uuid
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proxies import get_working_proxy

def sanitize_filename(filename):
    """Sanitize the filename to remove characters that might cause issues."""
    # Replace problematic characters with underscore
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", filename)
    # Limit filename length
    if len(sanitized) > 100:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:100] + ext
    return sanitized

def download_highest_quality(url, path):
    try:
        def progress_callback(stream, data_chunk, bytes_remaining):
            pbar.update(len(data_chunk) // 10 ** 6)

        # Add proxies to YouTube instance
        yt = YouTube(url, proxies=get_working_proxy())
        yt.register_on_progress_callback(progress_callback)
        streams = yt.streams

        # Get the highest resolution video stream (webm format)
        video_stream = streams.filter(progressive=False, type="video", file_extension="webm")
        video_stream = video_stream.order_by("resolution").desc().first()

        # Get the highest bitrate audio stream (mp4 format)
        audio_stream = streams.filter(progressive=False, type="audio", file_extension="mp4")
        audio_stream = audio_stream.order_by("abr").desc().first()

        # Generate safer filenames
        video_title = sanitize_filename(yt.title)
        unique_id = str(uuid.uuid4())[:8]  # Add a unique ID to avoid conflicts
        
        video_filename = f"{unique_id}-video.webm"
        audio_filename = f"{unique_id}-audio.mp4"
        output_filename = f"{video_title}-{video_stream.resolution}.mp4"
        final_filename = sanitize_filename(output_filename)

        # Ensure the directory exists
        os.makedirs(path, exist_ok=True)

        # Check if the file already exists
        if final_filename in os.listdir(path):
            print(f"Already available: {final_filename}")
            return f"static/video_dl/{final_filename}"

        print(f"Downloading: {video_title} ({video_stream.resolution})")
        pbar = tqdm(total=video_stream.filesize // 10 ** 6, unit="MB")

        # Download video and audio streams
        video_stream.download(output_path=path, filename=video_filename)
        pbar.close()
        audio_stream.download(output_path=path, filename=audio_filename)

        # Full paths for FFmpeg
        video_path = os.path.join(path, video_filename)
        audio_path = os.path.join(path, audio_filename)
        output_path = os.path.join(path, final_filename)

        print("Merging video and audio...")
        # Merge audio and video into a single mp4 file
        try:
            moviepy.video.io.ffmpeg_tools.ffmpeg_merge_video_audio(
                video_path,
                audio_path,
                output_path
            )
        except Exception as e:
            print(f"FFmpeg merge error: {e}")
            # Alternative method using moviepy
            try:
                video_clip = moviepy.editor.VideoFileClip(video_path)
                audio_clip = moviepy.editor.AudioFileClip(audio_path)
                final_clip = video_clip.set_audio(audio_clip)
                final_clip.write_videofile(output_path, codec='libx264')
                video_clip.close()
                audio_clip.close()
                final_clip.close()
            except Exception as e2:
                print(f"MoviePy merge error: {e2}")
                raise

        # Clean up temporary files
        try:
            os.remove(video_path)
            os.remove(audio_path)
        except Exception as e:
            print(f"Warning: Could not remove temporary files: {e}")

        print(f"Downloaded: {final_filename}")
        return f"static/video_dl/{final_filename}"

    except Exception as e:
        print(f"Error occurred: {e}")
        return None