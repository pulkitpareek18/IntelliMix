import json
import logging
import math
import os
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from statistics import median
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

# Ensure that the current directory (ai/) is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Ensure that the parent directory (backend/) is in the path
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ai.ai import AIServiceError, generate, generate_with_instruction
from ai.analyze_json import analyze_mix
from ai.search import get_youtube_url
from features.audio_download import download_audio
from features.audio_merge import merge_audio
from pydub import AudioSegment

LOGGER = logging.getLogger(__name__)

LLM_CANDIDATE_SELECTION_SYSTEM_INSTRUCTION = """
You are selecting remix timestamps for each track.

Input provides:
- user_prompt
- ordered tracks
- for each track: candidate segments aligned to beat/section boundaries with DSP metadata (bpm, key, waveform dynamics)

Output strict JSON only:
{
  "selections": [
    {
      "track_index": 0,
      "candidate_id": "t0c1",
      "reason": "Short reason"
    }
  ]
}

Rules:
- Pick exactly one candidate_id for each track_index present.
- Prefer smooth narrative flow with user prompt relevance.
- Prefer better drop_strength and higher transition quality.
- Prefer harmonic compatibility (key), stable tempo continuity, and section-aligned cuts.
- Avoid abrupt energy cliffs unless prompt explicitly asks for dramatic contrast.
"""

LLM_TIMESTAMPED_LYRICS_SYSTEM_INSTRUCTION = """
You are planning exact remix cut points using timestamped lyrics.

Input provides:
- user_prompt
- script_lines: ordered lines from "mixing way"
- tracks with timestamped lyrics entries

Output strict JSON only:
{
  "segments": [
    {
      "script_index": 0,
      "track_index": 0,
      "start_seconds": 12.3,
      "end_seconds": 24.8,
      "confidence": 0.91,
      "reason": "Brief reason"
    }
  ]
}

Rules:
- Return one segment for every script_index.
- Preserve script order in output.
- Keep consecutive lines on the same track unless there is a clear lyrical shift.
- Do not alternate tracks line-by-line unless the script explicitly alternates.
- Pick timestamps that best match each script line semantically and linguistically.
- Keep segment length between 8 and 28 seconds when possible.
- Prefer lyrical continuity across adjacent script lines.
- If exact match is unavailable, select the closest lyrical/phonetic equivalent.
"""

LLM_MIX_INTENT_SYSTEM_INSTRUCTION = """
You are an AI audio engineer deciding creative mix directives from a user prompt.

Output strict JSON only:
{
  "strategy": "creative_mix",
  "use_timestamped_lyrics": false,
  "target_total_duration_seconds": 600,
  "target_segment_duration_seconds": 34,
  "global_crossfade_seconds": 2.0,
  "transition_crossfade_seconds": [2.0, 3.0],
  "overlap_seconds": [],
  "track_windows": [
    {"track_index": 0, "start_seconds": 20, "end_seconds": 52}
  ],
  "reason": "short reason"
}

Rules:
- Always choose "creative_mix".
- Always set use_timestamped_lyrics=false.
- If user asks for a total duration (e.g., "10 minute mix"), set target_total_duration_seconds accordingly.
- If user gives specific fade/crossfade or overlap instructions, capture them.
- transition_crossfade_seconds should describe transitions between adjacent output segments.
- track_windows is optional and should only be included when user gave explicit cut positions.
- Prefer 0-based track_index, but if uncertain keep best mapping to provided tracks.
- Keep target_segment_duration_seconds in [14, 70].
- Keep target_total_duration_seconds in [60, 3600] when provided.
- Keep crossfade/overlap values in [0, 8] seconds.
"""

LYRICS_STOPWORDS = {
    "the",
    "and",
    "that",
    "this",
    "with",
    "from",
    "your",
    "you",
    "are",
    "for",
    "all",
    "was",
    "were",
    "have",
    "has",
    "had",
    "not",
    "but",
    "what",
    "when",
    "how",
    "why",
    "can",
    "could",
    "would",
    "should",
    "they",
    "them",
    "their",
    "there",
    "just",
    "into",
    "than",
    "then",
    "out",
    "our",
    "about",
    "love",
    "yeah",
    "baby",
    "wanna",
    "gonna",
    "nah",
    "hey",
    "ooo",
}

POSITIVE_WORDS = {
    "joy",
    "happy",
    "party",
    "dance",
    "shine",
    "win",
    "smile",
    "celebrate",
    "alive",
    "dream",
    "freedom",
    "good",
    "great",
    "fun",
}

NEGATIVE_WORDS = {
    "sad",
    "pain",
    "broken",
    "cry",
    "alone",
    "hurt",
    "dark",
    "fall",
    "lost",
    "fear",
    "cold",
    "bad",
    "hate",
    "tears",
}

PITCH_CLASS_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class _WorkspacePaths:
    temp_dir: str
    temp_split_dir: str
    output_dir: str
    json_path: str


@dataclass
class _SongPlanItem:
    title: str
    artist: str
    url: str
    suggested_start: int
    suggested_end: int
    anchor_ratio: float | None = None
    requested_duration_seconds: int | None = None
    forced_start_ms: int | None = None
    forced_end_ms: int | None = None


@dataclass
class _LyricsProfile:
    keywords: frozenset[str]
    positivity: float
    has_lyrics: bool
    excerpt: str


@dataclass
class _TrackSource:
    plan: _SongPlanItem
    source_path: str
    source_index: int
    prompt_relevance: float = 0.0
    lyrics_profile: _LyricsProfile | None = None


@dataclass
class _ScriptLineMatch:
    track_index: int
    anchor_ratio: float
    confidence: float


@dataclass
class _ScriptSegmentMatch:
    track_index: int
    anchor_ratio: float
    confidence: float
    line_count: int
    text: str


@dataclass
class _TimestampedLyricLine:
    text: str
    start_seconds: float
    end_seconds: float
    confidence: float
    source: str


@dataclass
class _PlannedTimedSegment:
    script_index: int
    track_index: int
    start_seconds: float
    end_seconds: float
    confidence: float


@dataclass
class _TrackWindowDirective:
    track_index: int
    start_seconds: float | None = None
    end_seconds: float | None = None


@dataclass
class _MixIntentPlan:
    strategy: str
    use_timestamped_lyrics: bool
    target_segment_duration_seconds: int
    global_crossfade_seconds: float | None
    transition_crossfade_seconds: list[float]
    track_windows: list[_TrackWindowDirective]
    target_total_duration_seconds: int | None = None
    reason: str = ""


@dataclass
class _TrackDSPProfile:
    beat_interval_ms: int
    bpm: float
    key_index: int
    key_scale: str
    key_name: str
    key_confidence: float
    frame_ms: int
    energy_frames: list[float]
    section_boundaries_ms: list[int]


@dataclass
class _SegmentCandidate:
    candidate_id: str
    track_index: int
    start_ms: int
    end_ms: int
    energy_db: float
    drop_strength: float
    transition_quality: float
    beat_interval_ms: int = 500
    bpm: float = 120.0
    key_index: int = -1
    key_scale: str = "unknown"
    key_name: str = "unknown"
    key_confidence: float = 0.0
    section_alignment: float = 0.0
    waveform_dynamics: float = 0.0


@dataclass
class _MixReviewResult:
    approved: bool
    reasons: list[str]
    duration_seconds: float
    minimum_required_seconds: float
    segment_count: int


def _safe_dbfs(segment: AudioSegment) -> float:
    value = segment.dBFS
    if value == float("-inf"):
        return -80.0
    return float(value)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _resolve_bool_env(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _resolve_float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        return default
    return _clamp(parsed, minimum, maximum)


def _resolve_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return default
    return int(_clamp(parsed, minimum, maximum))


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _prepare_workspace(session_dir: str | None) -> _WorkspacePaths:
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
    return _WorkspacePaths(
        temp_dir=temp_dir,
        temp_split_dir=temp_split_dir,
        output_dir=output_dir,
        json_path=json_path,
    )


def _extract_explicit_song_list(prompt: str) -> list[tuple[str, str]]:
    header = re.split(r"mixing\s*way\s*:", prompt, maxsplit=1, flags=re.IGNORECASE)[0]
    compact_header = re.sub(r"\s+", " ", header).strip()
    if not compact_header:
        return []

    has_song_header = bool(re.search(r"\bsongs?\s*:", header, flags=re.IGNORECASE))

    def _looks_like_generic_song_request(value: str) -> bool:
        compact = re.sub(r"\s+", " ", str(value or "").strip(" -:;,.")).lower()
        if not compact:
            return True
        if compact.startswith(
            (
                "i want ",
                "i need ",
                "please ",
                "add ",
                "remove ",
                "use ",
                "keep ",
                "repeat ",
                "then ",
                "same order",
                "order in ",
            )
        ):
            return True
        if compact in {"song", "songs", "track", "tracks", "song list", "track list"}:
            return True
        if re.fullmatch(r"\d{1,2}", compact):
            return True
        if "-" not in compact and re.search(r"\b(?:times?|transition|transitions|crossfade|segment|segments)\b", compact):
            return True
        if "-" not in compact and re.search(
            r"\b(?:start|ending|end|beginning|middle|order|intro|outro|flow)\b",
            compact,
        ):
            return True
        if re.search(r"\b(?:songs?|tracks?)\b", compact):
            if re.search(r"\b(?:of|by|from)\b", compact):
                return True
            if re.search(r"\b\d{1,2}\b", compact):
                return True
            if re.fullmatch(r"[a-z0-9][a-z0-9 .&'/\\-]{1,140}\s+(?:songs?|tracks?)", compact):
                return True
        return False

    def _normalize_song_entry(raw_entry: str, *, allow_title_only: bool) -> tuple[str, str] | None:
        cleaned = re.sub(r"^\s*(songs?\s*:)?\s*", "", raw_entry, flags=re.IGNORECASE)
        cleaned = re.sub(r"^\s*\d+\s*[\.\)]\s*", "", cleaned)
        cleaned = re.split(
            r"\b(?:with|for|where|having|keep|add|include|including|featuring)\b",
            cleaned,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        cleaned = re.split(r"\b(?:create|make|mix|remix|mashup)\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:;,.")
        if len(cleaned) < 2 or len(cleaned) > 140:
            return None
        if _looks_like_generic_song_request(cleaned):
            return None

        hyphen_match = re.match(r"^\s*([^-\n]{2,120})\s*-\s*([^-\n]{2,120})\s*$", cleaned)
        if hyphen_match:
            title = re.sub(r"\s+", " ", hyphen_match.group(1)).strip()
            artist = re.sub(r"\s+", " ", hyphen_match.group(2)).strip()
            if title and artist:
                return (title, artist)
        if allow_title_only:
            return (cleaned, "")
        return None

    candidates: list[str] = []

    # Parse numbered lists like "1. song a 2. song b 3. song c".
    numbered_matches = list(re.finditer(r"(\d+)\s*[\.\)]\s*", compact_header))
    if numbered_matches:
        for index, match in enumerate(numbered_matches):
            start = match.end()
            end = numbered_matches[index + 1].start() if index + 1 < len(numbered_matches) else len(compact_header)
            candidate = compact_header[start:end].strip(" ,;")
            if candidate:
                candidates.append(candidate)

    if not candidates:
        lines = [line.strip() for line in header.splitlines() if line.strip()]
        candidate_text = " ".join(lines[:5])
        candidates = [part.strip() for part in re.split(r",|;", candidate_text) if part.strip()]

    allow_title_only = bool(numbered_matches) or has_song_header

    songs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        normalized = _normalize_song_entry(candidate, allow_title_only=allow_title_only)
        if normalized is None:
            continue
        title, artist = normalized
        key = (title.lower(), artist.lower())
        if key in seen:
            continue
        seen.add(key)
        songs.append((title, artist))

    if songs:
        return songs[:8]

    # Parse song lists in prompts like "using A, B, and C".
    using_match = re.search(
        r"\b(?:songs?\s*:|using|use|mix of|mix with|combine)\b(?P<body>.+)",
        compact_header,
        flags=re.IGNORECASE,
    )
    if using_match:
        using_body = using_match.group("body")
        using_body = re.split(r"[.\n]", using_body, maxsplit=1)[0]
        using_candidates = [
            part.strip()
            for part in re.split(r",|;|\band\b", using_body, flags=re.IGNORECASE)
            if part.strip()
        ]
        for candidate in using_candidates:
            normalized = _normalize_song_entry(candidate, allow_title_only=True)
            if normalized is None:
                continue
            title, artist = normalized
            key = (title.lower(), artist.lower())
            if key in seen:
                continue
            seen.add(key)
            songs.append((title, artist))

    return songs[:8]


def _extract_mixing_script_lines(prompt: str) -> list[str]:
    parts = re.split(r"mixing\s*way\s*:", prompt, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) < 2:
        return []

    raw_script = parts[1]
    lines: list[str] = []
    for raw_line in raw_script.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^\[.*\]$", line):
            continue
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) < 3:
            continue
        lines.append(line)
    return lines


def _extract_mixing_script_blocks(prompt: str) -> list[str]:
    parts = re.split(r"mixing\s*way\s*:", prompt, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) < 2:
        return []

    raw_script = parts[1]
    blocks: list[str] = []
    current_lines: list[str] = []
    for raw_line in raw_script.splitlines():
        line = raw_line.strip()
        if not line:
            if current_lines:
                blocks.append(" ".join(current_lines))
                current_lines = []
            continue
        if re.match(r"^\[.*\]$", line):
            continue
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) < 3:
            continue
        current_lines.append(line)

    if current_lines:
        blocks.append(" ".join(current_lines))
    return blocks


def _detect_script_type(text: str) -> str:
    devanagari_count = len(re.findall(r"[\u0900-\u097F]", text))
    latin_count = len(re.findall(r"[A-Za-z]", text))
    total = devanagari_count + latin_count
    if total == 0:
        return "unknown"
    devanagari_ratio = devanagari_count / total
    if devanagari_ratio > 0.55:
        return "devanagari"
    if devanagari_ratio < 0.2:
        return "latin"
    return "mixed"


def _split_lyrics_lines(lyrics_text: str) -> list[str]:
    cleaned_lines: list[str] = []
    for raw_line in lyrics_text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if len(_tokenize_text(line)) < 2:
            continue
        cleaned_lines.append(line)
    return cleaned_lines


def _line_similarity(left: str, right: str) -> float:
    left_tokens = set(_tokenize_text(left))
    right_tokens = set(_tokenize_text(right))
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    if union == 0:
        return 0.0
    return intersection / union


def _script_line_match(
    line: str,
    lyrics_lines_by_track: list[list[str]],
) -> _ScriptLineMatch | None:
    best_track_index = -1
    best_line_index = -1
    best_score = 0.0

    for track_index, lyrics_lines in enumerate(lyrics_lines_by_track):
        if not lyrics_lines:
            continue
        for lyrics_line_index, lyrics_line in enumerate(lyrics_lines):
            score = _line_similarity(line, lyrics_line)
            if score > best_score:
                best_score = score
                best_track_index = track_index
                best_line_index = lyrics_line_index

    if best_track_index < 0 or best_line_index < 0:
        return None
    if best_score < 0.12:
        return None

    total_lines = max(1, len(lyrics_lines_by_track[best_track_index]))
    anchor_ratio = (best_line_index + 1) / total_lines
    return _ScriptLineMatch(
        track_index=best_track_index,
        anchor_ratio=float(_clamp(anchor_ratio, 0.03, 0.97)),
        confidence=best_score,
    )


def _normalize_script_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    normalized = re.sub(r"^\[[^\]]+\]$", "", normalized).strip()
    return normalized


def _parse_lrc_timestamped_lyrics(lrc_text: str) -> list[_TimestampedLyricLine]:
    if not lrc_text.strip():
        return []

    timestamp_pattern = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")
    timed_tokens: list[tuple[float, str]] = []
    for raw_line in lrc_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        matches = list(timestamp_pattern.finditer(line))
        if not matches:
            continue
        text = timestamp_pattern.sub("", line).strip()
        text = _normalize_script_text(text)
        if not text:
            continue
        if len(_tokenize_text(text)) < 2:
            continue
        for match in matches:
            minutes = _coerce_int(match.group(1), 0)
            seconds = _coerce_int(match.group(2), 0)
            fraction_raw = (match.group(3) or "").strip()
            fraction_value = 0.0
            if fraction_raw:
                if len(fraction_raw) == 3:
                    fraction_value = _coerce_int(fraction_raw, 0) / 1000
                elif len(fraction_raw) == 2:
                    fraction_value = _coerce_int(fraction_raw, 0) / 100
                else:
                    fraction_value = _coerce_int(fraction_raw, 0) / 10
            start_seconds = max(0.0, (minutes * 60) + seconds + fraction_value)
            timed_tokens.append((start_seconds, text))

    if not timed_tokens:
        return []

    timed_tokens.sort(key=lambda item: item[0])
    parsed_lines: list[_TimestampedLyricLine] = []
    for index, (start_seconds, text) in enumerate(timed_tokens):
        if index + 1 < len(timed_tokens):
            next_start = timed_tokens[index + 1][0]
            end_seconds = max(start_seconds + 0.8, next_start - 0.05)
        else:
            end_seconds = start_seconds + 4.5
        parsed_lines.append(
            _TimestampedLyricLine(
                text=text,
                start_seconds=float(start_seconds),
                end_seconds=float(max(start_seconds + 0.6, end_seconds)),
                confidence=0.93,
                source="lrc",
            )
        )

    deduped_lines: list[_TimestampedLyricLine] = []
    seen_keys: set[tuple[int, str]] = set()
    for item in parsed_lines:
        key = (int(item.start_seconds * 10), " ".join(_tokenize_text(item.text))[:160])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped_lines.append(item)
    return deduped_lines[:360]


@lru_cache(maxsize=512)
def _fetch_timestamped_lyrics_from_lrclib(
    artist: str,
    title: str,
    api_base_url: str,
    timeout_seconds: float,
) -> list[_TimestampedLyricLine]:
    normalized_artist = artist.strip()
    normalized_title = title.strip()
    if not normalized_artist or not normalized_title:
        return []

    api_base = api_base_url.strip().rstrip("/")
    if not api_base:
        api_base = "https://lrclib.net/api"
    if api_base.endswith("/get") or api_base.endswith("/search"):
        api_base = api_base.rsplit("/", 1)[0]

    full_query_string = urlencode(
        {
            "track_name": normalized_title,
            "artist_name": normalized_artist,
        }
    )
    title_only_query_string = urlencode({"track_name": normalized_title})
    candidate_endpoints = [
        f"{api_base}/get?{full_query_string}",
        f"{api_base}/search?{full_query_string}",
        f"{api_base}/search?{title_only_query_string}",
    ]

    reference_title = _normalize_script_text(normalized_title).lower()
    reference_artist = _normalize_script_text(normalized_artist).lower()

    best_candidate_lines: list[_TimestampedLyricLine] = []
    best_candidate_score = float("-inf")

    def _score_candidate(candidate_title: str, candidate_artist: str, line_count: int) -> float:
        title_score = _line_similarity(reference_title, candidate_title.lower())
        artist_score = _line_similarity(reference_artist, candidate_artist.lower())
        length_bonus = min(line_count / 40, 0.45)
        return (title_score * 1.8) + (artist_score * 1.1) + length_bonus

    for endpoint in candidate_endpoints:
        request = Request(endpoint, headers={"User-Agent": "IntelliMix/1.0"})
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                payload_raw = response.read().decode("utf-8", errors="ignore")
        except (HTTPError, URLError, TimeoutError, OSError):
            continue

        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, dict):
            synced_lyrics = str(payload.get("syncedLyrics", "")).strip()
            parsed = _parse_lrc_timestamped_lyrics(synced_lyrics)
            if parsed:
                candidate_title = _normalize_script_text(
                    str(payload.get("trackName") or payload.get("name") or normalized_title)
                )
                candidate_artist = _normalize_script_text(
                    str(payload.get("artistName") or payload.get("artist") or normalized_artist)
                )
                score = _score_candidate(candidate_title, candidate_artist, len(parsed))
                if score > best_candidate_score:
                    best_candidate_score = score
                    best_candidate_lines = parsed
            continue

        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                synced_lyrics = str(item.get("syncedLyrics", "")).strip()
                parsed = _parse_lrc_timestamped_lyrics(synced_lyrics)
                if not parsed:
                    continue
                candidate_title = _normalize_script_text(
                    str(item.get("trackName") or item.get("name") or normalized_title)
                )
                candidate_artist = _normalize_script_text(
                    str(item.get("artistName") or item.get("artist") or normalized_artist)
                )
                score = _score_candidate(candidate_title, candidate_artist, len(parsed))
                if score > best_candidate_score:
                    best_candidate_score = score
                    best_candidate_lines = parsed

    if best_candidate_lines and best_candidate_score > 0.2:
        return best_candidate_lines
    return []


def _merge_timestamped_lyrics_sources(*source_lists: list[_TimestampedLyricLine]) -> list[_TimestampedLyricLine]:
    merged = [item for source_list in source_lists for item in source_list]
    if not merged:
        return []

    deduped: list[_TimestampedLyricLine] = []
    best_index_by_key: dict[tuple[int, str], int] = {}
    for item in sorted(merged, key=lambda row: (row.start_seconds, -row.confidence)):
        key = (int(item.start_seconds * 10), " ".join(_tokenize_text(item.text))[:180])
        existing_index = best_index_by_key.get(key)
        if existing_index is None:
            best_index_by_key[key] = len(deduped)
            deduped.append(item)
            continue
        if item.confidence > deduped[existing_index].confidence:
            deduped[existing_index] = item

    deduped.sort(key=lambda row: row.start_seconds)
    return deduped[:420]


def _build_timestamped_lyrics_lines(
    lyrics_text: str,
    audio_duration_seconds: float,
) -> list[_TimestampedLyricLine]:
    lyrics_lines = _split_lyrics_lines(lyrics_text)
    if not lyrics_lines:
        return []

    duration_seconds = float(_clamp(audio_duration_seconds, 12.0, 1800.0))
    start_padding = float(_clamp(duration_seconds * 0.04, 2.0, 10.0))
    end_padding = float(_clamp(duration_seconds * 0.06, 3.0, 14.0))
    usable_duration = max(8.0, duration_seconds - start_padding - end_padding)
    line_step = usable_duration / max(1, len(lyrics_lines))

    estimated_lines: list[_TimestampedLyricLine] = []
    for index, lyrics_line in enumerate(lyrics_lines):
        start_seconds = start_padding + (index * line_step)
        end_seconds = min(duration_seconds, start_seconds + max(1.2, line_step * 0.95))
        if end_seconds <= start_seconds:
            end_seconds = min(duration_seconds, start_seconds + 1.8)
        estimated_lines.append(
            _TimestampedLyricLine(
                text=lyrics_line,
                start_seconds=float(max(0.0, start_seconds)),
                end_seconds=float(max(start_seconds + 0.6, end_seconds)),
                confidence=0.34,
                source="lyrics_estimated",
            )
        )

    deduped: list[_TimestampedLyricLine] = []
    seen_keys: set[tuple[int, str]] = set()
    for item in sorted(estimated_lines, key=lambda row: (row.start_seconds, -row.confidence)):
        key = (int(item.start_seconds * 10), " ".join(_tokenize_text(item.text))[:160])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(item)
    return deduped[:320]


def _segment_window_from_line_timestamps(start_seconds: float, end_seconds: float) -> tuple[float, float]:
    line_span = max(0.6, end_seconds - start_seconds)
    target_window = float(_clamp(line_span * 3.2, 8.0, 24.0))
    center = (start_seconds + end_seconds) / 2
    window_start = max(0.0, center - (target_window * 0.46))
    window_end = window_start + target_window
    return (window_start, window_end)


def _fallback_timed_segment_plan(
    script_lines: list[str],
    timed_lines_by_track: dict[int, list[_TimestampedLyricLine]],
    track_count: int,
) -> list[_PlannedTimedSegment]:
    planned: list[_PlannedTimedSegment] = []
    previous_track_index: int | None = None
    for script_index, script_line in enumerate(script_lines):
        best_track_index = -1
        best_line: _TimestampedLyricLine | None = None
        best_score = 0.0
        for track_index in range(track_count):
            for timed_line in timed_lines_by_track.get(track_index, []):
                score = _line_similarity(script_line, timed_line.text) * timed_line.confidence
                if score > best_score:
                    best_score = score
                    best_track_index = track_index
                    best_line = timed_line

        if best_line is None or best_track_index < 0 or best_score < 0.1:
            if track_count <= 1:
                best_track_index = 0
            elif previous_track_index is None:
                best_track_index = script_index % track_count
            else:
                best_track_index = (previous_track_index + 1) % track_count
            fallback_pool = timed_lines_by_track.get(best_track_index, [])
            if fallback_pool:
                best_line = fallback_pool[min(script_index, len(fallback_pool) - 1)]
            else:
                best_line = _TimestampedLyricLine(
                    text=script_line,
                    start_seconds=float(script_index * 12),
                    end_seconds=float((script_index * 12) + 5),
                    confidence=0.08,
                    source="fallback",
                )
            best_score = max(best_score, 0.08)

        seg_start, seg_end = _segment_window_from_line_timestamps(best_line.start_seconds, best_line.end_seconds)
        planned.append(
            _PlannedTimedSegment(
                script_index=script_index,
                track_index=best_track_index,
                start_seconds=seg_start,
                end_seconds=seg_end,
                confidence=float(_clamp(best_score, 0.05, 0.99)),
            )
        )
        previous_track_index = best_track_index

    return planned


def _plan_timed_segments_with_llm(
    prompt: str,
    script_lines: list[str],
    track_sources: list[_TrackSource],
    timed_lines_by_track: dict[int, list[_TimestampedLyricLine]],
) -> list[_PlannedTimedSegment]:
    payload_tracks: list[dict[str, Any]] = []
    max_lines_per_track = _resolve_int_env("AI_TIMESTAMPED_LYRICS_MAX_LINES_PER_TRACK", 120, 20, 260)
    for track_index, track in enumerate(track_sources):
        timed_payload = [
            {
                "line": line.text,
                "start_seconds": round(line.start_seconds, 3),
                "end_seconds": round(line.end_seconds, 3),
                "confidence": round(line.confidence, 4),
                "source": line.source,
            }
            for line in timed_lines_by_track.get(track_index, [])[:max_lines_per_track]
        ]
        payload_tracks.append(
            {
                "track_index": track_index,
                "title": track.plan.title,
                "artist": track.plan.artist,
                "timed_lyrics": timed_payload,
            }
        )

    llm_input = {
        "user_prompt": prompt,
        "script_lines": script_lines,
        "tracks": payload_tracks,
    }

    try:
        llm_raw_output = generate_with_instruction(
            prompt=json.dumps(llm_input, ensure_ascii=True),
            system_instruction=LLM_TIMESTAMPED_LYRICS_SYSTEM_INSTRUCTION,
        )
    except AIServiceError as exc:
        LOGGER.warning(
            "Timestamped lyrics planner failed with AIServiceError (%s). Falling back to deterministic planner.",
            exc.error_code,
        )
        return []
    except Exception:
        LOGGER.warning("Timestamped lyrics planner failed unexpectedly. Falling back to deterministic planner.")
        return []

    parsed = _extract_first_json_object(llm_raw_output)
    raw_segments = parsed.get("segments")
    if not isinstance(raw_segments, list):
        return []

    planned: list[_PlannedTimedSegment] = []
    for raw_item in raw_segments:
        if not isinstance(raw_item, dict):
            continue
        script_index = _coerce_int(raw_item.get("script_index"), -1)
        track_index = _coerce_int(raw_item.get("track_index"), -1)
        if script_index < 0 or script_index >= len(script_lines):
            continue
        if track_index < 0 or track_index >= len(track_sources):
            continue

        start_seconds = _coerce_float(raw_item.get("start_seconds"), -1.0)
        end_seconds = _coerce_float(raw_item.get("end_seconds"), -1.0)
        if start_seconds < 0:
            continue
        if end_seconds <= start_seconds:
            continue
        normalized_start, normalized_end = _segment_window_from_line_timestamps(start_seconds, end_seconds)
        confidence = _coerce_float(raw_item.get("confidence"), 0.5)
        planned.append(
            _PlannedTimedSegment(
                script_index=script_index,
                track_index=track_index,
                start_seconds=normalized_start,
                end_seconds=normalized_end,
                confidence=float(_clamp(confidence, 0.05, 0.99)),
            )
        )

    if not planned:
        return []

    # Keep only one entry per script line, preferring higher confidence.
    deduped_by_script: dict[int, _PlannedTimedSegment] = {}
    for item in planned:
        existing = deduped_by_script.get(item.script_index)
        if existing is None or item.confidence > existing.confidence:
            deduped_by_script[item.script_index] = item

    ordered = [deduped_by_script[index] for index in sorted(deduped_by_script)]
    if len(ordered) < len(script_lines):
        return []
    return ordered


def _group_planned_segments_by_track_switch(
    planned_segments: list[_PlannedTimedSegment],
    *,
    min_run_lines: int,
) -> list[_PlannedTimedSegment]:
    if not planned_segments:
        return []

    ordered = sorted(planned_segments, key=lambda item: item.script_index)
    min_run_lines = max(1, min_run_lines)

    if min_run_lines > 1 and len(ordered) >= 3:
        changed = True
        while changed:
            changed = False
            runs: list[tuple[int, int]] = []
            run_start = 0
            for index in range(1, len(ordered) + 1):
                if index == len(ordered) or ordered[index].track_index != ordered[index - 1].track_index:
                    runs.append((run_start, index - 1))
                    run_start = index

            for run_index, (left, right) in enumerate(runs):
                run_length = (right - left) + 1
                if run_length >= min_run_lines:
                    continue
                if run_index == 0 or run_index == len(runs) - 1:
                    continue

                prev_left, _ = runs[run_index - 1]
                next_left, _ = runs[run_index + 1]
                prev_track = ordered[prev_left].track_index
                next_track = ordered[next_left].track_index
                if prev_track != next_track:
                    continue

                for item_index in range(left, right + 1):
                    current = ordered[item_index]
                    ordered[item_index] = _PlannedTimedSegment(
                        script_index=current.script_index,
                        track_index=prev_track,
                        start_seconds=current.start_seconds,
                        end_seconds=current.end_seconds,
                        confidence=float(_clamp(current.confidence * 0.9, 0.05, 0.99)),
                    )
                changed = True
                break

    grouped: list[_PlannedTimedSegment] = []
    run_items: list[_PlannedTimedSegment] = [ordered[0]]
    for item in ordered[1:]:
        if item.track_index == run_items[-1].track_index:
            run_items.append(item)
            continue

        group_start = min(entry.start_seconds for entry in run_items)
        group_end = max(entry.end_seconds for entry in run_items)
        if group_end <= group_start:
            group_end = group_start + 8.0
        avg_confidence = sum(entry.confidence for entry in run_items) / len(run_items)
        grouped.append(
            _PlannedTimedSegment(
                script_index=run_items[0].script_index,
                track_index=run_items[0].track_index,
                start_seconds=group_start,
                end_seconds=group_end,
                confidence=float(_clamp(avg_confidence, 0.05, 0.99)),
            )
        )
        run_items = [item]

    group_start = min(entry.start_seconds for entry in run_items)
    group_end = max(entry.end_seconds for entry in run_items)
    if group_end <= group_start:
        group_end = group_start + 8.0
    avg_confidence = sum(entry.confidence for entry in run_items) / len(run_items)
    grouped.append(
        _PlannedTimedSegment(
            script_index=run_items[0].script_index,
            track_index=run_items[0].track_index,
            start_seconds=group_start,
            end_seconds=group_end,
            confidence=float(_clamp(avg_confidence, 0.05, 0.99)),
        )
    )

    return grouped


def _build_forced_sequence_from_song_plan(track_sources: list[_TrackSource]) -> list[_TrackSource]:
    forced_sequence: list[_TrackSource] = []
    for source_track in track_sources:
        suggested_start_seconds = max(0, source_track.plan.suggested_start)
        suggested_end_seconds = max(suggested_start_seconds + 10, source_track.plan.suggested_end)
        forced_start_ms = suggested_start_seconds * 1000
        forced_end_ms = suggested_end_seconds * 1000
        requested_duration = int(_clamp((forced_end_ms - forced_start_ms) / 1000, 8, 32))
        forced_sequence.append(
            _TrackSource(
                plan=_SongPlanItem(
                    title=source_track.plan.title,
                    artist=source_track.plan.artist,
                    url=source_track.plan.url,
                    suggested_start=suggested_start_seconds,
                    suggested_end=suggested_end_seconds,
                    requested_duration_seconds=requested_duration,
                    forced_start_ms=forced_start_ms,
                    forced_end_ms=forced_end_ms,
                ),
                source_path=source_track.source_path,
                source_index=source_track.source_index,
                prompt_relevance=source_track.prompt_relevance,
                lyrics_profile=source_track.lyrics_profile,
            )
        )
    return forced_sequence


def _build_default_timed_segment_plan(
    track_sources: list[_TrackSource],
    timed_lines_by_track: dict[int, list[_TimestampedLyricLine]],
) -> list[_PlannedTimedSegment]:
    planned: list[_PlannedTimedSegment] = []
    for track_index, track in enumerate(track_sources):
        timed_lines = timed_lines_by_track.get(track_index, [])
        if timed_lines:
            anchor_index = min(len(timed_lines) - 1, max(0, int(len(timed_lines) * 0.22)))
            anchor_line = timed_lines[anchor_index]
            start_seconds, end_seconds = _segment_window_from_line_timestamps(
                anchor_line.start_seconds,
                anchor_line.end_seconds,
            )
            confidence = float(_clamp(anchor_line.confidence, 0.08, 0.99))
        else:
            start_seconds = float(max(0, track.plan.suggested_start))
            end_seconds = float(max(start_seconds + 10.0, track.plan.suggested_end))
            confidence = 0.08
        planned.append(
            _PlannedTimedSegment(
                script_index=track_index,
                track_index=track_index,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                confidence=confidence,
            )
        )
    return planned


def _build_timestamped_lyrics_track_sequence(track_sources: list[_TrackSource], prompt: str) -> list[_TrackSource]:
    if not track_sources:
        return []
    require_llm_plan = _resolve_bool_env("AI_REQUIRE_LLM_TIMESTAMPED_PLAN", False)

    script_lines = _extract_mixing_script_lines(prompt)
    has_user_script = bool(script_lines)

    timeout_seconds = _resolve_float_env("LYRICS_FETCH_TIMEOUT_SECONDS", 2.5, 0.5, 8.0)
    timestamp_timeout_seconds = _resolve_float_env("TIMESTAMPED_LYRICS_TIMEOUT_SECONDS", 6.0, 1.0, 20.0)
    base_url = os.environ.get("LYRICS_API_URL", "https://api.lyrics.ovh/v1").strip() or "https://api.lyrics.ovh/v1"
    timestamped_lyrics_api_url = (
        os.environ.get("TIMESTAMPED_LYRICS_API_URL", "https://lrclib.net/api").strip() or "https://lrclib.net/api"
    )

    timed_lines_by_track: dict[int, list[_TimestampedLyricLine]] = {}
    tracks_with_timestamps = 0
    for track_index, track in enumerate(track_sources):
        lyrics_text = _fetch_lyrics_text(track.plan.artist, track.plan.title, base_url, timeout_seconds)
        audio_duration_seconds = 0.0
        try:
            audio_duration_seconds = len(AudioSegment.from_file(track.source_path, format="m4a")) / 1000
        except Exception:
            audio_duration_seconds = 180.0
        lrc_lines = _fetch_timestamped_lyrics_from_lrclib(
            track.plan.artist,
            track.plan.title,
            timestamped_lyrics_api_url,
            timestamp_timeout_seconds,
        )
        estimated_lines = _build_timestamped_lyrics_lines(lyrics_text, audio_duration_seconds)
        timed_lines = _merge_timestamped_lyrics_sources(lrc_lines, estimated_lines)
        timed_lines_by_track[track_index] = timed_lines
        if timed_lines:
            tracks_with_timestamps += 1
            LOGGER.info(
                "Timestamped lyrics ready for '%s - %s': lrc=%s estimated=%s merged=%s.",
                track.plan.title,
                track.plan.artist,
                len(lrc_lines),
                len(estimated_lines),
                len(timed_lines),
            )
        else:
            LOGGER.info(
                "Timestamped lyrics missing for '%s - %s' (lrc=0 estimated=0).",
                track.plan.title,
                track.plan.artist,
            )

    if tracks_with_timestamps == 0:
        LOGGER.info("Timestamped lyrics unavailable for selected tracks; using suggested song windows.")
        return _build_forced_sequence_from_song_plan(track_sources)

    if has_user_script:
        planned_segments = _plan_timed_segments_with_llm(prompt, script_lines, track_sources, timed_lines_by_track)
        if not planned_segments:
            if require_llm_plan:
                raise RuntimeError(
                    "Timestamped lyrics LLM planner did not return a valid cut plan. "
                    "Set AI_REQUIRE_LLM_TIMESTAMPED_PLAN=false to allow deterministic fallback."
                )
            planned_segments = _fallback_timed_segment_plan(script_lines, timed_lines_by_track, len(track_sources))
    else:
        planned_segments = _build_default_timed_segment_plan(track_sources, timed_lines_by_track)
        LOGGER.info(
            "No explicit mixing script found; using default timed-lyrics sequence with %s segments.",
            len(planned_segments),
        )

    if not planned_segments:
        LOGGER.info("Timed-lyrics planner produced no segments; using suggested song windows.")
        return _build_forced_sequence_from_song_plan(track_sources)

    if has_user_script:
        line_level_segments = list(planned_segments)

        if len(track_sources) > 1 and len(planned_segments) >= len(track_sources):
            track_counts: dict[int, int] = {}
            for item in planned_segments:
                track_counts[item.track_index] = track_counts.get(item.track_index, 0) + 1

            for missing_track_index in range(len(track_sources)):
                if track_counts.get(missing_track_index, 0) > 0:
                    continue
                replacement_index = -1
                replacement_confidence = float("inf")
                for index, item in enumerate(planned_segments):
                    if track_counts.get(item.track_index, 0) <= 1:
                        continue
                    if item.confidence < replacement_confidence:
                        replacement_index = index
                        replacement_confidence = item.confidence
                if replacement_index < 0:
                    continue

                replacement_line_pool = timed_lines_by_track.get(missing_track_index, [])
                if replacement_line_pool:
                    anchor_line = replacement_line_pool[0]
                    replacement_start, replacement_end = _segment_window_from_line_timestamps(
                        anchor_line.start_seconds,
                        anchor_line.end_seconds,
                    )
                else:
                    replacement_start = float(replacement_index * 10)
                    replacement_end = replacement_start + 10.0

                current_track_index = planned_segments[replacement_index].track_index
                track_counts[current_track_index] = track_counts.get(current_track_index, 1) - 1
                track_counts[missing_track_index] = track_counts.get(missing_track_index, 0) + 1
                planned_segments[replacement_index] = _PlannedTimedSegment(
                    script_index=planned_segments[replacement_index].script_index,
                    track_index=missing_track_index,
                    start_seconds=replacement_start,
                    end_seconds=replacement_end,
                    confidence=0.09,
                )

        min_lines_per_segment = _resolve_int_env("AI_TIMESTAMPED_MIN_LINES_PER_SEGMENT", 2, 1, 8)
        grouped_segments = _group_planned_segments_by_track_switch(
            planned_segments,
            min_run_lines=min_lines_per_segment,
        )

        if len(track_sources) > 1 and grouped_segments:
            grouped_track_counts: dict[int, int] = {}
            for item in grouped_segments:
                grouped_track_counts[item.track_index] = grouped_track_counts.get(item.track_index, 0) + 1

            missing_after_group = [
                track_index
                for track_index in range(len(track_sources))
                if grouped_track_counts.get(track_index, 0) == 0
            ]
            for missing_track_index in missing_after_group:
                rescue_segment = next(
                    (item for item in line_level_segments if item.track_index == missing_track_index),
                    None,
                )
                if rescue_segment is None:
                    continue
                grouped_segments.append(rescue_segment)

        grouped_segments.sort(key=lambda item: item.script_index)
        planned_segments = grouped_segments

    scripted_sequence: list[_TrackSource] = []
    for planned_segment in sorted(planned_segments, key=lambda item: item.script_index):
        source_track = track_sources[planned_segment.track_index]
        forced_start_ms = int(max(0.0, planned_segment.start_seconds * 1000))
        forced_end_ms = int(max(float(forced_start_ms + 1000), planned_segment.end_seconds * 1000))
        requested_duration = int(_clamp((forced_end_ms - forced_start_ms) / 1000, 8, 28))
        scripted_sequence.append(
            _TrackSource(
                plan=_SongPlanItem(
                    title=source_track.plan.title,
                    artist=source_track.plan.artist,
                    url=source_track.plan.url,
                    suggested_start=max(0, forced_start_ms // 1000),
                    suggested_end=max(1, forced_end_ms // 1000),
                    requested_duration_seconds=requested_duration,
                    forced_start_ms=forced_start_ms,
                    forced_end_ms=forced_end_ms,
                ),
                source_path=source_track.source_path,
                source_index=source_track.source_index,
                prompt_relevance=source_track.prompt_relevance + (planned_segment.confidence * 0.45),
                lyrics_profile=source_track.lyrics_profile,
            )
        )

    if scripted_sequence:
        LOGGER.info(
            "Using timestamped lyrics planner: %s lines -> %s song-change segments.",
            len(script_lines) if has_user_script else len(track_sources),
            len(scripted_sequence),
        )
    return scripted_sequence


def _estimate_script_segment_duration_seconds(script_text: str, line_count: int) -> int:
    punctuation_splits = [part for part in re.split(r"[,.;!?\u0964]+", script_text) if part.strip()]
    phrase_count = max(line_count, len(punctuation_splits))
    return int(_clamp(8 + (phrase_count * 4.2), 10, 84))


def _build_script_track_sequence(track_sources: list[_TrackSource], prompt: str) -> list[_TrackSource]:
    script_lines = _extract_mixing_script_lines(prompt)
    script_blocks = _extract_mixing_script_blocks(prompt)
    if not script_lines and not script_blocks:
        return track_sources

    if script_blocks and len(script_blocks) > 1:
        script_entries = script_blocks
        entry_line_counts = [
            max(1, len([part for part in re.split(r"[.!?\u0964]+", block) if part.strip()]))
            for block in script_blocks
        ]
        entry_mode = "blocks"
    else:
        script_entries = script_lines or script_blocks
        entry_line_counts = [1 for _ in script_entries]
        entry_mode = "lines"

    if not script_entries:
        return track_sources

    timeout_seconds = _resolve_float_env("LYRICS_FETCH_TIMEOUT_SECONDS", 2.5, 0.5, 8.0)
    base_url = os.environ.get("LYRICS_API_URL", "https://api.lyrics.ovh/v1").strip() or "https://api.lyrics.ovh/v1"

    lyrics_lines_by_track: list[list[str]] = []
    track_script_types: list[str] = []
    track_keyword_tokens: list[set[str]] = []
    for track in track_sources:
        lyrics_text = _fetch_lyrics_text(track.plan.artist, track.plan.title, base_url, timeout_seconds)
        lines = _split_lyrics_lines(lyrics_text)
        lyrics_lines_by_track.append(lines)
        track_script_types.append(_detect_script_type(lyrics_text))
        keyword_tokens = set(_tokenize_text(f"{track.plan.title} {track.plan.artist}"))
        track_keyword_tokens.append(keyword_tokens)

    entry_matches: list[_ScriptLineMatch] = []
    previous_track_index: int | None = None

    for entry_index, entry_text in enumerate(script_entries):
        if entry_mode == "lines":
            direct_match = _script_line_match(entry_text, lyrics_lines_by_track)
            if direct_match is not None:
                direct_confidence = direct_match.confidence + (
                    track_sources[direct_match.track_index].prompt_relevance * 0.18
                )
                entry_matches.append(
                    _ScriptLineMatch(
                        track_index=direct_match.track_index,
                        anchor_ratio=direct_match.anchor_ratio,
                        confidence=float(direct_confidence),
                    )
                )
                previous_track_index = direct_match.track_index
                continue

        block_tokens = set(_tokenize_text(entry_text))
        block_script_type = _detect_script_type(entry_text)

        best_track_index = -1
        best_score = float("-inf")
        best_anchor_ratio = (entry_index + 1) / (len(script_entries) + 1)

        for track_index, track in enumerate(track_sources):
            keyword_overlap = len(block_tokens & track_keyword_tokens[track_index])

            lyrics_lines = lyrics_lines_by_track[track_index]
            best_line_score = 0.0
            best_line_index = -1
            for lyrics_line_index, lyrics_line in enumerate(lyrics_lines):
                score = _line_similarity(entry_text, lyrics_line)
                if score > best_line_score:
                    best_line_score = score
                    best_line_index = lyrics_line_index

            script_bonus = 0.0
            if block_script_type in {"latin", "devanagari"} and track_script_types[track_index] == block_script_type:
                script_bonus = 0.7

            prompt_bonus = track.prompt_relevance * 0.18
            total_score = (best_line_score * 2.6) + (keyword_overlap * 0.7) + script_bonus + prompt_bonus
            if total_score > best_score:
                best_score = total_score
                best_track_index = track_index
                if best_line_index >= 0:
                    total_lines = max(1, len(lyrics_lines))
                    best_anchor_ratio = (best_line_index + 1) / total_lines

        minimum_score = 0.22 if entry_mode == "blocks" else 0.16
        if best_track_index < 0 or best_score < minimum_score:
            if len(track_sources) > 1:
                if previous_track_index is None:
                    fallback_index = entry_index % len(track_sources)
                else:
                    fallback_index = (previous_track_index + 1) % len(track_sources)
            else:
                fallback_index = 0
            entry_matches.append(
                _ScriptLineMatch(
                    track_index=fallback_index,
                    anchor_ratio=float(_clamp(best_anchor_ratio, 0.05, 0.95)),
                    confidence=0.0,
                )
            )
            previous_track_index = fallback_index
            continue

        entry_matches.append(
            _ScriptLineMatch(
                track_index=best_track_index,
                anchor_ratio=float(_clamp(best_anchor_ratio, 0.05, 0.95)),
                confidence=float(best_score),
            )
        )
        previous_track_index = best_track_index

    if not entry_matches:
        return track_sources

    segment_matches: list[_ScriptSegmentMatch] = []
    max_lines_per_segment = _resolve_int_env("AI_SCRIPT_MAX_LINES_PER_SEGMENT", 6, 2, 12)
    for entry_index, match in enumerate(entry_matches):
        entry_text = script_entries[entry_index]
        entry_lines = entry_line_counts[entry_index]

        if (
            segment_matches
            and segment_matches[-1].track_index == match.track_index
            and (segment_matches[-1].line_count + entry_lines) <= max_lines_per_segment
        ):
            previous_segment = segment_matches[-1]
            previous_weight = max(0.1, previous_segment.confidence + 0.25) * previous_segment.line_count
            current_weight = max(0.1, match.confidence + 0.25) * entry_lines
            total_weight = max(0.1, previous_weight + current_weight)
            previous_segment.anchor_ratio = float(
                _clamp(
                    ((previous_segment.anchor_ratio * previous_weight) + (match.anchor_ratio * current_weight))
                    / total_weight,
                    0.03,
                    0.97,
                )
            )
            total_lines = max(1, previous_segment.line_count + entry_lines)
            previous_segment.confidence = (
                (previous_segment.confidence * previous_segment.line_count) + (match.confidence * entry_lines)
            ) / total_lines
            previous_segment.line_count = total_lines
            previous_segment.text = f"{previous_segment.text} {entry_text}".strip()
            continue

        segment_matches.append(
            _ScriptSegmentMatch(
                track_index=match.track_index,
                anchor_ratio=match.anchor_ratio,
                confidence=match.confidence,
                line_count=entry_lines,
                text=entry_text,
            )
        )

    # Guarantee that explicit multi-song prompts do not collapse into a single-track sequence.
    if len(track_sources) > 1 and len(entry_matches) >= len(track_sources):
        track_counts: dict[int, int] = {}
        for match in segment_matches:
            track_counts[match.track_index] = track_counts.get(match.track_index, 0) + 1

        missing_tracks = [index for index in range(len(track_sources)) if track_counts.get(index, 0) == 0]
        for missing_track_index in missing_tracks:
            candidate_positions = sorted(
                range(len(segment_matches)),
                key=lambda index: (
                    segment_matches[index].confidence,
                    -track_counts.get(segment_matches[index].track_index, 0),
                ),
            )
            replacement_done = False
            for position in candidate_positions:
                current_track = segment_matches[position].track_index
                if track_counts.get(current_track, 0) <= 1:
                    continue
                track_counts[current_track] -= 1
                track_counts[missing_track_index] = track_counts.get(missing_track_index, 0) + 1
                segment_matches[position] = _ScriptSegmentMatch(
                    track_index=missing_track_index,
                    anchor_ratio=0.5,
                    confidence=0.0,
                    line_count=segment_matches[position].line_count,
                    text=segment_matches[position].text,
                )
                replacement_done = True
                break
            if not replacement_done:
                segment_matches.append(
                    _ScriptSegmentMatch(
                        track_index=missing_track_index,
                        anchor_ratio=0.5,
                        confidence=0.0,
                        line_count=1,
                        text=f"{track_sources[missing_track_index].plan.title} {track_sources[missing_track_index].plan.artist}",
                    )
                )

    scripted_sequence: list[_TrackSource] = []
    for match in segment_matches:
        source_track = track_sources[match.track_index]
        requested_duration = _estimate_script_segment_duration_seconds(match.text, match.line_count)

        scripted_sequence.append(
            _TrackSource(
                plan=_SongPlanItem(
                    title=source_track.plan.title,
                    artist=source_track.plan.artist,
                    url=source_track.plan.url,
                    suggested_start=source_track.plan.suggested_start,
                    suggested_end=source_track.plan.suggested_end,
                    anchor_ratio=match.anchor_ratio,
                    requested_duration_seconds=requested_duration,
                ),
                source_path=source_track.source_path,
                source_index=source_track.source_index,
                prompt_relevance=source_track.prompt_relevance + (match.confidence * 0.4),
                lyrics_profile=source_track.lyrics_profile,
            )
        )

    if scripted_sequence:
        LOGGER.info(
            "Using scripted mixing sequence from prompt: %s lines -> %s segments.",
            len(script_lines),
            len(scripted_sequence),
        )
        return scripted_sequence
    return track_sources


def _fetch_song_plan(prompt: str, json_path: str) -> list[_SongPlanItem]:
    explicit_songs = _extract_explicit_song_list(prompt)
    if explicit_songs:
        song_plan: list[_SongPlanItem] = []
        for title, artist in explicit_songs:
            normalized_title = str(title).strip()
            normalized_artist = str(artist).strip()
            if not normalized_title:
                continue

            url = get_youtube_url(normalized_title, normalized_artist)
            if not url and normalized_artist:
                url = get_youtube_url(normalized_title, "")
            if not url:
                continue
            song_plan.append(
                _SongPlanItem(
                    title=normalized_title,
                    artist=normalized_artist,
                    url=url,
                    suggested_start=0,
                    suggested_end=38,
                )
            )
        if song_plan:
            LOGGER.info("Using explicit song list from prompt with %s tracks.", len(song_plan))
            return song_plan

    generate(prompt, json_path=json_path)
    title_artist_start_end = analyze_mix(file_path=json_path)

    if not title_artist_start_end:
        raise RuntimeError("AI output did not produce any songs")

    song_plan: list[_SongPlanItem] = []
    for title, artist, start_time, end_time in title_artist_start_end:
        url = get_youtube_url(title, artist)
        if url:
            song_plan.append(
                _SongPlanItem(
                    title=str(title).strip(),
                    artist=str(artist).strip(),
                    url=str(url),
                    suggested_start=_coerce_int(start_time, 0),
                    suggested_end=_coerce_int(end_time, 30),
                )
            )

    if not song_plan:
        raise RuntimeError("Could not find playable YouTube URLs for generated songs")
    return song_plan


def _download_sources(song_plan: list[_SongPlanItem], temp_dir: str) -> list[_TrackSource]:
    track_sources: list[_TrackSource] = []
    for index, item in enumerate(song_plan):
        try:
            download_audio(item.url, name=str(index), output_dir=temp_dir)
        except Exception as exc:
            LOGGER.warning(
                "Failed to download track '%s - %s' from %s (%s). Skipping this track.",
                item.title,
                item.artist,
                item.url,
                exc,
            )
            continue

        source_path = os.path.join(temp_dir, f"{index}.m4a")
        if not os.path.exists(source_path):
            LOGGER.warning(
                "Downloaded track file missing for '%s - %s' at %s. Skipping this track.",
                item.title,
                item.artist,
                source_path,
            )
            continue

        track_sources.append(
            _TrackSource(
                plan=item,
                source_path=source_path,
                source_index=index,
            )
        )

    if not track_sources:
        raise RuntimeError("Could not download playable audio for any selected song")

    return track_sources


@lru_cache(maxsize=256)
def _fetch_lyrics_text(artist: str, title: str, base_url: str, timeout_seconds: float) -> str:
    normalized_artist = artist.strip()
    normalized_title = title.strip()
    if not normalized_artist or not normalized_title:
        return ""

    endpoint = f"{base_url.rstrip('/')}/{quote(normalized_artist)}/{quote(normalized_title)}"
    request = Request(endpoint, headers={"User-Agent": "IntelliMix/1.0"})

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload_raw = response.read().decode("utf-8", errors="ignore")
    except (HTTPError, URLError, TimeoutError, OSError):
        return ""

    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        return ""

    lyrics = str(payload.get("lyrics", "")).strip()
    if not lyrics:
        return ""
    return lyrics[:40000]


def _tokenize_text(text: str) -> list[str]:
    raw_tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
    filtered_tokens: list[str] = []
    for token in raw_tokens:
        if len(token) < 2:
            continue
        if token.isdigit():
            continue
        if token in LYRICS_STOPWORDS:
            continue
        filtered_tokens.append(token)
    return filtered_tokens


def _extract_lyrics_excerpt(lyrics_text: str, max_chars: int = 220) -> str:
    compact = " ".join(lyrics_text.strip().split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[:max_chars].rstrip()}..."


def _build_lyrics_profile(lyrics_text: str) -> _LyricsProfile:
    tokens = _tokenize_text(lyrics_text)
    if not tokens:
        return _LyricsProfile(
            keywords=frozenset(),
            positivity=0.0,
            has_lyrics=False,
            excerpt="",
        )

    frequencies: dict[str, int] = {}
    for token in tokens:
        frequencies[token] = frequencies.get(token, 0) + 1

    top_keywords = sorted(frequencies.keys(), key=lambda key: frequencies[key], reverse=True)[:40]
    positive_hits = sum(frequencies.get(word, 0) for word in POSITIVE_WORDS)
    negative_hits = sum(frequencies.get(word, 0) for word in NEGATIVE_WORDS)
    positivity = (positive_hits - negative_hits) / max(1, positive_hits + negative_hits)

    return _LyricsProfile(
        keywords=frozenset(top_keywords),
        positivity=float(_clamp(positivity, -1.0, 1.0)),
        has_lyrics=True,
        excerpt=_extract_lyrics_excerpt(lyrics_text),
    )


def _jaccard_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = len(left & right)
    union = len(left | right)
    if union == 0:
        return 0.0
    return intersection / union


def _lyrics_transition_compatibility(previous_track: _TrackSource, current_track: _TrackSource) -> float:
    previous_profile = previous_track.lyrics_profile
    current_profile = current_track.lyrics_profile
    if previous_profile is None or current_profile is None:
        return 0.0
    if not previous_profile.has_lyrics or not current_profile.has_lyrics:
        return 0.0

    keyword_similarity = _jaccard_similarity(previous_profile.keywords, current_profile.keywords)
    sentiment_gap = abs(previous_profile.positivity - current_profile.positivity)
    return (keyword_similarity * 1.1) - (sentiment_gap * 0.35)


def _order_tracks_for_lyrics(track_sources: list[_TrackSource]) -> list[_TrackSource]:
    if len(track_sources) <= 1:
        return track_sources

    lyrics_count = sum(
        1
        for item in track_sources
        if item.lyrics_profile is not None and item.lyrics_profile.has_lyrics
    )
    max_prompt_relevance = max((item.prompt_relevance for item in track_sources), default=0.0)

    if lyrics_count < 2 and max_prompt_relevance <= 0.01:
        return track_sources

    remaining = list(track_sources)
    start_track = max(
        remaining,
        key=lambda item: (
            item.prompt_relevance,
            1 if item.lyrics_profile and item.lyrics_profile.has_lyrics else 0,
            -item.source_index,
        ),
    )
    ordered: list[_TrackSource] = [start_track]
    remaining.remove(start_track)
    current = start_track

    while remaining:
        best_candidate = remaining[0]
        best_score = float("-inf")
        for candidate in remaining:
            compatibility = _lyrics_transition_compatibility(current, candidate)
            score = (compatibility * 0.7) + (candidate.prompt_relevance * 0.3)
            score += -(candidate.source_index * 0.0001)
            if score > best_score:
                best_score = score
                best_candidate = candidate
        ordered.append(best_candidate)
        remaining.remove(best_candidate)
        current = best_candidate

    return ordered


def _enrich_and_order_tracks_with_lyrics(track_sources: list[_TrackSource], prompt: str) -> list[_TrackSource]:
    if not track_sources:
        return track_sources

    lyrics_enabled = _resolve_bool_env("AI_ENABLE_LYRICS_ANALYSIS", True)
    if not lyrics_enabled:
        return track_sources

    timeout_seconds = _resolve_float_env("LYRICS_FETCH_TIMEOUT_SECONDS", 2.5, 0.5, 8.0)
    base_url = os.environ.get("LYRICS_API_URL", "https://api.lyrics.ovh/v1").strip() or "https://api.lyrics.ovh/v1"
    prompt_keywords = frozenset(_tokenize_text(prompt))

    enriched_tracks: list[_TrackSource] = []
    for track in track_sources:
        lyrics_text = _fetch_lyrics_text(track.plan.artist, track.plan.title, base_url, timeout_seconds)
        lyrics_profile = _build_lyrics_profile(lyrics_text)
        prompt_relevance = _jaccard_similarity(lyrics_profile.keywords, prompt_keywords)
        enriched_tracks.append(
            _TrackSource(
                plan=track.plan,
                source_path=track.source_path,
                source_index=track.source_index,
                prompt_relevance=prompt_relevance,
                lyrics_profile=lyrics_profile,
            )
        )

    ordered_tracks = _order_tracks_for_lyrics(enriched_tracks)
    if ordered_tracks != track_sources:
        LOGGER.info("Applied lyrics-aware ordering for %s tracks.", len(ordered_tracks))
    return ordered_tracks


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return float(variance**0.5)


def _extract_mono_samples(
    audio: AudioSegment,
    *,
    max_points: int = 220_000,
    target_frame_rate: int = 11_025,
) -> tuple[list[float], int]:
    mono = audio.set_channels(1)
    if mono.frame_rate > target_frame_rate:
        mono = mono.set_frame_rate(target_frame_rate)
    sample_rate = int(max(2_000, mono.frame_rate))

    sample_width_bits = max(8, mono.sample_width * 8)
    max_abs_value = float((2 ** (sample_width_bits - 1)) - 1)
    if max_abs_value <= 0:
        max_abs_value = 32767.0

    raw_samples = mono.get_array_of_samples()
    sample_count = len(raw_samples)
    if sample_count == 0:
        return ([], sample_rate)

    stride = max(1, int(math.ceil(sample_count / max_points)))
    extracted: list[float] = []
    for index in range(0, sample_count, stride):
        extracted.append(float(raw_samples[index]) / max_abs_value)

    effective_sample_rate = max(2_000, int(sample_rate / stride))
    return (extracted, effective_sample_rate)


def _hann_window(size: int) -> list[float]:
    if size <= 1:
        return [1.0]
    return [0.5 - (0.5 * math.cos((2.0 * math.pi * index) / (size - 1))) for index in range(size)]


def _goertzel_power(frame: list[float], sample_rate: int, target_frequency: float) -> float:
    sample_count = len(frame)
    if sample_count <= 2 or target_frequency <= 0:
        return 0.0

    k = int(round((sample_count * target_frequency) / sample_rate))
    if k <= 0 or k >= sample_count:
        return 0.0

    omega = (2.0 * math.pi * k) / sample_count
    coeff = 2.0 * math.cos(omega)
    q1 = 0.0
    q2 = 0.0
    for sample in frame:
        q0 = (coeff * q1) - q2 + sample
        q2 = q1
        q1 = q0
    power = (q1 * q1) + (q2 * q2) - (coeff * q1 * q2)
    return max(0.0, power)


def _estimate_key_signature(samples: list[float], sample_rate: int) -> tuple[int, str, float]:
    if len(samples) < 4096 or sample_rate <= 0:
        return (-1, "unknown", 0.0)

    frame_size = 1024
    max_frames = 48
    if len(samples) <= frame_size:
        return (-1, "unknown", 0.0)
    step = max(frame_size, (len(samples) - frame_size) // max_frames)
    window = _hann_window(frame_size)

    pitch_class_energy = [1e-9 for _ in range(12)]
    frame_positions = list(range(0, len(samples) - frame_size, step))
    if not frame_positions:
        return (-1, "unknown", 0.0)

    octave_values = (2, 3, 4, 5)
    for start in frame_positions[:max_frames]:
        frame = samples[start : start + frame_size]
        frame_rms = (_mean([value * value for value in frame])) ** 0.5
        if frame_rms < 0.01:
            continue
        windowed = [frame[index] * window[index] for index in range(frame_size)]
        for pitch_class in range(12):
            energy = 0.0
            for octave in octave_values:
                midi_note = ((octave + 1) * 12) + pitch_class
                frequency_hz = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
                if frequency_hz >= (sample_rate * 0.48):
                    continue
                energy += _goertzel_power(windowed, sample_rate, frequency_hz)
            pitch_class_energy[pitch_class] += energy

    total_energy = sum(pitch_class_energy)
    if total_energy <= 1e-6:
        return (-1, "unknown", 0.0)
    normalized = [value / total_energy for value in pitch_class_energy]

    major_profile = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
    minor_profile = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

    scored_keys: list[tuple[float, int, str]] = []
    for root in range(12):
        major_score = 0.0
        minor_score = 0.0
        for idx in range(12):
            value = normalized[(root + idx) % 12]
            major_score += value * major_profile[idx]
            minor_score += value * minor_profile[idx]
        scored_keys.append((major_score, root, "major"))
        scored_keys.append((minor_score, root, "minor"))

    scored_keys.sort(key=lambda item: item[0], reverse=True)
    if not scored_keys:
        return (-1, "unknown", 0.0)

    best_score, best_root, best_scale = scored_keys[0]
    second_score = scored_keys[1][0] if len(scored_keys) > 1 else 0.0
    confidence = float(_clamp((best_score - second_score) / max(best_score, 1e-9), 0.0, 1.0))
    if confidence < 0.02:
        return (-1, "unknown", confidence)
    return (best_root, best_scale, confidence)


def _estimate_waveform_flux(energies: list[float]) -> list[float]:
    if len(energies) < 2:
        return []
    flux: list[float] = [0.0]
    for prev, curr in zip(energies, energies[1:]):
        flux.append(max(0.0, curr - prev))
    return flux


def _estimate_tempo_from_flux(flux: list[float], frame_ms: int) -> int:
    if len(flux) < 8 or frame_ms <= 0:
        return 500

    avg_flux = _mean(flux)
    std_flux = _stddev(flux)
    threshold = avg_flux + (std_flux * 0.55)
    peak_indexes: list[int] = []
    for index in range(1, len(flux) - 1):
        value = flux[index]
        if value < threshold:
            continue
        if value >= flux[index - 1] and value >= flux[index + 1]:
            peak_indexes.append(index)

    intervals_ms: list[int] = []
    for left, right in zip(peak_indexes, peak_indexes[1:]):
        interval_ms = (right - left) * frame_ms
        if 250 <= interval_ms <= 1_000:
            intervals_ms.append(interval_ms)

    if not intervals_ms:
        return 500
    return int(_clamp(float(median(intervals_ms)), 260.0, 760.0))


def _estimate_section_boundaries_ms(
    energies: list[float],
    frame_ms: int,
    beat_interval_ms: int,
    audio_duration_ms: int,
) -> list[int]:
    if audio_duration_ms <= 0:
        return [0]

    boundaries = {0}
    if not energies or frame_ms <= 0:
        return [0, audio_duration_ms]

    phrase_ms = int(max(beat_interval_ms * 16, 7_000))
    for marker in range(phrase_ms, audio_duration_ms, phrase_ms):
        boundaries.add(int(_clamp(float(marker), 0.0, float(audio_duration_ms))))

    deltas: list[tuple[int, float]] = []
    for index in range(1, len(energies)):
        deltas.append((index, abs(energies[index] - energies[index - 1])))
    deltas.sort(key=lambda item: item[1], reverse=True)

    min_gap_frames = max(2, int(phrase_ms / max(frame_ms, 1) * 0.65))
    chosen_frames: list[int] = []
    max_boundaries = min(18, max(4, int(audio_duration_ms / max(phrase_ms, 1))))
    for frame_index, delta in deltas:
        if delta < 0.45:
            continue
        if any(abs(frame_index - existing) < min_gap_frames for existing in chosen_frames):
            continue
        chosen_frames.append(frame_index)
        boundaries.add(int(frame_index * frame_ms))
        if len(chosen_frames) >= max_boundaries:
            break

    boundaries.add(audio_duration_ms)
    return sorted(int(_clamp(float(boundary), 0.0, float(audio_duration_ms))) for boundary in boundaries)


def _boundary_alignment_score(start_ms: int, boundaries_ms: list[int], beat_interval_ms: int) -> float:
    if not boundaries_ms:
        return 0.0
    closest_gap = min(abs(start_ms - boundary) for boundary in boundaries_ms)
    tolerance = max(beat_interval_ms * 1.5, 600.0)
    return float(1.0 - _clamp(closest_gap / tolerance, 0.0, 1.0))


def _analyze_track_dsp(audio: AudioSegment, track_label: str) -> _TrackDSPProfile:
    frame_ms = 250
    energies = _energy_frames(audio, frame_ms)
    flux = _estimate_waveform_flux(energies)

    beat_interval_ms = _estimate_tempo_from_flux(flux, frame_ms)
    if beat_interval_ms <= 0:
        beat_interval_ms = _estimate_beat_interval_ms(audio)
    beat_interval_ms = int(_clamp(float(beat_interval_ms), 260.0, 760.0))
    bpm = float(60_000 / max(beat_interval_ms, 1))

    samples, sample_rate = _extract_mono_samples(audio)
    key_index, key_scale, key_confidence = _estimate_key_signature(samples, sample_rate)
    key_name = "unknown"
    if 0 <= key_index < len(PITCH_CLASS_NAMES):
        key_name = f"{PITCH_CLASS_NAMES[key_index]} {key_scale}"

    section_boundaries_ms = _estimate_section_boundaries_ms(
        energies,
        frame_ms,
        beat_interval_ms,
        len(audio),
    )

    LOGGER.info(
        "DSP analysis for %s: bpm=%.1f key=%s confidence=%.2f sections=%s",
        track_label,
        bpm,
        key_name,
        key_confidence,
        len(section_boundaries_ms),
    )

    return _TrackDSPProfile(
        beat_interval_ms=beat_interval_ms,
        bpm=bpm,
        key_index=key_index,
        key_scale=key_scale,
        key_name=key_name,
        key_confidence=key_confidence,
        frame_ms=frame_ms,
        energy_frames=energies,
        section_boundaries_ms=section_boundaries_ms,
    )


def _fallback_track_dsp_profile(audio: AudioSegment) -> _TrackDSPProfile:
    frame_ms = 400
    energies = _energy_frames(audio, frame_ms)
    beat_interval_ms = _estimate_beat_interval_ms(audio)
    beat_interval_ms = int(_clamp(float(beat_interval_ms), 260.0, 760.0))
    bpm = float(60_000 / max(beat_interval_ms, 1))
    section_boundaries = _estimate_section_boundaries_ms(energies, frame_ms, beat_interval_ms, len(audio))
    return _TrackDSPProfile(
        beat_interval_ms=beat_interval_ms,
        bpm=bpm,
        key_index=-1,
        key_scale="unknown",
        key_name="unknown",
        key_confidence=0.0,
        frame_ms=frame_ms,
        energy_frames=energies,
        section_boundaries_ms=section_boundaries,
    )


def _energy_frames(audio: AudioSegment, frame_ms: int) -> list[float]:
    energies: list[float] = []
    for start in range(0, len(audio), frame_ms):
        chunk = audio[start : start + frame_ms]
        energies.append(_safe_dbfs(chunk))
    return energies


def _estimate_beat_interval_ms(audio: AudioSegment) -> int:
    frame_ms = 250
    energies = _energy_frames(audio, frame_ms)
    if len(energies) < 6:
        return 500

    avg_energy = _mean(energies)
    std_energy = _stddev(energies)
    threshold = avg_energy + (std_energy * 0.35)

    peak_indexes: list[int] = []
    for index in range(1, len(energies) - 1):
        current = energies[index]
        if current <= threshold:
            continue
        if current >= energies[index - 1] and current >= energies[index + 1]:
            peak_indexes.append(index)

    intervals_ms: list[int] = []
    for left, right in zip(peak_indexes, peak_indexes[1:]):
        interval_ms = (right - left) * frame_ms
        if 240 <= interval_ms <= 850:
            intervals_ms.append(interval_ms)

    if not intervals_ms:
        return 500
    return int(_clamp(float(median(intervals_ms)), 260.0, 760.0))


def _align_to_beat_grid(value_ms: int, beat_interval_ms: int, max_value_ms: int) -> int:
    if beat_interval_ms <= 0:
        return int(_clamp(float(value_ms), 0.0, float(max_value_ms)))
    snapped = int(round(value_ms / beat_interval_ms) * beat_interval_ms)
    return int(_clamp(float(snapped), 0.0, float(max_value_ms)))


def _top_energy_start_points(energies: list[float], frame_ms: int, count: int) -> list[int]:
    ranked_indexes = sorted(range(len(energies)), key=lambda idx: energies[idx], reverse=True)
    selected_indexes: list[int] = []
    minimum_gap = max(2, int(2200 / frame_ms))
    for index in ranked_indexes:
        if any(abs(index - existing) < minimum_gap for existing in selected_indexes):
            continue
        selected_indexes.append(index)
        if len(selected_indexes) >= count:
            break
    return [index * frame_ms for index in selected_indexes]


def _top_drop_start_points(energies: list[float], frame_ms: int, count: int) -> list[int]:
    if len(energies) < 4:
        return []
    rises: list[tuple[int, float]] = []
    for index in range(2, len(energies) - 2):
        pre = _mean(energies[max(0, index - 3) : index])
        post = _mean(energies[index : min(len(energies), index + 3)])
        rise = post - pre
        rises.append((index, rise))

    ranked = sorted(rises, key=lambda item: item[1], reverse=True)
    selected_indexes: list[int] = []
    minimum_gap = max(2, int(1800 / frame_ms))
    for index, rise in ranked:
        if rise < 0.6:
            continue
        if any(abs(index - existing) < minimum_gap for existing in selected_indexes):
            continue
        selected_indexes.append(index)
        if len(selected_indexes) >= count:
            break
    return [index * frame_ms for index in selected_indexes]


def _candidate_priority(candidate: _SegmentCandidate) -> float:
    return (
        candidate.transition_quality
        + (candidate.drop_strength * 0.65)
        + (candidate.energy_db * 0.05)
        + (candidate.section_alignment * 0.9)
        + (min(candidate.waveform_dynamics / 6.0, 1.2) * 0.45)
    )


def _build_track_segment_candidates(
    track_source: _TrackSource,
    *,
    track_index: int,
    audio: AudioSegment,
    target_duration_ms: int,
    dsp_profile: _TrackDSPProfile | None = None,
) -> list[_SegmentCandidate]:
    audio_duration_ms = len(audio)
    profile = dsp_profile or _analyze_track_dsp(audio, f"{track_source.plan.title} - {track_source.plan.artist}")
    beat_interval_ms = profile.beat_interval_ms
    bpm = profile.bpm
    key_index = profile.key_index
    key_scale = profile.key_scale
    key_name = profile.key_name
    key_confidence = profile.key_confidence
    frame_ms = profile.frame_ms
    energies = profile.energy_frames if profile.energy_frames else _energy_frames(audio, frame_ms)
    section_boundaries = profile.section_boundaries_ms

    forced_start_ms = track_source.plan.forced_start_ms
    forced_end_ms = track_source.plan.forced_end_ms
    if forced_start_ms is not None and forced_end_ms is not None:
        max_start_ms = max(0, audio_duration_ms - 1200)
        start_ms = int(_clamp(float(forced_start_ms), 0.0, float(max_start_ms)))
        end_ms = int(_clamp(float(forced_end_ms), 0.0, float(audio_duration_ms)))
        if end_ms <= start_ms:
            end_ms = min(audio_duration_ms, start_ms + max(10_000, target_duration_ms))
        if (end_ms - start_ms) < 7_000:
            end_ms = min(audio_duration_ms, start_ms + 10_000)
        start_ms = _align_to_beat_grid(start_ms, beat_interval_ms, audio_duration_ms)
        end_ms = _align_to_beat_grid(end_ms, beat_interval_ms, audio_duration_ms)
        if end_ms <= start_ms:
            end_ms = min(audio_duration_ms, start_ms + max(beat_interval_ms * 16, 8_000))
        if end_ms <= start_ms:
            start_ms = 0
            end_ms = min(audio_duration_ms, max(10_000, target_duration_ms))

        forced_chunk = audio[start_ms:end_ms]
        transition_quality = _transition_aware_score(
            forced_chunk,
            chunk_start_ms=start_ms,
            chunk_end_ms=end_ms,
            source_duration_ms=audio_duration_ms,
            previous_tail_dbfs=None,
        )
        section_alignment = _boundary_alignment_score(start_ms, section_boundaries, beat_interval_ms)
        transition_quality += section_alignment * 0.55
        return [
            _SegmentCandidate(
                candidate_id=f"t{track_index}c0",
                track_index=track_index,
                start_ms=start_ms,
                end_ms=end_ms,
                energy_db=_safe_dbfs(forced_chunk),
                drop_strength=0.0,
                transition_quality=transition_quality,
                beat_interval_ms=beat_interval_ms,
                bpm=bpm,
                key_index=key_index,
                key_scale=key_scale,
                key_name=key_name,
                key_confidence=key_confidence,
                section_alignment=section_alignment,
                waveform_dynamics=float(_stddev(energies)),
            )
        ]

    if audio_duration_ms <= 10_000:
        return [
            _SegmentCandidate(
                candidate_id=f"t{track_index}c0",
                track_index=track_index,
                start_ms=0,
                end_ms=audio_duration_ms,
                energy_db=_safe_dbfs(audio),
                drop_strength=0.0,
                transition_quality=0.0,
                beat_interval_ms=beat_interval_ms,
                bpm=bpm,
                key_index=key_index,
                key_scale=key_scale,
                key_name=key_name,
                key_confidence=key_confidence,
                section_alignment=1.0,
                waveform_dynamics=float(_stddev(energies)),
            )
        ]

    if track_source.plan.anchor_ratio is not None:
        suggestion_ms = int(_clamp(track_source.plan.anchor_ratio, 0.0, 1.0) * audio_duration_ms)
    else:
        suggestion_ms = max(0, track_source.plan.suggested_start * 1000)

    seed_starts: list[int] = [0, suggestion_ms]
    seed_starts.extend(section_boundaries[: min(len(section_boundaries), 18)])
    seed_starts.extend(
        [
            max(0, suggestion_ms - (beat_interval_ms * 8)),
            max(0, suggestion_ms - (beat_interval_ms * 4)),
            suggestion_ms + (beat_interval_ms * 4),
            suggestion_ms + (beat_interval_ms * 8),
        ]
    )
    seed_starts.extend(_top_energy_start_points(energies, frame_ms, count=6))
    seed_starts.extend(_top_drop_start_points(energies, frame_ms, count=6))

    for ratio in (0.15, 0.35, 0.55, 0.75):
        seed_starts.append(int(audio_duration_ms * ratio))

    duration_variants = [
        int(target_duration_ms * 0.88),
        int(target_duration_ms),
        int(target_duration_ms * 1.12),
    ]
    duration_variants = [int(_clamp(float(value), 12_000.0, float(audio_duration_ms))) for value in duration_variants]

    candidates: list[_SegmentCandidate] = []
    seen_ranges: set[tuple[int, int]] = set()
    for seed_start in seed_starts:
        for duration_ms in duration_variants:
            start_ms = _align_to_beat_grid(seed_start, beat_interval_ms, audio_duration_ms)
            end_ms = _align_to_beat_grid(start_ms + duration_ms, beat_interval_ms, audio_duration_ms)
            if end_ms <= start_ms:
                continue
            if (end_ms - start_ms) < 10_000:
                continue
            if (start_ms, end_ms) in seen_ranges:
                continue
            seen_ranges.add((start_ms, end_ms))

            chunk = audio[start_ms:end_ms]
            start_frame = min(len(energies) - 1, max(0, start_ms // frame_ms))
            end_frame = min(len(energies), max(start_frame + 1, end_ms // frame_ms))
            pre_window = energies[max(0, start_frame - 4) : start_frame]
            post_window = energies[start_frame : min(len(energies), start_frame + 4)]
            drop_strength = _mean(post_window) - _mean(pre_window)
            window_energies = energies[start_frame:end_frame]
            waveform_dynamics = _stddev(window_energies)
            section_alignment = _boundary_alignment_score(start_ms, section_boundaries, beat_interval_ms)

            transition_quality = _transition_aware_score(
                chunk,
                chunk_start_ms=start_ms,
                chunk_end_ms=end_ms,
                source_duration_ms=audio_duration_ms,
                previous_tail_dbfs=None,
            )
            transition_quality += (section_alignment * 0.65) + (min(waveform_dynamics / 6.5, 1.0) * 0.45)

            candidates.append(
                _SegmentCandidate(
                    candidate_id="",
                    track_index=track_index,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    energy_db=_safe_dbfs(chunk),
                    drop_strength=float(_clamp(drop_strength, -6.0, 6.0)),
                    transition_quality=transition_quality,
                    beat_interval_ms=beat_interval_ms,
                    bpm=bpm,
                    key_index=key_index,
                    key_scale=key_scale,
                    key_name=key_name,
                    key_confidence=key_confidence,
                    section_alignment=section_alignment,
                    waveform_dynamics=float(waveform_dynamics),
                )
            )

    if not candidates:
        return [
            _SegmentCandidate(
                candidate_id=f"t{track_index}c0",
                track_index=track_index,
                start_ms=0,
                end_ms=min(audio_duration_ms, max(12_000, target_duration_ms)),
                energy_db=_safe_dbfs(audio[: min(audio_duration_ms, max(12_000, target_duration_ms))]),
                drop_strength=0.0,
                transition_quality=0.0,
                beat_interval_ms=beat_interval_ms,
                bpm=bpm,
                key_index=key_index,
                key_scale=key_scale,
                key_name=key_name,
                key_confidence=key_confidence,
                section_alignment=0.6,
                waveform_dynamics=float(_stddev(energies)),
            )
        ]

    ranked = sorted(candidates, key=_candidate_priority, reverse=True)
    max_candidates = _resolve_int_env("AI_LLM_CANDIDATES_PER_TRACK", 8, 4, 14)
    trimmed = ranked[:max_candidates]
    for index, candidate in enumerate(trimmed):
        candidate.candidate_id = f"t{track_index}c{index}"
    return trimmed


def _extract_first_json_object(raw_text: str) -> dict[str, Any]:
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _is_lyrics_driven_prompt(prompt: str) -> bool:
    lowered = prompt.lower()
    strong_markers = [
        "mixing way",
        "line by line",
        "line-by-line",
        "word by word",
        "word-by-word",
        "timestamped lyrics",
    ]
    if any(marker in lowered for marker in strong_markers):
        return True

    regex_markers = [
        r"\buse\s+(?:the\s+)?lyrics\b",
        r"\busing\s+(?:the\s+)?lyrics\b",
        r"\bbased on\s+(?:the\s+)?lyrics\b",
        r"\blyrics?\s*(?:script|sequence|timeline|timestamps?)\b",
        r"\bverse\s*(?:by|wise|based)\b",
        r"\bstanza\s*(?:by|wise|based)\b",
    ]
    return any(re.search(pattern, lowered) for pattern in regex_markers)


def _has_long_transition_intent(prompt: str) -> bool:
    lowered = prompt.lower()
    return (
        "long transition" in lowered
        or "smooth long transition" in lowered
        or "seamless transition" in lowered
        or "sleep" in lowered
        or "fall asleep" in lowered
    )


def _parse_requested_total_duration_seconds(prompt: str) -> int | None:
    lowered = prompt.lower()

    # Highest-confidence duration expressions.
    minute_match = re.search(r"\b(\d{1,3})\s*(?:minutes?|mins?|min)\b(?:\s*(?:mix|mashup|set|audio|track))?", lowered)
    hour_match = re.search(r"\b(\d{1,2})\s*(?:hours?|hrs?|hr)\b", lowered)

    total_seconds = 0
    if hour_match:
        total_seconds += _coerce_int(hour_match.group(1), 0) * 3600
    if minute_match:
        total_seconds += _coerce_int(minute_match.group(1), 0) * 60

    if total_seconds < 60:
        return None
    return int(_clamp(float(total_seconds), 60, 3600))


def _default_mix_intent_plan(prompt: str, track_count: int) -> _MixIntentPlan:
    strategy = "creative_mix"
    target_total_duration_seconds = _parse_requested_total_duration_seconds(prompt)
    long_transition_intent = _has_long_transition_intent(prompt)

    lowered = prompt.lower()
    target_segment_seconds = 36 if track_count <= 2 else 32
    if "short" in lowered or "quick" in lowered or "reel" in lowered:
        target_segment_seconds = min(target_segment_seconds, 22)
    if (
        "long" in lowered
        or "extended" in lowered
        or "full length" in lowered
        or re.search(r"\b[3-9]\s*(?:min|mins|minute|minutes)\b", lowered)
    ):
        target_segment_seconds = max(target_segment_seconds, 46)

    if target_total_duration_seconds and target_total_duration_seconds >= 360:
        target_segment_seconds = max(target_segment_seconds, 54)
    if long_transition_intent:
        target_segment_seconds = max(target_segment_seconds, 52)

    default_crossfade = 3.8 if long_transition_intent else 2.0
    return _MixIntentPlan(
        strategy=strategy,
        use_timestamped_lyrics=False,
        target_segment_duration_seconds=int(_clamp(float(target_segment_seconds), 14, 70)),
        global_crossfade_seconds=float(_clamp(default_crossfade, 0.0, 8.0)),
        transition_crossfade_seconds=[],
        track_windows=[],
        target_total_duration_seconds=target_total_duration_seconds,
        reason="fallback_heuristic",
    )


def _normalize_track_windows(
    raw_windows: object,
    *,
    track_count: int,
) -> list[_TrackWindowDirective]:
    if not isinstance(raw_windows, list) or track_count <= 0:
        return []

    raw_items: list[tuple[int, float | None, float | None]] = []
    for item in raw_windows:
        if not isinstance(item, dict):
            continue
        raw_index = _coerce_int(
            item.get("track_index", item.get("song_index", item.get("track_number", -1))),
            -1,
        )
        if raw_index < 0:
            continue
        start_seconds = item.get("start_seconds")
        end_seconds = item.get("end_seconds")
        start_value = None if start_seconds is None else max(0.0, _coerce_float(start_seconds, 0.0))
        end_value = None if end_seconds is None else max(0.0, _coerce_float(end_seconds, 0.0))
        raw_items.append((raw_index, start_value, end_value))

    if not raw_items:
        return []

    one_based = all(1 <= raw_index <= track_count for raw_index, _, _ in raw_items) and not any(
        raw_index == 0 for raw_index, _, _ in raw_items
    )

    normalized: list[_TrackWindowDirective] = []
    for raw_index, start_value, end_value in raw_items:
        track_index = raw_index - 1 if one_based else raw_index
        if track_index < 0 or track_index >= track_count:
            continue
        normalized.append(
            _TrackWindowDirective(
                track_index=track_index,
                start_seconds=start_value,
                end_seconds=end_value,
            )
        )
    return normalized


def _normalize_transition_seconds(raw_value: object, *, maximum_count: int) -> list[float]:
    if maximum_count <= 0:
        return []
    if not isinstance(raw_value, list):
        return []

    values: list[float] = []
    for item in raw_value:
        values.append(float(_clamp(_coerce_float(item, 0.0), 0.0, 8.0)))
    if not values:
        return []
    return values[:maximum_count]


def _plan_mix_intent(prompt: str, track_sources: list[_TrackSource]) -> _MixIntentPlan:
    track_count = len(track_sources)
    default_plan = _default_mix_intent_plan(prompt, track_count)
    if track_count == 0:
        return default_plan

    payload = {
        "user_prompt": prompt,
        "track_count": track_count,
        "tracks": [
            {
                "track_index": index,
                "title": track.plan.title,
                "artist": track.plan.artist,
            }
            for index, track in enumerate(track_sources)
        ],
    }

    try:
        llm_raw = generate_with_instruction(
            prompt=json.dumps(payload, ensure_ascii=True),
            system_instruction=LLM_MIX_INTENT_SYSTEM_INSTRUCTION,
        )
    except AIServiceError as exc:
        LOGGER.warning(
            "Mix intent planner failed with AIServiceError (%s). Using fallback strategy.",
            exc.error_code,
        )
        return default_plan
    except Exception:
        LOGGER.warning("Mix intent planner failed unexpectedly. Using fallback strategy.")
        return default_plan

    parsed = _extract_first_json_object(llm_raw)
    if not parsed:
        return default_plan

    strategy = "creative_mix"

    target_segment_duration_seconds = default_plan.target_segment_duration_seconds
    target_segment_duration_seconds = _coerce_int(
        parsed.get("target_segment_duration_seconds", target_segment_duration_seconds),
        target_segment_duration_seconds,
    )
    target_segment_duration_seconds = int(_clamp(float(target_segment_duration_seconds), 14, 70))

    raw_global_crossfade = parsed.get("global_crossfade_seconds", parsed.get("crossfade_seconds"))
    global_crossfade_seconds: float | None
    if raw_global_crossfade is None:
        global_crossfade_seconds = default_plan.global_crossfade_seconds
    else:
        global_crossfade_seconds = float(_clamp(_coerce_float(raw_global_crossfade, 0.0), 0.0, 8.0))

    transition_crossfade_seconds = _normalize_transition_seconds(
        parsed.get("transition_crossfade_seconds"),
        maximum_count=max(0, track_count - 1),
    )
    overlap_seconds = _normalize_transition_seconds(
        parsed.get("overlap_seconds"),
        maximum_count=max(0, track_count - 1),
    )
    if overlap_seconds:
        if not transition_crossfade_seconds:
            transition_crossfade_seconds = overlap_seconds
        else:
            merged: list[float] = []
            for index in range(max(len(transition_crossfade_seconds), len(overlap_seconds))):
                left = transition_crossfade_seconds[index] if index < len(transition_crossfade_seconds) else 0.0
                right = overlap_seconds[index] if index < len(overlap_seconds) else 0.0
                merged.append(max(left, right))
            transition_crossfade_seconds = merged

    track_windows = _normalize_track_windows(
        parsed.get("track_windows"),
        track_count=track_count,
    )

    raw_target_total_seconds = parsed.get(
        "target_total_duration_seconds",
        parsed.get("mix_duration_seconds", parsed.get("target_duration_seconds")),
    )
    if raw_target_total_seconds is None:
        target_total_duration_seconds = default_plan.target_total_duration_seconds
    else:
        parsed_total_seconds = _coerce_int(raw_target_total_seconds, 0)
        if parsed_total_seconds < 60:
            target_total_duration_seconds = default_plan.target_total_duration_seconds
        else:
            target_total_duration_seconds = int(_clamp(float(parsed_total_seconds), 60, 3600))

    reason = str(parsed.get("reason", "")).strip()[:240]
    return _MixIntentPlan(
        strategy=strategy,
        use_timestamped_lyrics=False,
        target_segment_duration_seconds=target_segment_duration_seconds,
        global_crossfade_seconds=global_crossfade_seconds,
        transition_crossfade_seconds=transition_crossfade_seconds,
        track_windows=track_windows,
        target_total_duration_seconds=target_total_duration_seconds,
        reason=reason or default_plan.reason,
    )


def _default_candidate_selection(candidates_by_track: dict[int, list[_SegmentCandidate]]) -> dict[int, _SegmentCandidate]:
    selected: dict[int, _SegmentCandidate] = {}
    for track_index, candidates in candidates_by_track.items():
        selected[track_index] = max(candidates, key=_candidate_priority)
    return selected


def _select_candidates_with_llm(
    prompt: str,
    track_sources: list[_TrackSource],
    candidates_by_track: dict[int, list[_SegmentCandidate]],
) -> dict[int, _SegmentCandidate]:
    default_selection = _default_candidate_selection(candidates_by_track)

    llm_enabled = _resolve_bool_env("AI_ENABLE_LLM_CANDIDATE_SELECTION", True)
    if not llm_enabled:
        return default_selection

    payload_tracks: list[dict[str, Any]] = []
    for track_index, track in enumerate(track_sources):
        candidates_payload = [
            {
                "candidate_id": candidate.candidate_id,
                "start_seconds": round(candidate.start_ms / 1000, 2),
                "end_seconds": round(candidate.end_ms / 1000, 2),
                "duration_seconds": round((candidate.end_ms - candidate.start_ms) / 1000, 2),
                "energy_db": round(candidate.energy_db, 3),
                "drop_strength": round(candidate.drop_strength, 3),
                "transition_quality": round(candidate.transition_quality, 3),
                "bpm": round(candidate.bpm, 2),
                "key": candidate.key_name,
                "key_confidence": round(candidate.key_confidence, 3),
                "section_alignment": round(candidate.section_alignment, 3),
                "waveform_dynamics": round(candidate.waveform_dynamics, 3),
            }
            for candidate in candidates_by_track[track_index]
        ]
        payload_tracks.append(
            {
                "track_index": track_index,
                "title": track.plan.title,
                "artist": track.plan.artist,
                "prompt_relevance": round(track.prompt_relevance, 4),
                "candidates": candidates_payload,
            }
        )

    llm_input = {
        "user_prompt": prompt,
        "tracks": payload_tracks,
    }

    try:
        llm_raw_output = generate_with_instruction(
            prompt=json.dumps(llm_input, ensure_ascii=True),
            system_instruction=LLM_CANDIDATE_SELECTION_SYSTEM_INSTRUCTION,
        )
    except AIServiceError as exc:
        LOGGER.warning(
            "LLM candidate selection failed with AIServiceError (%s). Falling back to deterministic candidates.",
            exc.error_code,
        )
        return default_selection
    except Exception:
        LOGGER.warning("LLM candidate selection failed unexpectedly. Falling back to deterministic candidates.")
        return default_selection

    parsed = _extract_first_json_object(llm_raw_output)
    raw_selections = parsed.get("selections")
    if not isinstance(raw_selections, list):
        return default_selection

    selected: dict[int, _SegmentCandidate] = {}
    for item in raw_selections:
        if not isinstance(item, dict):
            continue
        track_index = _coerce_int(item.get("track_index"), -1)
        candidate_id = str(item.get("candidate_id", "")).strip()
        if track_index not in candidates_by_track or not candidate_id:
            continue
        matched = next(
            (candidate for candidate in candidates_by_track[track_index] if candidate.candidate_id == candidate_id),
            None,
        )
        if matched is None:
            continue
        selected[track_index] = matched

    for track_index, fallback in default_selection.items():
        selected.setdefault(track_index, fallback)
    return selected


def _candidate_unary_score(
    candidate: _SegmentCandidate,
    track_source: _TrackSource,
    *,
    llm_selected_candidate_id: str | None,
) -> float:
    score = _candidate_priority(candidate) + (track_source.prompt_relevance * 2.1)
    duration_seconds = (candidate.end_ms - candidate.start_ms) / 1000
    if duration_seconds < 15:
        score -= 0.7
    elif duration_seconds > 58:
        score -= 0.5
    score += (candidate.key_confidence * 0.2)

    if llm_selected_candidate_id and candidate.candidate_id != llm_selected_candidate_id:
        stickiness = _resolve_float_env("AI_LLM_SELECTION_STICKINESS", 0.75, 0.0, 3.0)
        score -= stickiness
    return score


def _harmonic_transition_compatibility(left_candidate: _SegmentCandidate, right_candidate: _SegmentCandidate) -> float:
    if left_candidate.key_index < 0 or right_candidate.key_index < 0:
        return 0.62

    left_key = left_candidate.key_index % 12
    right_key = right_candidate.key_index % 12
    interval = min((left_key - right_key) % 12, (right_key - left_key) % 12)
    same_scale = left_candidate.key_scale == right_candidate.key_scale

    if interval == 0 and same_scale:
        return 1.0
    if interval == 0 and not same_scale:
        return 0.84
    if interval in {5, 7} and same_scale:
        return 0.9
    if interval in {1, 2, 10, 11}:
        return 0.72 if same_scale else 0.66
    if interval in {3, 4, 8, 9}:
        return 0.63 if same_scale else 0.55
    return 0.5


def _pair_transition_score(
    left_candidate: _SegmentCandidate,
    right_candidate: _SegmentCandidate,
    left_track: _TrackSource,
    right_track: _TrackSource,
) -> float:
    left_bpm = left_candidate.bpm if left_candidate.bpm > 0 else (60_000 / max(1, left_candidate.beat_interval_ms))
    right_bpm = (
        right_candidate.bpm if right_candidate.bpm > 0 else (60_000 / max(1, right_candidate.beat_interval_ms))
    )
    tempo_similarity = min(left_bpm, right_bpm) / max(left_bpm, right_bpm)

    energy_gap = abs(left_candidate.energy_db - right_candidate.energy_db)
    energy_score = 1.0 - _clamp(energy_gap / 9.0, 0.0, 1.0)

    drop_gap = abs(right_candidate.drop_strength - left_candidate.drop_strength)
    drop_score = 1.0 - _clamp(drop_gap / 4.0, 0.0, 1.0)
    harmonic_score = _harmonic_transition_compatibility(left_candidate, right_candidate)
    structure_score = _mean([left_candidate.section_alignment, right_candidate.section_alignment])
    dynamics_gap = abs(left_candidate.waveform_dynamics - right_candidate.waveform_dynamics)
    dynamics_score = 1.0 - _clamp(dynamics_gap / 8.0, 0.0, 1.0)
    return (
        (tempo_similarity * 1.1)
        + (harmonic_score * 1.25)
        + (energy_score * 0.9)
        + (drop_score * 0.65)
        + (structure_score * 0.55)
        + (dynamics_score * 0.45)
    )


def _optimize_candidate_transitions(
    track_sources: list[_TrackSource],
    candidates_by_track: dict[int, list[_SegmentCandidate]],
    llm_selected: dict[int, _SegmentCandidate],
) -> dict[int, _SegmentCandidate]:
    if len(track_sources) <= 1:
        return llm_selected

    optimizer_enabled = _resolve_bool_env("AI_ENABLE_TRANSITION_OPTIMIZER", True)
    if not optimizer_enabled:
        return llm_selected

    pair_weight = _resolve_float_env("AI_TRANSITION_PAIR_WEIGHT", 1.35, 0.5, 3.5)

    dp_scores: list[dict[str, float]] = []
    backpointers: list[dict[str, str | None]] = []

    first_candidates = candidates_by_track.get(0, [])
    if not first_candidates:
        return llm_selected

    first_scores: dict[str, float] = {}
    first_prev: dict[str, str | None] = {}
    llm_first_id = llm_selected.get(0).candidate_id if 0 in llm_selected else None
    for candidate in first_candidates:
        first_scores[candidate.candidate_id] = _candidate_unary_score(
            candidate,
            track_sources[0],
            llm_selected_candidate_id=llm_first_id,
        )
        first_prev[candidate.candidate_id] = None
    dp_scores.append(first_scores)
    backpointers.append(first_prev)

    for track_index in range(1, len(track_sources)):
        current_candidates = candidates_by_track.get(track_index, [])
        previous_candidates = candidates_by_track.get(track_index - 1, [])
        if not current_candidates or not previous_candidates:
            return llm_selected

        llm_current_id = llm_selected.get(track_index).candidate_id if track_index in llm_selected else None
        current_scores: dict[str, float] = {}
        current_prev: dict[str, str | None] = {}

        for candidate in current_candidates:
            unary = _candidate_unary_score(
                candidate,
                track_sources[track_index],
                llm_selected_candidate_id=llm_current_id,
            )
            best_score = float("-inf")
            best_prev_id: str | None = None

            for previous in previous_candidates:
                prev_score = dp_scores[track_index - 1].get(previous.candidate_id, float("-inf"))
                if prev_score == float("-inf"):
                    continue
                pair_score = _pair_transition_score(
                    previous,
                    candidate,
                    track_sources[track_index - 1],
                    track_sources[track_index],
                )
                total_score = prev_score + unary + (pair_score * pair_weight)
                if total_score > best_score:
                    best_score = total_score
                    best_prev_id = previous.candidate_id

            current_scores[candidate.candidate_id] = best_score
            current_prev[candidate.candidate_id] = best_prev_id

        dp_scores.append(current_scores)
        backpointers.append(current_prev)

    last_track_index = len(track_sources) - 1
    final_scores = dp_scores[last_track_index]
    if not final_scores:
        return llm_selected

    best_last_id = max(final_scores, key=final_scores.get)
    resolved_ids: dict[int, str] = {last_track_index: best_last_id}

    for track_index in range(last_track_index, 0, -1):
        prev_id = backpointers[track_index].get(resolved_ids[track_index])
        if prev_id is None:
            return llm_selected
        resolved_ids[track_index - 1] = prev_id

    optimized_selection: dict[int, _SegmentCandidate] = {}
    for track_index, candidates in candidates_by_track.items():
        target_id = resolved_ids.get(track_index)
        if not target_id:
            optimized_selection[track_index] = llm_selected.get(track_index, candidates[0])
            continue
        matched = next((candidate for candidate in candidates if candidate.candidate_id == target_id), None)
        if matched is None:
            optimized_selection[track_index] = llm_selected.get(track_index, candidates[0])
            continue
        optimized_selection[track_index] = matched

    changes = sum(
        1
        for track_index, candidate in optimized_selection.items()
        if track_index in llm_selected and llm_selected[track_index].candidate_id != candidate.candidate_id
    )
    if changes:
        LOGGER.info(
            "Transition optimizer adjusted %s/%s track selections for smoother flow.",
            changes,
            len(track_sources),
        )
    return optimized_selection


def _render_llm_selected_segments(
    track_sources: list[_TrackSource],
    selected_candidates: dict[int, _SegmentCandidate],
    split_dir: str,
) -> list[str]:
    rendered_files: list[str] = []
    previous_tail_dbfs: float | None = None

    for track_index, track_source in enumerate(track_sources):
        candidate = selected_candidates[track_index]
        audio = AudioSegment.from_file(track_source.source_path, format="m4a")
        start_ms = int(_clamp(float(candidate.start_ms), 0.0, float(len(audio))))
        end_ms = int(_clamp(float(candidate.end_ms), 0.0, float(len(audio))))
        if end_ms <= start_ms:
            end_ms = min(len(audio), start_ms + 12_000)
        segment = audio[start_ms:end_ms]

        if len(segment) > 3200:
            segment = segment.fade_in(min(900, len(segment) // 5)).fade_out(min(900, len(segment) // 5))

        target_loudness = -14.0
        current_loudness = _safe_dbfs(segment)
        gain_db = _clamp(target_loudness - current_loudness, -8.0, 8.0)
        if previous_tail_dbfs is not None:
            gain_db = _clamp(gain_db - ((current_loudness - previous_tail_dbfs) * 0.15), -8.0, 8.0)
        segment = segment.apply_gain(gain_db)

        previous_tail = segment[-min(2000, len(segment)) :]
        previous_tail_dbfs = _safe_dbfs(previous_tail)

        output_file = os.path.join(split_dir, f"{track_index}.mp3")
        segment.export(output_file, format="mp3")
        rendered_files.append(output_file)

    return rendered_files


def _render_forced_timestamped_segments(track_sources: list[_TrackSource], split_dir: str) -> list[str]:
    rendered_files: list[str] = []
    previous_tail_dbfs: float | None = None

    for track_index, track_source in enumerate(track_sources):
        audio = AudioSegment.from_file(track_source.source_path, format="m4a")
        forced_start_ms = track_source.plan.forced_start_ms
        forced_end_ms = track_source.plan.forced_end_ms

        if forced_start_ms is None:
            forced_start_ms = max(0, track_source.plan.suggested_start * 1000)
        if forced_end_ms is None:
            fallback_duration_ms = max(10_000, (track_source.plan.suggested_end - track_source.plan.suggested_start) * 1000)
            forced_end_ms = forced_start_ms + fallback_duration_ms

        start_ms = int(_clamp(float(forced_start_ms), 0.0, float(max(0, len(audio) - 1000))))
        end_ms = int(_clamp(float(forced_end_ms), 0.0, float(len(audio))))
        if end_ms <= start_ms:
            end_ms = min(len(audio), start_ms + 10_000)
        if (end_ms - start_ms) < 7_000:
            end_ms = min(len(audio), start_ms + 10_000)

        segment = audio[start_ms:end_ms]
        if len(segment) > 3200:
            segment = segment.fade_in(min(900, len(segment) // 5)).fade_out(min(900, len(segment) // 5))

        target_loudness = -14.0
        current_loudness = _safe_dbfs(segment)
        gain_db = _clamp(target_loudness - current_loudness, -8.0, 8.0)
        if previous_tail_dbfs is not None:
            gain_db = _clamp(gain_db - ((current_loudness - previous_tail_dbfs) * 0.15), -8.0, 8.0)
        segment = segment.apply_gain(gain_db)

        previous_tail = segment[-min(2000, len(segment)) :]
        previous_tail_dbfs = _safe_dbfs(previous_tail)

        output_file = os.path.join(split_dir, f"{track_index}.mp3")
        segment.export(output_file, format="mp3")
        rendered_files.append(output_file)

    return rendered_files


def _apply_mix_intent_to_tracks(track_sources: list[_TrackSource], mix_plan: _MixIntentPlan) -> list[_TrackSource]:
    if not track_sources:
        return []

    directives_by_track: dict[int, _TrackWindowDirective] = {
        directive.track_index: directive for directive in mix_plan.track_windows
    }
    target_seconds = int(_clamp(float(mix_plan.target_segment_duration_seconds), 14, 70))

    tuned_tracks: list[_TrackSource] = []
    for index, track in enumerate(track_sources):
        directive = directives_by_track.get(index)
        suggested_start = max(0, track.plan.suggested_start)
        suggested_end = max(suggested_start + 10, track.plan.suggested_end)
        forced_start_ms = track.plan.forced_start_ms
        forced_end_ms = track.plan.forced_end_ms
        requested_duration_seconds = target_seconds

        if directive is not None:
            if directive.start_seconds is not None and directive.end_seconds is not None:
                start_seconds = max(0.0, directive.start_seconds)
                end_seconds = max(start_seconds + 8.0, directive.end_seconds)
                suggested_start = int(start_seconds)
                suggested_end = int(end_seconds)
                forced_start_ms = int(start_seconds * 1000)
                forced_end_ms = int(end_seconds * 1000)
                requested_duration_seconds = int(_clamp((forced_end_ms - forced_start_ms) / 1000, 8, 84))
            elif directive.start_seconds is not None:
                suggested_start = int(max(0.0, directive.start_seconds))
                suggested_end = suggested_start + target_seconds
            elif directive.end_seconds is not None:
                suggested_end = int(max(1.0, directive.end_seconds))
                suggested_start = max(0, suggested_end - target_seconds)
        else:
            suggested_end = max(suggested_end, suggested_start + target_seconds)

        tuned_tracks.append(
            _TrackSource(
                plan=_SongPlanItem(
                    title=track.plan.title,
                    artist=track.plan.artist,
                    url=track.plan.url,
                    suggested_start=suggested_start,
                    suggested_end=suggested_end,
                    anchor_ratio=track.plan.anchor_ratio,
                    requested_duration_seconds=requested_duration_seconds,
                    forced_start_ms=forced_start_ms,
                    forced_end_ms=forced_end_ms,
                ),
                source_path=track.source_path,
                source_index=track.source_index,
                prompt_relevance=track.prompt_relevance,
                lyrics_profile=track.lyrics_profile,
            )
        )

    return tuned_tracks


def _render_creative_mix_segments(
    prompt: str,
    track_sources: list[_TrackSource],
    split_dir: str,
    mix_plan: _MixIntentPlan,
) -> list[str]:
    tuned_tracks = _apply_mix_intent_to_tracks(track_sources, mix_plan)
    candidates_by_track: dict[int, list[_SegmentCandidate]] = {}
    dsp_profiles: dict[int, _TrackDSPProfile] = {}
    dsp_enabled = _resolve_bool_env("AI_ENABLE_DSP_ANALYSIS", True)

    for track_index, track_source in enumerate(tuned_tracks):
        audio = AudioSegment.from_file(track_source.source_path, format="m4a")
        if dsp_enabled:
            dsp_profiles[track_index] = _analyze_track_dsp(audio, f"{track_source.plan.title} - {track_source.plan.artist}")
        else:
            dsp_profiles[track_index] = _fallback_track_dsp_profile(audio)
        suggested_duration = track_source.plan.requested_duration_seconds or (
            track_source.plan.suggested_end - track_source.plan.suggested_start
        )
        target_duration_ms = _derive_target_duration_ms(
            suggested_duration,
            index=track_index,
            total_tracks=len(tuned_tracks),
            source_duration_ms=len(audio),
            prompt_relevance=track_source.prompt_relevance,
        )
        candidates_by_track[track_index] = _build_track_segment_candidates(
            track_source,
            track_index=track_index,
            audio=audio,
            target_duration_ms=target_duration_ms,
            dsp_profile=dsp_profiles[track_index],
        )

    selected_candidates = _select_candidates_with_llm(prompt, tuned_tracks, candidates_by_track)
    selected_candidates = _optimize_candidate_transitions(tuned_tracks, candidates_by_track, selected_candidates)
    candidate_sequence = _build_candidate_sequence_for_target_duration(
        tuned_tracks,
        candidates_by_track,
        selected_candidates,
        mix_plan,
    )
    return _render_candidate_sequence_segments(tuned_tracks, candidate_sequence, split_dir)


def _estimated_crossfade_ms_for_plan(mix_plan: _MixIntentPlan, transition_index: int) -> int:
    if transition_index < 0:
        return 0
    if mix_plan.transition_crossfade_seconds:
        capped_index = min(transition_index, len(mix_plan.transition_crossfade_seconds) - 1)
        return int(_clamp(mix_plan.transition_crossfade_seconds[capped_index], 0.0, 8.0) * 1000)
    if mix_plan.global_crossfade_seconds is not None:
        return int(_clamp(mix_plan.global_crossfade_seconds, 0.0, 8.0) * 1000)
    return 1800


def _effective_sequence_duration_ms(
    sequence: list[_SegmentCandidate],
    mix_plan: _MixIntentPlan,
) -> int:
    if not sequence:
        return 0

    total_ms = 0
    previous_duration_ms = 0
    for index, candidate in enumerate(sequence):
        duration_ms = max(1_000, candidate.end_ms - candidate.start_ms)
        total_ms += duration_ms
        if index > 0:
            estimated_crossfade_ms = _estimated_crossfade_ms_for_plan(mix_plan, index - 1)
            max_safe_crossfade = max(0, min(previous_duration_ms, duration_ms) - 200)
            total_ms -= min(estimated_crossfade_ms, max_safe_crossfade)
        previous_duration_ms = duration_ms
    return total_ms


def _build_candidate_sequence_for_target_duration(
    track_sources: list[_TrackSource],
    candidates_by_track: dict[int, list[_SegmentCandidate]],
    selected_candidates: dict[int, _SegmentCandidate],
    mix_plan: _MixIntentPlan,
) -> list[_SegmentCandidate]:
    if not track_sources:
        return []

    base_sequence: list[_SegmentCandidate] = []
    selected_candidate_index_by_track: dict[int, int] = {}
    for track_index in range(len(track_sources)):
        candidates = candidates_by_track.get(track_index, [])
        if not candidates:
            continue
        selected_candidate = selected_candidates.get(track_index, candidates[0])
        selected_candidate_index = next(
            (index for index, candidate in enumerate(candidates) if candidate.candidate_id == selected_candidate.candidate_id),
            0,
        )
        selected_candidate_index_by_track[track_index] = selected_candidate_index
        base_sequence.append(candidates[selected_candidate_index])

    if not base_sequence:
        return []

    target_total_seconds = mix_plan.target_total_duration_seconds
    if not target_total_seconds:
        return base_sequence

    target_total_ms = int(_clamp(float(target_total_seconds * 1000), 60_000, 3_600_000))
    sequence = list(base_sequence)
    max_segments = min(260, max(20, len(track_sources) * 60))
    round_index = 1

    while len(sequence) < max_segments and _effective_sequence_duration_ms(sequence, mix_plan) < target_total_ms:
        for track_index in range(len(track_sources)):
            candidates = candidates_by_track.get(track_index, [])
            if not candidates:
                continue

            selected_index = selected_candidate_index_by_track.get(track_index, 0)
            variant_index = (selected_index + round_index) % len(candidates)
            sequence.append(candidates[variant_index])
            if _effective_sequence_duration_ms(sequence, mix_plan) >= target_total_ms or len(sequence) >= max_segments:
                break
        round_index += 1

    if len(sequence) > len(base_sequence):
        LOGGER.info(
            "Extended creative mix to %s segments to target ~%ss output.",
            len(sequence),
            target_total_seconds,
        )
    return sequence


def _render_candidate_sequence_segments(
    track_sources: list[_TrackSource],
    candidate_sequence: list[_SegmentCandidate],
    split_dir: str,
) -> list[str]:
    rendered_files: list[str] = []
    previous_tail_dbfs: float | None = None

    for segment_index, candidate in enumerate(candidate_sequence):
        track_index = candidate.track_index
        if track_index < 0 or track_index >= len(track_sources):
            continue
        track_source = track_sources[track_index]
        audio = AudioSegment.from_file(track_source.source_path, format="m4a")
        start_ms = int(_clamp(float(candidate.start_ms), 0.0, float(len(audio))))
        end_ms = int(_clamp(float(candidate.end_ms), 0.0, float(len(audio))))
        if end_ms <= start_ms:
            end_ms = min(len(audio), start_ms + 12_000)
        segment = audio[start_ms:end_ms]

        if len(segment) > 3200:
            segment = segment.fade_in(min(900, len(segment) // 5)).fade_out(min(900, len(segment) // 5))

        target_loudness = -14.0
        current_loudness = _safe_dbfs(segment)
        gain_db = _clamp(target_loudness - current_loudness, -8.0, 8.0)
        if previous_tail_dbfs is not None:
            gain_db = _clamp(gain_db - ((current_loudness - previous_tail_dbfs) * 0.15), -8.0, 8.0)
        segment = segment.apply_gain(gain_db)

        previous_tail = segment[-min(2000, len(segment)) :]
        previous_tail_dbfs = _safe_dbfs(previous_tail)

        output_file = os.path.join(split_dir, f"{segment_index}.mp3")
        segment.export(output_file, format="mp3")
        rendered_files.append(output_file)

    return rendered_files


def _derive_target_duration_ms(
    suggested_duration_seconds: int,
    *,
    index: int,
    total_tracks: int,
    source_duration_ms: int,
    prompt_relevance: float = 0.0,
) -> int:
    base_seconds = suggested_duration_seconds if suggested_duration_seconds > 0 else 28
    base_seconds = int(_clamp(base_seconds, 16, 52))

    shape_profile = [1.0, 1.15, 0.92, 1.22, 0.88, 1.05]
    base_seconds = int(base_seconds * shape_profile[index % len(shape_profile)])

    if total_tracks > 1 and index == 0:
        base_seconds = int(base_seconds * 0.9)
    if total_tracks > 1 and index == total_tracks - 1:
        base_seconds = int(base_seconds * 1.15)

    relevance_weight = _clamp(0.92 + (prompt_relevance * 0.35), 0.9, 1.25)
    base_seconds = int(base_seconds * relevance_weight)

    source_seconds = max(1, source_duration_ms // 1000)
    max_allowed = max(14, source_seconds - 8)
    base_seconds = int(_clamp(base_seconds, 14, max_allowed))
    return base_seconds * 1000


def _transition_aware_score(
    chunk: AudioSegment,
    *,
    chunk_start_ms: int,
    chunk_end_ms: int,
    source_duration_ms: int,
    previous_tail_dbfs: float | None,
) -> float:
    middle = chunk[len(chunk) // 4 : (len(chunk) * 3) // 4]
    head = chunk[: min(1200, len(chunk))]
    tail = chunk[-min(1200, len(chunk)) :]

    avg_db = _safe_dbfs(chunk)
    mid_db = _safe_dbfs(middle)
    head_db = _safe_dbfs(head)
    tail_db = _safe_dbfs(tail)
    boundary_gap = abs(head_db - tail_db)

    edge_penalty = 0.0
    if chunk_start_ms < 4000:
        edge_penalty += 1.5
    if (source_duration_ms - chunk_end_ms) < 4000:
        edge_penalty += 1.5

    transition_penalty = 0.0
    if previous_tail_dbfs is not None:
        transition_penalty = abs(head_db - previous_tail_dbfs) * 0.6

    return (avg_db * 1.1) + (mid_db * 0.8) - (boundary_gap * 0.5) - edge_penalty - transition_penalty


def _crossfade_for_segments(segment_files: list[str]) -> int:
    if len(segment_files) <= 1:
        return 0

    shortest_ms = 1_000_000
    for segment_path in segment_files:
        segment = AudioSegment.from_file(segment_path, format="mp3")
        shortest_ms = min(shortest_ms, len(segment))

    return int(_clamp(shortest_ms * 0.18, 1200, 4500))


def _resolve_mix_crossfade_duration(
    mix_plan: _MixIntentPlan,
    segment_files: list[str],
) -> int | list[int]:
    if mix_plan.transition_crossfade_seconds:
        transition_ms = [
            int(_clamp(seconds, 0.0, 8.0) * 1000) for seconds in mix_plan.transition_crossfade_seconds
        ]
        if transition_ms:
            return transition_ms
    if mix_plan.global_crossfade_seconds is not None:
        return int(_clamp(mix_plan.global_crossfade_seconds, 0.0, 8.0) * 1000)
    return _crossfade_for_segments(segment_files)


def _review_minimum_duration_seconds(mix_plan: _MixIntentPlan, track_count: int) -> float:
    if mix_plan.target_total_duration_seconds:
        return float(_clamp(mix_plan.target_total_duration_seconds * 0.72, 45.0, 3600.0))
    baseline = 24.0 if track_count <= 1 else (32.0 + ((track_count - 1) * 18.0))
    return float(_clamp(baseline, 24.0, 240.0))


def _review_engineered_mix_output(
    merged_file_path: str,
    split_files: list[str],
    mix_plan: _MixIntentPlan,
    *,
    track_count: int,
) -> _MixReviewResult:
    minimum_required_seconds = _review_minimum_duration_seconds(mix_plan, track_count)
    reasons: list[str] = []

    if not merged_file_path:
        return _MixReviewResult(
            approved=False,
            reasons=["Merged file path is missing."],
            duration_seconds=0.0,
            minimum_required_seconds=minimum_required_seconds,
            segment_count=len(split_files),
        )
    if not os.path.exists(merged_file_path):
        return _MixReviewResult(
            approved=False,
            reasons=[f"Merged file not found at {merged_file_path}."],
            duration_seconds=0.0,
            minimum_required_seconds=minimum_required_seconds,
            segment_count=len(split_files),
        )

    try:
        merged_audio = AudioSegment.from_file(merged_file_path, format="mp3")
    except Exception as exc:
        return _MixReviewResult(
            approved=False,
            reasons=[f"Merged file could not be opened for review ({exc})."],
            duration_seconds=0.0,
            minimum_required_seconds=minimum_required_seconds,
            segment_count=len(split_files),
        )

    duration_seconds = len(merged_audio) / 1000
    if duration_seconds + 0.1 < minimum_required_seconds:
        reasons.append(
            f"Duration {duration_seconds:.1f}s is below required {minimum_required_seconds:.1f}s."
        )

    if track_count > 1 and len(split_files) < 2:
        reasons.append(
            "Only one rendered segment was produced even though multiple tracks were selected."
        )

    loudness_db = _safe_dbfs(merged_audio)
    if loudness_db < -32.0:
        reasons.append(f"Output loudness is too low ({loudness_db:.1f} dBFS).")

    return _MixReviewResult(
        approved=not reasons,
        reasons=reasons,
        duration_seconds=duration_seconds,
        minimum_required_seconds=minimum_required_seconds,
        segment_count=len(split_files),
    )


def _build_audio_engineer_recovery_plan(
    mix_plan: _MixIntentPlan,
    review_result: _MixReviewResult,
    *,
    track_count: int,
) -> _MixIntentPlan:
    recovery_total_seconds = mix_plan.target_total_duration_seconds
    if recovery_total_seconds is None:
        recovery_total_seconds = int(max(180, review_result.minimum_required_seconds + 60))
    else:
        recovery_total_seconds = int(max(recovery_total_seconds, review_result.minimum_required_seconds + 30))

    recovery_crossfade = mix_plan.global_crossfade_seconds
    if recovery_crossfade is None:
        recovery_crossfade = 2.0 if track_count <= 2 else 2.4

    return _MixIntentPlan(
        strategy="creative_mix",
        use_timestamped_lyrics=False,
        target_segment_duration_seconds=int(_clamp(max(mix_plan.target_segment_duration_seconds, 36), 14, 70)),
        global_crossfade_seconds=float(_clamp(recovery_crossfade, 0.0, 8.0)),
        transition_crossfade_seconds=[],
        track_windows=mix_plan.track_windows,
        target_total_duration_seconds=int(_clamp(float(recovery_total_seconds), 60, 3600)),
        reason=f"{mix_plan.reason}|engineer_recovery",
    )


def _audio_engineer_render_and_merge(
    prompt: str,
    track_sources: list[_TrackSource],
    mix_plan: _MixIntentPlan,
    workspace: _WorkspacePaths,
) -> tuple[str, list[str], int | list[int]]:
    LOGGER.info("Audio engineer executing creative mixing flow.")
    split_files = _render_creative_mix_segments(
        prompt,
        track_sources,
        workspace.temp_split_dir,
        mix_plan,
    )

    if not split_files:
        raise RuntimeError("Audio engineer did not produce any split segments")

    crossfade_config = _resolve_mix_crossfade_duration(mix_plan, split_files)
    merged_file_path = merge_audio(
        split_files,
        crossfade_duration=crossfade_config,
        output_dir=workspace.output_dir,
    )
    if not merged_file_path:
        raise RuntimeError("Audio merge failed")
    return merged_file_path, split_files, crossfade_config


def _generate_ai_intelligent(prompt: str, workspace: _WorkspacePaths) -> str:
    song_plan = _fetch_song_plan(prompt, workspace.json_path)
    track_sources = _download_sources(song_plan, workspace.temp_dir)
    mix_plan = _plan_mix_intent(prompt, track_sources)
    LOGGER.info(
        "LLM audio engineer plan: strategy=%s target_segment=%ss target_total=%s reason=%s",
        mix_plan.strategy,
        mix_plan.target_segment_duration_seconds,
        mix_plan.target_total_duration_seconds if mix_plan.target_total_duration_seconds else "none",
        mix_plan.reason or "n/a",
    )

    merged_file_path, split_files, _ = _audio_engineer_render_and_merge(
        prompt,
        track_sources,
        mix_plan,
        workspace,
    )
    review_result = _review_engineered_mix_output(
        merged_file_path,
        split_files,
        mix_plan,
        track_count=len(track_sources),
    )
    LOGGER.info(
        "Audio engineer review: approved=%s duration=%.1fs required=%.1fs segments=%s reasons=%s",
        review_result.approved,
        review_result.duration_seconds,
        review_result.minimum_required_seconds,
        review_result.segment_count,
        "; ".join(review_result.reasons) if review_result.reasons else "none",
    )

    allow_auto_retry = _resolve_bool_env("AI_ENABLE_ENGINEER_AUTO_RETRY", True)
    if (not review_result.approved) and allow_auto_retry and len(track_sources) > 1:
        recovery_plan = _build_audio_engineer_recovery_plan(
            mix_plan,
            review_result,
            track_count=len(track_sources),
        )
        LOGGER.warning(
            "Audio engineer review requested retry. Re-rendering with recovery plan strategy=%s target_total=%s.",
            recovery_plan.strategy,
            recovery_plan.target_total_duration_seconds,
        )
        merged_file_path, split_files, _ = _audio_engineer_render_and_merge(
            prompt,
            track_sources,
            recovery_plan,
            workspace,
        )
        review_result = _review_engineered_mix_output(
            merged_file_path,
            split_files,
            recovery_plan,
            track_count=len(track_sources),
        )
        LOGGER.info(
            "Audio engineer review after retry: approved=%s duration=%.1fs required=%.1fs segments=%s reasons=%s",
            review_result.approved,
            review_result.duration_seconds,
            review_result.minimum_required_seconds,
            review_result.segment_count,
            "; ".join(review_result.reasons) if review_result.reasons else "none",
        )

    if not review_result.approved:
        reasons = "; ".join(review_result.reasons) if review_result.reasons else "unknown quality review failure"
        raise RuntimeError(f"Audio engineer review rejected the mix: {reasons}")

    LOGGER.info("Audio engineer approved final mix and delivered output to client.")
    return merged_file_path


def generate_ai(prompt: str, session_dir: str | None = None) -> str:
    workspace = _prepare_workspace(session_dir)
    return _generate_ai_intelligent(prompt, workspace)

