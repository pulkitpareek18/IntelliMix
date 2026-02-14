from __future__ import annotations

import pytest

import mix_chat_runner


def test_resolve_initial_song_candidates_uses_ai_suggestions_for_vague_prompt(monkeypatch):
    monkeypatch.setattr(
        mix_chat_runner,
        "_suggest_songs_with_ai",
        lambda _prompt, _artist, requested_count: [
            "Mere Mehboob Qayamat Hogi - Kishore Kumar",
            "O Mere Dil Ke Chain - Kishore Kumar",
            "Pal Pal Dil Ke Paas - Kishore Kumar",
            "Roop Tera Mastana - Kishore Kumar",
            "Ek Ajnabee Haseena Se - Kishore Kumar",
        ][:requested_count],
    )
    songs, source = mix_chat_runner._resolve_initial_song_candidates(  # noqa: SLF001
        "create a mashup kishore kumar songs"
    )

    assert source == "suggested"
    assert len(songs) >= 2
    assert any("kishore kumar" in song.lower() for song in songs)


def test_parse_song_list_from_prompt_ignores_generic_artist_count_request():
    songs = mix_chat_runner._parse_song_list_from_prompt("create a mix of 5 honey singh songs")  # noqa: SLF001
    assert songs == []


def test_resolve_initial_song_candidates_uses_suggestions_for_generic_artist_count_prompt(monkeypatch):
    monkeypatch.setattr(
        mix_chat_runner,
        "_suggest_songs_with_ai",
        lambda _prompt, _artist, requested_count: [
            "Brown Rang - Yo Yo Honey Singh",
            "Blue Eyes - Yo Yo Honey Singh",
            "Dope Shope - Yo Yo Honey Singh",
            "Love Dose - Yo Yo Honey Singh",
            "Desi Kalakaar - Yo Yo Honey Singh",
        ][:requested_count],
    )
    songs, source = mix_chat_runner._resolve_initial_song_candidates(  # noqa: SLF001
        "create a mix of 5 honey singh songs"
    )

    assert source == "suggested"
    assert len(songs) >= 2
    assert all("honey singh" in song.lower() for song in songs)


def test_resolve_initial_song_candidates_prefers_explicit_song_list():
    songs, source = mix_chat_runner._resolve_initial_song_candidates(  # noqa: SLF001
        "Songs: Brown Rang - Yo Yo Honey Singh, Blue Eyes - Yo Yo Honey Singh"
    )

    assert source == "explicit"
    assert songs
    assert "brown rang" in songs[0].lower()


def test_resolve_planning_state_marks_suggested_song_source(monkeypatch):
    monkeypatch.setattr(
        mix_chat_runner,
        "_suggest_songs_with_ai",
        lambda _prompt, _artist, requested_count: [
            "Brown Rang - Yo Yo Honey Singh",
            "Blue Eyes - Yo Yo Honey Singh",
            "Dope Shope - Yo Yo Honey Singh",
        ][:requested_count],
    )
    required_slots, confidence = mix_chat_runner._resolve_planning_state(  # noqa: SLF001
        "Mix 5 Honey Singh songs for wedding",
        {},
    )

    songs_slot = required_slots.get("songs_set", {})
    assert songs_slot.get("status") == "filled"
    assert songs_slot.get("source") == "suggested"
    assert isinstance(songs_slot.get("value"), list)
    assert len(songs_slot.get("value", [])) == 3
    assert isinstance(confidence, float)


def test_resolve_planning_state_preserves_previous_songs_when_confirmation_and_refresh_fails(monkeypatch):
    monkeypatch.setattr(
        mix_chat_runner,
        "_resolve_initial_song_candidates",
        lambda _prompt, force_suggestions=False: ([], "none"),
    )

    previous_slots = {
        "songs_set": {
            "status": "filled",
            "value": [
                "Pehli Nazar Mein - Atif Aslam",
                "Tu Jaane Na - Atif Aslam",
                "Tera Hone Laga Hoon - Atif Aslam",
            ],
            "source": "suggested",
            "confidence": 0.82,
        }
    }
    answers = {
        "songs_set": {
            "selected_option_id": "looks_correct",
            "other_text": "",
        }
    }

    required_slots, _confidence = mix_chat_runner._resolve_planning_state(  # noqa: SLF001
        "create a mashup of atif aslam songs",
        answers,
        previous_required_slots=previous_slots,
    )

    songs_slot = required_slots.get("songs_set", {})
    assert songs_slot.get("status") == "filled"
    assert songs_slot.get("source") == "suggested"
    assert songs_slot.get("value") == previous_slots["songs_set"]["value"]


def test_resolve_planning_state_preserves_previous_songs_when_regenerate_hits_rate_limit(monkeypatch):
    monkeypatch.setattr(
        mix_chat_runner,
        "_resolve_initial_song_candidates",
        lambda _prompt, force_suggestions=False: ([], "none"),
    )

    previous_slots = {
        "songs_set": {
            "status": "filled",
            "value": [
                "Brown Rang - Yo Yo Honey Singh",
                "Blue Eyes - Yo Yo Honey Singh",
                "Dope Shope - Yo Yo Honey Singh",
            ],
            "source": "suggested",
            "confidence": 0.76,
        }
    }
    answers = {
        "songs_set": {
            "selected_option_id": "regenerate_suggestions",
            "other_text": "",
        }
    }

    required_slots, _confidence = mix_chat_runner._resolve_planning_state(  # noqa: SLF001
        "create a mashup of honey singh songs",
        answers,
        previous_required_slots=previous_slots,
    )

    songs_slot = required_slots.get("songs_set", {})
    assert songs_slot.get("status") == "filled"
    assert songs_slot.get("source") == "suggested"
    assert songs_slot.get("value") == previous_slots["songs_set"]["value"]


def test_resolve_planning_state_locks_previous_songs_on_looks_correct_even_with_new_suggestions(monkeypatch):
    monkeypatch.setattr(
        mix_chat_runner,
        "_resolve_initial_song_candidates",
        lambda _prompt, force_suggestions=False: (
            [
                "Random New Track 1 - Artist",
                "Random New Track 2 - Artist",
                "Random New Track 3 - Artist",
            ],
            "suggested",
        ),
    )

    previous_slots = {
        "songs_set": {
            "status": "filled",
            "value": [
                "Brown Rang - Yo Yo Honey Singh",
                "Blue Eyes - Yo Yo Honey Singh",
                "Dope Shope - Yo Yo Honey Singh",
            ],
            "source": "suggested",
            "confidence": 0.9,
        }
    }
    answers = {
        "songs_set": {
            "selected_option_id": "looks_correct",
            "other_text": "",
        }
    }

    required_slots, _confidence = mix_chat_runner._resolve_planning_state(  # noqa: SLF001
        "create a mix of honey singh songs",
        answers,
        previous_required_slots=previous_slots,
    )

    songs_slot = required_slots.get("songs_set", {})
    assert songs_slot.get("status") == "filled"
    assert songs_slot.get("source") == "suggested"
    assert songs_slot.get("value") == previous_slots["songs_set"]["value"]


def test_build_planning_questions_raises_when_ai_disabled_in_pause_mode(monkeypatch):
    monkeypatch.setenv("AI_ENABLE_ADAPTIVE_PLANNING_QUESTIONS", "false")
    monkeypatch.setenv("AI_PLANNING_PAUSE_ON_AI_FAILURE", "true")

    required_slots = {
        "songs_set": {"status": "missing", "confidence": 0.0},
        "energy_curve": {"status": "missing", "confidence": 0.0},
        "use_case": {"status": "missing", "confidence": 0.0},
    }
    previous_questions = [
        {
            "question_id": "songs_set",
            "question": "I can suggest 5 Atif tracks; should I keep them?",
            "allow_other": True,
            "options": [
                {"id": "looks_correct", "label": "Keep these"},
                {"id": "add_remove", "label": "Add/remove"},
                {"id": "custom_list", "label": "My own list"},
            ],
        },
        {
            "question_id": "energy_curve",
            "question": "What energy journey do you want?",
            "allow_other": True,
            "options": [
                {"id": "balanced", "label": "Balanced"},
                {"id": "slow_build", "label": "Slow build"},
                {"id": "peaks_valleys", "label": "Peaks/valleys"},
                {"id": "high_energy", "label": "High energy"},
                {"id": "mellow", "label": "Mellow"},
            ],
        },
        {
            "question_id": "use_case",
            "question": "Where will you play this mix?",
            "allow_other": True,
            "options": [
                {"id": "party", "label": "Party"},
                {"id": "wedding", "label": "Wedding"},
                {"id": "sleep", "label": "Sleep"},
                {"id": "drive", "label": "Drive"},
                {"id": "workout", "label": "Workout"},
            ],
        },
    ]

    with pytest.raises(RuntimeError):
        mix_chat_runner._build_planning_questions(  # noqa: SLF001
            prompt="create a mashup of atif aslam songs",
            required_slots=required_slots,
            answers={},
            round_count=1,
            min_rounds=1,
            previous_questions=previous_questions,
        )


def test_revision_prompt_songset_change_detection():
    assert mix_chat_runner._revision_prompt_requests_songset_change("add two songs one is party all night") is True  # noqa: SLF001
    assert (
        mix_chat_runner._revision_prompt_requests_songset_change(
            "add 15 transitions here, of these songs, i want dope shope 4 times"
        )
        is False
    )  # noqa: SLF001
    assert mix_chat_runner._revision_prompt_requests_songset_change("I want dope shope at start then blue eyes") is False  # noqa: SLF001


def test_suggest_songs_with_ai_filters_instructional_lines(monkeypatch):
    monkeypatch.setenv("AI_ENABLE_GUIDED_SONG_SUGGESTIONS", "true")

    def _fake_guided(**_kwargs):
        return """{
            "songs": [
                "i want dope shope 4 times",
                "Dope Shope - Yo Yo Honey Singh",
                "same order in ending also"
            ]
        }"""

    monkeypatch.setattr(mix_chat_runner, "_generate_with_guided_retries", _fake_guided)

    songs = mix_chat_runner._suggest_songs_with_ai(  # noqa: SLF001
        "create a honey singh mix",
        "Yo Yo Honey Singh",
        5,
    )

    assert songs == ["Dope Shope - Yo Yo Honey Singh"]


def test_extract_song_slot_snapshot_filters_generic_song_entries():
    songs, source, confidence = mix_chat_runner._extract_song_slot_snapshot(  # noqa: SLF001
        {
            "songs_set": {
                "value": [
                    "i want dope shope 4 times",
                    "Dope Shope - Yo Yo Honey Singh",
                    "same order in ending also",
                ],
                "source": "suggested",
                "confidence": 0.81,
            }
        }
    )

    assert songs == ["Dope Shope - Yo Yo Honey Singh"]
    assert source == "suggested"
    assert confidence == 0.81


def test_sanitize_revision_ai_intent_maps_sequence_repeat_and_counts():
    songs = [
        "Dope Shope - Yo Yo Honey Singh",
        "Blue Eyes - Yo Yo Honey Singh",
        "Angreji Beat - Yo Yo Honey Singh",
    ]
    intent = mix_chat_runner._sanitize_revision_ai_intent(  # noqa: SLF001
        {
            "songset_change": False,
            "transition_count": 15,
            "segment_count": 15,
            "repeat_requests": [{"song": "dope shope", "count": 4}],
            "preferred_sequence": ["dope shope", "blue eys", "angreji beat"],
            "requested_songs": ["add 15 transitions", "Dope Shope - Yo Yo Honey Singh"],
        },
        songs,
    )

    assert intent["songset_change"] is False
    assert intent["transition_count"] == 15
    assert intent["segment_count"] == 15
    assert intent["repeat_requests"] == {"Dope Shope - Yo Yo Honey Singh": 4}
    assert intent["preferred_sequence"][:3] == songs
    assert intent["requested_songs"] == ["Dope Shope - Yo Yo Honey Singh"]


def test_interpret_revision_prompt_with_ai_uses_structured_output(monkeypatch):
    monkeypatch.setenv("AI_ENABLE_GUIDED_REVISION_INTERPRETER", "true")
    monkeypatch.setenv("AI_GUIDED_REVISION_AI_STRICT", "true")

    def _fake_guided(**_kwargs):
        return """{
            "songset_change": false,
            "transition_count": 15,
            "segment_count": 15,
            "repeat_requests": [{"song": "dope shope", "count": 4}],
            "preferred_sequence": ["dope shope", "blue eys", "angreji beat"],
            "requested_songs": []
        }"""

    monkeypatch.setattr(mix_chat_runner, "_generate_with_guided_retries", _fake_guided)

    intent = mix_chat_runner._interpret_revision_prompt_with_ai(  # noqa: SLF001
        source_prompt="create a honey singh mix",
        revision_prompt="i want dope shope 4 times and total 15 segments",
        current_songs=[
            "Dope Shope - Yo Yo Honey Singh",
            "Blue Eyes - Yo Yo Honey Singh",
            "Angreji Beat - Yo Yo Honey Singh",
        ],
        required_slots={},
        memory_context={},
    )

    assert isinstance(intent, dict)
    assert intent["songset_change"] is False
    assert intent["segment_count"] == 15
    assert intent["repeat_requests"] == {"Dope Shope - Yo Yo Honey Singh": 4}


def test_resolve_initial_song_candidates_uses_memory_when_suggestions_unavailable(monkeypatch):
    monkeypatch.setattr(mix_chat_runner, "_suggest_songs_with_ai", lambda _prompt, _artist, _count: [])

    songs, source = mix_chat_runner._resolve_initial_song_candidates(  # noqa: SLF001
        "make me a soft romantic mix",
        memory_context={
            "preferred_songs": [
                "Pehli Nazar Mein - Atif Aslam",
                "Tu Jaane Na - Atif Aslam",
                "Tera Hone Laga Hoon - Atif Aslam",
            ]
        },
    )

    assert source == "memory"
    assert songs[:2] == [
        "Pehli Nazar Mein - Atif Aslam",
        "Tu Jaane Na - Atif Aslam",
    ]


def test_resolve_planning_state_uses_memory_defaults_for_missing_slots(monkeypatch):
    monkeypatch.setattr(mix_chat_runner, "_resolve_initial_song_candidates", lambda _prompt, force_suggestions=False, memory_context=None: ([], "none"))

    required_slots, _confidence = mix_chat_runner._resolve_planning_state(  # noqa: SLF001
        "make a mix",
        {},
        memory_context={
            "default_energy_curve": "Warm and mellow",
            "default_use_case": "Sleep / focus listening",
            "preferred_songs": ["Agar Tum Saath Ho - Alka Yagnik, Arijit Singh"],
        },
    )

    assert required_slots["energy_curve"]["value"] == "Warm and mellow"
    assert required_slots["use_case"]["value"] == "Sleep / focus listening"


def test_build_provisional_timeline_honors_repeat_directive_for_known_song():
    songs = [
        "Brown Rang - Yo Yo Honey Singh",
        "Dope Shope - Yo Yo Honey Singh",
        "Blue Eyes - Yo Yo Honey Singh",
    ]
    timeline = mix_chat_runner._build_provisional_timeline(  # noqa: SLF001
        songs,
        300,
        "Peaks and valleys",
        prompt="add 15 transitions here, of these songs, i want dope shope 4 times",
    )
    sequence = [str(item.get("song", "")) for item in timeline]
    dope_count = sum(1 for item in sequence if "dope shope" in item.lower())
    assert len(sequence) >= 16
    assert dope_count >= 4


def test_build_provisional_timeline_honors_order_and_segment_directive():
    songs = [
        "Dope Shope - Yo Yo Honey Singh",
        "Brown Rang - Yo Yo Honey Singh",
        "Blue Eyes - Yo Yo Honey Singh",
        "Angreji Beat - Yo Yo Honey Singh",
    ]
    timeline = mix_chat_runner._build_provisional_timeline(  # noqa: SLF001
        songs,
        300,
        "Peaks and valleys",
        prompt="I want dope shope at start, then blue eys and then angreji beat, same order in ending also. total 15 segments",
    )
    sequence = [str(item.get("song", "")) for item in timeline]
    assert len(sequence) == 15
    assert "dope shope" in sequence[0].lower()
    assert "blue eyes" in sequence[1].lower()
    assert "angreji beat" in sequence[2].lower()
    assert "dope shope" in sequence[-3].lower()
    assert "blue eyes" in sequence[-2].lower()
    assert "angreji beat" in sequence[-1].lower()


def test_build_provisional_timeline_default_segments_do_not_inflate_without_constraints():
    songs = [
        "Brown Rang - Yo Yo Honey Singh",
        "Dope Shope - Yo Yo Honey Singh",
        "Blue Eyes - Yo Yo Honey Singh",
        "Love Dose - Yo Yo Honey Singh",
        "Sunny Sunny - Yo Yo Honey Singh",
    ]
    timeline = mix_chat_runner._build_provisional_timeline(  # noqa: SLF001
        songs,
        300,
        "Balanced flow",
        prompt="make it club friendly",
    )

    assert len(timeline) == len(songs)


def test_apply_song_constraints_flags_impossible_required_song_count():
    songs, violations = mix_chat_runner._apply_song_constraints(  # noqa: SLF001
        base_songs=[
            "A - X",
            "B - X",
            "C - X",
            "D - X",
        ],
        contract={
            "song_count": 2,
            "must_include_songs": ["A - X", "B - X", "C - X"],
        },
        ai_requested_songs=None,
    )

    assert isinstance(songs, list)
    assert any("marked required" in item.lower() for item in violations)


def test_contract_enforces_exact_song_and_segment_counts_for_revision_flow():
    base_songs = [
        "Millionaire - Yo Yo Honey Singh",
        "Brown Rang - Yo Yo Honey Singh",
        "Blue Eyes - Yo Yo Honey Singh",
        "Dope Shope - Yo Yo Honey Singh",
        "Angreji Beat - Yo Yo Honey Singh",
        "Sunny Sunny - Yo Yo Honey Singh",
        "Love Dose - Yo Yo Honey Singh",
        "Desi Kalakaar - Yo Yo Honey Singh",
        "Lungi Dance - Yo Yo Honey Singh",
    ]
    contract = {
        "song_count": 7,
        "segment_count": 15,
        "must_include_songs": [
            "Millionaire - Yo Yo Honey Singh",
            "Brown Rang - Yo Yo Honey Singh",
        ],
        "repeat_requests": {},
        "preferred_sequence": [],
    }
    constrained_songs, violations = mix_chat_runner._apply_song_constraints(  # noqa: SLF001
        base_songs=base_songs,
        contract=contract,
        ai_requested_songs=None,
    )
    assert violations == []
    assert len(constrained_songs) == 7

    required_slots = {
        "songs_set": {
            "label": "Song set",
            "status": "filled",
            "value": constrained_songs,
            "source": "constraint_contract",
            "confidence": 0.9,
        },
        "energy_curve": {"label": "Energy curve", "status": "filled", "value": "Peaks and valleys", "confidence": 0.9},
        "use_case": {"label": "Purpose / use-case", "status": "filled", "value": "Party / dance floor", "confidence": 0.9},
    }
    proposal, _resolution_notes = mix_chat_runner._build_plan_draft_payload(  # noqa: SLF001
        prompt="add two more songs, total 7 songs, and total 15 segments",
        required_slots=required_slots,
        adjustment_policy="minor_auto_adjust_allowed",
        revision_ai_intent={"segment_count": 15},
    )

    resolved_songs = proposal.get("resolved_songs", [])
    timeline = proposal.get("provisional_timeline", [])
    assert isinstance(resolved_songs, list)
    assert isinstance(timeline, list)
    assert len(resolved_songs) == 7
    assert len(timeline) == 15

    contract_violations = mix_chat_runner._validate_plan_contract(  # noqa: SLF001
        contract=contract,
        songs=constrained_songs,
        timeline=timeline,
    )
    assert contract_violations == []
