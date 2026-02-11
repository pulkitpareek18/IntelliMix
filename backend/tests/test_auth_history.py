from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ai.ai import AIServiceError
from ai import ai_main
from app import GenerationJob, create_app, db


@pytest.fixture()
def app():
    test_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": "test-jwt-secret-123456789012345678901234567890",
            "FLASK_SECRET_KEY": "test-flask-secret-123456789012345678901234567890",
        }
    )

    with test_app.app_context():
        db.drop_all()
        db.create_all()

    yield test_app


@pytest.fixture()
def client(app):
    return app.test_client()


def register_user(client, email: str = "test@example.com"):
    return client.post(
        "/api/v1/auth/register",
        json={
            "name": "Test User",
            "email": email,
            "password": "strong-password",
        },
    )


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_register_login_and_me(client):
    register_response = register_user(client)
    assert register_response.status_code == 201

    register_payload = register_response.get_json()
    assert register_payload["user"]["email"] == "test@example.com"
    assert register_payload["access_token"]
    assert register_payload["refresh_token"]

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "strong-password"},
    )
    assert login_response.status_code == 200
    login_payload = login_response.get_json()

    me_response = client.get("/api/v1/auth/me", headers=auth_headers(login_payload["access_token"]))
    assert me_response.status_code == 200
    assert me_response.get_json()["user"]["email"] == "test@example.com"


def test_refresh_token_and_logout(client):
    register_response = register_user(client, email="refresh@example.com")
    payload = register_response.get_json()

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": payload["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    refreshed_access_token = refresh_response.get_json()["access_token"]

    logout_response = client.post(
        "/api/v1/auth/logout",
        headers=auth_headers(refreshed_access_token),
        json={"refresh_token": payload["refresh_token"]},
    )
    assert logout_response.status_code == 200

    me_after_logout = client.get("/api/v1/auth/me", headers=auth_headers(refreshed_access_token))
    assert me_after_logout.status_code == 401


def test_history_is_scoped_per_user(client, app):
    first_user = register_user(client, email="first@example.com").get_json()
    second_user = register_user(client, email="second@example.com").get_json()

    with app.app_context():
        db.session.add(
            GenerationJob(
                user_id=first_user["user"]["id"],
                generation_type="ai_parody",
                status="success",
                input_payload={"prompt": "first prompt"},
                output_url="http://localhost/files/a/output.mp3",
                created_at=datetime.now(timezone.utc),
            )
        )
        db.session.add(
            GenerationJob(
                user_id=second_user["user"]["id"],
                generation_type="video_download",
                status="success",
                input_payload={"url": "https://youtube.com/watch?v=123"},
                output_url="http://localhost/files/b/video.mp4",
                created_at=datetime.now(timezone.utc),
            )
        )
        db.session.commit()

    first_history = client.get(
        "/api/v1/history",
        headers=auth_headers(first_user["access_token"]),
    )
    assert first_history.status_code == 200
    first_items = first_history.get_json()["items"]
    assert len(first_items) == 1
    assert first_items[0]["input_payload"]["prompt"] == "first prompt"

    second_history = client.get(
        "/api/v1/history",
        headers=auth_headers(second_user["access_token"]),
    )
    assert second_history.status_code == 200
    second_items = second_history.get_json()["items"]
    assert len(second_items) == 1
    assert second_items[0]["generation_type"] == "video_download"


def test_generate_ai_maps_upstream_errors(client, app, monkeypatch):
    user_payload = register_user(client, email="ai-errors@example.com").get_json()

    def _raise_quota_error(prompt: str, session_dir: str | None = None):
        raise AIServiceError(
            "Gemini quota or rate limit exceeded for model 'gemini-2.0-flash'. Retry later or use a billed Gemini project.",
            status_code=429,
            error_code="AI_RATE_LIMITED",
            retry_after_seconds=42,
        )

    monkeypatch.setattr(ai_main, "generate_ai", _raise_quota_error)

    response = client.post(
        "/api/v1/generate-ai",
        headers=auth_headers(user_payload["access_token"]),
        json={"prompt": "create a short mix"},
    )

    assert response.status_code == 429
    payload = response.get_json()
    assert payload["code"] == "AI_RATE_LIMITED"
    assert payload["retry_after_seconds"] == 42
    assert payload["job_id"]

    with app.app_context():
        job = GenerationJob.query.filter_by(id=payload["job_id"]).first()
        assert job is not None
        assert job.status == "failed"
        assert "quota or rate limit exceeded" in job.error_message
