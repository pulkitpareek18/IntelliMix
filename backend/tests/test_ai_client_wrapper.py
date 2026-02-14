from __future__ import annotations

from ai import ai as ai_module


class _FakeAPIError(ai_module.genai_errors.APIError):
    def __init__(self, status_code: int, message: str):
        Exception.__init__(self, message)
        self.status_code = status_code


def test_generate_with_instruction_falls_back_to_non_stream(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MAX_RETRIES", "0")

    class _FakeModels:
        @staticmethod
        def generate_content_stream(model, contents, config):
            raise RuntimeError("stream parser failure")

        @staticmethod
        def generate_content(model, contents, config):
            class _Response:
                text = '{"ok": true}'

            return _Response()

    class _FakeClient:
        def __init__(self, api_key):
            self.models = _FakeModels()

    monkeypatch.setattr(ai_module.genai, "Client", _FakeClient)

    output = ai_module.generate_with_instruction("hello", "system")
    assert output == '{"ok": true}'


def test_generate_with_instruction_maps_api_error(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MAX_RETRIES", "0")
    monkeypatch.setenv("GEMINI_MODEL_NAME", "gemini-3-flash-preview")

    class _FakeModels:
        @staticmethod
        def generate_content_stream(model, contents, config):
            raise _FakeAPIError(404, "model not found")

        @staticmethod
        def generate_content(model, contents, config):
            raise AssertionError("fallback should not run when APIError is raised directly")

    class _FakeClient:
        def __init__(self, api_key):
            self.models = _FakeModels()

    monkeypatch.setattr(ai_module.genai, "Client", _FakeClient)

    try:
        ai_module.generate_with_instruction("hello", "system")
    except ai_module.AIServiceError as exc:
        assert exc.error_code == "AI_MODEL_NOT_FOUND"
        assert exc.status_code == 502
    else:
        raise AssertionError("Expected AIServiceError")
