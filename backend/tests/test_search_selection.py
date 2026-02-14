from __future__ import annotations

from dataclasses import dataclass

from ai import search as search_module


@dataclass
class _Video:
    video_id: str
    title: str
    length: int
    author: str = ""
    views: int = 0
    watch_url: str = ""


def test_get_youtube_url_prefers_full_official_video(monkeypatch):
    videos = [
        _Video(
            video_id="short123",
            title="Sahiba lyrics short reel",
            length=32,
            author="random",
            views=150_000,
            watch_url="https://www.youtube.com/shorts/short123",
        ),
        _Video(
            video_id="full456",
            title="Sahiba (Official Music Video) Aditya Rikhari",
            length=240,
            author="T-Series",
            views=8_000_000,
            watch_url="https://www.youtube.com/watch?v=full456",
        ),
    ]

    class _FakeSearch:
        def __init__(self, query: str, proxies=None):
            self.videos = videos

    monkeypatch.setattr(search_module, "Search", _FakeSearch)

    url = search_module.get_youtube_url("Sahiba", "Aditya Rikhari")
    assert url == "https://www.youtube.com/watch?v=full456"


def test_get_youtube_url_returns_none_when_no_results(monkeypatch):
    class _FakeSearch:
        def __init__(self, query: str, proxies=None):
            self.videos = []

    monkeypatch.setattr(search_module, "Search", _FakeSearch)
    assert search_module.get_youtube_url("Missing Song", "Unknown Artist") is None
