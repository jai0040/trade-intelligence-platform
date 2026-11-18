"""Phase 9 integration tests: Checkout sessions, verified webhooks, idempotency, and tenant isolation."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from decimal import Decimal

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("argon2")

from fastapi.testclient import TestClient
from sqlalchemy import select

from database.models.billing import Payment, PaymentEvent, Subscription, SubscriptionPlan
from tests.conftest import build_test_app_context
from tests.integration.test_phase4_auth_and_isolation import _csrf_headers, _register_and_login


def test_checkout_session_creation_and_currency_guard() -> None:
    ctx = build_test_app_context()
    app = ctx["app"]
    plan_in_id = str(ctx["seed_ids"]["plan_in_id"])

    # Create a USD plan in DB to test Stripe
    with ctx["session_factory"]() as db:
        plan_us = SubscriptionPlan(
            code="us_monthly_usd",
            name="US Market Monthly",
            description="NASDAQ & NYSE signals",
            currency="USD",
            price_amount=Decimal("29.00"),
            billing_interval="monthly",
            grace_period_days=3,
            entitled_markets=["US"],
            features={"signals": True},
            is_active=True,
        )
        db.add(plan_us)
        db.commit()
        plan_us_id = str(plan_us.id)

    with TestClient(app) as client:
        client, user_data = _register_and_login(app, email="subscriber1@example.com", full_name="Subscriber One")

        # 1. Valid Razorpay checkout for INR plan
        res_rzp = client.post(
            "/api/v1/subscriptions/checkout",
            json={"plan_id": plan_in_id, "provider": "razorpay"},
            headers=_csrf_headers(client),
        )
        assert res_rzp.status_code == 200
        data_rzp = res_rzp.json()
        assert data_rzp["provider"] == "razorpay"
        assert data_rzp["currency"] == "INR"
        assert data_rzp["provider_order_id"].startswith("order_")
        assert "checkout_url" in data_rzp

        # 2. Currency mismatch: Razorpay checkout for USD plan -> 400
        res_mismatch = client.post(
            "/api/v1/subscriptions/checkout",
            json={"plan_id": plan_us_id, "provider": "razorpay"},
            headers=_csrf_headers(client),
        )
        assert res_mismatch.status_code == 400
        assert "only supports INR" in res_mismatch.json()["detail"]

        # 3. Valid Stripe checkout for USD plan
        res_stripe = client.post(
            "/api/v1/subscriptions/checkout",
            json={"plan_id": plan_us_id, "provider": "stripe"},
            headers=_csrf_headers(client),
        )
        assert res_stripe.status_code == 200
        data_stripe = res_stripe.json()
        assert data_stripe["provider"] == "stripe"
        assert data_stripe["currency"] == "USD"
        assert data_stripe["provider_session_id"].startswith("cs_test_")


def test_razorpay_webhook_verification_idempotency_and_activation() -> None:
    ctx = build_test_app_context()
    app = ctx["app"]
    settings = ctx["settings"]
    plan_in_id = str(ctx["seed_ids"]["plan_in_id"])

    with TestClient(app) as client:
        client_auth, user_data = _register_and_login(app, email="india.trader@example.com", full_name="India Trader")
        user_id = user_data["user"]["id"]

        # Verify initial subscription status is none
        sub_initial = client_auth.get("/api/v1/subscriptions/me").json()
        assert sub_initial["subscription_status"] == "none"
        assert sub_initial["is_entitled"] is False

        # 1. Forged / invalid signature webhook -> 400 Bad Request
        bad_payload = json.dumps({"event": "payment.captured"}).encode("utf-8")
        res_bad = client.post(
            "/api/v1/webhooks/razorpay",
            content=bad_payload,
            headers={"X-Razorpay-Signature": "invalid_forged_sig"},
        )
        assert res_bad.status_code == 400
        assert "verification failed" in res_bad.json()["detail"]

        # 2. Valid Razorpay payment.captured webhook
        event_id = f"rzp_evt_{uuid.uuid4().hex[:12]}"
        payment_id = f"pay_{uuid.uuid4().hex[:12]}"
        payload_dict = {
            "event": "payment.captured",
            "event_id": event_id,
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "amount": 249900,
                        "currency": "INR",
                        "status": "captured",
                        "notes": {
                            "user_id": user_id,
                            "plan_id": plan_in_id,
                        },
                    }
                }
            },
        }
        valid_raw_body = json.dumps(payload_dict).encode("utf-8")
        valid_signature = hmac.new(
            settings.razorpay_webhook_secret.encode("utf-8"),
            valid_raw_body,
            hashlib.sha256,
        ).hexdigest()

        res_webhook = client.post(
            "/api/v1/webhooks/razorpay",
            content=valid_raw_body,
            headers={"X-Razorpay-Signature": valid_signature},
        )
        assert res_webhook.status_code == 200
        webhook_data = res_webhook.json()
        assert webhook_data["status"] == "success"
        assert webhook_data["provider"] == "razorpay"

        # 3. Verify user's subscription is now active with India market entitlement
        sub_active = client_auth.get("/api/v1/subscriptions/me").json()
        assert sub_active["subscription_status"] == "active"
        assert sub_active["is_entitled"] is True
        assert "IN" in sub_active["entitled_markets"]
        assert sub_active["current_period_end"] is not None

        # 4. Webhook Idempotency: replay the EXACT same event -> returns duplicate
        res_replay = client.post(
            "/api/v1/webhooks/razorpay",
            content=valid_raw_body,
            headers={"X-Razorpay-Signature": valid_signature},
        )
        assert res_replay.status_code == 200
        assert res_replay.json()["status"] == "duplicate"


def test_stripe_webhook_verification_and_activation() -> None:
    ctx = build_test_app_context()
    app = ctx["app"]
    settings = ctx["settings"]

    with ctx["session_factory"]() as db:
        plan_us = SubscriptionPlan(
            code="us_monthly_usd_stripe",
            name="US Market Monthly",
            description="NASDAQ & NYSE signals",
            currency="USD",
            price_amount=Decimal("29.00"),
            billing_interval="monthly",
            grace_period_days=3,
            entitled_markets=["US"],
            features={"signals": True},
            is_active=True,
        )
        db.add(plan_us)
        db.commit()
        plan_us_id = str(plan_us.id)

    with TestClient(app) as client:
        client_auth, user_data = _register_and_login(app, email="us.trader@example.com", full_name="US Trader")
        user_id = user_data["user"]["id"]

        event_id = f"evt_stripe_{uuid.uuid4().hex[:12]}"
        payload_dict = {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": f"cs_test_{uuid.uuid4().hex[:14]}",
                    "payment_intent": f"pi_{uuid.uuid4().hex[:14]}",
                    "amount_total": 2900,
                    "currency": "usd",
                    "metadata": {
                        "user_id": user_id,
                        "plan_id": plan_us_id,
                    },
                }
            },
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        now_ts = int(time.time())
        signed_content = f"{now_ts}.".encode("utf-8") + raw_body
        sig = hmac.new(settings.stripe_webhook_secret.encode("utf-8"), signed_content, hashlib.sha256).hexdigest()
        stripe_header = f"t={now_ts},v1={sig}"

        res = client.post(
            "/api/v1/webhooks/stripe",
            content=raw_body,
            headers={"Stripe-Signature": stripe_header},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "success"

        # Check user status
        sub = client_auth.get("/api/v1/subscriptions/me").json()
        assert sub["subscription_status"] == "active"
        assert "US" in sub["entitled_markets"]

        # Duplicate replay
        res_dup = client.post(
            "/api/v1/webhooks/stripe",
            content=raw_body,
            headers={"Stripe-Signature": stripe_header},
        )
        assert res_dup.status_code == 200
        assert res_dup.json()["status"] == "duplicate"


def test_payment_history_tenant_isolation_and_cancellation() -> None:
    ctx = build_test_app_context()
    app = ctx["app"]
    settings = ctx["settings"]
    plan_in_id = str(ctx["seed_ids"]["plan_in_id"])

    with TestClient(app) as client:
        client_a, user_a = _register_and_login(app, email="user.a@example.com", full_name="User A")
        client_b, user_b = _register_and_login(app, email="user.b@example.com", full_name="User B")

        # Send webhook payment for User A
        event_id = f"rzp_evt_{uuid.uuid4().hex[:12]}"
        payload_dict = {
            "event": "payment.captured",
            "event_id": event_id,
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_{uuid.uuid4().hex[:12]}",
                        "amount": 249900,
                        "currency": "INR",
                        "status": "captured",
                        "notes": {"user_id": user_a["user"]["id"], "plan_id": plan_in_id},
                    }
                }
            },
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        sig = hmac.new(settings.razorpay_webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

        client.post("/api/v1/webhooks/razorpay", content=raw_body, headers={"X-Razorpay-Signature": sig})

        # User A checks history -> 1 invoice
        hist_a = client_a.get("/api/v1/payments/history").json()
        assert hist_a["total"] == 1
        assert hist_a["items"][0]["status"] == "succeeded"
        assert hist_a["items"][0]["amount"] == "2499.00"

        # User B checks history -> 0 invoices (strict tenant isolation!)
        hist_b = client_b.get("/api/v1/payments/history").json()
        assert hist_b["total"] == 0
        assert len(hist_b["items"]) == 0

        # User A schedules subscription cancellation
        cancel_res = client_a.post(
            "/api/v1/subscriptions/cancel",
            json={"reason": "Moving abroad"},
            headers=_csrf_headers(client_a),
        )
        assert cancel_res.status_code == 200
        cancel_data = cancel_res.json()
        assert cancel_data["cancel_at_period_end"] is True

        # User A still has entitled access until period end
        sub_a = client_a.get("/api/v1/subscriptions/me").json()
        assert sub_a["cancel_at_period_end"] is True
        assert sub_a["is_entitled"] is True
