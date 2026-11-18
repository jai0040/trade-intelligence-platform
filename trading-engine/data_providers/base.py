"""Abstract pluggable MarketDataProvider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from domain.models import Instrument, MarketCode, OHLCVBar, QuoteSnapshot


class MarketDataProvider(ABC):
    """Pluggable provider contract with mandatory provenance and licensing metadata."""

    provider_code: str
    is_commercial_licensed: bool
    supported_markets: tuple[MarketCode, ...]

    @abstractmethod
    def get_universe(self, market_code: MarketCode) -> list[Instrument]:
        """Return active tradeable instruments (equities, ETFs, indices) for market_code."""

    @abstractmethod
    def get_quotes(
        self, instruments: list[Instrument], *, as_of_utc: datetime | None = None
    ) -> dict[str, QuoteSnapshot]:
        """Fetch latest quote snapshots keyed by instrument_id. Never fabricate prices on error."""

    @abstractmethod
    def get_bars(
        self,
        instrument: Instrument,
        timeframe: str,
        start_utc: datetime,
        end_utc: datetime,
    ) -> list[OHLCVBar]:
        """Fetch ordered OHLCV bars for timeframe ('1m', '5m', '15m', '1d')."""

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Return provider liveness, commercial flag, and latency metadata."""
