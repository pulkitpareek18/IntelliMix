from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Iterable

from ai import ai_main
from features.audio_download import download_audio
from features.audio_merge import merge_audio
from pydub import AudioSegment


def download_track_audio(url: str, *, name: str, output_dir: str) -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    download_audio(url, name=name, output_dir=output_dir)
    return str(Path(output_dir) / f"{name}.m4a")


def split_track_segment(audio: AudioSegment, *, start_ms: int, end_ms: int) -> AudioSegment:
    clamped_start = int(max(0, min(start_ms, len(audio))))
    clamped_end = int(max(clamped_start + 1, min(end_ms, len(audio))))
    return audio[clamped_start:clamped_end]


def apply_eq_profile(
    segment: AudioSegment,
    *,
    low_gain_db: float = 0.0,
    mid_gain_db: float = 0.0,
    high_gain_db: float = 0.0,
) -> AudioSegment:
    low_band = segment.low_pass_filter(220).apply_gain(low_gain_db)
    mid_band = segment.high_pass_filter(220).low_pass_filter(4000).apply_gain(mid_gain_db)
    high_band = segment.high_pass_filter(4000).apply_gain(high_gain_db)
    return low_band.overlay(mid_band).overlay(high_band)


def apply_reverb_effect(
    segment: AudioSegment,
    *,
    wet_amount: float = 0.0,
) -> AudioSegment:
    wet_amount = float(max(0.0, min(1.0, wet_amount)))
    if wet_amount <= 0.0:
        return segment

    wet = segment.low_pass_filter(6200)
    rendered = segment
    for index, delay_ms in enumerate((70, 130, 190, 260)):
        attenuation = max(0.01, wet_amount / (index + 1))
        gain = 20.0 * math.log10(attenuation)
        rendered = rendered.overlay(wet.apply_gain(gain), position=delay_ms)
    return rendered


def apply_delay_effect(
    segment: AudioSegment,
    *,
    delay_ms: int = 0,
    feedback: float = 0.0,
    repeats: int = 3,
) -> AudioSegment:
    delay_ms = int(max(0, delay_ms))
    feedback = float(max(0.0, min(0.95, feedback)))
    repeats = int(max(0, min(repeats, 8)))
    if delay_ms <= 0 or feedback <= 0.0 or repeats <= 0:
        return segment

    rendered = segment
    for repeat_index in range(1, repeats + 1):
        attenuation = max(0.01, feedback**repeat_index)
        gain = 20.0 * math.log10(attenuation)
        rendered = rendered.overlay(segment.apply_gain(gain), position=delay_ms * repeat_index)
    return rendered


def analyze_track_beats(audio: AudioSegment, *, label: str) -> ai_main._TrackDSPProfile:
    return ai_main._analyze_track_dsp(audio, label)


def normalize_for_mix(segment: AudioSegment, *, target_dbfs: float = -14.0) -> AudioSegment:
    current_dbfs = ai_main._safe_dbfs(segment)
    gain_db = ai_main._clamp(target_dbfs - current_dbfs, -10.0, 10.0)
    return segment.apply_gain(gain_db)


def render_segment_with_effects(
    audio: AudioSegment,
    *,
    start_ms: int,
    end_ms: int,
    low_gain_db: float = 0.0,
    mid_gain_db: float = 0.0,
    high_gain_db: float = 0.0,
    reverb_amount: float = 0.0,
    delay_ms: int = 0,
    delay_feedback: float = 0.0,
) -> AudioSegment:
    segment = split_track_segment(audio, start_ms=start_ms, end_ms=end_ms)
    if len(segment) > 2400:
        segment = segment.fade_in(min(800, len(segment) // 5)).fade_out(min(800, len(segment) // 5))
    segment = apply_eq_profile(
        segment,
        low_gain_db=low_gain_db,
        mid_gain_db=mid_gain_db,
        high_gain_db=high_gain_db,
    )
    segment = apply_reverb_effect(segment, wet_amount=reverb_amount)
    segment = apply_delay_effect(segment, delay_ms=delay_ms, feedback=delay_feedback)
    return normalize_for_mix(segment)


def merge_segments(
    segment_files: Iterable[str],
    *,
    output_dir: str,
    crossfade_ms: int | list[int],
) -> str:
    return str(merge_audio(list(segment_files), crossfade_duration=crossfade_ms, output_dir=output_dir))

