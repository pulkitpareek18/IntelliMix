from __future__ import annotations

import logging
import os
from typing import Optional

try:
    import redis
except Exception:  # pragma: no cover - import guard for environments without redis extra
    redis = None  # type: ignore

LOGGER = logging.getLogger(__name__)


def _queue_url() -> str:
    return os.environ.get("MIX_CHAT_QUEUE_URL", "redis://redis:6379/0")


def _queue_key() -> str:
    return os.environ.get("MIX_CHAT_QUEUE_KEY", "intellimix:mix_chat_runs")


def _redis_client():
    if redis is None:
        return None
    try:
        client = redis.Redis.from_url(_queue_url())
        client.ping()
        return client
    except Exception:
        return None


def enqueue_run(run_id: str) -> bool:
    client = _redis_client()
    if client is None:
        LOGGER.warning("mix chat queue unavailable; enqueue skipped")
        return False
    try:
        client.rpush(_queue_key(), run_id)
        return True
    except Exception:
        LOGGER.exception("failed to enqueue run id %s", run_id)
        return False


def pop_run(block_seconds: int = 5) -> Optional[str]:
    client = _redis_client()
    if client is None:
        return None
    try:
        popped = client.blpop(_queue_key(), timeout=max(1, int(block_seconds)))
        if not popped:
            return None
        _, value = popped
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")
        return str(value)
    except Exception:
        LOGGER.exception("failed to pop mix chat run")
        return None


def queue_available() -> bool:
    return _redis_client() is not None
