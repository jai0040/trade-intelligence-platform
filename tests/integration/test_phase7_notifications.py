"""Phase 7 integration tests: User-isolated Notifications, Mark-Read, CSRF, and Notification Preferences."""

from __future__ import annotations

import uuid

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("argon2")

from fastapi.testclient import TestClient
from sqlalchemy import select

from database.models.identity import User
from database.models.workspace import Notification
from tests.conftest import build_test_app_context
from tests.integration.test_phase4_auth_and_isolation import _csrf_headers, _register_and_login


def test_notifications_and_preferences_strict_user_isolation() -> None:
    ctx = build_test_app_context()
    with TestClient(ctx["app"]):
        client_a, _ = _register_and_login(ctx["app"], email="notif.a@example.com")
        client_b, _ = _register_and_login(ctx["app"], email="notif.b@example.com")

        # Seed two notifications for User A
        with ctx["session_factory"]() as db:
            user_a = db.execute(select(User).where(User.email == "notif.a@example.com")).scalar_one()
            n1 = Notification(
                user_id=user_a.id,
                category="TARGET_HIT",
                title="Target Hit: NSE:RELIANCE",
                body="Target ₹2,995.00 reached on completed 5m bar.",
                dedupe_key=f"target-{uuid.uuid4()}",
            )
            n2 = Notification(
                user_id=user_a.id,
                category="NEW_SIGNAL",
                title="New Signal: NASDAQ:TSLA",
                body="ORB 15m breakout passed trader-risk.",
                dedupe_key=f"signal-{uuid.uuid4()}",
            )
            db.add_all([n1, n2])
            db.commit()
            n1_id = str(n1.id)

        # User A sees 2 unread notifications; User B sees 0
        list_a = client_a.get("/api/v1/notifications")
        assert list_a.status_code == 200
        assert list_a.json()["unread_count"] == 2
        assert list_a.json()["total"] == 2

        list_b = client_b.get("/api/v1/notifications")
        assert list_b.status_code == 200
        assert list_b.json()["unread_count"] == 0
        assert list_b.json()["total"] == 0

        # User B cannot mark User A's notification read (404 NOT_FOUND)
        cross_read = client_b.post(
            f"/api/v1/notifications/{n1_id}/read", headers=_csrf_headers(client_b)
        )
        assert cross_read.status_code == 404

        # CSRF required for mark-read
        no_csrf = client_a.post(f"/api/v1/notifications/{n1_id}/read")
        assert no_csrf.status_code == 403

        # User A marks one read, then marks all read
        ok_read = client_a.post(
            f"/api/v1/notifications/{n1_id}/read", headers=_csrf_headers(client_a)
        )
        assert ok_read.status_code == 200
        assert ok_read.json()["is_read"] is True
        assert client_a.get("/api/v1/notifications").json()["unread_count"] == 1

        read_all = client_a.post("/api/v1/notifications/read-all", headers=_csrf_headers(client_a))
        assert read_all.status_code == 200
        assert read_all.json()["marked_read"] == 1
        assert client_a.get("/api/v1/notifications").json()["unread_count"] == 0

        # Notification preferences CRUD strictly isolated to User A
        patch_pref = client_a.patch(
            "/api/v1/notifications/preferences",
            json={"market_filter": "IN", "notify_signal_expiry": True, "email_enabled": False},
            headers=_csrf_headers(client_a),
        )
        assert patch_pref.status_code == 200
        assert patch_pref.json()["market_filter"] == "IN"
        assert patch_pref.json()["email_enabled"] is False

        # User B preferences unaffected
        pref_b = client_b.get("/api/v1/notifications/preferences").json()
        assert pref_b["market_filter"] == "ALL"
        assert pref_b["email_enabled"] is True
