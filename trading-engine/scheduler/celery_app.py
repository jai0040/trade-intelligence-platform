"""Celery worker & beat configuration for multi-market background processing.

Security & Reliability Guarantees:
- Strictly JSON serialization (pickle disabled).
- All timestamps & schedules normalized in UTC; exchange-calendar checks run inside tasks.
- Dedicated queues isolate India market scans, US market scans, analysis/AI, notifications, and maintenance.
- `task_acks_late=True` and `worker_prefetch_multiplier=1` prevent silent job loss on worker shutdown.
"""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

TASK_QUEUES = (
    Queue("india_market"),
    Queue("us_market"),
    Queue("analysis"),
    Queue("notifications"),
    Queue("maintenance"),
)

celery_app = Celery(
    "trade_intelligence_engine",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["workflows.tasks"],
)

celery_app.conf.update(
    # Strict JSON serialization only (prevents pickle RCE risks)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # UTC everywhere; MarketAdapters handle IST / ET conversions & holidays
    timezone="UTC",
    enable_utc=True,
    # Reliability & graceful shutdown
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    # Queues & explicit routing
    task_queues=TASK_QUEUES,
    task_default_queue="maintenance",
    task_routes={
        "workflows.tasks.heartbeat": {"queue": "maintenance"},
        "workflows.tasks.run_india_*": {"queue": "india_market"},
        "workflows.tasks.run_us_*": {"queue": "us_market"},
        "workflows.tasks.run_analysis_*": {"queue": "analysis"},
        "workflows.tasks.dispatch_notification*": {"queue": "notifications"},
    },
    # Phase 3 foundation beat schedule (market-specific DAG triggers wired in Phase 6)
    beat_schedule={
        "worker-heartbeat-every-5m": {
            "task": "workflows.tasks.heartbeat",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "maintenance"},
        },
    },
)
