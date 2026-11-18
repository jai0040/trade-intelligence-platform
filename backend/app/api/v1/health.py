"""Health, readiness, and platform metadata endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.redis import check_redis_health, get_kill_switch_state
from database.session import check_database_health

router = APIRouter(tags=["system"])


@router.get("/health")
def health_check(request: Request) -> dict[str, Any]:
    """Return service liveness plus PostgreSQL and Valkey/Redis dependency health."""
    settings = get_settings()
    db_engine = getattr(request.app.state, "db_engine", None)
    redis_client = getattr(request.app.state, "redis_client", None)

    db_ok, db_detail = (
        check_database_health(db_engine) if db_engine is not None else (False, "not_initialized")
    )
    redis_ok, redis_detail = (
        check_redis_health(redis_client) if redis_client is not None else (False, "not_initialized")
    )
    kill_switch = (
        get_kill_switch_state(redis_client)
        if redis_client is not None and redis_ok
        else {"enabled": False, "source": "not_connected"}
    )

    overall = "healthy" if (db_ok and redis_ok) else "degraded"
    return {
        "status": overall,
        "service": settings.app_name,
        "environment": settings.app_env,
        "trading_mode": settings.trading_mode,
        "kill_switch": kill_switch,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "postgresql": {"ok": db_ok, "detail": db_detail},
            "valkey_redis": {"ok": redis_ok, "detail": redis_detail},
        },
        "markets": {
            "india": {
                "code": "IN",
                "exchanges": ["NSE", "BSE"],
                "currency": "INR",
                "timezone": "Asia/Kolkata",
                "provider": settings.market_data_provider_in,
            },
            "usa": {
                "code": "US",
                "exchanges": ["NASDAQ", "NYSE"],
                "currency": "USD",
                "timezone": "America/New_York",
                "provider": settings.market_data_provider_us,
            },
        },
    }
