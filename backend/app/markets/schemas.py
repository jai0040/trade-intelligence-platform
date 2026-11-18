"""Pydantic v2 schemas matching docs/api/openapi.yaml MarketStatus & Instrument endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class DataFreshnessResponse(BaseModel):
    provider: str
    status: Literal["HEALTHY", "DEGRADED", "DOWN"]
    last_quote_utc: datetime | None
    delay_seconds: int
    is_stale: bool
    stale_reason: str | None = None


class MarketStatusResponse(BaseModel):
    market_code: Literal["IN", "US"]
    exchange_code: Literal["NSE", "BSE", "NASDAQ", "NYSE"]
    is_open: bool
    session_phase: Literal["PRE_OPEN", "REGULAR", "EARLY_CLOSE", "CLOSED", "HOLIDAY"]
    timezone: str
    local_time: str
    next_open_utc: datetime | None
    session_reason: str
    session_5m_bars: int
    data_freshness: DataFreshnessResponse


class IndexSnapshotResponse(BaseModel):
    instrument_id: str
    market_code: Literal["IN", "US"]
    exchange_code: Literal["NSE", "BSE", "NASDAQ", "NYSE"]
    symbol: str
    canonical_code: str
    company_name: str
    currency: Literal["INR", "USD"]
    last_price: Decimal
    prev_close: Decimal
    change: Decimal
    change_pct: Decimal
    quote_timestamp_utc: datetime
    source_provider: str
    is_delayed: bool
    delay_seconds: int
    is_stale: bool


class InstrumentSummaryResponse(BaseModel):
    instrument_id: str
    market_code: Literal["IN", "US"]
    exchange_code: Literal["NSE", "BSE", "NASDAQ", "NYSE"]
    symbol: str
    canonical_code: str
    company_name: str
    asset_type: str
    currency: Literal["INR", "USD"]
    tick_size: Decimal
    lot_size: int
    sector: str | None = None


class OHLCVBarResponse(BaseModel):
    bar_start_utc: datetime
    bar_end_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    is_complete: bool


class InstrumentBarsResponse(BaseModel):
    instrument: InstrumentSummaryResponse
    timeframe: Literal["1m", "5m", "15m", "1d"]
    source_provider: str
    bar_count: int
    data_freshness: DataFreshnessResponse
    bars: list[OHLCVBarResponse]
