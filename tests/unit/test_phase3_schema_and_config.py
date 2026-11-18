"""SQLAlchemy schema metadata, Pydantic Settings guardrail, and Celery queue unit tests.

Runs automatically inside the project `.venv` or Docker backend/worker containers.
"""

from __future__ import annotations

import pytest


def test_sqlalchemy_registers_all_31_tables_and_single_session_index() -> None:
    pytest.importorskip("sqlalchemy")
    from database.models import Base

    tables = set(Base.metadata.tables.keys())
    expected_core = {
        "roles",
        "users",
        "sessions",
        "password_reset_tokens",
        "audit_logs",
        "subscription_plans",
        "subscriptions",
        "payments",
        "payment_events",
        "markets",
        "exchanges",
        "market_calendar_overrides",
        "instruments",
        "market_data",
        "provider_status",
        "system_settings",
        "workflow_runs",
        "skill_runs",
        "trading_signals",
        "signal_updates",
        "signal_outcomes",
        "market_news",
        "company_fundamentals",
        "congress_disclosures",
        "watchlists",
        "watchlist_items",
        "user_preferences",
        "user_trading_journal",
        "alerts",
        "notification_preferences",
        "notifications",
    }
    assert expected_core == tables
    session_indexes = {idx.name for idx in Base.metadata.tables["sessions"].indexes}
    assert "uq_sessions_one_active_per_user" in session_indexes


def test_settings_hard_locks_signals_only_and_production_guards() -> None:
    pytest.importorskip("pydantic_settings")
    from pydantic import ValidationError
    from app.core.config import Settings

    with pytest.raises(ValidationError, match="SIGNALS_ONLY"):
        Settings(trading_mode="LIVE")

    with pytest.raises(ValidationError, match="SESSION_COOKIE_SECURE"):
        Settings(
            app_env="production",
            secret_key="a" * 40,
            session_cookie_secure=False,
            market_data_provider_in="licensed_india",
            market_data_provider_us="licensed_us",
        )

    with pytest.raises(ValidationError, match="licensed commercial provider"):
        Settings(
            app_env="production",
            secret_key="a" * 40,
            session_cookie_secure=True,
            market_data_provider_in="dev_yahoo",
            market_data_provider_us="licensed_us",
        )


def test_celery_configures_5_queues_utc_and_json_only() -> None:
    pytest.importorskip("celery")
    from scheduler.celery_app import celery_app

    queue_names = {q.name for q in celery_app.conf.task_queues}
    assert queue_names == {"india_market", "us_market", "analysis", "notifications", "maintenance"}
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
