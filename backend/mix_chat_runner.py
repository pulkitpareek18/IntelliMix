from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from difflib import SequenceMatcher
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydub import AudioSegment
from ai.planning_prompts import (
    GUIDED_PLANNING_QUESTION_SYSTEM_INSTRUCTION as _GUIDED_PLANNING_QUESTION_SYSTEM_INSTRUCTION,
    GUIDED_REVISION_INTENT_SYSTEM_INSTRUCTION as _GUIDED_REVISION_INTENT_SYSTEM_INSTRUCTION,
    GUIDED_SONG_SUGGESTION_SYSTEM_INSTRUCTION as _GUIDED_SONG_SUGGESTION_SYSTEM_INSTRUCTION,
    TIMELINE_CONFLICT_CLASSIFIER_SYSTEM_INSTRUCTION as _TIMELINE_CONFLICT_CLASSIFIER_SYSTEM_INSTRUCTION,
)

LOGGER = logging.getLogger(__name__)
_APP = None


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _create_workspace(storage_root: str, session_id: str) -> Path:
    jobs_root = Path(storage_root).resolve() / "jobs"
    workspace = jobs_root / session_id
    required_dirs = [
        workspace / "temp",
        workspace / "temp" / "split",
        workspace / "temp" / "output",
        workspace / "csv",
        workspace / "static" / "output",
        workspace / "static" / "audio_dl",
        workspace / "static" / "video_dl",
    ]
    for directory in required_dirs:
        directory.mkdir(parents=True, exist_ok=True)
    return workspace


def _relative_file_url(session_id: str, filename: str) -> str:
    return f"/files/{session_id}/{filename}"


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _normalize_counter_map(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, float] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not key:
            continue
        score = _coerce_float(raw_value, 0.0)
        if score <= 0.0:
            continue
        normalized[key[:180]] = round(score, 4)
    return normalized


def _bump_counter(counter: dict[str, float], key: str, delta: float = 1.0) -> None:
    normalized_key = str(key or "").strip()
    if not normalized_key:
        return
    counter[normalized_key] = round(max(0.0, counter.get(normalized_key, 0.0) + float(delta)), 4)


def _top_counter_items(counter: dict[str, float], limit: int) -> list[str]:
    if not counter:
        return []
    ranked = sorted(counter.items(), key=lambda item: (-float(item[1]), item[0].lower()))
    return [key for key, _score in ranked[: max(1, limit)]]


def _default_memory_profile() -> dict[str, Any]:
    return {
        "artist_scores": {},
        "song_scores": {},
        "energy_scores": {},
        "use_case_scores": {},
        "transition_style_scores": {},
        "effect_averages": {
            "reverb_amount": 0.15,
            "delay_ms": 140.0,
            "delay_feedback": 0.16,
            "samples": 0,
        },
        "duration_state": {
            "avg_seconds": 300.0,
            "samples": 0,
        },
        "preferred_artists": [],
        "preferred_songs": [],
        "default_energy_curve": "",
        "default_use_case": "",
        "preferred_transition_style": "smooth",
        "updated_at": _now_iso(),
    }


def _default_memory_feedback() -> dict[str, Any]:
    return {
        "planning_approvals": 0,
        "planning_revisions": 0,
        "timeline_edits": 0,
        "timeline_attachment_runs": 0,
        "clarification_questions": 0,
        "timeline_resolution_counts": {
            "keep_attached_cuts": 0,
            "replan_with_prompt": 0,
            "replace_timeline": 0,
        },
        "run_kind_counts": {},
        "recent_actions": [],
        "updated_at": _now_iso(),
    }


def _default_memory_quality() -> dict[str, Any]:
    return {
        "samples": 0,
        "average_score": 0.0,
        "latest_score": 0.0,
        "grade_counts": {},
        "recent_scores": [],
        "updated_at": _now_iso(),
    }


def _normalize_memory_payload(memory_row: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    base_profile = _default_memory_profile()
    base_feedback = _default_memory_feedback()
    base_quality = _default_memory_quality()

    profile = _safe_dict(getattr(memory_row, "profile_json", {}))
    feedback = _safe_dict(getattr(memory_row, "feedback_json", {}))
    use_case_profiles = _safe_dict(getattr(memory_row, "use_case_profiles_json", {}))
    template_pack = _safe_dict(getattr(memory_row, "template_pack_json", {}))
    quality = _safe_dict(getattr(memory_row, "quality_json", {}))

    profile.setdefault("artist_scores", base_profile["artist_scores"])
    profile.setdefault("song_scores", base_profile["song_scores"])
    profile.setdefault("energy_scores", base_profile["energy_scores"])
    profile.setdefault("use_case_scores", base_profile["use_case_scores"])
    profile.setdefault("transition_style_scores", base_profile["transition_style_scores"])
    profile.setdefault("effect_averages", base_profile["effect_averages"])
    profile.setdefault("duration_state", base_profile["duration_state"])
    profile.setdefault("preferred_artists", base_profile["preferred_artists"])
    profile.setdefault("preferred_songs", base_profile["preferred_songs"])
    profile.setdefault("default_energy_curve", base_profile["default_energy_curve"])
    profile.setdefault("default_use_case", base_profile["default_use_case"])
    profile.setdefault("preferred_transition_style", base_profile["preferred_transition_style"])
    profile["artist_scores"] = _normalize_counter_map(profile.get("artist_scores"))
    profile["song_scores"] = _normalize_counter_map(profile.get("song_scores"))
    profile["energy_scores"] = _normalize_counter_map(profile.get("energy_scores"))
    profile["use_case_scores"] = _normalize_counter_map(profile.get("use_case_scores"))
    profile["transition_style_scores"] = _normalize_counter_map(profile.get("transition_style_scores"))

    duration_state = _safe_dict(profile.get("duration_state"))
    duration_state["avg_seconds"] = float(_coerce_float(duration_state.get("avg_seconds"), 300.0))
    duration_state["samples"] = int(max(0, _coerce_int(duration_state.get("samples"), 0)))
    profile["duration_state"] = duration_state

    effect_averages = _safe_dict(profile.get("effect_averages"))
    effect_averages["reverb_amount"] = float(_clamp(_coerce_float(effect_averages.get("reverb_amount"), 0.15), 0.0, 1.0))
    effect_averages["delay_ms"] = float(_clamp(_coerce_float(effect_averages.get("delay_ms"), 140.0), 0.0, 1200.0))
    effect_averages["delay_feedback"] = float(_clamp(_coerce_float(effect_averages.get("delay_feedback"), 0.16), 0.0, 0.95))
    effect_averages["samples"] = int(max(0, _coerce_int(effect_averages.get("samples"), 0)))
    profile["effect_averages"] = effect_averages

    if not isinstance(profile.get("preferred_artists"), list):
        profile["preferred_artists"] = []
    if not isinstance(profile.get("preferred_songs"), list):
        profile["preferred_songs"] = []

    feedback.setdefault("planning_approvals", base_feedback["planning_approvals"])
    feedback.setdefault("planning_revisions", base_feedback["planning_revisions"])
    feedback.setdefault("timeline_edits", base_feedback["timeline_edits"])
    feedback.setdefault("timeline_attachment_runs", base_feedback["timeline_attachment_runs"])
    feedback.setdefault("clarification_questions", base_feedback["clarification_questions"])
    feedback.setdefault("timeline_resolution_counts", base_feedback["timeline_resolution_counts"])
    feedback.setdefault("run_kind_counts", base_feedback["run_kind_counts"])
    feedback.setdefault("recent_actions", base_feedback["recent_actions"])
    feedback["timeline_resolution_counts"] = {
        "keep_attached_cuts": int(max(0, _coerce_int(_safe_dict(feedback.get("timeline_resolution_counts")).get("keep_attached_cuts"), 0))),
        "replan_with_prompt": int(max(0, _coerce_int(_safe_dict(feedback.get("timeline_resolution_counts")).get("replan_with_prompt"), 0))),
        "replace_timeline": int(max(0, _coerce_int(_safe_dict(feedback.get("timeline_resolution_counts")).get("replace_timeline"), 0))),
    }
    feedback["run_kind_counts"] = {
        key: int(max(0, _coerce_int(value, 0)))
        for key, value in _safe_dict(feedback.get("run_kind_counts")).items()
        if str(key).strip()
    }
    if not isinstance(feedback.get("recent_actions"), list):
        feedback["recent_actions"] = []

    normalized_use_case_profiles: dict[str, Any] = {}
    for raw_key, raw_value in use_case_profiles.items():
        key = str(raw_key).strip()
        if not key or not isinstance(raw_value, dict):
            continue
        normalized_use_case_profiles[key[:120]] = {
            "count": int(max(0, _coerce_int(raw_value.get("count"), 0))),
            "avg_target_duration_seconds": float(_coerce_float(raw_value.get("avg_target_duration_seconds"), 0.0)),
            "energy_scores": _normalize_counter_map(raw_value.get("energy_scores")),
            "quality_avg": float(_coerce_float(raw_value.get("quality_avg"), 0.0)),
            "quality_samples": int(max(0, _coerce_int(raw_value.get("quality_samples"), 0))),
            "updated_at": str(raw_value.get("updated_at", "")) or _now_iso(),
        }
    use_case_profiles = normalized_use_case_profiles

    if not isinstance(template_pack.get("templates"), dict):
        template_pack["templates"] = {}
    if not isinstance(template_pack.get("global"), dict):
        template_pack["global"] = {}

    quality.setdefault("samples", base_quality["samples"])
    quality.setdefault("average_score", base_quality["average_score"])
    quality.setdefault("latest_score", base_quality["latest_score"])
    quality.setdefault("grade_counts", base_quality["grade_counts"])
    quality.setdefault("recent_scores", base_quality["recent_scores"])
    quality["samples"] = int(max(0, _coerce_int(quality.get("samples"), 0)))
    quality["average_score"] = float(_coerce_float(quality.get("average_score"), 0.0))
    quality["latest_score"] = float(_coerce_float(quality.get("latest_score"), 0.0))
    quality["grade_counts"] = {
        str(key).strip()[:8]: int(max(0, _coerce_int(value, 0)))
        for key, value in _safe_dict(quality.get("grade_counts")).items()
        if str(key).strip()
    }
    if not isinstance(quality.get("recent_scores"), list):
        quality["recent_scores"] = []

    return profile, feedback, use_case_profiles, template_pack, quality


def _recompute_profile_summary(profile: dict[str, Any]) -> None:
    profile["preferred_artists"] = _top_counter_items(_safe_dict(profile.get("artist_scores")), limit=8)
    profile["preferred_songs"] = _top_counter_items(_safe_dict(profile.get("song_scores")), limit=12)

    energy_scores = _safe_dict(profile.get("energy_scores"))
    use_case_scores = _safe_dict(profile.get("use_case_scores"))
    transition_scores = _safe_dict(profile.get("transition_style_scores"))

    top_energy = _top_counter_items(energy_scores, limit=1)
    top_use_case = _top_counter_items(use_case_scores, limit=1)
    top_transition = _top_counter_items(transition_scores, limit=1)

    profile["default_energy_curve"] = top_energy[0] if top_energy else ""
    profile["default_use_case"] = top_use_case[0] if top_use_case else ""
    profile["preferred_transition_style"] = top_transition[0] if top_transition else "smooth"
    profile["updated_at"] = _now_iso()


def _update_duration_state(profile: dict[str, Any], seconds: int) -> None:
    if seconds <= 0:
        return
    duration_state = _safe_dict(profile.get("duration_state"))
    avg = float(_coerce_float(duration_state.get("avg_seconds"), 300.0))
    samples = int(max(0, _coerce_int(duration_state.get("samples"), 0)))
    next_samples = samples + 1
    next_avg = ((avg * samples) + float(seconds)) / float(next_samples)
    duration_state["avg_seconds"] = round(float(_clamp(next_avg, 60.0, 3600.0)), 2)
    duration_state["samples"] = next_samples
    profile["duration_state"] = duration_state


def _merge_effect_preference(profile: dict[str, Any], *, reverb_amount: float, delay_ms: float, delay_feedback: float) -> None:
    effect_averages = _safe_dict(profile.get("effect_averages"))
    samples = int(max(0, _coerce_int(effect_averages.get("samples"), 0)))
    current_reverb = float(_coerce_float(effect_averages.get("reverb_amount"), 0.15))
    current_delay_ms = float(_coerce_float(effect_averages.get("delay_ms"), 140.0))
    current_delay_feedback = float(_coerce_float(effect_averages.get("delay_feedback"), 0.16))

    next_samples = samples + 1
    effect_averages["reverb_amount"] = round(
        ((current_reverb * samples) + float(_clamp(reverb_amount, 0.0, 1.0))) / next_samples,
        4,
    )
    effect_averages["delay_ms"] = round(
        ((current_delay_ms * samples) + float(_clamp(delay_ms, 0.0, 1200.0))) / next_samples,
        2,
    )
    effect_averages["delay_feedback"] = round(
        ((current_delay_feedback * samples) + float(_clamp(delay_feedback, 0.0, 0.95))) / next_samples,
        4,
    )
    effect_averages["samples"] = next_samples
    profile["effect_averages"] = effect_averages


def _record_feedback_event(feedback: dict[str, Any], event: str, metadata: dict[str, Any] | None = None) -> None:
    run_kind_counts = _safe_dict(feedback.get("run_kind_counts"))
    _bump_counter(run_kind_counts, event, delta=1.0)
    feedback["run_kind_counts"] = {key: int(value) for key, value in run_kind_counts.items()}

    actions = feedback.get("recent_actions")
    if not isinstance(actions, list):
        actions = []
    action_payload = {"event": str(event)[:80], "at": _now_iso()}
    if metadata:
        action_payload["meta"] = metadata
    actions.append(action_payload)
    feedback["recent_actions"] = actions[-30:]
    feedback["updated_at"] = _now_iso()


def _normalize_use_case_label(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    lowered = normalized.lower()
    if "party" in lowered or "dance" in lowered or "club" in lowered:
        return "Party / dance floor"
    if "wedding" in lowered:
        return "Wedding celebration"
    if "sleep" in lowered or "focus" in lowered or "study" in lowered:
        return "Sleep / focus listening"
    if "drive" in lowered or "travel" in lowered or "road" in lowered:
        return "Drive / road trip"
    if "workout" in lowered or "gym" in lowered:
        return "Workout"
    return normalized[:120]


def _update_use_case_profiles(
    use_case_profiles: dict[str, Any],
    *,
    use_case: str,
    energy_curve: str,
    target_duration_seconds: int,
    quality_score: float | None,
) -> None:
    if not _bool_env("AI_MEMORY_USECASE_PROFILES_ENABLED", True):
        return

    label = _normalize_use_case_label(use_case)
    if not label:
        return

    profile = _safe_dict(use_case_profiles.get(label))
    count = int(max(0, _coerce_int(profile.get("count"), 0)))
    next_count = count + 1
    current_avg_duration = float(_coerce_float(profile.get("avg_target_duration_seconds"), 0.0))
    if target_duration_seconds > 0:
        if count == 0:
            next_avg_duration = float(target_duration_seconds)
        else:
            next_avg_duration = ((current_avg_duration * count) + target_duration_seconds) / float(next_count)
    else:
        next_avg_duration = current_avg_duration
    energy_scores = _normalize_counter_map(profile.get("energy_scores"))
    if energy_curve:
        _bump_counter(energy_scores, energy_curve[:120], delta=1.0)

    quality_samples = int(max(0, _coerce_int(profile.get("quality_samples"), 0)))
    quality_avg = float(_coerce_float(profile.get("quality_avg"), 0.0))
    if quality_score is not None and quality_score > 0:
        next_quality_samples = quality_samples + 1
        quality_avg = ((quality_avg * quality_samples) + quality_score) / float(next_quality_samples)
        quality_samples = next_quality_samples

    use_case_profiles[label] = {
        "count": next_count,
        "avg_target_duration_seconds": round(float(next_avg_duration), 2),
        "energy_scores": energy_scores,
        "quality_avg": round(float(quality_avg), 3),
        "quality_samples": quality_samples,
        "updated_at": _now_iso(),
    }


def _refresh_template_pack(
    template_pack: dict[str, Any],
    *,
    profile: dict[str, Any],
    use_case_profiles: dict[str, Any],
    feedback: dict[str, Any],
    quality: dict[str, Any],
) -> None:
    if not _bool_env("AI_MEMORY_TEMPLATE_PACKS_ENABLED", True):
        return

    effect_averages = _safe_dict(profile.get("effect_averages"))
    transition_style = str(profile.get("preferred_transition_style", "smooth")).strip() or "smooth"
    templates: dict[str, Any] = {}

    ranked_use_cases = sorted(
        (
            (key, _safe_dict(value))
            for key, value in use_case_profiles.items()
            if isinstance(value, dict)
        ),
        key=lambda item: int(max(0, _coerce_int(item[1].get("count"), 0))),
        reverse=True,
    )
    for use_case, stats in ranked_use_cases[:5]:
        energy_scores = _normalize_counter_map(stats.get("energy_scores"))
        top_energy = _top_counter_items(energy_scores, limit=1)
        avg_duration = int(_coerce_int(stats.get("avg_target_duration_seconds"), 0))
        default_crossfade = 3.0 if "mellow" in (top_energy[0].lower() if top_energy else "") else 2.0
        templates[use_case] = {
            "energy_curve": top_energy[0] if top_energy else str(profile.get("default_energy_curve", "")),
            "target_duration_seconds": avg_duration if avg_duration > 0 else int(
                _coerce_int(_safe_dict(profile.get("duration_state")).get("avg_seconds"), 300)
            ),
            "transition_style": transition_style,
            "default_crossfade_seconds": default_crossfade,
            "effects": {
                "reverb_amount": float(_coerce_float(effect_averages.get("reverb_amount"), 0.15)),
                "delay_ms": int(_coerce_int(effect_averages.get("delay_ms"), 140)),
                "delay_feedback": float(_coerce_float(effect_averages.get("delay_feedback"), 0.16)),
            },
            "quality_avg": float(_coerce_float(stats.get("quality_avg"), 0.0)),
        }

    resolution_counts = _safe_dict(feedback.get("timeline_resolution_counts"))
    preferred_resolution = "keep_attached_cuts"
    preferred_resolution_score = -1
    for resolution_id in ("keep_attached_cuts", "replan_with_prompt", "replace_timeline"):
        score = int(_coerce_int(resolution_counts.get(resolution_id), 0))
        if score > preferred_resolution_score:
            preferred_resolution = resolution_id
            preferred_resolution_score = score

    template_pack["templates"] = templates
    template_pack["global"] = {
        "preferred_timeline_resolution": preferred_resolution,
        "preferred_transition_style": transition_style,
        "preferred_effects": {
            "reverb_amount": float(_coerce_float(effect_averages.get("reverb_amount"), 0.15)),
            "delay_ms": int(_coerce_int(effect_averages.get("delay_ms"), 140)),
            "delay_feedback": float(_coerce_float(effect_averages.get("delay_feedback"), 0.16)),
        },
        "quality_average": float(_coerce_float(quality.get("average_score"), 0.0)),
    }
    template_pack["updated_at"] = _now_iso()


def _compute_mix_quality_score(
    *,
    proposal_payload: dict[str, Any],
    run_kind: str,
    timeline_resolution: str | None = None,
) -> dict[str, Any]:
    if not _bool_env("AI_MEMORY_QUALITY_SCORING_ENABLED", True):
        return {"score": 0.0, "grade": "N/A", "components": {}, "at": _now_iso()}

    proposal = _safe_dict(proposal_payload.get("proposal"))
    requirements = _safe_dict(proposal_payload.get("requirements"))
    tracks_raw = proposal_payload.get("tracks")
    tracks = tracks_raw if isinstance(tracks_raw, list) else []
    segments_raw = proposal.get("segments")
    segments = segments_raw if isinstance(segments_raw, list) else []

    segment_count = len([item for item in segments if isinstance(item, dict)])
    track_count = len([item for item in tracks if isinstance(item, dict)])

    crossfades: list[float] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        crossfades.append(float(_coerce_float(segment.get("crossfade_after_seconds"), 0.0)))

    segment_score = _clamp(6.0 + (segment_count * 1.9), 0.0, 24.0)
    track_score = _clamp(4.0 + (track_count * 2.8), 0.0, 18.0)

    if crossfades:
        avg_crossfade = sum(crossfades) / len(crossfades)
        smoothness = 20.0 - min(20.0, abs(avg_crossfade - 2.0) * 6.5)
        crossfade_score = _clamp(smoothness, 0.0, 20.0)
    else:
        crossfade_score = 8.0

    target_duration = int(_coerce_int(requirements.get("target_duration_seconds"), 0))
    estimated_duration = float(_coerce_float(proposal.get("estimated_duration_seconds"), 0.0))
    if target_duration > 0 and estimated_duration > 0:
        duration_gap = abs(float(target_duration) - float(estimated_duration))
        duration_score = _clamp(24.0 - ((duration_gap / max(1.0, target_duration)) * 34.0), 0.0, 24.0)
    else:
        duration_score = 10.0

    strategy_bonus = 0.0
    if run_kind == "timeline_edit":
        strategy_bonus = 6.0
    elif run_kind == "timeline_attachment":
        if timeline_resolution == "replan_with_prompt":
            strategy_bonus = 5.0
        elif timeline_resolution == "keep_attached_cuts":
            strategy_bonus = 3.0
        elif timeline_resolution == "replace_timeline":
            strategy_bonus = 2.0
    elif run_kind in {"planning_execute", "prompt"}:
        strategy_bonus = 4.0

    score = float(round(_clamp(segment_score + track_score + crossfade_score + duration_score + strategy_bonus, 0.0, 100.0), 3))
    grade = "A" if score >= 85.0 else "B" if score >= 70.0 else "C" if score >= 55.0 else "D"
    return {
        "score": score,
        "grade": grade,
        "components": {
            "segment_score": round(float(segment_score), 3),
            "track_score": round(float(track_score), 3),
            "crossfade_score": round(float(crossfade_score), 3),
            "duration_score": round(float(duration_score), 3),
            "strategy_bonus": round(float(strategy_bonus), 3),
        },
        "at": _now_iso(),
    }


def _append_quality_stats(quality: dict[str, Any], quality_payload: dict[str, Any]) -> None:
    score = float(_coerce_float(quality_payload.get("score"), 0.0))
    if score <= 0:
        return
    samples = int(max(0, _coerce_int(quality.get("samples"), 0)))
    average_score = float(_coerce_float(quality.get("average_score"), 0.0))
    next_samples = samples + 1
    next_average = ((average_score * samples) + score) / float(next_samples)
    quality["samples"] = next_samples
    quality["average_score"] = round(next_average, 3)
    quality["latest_score"] = round(score, 3)
    grade = str(quality_payload.get("grade", "D")).strip()[:2]
    grade_counts = _safe_dict(quality.get("grade_counts"))
    grade_counts[grade] = int(max(0, _coerce_int(grade_counts.get(grade), 0)) + 1)
    quality["grade_counts"] = grade_counts
    recent_scores = quality.get("recent_scores")
    if not isinstance(recent_scores, list):
        recent_scores = []
    recent_scores.append(
        {
            "score": round(score, 3),
            "grade": grade,
            "at": str(quality_payload.get("at", _now_iso())),
            "components": _safe_dict(quality_payload.get("components")),
        }
    )
    quality["recent_scores"] = recent_scores[-30:]
    quality["updated_at"] = _now_iso()


def _derive_user_memory_context(
    *,
    profile: dict[str, Any],
    feedback: dict[str, Any],
    use_case_profiles: dict[str, Any],
    template_pack: dict[str, Any],
    quality: dict[str, Any],
) -> dict[str, Any]:
    duration_state = _safe_dict(profile.get("duration_state"))
    effect_averages = _safe_dict(profile.get("effect_averages"))
    resolution_counts = _safe_dict(feedback.get("timeline_resolution_counts"))

    preferred_resolution = "keep_attached_cuts"
    preferred_resolution_score = -1
    for resolution_id in ("keep_attached_cuts", "replan_with_prompt", "replace_timeline"):
        score = int(_coerce_int(resolution_counts.get(resolution_id), 0))
        if score > preferred_resolution_score:
            preferred_resolution = resolution_id
            preferred_resolution_score = score

    ranked_use_case_profiles = sorted(
        (
            (name, _safe_dict(details))
            for name, details in use_case_profiles.items()
            if isinstance(details, dict)
        ),
        key=lambda item: int(max(0, _coerce_int(item[1].get("count"), 0))),
        reverse=True,
    )
    dominant_use_case = ranked_use_case_profiles[0][0] if ranked_use_case_profiles else str(profile.get("default_use_case", ""))

    return {
        "preferred_artists": [str(item) for item in profile.get("preferred_artists", []) if str(item).strip()][:6],
        "preferred_songs": [str(item) for item in profile.get("preferred_songs", []) if str(item).strip()][:10],
        "default_energy_curve": str(profile.get("default_energy_curve", "")).strip(),
        "default_use_case": str(profile.get("default_use_case", "")).strip(),
        "average_target_duration_seconds": int(_coerce_int(duration_state.get("avg_seconds"), 300)),
        "preferred_transition_style": str(profile.get("preferred_transition_style", "smooth")).strip() or "smooth",
        "preferred_effects": {
            "reverb_amount": float(_coerce_float(effect_averages.get("reverb_amount"), 0.15)),
            "delay_ms": int(_coerce_int(effect_averages.get("delay_ms"), 140)),
            "delay_feedback": float(_coerce_float(effect_averages.get("delay_feedback"), 0.16)),
        },
        "preferred_timeline_resolution": preferred_resolution,
        "dominant_use_case_profile": dominant_use_case,
        "quality_average": float(_coerce_float(quality.get("average_score"), 0.0)),
        "quality_samples": int(max(0, _coerce_int(quality.get("samples"), 0))),
        "template_pack": _safe_dict(template_pack.get("templates")),
    }


def _update_profile_from_prompt(profile: dict[str, Any], prompt: str) -> None:
    songs = _parse_song_list_from_prompt(prompt)[:10]
    song_scores = _safe_dict(profile.get("song_scores"))
    for song in songs:
        _bump_counter(song_scores, song[:180], delta=0.6)
    profile["song_scores"] = song_scores

    artist_hint, _requested_count = _extract_artist_and_song_count_from_prompt(prompt)
    artist_scores = _safe_dict(profile.get("artist_scores"))
    if artist_hint:
        _bump_counter(artist_scores, artist_hint[:180], delta=0.9)
    profile["artist_scores"] = artist_scores

    inferred_energy = _infer_energy_from_prompt(prompt)
    energy_scores = _safe_dict(profile.get("energy_scores"))
    if inferred_energy:
        _bump_counter(energy_scores, inferred_energy[:120], delta=0.5)
    profile["energy_scores"] = energy_scores

    inferred_use_case = _infer_use_case_from_prompt(prompt)
    use_case_scores = _safe_dict(profile.get("use_case_scores"))
    if inferred_use_case:
        _bump_counter(use_case_scores, inferred_use_case[:120], delta=0.5)
    profile["use_case_scores"] = use_case_scores

    try:
        from ai import ai_main

        duration_seconds = ai_main._parse_requested_total_duration_seconds(prompt)  # noqa: SLF001
        if isinstance(duration_seconds, int) and duration_seconds > 0:
            _update_duration_state(profile, duration_seconds)
    except Exception:
        pass

    transition_scores = _safe_dict(profile.get("transition_style_scores"))
    lowered = (prompt or "").lower()
    if "energetic" in lowered or "club" in lowered or "dance" in lowered:
        _bump_counter(transition_scores, "energetic", delta=0.45)
    if "smooth" in lowered or "seamless" in lowered or "long transition" in lowered:
        _bump_counter(transition_scores, "smooth", delta=0.45)
    if "ambient" in lowered or "cinematic" in lowered:
        _bump_counter(transition_scores, "ambient", delta=0.4)
    profile["transition_style_scores"] = transition_scores

    _recompute_profile_summary(profile)


def _update_profile_from_required_slots(profile: dict[str, Any], required_slots: dict[str, Any]) -> None:
    songs_slot = _safe_dict(required_slots.get("songs_set"))
    songs = songs_slot.get("value")
    song_scores = _safe_dict(profile.get("song_scores"))
    if isinstance(songs, list):
        for song in songs[:12]:
            song_value = str(song).strip()
            if song_value:
                _bump_counter(song_scores, song_value[:180], delta=1.2)
    profile["song_scores"] = song_scores

    energy_slot = _safe_dict(required_slots.get("energy_curve"))
    energy_value = str(energy_slot.get("value", "")).strip()
    if energy_value:
        energy_scores = _safe_dict(profile.get("energy_scores"))
        _bump_counter(energy_scores, energy_value[:120], delta=1.0)
        profile["energy_scores"] = energy_scores

    use_case_slot = _safe_dict(required_slots.get("use_case"))
    use_case_value = str(use_case_slot.get("value", "")).strip()
    if use_case_value:
        use_case_scores = _safe_dict(profile.get("use_case_scores"))
        _bump_counter(use_case_scores, _normalize_use_case_label(use_case_value)[:120], delta=1.0)
        profile["use_case_scores"] = use_case_scores

    _recompute_profile_summary(profile)


def _update_profile_from_proposal_payload(profile: dict[str, Any], proposal_payload: dict[str, Any]) -> None:
    requirements = _safe_dict(proposal_payload.get("requirements"))
    tracks = proposal_payload.get("tracks")
    if isinstance(tracks, list):
        song_scores = _safe_dict(profile.get("song_scores"))
        artist_scores = _safe_dict(profile.get("artist_scores"))
        for track in tracks[:20]:
            if not isinstance(track, dict):
                continue
            title = str(track.get("title", "")).strip()
            artist = str(track.get("artist", "")).strip()
            label = f"{title} - {artist}".strip(" -")
            if label:
                _bump_counter(song_scores, label[:180], delta=0.9)
            if artist:
                _bump_counter(artist_scores, artist[:180], delta=0.7)
        profile["song_scores"] = song_scores
        profile["artist_scores"] = artist_scores

    target_duration = int(_coerce_int(requirements.get("target_duration_seconds"), 0))
    if target_duration > 0:
        _update_duration_state(profile, target_duration)

    transition_style = str(requirements.get("transition_style", "")).strip()
    if transition_style:
        transition_scores = _safe_dict(profile.get("transition_style_scores"))
        _bump_counter(transition_scores, transition_style[:120], delta=0.8)
        profile["transition_style_scores"] = transition_scores

    effects = _safe_dict(requirements.get("effects"))
    _merge_effect_preference(
        profile,
        reverb_amount=float(_coerce_float(effects.get("reverb_amount"), 0.15)),
        delay_ms=float(_coerce_float(effects.get("delay_ms"), 140.0)),
        delay_feedback=float(_coerce_float(effects.get("delay_feedback"), 0.16)),
    )
    _recompute_profile_summary(profile)


def _persist_user_memory(
    memory_row: Any,
    *,
    profile: dict[str, Any],
    feedback: dict[str, Any],
    use_case_profiles: dict[str, Any],
    template_pack: dict[str, Any],
    quality: dict[str, Any],
) -> None:
    memory_row.profile_json = profile
    memory_row.feedback_json = feedback
    memory_row.use_case_profiles_json = use_case_profiles
    memory_row.template_pack_json = template_pack
    memory_row.quality_json = quality
    memory_row.updated_at = datetime.now(timezone.utc)


def _sanitize_timeline_segments(session_dir: Path, raw_segments: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_segments, list) or not raw_segments:
        raise RuntimeError("Timeline edit run requires non-empty segments.")

    duration_cache: dict[int, int] = {}
    normalized: list[dict[str, Any]] = []

    for index, item in enumerate(raw_segments):
        if not isinstance(item, dict):
            raise RuntimeError(f"Invalid segment at index {index}.")

        track_index = _coerce_int(item.get("track_index"), -1)
        if track_index < 0:
            raise RuntimeError(f"segments[{index}].track_index is invalid.")

        source_path = session_dir / "temp" / f"{track_index}.m4a"
        if track_index not in duration_cache:
            if not source_path.exists():
                raise RuntimeError(f"Missing source track for index {track_index}.")
            duration_cache[track_index] = len(AudioSegment.from_file(str(source_path), format="m4a"))

        max_ms = duration_cache[track_index]
        start_ms = _clamp(float(_coerce_int(item.get("start_ms"), 0)), 0.0, float(max(0, max_ms - 1000)))
        end_ms = _clamp(float(_coerce_int(item.get("end_ms"), max_ms)), start_ms + 1000.0, float(max_ms))

        effects_raw = item.get("effects", {})
        if not isinstance(effects_raw, dict):
            effects_raw = {}
        eq_raw = item.get("eq", {})
        if not isinstance(eq_raw, dict):
            eq_raw = {}

        normalized.append(
            {
                "id": str(item.get("id", f"seg_{index + 1}")).strip()[:80] or f"seg_{index + 1}",
                "order": index,
                "segment_name": str(item.get("segment_name", "")).strip()[:120] or f"Segment {index + 1}",
                "track_index": track_index,
                "track_id": str(item.get("track_id", track_index)).strip()[:80] or str(track_index),
                "track_title": str(item.get("track_title", "")).strip()[:200],
                "start_ms": int(start_ms),
                "end_ms": int(end_ms),
                "duration_ms": int(end_ms - start_ms),
                "crossfade_after_seconds": _clamp(_coerce_float(item.get("crossfade_after_seconds"), 0.0), 0.0, 8.0),
                "effects": {
                    "reverb_amount": _clamp(_coerce_float(effects_raw.get("reverb_amount"), 0.0), 0.0, 1.0),
                    "delay_ms": int(_clamp(_coerce_float(effects_raw.get("delay_ms"), 0.0), 0.0, 1200.0)),
                    "delay_feedback": _clamp(_coerce_float(effects_raw.get("delay_feedback"), 0.0), 0.0, 0.95),
                },
                "eq": {
                    "low_gain_db": _coerce_float(eq_raw.get("low_gain_db"), 0.0),
                    "mid_gain_db": _coerce_float(eq_raw.get("mid_gain_db"), 0.0),
                    "high_gain_db": _coerce_float(eq_raw.get("high_gain_db"), 0.0),
                },
            }
        )

    for index in range(len(normalized) - 1):
        current = normalized[index]
        nxt = normalized[index + 1]
        current_duration = max(0.1, current["duration_ms"] / 1000.0)
        next_duration = max(0.1, nxt["duration_ms"] / 1000.0)
        max_crossfade = _clamp(min(current_duration, next_duration) - 0.1, 0.0, 8.0)
        current["crossfade_after_seconds"] = _clamp(current["crossfade_after_seconds"], 0.0, max_crossfade)
    if normalized:
        normalized[-1]["crossfade_after_seconds"] = 0.0

    return normalized


def _extract_json_dict(raw_text: str) -> dict[str, Any]:
    if not raw_text:
        return {}
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _detect_prompt_cut_conflict_heuristic(prompt: str) -> tuple[bool, bool, list[str]]:
    text = (prompt or "").strip().lower()
    if not text:
        return False, False, []

    keep_phrases = (
        "keep same cuts",
        "keep the same cuts",
        "preserve cuts",
        "keep attached timeline",
        "reuse attached timeline",
        "same boundaries",
        "don't change cuts",
        "do not change cuts",
    )
    keep_hint = any(phrase in text for phrase in keep_phrases)

    cut_keywords = (
        "change cut",
        "change cuts",
        "replace cut",
        "replace cuts",
        "new cuts",
        "new cut points",
        "retime",
        "retiming",
        "trim",
        "shift segment",
        "move segment",
        "change start",
        "change end",
        "set start",
        "set end",
        "timestamp",
        "timecode",
    )
    keyword_hits = [keyword for keyword in cut_keywords if keyword in text]
    has_segment_reference = bool(re.search(r"\bseg(?:ment)?\s*\d+\b", text))
    has_time_reference = bool(
        re.search(
            r"\b\d{1,2}:\d{2}(?::\d{2})?\b|"
            r"\b\d+(?:\.\d+)?\s*(?:ms|msec|s|sec|secs|seconds)\b",
            text,
        )
    )

    score = 0
    reasons: list[str] = []
    if keyword_hits:
        score += 2
        reasons.append("Prompt requests cut/timeline changes.")
    if has_segment_reference:
        score += 1
        reasons.append("Prompt references specific segment indices.")
    if has_time_reference and (keyword_hits or has_segment_reference):
        score += 2
        reasons.append("Prompt includes explicit timing instructions for segments.")
    if keep_hint:
        score -= 3
        reasons.append("Prompt explicitly asks to preserve existing cuts.")

    conflict = score >= 3 and not keep_hint
    ambiguous = score > 0 and not conflict and not keep_hint
    return conflict, ambiguous, reasons[:4]


def _classify_timeline_conflict_with_llm(prompt: str, heuristic_reasons: list[str]) -> tuple[bool, str]:
    if not _bool_env("AI_ENABLE_TIMELINE_CONFLICT_LLM", True):
        return False, ""

    try:
        from ai.ai import AIServiceError, generate_with_instruction
    except Exception:
        return False, ""

    classifier_payload = {
        "prompt": prompt,
        "heuristic_reasons": heuristic_reasons,
    }
    try:
        raw = generate_with_instruction(
            prompt=json.dumps(classifier_payload, ensure_ascii=True),
            system_instruction=_TIMELINE_CONFLICT_CLASSIFIER_SYSTEM_INSTRUCTION,
        )
    except AIServiceError as exc:
        LOGGER.warning(
            "Timeline conflict classifier unavailable (%s); using heuristic decision only.",
            exc.error_code,
        )
        return False, ""
    except Exception:
        LOGGER.warning("Timeline conflict classifier failed unexpectedly; using heuristic decision only.")
        return False, ""

    parsed = _extract_json_dict(raw)
    if not parsed:
        return False, ""
    reason = str(parsed.get("reason", "")).strip()[:300]
    return _coerce_bool(parsed.get("conflict"), False), reason


def _normalize_tracks_with_preview(raw_tracks: Any, mix_session_id: str) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    if not isinstance(raw_tracks, list):
        return tracks
    for raw_track in raw_tracks:
        if not isinstance(raw_track, dict):
            continue
        track = dict(raw_track)
        preview_filename = str(track.get("preview_filename", "")).strip()
        preview_url = str(track.get("preview_url", "")).strip()
        if preview_filename and not preview_url:
            track["preview_url"] = _relative_file_url(mix_session_id, Path(preview_filename).name)
        tracks.append(track)
    return tracks


def _apply_non_cut_prompt_refinements(proposal: dict[str, Any], prompt: str) -> tuple[dict[str, Any], list[str]]:
    updated = dict(proposal)
    segments_raw = updated.get("segments", [])
    if not isinstance(segments_raw, list):
        updated["segments"] = []
        return updated, []

    segments = [dict(segment) for segment in segments_raw if isinstance(segment, dict)]
    if not segments:
        updated["segments"] = []
        return updated, []

    prompt_text = (prompt or "").strip()
    lowered = prompt_text.lower()
    applied: list[str] = []

    crossfade_target: float | None = None
    explicit_crossfade = re.search(r"(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)\s*crossfade", lowered)
    if explicit_crossfade:
        crossfade_target = _clamp(_coerce_float(explicit_crossfade.group(1), 2.0), 0.0, 8.0)
        applied.append(f"crossfade set to ~{crossfade_target:.1f}s where possible")
    elif any(phrase in lowered for phrase in {"long transition", "long transitions", "smooth transitions", "softer transition"}):
        crossfade_target = 3.0
        applied.append("longer crossfades for smoother transitions")
    elif any(phrase in lowered for phrase in {"quick transition", "hard cut", "snappy transitions"}):
        crossfade_target = 0.6
        applied.append("shorter crossfades for punchier transitions")

    reverb_target: float | None = None
    if "no reverb" in lowered or "without reverb" in lowered or "dry mix" in lowered:
        reverb_target = 0.0
        applied.append("reverb disabled")
    else:
        explicit_reverb = re.search(r"reverb(?:\s*(?:amount|level)?)?\s*(?:to|=)?\s*(0(?:\.\d+)?|1(?:\.0+)?)", lowered)
        if explicit_reverb:
            reverb_target = _clamp(_coerce_float(explicit_reverb.group(1), 0.2), 0.0, 1.0)
            applied.append(f"reverb set to {reverb_target:.2f}")
        elif "more reverb" in lowered:
            reverb_target = 0.28
            applied.append("slightly higher reverb")
        elif "less reverb" in lowered:
            reverb_target = 0.08
            applied.append("reduced reverb")

    delay_ms_target: int | None = None
    delay_feedback_target: float | None = None
    if "no delay" in lowered or "without delay" in lowered:
        delay_ms_target = 0
        delay_feedback_target = 0.0
        applied.append("delay disabled")
    elif "delay" in lowered:
        explicit_delay = re.search(r"delay[^0-9]{0,12}(\d{2,4})\s*ms", lowered)
        if explicit_delay:
            delay_ms_target = int(_clamp(_coerce_float(explicit_delay.group(1), 160.0), 0.0, 1200.0))
            applied.append(f"delay set to {delay_ms_target}ms")
        elif "more delay" in lowered:
            delay_ms_target = 240
            delay_feedback_target = 0.24
            applied.append("slightly longer delay tails")
        elif "less delay" in lowered:
            delay_ms_target = 90
            delay_feedback_target = 0.14
            applied.append("shorter delay tails")

    for index, segment in enumerate(segments):
        effects = segment.get("effects", {})
        if not isinstance(effects, dict):
            effects = {}
        if reverb_target is not None:
            effects["reverb_amount"] = float(reverb_target)
        if delay_ms_target is not None:
            effects["delay_ms"] = int(delay_ms_target)
        if delay_feedback_target is not None:
            effects["delay_feedback"] = float(_clamp(delay_feedback_target, 0.0, 0.95))
        segment["effects"] = effects

        if crossfade_target is not None and index < len(segments) - 1:
            current_duration = max(0.1, (_coerce_int(segment.get("end_ms"), 0) - _coerce_int(segment.get("start_ms"), 0)) / 1000.0)
            nxt = segments[index + 1]
            next_duration = max(0.1, (_coerce_int(nxt.get("end_ms"), 0) - _coerce_int(nxt.get("start_ms"), 0)) / 1000.0)
            max_crossfade = _clamp(min(current_duration, next_duration) - 0.1, 0.0, 8.0)
            segment["crossfade_after_seconds"] = float(_clamp(crossfade_target, 0.0, max_crossfade))

    if segments:
        segments[-1]["crossfade_after_seconds"] = 0.0

    updated["segments"] = segments
    base_rationale = str(updated.get("mixing_rationale", "")).strip()
    if prompt_text:
        refinement_line = f"Refined with attached timeline and user request: {prompt_text[:240]}"
        updated["mixing_rationale"] = f"{base_rationale} {refinement_line}".strip()
    return updated, applied


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name, str(default))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _guided_retryable_error_code(error_code: str) -> bool:
    normalized = str(error_code or "").strip().upper()
    return normalized in {
        "AI_RATE_LIMITED",
        "AI_TEMPORARILY_UNAVAILABLE",
        "AI_UPSTREAM_ERROR",
        "AI_UNEXPECTED_ERROR",
    }


def _generate_with_guided_retries(
    *,
    payload: dict[str, Any],
    system_instruction: str,
    task_label: str,
) -> str:
    from ai.ai import AIServiceError, generate_with_instruction

    extra_retries = _int_env("AI_GUIDED_RATE_LIMIT_EXTRA_RETRIES", 2, 0, 10)
    retry_base_seconds = _float_env("AI_GUIDED_RATE_LIMIT_RETRY_BASE_SECONDS", 4.0, 1.0, 60.0)
    retry_max_seconds = _int_env("AI_GUIDED_RATE_LIMIT_RETRY_MAX_SECONDS", 30, 1, 300)
    prompt_json = json.dumps(payload, ensure_ascii=True)

    for attempt in range(extra_retries + 1):
        try:
            return generate_with_instruction(
                prompt=prompt_json,
                system_instruction=system_instruction,
            )
        except AIServiceError as exc:
            if not _guided_retryable_error_code(exc.error_code) or attempt >= extra_retries:
                raise
            computed_wait = int(math.ceil(retry_base_seconds * (2**attempt)))
            wait_seconds = computed_wait
            if exc.retry_after_seconds:
                wait_seconds = max(wait_seconds, int(exc.retry_after_seconds))
            wait_seconds = max(1, min(wait_seconds, retry_max_seconds))
            LOGGER.warning(
                "%s (%s). Guided retry in %ss (attempt %s/%s).",
                task_label,
                exc.error_code,
                wait_seconds,
                attempt + 1,
                extra_retries,
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"{task_label} failed after guided retries.")


def _normalize_song_list(candidates: list[str]) -> list[str]:
    songs: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        value = re.sub(r"\s+", " ", str(candidate).strip()).strip(" -:;,")
        if len(value) < 2:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        songs.append(value[:180])
    return songs


def _looks_like_generic_song_request(candidate: str) -> bool:
    compact = re.sub(r"\s+", " ", str(candidate or "").strip(" -:;,.")).lower()
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


def _parse_song_list_from_prompt(prompt: str) -> list[str]:
    try:
        from ai import ai_main

        parsed = ai_main._extract_explicit_song_list(prompt)  # noqa: SLF001
    except Exception:
        parsed = []
    songs = [f"{title} - {artist}".strip(" -") for title, artist in parsed if title]
    if songs:
        filtered = [song for song in songs if not _looks_like_generic_song_request(song)]
        if filtered:
            return _normalize_song_list(filtered)

    compact = re.sub(r"\s+", " ", prompt or "").strip()
    if not compact:
        return []
    using_match = re.search(
        r"\b(?:songs?\s*:|using|use|mix of|mix with|combine)\b(?P<body>.+)",
        compact,
        flags=re.IGNORECASE,
    )
    if not using_match:
        return []
    body = re.split(r"[.\n]", using_match.group("body"), maxsplit=1)[0]
    raw_parts = [part.strip() for part in re.split(r",|;|\band\b", body, flags=re.IGNORECASE) if part.strip()]
    filtered_parts = [part for part in raw_parts if not _looks_like_generic_song_request(part)]
    return _normalize_song_list(filtered_parts)


def _extract_artist_and_song_count_from_prompt(prompt: str) -> tuple[str, int]:
    compact = re.sub(r"\s+", " ", prompt or "").strip()
    if not compact:
        return "", 0

    default_count = _coerce_int(os.environ.get("AI_GUIDED_DEFAULT_SONG_SUGGESTION_COUNT"), 5)
    if default_count <= 0:
        default_count = 5
    count_match = re.search(r"\b(?P<count>\d{1,4})\s*(?:songs?|tracks?)\b", compact, flags=re.IGNORECASE)
    requested_count = default_count
    if count_match:
        parsed_count = _coerce_int(count_match.group("count"), default_count)
        if parsed_count > 0:
            requested_count = parsed_count

    artist_patterns = [
        r"\b(?P<count>\d{1,4})\s+(?P<artist>[a-z0-9][a-z0-9 .&'\-]{1,80}?)\s+songs?\b",
        r"\bsongs?\s+(?:of|by|from)\s+(?P<artist>[a-z0-9][a-z0-9 .&'\-]{1,80})\b",
        r"\b(?:mashup|mix|medley|playlist)\s+(?P<artist>[a-z0-9][a-z0-9 .&'\-]{1,80}?)\s+songs?\b",
        r"\bmix(?:ing)?\s+(?:of|with)\s+(?P<count>\d{1,4})?\s*(?:songs?|tracks?)?\s*(?:by|of|from)?\s*(?P<artist>[a-z0-9][a-z0-9 .&'\-]{1,80})\b",
    ]
    artist_value = ""
    for pattern in artist_patterns:
        match = re.search(pattern, compact, flags=re.IGNORECASE)
        if not match:
            continue
        artist_value = str(match.groupdict().get("artist", "")).strip(" ,.;:-")
        if match.groupdict().get("count"):
            parsed_count = _coerce_int(match.groupdict().get("count"), requested_count)
            if parsed_count > 0:
                requested_count = parsed_count
        if artist_value:
            break

    if artist_value:
        artist_value = re.split(r"\b(?:for|with|and|to|that)\b", artist_value, maxsplit=1, flags=re.IGNORECASE)[0].strip(
            " ,.;:-"
        )
    return artist_value, requested_count


def _suggest_songs_with_ai(prompt: str, artist_value: str, requested_count: int) -> list[str]:
    if not _bool_env("AI_ENABLE_GUIDED_SONG_SUGGESTIONS", True):
        return []

    if requested_count <= 0:
        return []

    payload = {
        "prompt": str(prompt or "")[:1500],
        "artist_hint": artist_value[:120] if artist_value else "",
        "requested_count": int(requested_count),
    }

    try:
        raw = _generate_with_guided_retries(
            payload=payload,
            system_instruction=_GUIDED_SONG_SUGGESTION_SYSTEM_INSTRUCTION,
            task_label="Guided song suggestion LLM unavailable",
        )
    except Exception as exc:
        error_code = str(getattr(exc, "error_code", "UNKNOWN")).strip() or "UNKNOWN"
        if _bool_env("AI_PLANNING_PAUSE_ON_AI_FAILURE", True):
            raise RuntimeError(f"AI song suggestion unavailable ({error_code})") from exc
        LOGGER.warning(
            "Guided song suggestion LLM unavailable (%s); falling back to manual song confirmation.",
            error_code,
        )
        return []

    parsed = _extract_json_dict(raw)
    raw_songs = parsed.get("songs")
    if not isinstance(raw_songs, list):
        return []

    candidates: list[str] = []
    for item in raw_songs:
        if isinstance(item, dict):
            title = str(item.get("title", "")).strip()
            artist = str(item.get("artist", "")).strip()
            label = f"{title} - {artist}".strip(" -")
            if label:
                candidates.append(label)
            continue
        if isinstance(item, str):
            compact = item.strip()
            if compact:
                candidates.append(compact)

    normalized = _normalize_song_list(candidates)
    filtered = [song for song in normalized if not _looks_like_generic_song_request(song)]
    return filtered[:requested_count]


def _suggest_songs_from_prompt(prompt: str, memory_context: dict[str, Any] | None = None) -> list[str]:
    artist_value, requested_count = _extract_artist_and_song_count_from_prompt(prompt)
    if requested_count <= 0:
        requested_count = _coerce_int(os.environ.get("AI_GUIDED_DEFAULT_SONG_SUGGESTION_COUNT"), 5)
        if requested_count <= 0:
            requested_count = 5
    prompt_with_memory = str(prompt or "")
    if memory_context:
        preferred_artists = memory_context.get("preferred_artists", [])
        preferred_songs = memory_context.get("preferred_songs", [])
        default_use_case = str(memory_context.get("default_use_case", "")).strip()
        default_energy = str(memory_context.get("default_energy_curve", "")).strip()
        memory_lines: list[str] = []
        if isinstance(preferred_artists, list) and preferred_artists:
            memory_lines.append(f"Preferred artists from memory: {', '.join(str(item) for item in preferred_artists[:5])}.")
        if isinstance(preferred_songs, list) and preferred_songs:
            memory_lines.append(f"Previously liked songs: {', '.join(str(item) for item in preferred_songs[:6])}.")
        if default_use_case:
            memory_lines.append(f"Frequent use-case: {default_use_case}.")
        if default_energy:
            memory_lines.append(f"Typical energy preference: {default_energy}.")
        if memory_lines:
            prompt_with_memory = f"{prompt_with_memory}\n\nUser memory context:\n" + "\n".join(memory_lines)
    return _suggest_songs_with_ai(prompt_with_memory, artist_value, requested_count)


def _resolve_initial_song_candidates(
    prompt: str,
    *,
    force_suggestions: bool = False,
    memory_context: dict[str, Any] | None = None,
) -> tuple[list[str], str]:
    if not force_suggestions:
        explicit_songs = _parse_song_list_from_prompt(prompt)
        if explicit_songs:
            return explicit_songs, "explicit"

    suggested_songs = _suggest_songs_from_prompt(prompt, memory_context)
    if suggested_songs:
        return suggested_songs, "suggested"

    if force_suggestions:
        explicit_songs = _parse_song_list_from_prompt(prompt)
        if explicit_songs:
            return explicit_songs, "explicit"

    if memory_context:
        preferred_songs = memory_context.get("preferred_songs", [])
        if isinstance(preferred_songs, list):
            memory_songs = _normalize_song_list([str(item) for item in preferred_songs if str(item).strip()])
            if memory_songs:
                _artist_hint, requested_count = _extract_artist_and_song_count_from_prompt(prompt)
                target = requested_count if requested_count > 0 else len(memory_songs)
                return memory_songs[:target], "memory"

    return [], "none"


def _parse_song_list_from_other_text(other_text: str) -> list[str]:
    if not other_text.strip():
        return []
    parts = [part.strip() for part in re.split(r"[\n,;]|(?:\band\b)", other_text, flags=re.IGNORECASE) if part.strip()]
    filtered = [part for part in parts if not _looks_like_generic_song_request(part)]
    return _normalize_song_list(filtered)


def _infer_energy_from_prompt(prompt: str) -> str | None:
    text = (prompt or "").lower()
    if any(token in text for token in {"sleep", "chill", "calm", "sufi", "ambient", "lofi", "mellow"}):
        return "Warm and mellow"
    if any(token in text for token in {"wedding", "party", "club", "dance", "high energy", "hype"}):
        return "High-energy peaks and drops"
    if any(token in text for token in {"workout", "gym", "running"}):
        return "Steady energetic drive"
    if any(token in text for token in {"romantic", "soulful", "emotional"}):
        return "Soulful gradual build"
    return None


def _infer_use_case_from_prompt(prompt: str) -> str | None:
    text = (prompt or "").lower()
    if "sleep" in text or "study" in text or "focus" in text:
        return "Sleep / focus listening"
    if "wedding" in text:
        return "Wedding celebration"
    if "party" in text or "club" in text or "dance floor" in text:
        return "Party / dance floor"
    if "workout" in text or "gym" in text:
        return "Workout"
    if "drive" in text or "road trip" in text:
        return "Drive / road trip"
    return None


def _merge_planning_answers(existing_answers: dict[str, Any], new_answers: list[dict[str, str]]) -> dict[str, Any]:
    merged = dict(existing_answers or {})
    for answer in new_answers:
        question_id = answer.get("question_id", "").strip()
        if not question_id:
            continue
        merged[question_id] = {
            "selected_option_id": answer.get("selected_option_id", "").strip(),
            "other_text": answer.get("other_text", "").strip(),
            "answered_at": datetime.now(timezone.utc).isoformat(),
        }
    return merged


def _answer_value(answers: dict[str, Any], question_id: str) -> tuple[str, str]:
    raw = answers.get(question_id)
    if not isinstance(raw, dict):
        return "", ""
    selected = str(raw.get("selected_option_id", "")).strip()
    other = str(raw.get("other_text", "")).strip()
    return selected, other


def _extract_song_slot_snapshot(required_slots: dict[str, Any] | None) -> tuple[list[str], str, float]:
    if not isinstance(required_slots, dict):
        return [], "none", 0.0
    songs_slot = required_slots.get("songs_set")
    if not isinstance(songs_slot, dict):
        return [], "none", 0.0
    value = songs_slot.get("value")
    if not isinstance(value, list):
        return [], "none", 0.0
    songs = _normalize_song_list([str(item) for item in value if str(item).strip()])
    songs = [song for song in songs if not _looks_like_generic_song_request(song)]
    source = str(songs_slot.get("source", "none")).strip() or "none"
    confidence = _coerce_float(songs_slot.get("confidence"), 0.0)
    return songs, source, confidence


def _resolve_planning_state(
    prompt: str,
    answers: dict[str, Any],
    *,
    previous_required_slots: dict[str, Any] | None = None,
    memory_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], float]:
    songs_selected, songs_other = _answer_value(answers, "songs_set")
    force_song_refresh = songs_selected == "regenerate_suggestions"
    if memory_context is None:
        songs, songs_source = _resolve_initial_song_candidates(
            prompt,
            force_suggestions=force_song_refresh,
        )
    else:
        songs, songs_source = _resolve_initial_song_candidates(
            prompt,
            force_suggestions=force_song_refresh,
            memory_context=memory_context,
        )
    previous_songs, previous_song_source, previous_song_confidence = _extract_song_slot_snapshot(previous_required_slots)

    if songs_selected == "looks_correct" and previous_songs:
        songs = previous_songs
        songs_source = previous_song_source or "previous"
    elif songs_selected in {"add_remove", "custom_list", "other"} and songs_other:
        custom_songs = _parse_song_list_from_other_text(songs_other)
        if custom_songs:
            songs = custom_songs
            songs_source = "user_other"
        elif previous_songs:
            songs = previous_songs
            songs_source = previous_song_source or "previous"
    elif songs_selected == "looks_correct" and not songs and songs_other:
        custom_songs = _parse_song_list_from_other_text(songs_other)
        if custom_songs:
            songs = custom_songs
            songs_source = "user_other"

    # Preserve previously detected/suggested songs when user confirms existing list
    # and upstream suggestion lookup is temporarily unavailable.
    if not songs and previous_songs:
        if songs_selected in {"looks_correct", "regenerate_suggestions"}:
            songs = previous_songs
            songs_source = previous_song_source or "previous"
        elif not songs_selected:
            songs = previous_songs
            songs_source = previous_song_source or "previous"

    energy_selected, energy_other = _answer_value(answers, "energy_curve")
    if energy_other:
        energy_curve = energy_other[:120]
        energy_confidence = 0.95
    elif energy_selected:
        energy_lookup = {
            "balanced": "Balanced flow",
            "slow_build": "Slow build",
            "peaks_valleys": "Peaks and valleys",
            "high_energy": "High energy throughout",
            "mellow": "Warm and mellow",
            "other": "",
        }
        energy_curve = energy_lookup.get(energy_selected, energy_selected.replace("_", " ").title()).strip()
        energy_confidence = 0.9 if energy_curve else 0.35
    else:
        inferred_energy = _infer_energy_from_prompt(prompt)
        if inferred_energy:
            energy_curve = inferred_energy
            energy_confidence = 0.65
        elif memory_context and str(memory_context.get("default_energy_curve", "")).strip():
            energy_curve = str(memory_context.get("default_energy_curve", "")).strip()[:120]
            energy_confidence = 0.58
        else:
            energy_curve = ""
            energy_confidence = 0.0

    use_case_selected, use_case_other = _answer_value(answers, "use_case")
    if use_case_other:
        use_case = use_case_other[:120]
        use_case_confidence = 0.95
    elif use_case_selected:
        use_case_lookup = {
            "party": "Party / dance floor",
            "wedding": "Wedding celebration",
            "sleep": "Sleep / focus listening",
            "workout": "Workout",
            "drive": "Drive / road trip",
            "other": "",
        }
        use_case = use_case_lookup.get(use_case_selected, use_case_selected.replace("_", " ").title()).strip()
        use_case_confidence = 0.9 if use_case else 0.35
    else:
        inferred_use_case = _infer_use_case_from_prompt(prompt)
        if inferred_use_case:
            use_case = inferred_use_case
            use_case_confidence = 0.65
        elif memory_context and str(memory_context.get("default_use_case", "")).strip():
            use_case = str(memory_context.get("default_use_case", "")).strip()[:120]
            use_case_confidence = 0.58
        else:
            use_case = ""
            use_case_confidence = 0.0

    if songs_selected in {"looks_correct", "add_remove", "custom_list"} and songs:
        songs_confidence = 0.95
    elif songs and songs_source == "explicit":
        songs_confidence = 0.82
    elif songs and songs_source == "suggested":
        songs_confidence = 0.68
    elif songs and songs_source in {"previous", "user_other"}:
        songs_confidence = max(0.78, previous_song_confidence)
    elif songs and songs_source == "memory":
        songs_confidence = 0.62
    else:
        songs_confidence = 0.0
    required_slots = {
        "songs_set": {
            "label": "Song set",
            "status": "filled" if songs else "missing",
            "value": songs,
            "source": songs_source,
            "confidence": round(float(songs_confidence), 3),
        },
        "energy_curve": {
            "label": "Energy curve",
            "status": "filled" if energy_curve else "missing",
            "value": energy_curve,
            "confidence": round(float(energy_confidence), 3),
        },
        "use_case": {
            "label": "Purpose / use-case",
            "status": "filled" if use_case else "missing",
            "value": use_case,
            "confidence": round(float(use_case_confidence), 3),
        },
    }

    confidence_values = [slot["confidence"] for slot in required_slots.values()]
    confidence_score = sum(confidence_values) / max(1, len(confidence_values))
    return required_slots, float(round(confidence_score, 3))


def _build_planning_must_ask_ids(
    *,
    required_slots: dict[str, Any],
    answers: dict[str, Any],
    round_count: int,
    min_rounds: int,
    max_questions: int = 3,
) -> list[str]:
    must_ask_ids: list[str] = []
    if round_count < min_rounds:
        must_ask_ids = ["songs_set", "energy_curve", "use_case"]
    else:
        for slot_id in ("songs_set", "energy_curve", "use_case"):
            slot = required_slots.get(slot_id, {})
            status = str(slot.get("status", "missing"))
            confidence = float(slot.get("confidence", 0.0) or 0.0)
            selected, other = _answer_value(answers, slot_id)
            if status != "filled" or confidence < 0.78 or (not selected and not other):
                must_ask_ids.append(slot_id)

    unique_ids: list[str] = []
    for slot_id in must_ask_ids:
        if slot_id not in unique_ids:
            unique_ids.append(slot_id)
    return unique_ids[:max_questions]


def _build_planning_questions_fallback(must_ask_ids: list[str]) -> list[dict[str, Any]]:
    question_bank: dict[str, dict[str, Any]] = {
        "songs_set": {
            "question_id": "songs_set",
            "question": "Confirm the songs for this mix.",
            "allow_other": True,
            "options": [
                {"id": "looks_correct", "label": "Looks correct (Recommended)"},
                {"id": "add_remove", "label": "Add/remove songs"},
                {"id": "custom_list", "label": "Use custom list"},
            ],
        },
        "energy_curve": {
            "question_id": "energy_curve",
            "question": "How should the energy evolve?",
            "allow_other": True,
            "options": [
                {"id": "balanced", "label": "Balanced flow (Recommended)"},
                {"id": "slow_build", "label": "Slow build"},
                {"id": "peaks_valleys", "label": "Peaks and valleys"},
                {"id": "high_energy", "label": "High energy throughout"},
                {"id": "mellow", "label": "Warm and mellow"},
            ],
        },
        "use_case": {
            "question_id": "use_case",
            "question": "What is this mix mainly for?",
            "allow_other": True,
            "options": [
                {"id": "party", "label": "Party / dance floor"},
                {"id": "wedding", "label": "Wedding"},
                {"id": "sleep", "label": "Sleep / focus"},
                {"id": "drive", "label": "Drive / travel"},
                {"id": "workout", "label": "Workout"},
            ],
        },
    }

    return [question_bank[slot_id] for slot_id in must_ask_ids if slot_id in question_bank]


def _sanitize_adaptive_questions(raw_questions: Any, must_ask_ids: list[str]) -> list[dict[str, Any]]:
    if not isinstance(raw_questions, list):
        return []

    allowed_option_ids: dict[str, list[str]] = {
        "songs_set": ["looks_correct", "add_remove", "custom_list"],
        "energy_curve": ["balanced", "slow_build", "peaks_valleys", "high_energy", "mellow"],
        "use_case": ["party", "wedding", "sleep", "drive", "workout"],
    }

    by_id: dict[str, dict[str, Any]] = {}
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        question_id = str(item.get("question_id", "")).strip()
        if question_id not in must_ask_ids or question_id in by_id:
            continue
        question_text = str(item.get("question", "")).strip()[:220]
        raw_options = item.get("options")
        options: list[dict[str, str]] = []
        if isinstance(raw_options, list):
            allowed_ids = set(allowed_option_ids.get(question_id, []))
            seen_ids: set[str] = set()
            for option in raw_options:
                if not isinstance(option, dict):
                    continue
                option_id = str(option.get("id", "")).strip()
                label = str(option.get("label", "")).strip()[:120]
                if not option_id or not label:
                    continue
                if option_id not in allowed_ids or option_id in seen_ids:
                    continue
                seen_ids.add(option_id)
                options.append({"id": option_id, "label": label})
        if not question_text or not options:
            continue
        by_id[question_id] = {
            "question_id": question_id,
            "question": question_text,
            "allow_other": bool(item.get("allow_other", True)),
            "options": options,
        }

    ordered: list[dict[str, Any]] = []
    for slot_id in must_ask_ids:
        if slot_id in by_id:
            ordered.append(by_id[slot_id])
    return ordered


def _build_planning_questions(
    *,
    prompt: str,
    required_slots: dict[str, Any],
    answers: dict[str, Any],
    round_count: int,
    min_rounds: int,
    previous_questions: list[dict[str, Any]] | None = None,
    memory_context: dict[str, Any] | None = None,
    max_questions: int = 3,
) -> list[dict[str, Any]]:
    must_ask_ids = _build_planning_must_ask_ids(
        required_slots=required_slots,
        answers=answers,
        round_count=round_count,
        min_rounds=min_rounds,
        max_questions=max_questions,
    )
    if not must_ask_ids:
        return []

    fallback_questions = _build_planning_questions_fallback(must_ask_ids)
    preserved_questions = _sanitize_adaptive_questions(previous_questions, must_ask_ids)
    if not _bool_env("AI_ENABLE_ADAPTIVE_PLANNING_QUESTIONS", True):
        if _bool_env("AI_PLANNING_PAUSE_ON_AI_FAILURE", True):
            raise RuntimeError("AI adaptive question generator disabled.")
        return preserved_questions or fallback_questions

    payload = {
        "prompt": str(prompt or "")[:1800],
        "must_ask_ids": must_ask_ids,
        "required_slots": required_slots,
        "answers": answers,
        "round_count": int(round_count),
        "max_questions": int(max_questions),
        "memory_context": memory_context or {},
    }

    try:
        raw = _generate_with_guided_retries(
            payload=payload,
            system_instruction=_GUIDED_PLANNING_QUESTION_SYSTEM_INSTRUCTION,
            task_label="Adaptive planning question generator unavailable",
        )
    except Exception as exc:
        error_code = str(getattr(exc, "error_code", "UNKNOWN")).strip() or "UNKNOWN"
        if _bool_env("AI_PLANNING_PAUSE_ON_AI_FAILURE", True):
            raise RuntimeError(f"AI adaptive question generator unavailable ({error_code})") from exc
        LOGGER.warning(
            "Adaptive planning question generator unavailable (%s); using fallback questions.",
            error_code,
        )
        return preserved_questions or fallback_questions

    parsed = _extract_json_dict(raw)
    sanitized = _sanitize_adaptive_questions(parsed.get("questions"), must_ask_ids)
    if not sanitized:
        if _bool_env("AI_PLANNING_PAUSE_ON_AI_FAILURE", True):
            raise RuntimeError("AI adaptive question generator returned invalid schema.")
        return preserved_questions or fallback_questions

    sanitized_by_id = {
        str(item.get("question_id")): item
        for item in sanitized
        if isinstance(item, dict) and str(item.get("question_id", "")).strip()
    }
    fallback_by_id = {
        str(item.get("question_id")): item
        for item in fallback_questions
        if isinstance(item, dict) and str(item.get("question_id", "")).strip()
    }
    merged: list[dict[str, Any]] = []
    for slot_id in must_ask_ids:
        if slot_id in sanitized_by_id:
            merged.append(sanitized_by_id[slot_id])
        elif slot_id in fallback_by_id:
            merged.append(fallback_by_id[slot_id])
    return merged[:max_questions]


def _extract_transition_count_request(prompt: str) -> int | None:
    text = (prompt or "").lower()
    matches = re.findall(r"\b(\d{1,4})\s+transitions?\b", text)
    if not matches:
        return None
    requested = _coerce_int(matches[-1], 0)
    if requested <= 0:
        return None
    return requested


def _extract_segment_count_request(prompt: str) -> int | None:
    text = (prompt or "").lower()
    matches = re.findall(r"\b(?:total\s*)?(\d{1,4})\s+segments?\b", text)
    if not matches:
        return None
    requested = _coerce_int(matches[-1], 0)
    if requested <= 0:
        return None
    return requested


def _clean_repeat_song_phrase(raw_phrase: str) -> str:
    phrase = re.sub(r"\s+", " ", raw_phrase or "").strip(" ,.;:-").lower()
    if not phrase:
        return ""
    phrase = re.sub(
        r"^(?:i want|i need|please|add|use|keep|repeat|play|put|include|of these songs|among these songs)\s+",
        "",
        phrase,
        flags=re.IGNORECASE,
    )
    phrase = re.sub(r"\b(?:song|songs|track|tracks)\b", "", phrase, flags=re.IGNORECASE)
    phrase = re.sub(r"\s+", " ", phrase).strip(" ,.;:-")
    return phrase


def _song_title(song: str) -> str:
    return re.split(r"\s*-\s*", str(song or ""), maxsplit=1)[0].strip().lower()


def _phrase_song_similarity(phrase: str, song: str) -> float:
    phrase_norm = re.sub(r"\s+", " ", phrase.strip().lower())
    song_norm = re.sub(r"\s+", " ", song.strip().lower())
    title_norm = _song_title(song)

    base = _text_similarity(phrase_norm, song_norm)
    title_similarity = _text_similarity(phrase_norm, title_norm)
    ratio_score = SequenceMatcher(None, phrase_norm, title_norm).ratio()

    phrase_tokens = [token for token in re.findall(r"[a-z0-9]+", phrase_norm) if token]
    title_tokens = [token for token in re.findall(r"[a-z0-9]+", title_norm) if token]
    token_score = 0.0
    if phrase_tokens and title_tokens:
        token_matches: list[float] = []
        for phrase_token in phrase_tokens:
            best = max(SequenceMatcher(None, phrase_token, title_token).ratio() for title_token in title_tokens)
            token_matches.append(best)
        token_score = sum(token_matches) / len(token_matches)

    return max(base, title_similarity, ratio_score, token_score)


def _resolve_song_reference(phrase: str, songs: list[str], minimum_score: float = 0.55) -> str | None:
    cleaned = _clean_repeat_song_phrase(phrase)
    if not cleaned:
        return None

    normalized_songs = [str(song).strip() for song in songs if str(song).strip()]
    if not normalized_songs:
        return None

    best_song = ""
    best_score = 0.0
    for candidate in normalized_songs:
        score = _phrase_song_similarity(cleaned, candidate)
        if score > best_score:
            best_score = score
            best_song = candidate
    if best_song and best_score >= minimum_score:
        return best_song
    return None


def _sanitize_revision_ai_intent(intent: Any, songs_context: list[str]) -> dict[str, Any]:
    parsed = _safe_dict(intent)
    normalized_context = _normalize_song_list([str(song) for song in songs_context if str(song).strip()])

    def _bounded_int(raw_value: Any, minimum: int, maximum: int) -> int | None:
        value = _coerce_int(raw_value, 0)
        if value < minimum or value > maximum:
            return None
        return value

    songset_change = bool(parsed.get("songset_change", False))

    requested_songs: list[str] = []
    raw_requested_songs = parsed.get("requested_songs")
    if isinstance(raw_requested_songs, list):
        for item in raw_requested_songs:
            raw_song = str(item).strip()
            if not raw_song:
                continue
            resolved = _resolve_song_reference(raw_song, normalized_context)
            if resolved and resolved not in requested_songs:
                requested_songs.append(resolved)
                continue
            if songset_change and not _looks_like_generic_song_request(raw_song):
                cleaned = re.sub(r"\s+", " ", raw_song).strip(" -:;,.")
                if cleaned and cleaned not in requested_songs:
                    requested_songs.append(cleaned[:180])

    repeat_requests: dict[str, int] = {}
    raw_repeat_requests = parsed.get("repeat_requests")
    repeat_items: list[tuple[str, int]] = []
    if isinstance(raw_repeat_requests, dict):
        for raw_song, raw_count in raw_repeat_requests.items():
            repeat_items.append((str(raw_song).strip(), max(1, min(2000, _coerce_int(raw_count, 1)))))
    elif isinstance(raw_repeat_requests, list):
        for item in raw_repeat_requests:
            if not isinstance(item, dict):
                continue
            song_value = str(item.get("song", "")).strip()
            count_value = max(1, min(2000, _coerce_int(item.get("count"), 1)))
            if song_value:
                repeat_items.append((song_value, count_value))
    for raw_song, count in repeat_items:
        resolved = _resolve_song_reference(raw_song, normalized_context)
        if not resolved:
            continue
        repeat_requests[resolved] = max(repeat_requests.get(resolved, 0), count)

    preferred_sequence: list[str] = []
    seen: set[str] = set()
    raw_preferred = parsed.get("preferred_sequence")
    if isinstance(raw_preferred, list):
        for raw_item in raw_preferred:
            resolved = _resolve_song_reference(str(raw_item).strip(), normalized_context)
            if not resolved:
                continue
            key = resolved.lower()
            if key in seen:
                continue
            seen.add(key)
            preferred_sequence.append(resolved)

    return {
        "songset_change": songset_change,
        "requested_songs": requested_songs,
        "transition_count": _bounded_int(parsed.get("transition_count"), 1, 2000),
        "segment_count": _bounded_int(parsed.get("segment_count"), 1, 2000),
        "repeat_requests": repeat_requests,
        "preferred_sequence": preferred_sequence,
        "mirror_sequence_at_end": bool(parsed.get("mirror_sequence_at_end", False)),
        "notes": str(parsed.get("notes", "")).strip()[:300],
    }


def _interpret_revision_prompt_with_ai(
    *,
    source_prompt: str,
    revision_prompt: str,
    current_songs: list[str],
    required_slots: dict[str, Any] | None = None,
    memory_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    prompt_text = str(revision_prompt or "").strip()
    if not prompt_text:
        return None
    if not _bool_env("AI_ENABLE_GUIDED_REVISION_INTERPRETER", True):
        return None

    required = _safe_dict(required_slots)
    payload = {
        "source_prompt": str(source_prompt or "")[:1800],
        "revision_prompt": prompt_text[:1800],
        "current_songs": _normalize_song_list([str(item) for item in current_songs if str(item).strip()])[:20],
        "energy_curve": str(_safe_dict(required.get("energy_curve")).get("value", "")).strip()[:120],
        "use_case": str(_safe_dict(required.get("use_case")).get("value", "")).strip()[:120],
        "memory_context": {
            "default_energy_curve": str(_safe_dict(memory_context).get("default_energy_curve", "")).strip()[:120],
            "default_use_case": str(_safe_dict(memory_context).get("default_use_case", "")).strip()[:120],
            "preferred_transition_style": str(_safe_dict(memory_context).get("preferred_transition_style", "")).strip()[:80],
        },
    }

    try:
        raw = _generate_with_guided_retries(
            payload=payload,
            system_instruction=_GUIDED_REVISION_INTENT_SYSTEM_INSTRUCTION,
            task_label="Guided revision intent interpreter unavailable",
        )
    except Exception as exc:
        error_code = str(getattr(exc, "error_code", "UNKNOWN")).strip() or "UNKNOWN"
        if _bool_env("AI_GUIDED_REVISION_AI_STRICT", True):
            raise RuntimeError(f"AI revision interpreter unavailable ({error_code})") from exc
        LOGGER.warning(
            "Guided revision intent interpreter unavailable (%s); using fallback revision heuristics.",
            error_code,
        )
        return None

    parsed = _extract_json_dict(raw)
    if not parsed:
        if _bool_env("AI_GUIDED_REVISION_AI_STRICT", True):
            raise RuntimeError("AI revision interpreter returned invalid JSON.")
        LOGGER.warning("Guided revision intent interpreter returned invalid JSON; using fallback revision heuristics.")
        return None

    return _sanitize_revision_ai_intent(parsed, current_songs)


def _extract_song_repeat_requests(prompt: str, songs: list[str]) -> dict[str, int]:
    if not prompt or not songs:
        return {}

    repeats: dict[str, int] = {}
    normalized_songs = [str(song).strip() for song in songs if str(song).strip()]
    if not normalized_songs:
        return repeats

    text = re.sub(r"\s+", " ", prompt)
    patterns = [
        re.compile(r"(?P<phrase>[a-z0-9][a-z0-9 '&/.\-]{1,120}?)\s+(?P<count>\d{1,4})\s+times?\b", re.IGNORECASE),
        re.compile(r"(?P<count>\d{1,4})\s+times?\s+(?P<phrase>[a-z0-9][a-z0-9 '&/.\-]{1,120})\b", re.IGNORECASE),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            phrase = str(match.groupdict().get("phrase", "")).strip()
            count = max(1, min(2000, _coerce_int(match.groupdict().get("count"), 1)))
            resolved_song = _resolve_song_reference(phrase, normalized_songs)
            if not resolved_song:
                continue
            repeats[resolved_song] = max(repeats.get(resolved_song, 0), count)
    return repeats


def _extract_preferred_song_sequence(prompt: str, songs: list[str]) -> list[str]:
    if not prompt or not songs:
        return []
    normalized_songs = [str(song).strip() for song in songs if str(song).strip()]
    if not normalized_songs:
        return []

    clauses = re.split(r"\bthen\b|,|;|->", re.sub(r"\s+", " ", prompt), flags=re.IGNORECASE)
    preferred: list[str] = []
    seen: set[str] = set()
    for clause in clauses:
        candidate = clause.strip(" .:-")
        if not candidate:
            continue
        best_song = _resolve_song_reference(candidate, normalized_songs)
        if not best_song:
            continue
        key = best_song.lower()
        if key in seen:
            continue
        seen.add(key)
        preferred.append(best_song)
    return preferred


def _revision_prompt_requests_songset_change(prompt: str) -> bool:
    text = re.sub(r"\s+", " ", str(prompt or "").lower()).strip()
    if not text:
        return False

    structure_only_directive = bool(
        re.search(r"\b(?:transitions?|crossfades?|segments?|order|sequence|start|ending|end|intro|outro|flow)\b", text)
    )
    if structure_only_directive and re.search(r"\bof these (?:songs?|tracks?)\b", text):
        if not re.search(
            r"\b(?:add|include|insert|bring)\b.{0,25}\b(?:more|another|new|extra|different)\b.{0,20}\b(?:songs?|tracks?)\b",
            text,
        ) and not re.search(r"\b(?:remove|drop|exclude|replace|swap|change)\b.{0,30}\b(?:songs?|tracks?)\b", text):
            return False

    if re.search(
        r"\b(?:add|include|insert|bring)\b.{0,25}\b(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|another|new|more|extra)\b.{0,20}\b(?:songs?|tracks?)\b",
        text,
    ):
        return True
    if re.search(r"\b(?:add|include|insert|bring)\b.{0,120}\b(?:one is|called|named)\b", text):
        return True
    if re.search(r"\b(?:remove|drop|exclude|without)\b.{0,30}\b(?:songs?|tracks?)\b", text):
        return True
    if re.search(r"\b(?:replace|swap|change)\b.{0,30}\b(?:songs?|tracks?)\b", text):
        return True
    return False


def _parse_song_count_request(prompt: str) -> int | None:
    text = (prompt or "").lower()
    matches = re.findall(r"\b(?:total\s*)?(\d{1,4})\s+(?:songs?|tracks?)\b", text)
    if not matches:
        return None
    value = _coerce_int(matches[-1], 0)
    return value if value > 0 else None


def _extract_song_additions_from_prompt(prompt: str) -> list[str]:
    compact = re.sub(r"\s+", " ", prompt or "").strip()
    if not compact:
        return []
    match = re.search(
        r"\badd(?:\s+\w+){0,5}\s+(?:songs?|tracks?)\s*[:\-]?\s*(?P<body>.+)",
        compact,
        flags=re.IGNORECASE,
    )
    if not match:
        return []
    body = re.split(r"[.\n]", match.group("body"), maxsplit=1)[0]
    parts = [part.strip() for part in re.split(r",|;|\band\b", body, flags=re.IGNORECASE) if part.strip()]
    filtered = [part for part in parts if not _looks_like_generic_song_request(part)]
    return _normalize_song_list(filtered)


def _merge_unique_song_lists(*song_lists: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for values in song_lists:
        for raw_song in values:
            song = re.sub(r"\s+", " ", str(raw_song or "").strip()).strip(" -:;,")
            if not song or _looks_like_generic_song_request(song):
                continue
            key = song.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(song[:180])
    return merged


def _dominant_artist_hint_from_songs(songs: list[str]) -> str:
    artist_counts: dict[str, int] = {}
    for raw_song in songs:
        song = str(raw_song or "").strip()
        if " - " not in song:
            continue
        _title, artist = song.split(" - ", 1)
        artist_compact = re.sub(r"\s+", " ", artist).strip(" ,.;:-")
        if not artist_compact:
            continue
        key = artist_compact.lower()
        artist_counts[key] = artist_counts.get(key, 0) + 1
    if not artist_counts:
        return ""
    top = sorted(artist_counts.items(), key=lambda item: item[1], reverse=True)[0][0]
    return top.title()


def _prompt_requests_mirror_sequence_end(prompt: str) -> bool:
    text = re.sub(r"\s+", " ", str(prompt or "").lower()).strip()
    if not text:
        return False
    if re.search(r"\bsame order\b.{0,40}\b(?:ending|end)\b", text):
        return True
    if re.search(r"\brepeat\b.{0,40}\b(?:ending|end)\b", text):
        return True
    if re.search(r"\bat the end\b.{0,30}\bsame\b", text):
        return True
    return False


def _extract_constraint_contract(
    *,
    prompt: str,
    songs_context: list[str],
    revision_ai_intent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    compact_prompt = str(prompt or "").strip()
    normalized_songs = _normalize_song_list([str(item) for item in songs_context if str(item).strip()])
    explicit_songs = _parse_song_list_from_prompt(compact_prompt)
    added_songs = _extract_song_additions_from_prompt(compact_prompt)
    requested_songs: list[str] = _merge_unique_song_lists(explicit_songs, added_songs)

    if revision_ai_intent:
        requested_songs = _merge_unique_song_lists(
            requested_songs,
            [
                str(item)
                for item in (revision_ai_intent.get("requested_songs") if isinstance(revision_ai_intent.get("requested_songs"), list) else [])
            ],
        )

    song_pool = _merge_unique_song_lists(normalized_songs, requested_songs)
    resolved_requested: list[str] = []
    for requested in requested_songs:
        resolved = _resolve_song_reference(requested, song_pool, minimum_score=0.4)
        resolved_requested.append(resolved or requested)
    resolved_requested = _merge_unique_song_lists(resolved_requested)

    keep_existing_songs = bool(
        re.search(
            r"\b(?:keep|preserve|use)\b.{0,30}\b(?:same|existing|these)\s+(?:songs?|tracks?)\b",
            compact_prompt,
            flags=re.IGNORECASE,
        )
        or re.search(r"\bof these (?:songs?|tracks?)\b", compact_prompt, flags=re.IGNORECASE)
    )

    song_count = _parse_song_count_request(compact_prompt)
    segment_count = _extract_segment_count_request(compact_prompt)
    transition_count = _extract_transition_count_request(compact_prompt)

    repeat_requests = _extract_song_repeat_requests(compact_prompt, song_pool or resolved_requested or normalized_songs)
    preferred_sequence = _extract_preferred_song_sequence(compact_prompt, song_pool or normalized_songs)

    if revision_ai_intent:
        ai_repeat_requests = _safe_dict(revision_ai_intent.get("repeat_requests"))
        for song, raw_count in ai_repeat_requests.items():
            song_label = str(song).strip()
            if not song_label:
                continue
            resolved = _resolve_song_reference(song_label, song_pool or normalized_songs, minimum_score=0.35) or song_label
            repeat_requests[resolved] = max(repeat_requests.get(resolved, 0), _coerce_int(raw_count, 1))

        ai_preferred = (
            revision_ai_intent.get("preferred_sequence")
            if isinstance(revision_ai_intent.get("preferred_sequence"), list)
            else []
        )
        if isinstance(ai_preferred, list):
            for raw_song in ai_preferred:
                resolved = _resolve_song_reference(str(raw_song).strip(), song_pool or normalized_songs, minimum_score=0.35)
                if resolved and resolved not in preferred_sequence:
                    preferred_sequence.append(resolved)

        ai_segment_count = _coerce_int(revision_ai_intent.get("segment_count"), 0)
        if ai_segment_count > 0 and segment_count is None:
            segment_count = ai_segment_count
        ai_transition_count = _coerce_int(revision_ai_intent.get("transition_count"), 0)
        if ai_transition_count > 0 and transition_count is None:
            transition_count = ai_transition_count

    mirror_sequence_at_end = _prompt_requests_mirror_sequence_end(compact_prompt)
    if revision_ai_intent and isinstance(revision_ai_intent.get("mirror_sequence_at_end"), bool):
        mirror_sequence_at_end = bool(revision_ai_intent.get("mirror_sequence_at_end"))

    return {
        "song_count": song_count,
        "segment_count": segment_count,
        "transition_count": transition_count,
        "must_include_songs": resolved_requested,
        "repeat_requests": {
            str(song).strip(): max(1, _coerce_int(count, 1))
            for song, count in repeat_requests.items()
            if str(song).strip()
        },
        "preferred_sequence": _merge_unique_song_lists(preferred_sequence),
        "keep_existing_songs": keep_existing_songs,
        "mirror_sequence_at_end": mirror_sequence_at_end,
    }


def _merge_constraint_contract(existing: dict[str, Any] | None, updates: dict[str, Any] | None) -> dict[str, Any]:
    merged = _safe_dict(existing)
    incoming = _safe_dict(updates)
    for key in ("song_count", "segment_count", "transition_count"):
        value = _coerce_int(incoming.get(key), 0)
        if value > 0:
            merged[key] = value

    if isinstance(incoming.get("keep_existing_songs"), bool):
        merged["keep_existing_songs"] = bool(incoming.get("keep_existing_songs"))
    if isinstance(incoming.get("mirror_sequence_at_end"), bool):
        merged["mirror_sequence_at_end"] = bool(incoming.get("mirror_sequence_at_end"))

    existing_must_include = (
        [str(item) for item in merged.get("must_include_songs", []) if str(item).strip()]
        if isinstance(merged.get("must_include_songs"), list)
        else []
    )
    incoming_must_include = (
        [str(item) for item in incoming.get("must_include_songs", []) if str(item).strip()]
        if isinstance(incoming.get("must_include_songs"), list)
        else []
    )
    merged["must_include_songs"] = _merge_unique_song_lists(existing_must_include, incoming_must_include)

    existing_preferred = (
        [str(item) for item in merged.get("preferred_sequence", []) if str(item).strip()]
        if isinstance(merged.get("preferred_sequence"), list)
        else []
    )
    incoming_preferred = (
        [str(item) for item in incoming.get("preferred_sequence", []) if str(item).strip()]
        if isinstance(incoming.get("preferred_sequence"), list)
        else []
    )
    merged["preferred_sequence"] = _merge_unique_song_lists(incoming_preferred, existing_preferred)

    repeat_requests = _safe_dict(merged.get("repeat_requests"))
    for raw_song, raw_count in _safe_dict(incoming.get("repeat_requests")).items():
        song = str(raw_song).strip()
        if not song:
            continue
        count = max(1, _coerce_int(raw_count, 1))
        repeat_requests[song] = max(_coerce_int(repeat_requests.get(song), 0), count)
    merged["repeat_requests"] = repeat_requests
    merged["updated_at"] = _now_iso()
    return merged


def _apply_song_constraints(
    *,
    base_songs: list[str],
    contract: dict[str, Any],
    ai_requested_songs: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    violations: list[str] = []
    songs = _merge_unique_song_lists(base_songs)
    must_include = (
        [str(item) for item in contract.get("must_include_songs", []) if str(item).strip()]
        if isinstance(contract.get("must_include_songs"), list)
        else []
    )
    if ai_requested_songs:
        must_include = _merge_unique_song_lists(must_include, ai_requested_songs)
    songs = _merge_unique_song_lists(songs, must_include)

    preferred_sequence = (
        [str(item) for item in contract.get("preferred_sequence", []) if str(item).strip()]
        if isinstance(contract.get("preferred_sequence"), list)
        else []
    )
    if preferred_sequence:
        ordered = [song for song in preferred_sequence if song in songs]
        ordered.extend(song for song in songs if song not in ordered)
        songs = ordered

    song_count = _coerce_int(contract.get("song_count"), 0)
    if song_count > 0:
        if song_count > 300:
            violations.append(f"Requested song count {song_count} is too high. Please confirm a smaller count.")
        if len(must_include) > song_count:
            violations.append(
                f"Need exactly {song_count} songs, but {len(must_include)} songs are marked required. "
                "Please reduce required songs or increase total songs."
            )
        if len(songs) < song_count:
            violations.append(
                f"Need exactly {song_count} songs, but only {len(songs)} were resolved. Please add more songs."
            )
        elif len(songs) > song_count:
            protected = [song for song in songs if song in must_include]
            trimmed: list[str] = []
            for song in protected:
                if song not in trimmed:
                    trimmed.append(song)
            for song in songs:
                if len(trimmed) >= song_count:
                    break
                if song not in trimmed:
                    trimmed.append(song)
            if len(trimmed) > song_count:
                trimmed = trimmed[:song_count]
            songs = trimmed
            if len(songs) != song_count:
                violations.append(
                    f"Need exactly {song_count} songs, but constraints resolved to {len(songs)} songs."
                )

    missing = [song for song in must_include if song not in songs]
    if missing:
        violations.append(f"Missing required songs: {', '.join(missing[:8])}.")

    return songs, violations


def _validate_plan_contract(
    *,
    contract: dict[str, Any],
    songs: list[str],
    timeline: list[dict[str, Any]],
) -> list[str]:
    violations: list[str] = []
    song_count = _coerce_int(contract.get("song_count"), 0)
    if song_count > 0 and len(songs) != song_count:
        violations.append(f"Expected {song_count} songs, but plan has {len(songs)} songs.")

    segment_count = _coerce_int(contract.get("segment_count"), 0)
    if segment_count > 0 and len(timeline) != segment_count:
        violations.append(f"Expected {segment_count} segments, but plan has {len(timeline)} segments.")
    if segment_count > 400:
        violations.append(
            f"Requested segment count {segment_count} is very high. Confirm this count before rendering."
        )

    timeline_songs = [str(item.get("song", "")).strip() for item in timeline if str(item.get("song", "")).strip()]
    repeat_requests = _safe_dict(contract.get("repeat_requests"))
    for raw_song, raw_count in repeat_requests.items():
        song = str(raw_song).strip()
        if not song:
            continue
        required_count = max(1, _coerce_int(raw_count, 1))
        actual_count = sum(1 for item in timeline_songs if item.lower() == song.lower())
        if actual_count < required_count:
            violations.append(f"Song '{song}' requested {required_count} times but appears {actual_count} times.")

    must_include = (
        [str(item) for item in contract.get("must_include_songs", []) if str(item).strip()]
        if isinstance(contract.get("must_include_songs"), list)
        else []
    )
    missing = [song for song in must_include if song.lower() not in {item.lower() for item in songs}]
    if missing:
        violations.append(f"Missing required songs in plan: {', '.join(missing[:8])}.")

    preferred_sequence = (
        [str(item) for item in contract.get("preferred_sequence", []) if str(item).strip()]
        if isinstance(contract.get("preferred_sequence"), list)
        else []
    )
    if preferred_sequence and timeline_songs:
        sequence_len = min(len(preferred_sequence), len(timeline_songs))
        expected_start = [item.lower() for item in preferred_sequence[:sequence_len]]
        actual_start = [item.lower() for item in timeline_songs[:sequence_len]]
        if expected_start != actual_start:
            violations.append(
                "Requested opening song order is not preserved."
            )

        if bool(contract.get("mirror_sequence_at_end")) and len(timeline_songs) >= sequence_len:
            actual_end = [item.lower() for item in timeline_songs[-sequence_len:]]
            if expected_start != actual_end:
                violations.append(
                    "Requested ending song order is not preserved."
                )

    return violations


def _format_recent_context_for_prompt(recent_conversation: Any) -> str:
    if not isinstance(recent_conversation, list):
        return ""
    lines: list[str] = []
    for item in recent_conversation[-14:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower() or "user"
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        lines.append(f"{role}: {text[:300]}")
    return "\n".join(lines)


def _expand_song_candidates_to_count(
    *,
    prompt: str,
    base_songs: list[str],
    target_count: int,
) -> list[str]:
    if target_count <= 0:
        return _merge_unique_song_lists(base_songs)
    seed = _merge_unique_song_lists(base_songs)
    if len(seed) >= target_count:
        return seed

    artist_hint, _count_from_prompt = _extract_artist_and_song_count_from_prompt(prompt)
    if not artist_hint:
        artist_hint = _dominant_artist_hint_from_songs(seed)

    suggested = _suggest_songs_with_ai(prompt, artist_hint, target_count)
    return _merge_unique_song_lists(seed, suggested)


def _build_provisional_timeline(
    songs: list[str],
    target_duration_seconds: int,
    energy_curve: str,
    *,
    prompt: str = "",
    revision_ai_intent: dict[str, Any] | None = None,
    hard_segment_count: int | None = None,
) -> list[dict[str, Any]]:
    safe_songs = songs or ["Song A", "Song B", "Song C"]
    ai_intent = _safe_dict(revision_ai_intent)
    if ai_intent:
        requested_transitions_raw = _coerce_int(ai_intent.get("transition_count"), 0)
        requested_transitions = requested_transitions_raw if requested_transitions_raw > 0 else None
        requested_segments_raw = _coerce_int(ai_intent.get("segment_count"), 0)
        requested_segments = requested_segments_raw if requested_segments_raw > 0 else None
        requested_repeats = {
            str(song).strip(): max(1, min(2000, _coerce_int(count, 1)))
            for song, count in _safe_dict(ai_intent.get("repeat_requests")).items()
            if str(song).strip()
        }
        preferred_sequence = [
            str(item).strip()
            for item in (ai_intent.get("preferred_sequence") if isinstance(ai_intent.get("preferred_sequence"), list) else [])
            if str(item).strip()
        ]
        mirror_sequence_at_end = bool(ai_intent.get("mirror_sequence_at_end", False))
    else:
        requested_transitions = _extract_transition_count_request(prompt)
        requested_segments = _extract_segment_count_request(prompt)
        requested_repeats = _extract_song_repeat_requests(prompt, safe_songs)
        preferred_sequence = _extract_preferred_song_sequence(prompt, safe_songs)
        mirror_sequence_at_end = _prompt_requests_mirror_sequence_end(prompt)

    if hard_segment_count is not None and hard_segment_count > 0:
        segment_count = hard_segment_count
    elif requested_segments is not None:
        segment_count = requested_segments
    else:
        segment_count = len(safe_songs) if safe_songs else 1
        if requested_transitions is not None:
            segment_count = max(segment_count, requested_transitions + 1)
        if requested_repeats:
            segment_count = max(segment_count, max(requested_repeats.values()))
    segment_count = max(1, segment_count)
    segment_duration = max(5, int(round(max(1, target_duration_seconds) / segment_count)))

    cycle_seed = safe_songs
    if preferred_sequence:
        remaining = [song for song in safe_songs if song not in preferred_sequence]
        cycle_seed = preferred_sequence + remaining

    song_plan = [cycle_seed[index % len(cycle_seed)] for index in range(segment_count)]
    if requested_repeats:
        for repeat_song, repeat_count in requested_repeats.items():
            current_count = sum(1 for item in song_plan if item == repeat_song)
            needed = max(0, repeat_count - current_count)
            if needed <= 0:
                continue
            for slot in range(len(song_plan)):
                if needed <= 0:
                    break
                if song_plan[slot] == repeat_song:
                    continue
                song_plan[slot] = repeat_song
                needed -= 1

    if preferred_sequence:
        sequence_len = min(len(preferred_sequence), len(song_plan))
        for idx in range(sequence_len):
            song_plan[idx] = preferred_sequence[idx]
        if mirror_sequence_at_end and len(song_plan) >= sequence_len:
            end_start = len(song_plan) - sequence_len
            for idx in range(sequence_len):
                song_plan[end_start + idx] = preferred_sequence[idx]

    timeline: list[dict[str, Any]] = []
    cursor = 0
    for index in range(segment_count):
        song = song_plan[index]
        end_time = min(target_duration_seconds, cursor + segment_duration)
        timeline.append(
            {
                "segment_index": index + 1,
                "song": song,
                "start_seconds": cursor,
                "end_seconds": end_time,
                "transition_hint": "long blend" if "mellow" in energy_curve.lower() else "beat-safe blend",
            }
        )
        cursor = end_time
    if timeline:
        timeline[-1]["end_seconds"] = target_duration_seconds
    return timeline


def _build_plan_draft_payload(
    *,
    prompt: str,
    required_slots: dict[str, Any],
    adjustment_policy: str,
    revision_ai_intent: dict[str, Any] | None = None,
    memory_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        from ai import ai_main

        target_duration = ai_main._parse_requested_total_duration_seconds(prompt) or 300  # noqa: SLF001
    except Exception:
        target_duration = 300
    target_duration = max(60, min(3600, int(target_duration)))

    songs = required_slots.get("songs_set", {}).get("value", [])
    if not isinstance(songs, list):
        songs = []
    energy_curve = str(required_slots.get("energy_curve", {}).get("value", "")).strip()
    if not energy_curve and memory_context:
        energy_curve = str(memory_context.get("default_energy_curve", "")).strip()
    if not energy_curve:
        energy_curve = "Balanced flow"

    use_case = str(required_slots.get("use_case", {}).get("value", "")).strip()
    if not use_case and memory_context:
        use_case = str(memory_context.get("default_use_case", "")).strip()
    if not use_case:
        use_case = "General listening"

    resolved_songs: list[dict[str, Any]] = []
    for song in songs:
        resolved_songs.append(
            {
                "requested_song": song,
                "matched_track": song,
                "confidence": 0.85,
                "fallback_used": False,
            }
        )

    ai_intent = _safe_dict(revision_ai_intent)
    if ai_intent:
        requested_transitions_raw = _coerce_int(ai_intent.get("transition_count"), 0)
        requested_transitions = requested_transitions_raw if requested_transitions_raw > 0 else None
        hard_segment_count_raw = _coerce_int(ai_intent.get("segment_count"), 0)
        hard_segment_count = hard_segment_count_raw if hard_segment_count_raw > 0 else None
        requested_repeats = {
            str(song).strip(): max(1, min(2000, _coerce_int(count, 1)))
            for song, count in _safe_dict(ai_intent.get("repeat_requests")).items()
            if str(song).strip()
        }
    else:
        requested_transitions = _extract_transition_count_request(prompt)
        hard_segment_count = _extract_segment_count_request(prompt)
        requested_repeats = _extract_song_repeat_requests(prompt, songs)

    if memory_context and target_duration <= 0:
        target_duration = int(_coerce_int(memory_context.get("average_target_duration_seconds"), 300))
    target_duration = max(60, min(3600, int(target_duration)))
    provisional_timeline = _build_provisional_timeline(
        songs,
        target_duration,
        energy_curve,
        prompt=prompt,
        revision_ai_intent=ai_intent or None,
        hard_segment_count=hard_segment_count,
    )
    transition_strategy = "Beat-safe blended transitions"
    if memory_context:
        preferred_transition_style = str(memory_context.get("preferred_transition_style", "")).strip().lower()
        if preferred_transition_style == "energetic":
            transition_strategy = "Punchy beat-matched transitions"
        elif preferred_transition_style == "ambient":
            transition_strategy = "Long ambient transitions"
    if requested_transitions is not None:
        transition_strategy = f"{transition_strategy}; target ~{requested_transitions} transitions"

    directive_notes: list[str] = []
    if requested_transitions is not None:
        directive_notes.append(f"Requested transitions: {requested_transitions}")
    if requested_repeats:
        repeat_note = ", ".join(f"{song} x{count}" for song, count in requested_repeats.items())
        directive_notes.append(f"Requested repeats: {repeat_note}")

    proposal = {
        "title": "Guided Mix Plan Draft",
        "summary": "Plan draft ready for approval. Rendering starts only after approval.",
        "resolved_songs": resolved_songs,
        "energy_curve": energy_curve,
        "use_case": use_case,
        "target_duration_seconds": target_duration,
        "transition_strategy": transition_strategy,
        "minor_auto_adjust_allowed": adjustment_policy == "minor_auto_adjust_allowed",
        "provisional_timeline": provisional_timeline,
        "adjustment_note": (
            "Final render may apply minor beat-safe timing shifts (+/-3s) while preserving approved structure."
            if adjustment_policy == "minor_auto_adjust_allowed"
            else "Final render will preserve approved timeline boundaries."
        ),
        "directive_notes": directive_notes,
    }
    resolution_notes = {
        "fallback_song_count": 0,
        "songs": resolved_songs,
        "directive_notes": directive_notes,
    }
    return proposal, resolution_notes


def _build_execute_prompt(
    source_prompt: str,
    draft_payload: dict[str, Any],
    adjustment_policy: str,
    memory_context: dict[str, Any] | None = None,
) -> str:
    songs = draft_payload.get("resolved_songs", [])
    song_lines: list[str] = []
    if isinstance(songs, list):
        for item in songs:
            if isinstance(item, dict):
                label = str(item.get("matched_track") or item.get("requested_song") or "").strip()
                if label:
                    song_lines.append(label)
    if not song_lines:
        song_lines = _parse_song_list_from_prompt(source_prompt)

    energy_curve = str(draft_payload.get("energy_curve", "")).strip()
    use_case = str(draft_payload.get("use_case", "")).strip()
    target_duration = int(_coerce_int(draft_payload.get("target_duration_seconds"), 300))
    transition_strategy = str(draft_payload.get("transition_strategy", "Beat-safe blended transitions")).strip()

    approved_context = [
        "Approved guided planning context:",
        f"Songs: {', '.join(song_lines) if song_lines else 'Use the best matching songs from prompt'}",
        f"Energy curve: {energy_curve or 'Balanced flow'}",
        f"Use case: {use_case or 'General listening'}",
        f"Target duration: {target_duration} seconds",
        f"Transition strategy: {transition_strategy}",
    ]
    if memory_context:
        preferred_transition_style = str(memory_context.get("preferred_transition_style", "")).strip()
        preferred_resolution = str(memory_context.get("preferred_timeline_resolution", "")).strip()
        quality_average = float(_coerce_float(memory_context.get("quality_average"), 0.0))
        if preferred_transition_style:
            approved_context.append(f"User memory preferred transition style: {preferred_transition_style}.")
        if preferred_resolution:
            approved_context.append(f"User memory preferred timeline mode: {preferred_resolution}.")
        if quality_average > 0:
            approved_context.append(f"Historical quality baseline: {quality_average:.1f}/100.")
    if adjustment_policy == "minor_auto_adjust_allowed":
        approved_context.append(
            "You may apply minor beat-safe timing shifts (+/-3s) while preserving approved structure."
        )
    else:
        approved_context.append("Preserve approved structure strictly.")

    return f"{source_prompt}\n\n" + "\n".join(approved_context)


def _normalize_timeline_resolution(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"keep_attached_cuts", "replan_with_prompt", "replace_timeline"}:
        return normalized
    return "unspecified"


def _text_token_set(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", (value or "").lower()) if token}


def _text_similarity(a: str, b: str) -> float:
    a_tokens = _text_token_set(a)
    b_tokens = _text_token_set(b)
    if not a_tokens or not b_tokens:
        return 0.0
    intersection = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    if union == 0:
        return 0.0
    return float(intersection / union)


def _detect_removed_tracks(prompt: str, source_track_names: list[str]) -> list[str]:
    lowered = (prompt or "").lower()
    if not lowered.strip():
        return []
    trigger_words = ("remove", "without", "exclude", "skip", "drop")
    if not any(word in lowered for word in trigger_words):
        return []

    removed: list[str] = []
    for track in source_track_names:
        track_lower = track.lower()
        if any(f"{word} {track_lower}" in lowered for word in trigger_words):
            removed.append(track)
            continue
        similarity = _text_similarity(track_lower, lowered)
        if similarity >= 0.42 and any(word in lowered for word in trigger_words):
            removed.append(track)
    return _normalize_song_list(removed)


def _extract_timeline_attachment_intent(prompt: str, source_tracks: list[dict[str, Any]]) -> dict[str, Any]:
    source_track_names: list[str] = []
    for track in source_tracks:
        title = str(track.get("title", "")).strip()
        artist = str(track.get("artist", "")).strip()
        label = f"{title} - {artist}".strip(" -")
        if label:
            source_track_names.append(label)
    source_track_names = _normalize_song_list(source_track_names)

    requested_songs = _parse_song_list_from_prompt(prompt)
    if not requested_songs:
        add_match = re.search(
            r"\badd(?:\s+\w+){0,3}\s+songs?\s+(?P<body>.+)",
            prompt or "",
            flags=re.IGNORECASE,
        )
        if add_match:
            body = re.split(r"[.\n]", add_match.group("body"), maxsplit=1)[0]
            requested_songs = _normalize_song_list(
                [part.strip() for part in re.split(r",|;|\band\b", body, flags=re.IGNORECASE) if part.strip()]
            )
    add_tracks: list[str] = []
    for requested in requested_songs:
        best_similarity = 0.0
        for source_name in source_track_names:
            best_similarity = max(best_similarity, _text_similarity(requested, source_name))
        if best_similarity < 0.62:
            add_tracks.append(requested)

    remove_tracks = _detect_removed_tracks(prompt, source_track_names)
    cut_conflict, cut_ambiguous, cut_reasons = _detect_prompt_cut_conflict_heuristic(prompt)
    style_requests: list[str] = []
    style_hints = ("reverb", "delay", "smooth", "energetic", "mellow", "bass", "vocals", "transition")
    lowered = (prompt or "").lower()
    for token in style_hints:
        if token in lowered:
            style_requests.append(token)

    duration_request_seconds: int | None = None
    try:
        from ai import ai_main

        parsed_duration = ai_main._parse_requested_total_duration_seconds(prompt)  # noqa: SLF001
        if isinstance(parsed_duration, int) and parsed_duration > 0:
            duration_request_seconds = parsed_duration
    except Exception:
        duration_request_seconds = None

    return {
        "requests_trackset_change": bool(add_tracks or remove_tracks),
        "add_tracks": _normalize_song_list(add_tracks),
        "remove_tracks": _normalize_song_list(remove_tracks),
        "requests_cut_change": bool(cut_conflict or cut_ambiguous),
        "style_requests": _normalize_song_list(style_requests),
        "duration_request_seconds": duration_request_seconds,
        "cut_conflict": cut_conflict,
        "cut_ambiguous": cut_ambiguous,
        "cut_reasons": cut_reasons,
        "source_tracks": source_track_names,
        "requested_songs": requested_songs,
    }


def _build_combined_song_set(
    *,
    source_tracks: list[str],
    add_tracks: list[str],
    remove_tracks: list[str],
) -> list[str]:
    combined = list(source_tracks)
    filtered: list[str] = []
    for song in combined:
        should_remove = False
        for remove_item in remove_tracks:
            if _text_similarity(song, remove_item) >= 0.55:
                should_remove = True
                break
        if not should_remove:
            filtered.append(song)
    combined = filtered

    for added in add_tracks:
        if not added:
            continue
        best_similarity = max((_text_similarity(added, existing) for existing in combined), default=0.0)
        if best_similarity < 0.7:
            combined.append(added)
    return _normalize_song_list(combined)


def _build_attachment_replan_prompt(
    *,
    original_prompt: str,
    combined_songs: list[str],
    keep_soft_anchor: bool,
    memory_context: dict[str, Any] | None = None,
) -> str:
    numbered = "\n".join(f"{index + 1}. {song}" for index, song in enumerate(combined_songs))
    anchor_note = (
        "Preserve the attached timeline flow where feasible, but replan placements for better energy and blend."
        if keep_soft_anchor
        else "Build a fresh best-quality timeline."
    )
    memory_lines: list[str] = []
    if memory_context:
        preferred_transition_style = str(memory_context.get("preferred_transition_style", "")).strip()
        default_energy_curve = str(memory_context.get("default_energy_curve", "")).strip()
        default_use_case = str(memory_context.get("default_use_case", "")).strip()
        if preferred_transition_style:
            memory_lines.append(f"User memory transition style: {preferred_transition_style}.")
        if default_energy_curve:
            memory_lines.append(f"User memory energy curve: {default_energy_curve}.")
        if default_use_case:
            memory_lines.append(f"User memory use-case: {default_use_case}.")

    payload = (
        f"{original_prompt}\n\n"
        "Use this exact song set:\n"
        f"{numbered}\n\n"
        f"{anchor_note}\n"
        "If some songs are unavailable, choose best fallback matches and mention them clearly."
    )
    if memory_lines:
        payload = f"{payload}\n" + "\n".join(memory_lines)
    return payload


def _resolve_requested_song_matches(
    requested_songs: list[str],
    resolved_tracks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    resolved_names: list[str] = []
    for track in resolved_tracks:
        title = str(track.get("title", "")).strip()
        artist = str(track.get("artist", "")).strip()
        resolved_names.append(f"{title} - {artist}".strip(" -") or title or artist)

    resolution_rows: list[dict[str, Any]] = []
    fallback_count = 0
    for requested in requested_songs:
        best_name = ""
        best_confidence = 0.0
        for resolved_name in resolved_names:
            confidence = _text_similarity(requested, resolved_name)
            if confidence > best_confidence:
                best_confidence = confidence
                best_name = resolved_name
        fallback_used = best_confidence < 0.7
        if fallback_used:
            fallback_count += 1
        resolution_rows.append(
            {
                "requested_song": requested,
                "resolved_track": best_name or requested,
                "confidence": round(best_confidence, 3),
                "resolved_with_fallback": fallback_used,
                "reason": (
                    "Low-confidence direct match; used closest available candidate."
                    if fallback_used
                    else "Matched requested song."
                ),
            }
        )
    return resolution_rows, fallback_count


def _mark_planning_waiting_ai(
    *,
    run: Any,
    thread: Any,
    assistant_message: Any,
    draft_id: str,
    reason: str,
    retry_after_seconds: int = 8,
) -> None:
    retry_after_seconds = max(2, min(120, int(retry_after_seconds)))
    assistant_message.status = "completed"
    assistant_message.content_text = (
        "Audio engineer is temporarily at capacity. I paused planning and will retry shortly."
    )
    assistant_message.content_json = {
        "kind": "planning_waiting_ai",
        "draft_id": draft_id,
        "retry_after_seconds": retry_after_seconds,
        "reason": reason[:200],
        "status_label": "Retrying due to temporary AI capacity",
    }
    run.status = "completed"
    run.progress_stage = "waiting_ai"
    run.progress_percent = 20
    run.progress_label = "Retrying AI capacity"
    run.progress_detail = f"Planner unavailable: {reason[:180] or 'temporary capacity issue'}"
    run.progress_updated_at = datetime.now(timezone.utc)
    run.completed_at = datetime.now(timezone.utc)
    run.error_message = None
    thread.last_message_at = datetime.now(timezone.utc)


def process_mix_chat_run(run_id: str) -> None:
    from app import (
        GenerationJob,
        MixChatMessage,
        MixChatPlanDraft,
        MixChatRun,
        MixChatThread,
        MixChatVersion,
        MixUserMemory,
        MixSession,
        db,
    )
    from ai.mix_agent_flow import create_mix_proposal, finalize_mix_proposal

    global _APP
    if _APP is None:
        from app import create_app

        _APP = create_app()
    app = _APP
    with app.app_context():
        run = MixChatRun.query.filter_by(id=run_id).first()
        if run is None:
            LOGGER.warning("run %s missing; skipping", run_id)
            return
        if run.status in {"completed", "failed"}:
            return

        thread = MixChatThread.query.filter_by(id=run.thread_id).first()
        user_message = MixChatMessage.query.filter_by(id=run.user_message_id).first()
        assistant_message = MixChatMessage.query.filter_by(id=run.assistant_message_id).first()
        if thread is None or user_message is None or assistant_message is None:
            run.status = "failed"
            run.progress_stage = "failed"
            run.progress_percent = 100
            run.progress_label = "Failed"
            run.progress_detail = "Thread or message not found."
            run.progress_updated_at = datetime.now(timezone.utc)
            run.error_message = "Thread or message not found."
            run.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            return

        run.status = "running"
        run.progress_stage = "planning"
        run.progress_percent = 10
        run.progress_label = None
        run.progress_detail = None
        run.progress_updated_at = datetime.now(timezone.utc)
        run.started_at = datetime.now(timezone.utc)
        assistant_message.status = "running"
        thread.last_message_at = datetime.now(timezone.utc)
        db.session.commit()

        run_kind = "prompt"
        memory_enabled = False
        user_memory = None
        memory_profile: dict[str, Any] = {}
        memory_feedback: dict[str, Any] = {}
        memory_use_case_profiles: dict[str, Any] = {}
        memory_template_pack: dict[str, Any] = {}
        memory_quality: dict[str, Any] = {}

        try:
            run_kind = str(run.run_kind or "prompt").strip().lower()
            prompt = (user_message.content_text or "").strip()
            summary_payload = run.input_summary_json if isinstance(run.input_summary_json, dict) else {}

            memory_enabled = _bool_env("AI_USER_MEMORY_ENABLED", True)
            memory_context: dict[str, Any] = {}

            if memory_enabled:
                user_memory = MixUserMemory.query.filter_by(user_id=thread.user_id).first()
                if user_memory is None:
                    user_memory = MixUserMemory(
                        user_id=thread.user_id,
                        profile_json=_default_memory_profile(),
                        feedback_json=_default_memory_feedback(),
                        use_case_profiles_json={},
                        template_pack_json={"templates": {}, "global": {}, "updated_at": _now_iso()},
                        quality_json=_default_memory_quality(),
                    )
                    db.session.add(user_memory)
                    db.session.flush()

                (
                    memory_profile,
                    memory_feedback,
                    memory_use_case_profiles,
                    memory_template_pack,
                    memory_quality,
                ) = _normalize_memory_payload(user_memory)
                _update_profile_from_prompt(memory_profile, prompt)
                _record_feedback_event(
                    memory_feedback,
                    f"run_started:{run_kind}",
                    {"run_id": run.id[:8], "thread_id": thread.id[:8]},
                )
                _refresh_template_pack(
                    memory_template_pack,
                    profile=memory_profile,
                    use_case_profiles=memory_use_case_profiles,
                    feedback=memory_feedback,
                    quality=memory_quality,
                )
                memory_context = _derive_user_memory_context(
                    profile=memory_profile,
                    feedback=memory_feedback,
                    use_case_profiles=memory_use_case_profiles,
                    template_pack=memory_template_pack,
                    quality=memory_quality,
                )

            if run_kind in {"planning_intake", "planning_revision", "planning_execute"}:
                draft_id = str(summary_payload.get("draft_id", "")).strip()
                if not draft_id:
                    raise RuntimeError("Guided planning run is missing draft_id.")

                draft = MixChatPlanDraft.query.filter_by(id=draft_id, thread_id=thread.id).first()
                if draft is None:
                    raise RuntimeError("Guided plan draft was not found.")

                source_message = (
                    MixChatMessage.query.filter_by(id=draft.source_user_message_id, thread_id=thread.id).first()
                    if draft.source_user_message_id
                    else None
                )
                source_prompt = (source_message.content_text or "").strip() if source_message else prompt
                max_rounds = int(draft.max_rounds or _int_env("AI_GUIDED_MAX_ROUNDS", 5, 1, 10))
                min_rounds = _int_env("AI_GUIDED_MIN_ROUNDS", 1, 0, max_rounds)
                confidence_threshold = _float_env("AI_GUIDED_CONFIDENCE_THRESHOLD", 0.78, 0.2, 0.99)
                recent_conversation = (
                    summary_payload.get("recent_conversation")
                    if isinstance(summary_payload.get("recent_conversation"), list)
                    else []
                )
                recent_context_text = _format_recent_context_for_prompt(recent_conversation)
                existing_constraint_contract = (
                    draft.constraint_contract_json if isinstance(draft.constraint_contract_json, dict) else {}
                )

                if run_kind == "planning_intake":
                    run.progress_stage = "planning_questions"
                    current_answers = draft.answers_json if isinstance(draft.answers_json, dict) else {}
                    previous_required_slots = draft.required_slots_json if isinstance(draft.required_slots_json, dict) else None
                    try:
                        required_slots, confidence_score = _resolve_planning_state(
                            source_prompt,
                            current_answers,
                            previous_required_slots=previous_required_slots,
                            memory_context=memory_context,
                        )
                        questions = _build_planning_questions(
                            prompt=source_prompt,
                            required_slots=required_slots,
                            answers=current_answers,
                            round_count=int(draft.round_count or 0),
                            min_rounds=min_rounds,
                            previous_questions=draft.questions_json if isinstance(draft.questions_json, list) else None,
                            memory_context=memory_context,
                        )
                    except RuntimeError as exc:
                        draft.last_planner_trace_json = {
                            "phase": "planning_intake",
                            "error": str(exc)[:240],
                            "updated_at": _now_iso(),
                        }
                        _mark_planning_waiting_ai(
                            run=run,
                            thread=thread,
                            assistant_message=assistant_message,
                            draft_id=draft.id,
                            reason=str(exc),
                        )
                        db.session.commit()
                        return

                    intake_contract = _extract_constraint_contract(
                        prompt=source_prompt,
                        songs_context=[
                            str(item)
                            for item in (_safe_dict(required_slots.get("songs_set")).get("value") if isinstance(_safe_dict(required_slots.get("songs_set")).get("value"), list) else [])
                            if str(item).strip()
                        ],
                        revision_ai_intent=None,
                    )
                    merged_contract = _merge_constraint_contract(existing_constraint_contract, intake_contract)
                    draft.required_slots_json = required_slots
                    draft.questions_json = questions
                    draft.confidence_score = confidence_score
                    draft.constraint_contract_json = merged_contract
                    draft.pending_clarifications_json = []
                    draft.conversation_summary_json = {
                        "source_prompt": source_prompt[:1200],
                        "recent_turns": recent_conversation,
                        "updated_at": _now_iso(),
                    }
                    draft.status = "collecting"
                    draft.updated_at = datetime.now(timezone.utc)

                    assistant_message.status = "completed"
                    assistant_message.content_text = (
                        "Before I render, I need a few confirmations so the first mix lands exactly how you want."
                    )
                    assistant_message.content_json = {
                        "kind": "planning_questions",
                        "draft_id": draft.id,
                        "round_count": int(draft.round_count or 0),
                        "max_rounds": max_rounds,
                        "confidence_score": confidence_score,
                        "required_slots": required_slots,
                        "constraint_contract": merged_contract,
                        "questions": questions,
                        "hint": "Answer the chips below. Use Other when needed.",
                    }

                    run.status = "completed"
                    run.progress_stage = "waiting_approval"
                    run.completed_at = datetime.now(timezone.utc)
                    run.error_message = None
                    thread.last_message_at = datetime.now(timezone.utc)
                    if user_memory is not None:
                        _update_profile_from_required_slots(memory_profile, required_slots)
                        _record_feedback_event(
                            memory_feedback,
                            "planning:intake",
                            {"round": int(draft.round_count or 0), "draft_id": draft.id[:8]},
                        )
                        _refresh_template_pack(
                            memory_template_pack,
                            profile=memory_profile,
                            use_case_profiles=memory_use_case_profiles,
                            feedback=memory_feedback,
                            quality=memory_quality,
                        )
                        _persist_user_memory(
                            user_memory,
                            profile=memory_profile,
                            feedback=memory_feedback,
                            use_case_profiles=memory_use_case_profiles,
                            template_pack=memory_template_pack,
                            quality=memory_quality,
                        )
                    db.session.commit()
                    return

                if run_kind == "planning_revision":
                    current_answers = draft.answers_json if isinstance(draft.answers_json, dict) else {}
                    previous_required_slots = draft.required_slots_json if isinstance(draft.required_slots_json, dict) else None
                    incoming_answers = summary_payload.get("answers", [])
                    revision_prompt = str(summary_payload.get("revision_prompt", "")).strip()
                    effective_planning_prompt = source_prompt
                    if recent_context_text:
                        effective_planning_prompt = (
                            f"{effective_planning_prompt}\n\nRecent conversation context:\n{recent_context_text}"
                        )
                    if revision_prompt:
                        effective_planning_prompt = (
                            f"{effective_planning_prompt}\n\nPlan revision request:\n{revision_prompt}"
                        )
                    songs_answer_updated = False
                    if isinstance(incoming_answers, list):
                        valid_answers: list[dict[str, str]] = []
                        for answer in incoming_answers:
                            if not isinstance(answer, dict):
                                continue
                            normalized_answer = {
                                "question_id": str(answer.get("question_id", "")).strip()[:80],
                                "selected_option_id": str(answer.get("selected_option_id", "")).strip()[:80],
                                "other_text": str(answer.get("other_text", "")).strip()[:600],
                            }
                            valid_answers.append(normalized_answer)
                            if normalized_answer["question_id"] == "songs_set" and (
                                normalized_answer["selected_option_id"] or normalized_answer["other_text"]
                            ):
                                songs_answer_updated = True
                        if valid_answers:
                            current_answers = _merge_planning_answers(current_answers, valid_answers)
                            regenerate_only = all(
                                item.get("question_id") == "songs_set"
                                and item.get("selected_option_id") == "regenerate_suggestions"
                                and not item.get("other_text")
                                for item in valid_answers
                            )
                            if not regenerate_only:
                                draft.round_count = int(draft.round_count or 0) + 1
                    elif str(summary_payload.get("action", "")).strip().lower() == "revise_plan":
                        draft.round_count = int(draft.round_count or 0) + 1

                    draft.answers_json = current_answers
                    revision_ai_intent: dict[str, Any] | None = None
                    if revision_prompt:
                        previous_song_context, _previous_source, _previous_confidence = _extract_song_slot_snapshot(
                            previous_required_slots
                        )
                        try:
                            revision_ai_intent = _interpret_revision_prompt_with_ai(
                                source_prompt=source_prompt,
                                revision_prompt=revision_prompt,
                                current_songs=previous_song_context,
                                required_slots=previous_required_slots,
                                memory_context=memory_context,
                            )
                        except RuntimeError as exc:
                            LOGGER.warning("%s", str(exc))
                            draft.last_planner_trace_json = {
                                "phase": "planning_revision_interpret",
                                "error": str(exc)[:240],
                                "updated_at": _now_iso(),
                            }
                            _mark_planning_waiting_ai(
                                run=run,
                                thread=thread,
                                assistant_message=assistant_message,
                                draft_id=draft.id,
                                reason=str(exc),
                            )
                            db.session.commit()
                            return

                    try:
                        required_slots, confidence_score = _resolve_planning_state(
                            effective_planning_prompt,
                            current_answers,
                            previous_required_slots=previous_required_slots,
                            memory_context=memory_context,
                        )
                    except RuntimeError as exc:
                        draft.last_planner_trace_json = {
                            "phase": "planning_revision_resolve_state",
                            "error": str(exc)[:240],
                            "updated_at": _now_iso(),
                        }
                        _mark_planning_waiting_ai(
                            run=run,
                            thread=thread,
                            assistant_message=assistant_message,
                            draft_id=draft.id,
                            reason=str(exc),
                        )
                        db.session.commit()
                        return
                    songset_change_requested = False
                    requested_songs_from_ai: list[str] = []
                    if revision_prompt:
                        if revision_ai_intent is not None:
                            songset_change_requested = bool(revision_ai_intent.get("songset_change", False))
                            requested_songs_from_ai = _normalize_song_list(
                                [
                                    str(item)
                                    for item in (revision_ai_intent.get("requested_songs", []) if isinstance(revision_ai_intent.get("requested_songs"), list) else [])
                                    if str(item).strip()
                                ]
                            )
                        else:
                            songset_change_requested = _revision_prompt_requests_songset_change(revision_prompt)
                    if (
                        revision_prompt
                        and previous_required_slots
                        and not songs_answer_updated
                    ):
                        if not songset_change_requested:
                            previous_song_slot = _safe_dict(previous_required_slots.get("songs_set"))
                            previous_song_values = previous_song_slot.get("value")
                            if isinstance(previous_song_values, list):
                                preserved_songs = _normalize_song_list([str(item) for item in previous_song_values if str(item).strip()])
                                preserved_songs = [song for song in preserved_songs if not _looks_like_generic_song_request(song)]
                                if preserved_songs:
                                    required_slots["songs_set"] = {
                                        "label": "Song set",
                                        "status": "filled",
                                        "value": preserved_songs,
                                        "source": str(previous_song_slot.get("source", "previous")).strip() or "previous",
                                        "confidence": round(
                                            float(max(0.78, _coerce_float(previous_song_slot.get("confidence"), 0.0))),
                                            3,
                                        ),
                                    }
                        elif requested_songs_from_ai:
                            required_slots["songs_set"] = {
                                "label": "Song set",
                                "status": "filled",
                                "value": requested_songs_from_ai,
                                "source": "revision_ai",
                                "confidence": 0.88,
                            }
                        confidence_values = [
                            _coerce_float((required_slots.get(slot_id) or {}).get("confidence"), 0.0)
                            for slot_id in ("songs_set", "energy_curve", "use_case")
                        ]
                        confidence_score = float(round(sum(confidence_values) / max(1, len(confidence_values)), 3))

                    base_song_values = (
                        [str(item) for item in _safe_dict(required_slots.get("songs_set")).get("value", []) if str(item).strip()]
                        if isinstance(_safe_dict(required_slots.get("songs_set")).get("value"), list)
                        else []
                    )
                    contract_delta = _extract_constraint_contract(
                        prompt=revision_prompt or effective_planning_prompt,
                        songs_context=base_song_values,
                        revision_ai_intent=revision_ai_intent,
                    )
                    merged_contract = _merge_constraint_contract(existing_constraint_contract, contract_delta)
                    target_song_count = _coerce_int(merged_contract.get("song_count"), 0)
                    if target_song_count > 0 and len(base_song_values) < target_song_count:
                        try:
                            base_song_values = _expand_song_candidates_to_count(
                                prompt=effective_planning_prompt,
                                base_songs=base_song_values,
                                target_count=target_song_count,
                            )
                        except RuntimeError as exc:
                            draft.last_planner_trace_json = {
                                "phase": "planning_revision_song_expansion",
                                "error": str(exc)[:240],
                                "updated_at": _now_iso(),
                            }
                            _mark_planning_waiting_ai(
                                run=run,
                                thread=thread,
                                assistant_message=assistant_message,
                                draft_id=draft.id,
                                reason=str(exc),
                            )
                            db.session.commit()
                            return
                    constrained_songs, constraint_song_violations = _apply_song_constraints(
                        base_songs=base_song_values,
                        contract=merged_contract,
                        ai_requested_songs=requested_songs_from_ai if songset_change_requested else None,
                    )
                    if constrained_songs:
                        required_slots["songs_set"] = {
                            "label": "Song set",
                            "status": "filled",
                            "value": constrained_songs,
                            "source": "constraint_contract",
                            "confidence": round(float(max(0.86, _coerce_float(_safe_dict(required_slots.get("songs_set")).get("confidence"), 0.0))), 3),
                        }
                    elif _coerce_int(merged_contract.get("song_count"), 0) > 0:
                        required_slots["songs_set"] = {
                            "label": "Song set",
                            "status": "missing",
                            "value": [],
                            "source": "constraint_contract",
                            "confidence": 0.0,
                        }

                    is_slots_complete = all(
                        str((required_slots.get(slot_id) or {}).get("status", "missing")) == "filled"
                        for slot_id in ("songs_set", "energy_curve", "use_case")
                    )
                    ready_for_draft = (
                        draft.round_count >= min_rounds
                        and is_slots_complete
                        and confidence_score >= confidence_threshold
                    )
                    reached_round_cap = draft.round_count >= max_rounds

                    draft.required_slots_json = required_slots
                    draft.confidence_score = confidence_score
                    draft.constraint_contract_json = merged_contract
                    draft.conversation_summary_json = {
                        "source_prompt": source_prompt[:1200],
                        "latest_user_turn": revision_prompt[:900] if revision_prompt else "",
                        "recent_turns": recent_conversation,
                        "updated_at": _now_iso(),
                    }
                    draft.updated_at = datetime.now(timezone.utc)

                    if ready_for_draft or reached_round_cap:
                        revision_intent_for_payload = _safe_dict(revision_ai_intent)
                        contract_segment_count = _coerce_int(merged_contract.get("segment_count"), 0)
                        contract_transition_count = _coerce_int(merged_contract.get("transition_count"), 0)
                        if contract_segment_count > 0:
                            revision_intent_for_payload["segment_count"] = contract_segment_count
                        if contract_transition_count > 0:
                            revision_intent_for_payload["transition_count"] = contract_transition_count
                        if _safe_dict(merged_contract.get("repeat_requests")):
                            revision_intent_for_payload["repeat_requests"] = _safe_dict(
                                merged_contract.get("repeat_requests")
                            )
                        if isinstance(merged_contract.get("preferred_sequence"), list):
                            revision_intent_for_payload["preferred_sequence"] = [
                                str(item)
                                for item in merged_contract.get("preferred_sequence", [])
                                if str(item).strip()
                            ]
                        if isinstance(merged_contract.get("mirror_sequence_at_end"), bool):
                            revision_intent_for_payload["mirror_sequence_at_end"] = bool(
                                merged_contract.get("mirror_sequence_at_end")
                            )

                        proposal_payload, resolution_notes = _build_plan_draft_payload(
                            prompt=effective_planning_prompt,
                            required_slots=required_slots,
                            adjustment_policy=str(draft.adjustment_policy or "minor_auto_adjust_allowed"),
                            revision_ai_intent=revision_intent_for_payload or None,
                            memory_context=memory_context,
                        )
                        plan_resolved_songs = []
                        for entry in (
                            proposal_payload.get("resolved_songs", [])
                            if isinstance(proposal_payload.get("resolved_songs"), list)
                            else []
                        ):
                            if not isinstance(entry, dict):
                                continue
                            label = str(entry.get("matched_track") or entry.get("requested_song") or "").strip()
                            if label:
                                plan_resolved_songs.append(label)
                        plan_timeline = (
                            proposal_payload.get("provisional_timeline", [])
                            if isinstance(proposal_payload.get("provisional_timeline"), list)
                            else []
                        )
                        contract_violations = list(constraint_song_violations)
                        contract_violations.extend(
                            _validate_plan_contract(
                                contract=merged_contract,
                                songs=_merge_unique_song_lists(plan_resolved_songs),
                                timeline=plan_timeline,
                            )
                        )

                        if contract_violations:
                            draft.proposal_json = proposal_payload
                            draft.resolution_notes_json = resolution_notes
                            draft.questions_json = []
                            draft.pending_clarifications_json = contract_violations
                            draft.status = "collecting"
                            draft.last_planner_trace_json = {
                                "phase": "planning_revision_contract_validation",
                                "violations": contract_violations[:12],
                                "updated_at": _now_iso(),
                            }

                            assistant_message.status = "completed"
                            assistant_message.content_text = (
                                "I need one clarification to satisfy your exact constraints before finalizing the draft."
                            )
                            assistant_message.content_json = {
                                "kind": "planning_constraint_clarification",
                                "draft_id": draft.id,
                                "round_count": int(draft.round_count or 0),
                                "constraint_contract": merged_contract,
                                "violations": contract_violations[:12],
                                "required_slots": required_slots,
                                "proposal_preview": proposal_payload,
                            }

                            run.status = "completed"
                            run.progress_stage = "planning_questions"
                            run.completed_at = datetime.now(timezone.utc)
                            run.error_message = None
                            thread.last_message_at = datetime.now(timezone.utc)
                            db.session.commit()
                            return

                        draft.proposal_json = proposal_payload
                        draft.resolution_notes_json = resolution_notes
                        draft.questions_json = []
                        draft.pending_clarifications_json = []
                        draft.status = "draft_ready"

                        assistant_message.status = "completed"
                        assistant_message.content_text = (
                            "Plan draft is ready. Review songs, energy curve, and provisional timeline, then approve to render."
                        )
                        assistant_message.content_json = {
                            "kind": "planning_draft_ready",
                            "draft_id": draft.id,
                            "round_count": int(draft.round_count or 0),
                            "max_rounds": max_rounds,
                            "confidence_score": confidence_score,
                            "required_slots": required_slots,
                            "constraint_contract": merged_contract,
                            "proposal": proposal_payload,
                            "resolution_notes": resolution_notes,
                        }

                        run.status = "completed"
                        run.progress_stage = "planning_draft_ready"
                        run.completed_at = datetime.now(timezone.utc)
                        run.error_message = None
                        thread.last_message_at = datetime.now(timezone.utc)
                        if user_memory is not None:
                            _update_profile_from_required_slots(memory_profile, required_slots)
                            _record_feedback_event(
                                memory_feedback,
                                "planning:draft_ready",
                                {"round": int(draft.round_count or 0), "draft_id": draft.id[:8]},
                            )
                            _refresh_template_pack(
                                memory_template_pack,
                                profile=memory_profile,
                                use_case_profiles=memory_use_case_profiles,
                                feedback=memory_feedback,
                                quality=memory_quality,
                            )
                            _persist_user_memory(
                                user_memory,
                                profile=memory_profile,
                                feedback=memory_feedback,
                                use_case_profiles=memory_use_case_profiles,
                                template_pack=memory_template_pack,
                                quality=memory_quality,
                            )
                        db.session.commit()
                        return

                    if constraint_song_violations:
                        draft.questions_json = []
                        draft.status = "collecting"
                        draft.pending_clarifications_json = constraint_song_violations
                        assistant_message.status = "completed"
                        assistant_message.content_text = (
                            "Please confirm these constraints so I can continue with an accurate plan."
                        )
                        assistant_message.content_json = {
                            "kind": "planning_constraint_clarification",
                            "draft_id": draft.id,
                            "constraint_contract": merged_contract,
                            "violations": constraint_song_violations[:12],
                            "required_slots": required_slots,
                        }
                        run.status = "completed"
                        run.progress_stage = "planning_questions"
                        run.completed_at = datetime.now(timezone.utc)
                        run.error_message = None
                        thread.last_message_at = datetime.now(timezone.utc)
                        db.session.commit()
                        return

                    try:
                        questions = _build_planning_questions(
                            prompt=effective_planning_prompt,
                            required_slots=required_slots,
                            answers=current_answers,
                            round_count=int(draft.round_count or 0),
                            min_rounds=min_rounds,
                            previous_questions=draft.questions_json if isinstance(draft.questions_json, list) else None,
                            memory_context=memory_context,
                        )
                    except RuntimeError as exc:
                        draft.last_planner_trace_json = {
                            "phase": "planning_revision_questions",
                            "error": str(exc)[:240],
                            "updated_at": _now_iso(),
                        }
                        _mark_planning_waiting_ai(
                            run=run,
                            thread=thread,
                            assistant_message=assistant_message,
                            draft_id=draft.id,
                            reason=str(exc),
                        )
                        db.session.commit()
                        return
                    draft.questions_json = questions
                    draft.status = "collecting"
                    draft.pending_clarifications_json = []

                    assistant_message.status = "completed"
                    assistant_message.content_text = "Noted. I need a little more detail before I can lock the final plan."
                    assistant_message.content_json = {
                        "kind": "planning_revision_questions",
                        "draft_id": draft.id,
                        "round_count": int(draft.round_count or 0),
                        "max_rounds": max_rounds,
                        "confidence_score": confidence_score,
                        "required_slots": required_slots,
                        "constraint_contract": merged_contract,
                        "questions": questions,
                    }

                    run.status = "completed"
                    run.progress_stage = "planning_questions"
                    run.completed_at = datetime.now(timezone.utc)
                    run.error_message = None
                    thread.last_message_at = datetime.now(timezone.utc)
                    if user_memory is not None:
                        _update_profile_from_required_slots(memory_profile, required_slots)
                        _record_feedback_event(
                            memory_feedback,
                            "planning:revision",
                            {"round": int(draft.round_count or 0), "draft_id": draft.id[:8]},
                        )
                        memory_feedback["planning_revisions"] = int(_coerce_int(memory_feedback.get("planning_revisions"), 0) + 1)
                        _refresh_template_pack(
                            memory_template_pack,
                            profile=memory_profile,
                            use_case_profiles=memory_use_case_profiles,
                            feedback=memory_feedback,
                            quality=memory_quality,
                        )
                        _persist_user_memory(
                            user_memory,
                            profile=memory_profile,
                            feedback=memory_feedback,
                            use_case_profiles=memory_use_case_profiles,
                            template_pack=memory_template_pack,
                            quality=memory_quality,
                        )
                    db.session.commit()
                    return

                if run_kind == "planning_execute":
                    if draft.status not in {"approved", "draft_ready"}:
                        raise RuntimeError("Plan draft is not approved for execution.")

                    existing_contract = (
                        draft.constraint_contract_json if isinstance(draft.constraint_contract_json, dict) else {}
                    )
                    pending_clarifications = (
                        [str(item) for item in draft.pending_clarifications_json if str(item).strip()]
                        if isinstance(draft.pending_clarifications_json, list)
                        else []
                    )
                    if pending_clarifications:
                        draft.status = "collecting"
                        draft.approved_at = None
                        draft.updated_at = datetime.now(timezone.utc)
                        assistant_message.status = "completed"
                        assistant_message.content_text = (
                            "Please resolve these remaining constraints before rendering."
                        )
                        assistant_message.content_json = {
                            "kind": "planning_constraint_clarification",
                            "draft_id": draft.id,
                            "constraint_contract": existing_contract,
                            "violations": pending_clarifications[:20],
                            "required_slots": draft.required_slots_json if isinstance(draft.required_slots_json, dict) else {},
                        }
                        run.status = "completed"
                        run.progress_stage = "planning_questions"
                        run.completed_at = datetime.now(timezone.utc)
                        run.error_message = None
                        thread.last_message_at = datetime.now(timezone.utc)
                        db.session.commit()
                        return

                    draft_payload = draft.proposal_json if isinstance(draft.proposal_json, dict) else {}
                    if not draft_payload:
                        previous_required_slots = (
                            draft.required_slots_json if isinstance(draft.required_slots_json, dict) else None
                        )
                        try:
                            required_slots, confidence_score = _resolve_planning_state(
                                source_prompt,
                                draft.answers_json if isinstance(draft.answers_json, dict) else {},
                                previous_required_slots=previous_required_slots,
                                memory_context=memory_context,
                            )
                        except RuntimeError as exc:
                            draft.last_planner_trace_json = {
                                "phase": "planning_execute_resolve_state",
                                "error": str(exc)[:240],
                                "updated_at": _now_iso(),
                            }
                            _mark_planning_waiting_ai(
                                run=run,
                                thread=thread,
                                assistant_message=assistant_message,
                                draft_id=draft.id,
                                reason=str(exc),
                            )
                            db.session.commit()
                            return

                        execute_contract = _merge_constraint_contract(
                            existing_contract,
                            _extract_constraint_contract(
                                prompt=source_prompt,
                                songs_context=[
                                    str(item)
                                    for item in (
                                        _safe_dict(required_slots.get("songs_set")).get("value")
                                        if isinstance(_safe_dict(required_slots.get("songs_set")).get("value"), list)
                                        else []
                                    )
                                    if str(item).strip()
                                ],
                                revision_ai_intent=None,
                            ),
                        )
                        execute_song_count = _coerce_int(execute_contract.get("song_count"), 0)
                        base_execute_songs = (
                            [str(item) for item in _safe_dict(required_slots.get("songs_set")).get("value", []) if str(item).strip()]
                            if isinstance(_safe_dict(required_slots.get("songs_set")).get("value"), list)
                            else []
                        )
                        if execute_song_count > 0 and len(base_execute_songs) < execute_song_count:
                            try:
                                base_execute_songs = _expand_song_candidates_to_count(
                                    prompt=source_prompt,
                                    base_songs=base_execute_songs,
                                    target_count=execute_song_count,
                                )
                            except RuntimeError as exc:
                                draft.last_planner_trace_json = {
                                    "phase": "planning_execute_song_expansion",
                                    "error": str(exc)[:240],
                                    "updated_at": _now_iso(),
                                }
                                _mark_planning_waiting_ai(
                                    run=run,
                                    thread=thread,
                                    assistant_message=assistant_message,
                                    draft_id=draft.id,
                                    reason=str(exc),
                                )
                                db.session.commit()
                                return

                        constrained_execute_songs, execute_song_violations = _apply_song_constraints(
                            base_songs=base_execute_songs,
                            contract=execute_contract,
                            ai_requested_songs=None,
                        )
                        required_slots["songs_set"] = {
                            "label": "Song set",
                            "status": "filled" if constrained_execute_songs else "missing",
                            "value": constrained_execute_songs,
                            "source": "constraint_contract",
                            "confidence": round(
                                float(max(0.86, _coerce_float(_safe_dict(required_slots.get("songs_set")).get("confidence"), 0.0))),
                                3,
                            ),
                        }
                        if execute_song_violations:
                            draft.status = "collecting"
                            draft.approved_at = None
                            draft.pending_clarifications_json = execute_song_violations
                            draft.constraint_contract_json = execute_contract
                            draft.required_slots_json = required_slots
                            draft.updated_at = datetime.now(timezone.utc)
                            assistant_message.status = "completed"
                            assistant_message.content_text = (
                                "I need one clarification before rendering so constraints stay exact."
                            )
                            assistant_message.content_json = {
                                "kind": "planning_constraint_clarification",
                                "draft_id": draft.id,
                                "constraint_contract": execute_contract,
                                "violations": execute_song_violations[:20],
                                "required_slots": required_slots,
                            }
                            run.status = "completed"
                            run.progress_stage = "planning_questions"
                            run.completed_at = datetime.now(timezone.utc)
                            run.error_message = None
                            thread.last_message_at = datetime.now(timezone.utc)
                            db.session.commit()
                            return

                        execute_intent: dict[str, Any] = {}
                        execute_segment_count = _coerce_int(execute_contract.get("segment_count"), 0)
                        execute_transition_count = _coerce_int(execute_contract.get("transition_count"), 0)
                        if execute_segment_count > 0:
                            execute_intent["segment_count"] = execute_segment_count
                        if execute_transition_count > 0:
                            execute_intent["transition_count"] = execute_transition_count
                        if _safe_dict(execute_contract.get("repeat_requests")):
                            execute_intent["repeat_requests"] = _safe_dict(execute_contract.get("repeat_requests"))
                        if isinstance(execute_contract.get("preferred_sequence"), list):
                            execute_intent["preferred_sequence"] = [
                                str(item)
                                for item in execute_contract.get("preferred_sequence", [])
                                if str(item).strip()
                            ]
                        if isinstance(execute_contract.get("mirror_sequence_at_end"), bool):
                            execute_intent["mirror_sequence_at_end"] = bool(
                                execute_contract.get("mirror_sequence_at_end")
                            )

                        draft_payload, resolution_notes = _build_plan_draft_payload(
                            prompt=source_prompt,
                            required_slots=required_slots,
                            adjustment_policy=str(draft.adjustment_policy or "minor_auto_adjust_allowed"),
                            revision_ai_intent=execute_intent or None,
                            memory_context=memory_context,
                        )
                        payload_songs = []
                        for entry in (
                            draft_payload.get("resolved_songs", [])
                            if isinstance(draft_payload.get("resolved_songs"), list)
                            else []
                        ):
                            if not isinstance(entry, dict):
                                continue
                            label = str(entry.get("matched_track") or entry.get("requested_song") or "").strip()
                            if label:
                                payload_songs.append(label)
                        payload_timeline = (
                            draft_payload.get("provisional_timeline", [])
                            if isinstance(draft_payload.get("provisional_timeline"), list)
                            else []
                        )
                        execute_contract_violations = _validate_plan_contract(
                            contract=execute_contract,
                            songs=_merge_unique_song_lists(payload_songs),
                            timeline=payload_timeline,
                        )
                        if execute_contract_violations:
                            draft.status = "collecting"
                            draft.approved_at = None
                            draft.pending_clarifications_json = execute_contract_violations
                            draft.constraint_contract_json = execute_contract
                            draft.proposal_json = draft_payload
                            draft.resolution_notes_json = resolution_notes
                            draft.required_slots_json = required_slots
                            draft.updated_at = datetime.now(timezone.utc)
                            assistant_message.status = "completed"
                            assistant_message.content_text = (
                                "I need one clarification before rendering so constraints stay exact."
                            )
                            assistant_message.content_json = {
                                "kind": "planning_constraint_clarification",
                                "draft_id": draft.id,
                                "constraint_contract": execute_contract,
                                "violations": execute_contract_violations[:20],
                                "required_slots": required_slots,
                                "proposal_preview": draft_payload,
                            }
                            run.status = "completed"
                            run.progress_stage = "planning_questions"
                            run.completed_at = datetime.now(timezone.utc)
                            run.error_message = None
                            thread.last_message_at = datetime.now(timezone.utc)
                            db.session.commit()
                            return

                        draft.proposal_json = draft_payload
                        draft.required_slots_json = required_slots
                        draft.resolution_notes_json = resolution_notes
                        draft.confidence_score = confidence_score
                        draft.constraint_contract_json = execute_contract
                        draft.pending_clarifications_json = []
                    else:
                        effective_contract = (
                            draft.constraint_contract_json if isinstance(draft.constraint_contract_json, dict) else {}
                        )
                        payload_songs = []
                        for entry in (
                            draft_payload.get("resolved_songs", [])
                            if isinstance(draft_payload.get("resolved_songs"), list)
                            else []
                        ):
                            if not isinstance(entry, dict):
                                continue
                            label = str(entry.get("matched_track") or entry.get("requested_song") or "").strip()
                            if label:
                                payload_songs.append(label)
                        payload_timeline = (
                            draft_payload.get("provisional_timeline", [])
                            if isinstance(draft_payload.get("provisional_timeline"), list)
                            else []
                        )
                        payload_contract_violations = _validate_plan_contract(
                            contract=effective_contract,
                            songs=_merge_unique_song_lists(payload_songs),
                            timeline=payload_timeline,
                        )
                        if payload_contract_violations:
                            draft.status = "collecting"
                            draft.approved_at = None
                            draft.pending_clarifications_json = payload_contract_violations
                            draft.updated_at = datetime.now(timezone.utc)
                            assistant_message.status = "completed"
                            assistant_message.content_text = (
                                "Please confirm these constraints before rendering."
                            )
                            assistant_message.content_json = {
                                "kind": "planning_constraint_clarification",
                                "draft_id": draft.id,
                                "constraint_contract": effective_contract,
                                "violations": payload_contract_violations[:20],
                                "required_slots": draft.required_slots_json if isinstance(draft.required_slots_json, dict) else {},
                                "proposal_preview": draft_payload,
                            }
                            run.status = "completed"
                            run.progress_stage = "planning_questions"
                            run.completed_at = datetime.now(timezone.utc)
                            run.error_message = None
                            thread.last_message_at = datetime.now(timezone.utc)
                            db.session.commit()
                            return

                    draft.status = "approved"
                    if draft.approved_at is None:
                        draft.approved_at = datetime.now(timezone.utc)
                    draft.updated_at = datetime.now(timezone.utc)
                    run.progress_stage = "downloading"
                    db.session.commit()

                    effective_prompt = _build_execute_prompt(
                        source_prompt=source_prompt,
                        draft_payload=draft_payload,
                        adjustment_policy=str(draft.adjustment_policy or "minor_auto_adjust_allowed"),
                        memory_context=memory_context,
                    )

                    mix_session = MixSession(
                        user_id=thread.user_id,
                        prompt=effective_prompt,
                        status="planning",
                    )
                    db.session.add(mix_session)
                    db.session.commit()

                    workspace = _create_workspace(app.config["STORAGE_ROOT"], mix_session.id)
                    proposal_payload = create_mix_proposal(effective_prompt, session_dir=str(workspace))

                    tracks: list[dict[str, Any]] = []
                    for raw_track in proposal_payload.get("tracks", []):
                        if not isinstance(raw_track, dict):
                            continue
                        track = dict(raw_track)
                        preview_filename = str(track.get("preview_filename", "")).strip()
                        if preview_filename:
                            track["preview_url"] = _relative_file_url(mix_session.id, Path(preview_filename).name)
                        tracks.append(track)
                    proposal_payload["tracks"] = tracks

                    mix_session.planner_requirements = proposal_payload.get("requirements", {})
                    mix_session.downloaded_tracks = tracks
                    mix_session.engineer_proposal = proposal_payload.get("proposal", {})
                    mix_session.client_questions = []
                    mix_session.follow_up_questions = []
                    mix_session.status = "awaiting_client"
                    mix_session.updated_at = datetime.now(timezone.utc)
                    db.session.commit()

                    run.progress_stage = "rendering"
                    db.session.commit()

                    outputs = finalize_mix_proposal(
                        session_dir=str(workspace),
                        proposal=proposal_payload.get("proposal", {}),
                    )
                    mp3_filename = Path(outputs["mp3_path"]).name
                    wav_filename = Path(outputs["wav_path"]).name
                    mp3_url = _relative_file_url(mix_session.id, mp3_filename)
                    wav_url = _relative_file_url(mix_session.id, wav_filename)

                    generation_job = GenerationJob(
                        user_id=thread.user_id,
                        generation_type="ai_parody",
                        status="success",
                        input_payload={
                            "prompt": source_prompt,
                            "mode": "guided_plan_execute",
                            "run_id": run.id,
                            "draft_id": draft.id,
                        },
                        output_url=mp3_url,
                        created_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                    )
                    db.session.add(generation_job)
                    db.session.commit()

                    final_output = {
                        "mp3_url": mp3_url,
                        "wav_url": wav_url,
                        "job_id": generation_job.id,
                    }
                    mix_session.final_output = final_output
                    mix_session.status = "completed"
                    mix_session.completed_at = datetime.now(timezone.utc)
                    mix_session.updated_at = datetime.now(timezone.utc)
                    db.session.commit()

                    proposal = proposal_payload.get("proposal", {}) if isinstance(proposal_payload, dict) else {}
                    snapshot = {
                        "summary": str(proposal_payload.get("requirements", {}).get("summary", "")),
                        "mixing_rationale": str(proposal.get("mixing_rationale", "")),
                        "target_duration_seconds": proposal_payload.get("requirements", {}).get(
                            "target_duration_seconds"
                        ),
                        "segments_count": len(proposal.get("segments", []))
                        if isinstance(proposal.get("segments"), list)
                        else 0,
                        "auto_render": True,
                        "guided_planning": True,
                        "plan_draft_id": draft.id,
                        "minor_adjustments_allowed": str(draft.adjustment_policy or "") == "minor_auto_adjust_allowed",
                    }

                    version = MixChatVersion(
                        thread_id=thread.id,
                        source_user_message_id=user_message.id,
                        assistant_message_id=assistant_message.id,
                        parent_version_id=run.parent_version_id,
                        mix_session_id=mix_session.id,
                        proposal_json=proposal_payload,
                        final_output_json=final_output,
                        state_snapshot_json=snapshot,
                    )
                    db.session.add(version)
                    db.session.commit()

                    draft.status = "executed"
                    draft.executed_run_id = run.id
                    draft.executed_version_id = version.id
                    draft.updated_at = datetime.now(timezone.utc)

                    run.version_id = version.id
                    run.status = "completed"
                    run.progress_stage = "completed"
                    run.completed_at = datetime.now(timezone.utc)
                    run.error_message = None

                    assistant_message.status = "completed"
                    assistant_message.content_text = (
                        str(proposal.get("mixing_rationale", "")).strip()
                        or "Approved plan rendered successfully."
                    )
                    assistant_message.content_json = {
                        "kind": "mix_proposal",
                        "thread_id": thread.id,
                        "version_id": version.id,
                        "mix_session_id": mix_session.id,
                        "requirements": proposal_payload.get("requirements", {}),
                        "tracks": tracks,
                        "proposal": proposal,
                        "client_questions": [],
                        "final_output": final_output,
                        "auto_rendered": True,
                        "guided_planning": {
                            "draft_id": draft.id,
                            "executed": True,
                            "minor_adjustments_allowed": str(draft.adjustment_policy or "")
                            == "minor_auto_adjust_allowed",
                        },
                    }
                    thread.last_message_at = datetime.now(timezone.utc)
                    if user_memory is not None:
                        required_slots = draft.required_slots_json if isinstance(draft.required_slots_json, dict) else {}
                        _update_profile_from_required_slots(memory_profile, required_slots)
                        _update_profile_from_proposal_payload(memory_profile, proposal_payload)
                        memory_feedback["planning_approvals"] = int(_coerce_int(memory_feedback.get("planning_approvals"), 0) + 1)
                        _record_feedback_event(
                            memory_feedback,
                            "planning:execute",
                            {"draft_id": draft.id[:8], "version_id": version.id[:8]},
                        )
                        use_case_value = str(_safe_dict(required_slots.get("use_case")).get("value", "")).strip()
                        energy_value = str(_safe_dict(required_slots.get("energy_curve")).get("value", "")).strip()
                        target_duration = int(
                            _coerce_int(_safe_dict(proposal_payload.get("requirements")).get("target_duration_seconds"), 0)
                        )
                        quality_payload = _compute_mix_quality_score(
                            proposal_payload=proposal_payload,
                            run_kind="planning_execute",
                            timeline_resolution=None,
                        )
                        _append_quality_stats(memory_quality, quality_payload)
                        _update_use_case_profiles(
                            memory_use_case_profiles,
                            use_case=use_case_value,
                            energy_curve=energy_value,
                            target_duration_seconds=target_duration,
                            quality_score=float(_coerce_float(quality_payload.get("score"), 0.0)),
                        )
                        snapshot["quality"] = quality_payload
                        assistant_message.content_json["quality"] = quality_payload
                        _refresh_template_pack(
                            memory_template_pack,
                            profile=memory_profile,
                            use_case_profiles=memory_use_case_profiles,
                            feedback=memory_feedback,
                            quality=memory_quality,
                        )
                        _persist_user_memory(
                            user_memory,
                            profile=memory_profile,
                            feedback=memory_feedback,
                            use_case_profiles=memory_use_case_profiles,
                            template_pack=memory_template_pack,
                            quality=memory_quality,
                        )
                    db.session.commit()
                    return

            if run_kind == "timeline_attachment":
                if not run.parent_version_id:
                    raise RuntimeError("Timeline attachment run requires a source version.")

                parent_version = MixChatVersion.query.filter_by(id=run.parent_version_id, thread_id=thread.id).first()
                if parent_version is None:
                    raise RuntimeError("Source version for timeline attachment is missing.")
                if not parent_version.mix_session_id:
                    raise RuntimeError("Source version has no workspace for rendering.")

                summary_payload = run.input_summary_json if isinstance(run.input_summary_json, dict) else {}
                raw_attachments = summary_payload.get("attachments", [])
                if not isinstance(raw_attachments, list) or not raw_attachments:
                    raise RuntimeError("Timeline attachment payload is missing.")
                attachment = raw_attachments[0] if isinstance(raw_attachments[0], dict) else {}
                raw_segments = attachment.get("segments")
                timeline_resolution = _normalize_timeline_resolution(summary_payload.get("timeline_resolution"))

                parent_payload = parent_version.proposal_json if isinstance(parent_version.proposal_json, dict) else {}
                parent_proposal = parent_payload.get("proposal", {})
                if not isinstance(parent_proposal, dict):
                    raise RuntimeError("Source proposal is invalid.")
                source_tracks = _normalize_tracks_with_preview(parent_payload.get("tracks", []), parent_version.mix_session_id)

                workspace = _create_workspace(app.config["STORAGE_ROOT"], parent_version.mix_session_id)
                segments = _sanitize_timeline_segments(workspace, raw_segments)

                always_ask_first = _bool_env("AI_TIMELINE_ALWAYS_ASK_FIRST", True)
                intent = _extract_timeline_attachment_intent(prompt, source_tracks)
                trackset_change_detected = bool(intent.get("requests_trackset_change"))
                cut_change_detected = bool(intent.get("requests_cut_change"))

                detected_conflicts: list[str] = list(intent.get("cut_reasons", [])) if isinstance(
                    intent.get("cut_reasons"), list
                ) else []
                add_tracks = intent.get("add_tracks", [])
                if isinstance(add_tracks, list) and add_tracks:
                    detected_conflicts.append(f"Prompt requests adding tracks: {', '.join(add_tracks[:4])}.")
                remove_tracks = intent.get("remove_tracks", [])
                if isinstance(remove_tracks, list) and remove_tracks:
                    detected_conflicts.append(f"Prompt requests removing tracks: {', '.join(remove_tracks[:4])}.")

                if prompt and bool(intent.get("cut_ambiguous")) and not bool(intent.get("cut_conflict")):
                    llm_conflict, llm_reason = _classify_timeline_conflict_with_llm(prompt, detected_conflicts)
                    if llm_conflict:
                        cut_change_detected = True
                    if llm_reason:
                        detected_conflicts.append(llm_reason)

                conflict_detected = (
                    always_ask_first
                    and timeline_resolution == "unspecified"
                    and (trackset_change_detected or cut_change_detected)
                )
                LOGGER.info(
                    "timeline attachment run decision: run_id=%s source_version=%s resolution=%s conflict=%s "
                    "trackset_change=%s cut_change=%s add_tracks=%s remove_tracks=%s",
                    run.id,
                    parent_version.id,
                    timeline_resolution,
                    conflict_detected,
                    trackset_change_detected,
                    cut_change_detected,
                    len(add_tracks) if isinstance(add_tracks, list) else 0,
                    len(remove_tracks) if isinstance(remove_tracks, list) else 0,
                )

                if conflict_detected:
                    run.status = "completed"
                    run.progress_stage = "waiting_approval"
                    run.completed_at = datetime.now(timezone.utc)
                    run.error_message = None

                    assistant_message.status = "completed"
                    assistant_message.content_text = (
                        "Your prompt requests structural timeline changes. "
                        "Choose how IntelliMix should proceed."
                    )
                    assistant_message.content_json = {
                        "kind": "clarification_question",
                        "thread_id": thread.id,
                        "source_version_id": parent_version.id,
                        "detected_conflicts": detected_conflicts[:5],
                        "next_step_hint": "Reply with: keep attached cuts OR replace with new cuts.",
                        "timeline_snapshot": {
                            "type": "timeline_snapshot",
                            "source_version_id": parent_version.id,
                            "segments": segments,
                            "editor_metadata": attachment.get("editor_metadata", {}),
                        },
                        "tracks": source_tracks,
                        "quick_actions": [
                            {
                                "id": "keep_attached_cuts",
                                "label": "Keep attached cuts",
                                "description": "Preserve attached timeline boundaries and apply style tweaks only.",
                            },
                            {
                                "id": "replan_with_prompt",
                                "label": "Replan with prompt",
                                "description": "Merge prompt intent with attachment context and rebuild timeline.",
                            },
                            {
                                "id": "replace_timeline",
                                "label": "Replace timeline",
                                "description": "Ignore attached cuts and create a fresh timeline from prompt.",
                            },
                        ],
                        "trackset_change_detected": trackset_change_detected,
                        "intent": {
                            "add_tracks": add_tracks if isinstance(add_tracks, list) else [],
                            "remove_tracks": remove_tracks if isinstance(remove_tracks, list) else [],
                            "requests_cut_change": cut_change_detected,
                            "duration_request_seconds": intent.get("duration_request_seconds"),
                        },
                        "timeline_resolution_required": True,
                        "next_step_hint": (
                            "Pick one quick action, optionally edit the prompt, then send."
                        ),
                    }
                    thread.last_message_at = datetime.now(timezone.utc)
                    if user_memory is not None:
                        memory_feedback["clarification_questions"] = int(
                            _coerce_int(memory_feedback.get("clarification_questions"), 0) + 1
                        )
                        _record_feedback_event(
                            memory_feedback,
                            "timeline_attachment:clarification",
                            {
                                "source_version_id": parent_version.id[:8],
                                "trackset_change": trackset_change_detected,
                                "cut_change": cut_change_detected,
                            },
                        )
                        _persist_user_memory(
                            user_memory,
                            profile=memory_profile,
                            feedback=memory_feedback,
                            use_case_profiles=memory_use_case_profiles,
                            template_pack=memory_template_pack,
                            quality=memory_quality,
                        )
                    db.session.commit()
                    return

                if timeline_resolution in {"replace_timeline", "replan_with_prompt"} and not prompt.strip():
                    timeline_resolution = "keep_attached_cuts"

                def _finalize_new_mix_from_prompt(execution_prompt: str, mode_label: str) -> tuple[MixSession, dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
                    mix_session = MixSession(
                        user_id=thread.user_id,
                        prompt=execution_prompt,
                        status="planning",
                    )
                    db.session.add(mix_session)
                    db.session.commit()

                    new_workspace = _create_workspace(app.config["STORAGE_ROOT"], mix_session.id)
                    run.progress_stage = "downloading"
                    db.session.commit()

                    proposal_payload = create_mix_proposal(execution_prompt, session_dir=str(new_workspace))
                    tracks_payload: list[dict[str, Any]] = []
                    for raw_track in proposal_payload.get("tracks", []):
                        if not isinstance(raw_track, dict):
                            continue
                        track = dict(raw_track)
                        preview_filename = str(track.get("preview_filename", "")).strip()
                        if preview_filename:
                            track["preview_url"] = _relative_file_url(mix_session.id, Path(preview_filename).name)
                        tracks_payload.append(track)
                    proposal_payload["tracks"] = tracks_payload

                    mix_session.planner_requirements = proposal_payload.get("requirements", {})
                    mix_session.downloaded_tracks = tracks_payload
                    mix_session.engineer_proposal = proposal_payload.get("proposal", {})
                    mix_session.client_questions = []
                    mix_session.follow_up_questions = []
                    mix_session.status = "awaiting_client"
                    mix_session.updated_at = datetime.now(timezone.utc)
                    db.session.commit()

                    run.progress_stage = "rendering"
                    db.session.commit()

                    outputs = finalize_mix_proposal(
                        session_dir=str(new_workspace),
                        proposal=proposal_payload.get("proposal", {}),
                    )
                    mp3_filename = Path(outputs["mp3_path"]).name
                    wav_filename = Path(outputs["wav_path"]).name
                    mp3_url = _relative_file_url(mix_session.id, mp3_filename)
                    wav_url = _relative_file_url(mix_session.id, wav_filename)

                    generation_job = GenerationJob(
                        user_id=thread.user_id,
                        generation_type="ai_parody",
                        status="success",
                        input_payload={
                            "prompt": execution_prompt,
                            "mode": mode_label,
                            "run_id": run.id,
                            "source_version_id": parent_version.id,
                        },
                        output_url=mp3_url,
                        created_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                    )
                    db.session.add(generation_job)
                    db.session.commit()

                    final_output = {
                        "mp3_url": mp3_url,
                        "wav_url": wav_url,
                        "job_id": generation_job.id,
                    }
                    mix_session.final_output = final_output
                    mix_session.status = "completed"
                    mix_session.completed_at = datetime.now(timezone.utc)
                    mix_session.updated_at = datetime.now(timezone.utc)
                    db.session.commit()
                    return mix_session, proposal_payload, tracks_payload, final_output

                applied_refinements: list[str] = []
                song_resolution_rows: list[dict[str, Any]] = []
                fallback_song_count = 0

                if timeline_resolution == "replace_timeline":
                    execution_prompt = prompt.strip()
                    mix_session, proposal_payload, tracks, final_output = _finalize_new_mix_from_prompt(
                        execution_prompt,
                        mode_label="mix_chat_timeline_replace",
                    )
                    proposal = proposal_payload.get("proposal", {}) if isinstance(proposal_payload, dict) else {}
                    requested_for_resolution = intent.get("requested_songs", [])
                    if not isinstance(requested_for_resolution, list):
                        requested_for_resolution = []
                    song_resolution_rows, fallback_song_count = _resolve_requested_song_matches(
                        requested_for_resolution,
                        tracks,
                    )
                elif timeline_resolution == "replan_with_prompt":
                    base_tracks = intent.get("source_tracks", [])
                    if not isinstance(base_tracks, list):
                        base_tracks = []
                    add_tracks_value = intent.get("add_tracks", [])
                    if not isinstance(add_tracks_value, list):
                        add_tracks_value = []
                    remove_tracks_value = intent.get("remove_tracks", [])
                    if not isinstance(remove_tracks_value, list):
                        remove_tracks_value = []

                    combined_song_set = _build_combined_song_set(
                        source_tracks=base_tracks,
                        add_tracks=add_tracks_value,
                        remove_tracks=remove_tracks_value,
                    )
                    if not combined_song_set:
                        combined_song_set = _normalize_song_list(base_tracks)

                    execution_prompt = _build_attachment_replan_prompt(
                        original_prompt=prompt,
                        combined_songs=combined_song_set,
                        keep_soft_anchor=True,
                        memory_context=memory_context,
                    )
                    duration_request = intent.get("duration_request_seconds")
                    if isinstance(duration_request, int) and duration_request > 0:
                        execution_prompt += f"\nTarget duration: {duration_request} seconds."

                    mix_session, proposal_payload, tracks, final_output = _finalize_new_mix_from_prompt(
                        execution_prompt,
                        mode_label="mix_chat_timeline_replan",
                    )
                    proposal = proposal_payload.get("proposal", {}) if isinstance(proposal_payload, dict) else {}
                    requested_for_resolution = add_tracks_value or intent.get("requested_songs", []) or combined_song_set
                    if not isinstance(requested_for_resolution, list):
                        requested_for_resolution = []
                    song_resolution_rows, fallback_song_count = _resolve_requested_song_matches(
                        requested_for_resolution,
                        tracks,
                    )
                else:
                    proposal = dict(parent_proposal)
                    proposal["segments"] = segments
                    proposal, applied_refinements = _apply_non_cut_prompt_refinements(proposal, prompt)

                    proposal_payload = dict(parent_payload)
                    proposal_payload["proposal"] = proposal
                    tracks = _normalize_tracks_with_preview(
                        proposal_payload.get("tracks", []),
                        parent_version.mix_session_id,
                    )
                    proposal_payload["tracks"] = tracks

                    run.progress_stage = "rendering"
                    db.session.commit()

                    outputs = finalize_mix_proposal(session_dir=str(workspace), proposal=proposal)
                    mp3_filename = Path(outputs["mp3_path"]).name
                    wav_filename = Path(outputs["wav_path"]).name
                    mp3_url = _relative_file_url(parent_version.mix_session_id, mp3_filename)
                    wav_url = _relative_file_url(parent_version.mix_session_id, wav_filename)

                    generation_job = GenerationJob(
                        user_id=thread.user_id,
                        generation_type="ai_parody",
                        status="success",
                        input_payload={
                            "prompt": prompt,
                            "mode": "mix_chat_timeline_attachment",
                            "run_id": run.id,
                            "source_version_id": parent_version.id,
                            "timeline_resolution": timeline_resolution,
                        },
                        output_url=mp3_url,
                        created_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                    )
                    db.session.add(generation_job)
                    db.session.commit()

                    final_output = {
                        "mp3_url": mp3_url,
                        "wav_url": wav_url,
                        "job_id": generation_job.id,
                    }
                    mix_session = MixSession.query.filter_by(id=parent_version.mix_session_id).first()

                current_mix_session_id = mix_session.id if mix_session else parent_version.mix_session_id
                previous_snapshot = parent_version.state_snapshot_json if isinstance(parent_version.state_snapshot_json, dict) else {}
                proposal_segments = proposal.get("segments", []) if isinstance(proposal, dict) else []
                snapshot = {
                    "summary": str(previous_snapshot.get("summary", "")),
                    "mixing_rationale": str(proposal.get("mixing_rationale", "")) if isinstance(proposal, dict) else "",
                    "target_duration_seconds": previous_snapshot.get("target_duration_seconds"),
                    "segments_count": len(proposal_segments) if isinstance(proposal_segments, list) else 0,
                    "auto_render": True,
                    "source_version_id": parent_version.id,
                    "run_kind": "timeline_attachment",
                    "applied_refinements": applied_refinements,
                    "timeline_resolution": timeline_resolution,
                    "trackset_change_detected": trackset_change_detected,
                    "fallback_song_count": fallback_song_count,
                }

                version = MixChatVersion(
                    thread_id=thread.id,
                    source_user_message_id=user_message.id,
                    assistant_message_id=assistant_message.id,
                    parent_version_id=parent_version.id,
                    mix_session_id=current_mix_session_id,
                    proposal_json=proposal_payload,
                    final_output_json=final_output,
                    state_snapshot_json=snapshot,
                )
                db.session.add(version)
                db.session.commit()

                run.version_id = version.id
                run.status = "completed"
                run.progress_stage = "completed"
                run.completed_at = datetime.now(timezone.utc)
                run.error_message = None

                assistant_message.status = "completed"
                assistant_message.content_text = (
                    str(proposal.get("mixing_rationale", "")).strip()
                    or f"Attached timeline processed successfully with resolution '{timeline_resolution}'."
                )
                assistant_message.content_json = {
                    "kind": "timeline_attachment_result",
                    "thread_id": thread.id,
                    "version_id": version.id,
                    "mix_session_id": current_mix_session_id,
                    "source_version_id": parent_version.id,
                    "tracks": tracks,
                    "proposal": proposal,
                    "final_output": final_output,
                    "applied_refinements": applied_refinements,
                    "timeline_resolution": timeline_resolution,
                    "trackset_change_detected": trackset_change_detected,
                    "song_resolution": song_resolution_rows,
                    "fallback_song_count": fallback_song_count,
                    "timeline_snapshot": {
                        "type": "timeline_snapshot",
                        "source_version_id": parent_version.id,
                        "segments": segments,
                        "editor_metadata": attachment.get("editor_metadata", {}),
                    },
                }
                thread.last_message_at = datetime.now(timezone.utc)
                if user_memory is not None:
                    _update_profile_from_proposal_payload(memory_profile, proposal_payload)
                    _record_feedback_event(
                        memory_feedback,
                        "timeline_attachment:completed",
                        {
                            "resolution": timeline_resolution,
                            "version_id": version.id[:8],
                            "source_version_id": parent_version.id[:8],
                        },
                    )
                    memory_feedback["timeline_attachment_runs"] = int(
                        _coerce_int(memory_feedback.get("timeline_attachment_runs"), 0) + 1
                    )
                    resolution_counts = _safe_dict(memory_feedback.get("timeline_resolution_counts"))
                    resolution_counts[timeline_resolution] = int(_coerce_int(resolution_counts.get(timeline_resolution), 0) + 1)
                    memory_feedback["timeline_resolution_counts"] = resolution_counts
                    quality_payload = _compute_mix_quality_score(
                        proposal_payload=proposal_payload,
                        run_kind="timeline_attachment",
                        timeline_resolution=timeline_resolution,
                    )
                    _append_quality_stats(memory_quality, quality_payload)
                    snapshot["quality"] = quality_payload
                    assistant_message.content_json["quality"] = quality_payload
                    _refresh_template_pack(
                        memory_template_pack,
                        profile=memory_profile,
                        use_case_profiles=memory_use_case_profiles,
                        feedback=memory_feedback,
                        quality=memory_quality,
                    )
                    _persist_user_memory(
                        user_memory,
                        profile=memory_profile,
                        feedback=memory_feedback,
                        use_case_profiles=memory_use_case_profiles,
                        template_pack=memory_template_pack,
                        quality=memory_quality,
                    )
                db.session.commit()
                return

            if run_kind == "timeline_edit":
                if not run.parent_version_id:
                    raise RuntimeError("Timeline edit run requires a parent version.")

                parent_version = MixChatVersion.query.filter_by(id=run.parent_version_id, thread_id=thread.id).first()
                if parent_version is None:
                    raise RuntimeError("Parent version for timeline edit run is missing.")
                if not parent_version.mix_session_id:
                    raise RuntimeError("Parent version has no source workspace for rendering.")

                summary_payload = run.input_summary_json if isinstance(run.input_summary_json, dict) else {}
                raw_segments = summary_payload.get("segments")

                parent_payload = parent_version.proposal_json if isinstance(parent_version.proposal_json, dict) else {}
                parent_proposal = parent_payload.get("proposal", {})
                if not isinstance(parent_proposal, dict):
                    raise RuntimeError("Parent proposal is invalid.")

                workspace = _create_workspace(app.config["STORAGE_ROOT"], parent_version.mix_session_id)
                run.progress_stage = "rendering"
                db.session.commit()

                segments = _sanitize_timeline_segments(workspace, raw_segments)
                proposal = dict(parent_proposal)
                proposal["segments"] = segments

                proposal_payload = dict(parent_payload)
                proposal_payload["proposal"] = proposal

                tracks: list[dict[str, Any]] = []
                for raw_track in proposal_payload.get("tracks", []):
                    if not isinstance(raw_track, dict):
                        continue
                    track = dict(raw_track)
                    preview_filename = str(track.get("preview_filename", "")).strip()
                    if preview_filename and not track.get("preview_url"):
                        track["preview_url"] = _relative_file_url(parent_version.mix_session_id, Path(preview_filename).name)
                    tracks.append(track)
                proposal_payload["tracks"] = tracks

                outputs = finalize_mix_proposal(session_dir=str(workspace), proposal=proposal)
                mp3_filename = Path(outputs["mp3_path"]).name
                wav_filename = Path(outputs["wav_path"]).name
                mp3_url = _relative_file_url(parent_version.mix_session_id, mp3_filename)
                wav_url = _relative_file_url(parent_version.mix_session_id, wav_filename)

                generation_job = GenerationJob(
                    user_id=thread.user_id,
                    generation_type="ai_parody",
                    status="success",
                    input_payload={
                        "prompt": prompt,
                        "mode": "mix_chat_timeline_edit",
                        "run_id": run.id,
                        "source_version_id": parent_version.id,
                    },
                    output_url=mp3_url,
                    created_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                )
                db.session.add(generation_job)
                db.session.commit()

                final_output = {
                    "mp3_url": mp3_url,
                    "wav_url": wav_url,
                    "job_id": generation_job.id,
                }

                previous_snapshot = parent_version.state_snapshot_json if isinstance(parent_version.state_snapshot_json, dict) else {}
                snapshot = {
                    "summary": str(previous_snapshot.get("summary", "")),
                    "mixing_rationale": str(proposal.get("mixing_rationale", "")),
                    "target_duration_seconds": previous_snapshot.get("target_duration_seconds"),
                    "segments_count": len(segments),
                    "auto_render": True,
                    "source_version_id": parent_version.id,
                    "run_kind": "timeline_edit",
                }

                version = MixChatVersion(
                    thread_id=thread.id,
                    source_user_message_id=user_message.id,
                    assistant_message_id=assistant_message.id,
                    parent_version_id=parent_version.id,
                    mix_session_id=parent_version.mix_session_id,
                    proposal_json=proposal_payload,
                    final_output_json=final_output,
                    state_snapshot_json=snapshot,
                )
                db.session.add(version)
                db.session.commit()

                run.version_id = version.id
                run.status = "completed"
                run.progress_stage = "completed"
                run.completed_at = datetime.now(timezone.utc)
                run.error_message = None

                note = str(summary_payload.get("note", "")).strip()
                assistant_message.status = "completed"
                assistant_message.content_text = (
                    f"Timeline edits applied successfully with {len(segments)} segments."
                    + (f" Note: {note[:320]}" if note else "")
                )
                assistant_message.content_json = {
                    "kind": "timeline_edit_result",
                    "thread_id": thread.id,
                    "version_id": version.id,
                    "mix_session_id": parent_version.mix_session_id,
                    "source_version_id": parent_version.id,
                    "tracks": tracks,
                    "proposal": proposal,
                    "final_output": final_output,
                    "editor_metadata": summary_payload.get("editor_metadata", {}),
                }
                thread.last_message_at = datetime.now(timezone.utc)
                if user_memory is not None:
                    _update_profile_from_proposal_payload(memory_profile, proposal_payload)
                    _record_feedback_event(
                        memory_feedback,
                        "timeline_edit:completed",
                        {"version_id": version.id[:8], "source_version_id": parent_version.id[:8]},
                    )
                    memory_feedback["timeline_edits"] = int(_coerce_int(memory_feedback.get("timeline_edits"), 0) + 1)
                    quality_payload = _compute_mix_quality_score(
                        proposal_payload=proposal_payload,
                        run_kind="timeline_edit",
                        timeline_resolution=None,
                    )
                    _append_quality_stats(memory_quality, quality_payload)
                    snapshot["quality"] = quality_payload
                    assistant_message.content_json["quality"] = quality_payload
                    _refresh_template_pack(
                        memory_template_pack,
                        profile=memory_profile,
                        use_case_profiles=memory_use_case_profiles,
                        feedback=memory_feedback,
                        quality=memory_quality,
                    )
                    _persist_user_memory(
                        user_memory,
                        profile=memory_profile,
                        feedback=memory_feedback,
                        use_case_profiles=memory_use_case_profiles,
                        template_pack=memory_template_pack,
                        quality=memory_quality,
                    )
                db.session.commit()
                return

            effective_prompt = prompt
            if run.mode != "restart_fresh" and run.parent_version_id:
                parent_version = MixChatVersion.query.filter_by(id=run.parent_version_id).first()
                if parent_version and isinstance(parent_version.state_snapshot_json, dict):
                    prior = parent_version.state_snapshot_json
                    prior_summary = str(prior.get("summary", "")).strip()
                    prior_notes = str(prior.get("mixing_rationale", "")).strip()
                    if prior_summary or prior_notes:
                        effective_prompt = (
                            f"{prompt}\n\n"
                            "Refine this based on previous approved version.\n"
                            f"Previous summary: {prior_summary}\n"
                            f"Previous rationale: {prior_notes}\n"
                        )
            if memory_context and _bool_env("AI_MEMORY_PROMPT_CONTEXT_ENABLED", True):
                memory_lines: list[str] = []
                preferred_artists = memory_context.get("preferred_artists", [])
                preferred_songs = memory_context.get("preferred_songs", [])
                default_energy = str(memory_context.get("default_energy_curve", "")).strip()
                default_use_case = str(memory_context.get("default_use_case", "")).strip()
                preferred_transition_style = str(memory_context.get("preferred_transition_style", "")).strip()
                if isinstance(preferred_artists, list) and preferred_artists:
                    memory_lines.append(f"User memory preferred artists: {', '.join(str(item) for item in preferred_artists[:5])}.")
                if isinstance(preferred_songs, list) and preferred_songs:
                    memory_lines.append(f"User memory preferred songs: {', '.join(str(item) for item in preferred_songs[:6])}.")
                if default_energy:
                    memory_lines.append(f"User memory default energy: {default_energy}.")
                if default_use_case:
                    memory_lines.append(f"User memory default use-case: {default_use_case}.")
                if preferred_transition_style:
                    memory_lines.append(f"User memory transition style: {preferred_transition_style}.")
                if memory_lines:
                    effective_prompt = f"{effective_prompt}\n\nMemory context:\n" + "\n".join(memory_lines)

            mix_session = MixSession(
                user_id=thread.user_id,
                prompt=prompt,
                status="planning",
            )
            db.session.add(mix_session)
            db.session.commit()

            workspace = _create_workspace(app.config["STORAGE_ROOT"], mix_session.id)

            run.progress_stage = "downloading"
            db.session.commit()
            proposal_payload = create_mix_proposal(effective_prompt, session_dir=str(workspace))

            tracks: list[dict[str, Any]] = []
            for raw_track in proposal_payload.get("tracks", []):
                if not isinstance(raw_track, dict):
                    continue
                track = dict(raw_track)
                preview_filename = str(track.get("preview_filename", "")).strip()
                if preview_filename:
                    track["preview_url"] = _relative_file_url(mix_session.id, Path(preview_filename).name)
                tracks.append(track)
            proposal_payload["tracks"] = tracks

            mix_session.planner_requirements = proposal_payload.get("requirements", {})
            mix_session.downloaded_tracks = tracks
            mix_session.engineer_proposal = proposal_payload.get("proposal", {})
            mix_session.client_questions = proposal_payload.get("client_questions", [])
            mix_session.status = "awaiting_client"
            mix_session.updated_at = datetime.now(timezone.utc)
            db.session.commit()

            run.progress_stage = "draft_ready"
            db.session.commit()

            final_output: dict[str, Any] = {}
            auto_render = _bool_env("MIX_CHAT_AUTO_RENDER_DEFAULT", True)
            if auto_render:
                run.progress_stage = "rendering"
                db.session.commit()
                outputs = finalize_mix_proposal(
                    session_dir=str(workspace),
                    proposal=proposal_payload.get("proposal", {}),
                )

                mp3_filename = Path(outputs["mp3_path"]).name
                wav_filename = Path(outputs["wav_path"]).name
                mp3_url = _relative_file_url(mix_session.id, mp3_filename)
                wav_url = _relative_file_url(mix_session.id, wav_filename)

                generation_job = GenerationJob(
                    user_id=thread.user_id,
                    generation_type="ai_parody",
                    status="success",
                    input_payload={"prompt": prompt, "mode": "mix_chat_auto_render", "run_id": run.id},
                    output_url=mp3_url,
                    created_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                )
                db.session.add(generation_job)
                db.session.commit()

                final_output = {
                    "mp3_url": mp3_url,
                    "wav_url": wav_url,
                    "job_id": generation_job.id,
                }
                mix_session.final_output = final_output
                mix_session.status = "completed"
                mix_session.completed_at = datetime.now(timezone.utc)
                mix_session.updated_at = datetime.now(timezone.utc)
                db.session.commit()

            proposal = proposal_payload.get("proposal", {}) if isinstance(proposal_payload, dict) else {}
            snapshot = {
                "summary": str(proposal_payload.get("requirements", {}).get("summary", "")),
                "mixing_rationale": str(proposal.get("mixing_rationale", "")),
                "target_duration_seconds": proposal_payload.get("requirements", {}).get("target_duration_seconds"),
                "segments_count": len(proposal.get("segments", [])) if isinstance(proposal.get("segments"), list) else 0,
                "auto_render": auto_render,
            }

            version = MixChatVersion(
                thread_id=thread.id,
                source_user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                parent_version_id=run.parent_version_id,
                mix_session_id=mix_session.id,
                proposal_json=proposal_payload,
                final_output_json=final_output,
                state_snapshot_json=snapshot,
            )
            db.session.add(version)
            db.session.commit()

            run.version_id = version.id
            run.status = "completed"
            run.progress_stage = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.error_message = None

            assistant_message.status = "completed"
            assistant_message.content_text = (
                str(proposal.get("mixing_rationale", "")).strip()
                or "Mix draft created successfully."
            )
            assistant_message.content_json = {
                "kind": "mix_proposal",
                "thread_id": thread.id,
                "version_id": version.id,
                "mix_session_id": mix_session.id,
                "requirements": proposal_payload.get("requirements", {}),
                "tracks": tracks,
                "proposal": proposal,
                "client_questions": proposal_payload.get("client_questions", []),
                "final_output": final_output,
                "auto_rendered": auto_render,
            }
            thread.last_message_at = datetime.now(timezone.utc)
            if user_memory is not None:
                _update_profile_from_proposal_payload(memory_profile, proposal_payload)
                _record_feedback_event(
                    memory_feedback,
                    f"prompt:{'auto_render' if auto_render else 'draft_only'}",
                    {"version_id": version.id[:8], "run_id": run.id[:8]},
                )
                use_case_value = _normalize_use_case_label(_infer_use_case_from_prompt(prompt) or "")
                energy_value = str(_infer_energy_from_prompt(prompt) or "").strip()
                target_duration = int(
                    _coerce_int(_safe_dict(proposal_payload.get("requirements")).get("target_duration_seconds"), 0)
                )
                quality_payload = _compute_mix_quality_score(
                    proposal_payload=proposal_payload,
                    run_kind="prompt",
                    timeline_resolution=None,
                )
                _append_quality_stats(memory_quality, quality_payload)
                if use_case_value:
                    _update_use_case_profiles(
                        memory_use_case_profiles,
                        use_case=use_case_value,
                        energy_curve=energy_value,
                        target_duration_seconds=target_duration,
                        quality_score=float(_coerce_float(quality_payload.get("score"), 0.0)),
                    )
                snapshot["quality"] = quality_payload
                assistant_message.content_json["quality"] = quality_payload
                _refresh_template_pack(
                    memory_template_pack,
                    profile=memory_profile,
                    use_case_profiles=memory_use_case_profiles,
                    feedback=memory_feedback,
                    quality=memory_quality,
                )
                _persist_user_memory(
                    user_memory,
                    profile=memory_profile,
                    feedback=memory_feedback,
                    use_case_profiles=memory_use_case_profiles,
                    template_pack=memory_template_pack,
                    quality=memory_quality,
                )
            db.session.commit()
        except Exception as exc:
            LOGGER.exception("mix chat run %s failed", run.id)
            run.status = "failed"
            run.progress_stage = "failed"
            run.progress_percent = 100
            run.progress_label = "Failed"
            run.progress_detail = str(exc)[:500] or "Run failed before completion."
            run.progress_updated_at = datetime.now(timezone.utc)
            run.error_message = str(exc)[:2000]
            run.completed_at = datetime.now(timezone.utc)
            assistant_message.status = "failed"
            assistant_message.content_text = f"Mix generation failed: {str(exc)[:500]}"
            assistant_message.content_json = {
                "kind": "error",
                "error": str(exc)[:1200],
            }
            thread.last_message_at = datetime.now(timezone.utc)
            if memory_enabled and user_memory is not None:
                _record_feedback_event(
                    memory_feedback,
                    f"run_failed:{run_kind}",
                    {"run_id": run.id[:8], "error": str(exc)[:180]},
                )
                _persist_user_memory(
                    user_memory,
                    profile=memory_profile,
                    feedback=memory_feedback,
                    use_case_profiles=memory_use_case_profiles,
                    template_pack=memory_template_pack,
                    quality=memory_quality,
                )
            db.session.commit()

