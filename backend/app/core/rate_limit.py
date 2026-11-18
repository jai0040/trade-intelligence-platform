"""Redis-backed rate limiter with safe in-memory fallback for isolated unit testing."""

from __future__ import annotations

import math
import time
from threading import Lock
from typing import Any

from fastapi import Request

from app.core.errors import APIError

_MEMORY_LOCK = Lock()
_MEMORY_BUCKETS: dict[str, tuple[int, float]] = {}


def reset_in_memory_rate_limits() -> None:
    """Reset fallback in-memory rate-limit counters (intended for unit/integration tests)."""
    with _MEMORY_LOCK:
        _MEMORY_BUCKETS.clear()


def extract_client_ip(request: Request) -> str:
    """Extract client IP, preferring X-Forwarded-For left-most hop when present."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return first_hop
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _consume_redis(redis_client: Any, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    pipe = redis_client.pipeline()
    pipe.incr(key, 1)
    pipe.ttl(key)
    count, ttl = pipe.execute()
    if int(count) == 1 or int(ttl) < 0:
        redis_client.expire(key, window_seconds)
        ttl = window_seconds
    retry_after = max(1, int(ttl))
    return int(count) <= limit, retry_after


def _consume_memory(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    now = time.monotonic()
    with _MEMORY_LOCK:
        current = _MEMORY_BUCKETS.get(key)
        if current is None or now >= current[1]:
            _MEMORY_BUCKETS[key] = (1, now + window_seconds)
            return True, window_seconds
        count, expires_at = current
        count += 1
        _MEMORY_BUCKETS[key] = (count, expires_at)
        retry_after = max(1, math.ceil(expires_at - now))
        return count <= limit, retry_after


def enforce_rate_limit(
    redis_client: Any | None,
    *,
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Increment rate-limit counter for (scope, identifier) and raise 429 when exceeded."""
    key = f"rl:{scope}:{identifier}"
    allowed = True
    retry_after = window_seconds
    if redis_client is not None:
        try:
            allowed, retry_after = _consume_redis(redis_client, key, limit, window_seconds)
        except Exception:
            allowed, retry_after = _consume_memory(key, limit, window_seconds)
    else:
        allowed, retry_after = _consume_memory(key, limit, window_seconds)

    if not allowed:
        raise APIError(
            status_code=429,
            code="RATE_LIMITED",
            message="Too many requests. Please wait before trying again.",
            details={"scope": scope, "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )
