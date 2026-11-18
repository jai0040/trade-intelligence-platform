"""US equity market adapter (NASDAQ & NYSE, USD, America/New_York, 09:30-16:00 ET, 78 5m bars)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from adapters.base import CalendarOverride, MarketAdapter
from domain.errors import SymbolValidationError
from domain.models import ExchangeCode, Instrument, MarketCode, MarketSession

# US stocks & ETFs including dot share classes like BRK.B and BF.B
_US_SYMBOL_RE = re.compile(r"^[A-Z]{1,5}(?:\.[A-Z])?$")


def _observed_date(d: date) -> date:
    """NYSE/NASDAQ holiday observation rule: Saturday -> Friday, Sunday -> Monday."""
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    offset = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=offset)


def _good_friday(year: int) -> date:
    """Compute Good Friday using Anonymous Gregorian Computus algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    easter = date(year, month, day)
    return easter - timedelta(days=2)


def get_us_market_holidays(year: int) -> dict[date, str]:
    """Return full NYSE/NASDAQ holiday map for any calendar year."""
    holidays: dict[date, str] = {}

    new_years = _observed_date(date(year, 1, 1))
    if new_years.year == year:
        holidays[new_years] = "New Year's Day"
    # If Jan 1 of next year is Saturday, observed Friday Dec 31 is a holiday in current year
    next_ny = _observed_date(date(year + 1, 1, 1))
    if next_ny.year == year:
        holidays[next_ny] = "New Year's Day (Observed)"

    holidays[_nth_weekday(year, 1, 0, 3)] = "Martin Luther King Jr. Day"
    holidays[_nth_weekday(year, 2, 0, 3)] = "Washington's Birthday"
    holidays[_good_friday(year)] = "Good Friday"
    holidays[_last_weekday(year, 5, 0)] = "Memorial Day"
    if year >= 2022:
        holidays[_observed_date(date(year, 6, 19))] = "Juneteenth National Independence Day"
    holidays[_observed_date(date(year, 7, 4))] = "Independence Day"
    holidays[_nth_weekday(year, 9, 0, 1)] = "Labor Day"
    holidays[_nth_weekday(year, 11, 3, 4)] = "Thanksgiving Day"
    holidays[_observed_date(date(year, 12, 25))] = "Christmas Day"
    return holidays


def get_us_early_close_days(year: int) -> dict[date, str]:
    """Return standard NYSE/NASDAQ 13:00 ET early-close dates for any year."""
    early: dict[date, str] = {}
    holidays = get_us_market_holidays(year)

    # Day after Thanksgiving (Black Friday)
    black_friday = _nth_weekday(year, 11, 3, 4) + timedelta(days=1)
    early[black_friday] = "Day After Thanksgiving (13:00 ET Early Close)"

    # July 3 if weekday and not itself the observed July 4 holiday
    july_3 = date(year, 7, 3)
    if july_3.weekday() < 5 and july_3 not in holidays:
        early[july_3] = "Independence Day Eve (13:00 ET Early Close)"

    # Christmas Eve Dec 24 if weekday and not itself the observed Christmas holiday
    dec_24 = date(year, 12, 24)
    if dec_24.weekday() < 5 and dec_24 not in holidays:
        early[dec_24] = "Christmas Eve (13:00 ET Early Close)"

    return early


class USMarketAdapter(MarketAdapter):
    """Adapter encapsulating NASDAQ & NYSE hours, DST, holidays, early closes, and USD tick rules."""

    market_code = MarketCode.US
    currency = "USD"
    timezone_name = "America/New_York"
    supported_exchanges = (ExchangeCode.NASDAQ, ExchangeCode.NYSE)
    session_5m_bar_count = 78  # 09:30 to 16:00 ET = 390 minutes = 78 x 5m bars

    PRE_OPEN_LOCAL = time(4, 0)
    REGULAR_OPEN_LOCAL = time(9, 30)
    REGULAR_CLOSE_LOCAL = time(16, 0)
    EARLY_CLOSE_LOCAL = time(13, 0)
    ENTRY_START_OFFSET_MINUTES = 15  # 09:45 ET (after 15m opening range)
    ENTRY_CUTOFF_BEFORE_CLOSE_MINUTES = 30  # 15:30 ET (or 12:30 ET on early close)

    def validate_symbol(self, symbol: str, exchange: ExchangeCode = ExchangeCode.NASDAQ) -> bool:
        self._ensure_supported_exchange(exchange)
        cleaned = symbol.strip().upper()
        if not cleaned or " " in cleaned:
            return False
        return bool(_US_SYMBOL_RE.match(cleaned))

    def normalize_input_symbol(
        self, raw_symbol: str, default_exchange: ExchangeCode | None = ExchangeCode.NASDAQ
    ) -> tuple[str, ExchangeCode]:
        """Normalize inputs like 'NASDAQ:TSLA', 'NYSE:BRK.B', or Yahoo-style 'BRK-B'."""
        cleaned = raw_symbol.strip().upper()
        exchange = default_exchange or ExchangeCode.NASDAQ

        if cleaned.startswith("NASDAQ:"):
            exchange = ExchangeCode.NASDAQ
            cleaned = cleaned[7:]
        elif cleaned.startswith("NYSE:"):
            exchange = ExchangeCode.NYSE
            cleaned = cleaned[5:]

        # Convert Yahoo hyphen class share suffix (BRK-B) back to canonical dot form (BRK.B)
        if re.match(r"^[A-Z]{1,5}-[A-Z]$", cleaned):
            cleaned = cleaned.replace("-", ".")

        self._ensure_supported_exchange(exchange)
        if not self.validate_symbol(cleaned, exchange):
            raise SymbolValidationError(
                f"Invalid US equity symbol {raw_symbol!r} for exchange {exchange.value}."
            )
        return cleaned, exchange

    def to_provider_symbol(self, instrument: Instrument, provider_code: str) -> str:
        """Map canonical US Instrument to provider symbol (only Yahoo converts '.' to '-')."""
        self._ensure_supported_exchange(instrument.exchange_code)
        key = provider_code.strip().lower()
        if key in instrument.provider_symbols:
            return instrument.provider_symbols[key]

        if key in {"dev_yahoo", "yahoo"}:
            return instrument.symbol.replace(".", "-")
        if key in {"polygon", "databento", "alpaca", "licensed_us"}:
            return instrument.symbol
        if key == "mock":
            return f"{instrument.exchange_code.value}:{instrument.symbol}"
        return instrument.symbol

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
            if ov_type in {"EARLY_CLOSE", "SPECIAL_SESSION"}:
                open_loc = override.open_local or self.REGULAR_OPEN_LOCAL
                close_loc = override.close_local or self.EARLY_CLOSE_LOCAL
                open_dt = datetime.combine(session_date, open_loc, tzinfo=tz)
                close_dt = datetime.combine(session_date, close_loc, tzinfo=tz)
                pre_open_dt = datetime.combine(session_date, self.PRE_OPEN_LOCAL, tzinfo=tz)
                duration_mins = max(5, int((close_dt - open_dt).total_seconds() // 60))
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
                    entry_start_utc=(open_dt + timedelta(minutes=15)).astimezone(timezone.utc),
                    entry_cutoff_utc=(close_dt - timedelta(minutes=30)).astimezone(timezone.utc),
                    session_5m_bars=duration_mins // 5,
                )

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

        holidays = get_us_market_holidays(session_date.year)
        if session_date in holidays:
            return MarketSession(
                market_code=self.market_code,
                exchange_code=exchange,
                session_date=session_date,
                is_trading_day=False,
                is_holiday=True,
                is_early_close=False,
                is_special_session=False,
                reason=holidays[session_date],
                timezone_name=self.timezone_name,
                open_utc=None,
                close_utc=None,
                pre_open_utc=None,
                entry_start_utc=None,
                entry_cutoff_utc=None,
                session_5m_bars=0,
            )

        early_days = get_us_early_close_days(session_date.year)
        is_early = session_date in early_days
        close_loc = self.EARLY_CLOSE_LOCAL if is_early else self.REGULAR_CLOSE_LOCAL
        reason = early_days[session_date] if is_early else "Regular Session"

        open_dt = datetime.combine(session_date, self.REGULAR_OPEN_LOCAL, tzinfo=tz)
        close_dt = datetime.combine(session_date, close_loc, tzinfo=tz)
        pre_open_dt = datetime.combine(session_date, self.PRE_OPEN_LOCAL, tzinfo=tz)
        duration_mins = int((close_dt - open_dt).total_seconds() // 60)

        return MarketSession(
            market_code=self.market_code,
            exchange_code=exchange,
            session_date=session_date,
            is_trading_day=True,
            is_holiday=False,
            is_early_close=is_early,
            is_special_session=False,
            reason=reason,
            timezone_name=self.timezone_name,
            open_utc=open_dt.astimezone(timezone.utc),
            close_utc=close_dt.astimezone(timezone.utc),
            pre_open_utc=pre_open_dt.astimezone(timezone.utc),
            entry_start_utc=(
                open_dt + timedelta(minutes=self.ENTRY_START_OFFSET_MINUTES)
            ).astimezone(timezone.utc),
            entry_cutoff_utc=(
                close_dt - timedelta(minutes=self.ENTRY_CUTOFF_BEFORE_CLOSE_MINUTES)
            ).astimezone(timezone.utc),
            session_5m_bars=duration_mins // 5,
        )

    def get_cost_model_bps(self) -> Decimal:
        """Transparent US intraday reference cost (spread + slippage + SEC/TAF fees)."""
        return Decimal("8.0")
