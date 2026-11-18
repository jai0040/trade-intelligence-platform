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
    # Multi-market beat schedules (UTC); MarketAdapters enforce exact IST/ET holidays & DST inside tasks
    beat_schedule={
        "worker-heartbeat-every-5m": {
            "task": "workflows.tasks.heartbeat",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "maintenance"},
        },
        "india-premarket-daily-scan": {
            "task": "workflows.tasks.run_india_premarket_scan",
            "schedule": crontab(hour=3, minute=15, day_of_week="1-5"),  # 08:45 IST
            "options": {"queue": "india_market"},
        },
        "india-intraday-orb-every-5m": {
            "task": "workflows.tasks.run_india_intraday_orb",
            "schedule": crontab(minute="*/5", hour="3-10", day_of_week="1-5"),  # 09:15-15:30 IST
            "options": {"queue": "india_market"},
        },
        "us-premarket-daily-scan": {
            "task": "workflows.tasks.run_us_premarket_scan",
            "schedule": crontab(hour=13, minute=0, day_of_week="1-5"),  # 08:00 EST / 09:00 EDT
            "options": {"queue": "us_market"},
        },
        "us-intraday-orb-every-5m": {
            "task": "workflows.tasks.run_us_intraday_orb",
            "schedule": crontab(minute="*/5", hour="13-21", day_of_week="1-5"),  # US regular hours
            "options": {"queue": "us_market"},
        },
    },
)
