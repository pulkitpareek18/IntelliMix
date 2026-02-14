from __future__ import annotations

import pytest

import mix_chat_queue
from app import MixChatPlanDraft, MixChatRun, MixChatVersion, create_app, db


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv("MIX_CHAT_INLINE_FALLBACK", "false")
    test_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": "test-jwt-secret-123456789012345678901234567890",
            "FLASK_SECRET_KEY": "test-flask-secret-123456789012345678901234567890",
            "STORAGE_ROOT": "storage-test",
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
            "name": "Chat User",
            "email": email,
            "password": "strong-password",
        },
    )
    assert response.status_code == 201
    return response.get_json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_mix_memory_endpoint_bootstraps_profile(client):
    user = _register(client, "chat-memory@example.com")
    headers = _auth(user["access_token"])

    response = client.get("/api/v1/mix-memory", headers=headers)
    assert response.status_code == 200
    memory = response.get_json()["memory"]
    assert memory["user_id"]
    assert isinstance(memory.get("profile_json"), dict)
    assert isinstance(memory.get("feedback_json"), dict)
    assert isinstance(memory.get("use_case_profiles_json"), dict)
    assert isinstance(memory.get("template_pack_json"), dict)
    assert isinstance(memory.get("quality_json"), dict)


def test_mix_chat_thread_crud(client):
    user = _register(client, "chat-crud@example.com")
    headers = _auth(user["access_token"])

    create_response = client.post("/api/v1/mix-chats", headers=headers, json={"title": "My First Chat"})
    assert create_response.status_code == 201
    thread = create_response.get_json()["thread"]
    assert thread["title"] == "My First Chat"

    list_response = client.get("/api/v1/mix-chats?limit=20&page=1", headers=headers)
    assert list_response.status_code == 200
    items = list_response.get_json()["items"]
    assert any(item["id"] == thread["id"] for item in items)

    patch_response = client.patch(
        f"/api/v1/mix-chats/{thread['id']}",
        headers=headers,
        json={"title": "Renamed Chat"},
    )
    assert patch_response.status_code == 200
    assert patch_response.get_json()["thread"]["title"] == "Renamed Chat"

    archive_response = client.delete(f"/api/v1/mix-chats/{thread['id']}", headers=headers)
    assert archive_response.status_code == 200
    assert archive_response.get_json()["thread"]["archived"] is True

    active_list_response = client.get("/api/v1/mix-chats?archived=false", headers=headers)
    assert active_list_response.status_code == 200
    assert all(item["id"] != thread["id"] for item in active_list_response.get_json()["items"])

    archived_list_response = client.get("/api/v1/mix-chats?archived=true", headers=headers)
    assert archived_list_response.status_code == 200
    assert any(item["id"] == thread["id"] for item in archived_list_response.get_json()["items"])


def test_mix_chat_message_and_run_scoping(client, monkeypatch):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)

    first = _register(client, "chat-owner@example.com")
    second = _register(client, "chat-other@example.com")
    first_headers = _auth(first["access_token"])
    second_headers = _auth(second["access_token"])

    thread_response = client.post("/api/v1/mix-chats", headers=first_headers, json={"title": "Owner Chat"})
    thread_id = thread_response.get_json()["thread"]["id"]

    message_response = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=first_headers,
        json={"content": "Create a romantic Hindi mix", "mode": "refine_last"},
    )
    assert message_response.status_code == 202
    payload = message_response.get_json()
    run_id = payload["run"]["id"]

    own_messages = client.get(f"/api/v1/mix-chats/{thread_id}/messages?limit=20", headers=first_headers)
    assert own_messages.status_code == 200
    assert len(own_messages.get_json()["items"]) == 2

    own_run = client.get(f"/api/v1/mix-chat-runs/{run_id}", headers=first_headers)
    assert own_run.status_code == 200
    own_run_payload = own_run.get_json()["run"]
    assert own_run_payload["status"] == "queued"
    assert "progress_percent" in own_run_payload
    assert "progress_label" in own_run_payload
    assert "progress_detail" in own_run_payload

    forbidden_messages = client.get(f"/api/v1/mix-chats/{thread_id}/messages", headers=second_headers)
    assert forbidden_messages.status_code == 404

    forbidden_run = client.get(f"/api/v1/mix-chat-runs/{run_id}", headers=second_headers)
    assert forbidden_run.status_code == 404


def test_mix_chat_run_events_stream_returns_sse_payload(client, monkeypatch):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)

    user = _register(client, "chat-events@example.com")
    headers = _auth(user["access_token"])

    thread_response = client.post("/api/v1/mix-chats", headers=headers, json={"title": "Events Chat"})
    assert thread_response.status_code == 201
    thread_id = thread_response.get_json()["thread"]["id"]

    message_response = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={"content": "Create a romantic Hindi mix", "mode": "refine_last"},
    )
    assert message_response.status_code == 202
    run_id = message_response.get_json()["run"]["id"]

    stream_response = client.get(
        f"/api/v1/mix-chat-runs/{run_id}/events?token={user['access_token']}",
        buffered=False,
    )
    assert stream_response.status_code == 200
    assert stream_response.mimetype == "text/event-stream"

    first_chunk = next(stream_response.response).decode("utf-8")
    assert "event: run_update" in first_chunk
    assert run_id in first_chunk
    assert "progress_percent" in first_chunk
    stream_response.close()


def test_mix_chat_timeline_edit_run_endpoint(client, app, monkeypatch):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)

    user = _register(client, "chat-edit@example.com")
    headers = _auth(user["access_token"])

    thread_response = client.post("/api/v1/mix-chats", headers=headers, json={"title": "Edit Chat"})
    assert thread_response.status_code == 201
    thread_id = thread_response.get_json()["thread"]["id"]

    with app.app_context():
        version = MixChatVersion(
            thread_id=thread_id,
            source_user_message_id=None,
            assistant_message_id=None,
            parent_version_id=None,
            mix_session_id="session-edit-1",
            proposal_json={
                "tracks": [{"id": "0", "track_index": 0, "title": "Track 1"}],
                "proposal": {
                    "segments": [
                        {
                            "id": "seg_1",
                            "track_index": 0,
                            "start_ms": 1000,
                            "end_ms": 6000,
                            "crossfade_after_seconds": 1.5,
                            "effects": {"reverb_amount": 0.1, "delay_ms": 120, "delay_feedback": 0.2},
                            "eq": {"low_gain_db": 0, "mid_gain_db": 0, "high_gain_db": 0},
                        }
                    ]
                },
            },
            final_output_json={},
            state_snapshot_json={},
        )
        db.session.add(version)
        db.session.commit()
        version_id = version.id

    response = client.post(
        f"/api/v1/mix-chats/{thread_id}/versions/{version_id}/edit-runs",
        headers=headers,
        json={
            "segments": [
                {
                    "id": "seg_1",
                    "track_index": 0,
                    "start_ms": 1500,
                    "end_ms": 6500,
                    "crossfade_after_seconds": 2.0,
                    "effects": {"reverb_amount": 0.2, "delay_ms": 180, "delay_feedback": 0.22},
                    "eq": {"low_gain_db": 0, "mid_gain_db": 0, "high_gain_db": 0},
                }
            ],
            "note": "tighten intro",
            "editor_metadata": {"changed_segment_ids": ["seg_1"]},
        },
    )
    assert response.status_code == 202
    payload = response.get_json()
    assert payload["run"]["run_kind"] == "timeline_edit"
    assert payload["run"]["parent_version_id"] == version_id
    assert payload["user_message"]["content_json"]["kind"] == "timeline_edit_request"


def test_mix_chat_timeline_edit_run_validation_and_scoping(client, app, monkeypatch):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)

    owner = _register(client, "chat-edit-owner@example.com")
    other = _register(client, "chat-edit-other@example.com")
    owner_headers = _auth(owner["access_token"])
    other_headers = _auth(other["access_token"])

    thread_response = client.post("/api/v1/mix-chats", headers=owner_headers, json={"title": "Owner Edit Chat"})
    thread_id = thread_response.get_json()["thread"]["id"]

    with app.app_context():
        version = MixChatVersion(
            thread_id=thread_id,
            source_user_message_id=None,
            assistant_message_id=None,
            parent_version_id=None,
            mix_session_id="session-edit-2",
            proposal_json={"proposal": {"segments": []}},
            final_output_json={},
            state_snapshot_json={},
        )
        db.session.add(version)
        db.session.commit()
        version_id = version.id

    forbidden = client.post(
        f"/api/v1/mix-chats/{thread_id}/versions/{version_id}/edit-runs",
        headers=other_headers,
        json={
            "segments": [
                {"id": "seg_1", "track_index": 0, "start_ms": 0, "end_ms": 3000, "crossfade_after_seconds": 1.0}
            ]
        },
    )
    assert forbidden.status_code == 404

    invalid = client.post(
        f"/api/v1/mix-chats/{thread_id}/versions/{version_id}/edit-runs",
        headers=owner_headers,
        json={
            "segments": [
                {"id": "seg_1", "track_index": 0, "start_ms": 5000, "end_ms": 5000, "crossfade_after_seconds": 1.0}
            ]
        },
    )
    assert invalid.status_code == 400


def test_mix_chat_message_timeline_attachment_only(client, app, monkeypatch):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)

    user = _register(client, "chat-attach@example.com")
    headers = _auth(user["access_token"])

    thread_response = client.post("/api/v1/mix-chats", headers=headers, json={"title": "Attachment Chat"})
    assert thread_response.status_code == 201
    thread_id = thread_response.get_json()["thread"]["id"]

    with app.app_context():
        version = MixChatVersion(
            thread_id=thread_id,
            source_user_message_id=None,
            assistant_message_id=None,
            parent_version_id=None,
            mix_session_id="session-attach-1",
            proposal_json={
                "tracks": [{"id": "0", "track_index": 0, "title": "Track 1"}],
                "proposal": {"segments": []},
            },
            final_output_json={},
            state_snapshot_json={},
        )
        db.session.add(version)
        db.session.commit()
        version_id = version.id

    response = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={
            "content": "",
            "attachments": [
                {
                    "type": "timeline_snapshot",
                    "source_version_id": version_id,
                    "segments": [
                        {
                            "id": "seg_1",
                            "segment_name": "Intro",
                            "track_index": 0,
                            "track_id": "0",
                            "track_title": "Track 1",
                            "start_ms": 1000,
                            "end_ms": 6000,
                            "crossfade_after_seconds": 1.5,
                            "effects": {"reverb_amount": 0.1, "delay_ms": 120, "delay_feedback": 0.2},
                            "eq": {"low_gain_db": 0, "mid_gain_db": 0, "high_gain_db": 0},
                        }
                    ],
                    "editor_metadata": {"changed_segment_ids": ["seg_1"]},
                }
            ],
        },
    )
    assert response.status_code == 202
    payload = response.get_json()
    assert payload["run"]["run_kind"] == "timeline_attachment"
    assert payload["run"]["parent_version_id"] == version_id
    assert payload["user_message"]["content_json"]["kind"] == "timeline_attachment_request"


def test_mix_chat_message_timeline_attachment_validation(client, app, monkeypatch):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)

    user = _register(client, "chat-attach-validation@example.com")
    headers = _auth(user["access_token"])

    thread_response = client.post("/api/v1/mix-chats", headers=headers, json={"title": "Attachment Validation Chat"})
    assert thread_response.status_code == 201
    thread_id = thread_response.get_json()["thread"]["id"]

    with app.app_context():
        version = MixChatVersion(
            thread_id=thread_id,
            source_user_message_id=None,
            assistant_message_id=None,
            parent_version_id=None,
            mix_session_id="session-attach-2",
            proposal_json={"tracks": [], "proposal": {"segments": []}},
            final_output_json={},
            state_snapshot_json={},
        )
        db.session.add(version)
        db.session.commit()
        version_id = version.id

    bad_multiple = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={
            "attachments": [
                {"type": "timeline_snapshot", "source_version_id": version_id, "segments": []},
                {"type": "timeline_snapshot", "source_version_id": version_id, "segments": []},
            ]
        },
    )
    assert bad_multiple.status_code == 400

    bad_source = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={
            "attachments": [
                {
                    "type": "timeline_snapshot",
                    "source_version_id": "missing-version",
                    "segments": [
                        {
                            "id": "seg_1",
                            "track_index": 0,
                            "start_ms": 1000,
                            "end_ms": 3000,
                            "crossfade_after_seconds": 1.0,
                        }
                    ],
                }
            ]
        },
    )
    assert bad_source.status_code == 404


def test_first_prompt_creates_guided_plan_draft_and_intake_run(client, app, monkeypatch):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)

    user = _register(client, "chat-guided-intake@example.com")
    headers = _auth(user["access_token"])

    thread_response = client.post("/api/v1/mix-chats", headers=headers, json={"title": "Guided Chat"})
    assert thread_response.status_code == 201
    thread_id = thread_response.get_json()["thread"]["id"]

    message_response = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={"content": "Create a nostalgic 90s Hindi party mix"},
    )
    assert message_response.status_code == 202
    payload = message_response.get_json()
    assert payload["run"]["run_kind"] == "planning_intake"

    with app.app_context():
        draft = (
            MixChatPlanDraft.query.filter_by(thread_id=thread_id)
            .order_by(MixChatPlanDraft.created_at.desc())
            .first()
        )
        assert draft is not None
        assert draft.status == "collecting"
        draft_id = draft.id

    draft_response = client.get(f"/api/v1/mix-chats/{thread_id}/plan-drafts/{draft_id}", headers=headers)
    assert draft_response.status_code == 200
    assert draft_response.get_json()["draft"]["id"] == draft_id


def test_plain_content_auto_routes_to_active_draft_revision(client, app, monkeypatch):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)

    user = _register(client, "chat-active-draft-route@example.com")
    headers = _auth(user["access_token"])

    thread_response = client.post("/api/v1/mix-chats", headers=headers, json={"title": "Active Draft Route"})
    assert thread_response.status_code == 201
    thread_id = thread_response.get_json()["thread"]["id"]

    kickoff = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={"content": "create a mashup of 5 honey singh songs"},
    )
    assert kickoff.status_code == 202

    with app.app_context():
        active_draft = (
            MixChatPlanDraft.query.filter_by(thread_id=thread_id)
            .order_by(MixChatPlanDraft.created_at.desc())
            .first()
        )
        assert active_draft is not None
        draft_id = active_draft.id

    revise = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={"content": "add two more songs and keep party vibe"},
    )
    assert revise.status_code == 202
    payload = revise.get_json()
    assert payload["run"]["run_kind"] == "planning_revision"
    assert payload["user_message"]["content_json"]["kind"] == "planning_freeform_revision"
    assert payload["user_message"]["content_json"]["draft_id"] == draft_id

    with app.app_context():
        run = MixChatRun.query.filter_by(id=payload["run"]["id"]).first()
        assert run is not None
        assert run.input_summary_json["draft_id"] == draft_id
        assert run.input_summary_json["action"] == "freeform_revision"


def test_plain_content_with_new_draft_target_creates_new_intake(client, app, monkeypatch):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)

    user = _register(client, "chat-new-draft-target@example.com")
    headers = _auth(user["access_token"])

    thread_response = client.post("/api/v1/mix-chats", headers=headers, json={"title": "New Draft Target"})
    assert thread_response.status_code == 201
    thread_id = thread_response.get_json()["thread"]["id"]

    kickoff = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={"content": "create a mashup of 5 honey singh songs"},
    )
    assert kickoff.status_code == 202

    with app.app_context():
        first_draft = (
            MixChatPlanDraft.query.filter_by(thread_id=thread_id)
            .order_by(MixChatPlanDraft.created_at.desc())
            .first()
        )
        assert first_draft is not None
        first_draft_id = first_draft.id

    new_draft_response = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={
            "content": "start a fresh draft for an atif aslam mellow mix",
            "planning_target": "new_draft",
        },
    )
    assert new_draft_response.status_code == 202
    payload = new_draft_response.get_json()
    assert payload["run"]["run_kind"] == "planning_intake"

    with app.app_context():
        latest_draft = (
            MixChatPlanDraft.query.filter_by(thread_id=thread_id)
            .order_by(MixChatPlanDraft.created_at.desc())
            .first()
        )
        first_draft = MixChatPlanDraft.query.filter_by(id=first_draft_id).first()
        assert latest_draft is not None
        assert latest_draft.id != first_draft_id
        assert first_draft is not None
        assert first_draft.status == "superseded"


def test_guided_plan_answer_and_approve_actions(client, app, monkeypatch):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)

    user = _register(client, "chat-guided-actions@example.com")
    headers = _auth(user["access_token"])

    thread_response = client.post("/api/v1/mix-chats", headers=headers, json={"title": "Guided Actions"})
    assert thread_response.status_code == 201
    thread_id = thread_response.get_json()["thread"]["id"]

    kickoff = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={"content": "Mix 3 songs for a wedding entry"},
    )
    assert kickoff.status_code == 202

    with app.app_context():
        draft = (
            MixChatPlanDraft.query.filter_by(thread_id=thread_id)
            .order_by(MixChatPlanDraft.created_at.desc())
            .first()
        )
        assert draft is not None
        draft_id = draft.id

    answers_response = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={
            "planning_response": {
                "draft_id": draft_id,
                "answers": [
                    {"question_id": "songs_set", "selected_option_id": "custom_list", "other_text": "Kun Faya Kun, Channa Mereya"},
                    {"question_id": "energy_curve", "selected_option_id": "slow_build"},
                ],
            }
        },
    )
    assert answers_response.status_code == 202
    assert answers_response.get_json()["run"]["run_kind"] == "planning_revision"
    assert answers_response.get_json()["user_message"]["content_json"]["kind"] == "planning_answers"

    revise_response = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={
            "planning_action": {
                "draft_id": draft_id,
                "action": "revise_plan",
                "revision_prompt": "Keep it mellow and reduce high-energy peaks.",
            }
        },
    )
    assert revise_response.status_code == 202
    revise_payload = revise_response.get_json()
    assert revise_payload["run"]["run_kind"] == "planning_revision"
    assert revise_payload["user_message"]["content_json"]["kind"] == "planning_revision_request"
    assert revise_payload["user_message"]["content_json"]["revision_prompt"] == "Keep it mellow and reduce high-energy peaks."
    with app.app_context():
        run = MixChatRun.query.filter_by(id=revise_payload["run"]["id"]).first()
        assert run is not None
        assert run.input_summary_json["revision_prompt"] == "Keep it mellow and reduce high-energy peaks."

    approve_before_ready = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={"planning_action": {"draft_id": draft_id, "action": "approve_plan"}},
    )
    assert approve_before_ready.status_code == 409

    with app.app_context():
        draft = MixChatPlanDraft.query.filter_by(id=draft_id, thread_id=thread_id).first()
        assert draft is not None
        draft.status = "draft_ready"
        db.session.commit()

    approve_response = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={"planning_action": {"draft_id": draft_id, "action": "approve_plan"}},
    )
    assert approve_response.status_code == 202
    assert approve_response.get_json()["run"]["run_kind"] == "planning_execute"
    assert approve_response.get_json()["user_message"]["content_json"]["kind"] == "planning_approval"


def test_timeline_resolution_requires_attachment(client, monkeypatch):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)

    user = _register(client, "chat-resolution-validation@example.com")
    headers = _auth(user["access_token"])
    thread_response = client.post("/api/v1/mix-chats", headers=headers, json={"title": "Resolution Validation"})
    assert thread_response.status_code == 201
    thread_id = thread_response.get_json()["thread"]["id"]

    response = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={
            "content": "make it smoother",
            "timeline_resolution": "replan_with_prompt",
        },
    )
    assert response.status_code == 400


def test_timeline_resolution_is_stored_for_attachment_runs(client, app, monkeypatch):
    monkeypatch.setattr(mix_chat_queue, "enqueue_run", lambda run_id: True)

    user = _register(client, "chat-resolution-store@example.com")
    headers = _auth(user["access_token"])

    thread_response = client.post("/api/v1/mix-chats", headers=headers, json={"title": "Resolution Store"})
    assert thread_response.status_code == 201
    thread_id = thread_response.get_json()["thread"]["id"]

    with app.app_context():
        version = MixChatVersion(
            thread_id=thread_id,
            source_user_message_id=None,
            assistant_message_id=None,
            parent_version_id=None,
            mix_session_id="session-resolution-1",
            proposal_json={
                "tracks": [{"id": "0", "track_index": 0, "title": "Brown Rang", "artist": "Yo Yo Honey Singh"}],
                "proposal": {"segments": []},
            },
            final_output_json={},
            state_snapshot_json={},
        )
        db.session.add(version)
        db.session.commit()
        version_id = version.id

    response = client.post(
        f"/api/v1/mix-chats/{thread_id}/messages",
        headers=headers,
        json={
            "content": "add two songs: Party All Night and Sunny Sunny",
            "timeline_resolution": "replan_with_prompt",
            "attachments": [
                {
                    "type": "timeline_snapshot",
                    "source_version_id": version_id,
                    "segments": [
                        {
                            "id": "seg_1",
                            "track_index": 0,
                            "track_id": "0",
                            "track_title": "Brown Rang",
                            "segment_name": "Segment 1",
                            "start_ms": 1000,
                            "end_ms": 5000,
                            "crossfade_after_seconds": 1.0,
                        }
                    ],
                }
            ],
        },
    )
    assert response.status_code == 202
    payload = response.get_json()
    run_id = payload["run"]["id"]
    assert payload["user_message"]["content_json"]["timeline_resolution"] == "replan_with_prompt"

    with app.app_context():
        run = MixChatRun.query.filter_by(id=run_id).first()
        assert run is not None
        assert run.run_kind == "timeline_attachment"
        assert run.input_summary_json["timeline_resolution"] == "replan_with_prompt"
