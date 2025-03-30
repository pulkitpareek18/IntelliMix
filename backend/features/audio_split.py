from pydub import AudioSegment

def split_audio(audio_file, start_time, end_time):
    # Load audio file (MP3 or WAV)
    audio = AudioSegment.from_file(audio_file, format="m4a")

    # Define start and end times in milliseconds
    start_time = start_time * 1000
    end_time = end_time * 1000

    # Extract segment
    split_audio = audio[start_time:end_time]

    # Save the split audio as MP3
    output_file = audio_file.replace(".m4a", ".mp3").replace("temp/", "temp/split/")
    split_audio.export(output_file, format="mp3")
    print(f"Audio split and converted to {output_file} successfully!")
