"""Markets, Exchanges, Calendar Overrides, Instruments, OHLCV Market Data, and Provider Status models."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class Market(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "markets"

    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    exchanges: Mapped[list[Exchange]] = relationship("Exchange", back_populates="market")


class Exchange(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "exchanges"

    market_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("markets.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    mic_code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    regular_open_local: Mapped[time] = mapped_column(Time, nullable=False)
    regular_close_local: Mapped[time] = mapped_column(Time, nullable=False)
    session_5m_bars: Mapped[int] = mapped_column(Integer, nullable=False)

    market: Mapped[Market] = relationship("Market", back_populates="exchanges")


class MarketCalendarOverride(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "market_calendar_overrides"
    __table_args__ = (
        UniqueConstraint("exchange_id", "session_date", name="uq_calendar_override_exchange_date"),
    )

    exchange_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("exchanges.id", ondelete="CASCADE"), nullable=False
    )
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    override_type: Mapped[str] = mapped_column(String(24), nullable=False)
    open_local: Mapped[time | None] = mapped_column(Time, nullable=True)
    close_local: Mapped[time | None] = mapped_column(Time, nullable=True)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)


class Instrument(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint("exchange_id", "symbol", name="uq_instruments_exchange_symbol"),
        Index("ix_instruments_market_active", "market_id", "is_active"),
    )

    market_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("markets.id", ondelete="RESTRICT"), nullable=False
    )
    exchange_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("exchanges.id", ondelete="RESTRICT"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_code: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False, default="EQUITY")
    sector: Mapped[str | None] = mapped_column(String(80), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(24), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    tick_size: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    lot_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provider_symbols: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class MarketData(Base):
    """OHLCV bars with mandatory source_provider and fetched_at_utc provenance."""

    __tablename__ = "market_data"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "timeframe", "bar_start_utc", name="uq_market_data_bar_slot"
        ),
        Index("ix_market_data_lookup", "instrument_id", "timeframe", "bar_start_utc"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    bar_start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bar_end_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_provider: Mapped[str] = mapped_column(String(48), nullable=False)
    fetched_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProviderStatus(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "provider_status"

    provider_code: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    market_code: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="HEALTHY")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    avg_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_api_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
