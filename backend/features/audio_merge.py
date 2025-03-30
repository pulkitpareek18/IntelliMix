from pydub import AudioSegment
import time
import os

def merge_audio(list_of_audio_files, crossfade_duration=3000):
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
    
    # Save the combined audio
    output_file = f"static/output/combined_audio_{int(time.time())}.mp3"
    combined_audio.export(output_file, format="mp3")
    print(f"Audio combined successfully with {crossfade_duration//1000} second crossfade!")
    print(f"Output saved to: {output_file}")
    return output_file