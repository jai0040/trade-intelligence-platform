"""Phase 6 FastAPI integration tests: scanner, signals, position sizing, AI query, and kill switch."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("argon2")

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from database.models.identity import AuditLog, Role, User
from tests.conftest import build_test_app_context
from tests.integration.test_phase4_auth_and_isolation import _csrf_headers, _register_and_login


def test_signals_scanner_news_disclosures_sizing_and_ai_query_endpoints() -> None:
    ctx = build_test_app_context()
    with TestClient(ctx["app"]):
        client, _ = _register_and_login(ctx["app"], email="signals.user@example.com")

        # 1. Scanner hits across India & US
        scan_res = client.get("/api/v1/scanner/results", params={"market": "ALL"})
        assert scan_res.status_code == 200
        assert scan_res.json()["total"] > 0

        # 2. Published signals (strictly PASSED risk gate)
        sig_res = client.get("/api/v1/signals", params={"market": "ALL"})
        assert sig_res.status_code == 200
        items = sig_res.json()["items"]
        assert len(items) > 0
        assert all(s["risk_validation_status"] == "PASSED" for s in items)
        assert all(s["broker_ticket_preview"]["auto_executed"] is False for s in items)

        # 3. Signal detail endpoint
        first_id = items[0]["id"]
        detail = client.get(f"/api/v1/signals/{first_id}")
        assert detail.status_code == 200
        assert detail.json()["id"] == first_id

        # 4. Market news & US congressional disclosures
        assert client.get("/api/v1/news").status_code == 200
        congress = client.get("/api/v1/disclosures/congress")
        assert congress.status_code == 200
        assert congress.json()["market_code"] == "US"
        assert congress.json()["total"] >= 1

        # 5. Personal position sizing calculator (deterministic Decimal math, never places orders)
        sizing_res = client.post(
            "/api/v1/tools/position-size",
            json={
                "market_code": "IN",
                "exchange_code": "NSE",
                "symbol": "RELIANCE",
                "signal_type": "BUY",
                "entry_price": "2950.00",
                "stop_loss": "2900.00",
                "target_price": "3050.00",
                "capital_budget": "200000.00",
                "max_loss_amount": "2000.00",
            },
            headers=_csrf_headers(client),
        )
        assert sizing_res.status_code == 200
        sizing_body = sizing_res.json()
        assert sizing_body["order_placed"] is False
        assert sizing_body["risk_validation"]["status"] == "PASSED"
        assert sizing_body["sizing"]["recommended_shares"] == 16  # 25% of 200k = 50k / 2950 = 16

        # 6. Rate-limited AI Analyst query
        ai_res = client.post(
            "/api/v1/ai-analyst/query",
            json={"question": "Summarize today's best India setups", "market_code": "IN"},
            headers=_csrf_headers(client),
        )
        assert ai_res.status_code == 200
        assert "SIGNALS-ONLY" in ai_res.json()["disclaimer"]


def test_admin_kill_switch_halts_workflows_and_writes_audit_log() -> None:
    ctx = build_test_app_context()
    app = ctx["app"]

    with ctx["session_factory"]() as db:
        super_role = db.execute(select(Role).where(Role.code == "super_admin")).scalar_one()
        db.add(
            User(
                role_id=super_role.id,
                email="killswitch.admin@platform.local",
                password_hash=hash_password("SuperAdmin#2026!"),
                full_name="Kill Switch Admin",
                country_code="IN",
                is_active=True,
                is_email_verified=True,
            )
        )
        db.commit()

    with TestClient(app) as admin_client:
        login = admin_client.post(
            "/api/v1/auth/login",
            json={"email": "killswitch.admin@platform.local", "password": "SuperAdmin#2026!"},
        )
        assert login.status_code == 200

        # Trigger normal India workflow first -> SUCCEEDED
        ok_run = admin_client.post(
            "/api/v1/admin/workflows/trigger",
            json={"market_code": "IN", "mode": "orb"},
            headers=_csrf_headers(admin_client),
        )
        assert ok_run.status_code == 200
        assert ok_run.json()["status"] == "SUCCEEDED"
        before_count = admin_client.get("/api/v1/signals").json()["total"]
        assert before_count > 0

        # Activate Global Emergency Kill Switch
        ks_on = admin_client.post(
            "/api/v1/admin/kill-switch",
            json={"enabled": True, "reason": "Exchange feed anomaly drill"},
            headers=_csrf_headers(admin_client),
        )
        assert ks_on.status_code == 200
        assert ks_on.json()["enabled"] is True

        # Subsequent workflow trigger immediately aborts without deleting prior signals
        aborted = admin_client.post(
            "/api/v1/admin/workflows/trigger",
            json={"market_code": "US", "mode": "orb"},
            headers=_csrf_headers(admin_client),
        )
        assert aborted.status_code == 200
        assert aborted.json()["status"] == "ABORTED_KILL_SWITCH"
        assert admin_client.get("/api/v1/signals").json()["total"] == before_count

        # Verify immutable audit_logs entry
        with ctx["session_factory"]() as db:
            ks_audit = db.execute(
                select(AuditLog).where(AuditLog.action == "KILL_SWITCH_ENABLED")
            ).scalar_one_or_none()
            assert ks_audit is not None
