from pydub import AudioSegment
import os

def split_audio(audio_file, start_time, end_time, output_dir="temp/split"):
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load audio file (MP3 or WAV)
    audio = AudioSegment.from_file(audio_file, format="m4a")

    # Define start and end times in milliseconds
    start_time = start_time * 1000
    end_time = end_time * 1000

    # Extract segment
    split_audio = audio[start_time:end_time]

    # Get base filename without directory part
    base_filename = os.path.basename(audio_file).replace(".m4a", ".mp3")
    output_file = os.path.join(output_dir, base_filename)
    
    # Save the split audio as MP3
    split_audio.export(output_file, format="mp3")
    print(f"Audio split and converted to {output_file} successfully!")
    
    return output_file