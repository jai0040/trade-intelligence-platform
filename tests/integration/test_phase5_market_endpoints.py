"""Phase 5 integration tests for /api/v1/markets/*, /instruments/*, and outage fail-safe responses."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("argon2")

from fastapi.testclient import TestClient

from data_providers.mock_provider import MockMarketDataProvider
from domain.models import MarketCode
from tests.conftest import build_test_app_context
from tests.integration.test_phase4_auth_and_isolation import _register_and_login


def test_markets_status_indices_search_and_bars_endpoints() -> None:
    ctx = build_test_app_context()
    with TestClient(ctx["app"]):
        client, _ = _register_and_login(ctx["app"], email="market.reader@example.com")

        # 1. Markets status returns NSE, BSE, NASDAQ, NYSE with freshness metadata
        status_res = client.get("/api/v1/markets/status")
        assert status_res.status_code == 200
        statuses = status_res.json()
        exchanges = {row["exchange_code"] for row in statuses}
        assert exchanges == {"NSE", "BSE", "NASDAQ", "NYSE"}
        assert all(row["data_freshness"]["provider"] == "mock" for row in statuses)

        # 2. India & US benchmark indices
        in_idx = client.get("/api/v1/markets/IN/indices")
        assert in_idx.status_code == 200
        assert {r["symbol"] for r in in_idx.json()} >= {"NIFTY50", "SENSEX", "BANKNIFTY"}

        us_idx = client.get("/api/v1/markets/US/indices")
        assert us_idx.status_code == 200
        assert {r["symbol"] for r in us_idx.json()} >= {"SPY", "QQQ", "DIA"}

        # 3. Search instruments (supports Indian M&M and US BRK.B)
        mm_res = client.get("/api/v1/instruments/search", params={"q": "M&M", "market": "IN"})
        assert mm_res.status_code == 200
        assert any(r["canonical_code"] == "NSE:M&M" for r in mm_res.json())

        brk_res = client.get("/api/v1/instruments/search", params={"q": "BRK.B", "market": "US"})
        assert brk_res.status_code == 200
        brk = next(r for r in brk_res.json() if r["canonical_code"] == "NYSE:BRK.B")

        # 4. Historical daily bars returned in chronological order with source provenance
        bars_res = client.get(
            f"/api/v1/instruments/{brk['instrument_id']}/bars",
            params={"timeframe": "1d", "limit": 30},
        )
        assert bars_res.status_code == 200
        payload = bars_res.json()
        assert payload["source_provider"] == "mock"
        assert payload["bar_count"] > 0
        assert all(b["is_complete"] is True for b in payload["bars"])


def test_provider_outage_returns_503_never_fabricates_prices() -> None:
    ctx = build_test_app_context()
    app = ctx["app"]
    with TestClient(app):
        client, _ = _register_and_login(app, email="outage.check@example.com")
        # Inject simulated outage into India provider
        app.state.market_providers[MarketCode.IN] = MockMarketDataProvider(
            simulate_outage=True, outage_reason="NSE feed timeout"
        )

        res = client.get("/api/v1/markets/IN/indices")
        assert res.status_code == 503
        assert res.json()["code"] == "PROVIDER_UNAVAILABLE"

        # Markets status degrades cleanly without crashing
        status_res = client.get("/api/v1/markets/status")
        assert status_res.status_code == 200
        nse_row = next(r for r in status_res.json() if r["exchange_code"] == "NSE")
        assert nse_row["data_freshness"]["is_stale"] is True
        assert nse_row["data_freshness"]["status"] in {"DEGRADED", "DOWN"}
