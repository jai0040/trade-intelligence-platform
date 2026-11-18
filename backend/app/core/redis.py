"""Valkey / Redis client wrapper for health checks, sessions, Pub/Sub events, and kill-switch."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import redis

KILL_SWITCH_REDIS_KEY = "system:kill_switch"


def active_session_key(user_id: uuid.UUID | str) -> str:
    """Canonical Redis key storing a user's single active session pointer."""
    return f"user:{user_id}:active_session"


def user_ws_channel(user_id: uuid.UUID | str) -> str:
    """Private WebSocket Pub/Sub channel for a single authenticated user."""
    return f"ws:user:{user_id}"


def market_ws_channel(market_code: str) -> str:
    """Market-scoped WebSocket Pub/Sub channel (IN or US)."""
    return f"ws:market:{market_code.upper()}"


def admin_ws_channel() -> str:
    """Admin-only WebSocket Pub/Sub channel."""
    return "ws:admin:system"


def build_redis_client(redis_url: str) -> redis.Redis[str]:
    return redis.Redis.from_url(
        redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
    )


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


def set_active_session_cache(
    client: Any | None,
    *,
    user_id: uuid.UUID | str,
    session_id: uuid.UUID | str,
    token_hash: str,
    session_version: int,
    ttl_seconds: int,
) -> bool:
    """Mirror the user's single active session into Redis with TTL."""
    if client is None:
        return False
    payload = json.dumps(
        {
            "session_id": str(session_id),
            "token_hash": token_hash,
            "session_version": session_version,
        }
    )
    try:
        client.setex(active_session_key(user_id), max(1, ttl_seconds), payload)
        return True
    except Exception:  # pragma: no cover - graceful DB fallback
        return False


def get_active_session_cache(client: Any | None, user_id: uuid.UUID | str) -> dict[str, Any] | None:
    """Read mirrored active session metadata from Redis if available."""
    if client is None:
        return None
    try:
        raw = client.get(active_session_key(user_id))
        if not raw:
            return None
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:  # pragma: no cover
        return None


def clear_active_session_cache(client: Any | None, user_id: uuid.UUID | str) -> None:
    """Remove a user's active session key from Redis upon logout or revocation."""
    if client is None:
        return
    try:
        client.delete(active_session_key(user_id))
    except Exception:  # pragma: no cover
        return


def build_ws_envelope(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a uniform WebSocket event envelope matching docs/api/websockets.md."""
    return {
        "event_id": str(uuid.uuid4()),
        "type": event_type,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def publish_session_invalidated(
    client: Any | None,
    *,
    user_id: uuid.UUID | str,
    code: str = "SESSION_SUPERSEDED",
    reason: str = "Your account was signed in from another device or browser.",
    revoked_by: str = "new_login",
    revoked_session_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Publish a session.invalidated event to ws:user:{user_id} over Redis Pub/Sub."""
    envelope = build_ws_envelope(
        "session.invalidated",
        {
            "code": code,
            "reason": reason,
            "revoked_by": revoked_by,
            "revoked_session_ids": revoked_session_ids or [],
        },
    )
    if client is not None:
        try:
            client.publish(user_ws_channel(user_id), json.dumps(envelope))
        except Exception:  # pragma: no cover
            pass
    return envelope
