"""Strictly user-isolated workspace ORM models (watchlists, preferences, journal, alerts, notifications)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class Watchlist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "watchlists"
    __table_args__ = (Index("ix_watchlists_user", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    market_scope: Mapped[str] = mapped_column(String(8), nullable=False, default="ALL")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class WatchlistItem(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("watchlist_id", "instrument_id", name="uq_watchlist_items_unique"),
        Index("ix_watchlist_items_user", "user_id", "watchlist_id"),
    )

    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    default_market: Mapped[str] = mapped_column(String(8), nullable=False, default="ALL")
    theme: Mapped[str] = mapped_column(String(16), nullable=False, default="dark")
    display_timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    default_budget_inr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("200000.00")
    )
    default_max_loss_inr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("2000.00")
    )
    default_budget_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("5000.00")
    )
    default_max_loss_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("50.00")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class UserTradingJournal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_trading_journal"
    __table_args__ = (Index("ix_journal_user_entered", "user_id", "entered_at_utc"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    signal_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("trading_signals.id", ondelete="SET NULL"), nullable=True
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )
    market_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("markets.id", ondelete="RESTRICT"), nullable=False
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    planned_stop: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    planned_target: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    emotions_tags: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    entered_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exited_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Alert(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_user_active", "user_id", "is_active"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="CASCADE"), nullable=True
    )
    signal_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("trading_signals.id", ondelete="SET NULL"), nullable=True
    )
    rule_type: Mapped[str] = mapped_column(String(24), nullable=False)
    threshold_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    rearm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_triggered_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    browser_push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_new_signals: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_entry_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_target_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_stop_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_signal_expiry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_market_news: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_market_reports: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    market_filter: Mapped[str] = mapped_column(String(8), nullable=False, default="ALL")
    quiet_hours_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
        Index("ix_notifications_user_unread", "user_id", "is_read", "created_at_utc"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    dedupe_key: Mapped[str] = mapped_column(String(128), nullable=False)
    channel_status: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
