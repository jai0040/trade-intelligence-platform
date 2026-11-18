"""Signals, Scanner, News, Congressional Disclosures, Position-Sizing Tool, and AI Analyst REST router."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session as DbSession

from adapters.registry import get_market_adapter
from ai_analyst.service import STANDARD_DISCLAIMER
from app.authentication.dependencies import (
    AuthContext,
    get_current_auth,
    get_db,
    get_redis,
    require_csrf,
)
from app.core.errors import APIError
from app.core.rate_limit import enforce_rate_limit
from app.signals.schemas import (
    AIAnalystQueryRequest,
    AIAnalystQueryResponse,
    PositionSizeRequest,
    PositionSizeResponse,
)
from app.signals.service import SignalsEngineHub, read_kill_switch
from domain.models import ExchangeCode, Instrument, MarketCode
from risk_engine.validator import validate_signal_risk
from skill_wrappers.budget_wrapper import calculate_position_size

router = APIRouter(tags=["signals"])


def _get_hub(request: Request) -> SignalsEngineHub:
    hub: SignalsEngineHub = request.app.state.signals_hub
    providers = getattr(request.app.state, "market_providers", {})
    redis_client = getattr(request.app.state, "redis_client", None)
    kill_active = read_kill_switch(None, redis_client)
    hub.ensure_seeded_from_providers(providers=providers, kill_switch_active=kill_active)
    return hub


@router.get("/scanner/results")
def get_scanner_results(
    request: Request,
    market: Literal["ALL", "IN", "US"] = Query(default="ALL"),
    mode: Literal["daily", "orb", "all"] = Query(default="all"),
    setup: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _auth: AuthContext = Depends(get_current_auth),
) -> dict[str, Any]:
    """Return paginated stock scanner hits with market, setup, liquidity, and freshness metadata."""
    hub = _get_hub(request)
    hits = list(hub.scanner_hits)
    if market != "ALL":
        hits = [h for h in hits if h["market_code"] == market]
    if mode != "all":
        hits = [h for h in hits if h["mode"] == mode]
    if setup:
        hits = [h for h in hits if h["setup_type"].lower() == setup.lower()]

    total = len(hits)
    start = (page - 1) * page_size
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": hits[start : start + page_size],
    }


@router.get("/signals")
def list_signals(
    request: Request,
    market: Literal["ALL", "IN", "US"] = Query(default="ALL"),
    signal_type: Literal["BUY", "SELL", "WATCH"] | None = Query(default=None),
    status: str | None = Query(default=None),
    strategy: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _auth: AuthContext = Depends(get_current_auth),
) -> dict[str, Any]:
    """List published trading signals (strictly risk-PASSED signals for subscribers)."""
    hub = _get_hub(request)
    items = hub.list_published_signals(
        market=market,
        signal_type=signal_type,
        status=status,
        strategy=strategy,
        search=search,
    )
    total = len(items)
    start = (page - 1) * page_size
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": items[start : start + page_size],
    }


@router.get("/signals/performance/summary")
def get_signals_performance_summary(
    request: Request,
    market: Literal["ALL", "IN", "US"] = Query(default="ALL"),
    _auth: AuthContext = Depends(get_current_auth),
) -> dict[str, Any]:
    """Return historical signal outcome analytics with documented gross/net methodology."""
    hub = _get_hub(request)
    return hub.performance_summary(market=market)


@router.get("/signals/{signal_id}")
def get_signal_detail(
    signal_id: str,
    request: Request,
    _auth: AuthContext = Depends(get_current_auth),
) -> dict[str, Any]:
    """Return detailed immutable signal snapshot and read-only broker ticket preview."""
    hub = _get_hub(request)
    sig = hub.signals_by_id.get(signal_id)
    if sig is None or sig.get("risk_validation_status") != "PASSED":
        raise APIError(status_code=404, code="NOT_FOUND", message="Trading signal not found.")
    return sig


@router.get("/news")
def list_market_news(
    request: Request,
    market: Literal["ALL", "IN", "US"] = Query(default="ALL"),
    symbol: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    _auth: AuthContext = Depends(get_current_auth),
) -> dict[str, Any]:
    """Return market news and regulatory filings (SEC 8-K / NSE-BSE announcements)."""
    hub = _get_hub(request)
    items = list(hub.news_items)
    if market != "ALL":
        items = [n for n in items if n["market_code"] == market]
    if symbol:
        needle = symbol.strip().upper()
        items = [n for n in items if n["symbol"].upper() == needle]
    return {"total": len(items), "items": items[:limit]}


@router.get("/disclosures/congress")
def list_congress_disclosures(
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
    _auth: AuthContext = Depends(get_current_auth),
) -> dict[str, Any]:
    """Return US Congressional PTR disclosures (trader-pelosi, US market only, with disclosure lag)."""
    hub = _get_hub(request)
    return {
        "market_code": "US",
        "stock_act_notice": "US House Clerk PTR filings may carry up to a 45-day statutory disclosure lag.",
        "total": len(hub.congress_disclosures),
        "items": hub.congress_disclosures[:limit],
    }


@router.post(
    "/tools/position-size",
    response_model=PositionSizeResponse,
    dependencies=[Depends(require_csrf)],
)
def position_size_calculator(
    payload: PositionSizeRequest,
    _auth: AuthContext = Depends(get_current_auth),
) -> PositionSizeResponse:
    """Deterministic personal position sizing calculator (trader-budget + trader-risk; zero order placement)."""
    mkt = MarketCode(payload.market_code)
    ex = ExchangeCode(payload.exchange_code)
    adapter = get_market_adapter(mkt)
    currency = "INR" if mkt == MarketCode.IN else "USD"
    tick = Decimal("0.05") if mkt == MarketCode.IN else Decimal("0.01")

    symbol_clean = payload.symbol.strip().upper()
    inst = Instrument(
        instrument_id=f"calc-{ex.value}-{symbol_clean}",
        market_code=mkt,
        exchange_code=ex,
        symbol=symbol_clean,
        canonical_code=f"{ex.value}:{symbol_clean}",
        company_name=symbol_clean,
        asset_type="EQUITY",
        currency=currency,
        tick_size=tick,
        lot_size=payload.lot_size,
    )

    try:
        sizing = calculate_position_size(
            entry_price=payload.entry_price,
            stop_loss=payload.stop_loss,
            capital_budget=payload.capital_budget,
            max_loss_amount=payload.max_loss_amount,
            max_position_pct=payload.max_position_pct,
            lot_size=payload.lot_size,
            currency=currency,
        )
    except ValueError as exc:
        raise APIError(status_code=422, code="VALIDATION_ERROR", message=str(exc)) from exc

    risk_per_share = abs(payload.entry_price - payload.stop_loss)
    reward_per_share = abs(payload.target_price - payload.entry_price)
    rr_ratio = (reward_per_share / risk_per_share).quantize(Decimal("0.001"))

    risk_res = validate_signal_risk(
        instrument=inst,
        market_adapter=adapter,
        signal_type=payload.signal_type,
        entry_price=payload.entry_price,
        stop_loss=payload.stop_loss,
        target_price=payload.target_price,
        risk_reward_ratio=rr_ratio,
        quote_is_stale=False,
        as_of_utc=datetime.now(timezone.utc),
        recommended_shares=sizing["recommended_shares"],
    )

    return PositionSizeResponse(
        sizing={k: str(v) if isinstance(v, Decimal) else v for k, v in sizing.items()},
        risk_validation={
            "status": risk_res.status,
            "passed": risk_res.passed,
            "blocking_reasons": risk_res.blocking_reasons,
            "warnings": risk_res.warnings,
            "checks": risk_res.checks,
            "risk_fingerprint": risk_res.risk_fingerprint,
        },
        disclaimer=STANDARD_DISCLAIMER,
    )


@router.post(
    "/ai-analyst/query",
    response_model=AIAnalystQueryResponse,
    dependencies=[Depends(require_csrf)],
)
def ai_analyst_query(
    payload: AIAnalystQueryRequest,
    request: Request,
    auth: AuthContext = Depends(get_current_auth),
    redis_client: Any | None = Depends(get_redis),
) -> AIAnalystQueryResponse:
    """Rate-limited AI explanation query over deterministic risk-validated signals."""
    enforce_rate_limit(
        redis_client,
        scope="ai_analyst_query",
        identifier=str(auth.user.id),
        limit=20,
        window_seconds=3600,
    )
    hub = _get_hub(request)
    signals = hub.list_published_signals(market=payload.market_code)
    result = hub.ai_analyst.answer_user_query(
        question=payload.question,
        context_signals=signals,
        market_code=payload.market_code,
    )
    return AIAnalystQueryResponse(**result)
