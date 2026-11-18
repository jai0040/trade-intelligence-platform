"""Valkey / Redis client wrapper for health checks, distributed locks, sessions, and kill-switch mirror."""

from __future__ import annotations

from typing import Any

import redis

KILL_SWITCH_REDIS_KEY = "system:kill_switch"


def build_redis_client(redis_url: str) -> redis.Redis[str]:
    return redis.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)


def check_redis_health(client: redis.Redis[str]) -> tuple[bool, str]:
    try:
        if client.ping():
            return True, "ok"
        return False, "ping returned false"
    except Exception as exc:  # pragma: no cover - integration failure path
        return False, str(exc)


def get_kill_switch_state(client: redis.Redis[str]) -> dict[str, Any]:
    """Read mirrored kill-switch state from Redis; fails safe to unknown if unavailable."""
    try:
        val = client.get(KILL_SWITCH_REDIS_KEY)
        return {"enabled": val == "1", "source": "redis"}
    except Exception:  # pragma: no cover
        return {"enabled": False, "source": "unavailable"}
