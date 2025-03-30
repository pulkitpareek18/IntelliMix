import os
import sys

# Ensure that the current directory (ai/) is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Ensure that the parent directory (backend/) is in the path
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now import the modules
from ai.ai import generate  # Use fully qualified module paths
from ai.analyze_json import analyze_mix
from ai.search import get_youtube_url
from features.audio_download import download_audio
from features.audio_split import split_audio
from features.audio_merge import merge_audio


def generate_ai(prompt):

    generate(prompt)
    title_artist_start_end = analyze_mix()

    url_start_end = []

    for i in title_artist_start_end:
        title = i[0]
        artist = i[1]
        start_time = i[2]
        end_time = i[3]

        url = get_youtube_url(title, artist)
        url_start_end.append([url,start_time,end_time])




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

    print(merged_file_path)
    return merged_file_path