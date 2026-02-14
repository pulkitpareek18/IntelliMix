from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from ai import ai_main
from ai.ai import AIServiceError, generate_with_instruction
from features.audio_engineer_tools import analyze_track_beats, merge_segments, render_segment_with_effects
from pydub import AudioSegment

LOGGER = logging.getLogger(__name__)


PLANNER_AGENT_SYSTEM_INSTRUCTION = """
You are Requirements Agent for an AI music production suite.

Return strict JSON only:
{
  "summary": "Short summary",
  "target_duration_seconds": 300,
  "transition_style": "smooth|energetic|cinematic|ambient",
  "priority": "vocals|beats|balanced",
  "effects": {
    "reverb_amount": 0.2,
    "delay_ms": 180,
    "delay_feedback": 0.25
  },
  "client_questions": [
    {
      "id": "energy_curve",
      "question": "Choose energy flow",
      "options": ["Linear (Recommended)", "Slow build", "Peaks and valleys"]
    }
  ],
  "notes": "Optional note"
}

Rules:
- Keep target_duration_seconds in [60, 3600].
- Keep reverb_amount in [0, 1].
- Keep delay_ms in [0, 1200].
- Keep delay_feedback in [0, 0.95].
- Provide 1 to 3 client_questions with 2 to 4 options each.
"""


ENGINEER_AGENT_SYSTEM_INSTRUCTION = """
You are Audio Engineer Agent.

Input includes:
- prompt
- production requirements
- downloaded tracks with analysis metadata (duration, bpm, key)
- draft timeline segments

Return strict JSON only:
{
  "proposal_title": "Short title",
  "mixing_rationale": "How transitions/effects are chosen",
  "segment_notes": [
    {
      "segment_index": 0,
      "note": "Why this cut works"
    }
  ],
  "questions_for_client": []
}

Rules:
- Do not change numeric cut timestamps.
- Explain intent and quality rationale.
- Keep concise and practical.
"""


def _extract_json(raw_text: str) -> dict[str, Any]:
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _default_requirements(prompt: str) -> dict[str, Any]:
    target_duration_seconds = ai_main._parse_requested_total_duration_seconds(prompt) or 240
    long_transition = ai_main._has_long_transition_intent(prompt)
    return {
        "summary": "DSP-first creative mixing plan with editable transitions.",
        "target_duration_seconds": target_duration_seconds,
        "transition_style": "ambient" if long_transition else "smooth",
        "priority": "balanced",
        "effects": {
            "reverb_amount": 0.25 if long_transition else 0.15,
            "delay_ms": 200 if long_transition else 140,
            "delay_feedback": 0.22 if long_transition else 0.16,
        },
        "client_questions": [
            {
                "id": "energy_curve",
                "question": "How should the energy evolve?",
                "options": ["Balanced flow (Recommended)", "Slow build", "High energy throughout"],
            },
            {
                "id": "vocal_clarity",
                "question": "How vocal-forward should transitions be?",
                "options": ["Balanced (Recommended)", "Vocals prominent", "Beat-led transitions"],
            },
        ],
        "notes": "",
    }


def _plan_requirements(prompt: str) -> dict[str, Any]:
    fallback = _default_requirements(prompt)
    try:
        raw_output = generate_with_instruction(prompt=prompt, system_instruction=PLANNER_AGENT_SYSTEM_INSTRUCTION)
    except AIServiceError as exc:
        LOGGER.warning("Planner agent unavailable (%s). Using fallback requirements.", exc.error_code)
        return fallback
    except Exception:
        LOGGER.warning("Planner agent failed unexpectedly. Using fallback requirements.")
        return fallback

    parsed = _extract_json(raw_output)
    if not parsed:
        return fallback

    effects = parsed.get("effects", {})
    if not isinstance(effects, dict):
        effects = {}

    questions = parsed.get("client_questions", [])
    if not isinstance(questions, list):
        questions = []

    target_duration_seconds = ai_main._coerce_int(parsed.get("target_duration_seconds"), fallback["target_duration_seconds"])
    target_duration_seconds = int(ai_main._clamp(float(target_duration_seconds), 60.0, 3600.0))

    requirements = {
        "summary": str(parsed.get("summary", fallback["summary"]))[:500],
        "target_duration_seconds": target_duration_seconds,
        "transition_style": str(parsed.get("transition_style", fallback["transition_style"]))[:80],
        "priority": str(parsed.get("priority", fallback["priority"]))[:80],
        "effects": {
            "reverb_amount": float(ai_main._clamp(ai_main._coerce_float(effects.get("reverb_amount"), fallback["effects"]["reverb_amount"]), 0.0, 1.0)),
            "delay_ms": int(ai_main._clamp(float(ai_main._coerce_int(effects.get("delay_ms"), fallback["effects"]["delay_ms"])), 0.0, 1200.0)),
            "delay_feedback": float(ai_main._clamp(ai_main._coerce_float(effects.get("delay_feedback"), fallback["effects"]["delay_feedback"]), 0.0, 0.95)),
        },
        "client_questions": [],
        "notes": str(parsed.get("notes", ""))[:600],
    }

    normalized_questions: list[dict[str, Any]] = []
    for raw_question in questions[:3]:
        if not isinstance(raw_question, dict):
            continue
        question_id = str(raw_question.get("id", "")).strip()
        question_text = str(raw_question.get("question", "")).strip()
        raw_options = raw_question.get("options", [])
        if not question_id or not question_text or not isinstance(raw_options, list):
            continue
        options = [str(option).strip() for option in raw_options if str(option).strip()]
        if len(options) < 2:
            continue
        normalized_questions.append(
            {
                "id": question_id[:64],
                "question": question_text[:220],
                "options": options[:4],
            }
        )
    requirements["client_questions"] = normalized_questions or fallback["client_questions"]
    return requirements


def _crossfade_seconds_for_sequence(mix_plan: ai_main._MixIntentPlan, sequence_length: int) -> list[float]:
    transition_count = max(0, sequence_length - 1)
    if transition_count == 0:
        return []
    if mix_plan.transition_crossfade_seconds:
        values = mix_plan.transition_crossfade_seconds[:transition_count]
        if len(values) < transition_count:
            values.extend([values[-1]] * (transition_count - len(values)))
        return [float(ai_main._clamp(value, 0.0, 8.0)) for value in values]
    if mix_plan.global_crossfade_seconds is not None:
        value = float(ai_main._clamp(mix_plan.global_crossfade_seconds, 0.0, 8.0))
        return [value for _ in range(transition_count)]
    return [1.8 for _ in range(transition_count)]


def _default_engineer_text(prompt: str, segments: list[dict[str, Any]]) -> dict[str, Any]:
    notes = []
    for index in range(min(len(segments), 8)):
        notes.append({"segment_index": index, "note": "Beat-aligned section transition for flow continuity."})
    return {
        "proposal_title": "AI Audio Engineer Proposal",
        "mixing_rationale": f"Created a DSP-first mix plan from prompt: {prompt[:180]}",
        "segment_notes": notes,
        "questions_for_client": [],
    }


def _engineer_explain_proposal(
    prompt: str,
    requirements: dict[str, Any],
    tracks: list[dict[str, Any]],
    segments: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {
        "prompt": prompt,
        "requirements": requirements,
        "tracks": tracks,
        "segments": segments[:24],
    }
    try:
        raw_output = generate_with_instruction(
            prompt=json.dumps(payload, ensure_ascii=True),
            system_instruction=ENGINEER_AGENT_SYSTEM_INSTRUCTION,
        )
    except Exception:
        return _default_engineer_text(prompt, segments)
    parsed = _extract_json(raw_output)
    if not parsed:
        return _default_engineer_text(prompt, segments)

    proposal_title = str(parsed.get("proposal_title", "AI Audio Engineer Proposal")).strip()[:140]
    rationale = str(parsed.get("mixing_rationale", "")).strip()[:1200]
    raw_segment_notes = parsed.get("segment_notes", [])
    raw_questions = parsed.get("questions_for_client", [])

    segment_notes: list[dict[str, Any]] = []
    if isinstance(raw_segment_notes, list):
        for item in raw_segment_notes[:24]:
            if not isinstance(item, dict):
                continue
            index = ai_main._coerce_int(item.get("segment_index"), -1)
            note = str(item.get("note", "")).strip()
            if index < 0 or not note:
                continue
            segment_notes.append({"segment_index": index, "note": note[:220]})

    questions_for_client: list[str] = []
    if isinstance(raw_questions, list):
        for item in raw_questions[:5]:
            question = str(item).strip()
            if question:
                questions_for_client.append(question[:220])

    return {
        "proposal_title": proposal_title or "AI Audio Engineer Proposal",
        "mixing_rationale": rationale or "DSP-aligned segment plan with editable transitions and effects.",
        "segment_notes": segment_notes,
        "questions_for_client": questions_for_client,
    }


def create_mix_proposal(prompt: str, *, session_dir: str) -> dict[str, Any]:
    workspace = ai_main._prepare_workspace(session_dir)
    requirements = _plan_requirements(prompt)

    song_plan = ai_main._fetch_song_plan(prompt, workspace.json_path)
    track_sources = ai_main._download_sources(song_plan, workspace.temp_dir)
    mix_plan = ai_main._plan_mix_intent(prompt, track_sources)
    mix_plan = ai_main._MixIntentPlan(
        strategy="creative_mix",
        use_timestamped_lyrics=False,
        target_segment_duration_seconds=mix_plan.target_segment_duration_seconds,
        global_crossfade_seconds=mix_plan.global_crossfade_seconds,
        transition_crossfade_seconds=mix_plan.transition_crossfade_seconds,
        track_windows=mix_plan.track_windows,
        target_total_duration_seconds=requirements["target_duration_seconds"],
        reason=mix_plan.reason,
    )

    tuned_tracks = ai_main._apply_mix_intent_to_tracks(track_sources, mix_plan)
    candidates_by_track: dict[int, list[ai_main._SegmentCandidate]] = {}
    track_cards: list[dict[str, Any]] = []

    preview_dir = Path(session_dir) / "static" / "audio_dl"
    preview_dir.mkdir(parents=True, exist_ok=True)

    for track_index, track_source in enumerate(tuned_tracks):
        audio = AudioSegment.from_file(track_source.source_path, format="m4a")
        dsp = analyze_track_beats(audio, label=f"{track_source.plan.title} - {track_source.plan.artist}")
        target_duration_ms = ai_main._derive_target_duration_ms(
            track_source.plan.requested_duration_seconds or (track_source.plan.suggested_end - track_source.plan.suggested_start),
            index=track_index,
            total_tracks=len(tuned_tracks),
            source_duration_ms=len(audio),
            prompt_relevance=track_source.prompt_relevance,
        )
        candidates_by_track[track_index] = ai_main._build_track_segment_candidates(
            track_source,
            track_index=track_index,
            audio=audio,
            target_duration_ms=target_duration_ms,
            dsp_profile=dsp,
        )

        preview_filename = f"track_{track_index}.mp3"
        preview_path = preview_dir / preview_filename
        if not preview_path.exists():
            audio.export(str(preview_path), format="mp3")

        track_cards.append(
            {
                "id": str(track_index),
                "track_index": track_index,
                "title": track_source.plan.title,
                "artist": track_source.plan.artist,
                "duration_seconds": round(len(audio) / 1000, 2),
                "bpm": round(dsp.bpm, 2),
                "key": dsp.key_name,
                "source_filename": Path(track_source.source_path).name,
                "preview_filename": preview_filename,
            }
        )

    llm_selected = ai_main._select_candidates_with_llm(prompt, tuned_tracks, candidates_by_track)
    optimized = ai_main._optimize_candidate_transitions(tuned_tracks, candidates_by_track, llm_selected)
    sequence = ai_main._build_candidate_sequence_for_target_duration(tuned_tracks, candidates_by_track, optimized, mix_plan)
    if not sequence:
        sequence = [optimized[index] for index in sorted(optimized.keys())]

    crossfades = _crossfade_seconds_for_sequence(mix_plan, len(sequence))
    segments: list[dict[str, Any]] = []
    for index, candidate in enumerate(sequence):
        effect_defaults = requirements.get("effects", {})
        segments.append(
            {
                "id": f"seg_{index + 1}",
                "order": index,
                "track_index": candidate.track_index,
                "track_id": str(candidate.track_index),
                "track_title": tuned_tracks[candidate.track_index].plan.title,
                "start_ms": int(candidate.start_ms),
                "end_ms": int(candidate.end_ms),
                "duration_ms": int(max(1, candidate.end_ms - candidate.start_ms)),
                "crossfade_after_seconds": float(crossfades[index]) if index < len(crossfades) else 0.0,
                "effects": {
                    "reverb_amount": float(effect_defaults.get("reverb_amount", 0.15)),
                    "delay_ms": int(effect_defaults.get("delay_ms", 140)),
                    "delay_feedback": float(effect_defaults.get("delay_feedback", 0.16)),
                },
                "eq": {
                    "low_gain_db": 0.0,
                    "mid_gain_db": 0.0,
                    "high_gain_db": 0.0,
                },
            }
        )

    engineer_text = _engineer_explain_proposal(prompt, requirements, track_cards, segments)
    estimated_duration_ms = ai_main._effective_sequence_duration_ms(sequence, mix_plan)

    return {
        "requirements": requirements,
        "tracks": track_cards,
        "proposal": {
            "title": engineer_text["proposal_title"],
            "mixing_rationale": engineer_text["mixing_rationale"],
            "segments": segments,
            "segment_notes": engineer_text["segment_notes"],
            "estimated_duration_seconds": round(estimated_duration_ms / 1000, 2),
            "questions_for_client": engineer_text["questions_for_client"],
        },
        "client_questions": requirements.get("client_questions", []),
    }


def review_client_submission(
    client_questions: list[dict[str, Any]],
    answers: dict[str, Any],
) -> list[dict[str, Any]]:
    follow_ups: list[dict[str, Any]] = []
    for question in client_questions:
        question_id = str(question.get("id", "")).strip()
        if not question_id:
            continue
        answer_payload = answers.get(question_id)
        if isinstance(answer_payload, dict):
            selected = str(answer_payload.get("selected", "")).strip()
            custom = str(answer_payload.get("other_text", "")).strip()
            if selected and selected.lower() != "other":
                continue
            if selected.lower() == "other" and custom:
                continue
        elif isinstance(answer_payload, str) and answer_payload.strip():
            continue

        follow_ups.append(
            {
                "id": question_id,
                "question": question.get("question", "Please provide details"),
                "options": question.get("options", []),
                "allow_other": True,
            }
        )
    return follow_ups


def finalize_mix_proposal(
    *,
    session_dir: str,
    proposal: dict[str, Any],
) -> dict[str, str]:
    raw_segments = proposal.get("segments", [])
    if not isinstance(raw_segments, list) or not raw_segments:
        raise RuntimeError("No segments provided for final render.")

    split_dir = Path(session_dir) / "temp" / "split"
    output_dir = Path(session_dir) / "static" / "output"
    split_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_cache: dict[int, AudioSegment] = {}
    rendered_files: list[str] = []
    transition_crossfade_ms: list[int] = []

    for order, raw_segment in enumerate(raw_segments):
        if not isinstance(raw_segment, dict):
            continue
        track_index = ai_main._coerce_int(raw_segment.get("track_index"), -1)
        if track_index < 0:
            continue

        if track_index not in audio_cache:
            source_path = Path(session_dir) / "temp" / f"{track_index}.m4a"
            if not source_path.exists():
                raise RuntimeError(f"Missing source track for index {track_index}.")
            audio_cache[track_index] = AudioSegment.from_file(str(source_path), format="m4a")

        segment_audio = render_segment_with_effects(
            audio_cache[track_index],
            start_ms=ai_main._coerce_int(raw_segment.get("start_ms"), 0),
            end_ms=ai_main._coerce_int(raw_segment.get("end_ms"), 1000),
            low_gain_db=ai_main._coerce_float(raw_segment.get("eq", {}).get("low_gain_db", 0.0), 0.0)
            if isinstance(raw_segment.get("eq"), dict)
            else 0.0,
            mid_gain_db=ai_main._coerce_float(raw_segment.get("eq", {}).get("mid_gain_db", 0.0), 0.0)
            if isinstance(raw_segment.get("eq"), dict)
            else 0.0,
            high_gain_db=ai_main._coerce_float(raw_segment.get("eq", {}).get("high_gain_db", 0.0), 0.0)
            if isinstance(raw_segment.get("eq"), dict)
            else 0.0,
            reverb_amount=ai_main._coerce_float(raw_segment.get("effects", {}).get("reverb_amount", 0.0), 0.0)
            if isinstance(raw_segment.get("effects"), dict)
            else 0.0,
            delay_ms=ai_main._coerce_int(raw_segment.get("effects", {}).get("delay_ms", 0), 0)
            if isinstance(raw_segment.get("effects"), dict)
            else 0,
            delay_feedback=ai_main._coerce_float(raw_segment.get("effects", {}).get("delay_feedback", 0.0), 0.0)
            if isinstance(raw_segment.get("effects"), dict)
            else 0.0,
        )

        segment_path = split_dir / f"{order:03d}.mp3"
        segment_audio.export(str(segment_path), format="mp3")
        rendered_files.append(str(segment_path))

        crossfade_seconds = ai_main._coerce_float(raw_segment.get("crossfade_after_seconds"), 0.0)
        transition_crossfade_ms.append(int(ai_main._clamp(crossfade_seconds, 0.0, 8.0) * 1000))

    if not rendered_files:
        raise RuntimeError("No valid segments available to render.")

    merge_crossfades = transition_crossfade_ms[: max(0, len(rendered_files) - 1)]
    merged_mp3 = merge_segments(
        rendered_files,
        output_dir=str(output_dir),
        crossfade_ms=merge_crossfades if merge_crossfades else 0,
    )
    merged_mp3_path = Path(merged_mp3)
    if not merged_mp3_path.exists():
        raise RuntimeError("Merged MP3 output is missing.")

    merged_audio = AudioSegment.from_file(str(merged_mp3_path), format="mp3")
    merged_wav_path = merged_mp3_path.with_suffix(".wav")
    merged_audio.export(str(merged_wav_path), format="wav")

    return {
        "mp3_path": str(merged_mp3_path),
        "wav_path": str(merged_wav_path),
    }

