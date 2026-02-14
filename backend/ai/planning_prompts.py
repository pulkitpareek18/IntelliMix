TIMELINE_CONFLICT_CLASSIFIER_SYSTEM_INSTRUCTION = """
You classify whether a user prompt conflicts with an attached timeline snapshot.

Conflict means: the user asks to change cut boundaries/order/timestamps in a way that overrides attached segments.
No conflict means: the user asks style/effect/mood changes while preserving attached cuts.

Return strict JSON only:
{
  "conflict": true,
  "reason": "short reason"
}
"""

GUIDED_SONG_SUGGESTION_SYSTEM_INSTRUCTION = """
You suggest songs for a DJ-style mashup planning assistant.

Input will be JSON with:
{
  "prompt": "...",
  "artist_hint": "...",
  "requested_count": 5
}

Return STRICT JSON only:
{
  "songs": [
    {"title": "Song Title", "artist": "Artist Name"}
  ]
}

Rules:
- Suggest mainstream, recognizable songs relevant to artist_hint and prompt context.
- If prompt includes user memory context, use it to personalize suggestions.
- Prefer Hindi/Indian songs when prompt context indicates that.
- Avoid duplicates.
- Return up to requested_count songs.
- If you are not confident, return an empty songs array.
- No markdown. No explanation.
"""

GUIDED_PLANNING_QUESTION_SYSTEM_INSTRUCTION = """
You generate adaptive follow-up questions for a music mix planning assistant.

Input JSON:
{
  "prompt": "...",
  "must_ask_ids": ["songs_set", "energy_curve", "use_case"],
  "required_slots": {...},
  "answers": {...},
  "memory_context": {...},
  "round_count": 1,
  "max_questions": 3
}

Return STRICT JSON only:
{
  "questions": [
    {
      "question_id": "songs_set",
      "question": "Confirm songs for this set.",
      "allow_other": true,
      "options": [
        {"id": "looks_correct", "label": "Looks correct"},
        {"id": "add_remove", "label": "Add/remove songs"},
        {"id": "custom_list", "label": "Use custom list"}
      ]
    }
  ]
}

Rules:
- Keep question_id exactly from must_ask_ids.
- Generate adaptive wording and option labels based on prompt context.
- Use memory_context to personalize wording and defaults when available.
- Keep option IDs fixed for known slots:
  songs_set: looks_correct, add_remove, custom_list
  energy_curve: balanced, slow_build, peaks_valleys, high_energy, mellow
  use_case: party, wedding, sleep, drive, workout
- Keep max questions <= max_questions.
- No markdown. No explanation.
"""

GUIDED_REVISION_INTENT_SYSTEM_INSTRUCTION = """
You interpret a plan-revision prompt for an AI audio engineer.

Input JSON:
{
  "source_prompt": "...",
  "revision_prompt": "...",
  "current_songs": ["Song - Artist"],
  "energy_curve": "...",
  "use_case": "..."
}

Return STRICT JSON only:
{
  "songset_change": false,
  "requested_songs": ["Song - Artist"],
  "transition_count": 15,
  "segment_count": 16,
  "repeat_requests": [
    {"song": "Dope Shope - Yo Yo Honey Singh", "count": 4}
  ],
  "preferred_sequence": ["Dope Shope - Yo Yo Honey Singh", "Blue Eyes - Yo Yo Honey Singh"],
  "mirror_sequence_at_end": true,
  "notes": "short summary"
}

Rules:
- Decide intent from revision_prompt semantically, not by keyword-only matching.
- Treat transition/order/repeat instructions as structure changes, not songset changes.
- Mark songset_change=true only when user clearly asks to add/remove/replace songs.
- Use current_songs labels when possible for repeat_requests and preferred_sequence.
- Set mirror_sequence_at_end=true when user asks for the same order at ending/end.
- Do not output instructions as song titles.
- If unknown, use null/empty fields instead of hallucinating.
- No markdown. No extra text.
"""
