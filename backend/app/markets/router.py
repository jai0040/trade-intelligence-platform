"""Market status, benchmark indices, instrument search, and OHLCV bars REST router."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session as DbSession

from app.authentication.dependencies import AuthContext, get_app_settings, get_current_auth, get_db
from app.core.config import Settings
from app.markets.schemas import (
    IndexSnapshotResponse,
    InstrumentBarsResponse,
    InstrumentSummaryResponse,
    MarketStatusResponse,
)
from app.markets.service import (
    build_all_market_statuses,
    fetch_instrument_bars,
    fetch_market_indices,
    search_instruments,
)
from data_providers.base import MarketDataProvider
from data_providers.freshness import ProviderHealthMonitor
from domain.models import MarketCode

router = APIRouter(tags=["markets"])


def _get_providers(request: Request) -> dict[MarketCode, MarketDataProvider]:
    return request.app.state.market_providers


def _get_health_monitor(request: Request) -> ProviderHealthMonitor:
    return request.app.state.provider_health_monitor


@router.get("/markets/status", response_model=list[MarketStatusResponse])
def get_markets_status(
    request: Request,
    _auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> list[MarketStatusResponse]:
    """Live open/closed status, session phases, and data freshness for India & US exchanges."""
    rows = build_all_market_statuses(
        providers=_get_providers(request),
        monitor=_get_health_monitor(request),
        settings=settings,
        db=db,
    )
    return [MarketStatusResponse(**row) for row in rows]


@router.get("/markets/{market_code}/indices", response_model=list[IndexSnapshotResponse])
def get_market_indices(
    market_code: Literal["IN", "US"],
    request: Request,
    _auth: AuthContext = Depends(get_current_auth),
    settings: Settings = Depends(get_app_settings),
) -> list[IndexSnapshotResponse]:
    """Benchmark indices for India (NIFTY 50, SENSEX, BANKNIFTY) or US (SPY, QQQ, DIA)."""
    rows = fetch_market_indices(
        MarketCode(market_code),
        providers=_get_providers(request),
        monitor=_get_health_monitor(request),
        settings=settings,
    )
    return [IndexSnapshotResponse(**row) for row in rows]


@router.get("/instruments/search", response_model=list[InstrumentSummaryResponse])
def search_instruments_endpoint(
    request: Request,
    q: str = Query(..., min_length=1, max_length=40),
    market: Literal["ALL", "IN", "US"] = Query(default="ALL"),
    _auth: AuthContext = Depends(get_current_auth),
) -> list[InstrumentSummaryResponse]:
    """Search active equities, ETFs, and indices across India and US markets."""
    matches = search_instruments(q, market_filter=market, providers=_get_providers(request))
    return [
        InstrumentSummaryResponse(
            instrument_id=inst.instrument_id,
            market_code=inst.market_code.value,
            exchange_code=inst.exchange_code.value,
            symbol=inst.symbol,
            canonical_code=inst.canonical_code,
            company_name=inst.company_name,
            asset_type=inst.asset_type,
            currency=inst.currency,
            tick_size=inst.tick_size,
            lot_size=inst.lot_size,
            sector=inst.sector,
        )
        for inst in matches
    ]


@router.get("/instruments/{instrument_id}/bars", response_model=InstrumentBarsResponse)
def get_instrument_bars_endpoint(
    instrument_id: str,
    request: Request,
    timeframe: Literal["1m", "5m", "15m", "1d"] = Query(default="5m"),
    limit: int = Query(default=200, ge=10, le=1000),
    _auth: AuthContext = Depends(get_current_auth),
    settings: Settings = Depends(get_app_settings),
) -> InstrumentBarsResponse:
    """Return ordered completed OHLCV bars with provenance and freshness metadata."""
    payload = fetch_instrument_bars(
        instrument_id,
        timeframe=timeframe,
        limit=limit,
        providers=_get_providers(request),
        monitor=_get_health_monitor(request),
        settings=settings,
    )
    return InstrumentBarsResponse(**payload)
