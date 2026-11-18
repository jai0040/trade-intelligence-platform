"""India equity market adapter (NSE & BSE, INR, Asia/Kolkata, 09:15-15:30 IST, 75 5m bars)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from adapters.base import CalendarOverride, MarketAdapter
from domain.errors import SymbolValidationError
from domain.models import ExchangeCode, Instrument, MarketCode, MarketSession

# NSE/BSE ticker format: uppercase letters/digits, '&' (M&M, L&TFH), '-' (BAJAJ-AUTO), 1..20 chars
_INDIA_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9&-]{0,19}$")

# Built-in major NSE/BSE equity trading holidays (2025-2027); DB overrides always take precedence.
_INDIA_DEFAULT_HOLIDAYS: dict[date, str] = {
    # 2025
    date(2025, 2, 26): "Mahashivratri",
    date(2025, 3, 14): "Holi",
    date(2025, 3, 31): "Id-Ul-Fitr (Ramzan Eid)",
    date(2025, 4, 10): "Shri Mahavir Jayanti",
    date(2025, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
    date(2025, 4, 18): "Good Friday",
    date(2025, 5, 1): "Maharashtra Day",
    date(2025, 8, 15): "Independence Day",
    date(2025, 8, 27): "Ganesh Chaturthi",
    date(2025, 10, 2): "Mahatma Gandhi Jayanti / Dussehra",
    date(2025, 10, 21): "Diwali Laxmi Pujan",
    date(2025, 10, 22): "Diwali Balipratipada",
    date(2025, 11, 5): "Prakash Gurpurb Sri Guru Nanak Dev",
    date(2025, 12, 25): "Christmas",
    # 2026
    date(2026, 1, 26): "Republic Day",
    date(2026, 3, 3): "Holi",
    date(2026, 3, 26): "Shri Ram Navami",
    date(2026, 3, 31): "Shri Mahavir Jayanti",
    date(2026, 4, 3): "Good Friday",
    date(2026, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
    date(2026, 5, 1): "Maharashtra Day",
    date(2026, 5, 28): "Bakri Id",
    date(2026, 6, 26): "Muharram",
    date(2026, 9, 14): "Ganesh Chaturthi",
    date(2026, 10, 2): "Mahatma Gandhi Jayanti",
    date(2026, 10, 20): "Dussehra",
    date(2026, 11, 10): "Diwali Balipratipada",
    date(2026, 11, 24): "Prakash Gurpurb Sri Guru Nanak Dev",
    date(2026, 12, 25): "Christmas",
    # 2027
    date(2027, 1, 26): "Republic Day",
    date(2027, 3, 22): "Holi",
    date(2027, 3, 26): "Good Friday",
    date(2027, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
    date(2027, 8, 15): "Independence Day",
    date(2027, 10, 2): "Mahatma Gandhi Jayanti",
    date(2027, 12, 25): "Christmas",
}


class IndiaMarketAdapter(MarketAdapter):
    """Adapter encapsulating NSE & BSE market hours, holidays, Muhurat sessions, and INR tick rules."""

    market_code = MarketCode.IN
    currency = "INR"
    timezone_name = "Asia/Kolkata"
    supported_exchanges = (ExchangeCode.NSE, ExchangeCode.BSE)
    session_5m_bar_count = 75  # 09:15 to 15:30 IST = 375 minutes = 75 x 5m bars

    PRE_OPEN_LOCAL = time(9, 0)
    REGULAR_OPEN_LOCAL = time(9, 15)
    REGULAR_CLOSE_LOCAL = time(15, 30)
    ENTRY_START_OFFSET_MINUTES = 15  # 09:30 IST (after 15m opening range)
    ENTRY_CUTOFF_BEFORE_CLOSE_MINUTES = 30  # 15:00 IST (30m before close)

    def validate_symbol(self, symbol: str, exchange: ExchangeCode = ExchangeCode.NSE) -> bool:
        self._ensure_supported_exchange(exchange)
        cleaned = symbol.strip().upper()
        if not cleaned or "." in cleaned or " " in cleaned:
            return False
        return bool(_INDIA_SYMBOL_RE.match(cleaned))

    def normalize_input_symbol(
        self, raw_symbol: str, default_exchange: ExchangeCode | None = ExchangeCode.NSE
    ) -> tuple[str, ExchangeCode]:
        """Normalize inputs like 'RELIANCE.NS', 'TCS.BO', 'NSE:M&M', or 'BAJAJ-AUTO'."""
        cleaned = raw_symbol.strip().upper()
        exchange = default_exchange or ExchangeCode.NSE

        if cleaned.startswith("NSE:"):
            exchange = ExchangeCode.NSE
            cleaned = cleaned[4:]
        elif cleaned.startswith("BSE:"):
            exchange = ExchangeCode.BSE
            cleaned = cleaned[4:]
        elif cleaned.endswith(".NS"):
            exchange = ExchangeCode.NSE
            cleaned = cleaned[:-3]
        elif cleaned.endswith(".BO"):
            exchange = ExchangeCode.BSE
            cleaned = cleaned[:-3]

        self._ensure_supported_exchange(exchange)
        if not self.validate_symbol(cleaned, exchange):
            raise SymbolValidationError(
                f"Invalid Indian equity symbol {raw_symbol!r} for exchange {exchange.value}."
            )
        return cleaned, exchange

    def to_provider_symbol(self, instrument: Instrument, provider_code: str) -> str:
        """Map canonical India Instrument to provider symbol without mutating '&' or '-'."""
        self._ensure_supported_exchange(instrument.exchange_code)
        key = provider_code.strip().lower()
        if key in instrument.provider_symbols:
            return instrument.provider_symbols[key]

        if key in {"dev_yahoo", "yahoo"}:
            suffix = ".NS" if instrument.exchange_code == ExchangeCode.NSE else ".BO"
            return f"{instrument.symbol}{suffix}"
        if key in {"licensed_india", "kite", "upstox", "truedata", "mock"}:
            return f"{instrument.exchange_code.value}:{instrument.symbol}"
        return instrument.canonical_code

    def effective_tick_size(self, price: Decimal, instrument: Instrument) -> Decimal:
        """Apply NSE/SEBI tick size rules (0.01 under ₹250 if configured, else instrument tick_size)."""
        if instrument.tick_size == Decimal("0.05") and price < Decimal("250"):
            return Decimal("0.01")
        return instrument.tick_size

    def get_session_window(
        self,
        exchange: ExchangeCode,
        session_date: date,
        overrides: Iterable[CalendarOverride] | None = None,
    ) -> MarketSession:
        self._ensure_supported_exchange(exchange)
        tz = self.local_timezone()
        ov_map = self._index_overrides(exchange, overrides)
        override = ov_map.get(session_date)

        # Explicit DB/runtime override takes top priority (e.g., Diwali Muhurat Trading on Sunday)
        if override is not None:
            ov_type = override.override_type.upper()
            if ov_type == "HOLIDAY":
                return MarketSession(
                    market_code=self.market_code,
                    exchange_code=exchange,
                    session_date=session_date,
                    is_trading_day=False,
                    is_holiday=True,
                    is_early_close=False,
                    is_special_session=False,
                    reason=override.reason,
                    timezone_name=self.timezone_name,
                    open_utc=None,
                    close_utc=None,
                    pre_open_utc=None,
                    entry_start_utc=None,
                    entry_cutoff_utc=None,
                    session_5m_bars=0,
                )
            if ov_type in {"SPECIAL_SESSION", "EARLY_CLOSE"}:
                open_loc = override.open_local or self.REGULAR_OPEN_LOCAL
                close_loc = override.close_local or self.REGULAR_CLOSE_LOCAL
                open_dt = datetime.combine(session_date, open_loc, tzinfo=tz)
                close_dt = datetime.combine(session_date, close_loc, tzinfo=tz)
                duration_mins = max(5, int((close_dt - open_dt).total_seconds() // 60))
                pre_open_dt = open_dt - timedelta(minutes=15)
                entry_start = open_dt + timedelta(minutes=min(15, max(5, duration_mins // 4)))
                entry_cutoff = close_dt - timedelta(minutes=min(15, max(5, duration_mins // 4)))
                return MarketSession(
                    market_code=self.market_code,
                    exchange_code=exchange,
                    session_date=session_date,
                    is_trading_day=True,
                    is_holiday=False,
                    is_early_close=(ov_type == "EARLY_CLOSE"),
                    is_special_session=(ov_type == "SPECIAL_SESSION"),
                    reason=override.reason,
                    timezone_name=self.timezone_name,
                    open_utc=open_dt.astimezone(timezone.utc),
                    close_utc=close_dt.astimezone(timezone.utc),
                    pre_open_utc=pre_open_dt.astimezone(timezone.utc),
                    entry_start_utc=entry_start.astimezone(timezone.utc),
                    entry_cutoff_utc=entry_cutoff.astimezone(timezone.utc),
                    session_5m_bars=duration_mins // 5,
                )

        # Standard weekend closure
        if session_date.weekday() >= 5:
            return MarketSession(
                market_code=self.market_code,
                exchange_code=exchange,
                session_date=session_date,
                is_trading_day=False,
                is_holiday=False,
                is_early_close=False,
                is_special_session=False,
                reason="Weekend",
                timezone_name=self.timezone_name,
                open_utc=None,
                close_utc=None,
                pre_open_utc=None,
                entry_start_utc=None,
                entry_cutoff_utc=None,
                session_5m_bars=0,
            )

        # Built-in NSE/BSE holiday
        holiday_name = _INDIA_DEFAULT_HOLIDAYS.get(session_date)
        if holiday_name is not None:
            return MarketSession(
                market_code=self.market_code,
                exchange_code=exchange,
                session_date=session_date,
                is_trading_day=False,
                is_holiday=True,
                is_early_close=False,
                is_special_session=False,
                reason=holiday_name,
                timezone_name=self.timezone_name,
                open_utc=None,
                close_utc=None,
                pre_open_utc=None,
                entry_start_utc=None,
                entry_cutoff_utc=None,
                session_5m_bars=0,
            )

        open_dt = datetime.combine(session_date, self.REGULAR_OPEN_LOCAL, tzinfo=tz)
        close_dt = datetime.combine(session_date, self.REGULAR_CLOSE_LOCAL, tzinfo=tz)
        pre_open_dt = datetime.combine(session_date, self.PRE_OPEN_LOCAL, tzinfo=tz)
        entry_start_dt = open_dt + timedelta(minutes=self.ENTRY_START_OFFSET_MINUTES)
        entry_cutoff_dt = close_dt - timedelta(minutes=self.ENTRY_CUTOFF_BEFORE_CLOSE_MINUTES)

        return MarketSession(
            market_code=self.market_code,
            exchange_code=exchange,
            session_date=session_date,
            is_trading_day=True,
            is_holiday=False,
            is_early_close=False,
            is_special_session=False,
            reason="Regular Session",
            timezone_name=self.timezone_name,
            open_utc=open_dt.astimezone(timezone.utc),
            close_utc=close_dt.astimezone(timezone.utc),
            pre_open_utc=pre_open_dt.astimezone(timezone.utc),
            entry_start_utc=entry_start_dt.astimezone(timezone.utc),
            entry_cutoff_utc=entry_cutoff_dt.astimezone(timezone.utc),
            session_5m_bars=self.session_5m_bar_count,
        )

    def get_cost_model_bps(self) -> Decimal:
        """Transparent India intraday reference cost (STT + exchange + SEBI + stamp + slippage)."""
        return Decimal("15.0")
