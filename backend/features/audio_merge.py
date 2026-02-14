import os
import time
from collections.abc import Sequence

from pydub import AudioSegment


def _normalized_crossfades(
    crossfade_duration: int | float | Sequence[int | float],
    transition_count: int,
) -> list[int]:
    if transition_count <= 0:
        return []

    if isinstance(crossfade_duration, Sequence) and not isinstance(crossfade_duration, (str, bytes)):
        raw_values = [int(max(0, float(value))) for value in crossfade_duration]
        if not raw_values:
            raw_values = [0]
        if len(raw_values) < transition_count:
            raw_values.extend([raw_values[-1]] * (transition_count - len(raw_values)))
        return raw_values[:transition_count]

    value = int(max(0, float(crossfade_duration)))
    return [value for _ in range(transition_count)]


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

    transition_crossfades = _normalized_crossfades(crossfade_duration, len(audio_files) - 1)

    # Append the rest with transition-aware crossfades.
    for transition_index, audio in enumerate(audio_files[1:]):
        requested_crossfade = transition_crossfades[transition_index]
        max_allowed_crossfade = max(0, min(len(combined_audio), len(audio)) - 1)
        effective_crossfade = min(requested_crossfade, max_allowed_crossfade)
        combined_audio = combined_audio.append(audio, crossfade=effective_crossfade)
    
    # Generate output filename with timestamp
    output_filename = f"combined_audio_{int(time.time())}.mp3"
    output_file = os.path.join(output_dir, output_filename)
    
    # Save the combined audio
    combined_audio.export(output_file, format="mp3")
    if transition_crossfades:
        display_crossfades = ", ".join(f"{value / 1000:.2f}s" for value in transition_crossfades)
        print(f"Audio combined successfully with crossfades: [{display_crossfades}]")
    else:
        print("Audio combined successfully with no crossfade.")
    print(f"Output saved to: {output_file}")
    
    return output_file
