"""Foundation Celery tasks with kill-switch awareness and idempotent key utilities."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

import redis

from scheduler.celery_app import celery_app

KILL_SWITCH_REDIS_KEY = "system:kill_switch"


def compute_workflow_idempotency_key(
    workflow_type: str,
    market_code: str,
    session_date_iso: str,
    slot_utc_iso: str,
) -> str:
    """Deterministic SHA-256 idempotency key preventing duplicate scans across workers/retries."""
    raw = f"{workflow_type}:{market_code}:{session_date_iso}:{slot_utc_iso}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_kill_switch_enabled() -> bool:
    """Check Valkey/Redis kill-switch flag before running automated market workflows."""
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
        try:
            return client.get(KILL_SWITCH_REDIS_KEY) == "1"
        finally:
            client.close()
    except Exception:
        return False


@celery_app.task(name="workflows.tasks.heartbeat", bind=True, max_retries=0)
def heartbeat(self: Any) -> dict[str, Any]:
    """Lightweight liveness heartbeat confirming Celery worker + Beat connectivity."""
    return {
        "status": "ok",
        "task_id": self.request.id,
        "trading_mode": os.environ.get("TRADING_MODE", "SIGNALS_ONLY"),
        "kill_switch_enabled": is_kill_switch_enabled(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
