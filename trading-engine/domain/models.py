"""Canonical immutable domain models shared across adapters, providers, skills, and backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum


class MarketCode(str, Enum):
    IN = "IN"
    US = "US"


class ExchangeCode(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NASDAQ = "NASDAQ"
    NYSE = "NYSE"


class AssetType(str, Enum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    INDEX = "INDEX"


class SessionPhase(str, Enum):
    PRE_OPEN = "PRE_OPEN"
    REGULAR = "REGULAR"
    EARLY_CLOSE = "EARLY_CLOSE"
    CLOSED = "CLOSED"
    HOLIDAY = "HOLIDAY"


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WATCH = "WATCH"


class SignalStatus(str, Enum):
    PENDING = "Pending"
    ACTIVE = "Active"
    TRIGGERED = "Triggered"
    TARGET_HIT = "Target Hit"
    STOP_LOSS_HIT = "Stop Loss Hit"
    EXPIRED = "Expired"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"


class ProviderHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"


def _require_utc(dt: datetime, field_name: str) -> None:
    if dt.tzinfo is None or dt.utcoffset() != timezone.utc.utcoffset(dt):
        raise ValueError(f"{field_name} must be a timezone-aware UTC datetime.")


@dataclass(frozen=True)
class Instrument:
    instrument_id: str
    market_code: MarketCode
    exchange_code: ExchangeCode
    symbol: str
    canonical_code: str
    company_name: str
    asset_type: str
    currency: str
    tick_size: Decimal
    lot_size: int = 1
    sector: str | None = None
    isin: str | None = None
    provider_symbols: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tick_size <= Decimal("0"):
            raise ValueError("tick_size must be positive.")
        if self.lot_size < 1:
            raise ValueError("lot_size must be >= 1.")


@dataclass(frozen=True)
class OHLCVBar:
    instrument_id: str
    timeframe: str
    bar_start_utc: datetime
    bar_end_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    is_complete: bool
    source_provider: str
    fetched_at_utc: datetime

    def __post_init__(self) -> None:
        _require_utc(self.bar_start_utc, "bar_start_utc")
        _require_utc(self.bar_end_utc, "bar_end_utc")
        _require_utc(self.fetched_at_utc, "fetched_at_utc")
        if self.bar_end_utc <= self.bar_start_utc:
            raise ValueError("bar_end_utc must be strictly after bar_start_utc.")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("OHLCVBar violates high >= max(open, close) and low <= min(open, close).")
        if self.low <= Decimal("0"):
            raise ValueError("OHLCVBar prices must be strictly positive.")
        if self.volume < 0:
            raise ValueError("OHLCVBar volume cannot be negative.")


@dataclass(frozen=True)
class QuoteSnapshot:
    instrument_id: str
    last_price: Decimal
    prev_close: Decimal
    volume: int
    quote_timestamp_utc: datetime
    fetched_at_utc: datetime
    source_provider: str
    is_delayed: bool
    delay_seconds: int

    def __post_init__(self) -> None:
        _require_utc(self.quote_timestamp_utc, "quote_timestamp_utc")
        _require_utc(self.fetched_at_utc, "fetched_at_utc")
        if self.last_price <= Decimal("0") or self.prev_close <= Decimal("0"):
            raise ValueError("QuoteSnapshot prices must be strictly positive.")
        if self.volume < 0:
            raise ValueError("QuoteSnapshot volume cannot be negative.")

    @property
    def change(self) -> Decimal:
        return self.last_price - self.prev_close

    @property
    def change_pct(self) -> Decimal:
        if self.prev_close == Decimal("0"):
            return Decimal("0")
        return ((self.last_price - self.prev_close) / self.prev_close) * Decimal("100")


@dataclass(frozen=True)
class MarketSession:
    market_code: MarketCode
    exchange_code: ExchangeCode
    session_date: date
    is_trading_day: bool
    is_holiday: bool
    is_early_close: bool
    is_special_session: bool
    reason: str
    timezone_name: str
    open_utc: datetime | None
    close_utc: datetime | None
    pre_open_utc: datetime | None
    entry_start_utc: datetime | None
    entry_cutoff_utc: datetime | None
    session_5m_bars: int


@dataclass(frozen=True)
class DataFreshnessReport:
    provider: str
    status: ProviderHealthStatus
    last_quote_utc: datetime | None
    delay_seconds: int
    is_stale: bool
    stale_reason: str | None = None
