from __future__ import annotations

import os

import pytest

import mix_chat_queue
import mix_chat_runner
from app import MixChatMessage, MixChatRun, MixChatVersion, create_app, db


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv("MIX_CHAT_INLINE_FALLBACK", "false")
    test_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": "test-jwt-secret-123456789012345678901234567890",
            "FLASK_SECRET_KEY": "test-flask-secret-123456789012345678901234567890",
            "STORAGE_ROOT": "storage-test-runner",
        }
    )

    with test_app.app_context():
        db.drop_all()
        db.create_all()

    yield test_app


@pytest.fixture()
def client(app):
    return app.test_client()


def _register(client, email: str):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Runner User",
            "email": email,
            "password": "strong-password",
        },
    )
    assert response.status_code == 201
    return response.get_json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_parent_version(app, thread_id: str, mix_session_id: str = "session-parent-1") -> str:
    with app.app_context():
        version = MixChatVersion(
            thread_id=thread_id,
            source_user_message_id=None,
            assistant_message_id=None,
            parent_version_id=None,
            mix_session_id=mix_session_id,
            proposal_json={
                "tracks": [
                    {
                        "id": "0",
                        "track_index": 0,
                        "title": "Brown Rang",
                        "artist": "Yo Yo Honey Singh",
                    },
                    {
                        "id": "1",
                        "track_index": 1,
                        "title": "Dope Shope",
                        "artist": "Deep Money feat. Yo Yo Honey Singh",
                    },
                ],
                "proposal": {
                    "title": "Parent Mix",
                    "mixing_rationale": "Parent rationale",
                    "segments": [
                        {
                            "id": "seg_1",
                            "segment_name": "Segment 1",
                            "track_index": 0,
                            "track_id": "0",
                            "track_title": "Brown Rang",
                            "start_ms": 1000,
                            "end_ms": 7000,
                            "crossfade_after_seconds": 1.2,
                            "effects": {"reverb_amount": 0.1, "delay_ms": 120, "delay_feedback": 0.2},
                            "eq": {"low_gain_db": 0, "mid_gain_db": 0, "high_gain_db": 0},
                        }
                    ],
                },
            },
            final_output_json={},
            state_snapshot_json={"summary": "parent summary"},
        )
        db.session.add(version)
        db.session.commit()
        return version.id


def _create_attachment_payload(source_version_id: str) -> list[dict[str, object]]:
    return [
        {
            "type": "timeline_snapshot",
            "source_version_id": source_version_id,
            "segments": [
                {
                    "id": "seg_1",
                    "segment_name": "Segment 1",
                    "track_index": 0,
                    "track_id": "0",
                    "track_title": "Brown Rang",
                    "start_ms": 1000,
                    "end_ms": 7000,
                    "crossfade_after_seconds": 1.2,
                }
            ],
        }
    ]


def test_timeline_attachment_unspecified_structural_change_returns_clarification(
    client, app, monkeypatch
):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)
    monkeypatch.setattr(mix_chat_runner, "_APP", app)
    monkeypatch.setattr(mix_chat_runner, "_sanitize_timeline_segments", lambda _session_dir, raw_segments: raw_segments)
    monkeypatch.setenv("AI_TIMELINE_ALWAYS_ASK_FIRST", "true")

    user = _register(client, "runner-clarification@example.com")
    headers = _auth(user["access_token"])

    thread_response = client.post("/api/v1/mix-chats", headers=headers, json={"title": "Runner Clarification"})
    assert thread_response.status_code == 201
    thread_id = thread_response.get_json()["thread"]["id"]
    version_id = _create_parent_version(app, thread_id, mix_session_id="session-parent-clarify")

    response = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={
            "content": "add two songs party all night and sunny sunny",
            "attachments": _create_attachment_payload(version_id),
        },
    )
    assert response.status_code == 202
    run_id = response.get_json()["run"]["id"]

    mix_chat_runner.process_mix_chat_run(run_id)

    with app.app_context():
        run = MixChatRun.query.filter_by(id=run_id).first()
        assert run is not None
        assert run.status == "completed"
        assert run.version_id is None

        assistant_message = MixChatMessage.query.filter_by(id=run.assistant_message_id).first()
        assert assistant_message is not None
        assert assistant_message.content_json.get("kind") == "clarification_question"
        quick_actions = assistant_message.content_json.get("quick_actions", [])
        assert isinstance(quick_actions, list)
        assert len(quick_actions) == 3


def test_timeline_attachment_replan_with_prompt_creates_new_version(
    client, app, monkeypatch
):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)
    monkeypatch.setattr(mix_chat_runner, "_APP", app)
    monkeypatch.setattr(mix_chat_runner, "_sanitize_timeline_segments", lambda _session_dir, raw_segments: raw_segments)
    monkeypatch.setenv("AI_TIMELINE_ALWAYS_ASK_FIRST", "true")

    user = _register(client, "runner-replan@example.com")
    headers = _auth(user["access_token"])

    thread_response = client.post("/api/v1/mix-chats", headers=headers, json={"title": "Runner Replan"})
    assert thread_response.status_code == 201
    thread_id = thread_response.get_json()["thread"]["id"]
    version_id = _create_parent_version(app, thread_id, mix_session_id="session-parent-replan")

    from ai import mix_agent_flow

    def fake_create_mix_proposal(prompt: str, *, session_dir: str):
        assert "Party All Night" in prompt or "party all night" in prompt.lower()
        return {
            "requirements": {"summary": "replanned"},
            "tracks": [
                {"id": "0", "track_index": 0, "title": "Brown Rang", "artist": "Yo Yo Honey Singh", "preview_filename": "track_0.mp3"},
                {"id": "1", "track_index": 1, "title": "Party All Night", "artist": "Yo Yo Honey Singh", "preview_filename": "track_1.mp3"},
                {"id": "2", "track_index": 2, "title": "Sunny Sunny", "artist": "Yo Yo Honey Singh", "preview_filename": "track_2.mp3"},
            ],
            "proposal": {
                "title": "Replanned",
                "mixing_rationale": "Replanned with added songs",
                "segments": [
                    {
                        "id": "seg_1",
                        "segment_name": "Segment 1",
                        "track_index": 0,
                        "track_id": "0",
                        "track_title": "Brown Rang",
                        "start_ms": 1000,
                        "end_ms": 7000,
                        "crossfade_after_seconds": 1.2,
                        "effects": {"reverb_amount": 0.1, "delay_ms": 120, "delay_feedback": 0.2},
                        "eq": {"low_gain_db": 0, "mid_gain_db": 0, "high_gain_db": 0},
                    }
                ],
            },
            "client_questions": [],
        }

    def fake_finalize_mix_proposal(*, session_dir: str, proposal: dict[str, object]):
        return {
            "mp3_path": os.path.join(session_dir, "static", "output", "fake.mp3"),
            "wav_path": os.path.join(session_dir, "static", "output", "fake.wav"),
        }

    monkeypatch.setattr(mix_agent_flow, "create_mix_proposal", fake_create_mix_proposal)
    monkeypatch.setattr(mix_agent_flow, "finalize_mix_proposal", fake_finalize_mix_proposal)

    response = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={
            "content": "add two songs party all night and sunny sunny",
            "timeline_resolution": "replan_with_prompt",
            "attachments": _create_attachment_payload(version_id),
        },
    )
    assert response.status_code == 202
    run_id = response.get_json()["run"]["id"]

    mix_chat_runner.process_mix_chat_run(run_id)

    with app.app_context():
        run = MixChatRun.query.filter_by(id=run_id).first()
        assert run is not None
        assert run.status == "completed"
        assert run.version_id

        assistant_message = MixChatMessage.query.filter_by(id=run.assistant_message_id).first()
        assert assistant_message is not None
        assert assistant_message.content_json.get("kind") == "timeline_attachment_result"

        tracks = assistant_message.content_json.get("tracks", [])
        titles = {str(track.get("title", "")) for track in tracks if isinstance(track, dict)}
        assert "Party All Night" in titles
        assert "Sunny Sunny" in titles

        song_resolution = assistant_message.content_json.get("song_resolution", [])
        assert isinstance(song_resolution, list)
        assert len(song_resolution) >= 1
