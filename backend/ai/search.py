import os
import re
import sys
from math import log10
from typing import Any

from pytubefix import Search

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proxies import proxies

NEGATIVE_HINTS = {
    "short",
    "shorts",
    "status",
    "lyric",
    "lyrics",
    "slowed",
    "reverb",
    "sped",
    "nightcore",
    "lofi",
    "8d",
    "edit",
    "cover",
    "karaoke",
    "instrumental",
    "snippet",
}

POSITIVE_HINTS = {
    "official",
    "official video",
    "music video",
    "full song",
    "audio",
    "topic",
}


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= 2}


def _candidate_score(video: Any, title: str, artist: str) -> float:
    target_title_tokens = _tokenize(title)
    target_artist_tokens = _tokenize(artist)

    video_title = str(getattr(video, "title", "") or "")
    channel_name = str(getattr(video, "author", "") or "")
    metadata_text = f"{video_title} {channel_name}".lower()
    metadata_tokens = _tokenize(metadata_text)

    title_overlap = len(target_title_tokens & metadata_tokens) / max(1, len(target_title_tokens))
    artist_overlap = len(target_artist_tokens & metadata_tokens) / max(1, len(target_artist_tokens))

    score = (title_overlap * 3.2) + (artist_overlap * 2.4)

    lowered_title = video_title.lower()
    lowered_text = metadata_text.lower()
    for hint in POSITIVE_HINTS:
        if hint in lowered_text:
            score += 0.55
    for hint in NEGATIVE_HINTS:
        if hint in lowered_title:
            score -= 1.05

    watch_url = str(getattr(video, "watch_url", "") or "")
    if "/shorts/" in watch_url:
        score -= 2.5

    length_seconds = getattr(video, "length", None)
    try:
        length_seconds = int(length_seconds) if length_seconds is not None else None
    except (TypeError, ValueError):
        length_seconds = None
    if length_seconds is not None:
        if length_seconds < 90:
            score -= 3.0
        elif length_seconds < 150:
            score -= 1.4
        elif 150 <= length_seconds <= 520:
            score += 0.85

    view_count = getattr(video, "views", None)
    try:
        view_count = int(view_count) if view_count is not None else None
    except (TypeError, ValueError):
        view_count = None
    if view_count and view_count > 0:
        score += min(log10(float(view_count + 1)) * 0.12, 0.85)

    if title_overlap < 0.2:
        score -= 1.3
    if artist_overlap < 0.15:
        score -= 0.7

    return score


def get_youtube_url(title, artist):
    """
    Search for a song on YouTube based on title and artist name, then return its URL.
    
    Args:
        title (str): The title of the song
        artist (str): The name of the artist
        
    Returns:
        str: URL of the first search result, or None if no results found
    """
    try:
        query = f"{title} {artist} official full song"
        search_results = Search(query, proxies=proxies).videos

        if not search_results:
            return None

        best_result = None
        best_score = float("-inf")
        for candidate in search_results[:12]:
            score = _candidate_score(candidate, str(title), str(artist))
            if score > best_score:
                best_score = score
                best_result = candidate

        selected = best_result or search_results[0]
        video_id = getattr(selected, "video_id", None)
        if not video_id:
            return None
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        return video_url
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

# Example usage
if __name__ == "__main__":
    # Test the function
    test_title = "angrezi beat"
    test_artist = "honey singh"
    
    result = get_youtube_url(test_title, test_artist)
    print(f"URL: {result}")
