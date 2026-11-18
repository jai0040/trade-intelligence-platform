"""System Settings (Kill Switch), Workflow/Skill Runs, Immutable Signals, Outcomes, News, Fundamentals, Disclosures."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, utc_now


class SystemSetting(Base):
    """Global platform settings including the audited Emergency Kill Switch."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class WorkflowRun(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint(
            "workflow_type", "market_id", "idempotency_key", name="uq_workflow_runs_idempotency"
        ),
        Index("ix_workflow_runs_market_created", "market_id", "created_at"),
    )

    market_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("markets.id", ondelete="RESTRICT"), nullable=False
    )
    workflow_type: Mapped[str] = mapped_column(String(48), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="QUEUED")
    triggered_by: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduler")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class SkillRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "skill_runs"
    __table_args__ = (Index("ix_skill_runs_workflow_skill", "workflow_run_id", "skill_name"),)

    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    skill_name: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="RUNNING")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    output_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    error_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TradingSignal(UUIDPrimaryKeyMixin, Base):
    """Immutable trading signal snapshot protected by DB trigger against retroactive price edits."""

    __tablename__ = "trading_signals"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 100", name="confidence_score_range"
        ),
        Index("ix_signals_market_status_gen", "market_id", "current_status", "generated_at_utc"),
        Index("ix_signals_instrument_gen", "instrument_id", "generated_at_utc"),
    )

    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    market_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("markets.id", ondelete="RESTRICT"), nullable=False
    )
    exchange_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("exchanges.id", ondelete="RESTRICT"), nullable=False
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )
    strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    target_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    risk_reward_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    confidence_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    technical_indicators: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    news_context: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    timemachine_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    broker_ticket_preview: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    risk_validation_status: Mapped[str] = mapped_column(String(16), nullable=False)
    risk_validation_details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    data_source_provider: Mapped[str] = mapped_column(String(48), nullable=False)
    data_as_of_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_status: Mapped[str] = mapped_column(String(24), nullable=False)
    generated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    expires_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class SignalUpdate(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "signal_updates"
    __table_args__ = (Index("ix_signal_updates_signal_created", "signal_id", "created_at_utc"),)

    signal_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("trading_signals.id", ondelete="RESTRICT"), nullable=False
    )
    previous_status: Mapped[str] = mapped_column(String(24), nullable=False)
    new_status: Mapped[str] = mapped_column(String(24), nullable=False)
    trigger_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    bar_timestamp_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class SignalOutcome(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "signal_outcomes"

    signal_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trading_signals.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    final_status: Mapped[str] = mapped_column(String(24), nullable=False)
    triggered_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assumed_entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    assumed_exit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    estimated_cost_bps: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    gross_return_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    net_return_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    realized_r_multiple: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    calculated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class MarketNews(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "market_news"
    __table_args__ = (
        Index("ix_market_news_market_pub", "market_id", "published_at_utc"),
        Index("ix_market_news_instrument_pub", "instrument_id", "published_at_utc"),
    )

    market_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("markets.id", ondelete="RESTRICT"), nullable=False
    )
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    is_regulatory_filing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filing_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dedupe_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    published_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class CompanyFundamental(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "company_fundamentals"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "period_end_date",
            "fiscal_period",
            name="uq_fundamentals_instrument_period",
        ),
    )

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_period: Mapped[str] = mapped_column(String(16), nullable=False)
    filing_source: Mapped[str] = mapped_column(String(32), nullable=False)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    gross_margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    operating_margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    net_margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    net_income: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    diluted_eps: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    is_derived_q4: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    filing_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    filed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CongressDisclosure(UUIDPrimaryKeyMixin, Base):
    """US-only STOCK Act PTR disclosures with explicit disclosure lag tracking."""

    __tablename__ = "congress_disclosures"
    __table_args__ = (
        UniqueConstraint(
            "doc_id",
            "raw_ticker",
            "trade_date",
            "transaction_type",
            "amount_range",
            name="uq_congress_disclosure_row",
        ),
        Index("ix_congress_disclosures_filing_date", "filing_date"),
    )

    doc_id: Mapped[str] = mapped_column(String(32), nullable=False)
    member_name: Mapped[str] = mapped_column(String(120), nullable=False)
    district: Mapped[str | None] = mapped_column(String(16), nullable=True)
    owner_type: Mapped[str] = mapped_column(String(16), nullable=False, default="SELF")
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True
    )
    raw_ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_description: Mapped[str] = mapped_column(Text, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_range: Mapped[str] = mapped_column(String(64), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    disclosure_delay_days: Mapped[int] = mapped_column(Integer, nullable=False)
    is_late_filing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_pdf_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
