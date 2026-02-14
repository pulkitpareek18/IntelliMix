from __future__ import annotations

from ai import ai_main


def test_resolve_mixing_mode_aliases_and_defaults():
    assert not hasattr(ai_main, "_resolve_mixing_mode")


def test_generate_ai_uses_single_intelligent_pipeline(monkeypatch, tmp_path):
    called = {"mode": None}

    def _fake_intelligent(prompt: str, workspace: ai_main._WorkspacePaths) -> str:
        called["mode"] = "intelligent"
        assert prompt == "test prompt"
        assert workspace.temp_dir.endswith("temp")
        return "intelligent.mp3"

    monkeypatch.setattr(ai_main, "_generate_ai_intelligent", _fake_intelligent)

    output = ai_main.generate_ai("test prompt", session_dir=str(tmp_path))
    assert output == "intelligent.mp3"
    assert called["mode"] == "intelligent"
