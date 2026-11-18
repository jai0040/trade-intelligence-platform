"""Market status, indices, instrument lookup, and bar retrieval service."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from adapters.base import CalendarOverride
from adapters.registry import get_market_adapter
from app.core.config import Settings
from app.core.errors import APIError
from data_providers.base import MarketDataProvider
from data_providers.freshness import (
    ProviderHealthMonitor,
    evaluate_quote_freshness,
    filter_completed_bars,
)
from domain.errors import ProviderUnavailableError
from domain.models import (
    AssetType,
    DataFreshnessReport,
    ExchangeCode,
    Instrument,
    MarketCode,
    ProviderHealthStatus,
)
from database.models.markets import Exchange as DbExchange, MarketCalendarOverride

INDEX_SYMBOLS_BY_MARKET: dict[MarketCode, set[str]] = {
    MarketCode.IN: {"NIFTY50", "SENSEX", "BANKNIFTY"},
    MarketCode.US: {"SPY", "QQQ", "DIA"},
}


def load_calendar_overrides(db: DbSession | None) -> list[CalendarOverride]:
    """Load DB market_calendar_overrides rows into domain CalendarOverride objects."""
    if db is None:
        return []
    try:
        rows = db.execute(
            select(MarketCalendarOverride, DbExchange.code).join(
                DbExchange, MarketCalendarOverride.exchange_id == DbExchange.id
            )
        ).all()
    except Exception:
        return []

    overrides: list[CalendarOverride] = []
    for ov, exchange_code in rows:
        try:
            ex = ExchangeCode(exchange_code.upper())
        except ValueError:
            continue
        overrides.append(
            CalendarOverride(
                exchange_code=ex,
                session_date=ov.session_date,
                override_type=ov.override_type,
                reason=ov.reason,
                open_local=ov.open_local,
                close_local=ov.close_local,
            )
        )
    return overrides


def _probe_market_freshness(
    provider: MarketDataProvider,
    market_code: MarketCode,
    *,
    monitor: ProviderHealthMonitor,
    settings: Settings,
    now_utc: datetime,
) -> DataFreshnessReport:
    t0 = time.perf_counter()
    try:
        universe = provider.get_universe(market_code)
        probe_list = universe[:1]
        quotes = provider.get_quotes(probe_list, as_of_utc=now_utc) if probe_list else {}
        latency_ms = max(1, int((time.perf_counter() - t0) * 1000))
        monitor.record_success(
            provider.provider_code, market_code.value, latency_ms=latency_ms, now_utc=now_utc
        )
        sample_quote = next(iter(quotes.values()), None)
        return evaluate_quote_freshness(
            sample_quote,
            provider_code=provider.provider_code,
            now_utc=now_utc,
            max_age_seconds=settings.quote_stale_threshold_seconds,
            provider_status=ProviderHealthStatus.HEALTHY,
        )
    except ProviderUnavailableError as exc:
        rec = monitor.record_failure(
            provider.provider_code,
            market_code.value,
            error_message=exc.reason,
            now_utc=now_utc,
        )
        return DataFreshnessReport(
            provider=provider.provider_code,
            status=rec.status,
            last_quote_utc=None,
            delay_seconds=settings.quote_stale_threshold_seconds + 1,
            is_stale=True,
            stale_reason=exc.reason,
        )


def build_all_market_statuses(
    *,
    providers: dict[MarketCode, MarketDataProvider],
    monitor: ProviderHealthMonitor,
    settings: Settings,
    db: DbSession | None = None,
    now_utc: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now_utc or datetime.now(timezone.utc)
    overrides = load_calendar_overrides(db)
    results: list[dict[str, Any]] = []

    for market_code in (MarketCode.IN, MarketCode.US):
        adapter = get_market_adapter(market_code)
        provider = providers[market_code]
        freshness = _probe_market_freshness(
            provider, market_code, monitor=monitor, settings=settings, now_utc=now
        )
        local_dt = now.astimezone(adapter.local_timezone())
        for exchange in adapter.supported_exchanges:
            is_open, phase, session, next_open = adapter.get_live_session_phase(
                exchange, now, overrides=overrides
            )
            results.append(
                {
                    "market_code": market_code.value,
                    "exchange_code": exchange.value,
                    "is_open": is_open,
                    "session_phase": phase.value,
                    "timezone": adapter.timezone_name,
                    "local_time": local_dt.isoformat(),
                    "next_open_utc": next_open,
                    "session_reason": session.reason,
                    "session_5m_bars": session.session_5m_bars,
                    "data_freshness": {
                        "provider": freshness.provider,
                        "status": freshness.status.value,
                        "last_quote_utc": freshness.last_quote_utc,
                        "delay_seconds": freshness.delay_seconds,
                        "is_stale": freshness.is_stale,
                        "stale_reason": freshness.stale_reason,
                    },
                }
            )
    return results


def fetch_market_indices(
    market_code: MarketCode,
    *,
    providers: dict[MarketCode, MarketDataProvider],
    monitor: ProviderHealthMonitor,
    settings: Settings,
    now_utc: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now_utc or datetime.now(timezone.utc)
    provider = providers[market_code]
    t0 = time.perf_counter()
    try:
        universe = provider.get_universe(market_code)
        target_symbols = INDEX_SYMBOLS_BY_MARKET[market_code]
        benchmarks = [
            inst
            for inst in universe
            if inst.symbol in target_symbols or inst.asset_type == AssetType.INDEX.value
        ]
        quotes = provider.get_quotes(benchmarks, as_of_utc=now)
        latency_ms = max(1, int((time.perf_counter() - t0) * 1000))
        monitor.record_success(
            provider.provider_code, market_code.value, latency_ms=latency_ms, now_utc=now
        )
    except ProviderUnavailableError as exc:
        monitor.record_failure(
            provider.provider_code, market_code.value, error_message=exc.reason, now_utc=now
        )
        raise APIError(
            status_code=503,
            code="PROVIDER_UNAVAILABLE",
            message="Market data provider is currently unavailable. Data Unavailable.",
            details={"provider": provider.provider_code, "market_code": market_code.value},
        ) from exc

    snapshots: list[dict[str, Any]] = []
    for inst in benchmarks:
        quote = quotes.get(inst.instrument_id)
        if quote is None:
            continue
        freshness = evaluate_quote_freshness(
            quote,
            provider_code=provider.provider_code,
            now_utc=now,
            max_age_seconds=settings.quote_stale_threshold_seconds,
        )
        snapshots.append(
            {
                "instrument_id": inst.instrument_id,
                "market_code": inst.market_code.value,
                "exchange_code": inst.exchange_code.value,
                "symbol": inst.symbol,
                "canonical_code": inst.canonical_code,
                "company_name": inst.company_name,
                "currency": inst.currency,
                "last_price": quote.last_price,
                "prev_close": quote.prev_close,
                "change": quote.change,
                "change_pct": quote.change_pct.quantize(Decimal("0.01")),
                "quote_timestamp_utc": quote.quote_timestamp_utc,
                "source_provider": quote.source_provider,
                "is_delayed": quote.is_delayed,
                "delay_seconds": freshness.delay_seconds,
                "is_stale": freshness.is_stale,
            }
        )
    return snapshots


def search_instruments(
    query: str,
    *,
    market_filter: str,
    providers: dict[MarketCode, MarketDataProvider],
) -> list[Instrument]:
    needle = query.strip().upper()
    markets = (
        [MarketCode.IN, MarketCode.US]
        if market_filter.upper() == "ALL"
        else [MarketCode(market_filter.upper())]
    )
    matches: list[Instrument] = []
    for mkt in markets:
        try:
            universe = providers[mkt].get_universe(mkt)
        except ProviderUnavailableError:
            continue
        for inst in universe:
            if (
                needle in inst.symbol.upper()
                or needle in inst.canonical_code.upper()
                or needle in inst.company_name.upper()
            ):
                matches.append(inst)
    return matches[:50]


def fetch_instrument_bars(
    instrument_id: str,
    *,
    timeframe: str,
    limit: int,
    providers: dict[MarketCode, MarketDataProvider],
    monitor: ProviderHealthMonitor,
    settings: Settings,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    target: Instrument | None = None
    provider: MarketDataProvider | None = None

    for mkt in (MarketCode.IN, MarketCode.US):
        cand_provider = providers[mkt]
        try:
            for inst in cand_provider.get_universe(mkt):
                if inst.instrument_id == instrument_id or inst.canonical_code.upper() == instrument_id.upper():
                    target = inst
                    provider = cand_provider
                    break
        except ProviderUnavailableError:
            continue
        if target is not None:
            break

    if target is None or provider is None:
        raise APIError(status_code=404, code="NOT_FOUND", message="Instrument not found.")

    lookback_days = 150 if timeframe == "1d" else 7
    start_utc = now - timedelta(days=lookback_days)
    t0 = time.perf_counter()
    try:
        raw_bars = provider.get_bars(target, timeframe, start_utc, now)
        quotes = provider.get_quotes([target], as_of_utc=now)
        latency_ms = max(1, int((time.perf_counter() - t0) * 1000))
        monitor.record_success(
            provider.provider_code, target.market_code.value, latency_ms=latency_ms, now_utc=now
        )
    except ProviderUnavailableError as exc:
        monitor.record_failure(
            provider.provider_code, target.market_code.value, error_message=exc.reason, now_utc=now
        )
        raise APIError(
            status_code=503,
            code="PROVIDER_UNAVAILABLE",
            message="Market data provider is currently unavailable. Data Unavailable.",
            details={"provider": provider.provider_code},
        ) from exc

    completed = filter_completed_bars(raw_bars, as_of_utc=now)[-limit:]
    freshness = evaluate_quote_freshness(
        quotes.get(target.instrument_id),
        provider_code=provider.provider_code,
        now_utc=now,
        max_age_seconds=settings.quote_stale_threshold_seconds,
    )
    return {
        "instrument": {
            "instrument_id": target.instrument_id,
            "market_code": target.market_code.value,
            "exchange_code": target.exchange_code.value,
            "symbol": target.symbol,
            "canonical_code": target.canonical_code,
            "company_name": target.company_name,
            "asset_type": target.asset_type,
            "currency": target.currency,
            "tick_size": target.tick_size,
            "lot_size": target.lot_size,
            "sector": target.sector,
        },
        "timeframe": timeframe,
        "source_provider": provider.provider_code,
        "bar_count": len(completed),
        "data_freshness": {
            "provider": freshness.provider,
            "status": freshness.status.value,
            "last_quote_utc": freshness.last_quote_utc,
            "delay_seconds": freshness.delay_seconds,
            "is_stale": freshness.is_stale,
            "stale_reason": freshness.stale_reason,
        },
        "bars": [
            {
                "bar_start_utc": b.bar_start_utc,
                "bar_end_utc": b.bar_end_utc,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                "is_complete": b.is_complete,
            }
            for b in completed
        ],
    }
