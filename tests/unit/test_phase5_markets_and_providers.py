"""Phase 5 unit tests: Market adapters, calendars (DST/early-close/NSE/Muhurat), symbols, and data providers."""

from __future__ import annotations

import ast
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "backend"), str(ROOT / "trading-engine")):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_all_phase5_files_compile_cleanly() -> None:
    targets: list[Path] = []
    for folder in ("trading-engine/domain", "trading-engine/adapters", "trading-engine/data_providers", "backend/app/markets"):
        for py_file in (ROOT / folder).rglob("*.py"):
            targets.append(py_file)
    assert len(targets) >= 15
    for py_file in targets:
        ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))


def test_india_calendar_75_bars_holidays_and_muhurat_override() -> None:
    from adapters.base import CalendarOverride
    from adapters.india.adapter import IndiaMarketAdapter
    from domain.models import ExchangeCode, SessionPhase

    adapter = IndiaMarketAdapter()

    # Regular weekday (Wed 2026-11-18): 09:15-15:30 IST == 03:45-10:00 UTC (75 five-minute bars)
    reg = adapter.get_session_window(ExchangeCode.NSE, date(2026, 11, 18))
    assert reg.is_trading_day is True
    assert reg.session_5m_bars == 75
    assert reg.open_utc == datetime(2026, 11, 18, 3, 45, tzinfo=timezone.utc)
    assert reg.close_utc == datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc)
    assert reg.entry_start_utc == datetime(2026, 11, 18, 4, 0, tzinfo=timezone.utc)   # 09:30 IST
    assert reg.entry_cutoff_utc == datetime(2026, 11, 18, 9, 30, tzinfo=timezone.utc)  # 15:00 IST

    # Entry window checks
    ok_open, _ = adapter.is_within_entry_window(
        ExchangeCode.NSE, datetime(2026, 11, 18, 3, 50, tzinfo=timezone.utc)  # 09:20 IST (ORB forming)
    )
    assert ok_open is False
    ok_mid, _ = adapter.is_within_entry_window(
        ExchangeCode.NSE, datetime(2026, 11, 18, 5, 0, tzinfo=timezone.utc)  # 10:30 IST
    )
    assert ok_mid is True
    ok_late, _ = adapter.is_within_entry_window(
        ExchangeCode.NSE, datetime(2026, 11, 18, 9, 40, tzinfo=timezone.utc)  # 15:10 IST (past cutoff)
    )
    assert ok_late is False

    # Republic Day holiday (Mon 2026-01-26)
    hol = adapter.get_session_window(ExchangeCode.NSE, date(2026, 1, 26))
    assert hol.is_trading_day is False
    assert hol.is_holiday is True
    assert "Republic Day" in hol.reason

    # Weekend Sunday normally closed, but Muhurat Trading SPECIAL_SESSION override opens 18:00-19:00 IST
    muhurat_date = date(2026, 11, 8)  # Sunday
    assert adapter.get_session_window(ExchangeCode.NSE, muhurat_date).is_trading_day is False

    muhurat_override = [
        CalendarOverride(
            exchange_code=ExchangeCode.NSE,
            session_date=muhurat_date,
            override_type="SPECIAL_SESSION",
            open_local=time(18, 0),
            close_local=time(19, 0),
            reason="Diwali Muhurat Trading",
        )
    ]
    muhurat_sess = adapter.get_session_window(ExchangeCode.NSE, muhurat_date, overrides=muhurat_override)
    assert muhurat_sess.is_trading_day is True
    assert muhurat_sess.is_special_session is True
    assert muhurat_sess.session_5m_bars == 12
    assert muhurat_sess.open_utc == datetime(2026, 11, 8, 12, 30, tzinfo=timezone.utc)
    assert muhurat_sess.close_utc == datetime(2026, 11, 8, 13, 30, tzinfo=timezone.utc)

    is_open, phase, _, _ = adapter.get_live_session_phase(
        ExchangeCode.NSE,
        datetime(2026, 11, 8, 12, 45, tzinfo=timezone.utc),  # 18:15 IST
        overrides=muhurat_override,
    )
    assert is_open is True
    assert phase == SessionPhase.REGULAR


def test_us_calendar_dst_78_bars_holidays_and_early_close() -> None:
    from adapters.usa.adapter import USMarketAdapter
    from domain.models import ExchangeCode, SessionPhase

    adapter = USMarketAdapter()

    # Winter EST (UTC-5): Wed 2026-01-14 -> 09:30-16:00 EST == 14:30-21:00 UTC (78 5m bars)
    winter = adapter.get_session_window(ExchangeCode.NASDAQ, date(2026, 1, 14))
    assert winter.is_trading_day is True
    assert winter.session_5m_bars == 78
    assert winter.open_utc == datetime(2026, 1, 14, 14, 30, tzinfo=timezone.utc)
    assert winter.close_utc == datetime(2026, 1, 14, 21, 0, tzinfo=timezone.utc)

    # Summer EDT (UTC-4): Wed 2026-07-15 -> 09:30-16:00 EDT == 13:30-20:00 UTC (78 5m bars)
    summer = adapter.get_session_window(ExchangeCode.NYSE, date(2026, 7, 15))
    assert summer.is_trading_day is True
    assert summer.session_5m_bars == 78
    assert summer.open_utc == datetime(2026, 7, 15, 13, 30, tzinfo=timezone.utc)
    assert summer.close_utc == datetime(2026, 7, 15, 20, 0, tzinfo=timezone.utc)

    # Good Friday 2026 (2026-04-03) and Thanksgiving 2026 (2026-11-26) are holidays
    gf = adapter.get_session_window(ExchangeCode.NYSE, date(2026, 4, 3))
    assert gf.is_trading_day is False and gf.is_holiday is True
    tg = adapter.get_session_window(ExchangeCode.NASDAQ, date(2026, 11, 26))
    assert tg.is_trading_day is False and tg.is_holiday is True

    # Day after Thanksgiving 2026 (2026-11-27) -> Early close 13:00 EST == 18:00 UTC (42 5m bars)
    bf = adapter.get_session_window(ExchangeCode.NYSE, date(2026, 11, 27))
    assert bf.is_trading_day is True
    assert bf.is_early_close is True
    assert bf.session_5m_bars == 42
    assert bf.close_utc == datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc)

    is_open, phase, _, _ = adapter.get_live_session_phase(
        ExchangeCode.NYSE, datetime(2026, 11, 27, 16, 0, tzinfo=timezone.utc)  # 11:00 EST
    )
    assert is_open is True
    assert phase == SessionPhase.EARLY_CLOSE


def test_symbol_normalization_provider_mapping_and_tick_rounding() -> None:
    from adapters.india.adapter import IndiaMarketAdapter
    from adapters.usa.adapter import USMarketAdapter
    from domain.errors import SymbolValidationError
    from domain.models import ExchangeCode, Instrument, MarketCode

    in_adapter = IndiaMarketAdapter()
    us_adapter = USMarketAdapter()

    # India symbol normalization preserves '&' and '-' and handles .NS / .BO cleanly
    assert in_adapter.normalize_input_symbol("RELIANCE.NS") == ("RELIANCE", ExchangeCode.NSE)
    assert in_adapter.normalize_input_symbol("TCS.BO") == ("TCS", ExchangeCode.BSE)
    assert in_adapter.normalize_input_symbol("NSE:M&M") == ("M&M", ExchangeCode.NSE)
    assert in_adapter.normalize_input_symbol("BAJAJ-AUTO") == ("BAJAJ-AUTO", ExchangeCode.NSE)

    try:
        in_adapter.normalize_input_symbol("BAD SYMBOL!")
        raise AssertionError("Expected SymbolValidationError")
    except SymbolValidationError:
        pass

    # US symbol normalization handles BRK.B and Yahoo BRK-B -> canonical BRK.B
    assert us_adapter.normalize_input_symbol("NYSE:BRK.B") == ("BRK.B", ExchangeCode.NYSE)
    assert us_adapter.normalize_input_symbol("BRK-B", ExchangeCode.NYSE) == ("BRK.B", ExchangeCode.NYSE)

    # Provider symbol mapping never mutates canonical symbols globally
    mm = Instrument(
        instrument_id="id-mm",
        market_code=MarketCode.IN,
        exchange_code=ExchangeCode.NSE,
        symbol="M&M",
        canonical_code="NSE:M&M",
        company_name="Mahindra & Mahindra",
        asset_type="EQUITY",
        currency="INR",
        tick_size=Decimal("0.05"),
    )
    assert in_adapter.to_provider_symbol(mm, "dev_yahoo") == "M&M.NS"
    assert in_adapter.to_provider_symbol(mm, "licensed_india") == "NSE:M&M"

    brk = Instrument(
        instrument_id="id-brk",
        market_code=MarketCode.US,
        exchange_code=ExchangeCode.NYSE,
        symbol="BRK.B",
        canonical_code="NYSE:BRK.B",
        company_name="Berkshire Hathaway B",
        asset_type="EQUITY",
        currency="USD",
        tick_size=Decimal("0.01"),
    )
    assert us_adapter.to_provider_symbol(brk, "polygon") == "BRK.B"
    assert us_adapter.to_provider_symbol(brk, "dev_yahoo") == "BRK-B"

    # Tick-size rounding (exact Decimal math)
    assert in_adapter.round_to_tick(Decimal("2941.23"), mm, "down") == Decimal("2941.20")
    assert in_adapter.round_to_tick(Decimal("2941.23"), mm, "up") == Decimal("2941.25")
    # NSE sub-₹250 ₹0.01 tick size rule
    assert in_adapter.round_to_tick(Decimal("124.567"), mm, "down") == Decimal("124.56")
    # US $0.01 tick size
    assert us_adapter.round_to_tick(Decimal("468.254"), brk, "down") == Decimal("468.25")
    assert us_adapter.round_to_tick(Decimal("468.254"), brk, "up") == Decimal("468.26")


def test_mock_provider_deterministic_bars_freshness_outage_and_production_guard() -> None:
    from data_providers.factory import build_market_data_provider
    from data_providers.freshness import (
        ProviderHealthMonitor,
        assert_fresh_quote,
        evaluate_quote_freshness,
        filter_completed_bars,
    )
    from data_providers.mock_provider import MockMarketDataProvider
    from domain.errors import (
        CommercialProviderPolicyError,
        ProviderUnavailableError,
        StaleDataError,
    )
    from domain.models import MarketCode, OHLCVBar, ProviderHealthStatus

    # 1. Production commercial guardrail blocks mock & dev_yahoo
    for forbidden in ("mock", "dev_yahoo"):
        try:
            build_market_data_provider(forbidden, app_env="production")
            raise AssertionError(f"Expected CommercialProviderPolicyError for {forbidden} in production")
        except CommercialProviderPolicyError:
            pass

    # 2. Unconfigured commercial provider fails closed (never fabricates prices)
    prod_in = build_market_data_provider("licensed_india", app_env="production")
    assert prod_in.is_commercial_licensed is True
    try:
        prod_in.get_universe(MarketCode.IN)
        raise AssertionError("Expected ProviderUnavailableError when credentials unconfigured")
    except ProviderUnavailableError:
        pass

    # 3. Mock provider generates full 75 (NSE) and 78 (NASDAQ) 5m bars cleanly
    mock = MockMarketDataProvider(simulated_delay_seconds=5)
    in_univ = mock.get_universe(MarketCode.IN)
    us_univ = mock.get_universe(MarketCode.US)
    assert any(i.symbol == "M&M" for i in in_univ)
    assert any(i.symbol == "BRK.B" for i in us_univ)

    reliance = mock.get_instrument_by_code("NSE:RELIANCE")
    tsla = mock.get_instrument_by_code("NASDAQ:TSLA")
    assert reliance is not None and tsla is not None

    in_bars = mock.get_bars(
        reliance,
        "5m",
        datetime(2026, 11, 18, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc),
    )
    assert len(in_bars) == 75
    assert all(b.is_complete for b in in_bars)

    us_bars = mock.get_bars(
        tsla,
        "5m",
        datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 18, 22, 0, tzinfo=timezone.utc),
    )
    assert len(us_bars) == 78

    # 4. Forming bar filter strips incomplete bars
    forming_bar = OHLCVBar(
        instrument_id=tsla.instrument_id,
        timeframe="5m",
        bar_start_utc=datetime(2026, 11, 18, 21, 0, tzinfo=timezone.utc),
        bar_end_utc=datetime(2026, 11, 18, 21, 5, tzinfo=timezone.utc),
        open=Decimal("365.00"),
        high=Decimal("366.00"),
        low=Decimal("364.50"),
        close=Decimal("365.80"),
        volume=1000,
        is_complete=False,
        source_provider="mock",
        fetched_at_utc=datetime(2026, 11, 18, 21, 2, tzinfo=timezone.utc),
    )
    filtered = filter_completed_bars(us_bars + [forming_bar])
    assert len(filtered) == 78

    # 5. Quote freshness & staleness rejection guard
    now = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)
    quotes = mock.get_quotes([reliance], as_of_utc=now)
    q = quotes[reliance.instrument_id]
    assert assert_fresh_quote(q, now_utc=now, max_age_seconds=900) == q

    stale_mock = MockMarketDataProvider(simulated_delay_seconds=1200)
    stale_q = stale_mock.get_quotes([reliance], as_of_utc=now)[reliance.instrument_id]
    report = evaluate_quote_freshness(
        stale_q, provider_code="mock", now_utc=now, max_age_seconds=900
    )
    assert report.is_stale is True
    assert report.status == ProviderHealthStatus.DEGRADED
    try:
        assert_fresh_quote(stale_q, now_utc=now, max_age_seconds=900)
        raise AssertionError("Expected StaleDataError for 1200s delayed quote")
    except StaleDataError:
        pass

    # 6. Simulated outage raises ProviderUnavailableError and trips ProviderHealthMonitor to DOWN
    outage_mock = MockMarketDataProvider(simulate_outage=True, outage_reason="Upstream 503")
    monitor = ProviderHealthMonitor(degraded_threshold=1, down_threshold=3)
    for expected_status in (
        ProviderHealthStatus.DEGRADED,
        ProviderHealthStatus.DEGRADED,
        ProviderHealthStatus.DOWN,
    ):
        try:
            outage_mock.get_quotes([reliance], as_of_utc=now)
            raise AssertionError("Expected ProviderUnavailableError")
        except ProviderUnavailableError as exc:
            rec = monitor.record_failure("mock", "IN", error_message=exc.reason, now_utc=now)
            assert rec.status == expected_status
