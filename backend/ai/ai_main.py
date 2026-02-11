import os
import sys

# Ensure that the current directory (ai/) is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Ensure that the parent directory (backend/) is in the path
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ai.ai import generate
from ai.analyze_json import analyze_mix
from ai.search import get_youtube_url
from features.audio_download import download_audio
from features.audio_merge import merge_audio
from features.audio_split import split_audio


def generate_ai(prompt: str, session_dir: str | None = None) -> str:
    if session_dir:
        temp_dir = os.path.join(session_dir, "temp")
        temp_split_dir = os.path.join(session_dir, "temp", "split")
        output_dir = os.path.join(session_dir, "static", "output")
        json_path = os.path.join(session_dir, "audio_data.json")
    else:
        temp_dir = "temp"
        temp_split_dir = "temp/split"
        output_dir = "static/output"
        json_path = "audio_data.json"

    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(temp_split_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    generate(prompt, json_path=json_path)
    title_artist_start_end = analyze_mix(file_path=json_path)

    if not title_artist_start_end:
        raise RuntimeError("AI output did not produce any songs")

    url_start_end: list[list[int | str]] = []
    for title, artist, start_time, end_time in title_artist_start_end:
        url = get_youtube_url(title, artist)
        if url:
            url_start_end.append([url, start_time, end_time])

    if not url_start_end:
        raise RuntimeError("Could not find playable YouTube URLs for generated songs")

    for index, item in enumerate(url_start_end):
        download_audio(item[0], name=str(index), output_dir=temp_dir)

    for index, item in enumerate(url_start_end):
        start = int(item[1])
        end = int(item[2])
        if end <= start:
            raise RuntimeError("Generated timestamp range is invalid")
        split_audio(os.path.join(temp_dir, f"{index}.m4a"), start, end, output_dir=temp_split_dir)

    split_files = [os.path.join(temp_split_dir, f"{index}.mp3") for index in range(len(url_start_end))]
    merged_file_path = merge_audio(split_files, output_dir=output_dir)

    if not merged_file_path:
        raise RuntimeError("Audio merge failed")

    return merged_file_path
