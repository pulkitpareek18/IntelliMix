from __future__ import annotations

from ai import ai_main
from pydub import AudioSegment


def _build_track(index: int, title: str, artist: str) -> ai_main._TrackSource:
    return ai_main._TrackSource(
        plan=ai_main._SongPlanItem(
            title=title,
            artist=artist,
            url=f"https://example.com/{index}",
            suggested_start=0,
            suggested_end=30,
        ),
        source_path=f"/tmp/{index}.m4a",
        source_index=index,
    )


def test_tokenize_text_filters_common_words():
    tokens = ai_main._tokenize_text("This is the night we dance and celebrate together")
    assert "this" not in tokens
    assert "the" not in tokens
    assert "night" in tokens
    assert "dance" in tokens
    assert "celebrate" in tokens


def test_lyrics_analysis_can_reorder_tracks(monkeypatch):
    tracks = [
        _build_track(0, "Love Night", "Artist A"),
        _build_track(1, "Broken Road", "Artist B"),
        _build_track(2, "City Lights", "Artist C"),
    ]

    lyrics_by_song = {
        ("Artist A", "Love Night"): "dance party smile celebrate dream",
        ("Artist B", "Broken Road"): "alone cry broken tears cold pain",
        ("Artist C", "City Lights"): "night city party dance dream shine",
    }

    monkeypatch.setenv("AI_ENABLE_LYRICS_ANALYSIS", "true")
    monkeypatch.setenv("LYRICS_FETCH_TIMEOUT_SECONDS", "1.0")
    monkeypatch.setattr(
        ai_main,
        "_fetch_lyrics_text",
        lambda artist, title, base_url, timeout_seconds: lyrics_by_song.get((artist, title), ""),
    )

    ordered = ai_main._enrich_and_order_tracks_with_lyrics(tracks, "dance party celebration mix")
    ordered_titles = [item.plan.title for item in ordered]
    assert ordered_titles[0] == "Love Night"
    assert ordered_titles[-1] == "Broken Road"


def test_lyrics_analysis_can_be_disabled(monkeypatch):
    tracks = [
        _build_track(0, "Song One", "Artist One"),
        _build_track(1, "Song Two", "Artist Two"),
    ]
    fetch_called = {"value": False}

    def _fake_fetch(artist: str, title: str, base_url: str, timeout_seconds: float) -> str:
        fetch_called["value"] = True
        return "lyrics"

    monkeypatch.setenv("AI_ENABLE_LYRICS_ANALYSIS", "false")
    monkeypatch.setattr(ai_main, "_fetch_lyrics_text", _fake_fetch)

    ordered = ai_main._enrich_and_order_tracks_with_lyrics(tracks, "any prompt")
    assert [item.source_index for item in ordered] == [0, 1]
    assert fetch_called["value"] is False


def test_llm_candidate_selection_uses_model_output(monkeypatch):
    track = _build_track(0, "Love Night", "Artist A")
    track.lyrics_profile = ai_main._LyricsProfile(
        keywords=frozenset({"dance", "party"}),
        positivity=0.6,
        has_lyrics=True,
        excerpt="dance party all night",
    )
    candidates_by_track = {
        0: [
            ai_main._SegmentCandidate(
                candidate_id="t0c0",
                track_index=0,
                start_ms=0,
                end_ms=20000,
                energy_db=-12.0,
                drop_strength=0.4,
                transition_quality=2.0,
            ),
            ai_main._SegmentCandidate(
                candidate_id="t0c1",
                track_index=0,
                start_ms=10000,
                end_ms=30000,
                energy_db=-11.5,
                drop_strength=1.4,
                transition_quality=2.5,
            ),
        ]
    }

    monkeypatch.setenv("AI_ENABLE_LLM_LYRICS_BEATS", "true")
    monkeypatch.setattr(
        ai_main,
        "generate_with_instruction",
        lambda prompt, system_instruction: '{"selections":[{"track_index":0,"candidate_id":"t0c1"}]}',
    )

    selected = ai_main._select_candidates_with_llm("party mix", [track], candidates_by_track)
    assert selected[0].candidate_id == "t0c1"


def test_llm_candidate_selection_falls_back_when_invalid(monkeypatch):
    track = _build_track(0, "Song One", "Artist One")
    candidates_by_track = {
        0: [
            ai_main._SegmentCandidate(
                candidate_id="t0c0",
                track_index=0,
                start_ms=0,
                end_ms=20000,
                energy_db=-12.0,
                drop_strength=0.4,
                transition_quality=2.0,
            ),
            ai_main._SegmentCandidate(
                candidate_id="t0c1",
                track_index=0,
                start_ms=10000,
                end_ms=30000,
                energy_db=-11.5,
                drop_strength=1.2,
                transition_quality=2.6,
            ),
        ]
    }

    monkeypatch.setenv("AI_ENABLE_LLM_LYRICS_BEATS", "true")
    monkeypatch.setattr(ai_main, "generate_with_instruction", lambda prompt, system_instruction: "not-json")

    selected = ai_main._select_candidates_with_llm("any prompt", [track], candidates_by_track)
    assert selected[0].candidate_id == "t0c1"


def test_transition_optimizer_improves_pair_flow(monkeypatch):
    track_a = _build_track(0, "Song A", "Artist A")
    track_b = _build_track(1, "Song B", "Artist B")

    candidates_by_track = {
        0: [
            ai_main._SegmentCandidate(
                candidate_id="t0c0",
                track_index=0,
                start_ms=0,
                end_ms=22000,
                energy_db=-12.0,
                drop_strength=0.9,
                transition_quality=2.1,
                beat_interval_ms=320,
                bpm=124.0,
                key_index=0,
                key_scale="major",
                key_name="C major",
                key_confidence=0.7,
                section_alignment=0.9,
                waveform_dynamics=2.0,
            )
        ],
        1: [
            ai_main._SegmentCandidate(
                candidate_id="t1c0",
                track_index=1,
                start_ms=0,
                end_ms=22000,
                energy_db=-12.2,
                drop_strength=0.7,
                transition_quality=2.2,
                beat_interval_ms=700,
                bpm=86.0,
                key_index=6,
                key_scale="minor",
                key_name="F# minor",
                key_confidence=0.7,
                section_alignment=0.2,
                waveform_dynamics=4.5,
            ),
            ai_main._SegmentCandidate(
                candidate_id="t1c1",
                track_index=1,
                start_ms=10000,
                end_ms=32000,
                energy_db=-12.5,
                drop_strength=0.8,
                transition_quality=1.9,
                beat_interval_ms=330,
                bpm=122.0,
                key_index=7,
                key_scale="major",
                key_name="G major",
                key_confidence=0.7,
                section_alignment=0.88,
                waveform_dynamics=2.2,
            ),
        ],
    }
    llm_selected = {
        0: candidates_by_track[0][0],
        1: candidates_by_track[1][0],
    }

    monkeypatch.setenv("AI_ENABLE_TRANSITION_OPTIMIZER", "true")
    monkeypatch.setenv("AI_TRANSITION_PAIR_WEIGHT", "3.0")
    monkeypatch.setenv("AI_LLM_SELECTION_STICKINESS", "0.0")

    optimized = ai_main._optimize_candidate_transitions(
        [track_a, track_b],
        candidates_by_track,
        llm_selected,
    )
    assert optimized[1].candidate_id == "t1c1"


def test_harmonic_transition_compatibility_prefers_related_keys():
    left = ai_main._SegmentCandidate(
        candidate_id="l",
        track_index=0,
        start_ms=0,
        end_ms=20_000,
        energy_db=-12.0,
        drop_strength=0.4,
        transition_quality=2.0,
        key_index=0,  # C
        key_scale="major",
        key_name="C major",
    )
    related = ai_main._SegmentCandidate(
        candidate_id="r1",
        track_index=1,
        start_ms=0,
        end_ms=20_000,
        energy_db=-12.0,
        drop_strength=0.4,
        transition_quality=2.0,
        key_index=7,  # G
        key_scale="major",
        key_name="G major",
    )
    distant = ai_main._SegmentCandidate(
        candidate_id="r2",
        track_index=1,
        start_ms=0,
        end_ms=20_000,
        energy_db=-12.0,
        drop_strength=0.4,
        transition_quality=2.0,
        key_index=1,  # C#
        key_scale="minor",
        key_name="C# minor",
    )
    assert ai_main._harmonic_transition_compatibility(left, related) > ai_main._harmonic_transition_compatibility(
        left, distant
    )


def test_build_track_segment_candidates_includes_dsp_metadata():
    track = _build_track(0, "Song A", "Artist A")
    audio = AudioSegment.silent(duration=45_000)
    dsp_profile = ai_main._TrackDSPProfile(
        beat_interval_ms=500,
        bpm=120.0,
        key_index=9,
        key_scale="minor",
        key_name="A minor",
        key_confidence=0.6,
        frame_ms=250,
        energy_frames=[-20.0 for _ in range(180)],
        section_boundaries_ms=[0, 8_000, 16_000, 24_000, 32_000, 40_000, 45_000],
    )

    candidates = ai_main._build_track_segment_candidates(
        track,
        track_index=0,
        audio=audio,
        target_duration_ms=22_000,
        dsp_profile=dsp_profile,
    )
    assert candidates
    assert all(candidate.bpm == 120.0 for candidate in candidates)
    assert all(candidate.key_name == "A minor" for candidate in candidates)
    assert all(0.0 <= candidate.section_alignment <= 1.0 for candidate in candidates)


def test_extract_explicit_song_list_from_prompt():
    prompt = "haseen - talwinder, sahiba - aditya rikhari\nmixing way:\nline one"
    songs = ai_main._extract_explicit_song_list(prompt)
    assert songs == [("haseen", "talwinder"), ("sahiba", "aditya rikhari")]


def test_build_script_track_sequence_repeats_tracks_from_prompt(monkeypatch):
    tracks = [
        _build_track(0, "Haseen", "Talwinder"),
        _build_track(1, "Sahiba", "Aditya Rikhari"),
    ]
    tracks[0].prompt_relevance = 0.5
    tracks[1].prompt_relevance = 0.4

    lyrics_by_song = {
        ("Talwinder", "Haseen"): "Tere ishq da jaam haseen ae\nTu haseen tera naam haseen ae",
        ("Aditya Rikhari", "Sahiba"): "साहिबा समंदर मेरी आंखों में रह गए\nदिल न किराए का थोड़ा तो संभालो ना",
    }

    prompt = (
        "haseen - talwinder, sahiba - aditya rikhari\n"
        "mixing way:\n"
        "Tere ishq da jaam haseen ae\n"
        "साहिबा समंदर मेरी आंखों में रह गए\n"
        "Tu haseen tera naam haseen ae\n"
    )

    monkeypatch.setenv("LYRICS_FETCH_TIMEOUT_SECONDS", "1.0")
    monkeypatch.setattr(
        ai_main,
        "_fetch_lyrics_text",
        lambda artist, title, base_url, timeout_seconds: lyrics_by_song.get((artist, title), ""),
    )

    scripted = ai_main._build_script_track_sequence(tracks, prompt)
    assert len(scripted) == 3
    assert scripted[0].plan.title == "Haseen"
    assert scripted[1].plan.title == "Sahiba"
    assert scripted[2].plan.title == "Haseen"


def test_build_script_track_sequence_keeps_all_explicit_tracks(monkeypatch):
    tracks = [
        _build_track(0, "Haseen", "Talwinder"),
        _build_track(1, "Sahiba", "Aditya Rikhari"),
    ]
    tracks[0].prompt_relevance = 0.7
    tracks[1].prompt_relevance = 0.1

    lyrics_by_song = {
        ("Talwinder", "Haseen"): "Tere ishq da jaam haseen ae\nTu haseen tera naam haseen ae",
        ("Aditya Rikhari", "Sahiba"): "",
    }

    prompt = (
        "haseen - talwinder, sahiba - aditya rikhari\n"
        "mixing way:\n"
        "Tere ishq da jaam haseen ae\n"
        "Tu haseen tera naam haseen ae\n"
        "Subha haseen meri shaam haseen ae\n"
    )

    monkeypatch.setenv("LYRICS_FETCH_TIMEOUT_SECONDS", "1.0")
    monkeypatch.setattr(
        ai_main,
        "_fetch_lyrics_text",
        lambda artist, title, base_url, timeout_seconds: lyrics_by_song.get((artist, title), ""),
    )

    scripted = ai_main._build_script_track_sequence(tracks, prompt)
    scripted_titles = [item.plan.title for item in scripted]
    assert "Haseen" in scripted_titles
    assert "Sahiba" in scripted_titles


def test_timestamped_lyrics_sequence_uses_llm_segments(monkeypatch):
    tracks = [
        _build_track(0, "Haseen", "Talwinder"),
        _build_track(1, "Sahiba", "Aditya Rikhari"),
    ]
    tracks[0].plan.url = "https://youtu.be/haseen123"
    tracks[1].plan.url = "https://youtu.be/sahiba123"

    lyrics_by_song = {
        ("Talwinder", "Haseen"): "Tere ishq da jaam haseen ae\nTu haseen tera naam haseen ae",
        ("Aditya Rikhari", "Sahiba"): "Sahiba samandar meri aankhon me reh gaye",
    }

    prompt = (
        "haseen - talwinder, sahiba - aditya rikhari\n"
        "mixing way:\n"
        "Tere ishq da jaam haseen ae\n"
        "Sahiba samandar meri aankhon me reh gaye\n"
    )

    monkeypatch.setenv("AI_ENABLE_TIMESTAMPED_LYRICS", "true")
    monkeypatch.setattr(
        ai_main,
        "_fetch_lyrics_text",
        lambda artist, title, base_url, timeout_seconds: lyrics_by_song.get((artist, title), ""),
    )
    monkeypatch.setattr(
        ai_main,
        "_fetch_timestamped_lyrics_from_lrclib",
        lambda artist, title, api_base_url, timeout_seconds: [],
    )
    monkeypatch.setattr(
        ai_main,
        "generate_with_instruction",
        lambda prompt, system_instruction: (
            '{"segments":['
            '{"script_index":0,"track_index":0,"start_seconds":12.0,"end_seconds":15.0,"confidence":0.9},'
            '{"script_index":1,"track_index":1,"start_seconds":28.0,"end_seconds":31.0,"confidence":0.88}'
            "]}"
        ),
    )

    scripted = ai_main._build_timestamped_lyrics_track_sequence(tracks, prompt)
    assert len(scripted) == 2
    assert scripted[0].plan.title == "Haseen"
    assert scripted[1].plan.title == "Sahiba"
    assert scripted[0].plan.forced_start_ms is not None
    assert scripted[0].plan.forced_end_ms is not None
    assert scripted[1].plan.forced_start_ms is not None
    assert scripted[1].plan.forced_end_ms is not None


def test_timestamped_lyrics_sequence_falls_back_when_llm_invalid(monkeypatch):
    tracks = [
        _build_track(0, "Haseen", "Talwinder"),
        _build_track(1, "Sahiba", "Aditya Rikhari"),
    ]
    tracks[0].plan.url = "https://youtu.be/haseen123"
    tracks[1].plan.url = "https://youtu.be/sahiba123"

    lyrics_by_song = {
        ("Talwinder", "Haseen"): "Tere ishq da jaam haseen ae",
        ("Aditya Rikhari", "Sahiba"): "Sahiba samandar meri aankhon me reh gaye",
    }

    prompt = (
        "haseen - talwinder, sahiba - aditya rikhari\n"
        "mixing way:\n"
        "Tere ishq da jaam haseen ae\n"
        "Sahiba samandar meri aankhon me reh gaye\n"
    )

    monkeypatch.setenv("AI_ENABLE_TIMESTAMPED_LYRICS", "true")
    monkeypatch.setattr(
        ai_main,
        "_fetch_lyrics_text",
        lambda artist, title, base_url, timeout_seconds: lyrics_by_song.get((artist, title), ""),
    )
    monkeypatch.setattr(
        ai_main,
        "_fetch_timestamped_lyrics_from_lrclib",
        lambda artist, title, api_base_url, timeout_seconds: [],
    )
    monkeypatch.setattr(ai_main, "generate_with_instruction", lambda prompt, system_instruction: "not-json")

    scripted = ai_main._build_timestamped_lyrics_track_sequence(tracks, prompt)
    assert len(scripted) == 2
    assert scripted[0].plan.title == "Haseen"
    assert scripted[1].plan.title == "Sahiba"


def test_forced_segment_window_is_used_for_candidates():
    track = _build_track(0, "Haseen", "Talwinder")
    track.plan.forced_start_ms = 10_000
    track.plan.forced_end_ms = 22_000
    audio = AudioSegment.silent(duration=30_000)

    candidates = ai_main._build_track_segment_candidates(
        track,
        track_index=0,
        audio=audio,
        target_duration_ms=18_000,
    )
    assert len(candidates) == 1
    assert candidates[0].start_ms >= 9_000
    assert candidates[0].end_ms <= 24_000


def test_parse_lrc_timestamped_lyrics_extracts_ordered_lines():
    lrc = (
        "[00:12.50]Tere ishq da jaam haseen ae\n"
        "[00:28.00]Sahiba samandar meri aankhon me reh gaye\n"
    )
    lines = ai_main._parse_lrc_timestamped_lyrics(lrc)
    assert len(lines) == 2
    assert lines[0].start_seconds < lines[1].start_seconds
    assert "haseen" in lines[0].text.lower()
    assert lines[0].source == "lrc"


def test_build_timestamped_lyrics_lines_estimates_from_plain_lyrics():
    lyrics = "line one for haseen\nline two for haseen\nline three for haseen"
    lines = ai_main._build_timestamped_lyrics_lines(lyrics, audio_duration_seconds=180.0)
    assert len(lines) == 3
    assert lines[0].start_seconds < lines[-1].start_seconds
    assert all(line.source == "lyrics_estimated" for line in lines)


def test_timestamped_lyrics_sequence_uses_lrc_when_transcript_missing(monkeypatch):
    tracks = [
        _build_track(0, "Haseen", "Talwinder"),
        _build_track(1, "Sahiba", "Aditya Rikhari"),
    ]
    tracks[0].plan.url = "https://youtu.be/haseen123"
    tracks[1].plan.url = "https://youtu.be/sahiba123"

    prompt = (
        "haseen - talwinder, sahiba - aditya rikhari\n"
        "mixing way:\n"
        "Tere ishq da jaam haseen ae\n"
        "Sahiba samandar meri aankhon me reh gaye\n"
    )

    monkeypatch.setenv("AI_ENABLE_TIMESTAMPED_LYRICS", "true")
    monkeypatch.setattr(ai_main, "_fetch_lyrics_text", lambda artist, title, base_url, timeout_seconds: "")
    monkeypatch.setattr(
        ai_main,
        "_fetch_timestamped_lyrics_from_lrclib",
        lambda artist, title, api_base_url, timeout_seconds: (
            [
                ai_main._TimestampedLyricLine(
                    text="Tere ishq da jaam haseen ae",
                    start_seconds=12.0,
                    end_seconds=16.0,
                    confidence=0.93,
                    source="lrc",
                )
            ]
            if title == "Haseen"
            else [
                ai_main._TimestampedLyricLine(
                    text="Sahiba samandar meri aankhon me reh gaye",
                    start_seconds=30.0,
                    end_seconds=34.0,
                    confidence=0.93,
                    source="lrc",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        ai_main,
        "generate_with_instruction",
        lambda prompt, system_instruction: (
            '{"segments":['
            '{"script_index":0,"track_index":0,"start_seconds":12.0,"end_seconds":16.0,"confidence":0.9},'
            '{"script_index":1,"track_index":1,"start_seconds":30.0,"end_seconds":34.0,"confidence":0.9}'
            "]}"
        ),
    )

    scripted = ai_main._build_timestamped_lyrics_track_sequence(tracks, prompt)
    assert len(scripted) == 2
    assert scripted[0].plan.title == "Haseen"
    assert scripted[1].plan.title == "Sahiba"


def test_generate_ai_intelligent_uses_creative_flow_only(monkeypatch, tmp_path):
    workspace = ai_main._prepare_workspace(str(tmp_path))

    timed_track = _build_track(0, "Haseen", "Talwinder")
    timed_track.plan.forced_start_ms = 12_000
    timed_track.plan.forced_end_ms = 24_000

    monkeypatch.setattr(
        ai_main,
        "_fetch_song_plan",
        lambda prompt, json_path: [
            ai_main._SongPlanItem(
                title="Haseen",
                artist="Talwinder",
                url="https://example.com/0",
                suggested_start=0,
                suggested_end=30,
            )
        ],
    )
    monkeypatch.setattr(ai_main, "_download_sources", lambda song_plan, temp_dir: [timed_track])
    monkeypatch.setattr(
        ai_main,
        "_plan_mix_intent",
        lambda prompt, tracks: ai_main._MixIntentPlan(
            strategy="creative_mix",
            use_timestamped_lyrics=False,
            target_segment_duration_seconds=24,
            global_crossfade_seconds=1.2,
            transition_crossfade_seconds=[],
            track_windows=[],
            reason="test",
        ),
    )
    monkeypatch.setattr(ai_main, "_render_creative_mix_segments", lambda prompt, tracks, split_dir, mix_plan: ["0.mp3"])
    monkeypatch.setattr(ai_main, "_resolve_mix_crossfade_duration", lambda mix_plan, split_files: 1200)
    monkeypatch.setattr(
        ai_main,
        "merge_audio",
        lambda split_files, crossfade_duration, output_dir: "timed-flow-output.mp3",
    )
    monkeypatch.setattr(
        ai_main,
        "_review_engineered_mix_output",
        lambda merged_file_path, split_files, mix_plan, track_count: ai_main._MixReviewResult(
            approved=True,
            reasons=[],
            duration_seconds=120.0,
            minimum_required_seconds=30.0,
            segment_count=len(split_files),
        ),
    )

    output = ai_main._generate_ai_intelligent("prompt", workspace)
    assert output == "timed-flow-output.mp3"


def test_timestamped_lyrics_sequence_can_require_llm_plan(monkeypatch):
    tracks = [
        _build_track(0, "Haseen", "Talwinder"),
        _build_track(1, "Sahiba", "Aditya Rikhari"),
    ]
    tracks[0].plan.url = "https://youtu.be/haseen123"
    tracks[1].plan.url = "https://youtu.be/sahiba123"

    prompt = (
        "haseen - talwinder, sahiba - aditya rikhari\n"
        "mixing way:\n"
        "Tere ishq da jaam haseen ae\n"
        "Sahiba samandar meri aankhon me reh gaye\n"
    )

    monkeypatch.setenv("AI_ENABLE_TIMESTAMPED_LYRICS", "true")
    monkeypatch.setenv("AI_REQUIRE_LLM_TIMESTAMPED_PLAN", "true")
    monkeypatch.setattr(ai_main, "_fetch_lyrics_text", lambda artist, title, base_url, timeout_seconds: "")
    monkeypatch.setattr(
        ai_main,
        "_fetch_timestamped_lyrics_from_lrclib",
        lambda artist, title, api_base_url, timeout_seconds: [
            ai_main._TimestampedLyricLine(
                text=f"{title} line",
                start_seconds=10.0,
                end_seconds=14.0,
                confidence=0.9,
                source="lrc",
            )
        ],
    )
    monkeypatch.setattr(ai_main, "generate_with_instruction", lambda prompt, system_instruction: "not-json")

    try:
        ai_main._build_timestamped_lyrics_track_sequence(tracks, prompt)
        assert False, "Expected RuntimeError when AI_REQUIRE_LLM_TIMESTAMPED_PLAN=true and LLM output is invalid"
    except RuntimeError as exc:
        assert "AI_REQUIRE_LLM_TIMESTAMPED_PLAN" in str(exc)


def test_group_planned_segments_by_track_switch_merges_runs():
    planned = [
        ai_main._PlannedTimedSegment(script_index=0, track_index=0, start_seconds=10.0, end_seconds=14.0, confidence=0.8),
        ai_main._PlannedTimedSegment(script_index=1, track_index=0, start_seconds=14.1, end_seconds=18.0, confidence=0.85),
        ai_main._PlannedTimedSegment(script_index=2, track_index=0, start_seconds=18.1, end_seconds=22.0, confidence=0.82),
        ai_main._PlannedTimedSegment(script_index=3, track_index=1, start_seconds=30.0, end_seconds=34.0, confidence=0.9),
        ai_main._PlannedTimedSegment(script_index=4, track_index=1, start_seconds=34.1, end_seconds=38.0, confidence=0.87),
        ai_main._PlannedTimedSegment(script_index=5, track_index=0, start_seconds=42.0, end_seconds=46.0, confidence=0.86),
    ]
    grouped = ai_main._group_planned_segments_by_track_switch(planned, min_run_lines=1)
    assert len(grouped) == 3
    assert grouped[0].track_index == 0
    assert grouped[1].track_index == 1
    assert grouped[2].track_index == 0


def test_group_planned_segments_by_track_switch_smooths_single_line_noise():
    planned = [
        ai_main._PlannedTimedSegment(script_index=0, track_index=0, start_seconds=10.0, end_seconds=14.0, confidence=0.8),
        ai_main._PlannedTimedSegment(script_index=1, track_index=1, start_seconds=15.0, end_seconds=19.0, confidence=0.7),
        ai_main._PlannedTimedSegment(script_index=2, track_index=0, start_seconds=20.0, end_seconds=24.0, confidence=0.82),
    ]
    grouped = ai_main._group_planned_segments_by_track_switch(planned, min_run_lines=2)
    assert len(grouped) == 1
    assert grouped[0].track_index == 0


def test_mix_intent_fallback_prefers_creative_for_non_lyrics_prompt(monkeypatch):
    tracks = [
        _build_track(0, "Mann Ki Lagan", "Rahat Fateh Ali Khan"),
        _build_track(1, "Channa Mereya", "Arijit Singh"),
    ]

    monkeypatch.setattr(
        ai_main,
        "generate_with_instruction",
        lambda prompt, system_instruction: (_ for _ in ()).throw(RuntimeError("planner unavailable")),
    )

    plan = ai_main._plan_mix_intent("Create a soulful mix of these songs", tracks)
    assert plan.strategy == "creative_mix"
    assert plan.use_timestamped_lyrics is False


def test_mix_intent_fallback_ignores_generic_lyrics_word_without_script(monkeypatch):
    tracks = [
        _build_track(0, "Song A", "Artist A"),
        _build_track(1, "Song B", "Artist B"),
    ]

    monkeypatch.setattr(
        ai_main,
        "generate_with_instruction",
        lambda prompt, system_instruction: (_ for _ in ()).throw(RuntimeError("planner unavailable")),
    )

    plan = ai_main._plan_mix_intent("Create a smooth mix from these lyrics videos", tracks)
    assert plan.strategy == "creative_mix"
    assert plan.use_timestamped_lyrics is False


def test_mix_intent_fallback_keeps_creative_even_for_lyrics_wording(monkeypatch):
    tracks = [
        _build_track(0, "Haseen", "Talwinder"),
        _build_track(1, "Sahiba", "Aditya Rikhari"),
    ]

    monkeypatch.setattr(
        ai_main,
        "generate_with_instruction",
        lambda prompt, system_instruction: (_ for _ in ()).throw(RuntimeError("planner unavailable")),
    )

    plan = ai_main._plan_mix_intent("Use lyrics line by line to mix these songs", tracks)
    assert plan.strategy == "creative_mix"
    assert plan.use_timestamped_lyrics is False


def test_mix_intent_parses_transition_and_track_window_directives(monkeypatch):
    tracks = [
        _build_track(0, "Song A", "Artist A"),
        _build_track(1, "Song B", "Artist B"),
        _build_track(2, "Song C", "Artist C"),
    ]

    monkeypatch.setattr(
        ai_main,
        "generate_with_instruction",
        lambda prompt, system_instruction: (
            '{"strategy":"creative_mix","use_timestamped_lyrics":false,'
            '"target_segment_duration_seconds":44,'
            '"transition_crossfade_seconds":[2,3],'
            '"track_windows":[{"track_index":1,"start_seconds":20,"end_seconds":48},'
            '{"track_index":2,"start_seconds":30}]}'
        ),
    )

    plan = ai_main._plan_mix_intent("mix with 2s then 3s fade", tracks)
    assert plan.strategy == "creative_mix"
    assert plan.transition_crossfade_seconds == [2.0, 3.0]
    assert plan.target_segment_duration_seconds == 44
    assert len(plan.track_windows) == 2
    assert plan.track_windows[0].track_index == 0
    assert plan.track_windows[1].track_index == 1
    assert plan.track_windows[0].start_seconds == 20.0
    assert plan.track_windows[0].end_seconds == 48.0


def test_mix_intent_overrides_llm_lyrics_strategy_without_user_script(monkeypatch):
    tracks = [
        _build_track(0, "Mann Ki Lagan", "Rahat Fateh Ali Khan"),
        _build_track(1, "Channa Mereya", "Arijit Singh"),
    ]

    monkeypatch.setattr(
        ai_main,
        "generate_with_instruction",
        lambda prompt, system_instruction: (
            '{"strategy":"lyrics_scripted","use_timestamped_lyrics":true,'
            '"target_segment_duration_seconds":24,"reason":"llm_misclassified"}'
        ),
    )

    plan = ai_main._plan_mix_intent("Create a soulful mix of all these three songs", tracks)
    assert plan.strategy == "creative_mix"
    assert plan.use_timestamped_lyrics is False


def test_mix_intent_ignores_llm_lyrics_strategy_with_explicit_script(monkeypatch):
    tracks = [
        _build_track(0, "Haseen", "Talwinder"),
        _build_track(1, "Sahiba", "Aditya Rikhari"),
    ]

    monkeypatch.setattr(
        ai_main,
        "generate_with_instruction",
        lambda prompt, system_instruction: (
            '{"strategy":"lyrics_scripted","use_timestamped_lyrics":true,'
            '"target_segment_duration_seconds":26,"reason":"scripted_prompt"}'
        ),
    )

    prompt = (
        "haseen - talwinder, sahiba - aditya rikhari\n"
        "mixing way:\n"
        "Tere ishq da jaam haseen ae\n"
        "Sahiba samandar meri aankhon me reh gaye\n"
    )
    plan = ai_main._plan_mix_intent(prompt, tracks)
    assert plan.strategy == "creative_mix"
    assert plan.use_timestamped_lyrics is False


def test_generate_ai_intelligent_uses_creative_path_when_planner_disables_lyrics(monkeypatch, tmp_path):
    workspace = ai_main._prepare_workspace(str(tmp_path))
    base_tracks = [_build_track(0, "Song A", "Artist A"), _build_track(1, "Song B", "Artist B")]

    monkeypatch.setattr(
        ai_main,
        "_fetch_song_plan",
        lambda prompt, json_path: [
            ai_main._SongPlanItem(
                title="Song A",
                artist="Artist A",
                url="https://example.com/0",
                suggested_start=0,
                suggested_end=30,
            ),
            ai_main._SongPlanItem(
                title="Song B",
                artist="Artist B",
                url="https://example.com/1",
                suggested_start=0,
                suggested_end=30,
            ),
        ],
    )
    monkeypatch.setattr(ai_main, "_download_sources", lambda song_plan, temp_dir: base_tracks)
    monkeypatch.setattr(
        ai_main,
        "_plan_mix_intent",
        lambda prompt, tracks: ai_main._MixIntentPlan(
            strategy="creative_mix",
            use_timestamped_lyrics=False,
            target_segment_duration_seconds=38,
            global_crossfade_seconds=None,
            transition_crossfade_seconds=[2.0],
            track_windows=[],
            reason="creative",
        ),
    )
    monkeypatch.setattr(
        ai_main,
        "_build_timestamped_lyrics_track_sequence",
        lambda tracks, prompt: (_ for _ in ()).throw(AssertionError("timed lyrics path should not run")),
    )
    monkeypatch.setattr(
        ai_main,
        "_render_creative_mix_segments",
        lambda prompt, track_sources, split_dir, mix_plan: ["0.mp3", "1.mp3"],
    )
    monkeypatch.setattr(ai_main, "_resolve_mix_crossfade_duration", lambda mix_plan, split_files: [2000])

    observed = {"crossfade": None}

    def _fake_merge(split_files, crossfade_duration, output_dir):
        observed["crossfade"] = crossfade_duration
        return "creative-flow-output.mp3"

    monkeypatch.setattr(ai_main, "merge_audio", _fake_merge)
    monkeypatch.setattr(
        ai_main,
        "_review_engineered_mix_output",
        lambda merged_file_path, split_files, mix_plan, track_count: ai_main._MixReviewResult(
            approved=True,
            reasons=[],
            duration_seconds=180.0,
            minimum_required_seconds=30.0,
            segment_count=len(split_files),
        ),
    )

    output = ai_main._generate_ai_intelligent("party mix", workspace)
    assert output == "creative-flow-output.mp3"
    assert observed["crossfade"] == [2000]


def test_generate_ai_intelligent_retries_when_review_rejects(monkeypatch, tmp_path):
    workspace = ai_main._prepare_workspace(str(tmp_path))
    base_tracks = [_build_track(0, "Song A", "Artist A"), _build_track(1, "Song B", "Artist B")]

    monkeypatch.setattr(
        ai_main,
        "_fetch_song_plan",
        lambda prompt, json_path: [
            ai_main._SongPlanItem(
                title="Song A",
                artist="Artist A",
                url="https://example.com/0",
                suggested_start=0,
                suggested_end=30,
            ),
            ai_main._SongPlanItem(
                title="Song B",
                artist="Artist B",
                url="https://example.com/1",
                suggested_start=0,
                suggested_end=30,
            ),
        ],
    )
    monkeypatch.setattr(ai_main, "_download_sources", lambda song_plan, temp_dir: base_tracks)
    monkeypatch.setattr(
        ai_main,
        "_plan_mix_intent",
        lambda prompt, tracks: ai_main._MixIntentPlan(
            strategy="creative_mix",
            use_timestamped_lyrics=False,
            target_segment_duration_seconds=30,
            global_crossfade_seconds=1.2,
            transition_crossfade_seconds=[],
            track_windows=[],
            reason="initial",
            target_total_duration_seconds=300,
        ),
    )

    merge_calls = {"count": 0}
    monkeypatch.setattr(
        ai_main,
        "_audio_engineer_render_and_merge",
        lambda prompt, track_sources, mix_plan, workspace: (
            f"mix-{(merge_calls.__setitem__('count', merge_calls['count'] + 1) or merge_calls['count'])}.mp3",
            ["0.mp3", "1.mp3"],
            1200,
        ),
    )

    review_calls = {"count": 0}

    def _fake_review(merged_file_path, split_files, mix_plan, track_count):
        review_calls["count"] += 1
        if review_calls["count"] == 1:
            return ai_main._MixReviewResult(
                approved=False,
                reasons=["too short"],
                duration_seconds=90.0,
                minimum_required_seconds=160.0,
                segment_count=2,
            )
        return ai_main._MixReviewResult(
            approved=True,
            reasons=[],
            duration_seconds=220.0,
            minimum_required_seconds=160.0,
            segment_count=2,
        )

    monkeypatch.setattr(ai_main, "_review_engineered_mix_output", _fake_review)
    monkeypatch.setenv("AI_ENABLE_ENGINEER_AUTO_RETRY", "true")

    output = ai_main._generate_ai_intelligent("make it long", workspace)
    assert output == "mix-2.mp3"
    assert merge_calls["count"] == 2


def test_extract_explicit_song_list_from_using_clause():
    prompt = (
        "Create a soulful Hindi Sufi mashup using Kun Faya Kun, Agar Tum Saath Ho, "
        "and Phir Le Aaya Dil with smooth long transitions."
    )
    songs = ai_main._extract_explicit_song_list(prompt)
    assert songs[:3] == [
        ("Kun Faya Kun", ""),
        ("Agar Tum Saath Ho", ""),
        ("Phir Le Aaya Dil", ""),
    ]


def test_extract_explicit_song_list_ignores_generic_artist_count_prompt():
    songs = ai_main._extract_explicit_song_list("create a mix of 5 honey singh songs")
    assert songs == []


def test_extract_explicit_song_list_ignores_instructional_repeat_phrase():
    songs = ai_main._extract_explicit_song_list(
        "add 15 transitions here, of these songs, i want dope shope 4 times"
    )
    assert songs == []


def test_extract_explicit_song_list_ignores_order_instruction_phrase():
    songs = ai_main._extract_explicit_song_list(
        "I want dope shope at start, then blue eyes and then angreji beat, same order in ending also. total 15 segments"
    )
    assert songs == []


def test_default_mix_intent_plan_respects_total_duration_and_long_transitions():
    prompt = "Create a 10 minute mix with long long transitions to help me fall asleep"
    plan = ai_main._default_mix_intent_plan(prompt, track_count=3)
    assert plan.strategy == "creative_mix"
    assert plan.target_total_duration_seconds == 600
    assert plan.target_segment_duration_seconds >= 50
    assert plan.global_crossfade_seconds is not None
    assert plan.global_crossfade_seconds >= 3.0


def test_build_candidate_sequence_extends_for_target_total():
    tracks = [
        _build_track(0, "Song A", "Artist A"),
        _build_track(1, "Song B", "Artist B"),
    ]
    candidates_by_track = {
        0: [
            ai_main._SegmentCandidate(
                candidate_id="t0c0",
                track_index=0,
                start_ms=0,
                end_ms=45_000,
                energy_db=-12.0,
                drop_strength=0.5,
                transition_quality=2.0,
            ),
            ai_main._SegmentCandidate(
                candidate_id="t0c1",
                track_index=0,
                start_ms=10_000,
                end_ms=55_000,
                energy_db=-11.5,
                drop_strength=0.6,
                transition_quality=2.2,
            ),
        ],
        1: [
            ai_main._SegmentCandidate(
                candidate_id="t1c0",
                track_index=1,
                start_ms=0,
                end_ms=48_000,
                energy_db=-12.1,
                drop_strength=0.4,
                transition_quality=2.1,
            ),
            ai_main._SegmentCandidate(
                candidate_id="t1c1",
                track_index=1,
                start_ms=8_000,
                end_ms=56_000,
                energy_db=-11.8,
                drop_strength=0.5,
                transition_quality=2.3,
            ),
        ],
    }
    selected = {
        0: candidates_by_track[0][0],
        1: candidates_by_track[1][0],
    }
    plan = ai_main._MixIntentPlan(
        strategy="creative_mix",
        use_timestamped_lyrics=False,
        target_segment_duration_seconds=50,
        global_crossfade_seconds=3.0,
        transition_crossfade_seconds=[],
        track_windows=[],
        target_total_duration_seconds=480,
        reason="test",
    )
    sequence = ai_main._build_candidate_sequence_for_target_duration(
        tracks,
        candidates_by_track,
        selected,
        plan,
    )
    assert len(sequence) > len(tracks)
    estimated_ms = ai_main._effective_sequence_duration_ms(sequence, plan)
    assert estimated_ms >= 440_000
