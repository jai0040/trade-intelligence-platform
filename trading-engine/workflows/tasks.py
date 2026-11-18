"""Celery worker tasks executing India & US market DAG workflows with kill-switch awareness."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

import redis

from data_providers.factory import build_market_data_provider
from domain.models import MarketCode
from scheduler.celery_app import celery_app
from workflows.dag_engine import WorkflowEngine, compute_workflow_idempotency_key

KILL_SWITCH_REDIS_KEY = "system:kill_switch"


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


def _execute_scheduled_market_dag(
    *,
    market_code: MarketCode,
    workflow_type: str,
    mode: str,
) -> dict[str, Any]:
    app_env = os.environ.get("APP_ENV", "development")
    provider_env_key = (
        "MARKET_DATA_PROVIDER_IN" if market_code == MarketCode.IN else "MARKET_DATA_PROVIDER_US"
    )
    provider_code = os.environ.get(provider_env_key, "mock")
    provider = build_market_data_provider(provider_code, app_env=app_env)
    engine = WorkflowEngine(kill_switch_checker=is_kill_switch_enabled)
    report = engine.execute_market_workflow(
        market_code=market_code,
        workflow_type=workflow_type,
        data_provider=provider,
        as_of_utc=datetime.now(timezone.utc),
        triggered_by="celery_beat",
        mode=mode,
    )
    return report.summary()


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


@celery_app.task(name="workflows.tasks.run_india_premarket_scan", bind=True, max_retries=2)
def run_india_premarket_scan(self: Any) -> dict[str, Any]:
    """Scheduled India (NSE/BSE) pre-market daily setup scan."""
    return _execute_scheduled_market_dag(
        market_code=MarketCode.IN,
        workflow_type="india_premarket_daily",
        mode="daily",
    )


@celery_app.task(name="workflows.tasks.run_india_intraday_orb", bind=True, max_retries=2)
def run_india_intraday_orb(self: Any) -> dict[str, Any]:
    """Scheduled India (NSE/BSE) 5-minute intraday ORB & signal lifecycle workflow."""
    return _execute_scheduled_market_dag(
        market_code=MarketCode.IN,
        workflow_type="india_intraday_orb",
        mode="orb",
    )


@celery_app.task(name="workflows.tasks.run_us_premarket_scan", bind=True, max_retries=2)
def run_us_premarket_scan(self: Any) -> dict[str, Any]:
    """Scheduled US (NASDAQ/NYSE) pre-market daily setup scan."""
    return _execute_scheduled_market_dag(
        market_code=MarketCode.US,
        workflow_type="us_premarket_daily",
        mode="daily",
    )


@celery_app.task(name="workflows.tasks.run_us_intraday_orb", bind=True, max_retries=2)
def run_us_intraday_orb(self: Any) -> dict[str, Any]:
    """Scheduled US (NASDAQ/NYSE) 5-minute intraday ORB & signal lifecycle workflow."""
    return _execute_scheduled_market_dag(
        market_code=MarketCode.US,
        workflow_type="us_intraday_orb",
        mode="orb",
    )


__all__ = [
    "KILL_SWITCH_REDIS_KEY",
    "compute_workflow_idempotency_key",
    "heartbeat",
    "is_kill_switch_enabled",
    "run_india_intraday_orb",
    "run_india_premarket_scan",
    "run_us_intraday_orb",
    "run_us_premarket_scan",
]
