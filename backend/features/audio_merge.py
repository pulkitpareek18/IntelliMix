from pydub import AudioSegment
import time
import os

def merge_audio(list_of_audio_files, crossfade_duration=3000, output_dir="static/output"):
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the audio files
    audio_files = []
    for audio_file in list_of_audio_files:
        audio_files.append(AudioSegment.from_file(audio_file, format="mp3"))
    
    # Check if we have files to merge
    if not audio_files:
        print("No audio files to merge.")
        return
    
    # Start with the first audio file
    combined_audio = audio_files[0]
    
    # Append the rest with crossfade
    for audio in audio_files[1:]:
        combined_audio = combined_audio.append(audio, crossfade=crossfade_duration)
    
    # Generate output filename with timestamp
    output_filename = f"combined_audio_{int(time.time())}.mp3"
    output_file = os.path.join(output_dir, output_filename)
    
    # Save the combined audio
    combined_audio.export(output_file, format="mp3")
    print(f"Audio combined successfully with {crossfade_duration//1000} second crossfade!")
    print(f"Output saved to: {output_file}")
    
    return output_file