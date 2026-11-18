"""Abstract MarketAdapter interface and shared calendar/tick-size primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP

from domain.models import ExchangeCode, Instrument, MarketCode, MarketSession, SessionPhase
from domain.timezones import get_timezone


@dataclass(frozen=True)
class CalendarOverride:
    """Explicit exchange calendar override (mirrors DB market_calendar_overrides)."""

    exchange_code: ExchangeCode
    session_date: date
    override_type: str  # "HOLIDAY" | "EARLY_CLOSE" | "SPECIAL_SESSION"
    reason: str
    open_local: time | None = None
    close_local: time | None = None


class MarketAdapter(ABC):
    """Market-specific calendar, symbol, tick-size, and entry-window adapter."""

    market_code: MarketCode
    currency: str
    timezone_name: str
    supported_exchanges: tuple[ExchangeCode, ...]
    session_5m_bar_count: int

    def local_timezone(self):
        return get_timezone(self.timezone_name)

    def _index_overrides(
        self, exchange: ExchangeCode, overrides: Iterable[CalendarOverride] | None
    ) -> dict[date, CalendarOverride]:
        if not overrides:
            return {}
        return {
            ov.session_date: ov for ov in overrides if ov.exchange_code == exchange
        }

    def _ensure_supported_exchange(self, exchange: ExchangeCode) -> None:
        if exchange not in self.supported_exchanges:
            raise ValueError(
                f"Exchange {exchange.value} is not supported by {self.__class__.__name__}"
            )

    @abstractmethod
    def validate_symbol(self, symbol: str, exchange: ExchangeCode) -> bool:
        """Return True if symbol obeys exchange-specific ticker syntax."""

    @abstractmethod
    def normalize_input_symbol(
        self, raw_symbol: str, default_exchange: ExchangeCode | None = None
    ) -> tuple[str, ExchangeCode]:
        """Parse user/provider symbol strings (e.g. RELIANCE.NS, NSE:M&M, BRK.B) into (symbol, exchange)."""

    @abstractmethod
    def to_provider_symbol(self, instrument: Instrument, provider_code: str) -> str:
        """Map canonical Instrument to a provider-specific symbol without destructive global mutations."""

    def effective_tick_size(self, price: Decimal, instrument: Instrument) -> Decimal:
        """Return effective tick size for an instrument at a given price."""
        return instrument.tick_size

    def round_to_tick(
        self, price: Decimal, instrument: Instrument, direction: str = "nearest"
    ) -> Decimal:
        """Round Decimal price cleanly to exchange tick size.

        direction:
          - 'down': floor to tick (conservative stop-loss for BUY longs, or target for BUY)
          - 'up': ceil to tick (conservative stop-loss for SELL shorts, or entry breakout)
          - 'nearest': standard half-up tick rounding
        """
        tick = self.effective_tick_size(price, instrument)
        if tick <= Decimal("0"):
            raise ValueError("Tick size must be strictly positive.")
        units = price / tick
        mode_map = {
            "down": ROUND_FLOOR,
            "up": ROUND_CEILING,
            "nearest": ROUND_HALF_UP,
        }
        rounding = mode_map.get(direction.lower())
        if rounding is None:
            raise ValueError(f"Unsupported rounding direction: {direction!r}")
        rounded_units = units.to_integral_value(rounding=rounding)
        return (rounded_units * tick).quantize(tick)

    @abstractmethod
    def get_session_window(
        self,
        exchange: ExchangeCode,
        session_date: date,
        overrides: Iterable[CalendarOverride] | None = None,
    ) -> MarketSession:
        """Return MarketSession metadata and UTC open/close/entry windows for session_date."""

    def get_next_open_utc(
        self,
        exchange: ExchangeCode,
        after_utc: datetime,
        overrides: Iterable[CalendarOverride] | None = None,
    ) -> datetime | None:
        """Find the next regular or special session open timestamp strictly after after_utc."""
        self._ensure_supported_exchange(exchange)
        local_tz = self.local_timezone()
        local_dt = after_utc.astimezone(local_tz)
        for day_offset in range(0, 15):
            candidate_date = local_dt.date() + timedelta(days=day_offset)
            session = self.get_session_window(exchange, candidate_date, overrides=overrides)
            if session.is_trading_day and session.open_utc is not None and session.open_utc > after_utc:
                return session.open_utc
        return None

    def get_live_session_phase(
        self,
        exchange: ExchangeCode,
        now_utc: datetime,
        overrides: Iterable[CalendarOverride] | None = None,
    ) -> tuple[bool, SessionPhase, MarketSession, datetime | None]:
        """Compute live (is_open, session_phase, current_session, next_open_utc) at now_utc."""
        self._ensure_supported_exchange(exchange)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        else:
            now_utc = now_utc.astimezone(timezone.utc)

        local_dt = now_utc.astimezone(self.local_timezone())
        session = self.get_session_window(exchange, local_dt.date(), overrides=overrides)

        if not session.is_trading_day:
            phase = SessionPhase.HOLIDAY if session.is_holiday else SessionPhase.CLOSED
            return False, phase, session, self.get_next_open_utc(exchange, now_utc, overrides=overrides)

        assert session.open_utc is not None and session.close_utc is not None
        if session.pre_open_utc is not None and session.pre_open_utc <= now_utc < session.open_utc:
            return False, SessionPhase.PRE_OPEN, session, session.open_utc

        if session.open_utc <= now_utc < session.close_utc:
            phase = SessionPhase.EARLY_CLOSE if session.is_early_close else SessionPhase.REGULAR
            return True, phase, session, None

        return (
            False,
            SessionPhase.CLOSED,
            session,
            self.get_next_open_utc(exchange, now_utc, overrides=overrides),
        )

    def is_within_entry_window(
        self,
        exchange: ExchangeCode,
        now_utc: datetime,
        overrides: Iterable[CalendarOverride] | None = None,
    ) -> tuple[bool, str]:
        """Verify whether new intraday signal entries are allowed at now_utc."""
        self._ensure_supported_exchange(exchange)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        else:
            now_utc = now_utc.astimezone(timezone.utc)

        local_dt = now_utc.astimezone(self.local_timezone())
        session = self.get_session_window(exchange, local_dt.date(), overrides=overrides)

        if not session.is_trading_day:
            return False, f"Market closed ({session.reason})."
        assert (
            session.open_utc is not None
            and session.close_utc is not None
            and session.entry_start_utc is not None
            and session.entry_cutoff_utc is not None
        )
        if now_utc < session.open_utc:
            return False, "Market has not opened yet."
        if now_utc < session.entry_start_utc:
            return False, "Opening range still forming; wait for opening range completion."
        if now_utc >= session.close_utc:
            return False, "Market session has closed."
        if now_utc > session.entry_cutoff_utc:
            return False, "Past intraday entry cutoff window."
        return True, "Within active intraday entry window."

    @abstractmethod
    def get_cost_model_bps(self) -> Decimal:
        """Transparent round-trip slippage + statutory/brokerage cost basis points."""
