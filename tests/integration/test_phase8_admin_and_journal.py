"""Phase 8 integration tests: User-isolated Trading Journal, Realized P&L, and Super Admin control plane."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("argon2")

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from database.models.identity import Role, User
from tests.conftest import build_test_app_context
from tests.integration.test_phase4_auth_and_isolation import _csrf_headers, _register_and_login


def test_trading_journal_crud_and_tenant_isolation() -> None:
    ctx = build_test_app_context()
    app = ctx["app"]
    rel_id = str(ctx["seed_ids"]["reliance_id"])

    with TestClient(app):
        client_a, _ = _register_and_login(app, email="trader.a@example.com", full_name="Trader A")
        client_b, _ = _register_and_login(app, email="trader.b@example.com", full_name="Trader B")

        # 1. User A logs an open BUY trade
        create_res = client_a.post(
            "/api/v1/journal",
            json={
                "instrument_id": rel_id,
                "market_id": "00000000-0000-0000-0000-000000000001",
                "side": "BUY",
                "entry_price": "2940.00",
                "quantity": "10",
                "currency": "INR",
                "planned_stop": "2900.00",
                "planned_target": "3020.00",
                "emotions_tags": ["FOLLOWED_PLAN", "PATIENT"],
                "notes": "ORB breakout entry on completed 5m bar.",
            },
            headers=_csrf_headers(client_a),
        )
        assert create_res.status_code == 201
        entry_a = create_res.json()
        assert entry_a["side"] == "BUY"
        assert entry_a["exit_price"] is None
        assert entry_a["realized_pnl"] is None
        entry_a_id = entry_a["id"]

        # User A's journal has 1 trade (1 open)
        list_a = client_a.get("/api/v1/journal").json()
        assert list_a["total"] == 1
        assert list_a["stats"]["open_trades"] == 1
        assert list_a["stats"]["closed_trades"] == 0

        # User B's journal is empty (0 trades)
        list_b = client_b.get("/api/v1/journal").json()
        assert list_b["total"] == 0
        assert list_b["stats"]["total_trades"] == 0

        # User B CANNOT see, update, or delete User A's entry (strictly 404 NOT_FOUND)
        assert client_b.get(f"/api/v1/journal/{entry_a_id}").status_code == 404
        assert (
            client_b.patch(
                f"/api/v1/journal/{entry_a_id}",
                json={"exit_price": "2980.00"},
                headers=_csrf_headers(client_b),
            ).status_code
            == 404
        )
        assert (
            client_b.delete(
                f"/api/v1/journal/{entry_a_id}",
                headers=_csrf_headers(client_b),
            ).status_code
            == 404
        )

        # 2. User A closes the trade by recording exit price: 2980.00 -> Realized P&L = +400.00
        close_res = client_a.patch(
            f"/api/v1/journal/{entry_a_id}",
            json={"exit_price": "2980.00", "notes": "Target reached smoothly."},
            headers=_csrf_headers(client_a),
        )
        assert close_res.status_code == 200
        closed_entry = close_res.json()
        assert Decimal(closed_entry["exit_price"]) == Decimal("2980.00")
        assert Decimal(closed_entry["realized_pnl"]) == Decimal("400.0000")

        # Stats now show 100% win rate and +400 INR realized P&L
        stats_a = client_a.get("/api/v1/journal").json()["stats"]
        assert stats_a["closed_trades"] == 1
        assert stats_a["winning_trades"] == 1
        assert Decimal(str(stats_a["win_rate_pct"])) == Decimal("100.00")
        assert Decimal(str(stats_a["total_realized_pnl_inr"])) == Decimal("400.00")

        # 3. User A deletes the entry
        del_res = client_a.delete(f"/api/v1/journal/{entry_a_id}", headers=_csrf_headers(client_a))
        assert del_res.status_code == 204
        assert client_a.get("/api/v1/journal").json()["total"] == 0


def test_super_admin_overview_users_plans_and_rbac_guards() -> None:
    ctx = build_test_app_context()
    app = ctx["app"]

    with ctx["session_factory"]() as db:
        super_role = db.execute(select(Role).where(Role.code == "super_admin")).scalar_one()
        db.add(
            User(
                role_id=super_role.id,
                email="superadmin.ctrl@platform.local",
                password_hash=hash_password("SuperAdmin#2026!"),
                full_name="Control Super Admin",
                country_code="IN",
                is_active=True,
                is_email_verified=True,
            )
        )
        db.commit()

    with TestClient(app) as client:
        # 1. Regular subscriber is rejected from all admin endpoints with 403
        sub_client, _ = _register_and_login(app, email="ordinary.user@example.com")
        assert sub_client.get("/api/v1/admin/overview").status_code == 403
        assert sub_client.get("/api/v1/admin/users").status_code == 403
        assert sub_client.get("/api/v1/admin/audit-logs").status_code == 403
        assert (
            sub_client.post(
                "/api/v1/admin/plans",
                json={"code": "hack", "name": "Hack", "currency": "INR", "price_amount": "0", "entitled_markets": ["IN"]},
                headers=_csrf_headers(sub_client),
            ).status_code
            == 403
        )

        # 2. Super Admin logs in
        admin_client = TestClient(app)
        admin_login = admin_client.post(
            "/api/v1/auth/login",
            json={"email": "superadmin.ctrl@platform.local", "password": "SuperAdmin#2026!"},
        )
        assert admin_login.status_code == 200

        # Overview KPIs
        overview = admin_client.get("/api/v1/admin/overview")
        assert overview.status_code == 200
        ov_data = overview.json()
        assert ov_data["total_users"] >= 2
        assert ov_data["trading_mode"] == "SIGNALS_ONLY"

        # Users Directory
        users_res = admin_client.get("/api/v1/admin/users")
        assert users_res.status_code == 200
        u_data = users_res.json()
        assert u_data["total"] >= 2
        emails = {u["email"] for u in u_data["items"]}
        assert "ordinary.user@example.com" in emails
        assert "superadmin.ctrl@platform.local" in emails

        # Super Admin creates new subscription plan pricing (audited)
        plan_res = admin_client.post(
            "/api/v1/admin/plans",
            json={
                "code": "india_annual_inr",
                "name": "India Market Annual (Save 20%)",
                "description": "Full access to NSE & BSE signals for 1 year",
                "currency": "INR",
                "price_amount": "23990.00",
                "billing_interval": "yearly",
                "grace_period_days": 5,
                "entitled_markets": ["IN"],
            },
            headers=_csrf_headers(admin_client),
        )
        assert plan_res.status_code == 201
        created_plan = plan_res.json()
        assert created_plan["code"] == "india_annual_inr"
        assert Decimal(str(created_plan["price_amount"])) == Decimal("23990.00")

        # Verify audit logs record plan creation
        audit_res = admin_client.get("/api/v1/admin/audit-logs", params={"action": "ADMIN_PLAN_CREATED"})
        assert audit_res.status_code == 200
        logs = audit_res.json()
        assert len(logs) >= 1
        assert logs[0]["resource_id"] == "india_annual_inr"
