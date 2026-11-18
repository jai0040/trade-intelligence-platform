"""Phase 4 integration tests: Auth, Single Active Session, CSRF, Rate Limits, RBAC, Isolation, & Entitlements."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

fastapi = pytest.importorskip("fastapi")
sqlalchemy = pytest.importorskip("sqlalchemy")
argon2 = pytest.importorskip("argon2")

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.authentication.dependencies import AuthContext
from app.core.security import hash_password, hash_token
from app.subscriptions.dependencies import require_active_subscription
from database.models.billing import Subscription
from database.models.identity import AuditLog, PasswordResetToken, Role, Session, User
from tests.conftest import build_test_app_context


def _csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("tip_csrf")
    assert token, "Expected tip_csrf cookie after login"
    return {"X-CSRF-Token": token}


def _register_and_login(
    app: Any,
    *,
    email: str,
    password: str = "TraderPass#2026!",
    full_name: str = "Aarav Mehta",
    country_code: str = "IN",
) -> tuple[TestClient, dict[str, Any]]:
    client = TestClient(app)
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "country_code": country_code,
        },
    )
    assert reg.status_code == 201, reg.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return client, login.json()


def test_registration_argon2id_and_cookie_security() -> None:
    ctx = build_test_app_context()
    with TestClient(ctx["app"]) as client:
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": "Alice.Trader@Example.COM",
                "password": "StrongPassword#2026",
                "full_name": "Alice Trader",
                "country_code": "IN",
            },
        )
        assert reg.status_code == 201
        assert reg.json()["email"] == "alice.trader@example.com"
        assert reg.json()["role"] == "subscriber"

        # Duplicate registration (case-insensitive) rejected with 409
        dup = client.post(
            "/api/v1/auth/register",
            json={
                "email": "alice.trader@example.com",
                "password": "StrongPassword#2026",
                "full_name": "Alice Duplicate",
                "country_code": "IN",
            },
        )
        assert dup.status_code == 409
        assert dup.json()["code"] == "CONFLICT"

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "alice.trader@example.com", "password": "StrongPassword#2026"},
        )
        assert login.status_code == 200
        set_cookie_headers = login.headers.get_list("set-cookie")
        session_cookie_header = next(h for h in set_cookie_headers if h.startswith("tip_session="))
        assert "httponly" in session_cookie_header.lower()
        assert "samesite=lax" in session_cookie_header.lower()

        raw_cookie = client.cookies.get("tip_session")
        assert raw_cookie is not None

        with ctx["session_factory"]() as db:
            user = db.execute(
                select(User).where(User.email == "alice.trader@example.com")
            ).scalar_one()
            assert user.password_hash.startswith("$argon2id$")
            assert "StrongPassword#2026" not in user.password_hash

            sess = db.execute(select(Session).where(Session.user_id == user.id)).scalar_one()
            assert sess.token_hash != raw_cookie
            assert sess.token_hash == hash_token(raw_cookie)
            assert sess.status == "ACTIVE"


def test_csrf_protection_required_on_mutations() -> None:
    ctx = build_test_app_context()
    with TestClient(ctx["app"]):
        client, _ = _register_and_login(ctx["app"], email="csrf.user@example.com")

        # Missing CSRF header -> 403 CSRF_INVALID
        missing = client.post("/api/v1/watchlists", json={"name": "Tech Picks", "market_scope": "US"})
        assert missing.status_code == 403
        assert missing.json()["code"] == "CSRF_INVALID"

        # Mismatched CSRF header -> 403 CSRF_INVALID
        wrong = client.post(
            "/api/v1/watchlists",
            json={"name": "Tech Picks", "market_scope": "US"},
            headers={"X-CSRF-Token": "forged-token"},
        )
        assert wrong.status_code == 403
        assert wrong.json()["code"] == "CSRF_INVALID"

        # Valid CSRF header -> 201 Created
        ok = client.post(
            "/api/v1/watchlists",
            json={"name": "Tech Picks", "market_scope": "US"},
            headers=_csrf_headers(client),
        )
        assert ok.status_code == 201


def test_single_active_session_evicts_previous_device_and_websocket() -> None:
    ctx = build_test_app_context()
    app = ctx["app"]

    with TestClient(app) as device1:
        reg = device1.post(
            "/api/v1/auth/register",
            json={
                "email": "single.session@example.com",
                "password": "SingleDevice#2026!",
                "full_name": "Single Session User",
                "country_code": "IN",
            },
        )
        assert reg.status_code == 201

        # Device 1 signs in
        r1 = device1.post(
            "/api/v1/auth/login",
            json={"email": "single.session@example.com", "password": "SingleDevice#2026!"},
        )
        assert r1.status_code == 200
        assert device1.get("/api/v1/auth/me").status_code == 200

        # Query-string token on WebSocket is strictly prohibited
        with pytest.raises(Exception):
            with device1.websocket_connect("/ws/v1/stream?token=leaked"):
                pass

        # Device 1 opens real-time WebSocket using HttpOnly cookie
        with device1.websocket_connect("/ws/v1/stream") as ws1:
            ready_frame = ws1.receive_json()
            assert ready_frame["type"] == "connection.ready"

            # Device 2 signs in with the SAME account
            device2 = TestClient(app)
            r2 = device2.post(
                "/api/v1/auth/login",
                json={"email": "single.session@example.com", "password": "SingleDevice#2026!"},
            )
            assert r2.status_code == 200

            # Device 1 WebSocket immediately receives session.invalidated
            eviction_frame = ws1.receive_json()
            assert eviction_frame["type"] == "session.invalidated"
            assert eviction_frame["payload"]["code"] == "SESSION_SUPERSEDED"
            assert eviction_frame["payload"]["revoked_by"] == "new_login"

        # Device 1 REST call is now rejected with 401 SESSION_SUPERSEDED
        me1 = device1.get("/api/v1/auth/me")
        assert me1.status_code == 401
        assert me1.json()["code"] == "SESSION_SUPERSEDED"

        # Device 2 remains active and authenticated
        me2 = device2.get("/api/v1/auth/me")
        assert me2.status_code == 200
        assert me2.json()["email"] == "single.session@example.com"

        # Verify DB invariants & Redis Pub/Sub eviction event
        with ctx["session_factory"]() as db:
            user = db.execute(
                select(User).where(User.email == "single.session@example.com")
            ).scalar_one()
            sessions = list(
                db.execute(select(Session).where(Session.user_id == user.id)).scalars().all()
            )
            statuses = sorted(s.status for s in sessions)
            assert statuses == ["ACTIVE", "SUPERSEDED"]

            superseded_audit = db.execute(
                select(AuditLog).where(
                    AuditLog.actor_user_id == user.id,
                    AuditLog.action == "SESSION_SUPERSEDED",
                )
            ).scalar_one_or_none()
            assert superseded_audit is not None

        assert any(
            ch.startswith("ws:user:") and json.loads(msg)["type"] == "session.invalidated"
            for ch, msg in ctx["redis"].published
        )


def test_password_reset_constant_response_and_session_revocation() -> None:
    ctx = build_test_app_context()
    app = ctx["app"]
    captured_tokens: list[tuple[str, str]] = []

    with TestClient(app) as client:
        app.state.password_reset_notifier = lambda email, tok: captured_tokens.append((email, tok))

        user_client, _ = _register_and_login(app, email="reset.me@example.com")

        # Unknown and known email return identical 202 response (anti-enumeration)
        unknown_res = client.post(
            "/api/v1/auth/password-reset/request", json={"email": "nobody@example.com"}
        )
        known_res = client.post(
            "/api/v1/auth/password-reset/request", json={"email": "reset.me@example.com"}
        )
        assert unknown_res.status_code == 202
        assert known_res.status_code == 202
        assert unknown_res.json() == known_res.json()
        assert len(captured_tokens) == 1

        _, raw_reset_token = captured_tokens[0]
        with ctx["session_factory"]() as db:
            tok_row = db.execute(select(PasswordResetToken)).scalar_one()
            assert tok_row.token_hash != raw_reset_token
            assert tok_row.token_hash == hash_token(raw_reset_token)

        # Confirm reset -> revokes active session
        confirm = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_reset_token, "new_password": "BrandNewPass#2026!"},
        )
        assert confirm.status_code == 200

        # Old session is immediately revoked
        old_me = user_client.get("/api/v1/auth/me")
        assert old_me.status_code == 401
        assert old_me.json()["code"] in {"SESSION_REVOKED", "SESSION_SUPERSEDED"}

        # Token cannot be reused
        reuse = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_reset_token, "new_password": "AnotherPass#2026!"},
        )
        assert reuse.status_code == 400
        assert reuse.json()["code"] == "INVALID_RESET_TOKEN"

        # New password works
        relogin = client.post(
            "/api/v1/auth/login",
            json={"email": "reset.me@example.com", "password": "BrandNewPass#2026!"},
        )
        assert relogin.status_code == 200


def test_login_rate_limiting_returns_429() -> None:
    ctx = build_test_app_context(rate_limit_login_max=3)
    with TestClient(ctx["app"]) as client:
        for _ in range(3):
            res = client.post(
                "/api/v1/auth/login",
                json={"email": "ratelimit@example.com", "password": "WrongPassword#1"},
            )
            assert res.status_code == 401

        blocked = client.post(
            "/api/v1/auth/login",
            json={"email": "ratelimit@example.com", "password": "WrongPassword#1"},
        )
        assert blocked.status_code == 429
        assert blocked.json()["code"] == "RATE_LIMITED"
        assert "retry-after" in {k.lower() for k in blocked.headers.keys()}


def test_strict_multi_user_workspace_isolation() -> None:
    ctx = build_test_app_context()
    with TestClient(ctx["app"]):
        client_a, _ = _register_and_login(ctx["app"], email="user.a@example.com", full_name="User A")
        client_b, _ = _register_and_login(ctx["app"], email="user.b@example.com", full_name="User B")

        # User A creates a private watchlist and adds NSE:RELIANCE
        wl_res = client_a.post(
            "/api/v1/watchlists",
            json={"name": "A's India Breakouts", "market_scope": "IN"},
            headers=_csrf_headers(client_a),
        )
        assert wl_res.status_code == 201
        wl_a_id = wl_res.json()["id"]

        item_res = client_a.post(
            f"/api/v1/watchlists/{wl_a_id}/items",
            json={"instrument_id": str(ctx["seed_ids"]["reliance_id"]), "notes": "ORB candidate"},
            headers=_csrf_headers(client_a),
        )
        assert item_res.status_code == 201
        item_a_id = item_res.json()["id"]

        # User A updates preferences
        pref_a = client_a.patch(
            "/api/v1/users/me/preferences",
            json={"default_market": "IN", "theme": "light"},
            headers=_csrf_headers(client_a),
        )
        assert pref_a.status_code == 200
        assert pref_a.json()["default_market"] == "IN"

        # User B attempts to read/modify/delete User A's watchlist & item -> strictly 404
        assert client_b.get(f"/api/v1/watchlists/{wl_a_id}").status_code == 404
        assert (
            client_b.patch(
                f"/api/v1/watchlists/{wl_a_id}",
                json={"name": "Hijacked"},
                headers=_csrf_headers(client_b),
            ).status_code
            == 404
        )
        assert (
            client_b.delete(
                f"/api/v1/watchlists/{wl_a_id}",
                headers=_csrf_headers(client_b),
            ).status_code
            == 404
        )
        assert (
            client_b.delete(
                f"/api/v1/watchlists/{wl_a_id}/items/{item_a_id}",
                headers=_csrf_headers(client_b),
            ).status_code
            == 404
        )

        # User B only sees their own default watchlist and default dark preferences
        wl_b_list = client_b.get("/api/v1/watchlists").json()
        assert all(w["id"] != wl_a_id for w in wl_b_list)
        assert client_b.get("/api/v1/users/me/preferences").json()["theme"] == "dark"


def test_rbac_and_admin_session_revocation_and_deactivation() -> None:
    ctx = build_test_app_context()
    app = ctx["app"]

    # Seed a super_admin account directly in DB
    with ctx["session_factory"]() as db:
        super_role = db.execute(select(Role).where(Role.code == "super_admin")).scalar_one()
        admin_user = User(
            role_id=super_role.id,
            email="superadmin@platform.local",
            password_hash=hash_password("SuperAdmin#2026!"),
            full_name="Platform Super Admin",
            country_code="IN",
            is_active=True,
            is_email_verified=True,
        )
        db.add(admin_user)
        db.commit()

    with TestClient(app):
        sub_client, sub_profile = _register_and_login(app, email="regular.sub@example.com")
        sub_id = sub_profile["id"]

        # Subscriber cannot access admin routes (403 FORBIDDEN)
        forbidden = sub_client.get("/api/v1/admin/audit-logs")
        assert forbidden.status_code == 403
        assert forbidden.json()["code"] == "FORBIDDEN"

        forbidden_revoke = sub_client.post(
            f"/api/v1/admin/users/{sub_id}/revoke-session",
            headers=_csrf_headers(sub_client),
        )
        assert forbidden_revoke.status_code == 403

        # Super Admin logs in and revokes subscriber's active session
        admin_client = TestClient(app)
        login_admin = admin_client.post(
            "/api/v1/auth/login",
            json={"email": "superadmin@platform.local", "password": "SuperAdmin#2026!"},
        )
        assert login_admin.status_code == 200
        assert login_admin.json()["role"] == "super_admin"

        revoke_res = admin_client.post(
            f"/api/v1/admin/users/{sub_id}/revoke-session",
            json={"reason": "Security audit check"},
            headers=_csrf_headers(admin_client),
        )
        assert revoke_res.status_code == 200
        assert revoke_res.json()["revoked_sessions_count"] == 1

        # Subscriber's existing session is immediately evicted
        assert sub_client.get("/api/v1/auth/me").status_code == 401

        # Super Admin deactivates subscriber -> blocks login
        deact = admin_client.patch(
            f"/api/v1/admin/users/{sub_id}/status",
            json={"is_active": False, "reason": "Chargeback review"},
            headers=_csrf_headers(admin_client),
        )
        assert deact.status_code == 200
        assert deact.json()["is_active"] is False

        blocked_login = sub_client.post(
            "/api/v1/auth/login",
            json={"email": "regular.sub@example.com", "password": "TraderPass#2026!"},
        )
        assert blocked_login.status_code == 403
        assert blocked_login.json()["code"] == "ACCOUNT_INACTIVE"

        # Audit logs recorded both admin actions
        logs = admin_client.get("/api/v1/admin/audit-logs").json()
        actions = {row["action"] for row in logs}
        assert "ADMIN_SESSION_REVOKED" in actions
        assert "ADMIN_USER_DEACTIVATED" in actions


def test_subscription_entitlement_guards_in_and_us() -> None:
    ctx = build_test_app_context()
    app = ctx["app"]

    @app.get("/api/v1/_test/entitled-in")
    def _entitled_in(auth: AuthContext = Depends(require_active_subscription("IN"))) -> dict[str, Any]:
        return {"ok": True, "user_id": str(auth.user.id)}

    @app.get("/api/v1/_test/entitled-us")
    def _entitled_us(auth: AuthContext = Depends(require_active_subscription("US"))) -> dict[str, Any]:
        return {"ok": True, "user_id": str(auth.user.id)}

    with TestClient(app):
        client, profile = _register_and_login(app, email="entitlement@example.com")

        # Public plan catalog works
        plans_res = client.get("/api/v1/subscriptions/plans")
        assert plans_res.status_code == 200
        assert len(plans_res.json()) == 2

        # Unsubscribed user blocked with 403 SUBSCRIPTION_REQUIRED
        r_none = client.get("/api/v1/_test/entitled-in")
        assert r_none.status_code == 403
        assert r_none.json()["code"] == "SUBSCRIPTION_REQUIRED"

        # Assign active India-only subscription
        now = datetime.now(timezone.utc)
        with ctx["session_factory"]() as db:
            user = db.execute(select(User).where(User.email == "entitlement@example.com")).scalar_one()
            sub = Subscription(
                user_id=user.id,
                plan_id=ctx["seed_ids"]["plan_in_id"],
                provider="razorpay",
                status="active",
                current_period_start=now - timedelta(days=1),
                current_period_end=now + timedelta(days=29),
            )
            db.add(sub)
            db.commit()

        # Allowed on India, denied on US (403 MARKET_NOT_ENTITLED)
        assert client.get("/api/v1/_test/entitled-in").status_code == 200
        r_us = client.get("/api/v1/_test/entitled-us")
        assert r_us.status_code == 403
        assert r_us.json()["code"] == "MARKET_NOT_ENTITLED"

        # Expire subscription without grace -> blocked again
        with ctx["session_factory"]() as db:
            sub_row = db.execute(select(Subscription)).scalar_one()
            sub_row.current_period_end = now - timedelta(hours=1)
            sub_row.grace_until = None
            db.commit()

        assert client.get("/api/v1/_test/entitled-in").status_code == 403
        assert client.get("/api/v1/subscriptions/me").json()["subscription_status"] == "expired"
