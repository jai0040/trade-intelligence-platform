"""Payments, checkout session management, subscription lifecycles, and verified webhooks."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession, joinedload

from app.core.config import Settings
from app.payments.crypto import (
    calculate_period_end_and_grace,
    generate_invoice_number,
    verify_razorpay_webhook_signature,
    verify_stripe_webhook_signature,
)
from app.payments.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PaymentHistoryItem,
    PaymentHistoryResponse,
    SubscriptionCancelResponse,
    WebhookEventResponse,
)
from database.models.billing import Payment, PaymentEvent, Subscription, SubscriptionPlan
from database.models.identity import User

logger = logging.getLogger("trade_intelligence.payments")


def create_checkout_session(
    db: DbSession,
    *,
    user_id: uuid.UUID,
    request: CheckoutRequest,
    settings: Settings,
) -> CheckoutResponse:
    """Initiate a checkout session for Razorpay (INR) or Stripe (USD).

    Security rule: Frontend returns NEVER directly activate subscriptions;
    only cryptographically verified server webhooks activate or renew subscriptions.
    """
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user account is inactive or not found.",
        )

    plan = db.get(SubscriptionPlan, request.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested subscription plan is not found or inactive.",
        )

    # Provider vs currency compatibility check
    if request.provider == "razorpay" and plan.currency != "INR":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Razorpay provider only supports INR plans. Plan {plan.code} is {plan.currency}.",
        )
    if request.provider == "stripe" and plan.currency != "USD":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe provider only supports USD plans. Plan {plan.code} is {plan.currency}.",
        )

    # Find existing subscription or create a pending record
    stmt = (
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    existing_sub = db.execute(stmt).scalar_one_or_none()

    if existing_sub is None or existing_sub.status in {"expired", "cancelled"}:
        subscription = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            provider=request.provider,
            status="pending",
        )
        db.add(subscription)
        db.flush()
    else:
        subscription = existing_sub

    # Build provider checkout parameters
    if request.provider == "razorpay":
        order_id = f"order_{uuid.uuid4().hex[:14]}"
        session_id = order_id
        checkout_url = f"{settings.app_base_url}/checkout/razorpay?order_id={order_id}"
        public_key = settings.razorpay_key_id
    else:
        session_id = f"cs_test_{uuid.uuid4().hex[:16]}"
        checkout_url = f"https://checkout.stripe.com/c/pay/{session_id}"
        public_key = settings.stripe_publishable_key

    subscription.provider_subscription_id = session_id
    db.commit()

    return CheckoutResponse(
        checkout_url=checkout_url,
        provider=request.provider,
        provider_session_id=session_id,
        provider_order_id=session_id,
        public_key=public_key,
        currency=plan.currency,
        amount=plan.price_amount,
        plan_id=plan.id,
        plan_name=plan.name,
        plan_code=plan.code,
    )


def cancel_user_subscription(
    db: DbSession,
    *,
    user_id: uuid.UUID,
    reason: str | None = None,
) -> SubscriptionCancelResponse:
    """Schedule user subscription cancellation at the end of the current billing cycle."""
    stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trialing", "past_due"]),
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub = db.execute(stmt).scalar_one_or_none()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active or past due subscription found to cancel.",
        )

    now = datetime.now(timezone.utc)
    sub.cancel_at_period_end = True
    sub.cancelled_at = now
    db.commit()

    return SubscriptionCancelResponse(
        status="cancellation_scheduled",
        cancel_at_period_end=True,
        cancelled_at=now,
        current_period_end=sub.current_period_end,
        message="Your subscription has been scheduled for cancellation. Access remains active until period end.",
    )


def get_payment_history(
    db: DbSession,
    *,
    user_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> PaymentHistoryResponse:
    """Return user-scoped payment transactions and invoices strictly isolated by user_id."""
    count_stmt = select(func.count(Payment.id)).where(Payment.user_id == user_id)
    total = db.execute(count_stmt).scalar() or 0

    stmt = (
        select(Payment)
        .options(joinedload(Payment.subscription).joinedload(Subscription.plan))
        .where(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    payments = db.execute(stmt).scalars().unique().all()

    items = [
        PaymentHistoryItem(
            id=p.id,
            invoice_number=p.invoice_number,
            provider=p.provider,
            provider_payment_id=p.provider_payment_id,
            amount=p.amount,
            tax_amount=p.tax_amount,
            currency=p.currency,
            status=p.status,
            failure_reason=p.failure_reason,
            receipt_url=p.receipt_url,
            paid_at=p.paid_at,
            created_at=p.created_at,
            plan_name=p.subscription.plan.name if p.subscription and p.subscription.plan else None,
        )
        for p in payments
    ]

    return PaymentHistoryResponse(items=items, total=total)


def process_razorpay_webhook(
    db: DbSession,
    *,
    raw_body: bytes,
    signature: str | None,
    settings: Settings,
) -> WebhookEventResponse:
    """Cryptographically verify and idempotently process Razorpay webhook notifications."""
    if not verify_razorpay_webhook_signature(raw_body, signature, settings.razorpay_webhook_secret):
        logger.warning("Rejected Razorpay webhook with invalid signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cryptographic signature verification failed for Razorpay webhook.",
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON payload: {exc}",
        )

    event_type = payload.get("event", "unknown")
    event_id = payload.get("event_id") or payload.get("id")
    if not event_id:
        payment_entity = (
            payload.get("payload", {}).get("payment", {}).get("entity", {})
        )
        event_id = payment_entity.get("id") or f"rzp_evt_{uuid.uuid4().hex[:12]}"

    # Idempotency Check
    existing_event = db.execute(
        select(PaymentEvent).where(
            PaymentEvent.provider == "razorpay",
            PaymentEvent.provider_event_id == event_id,
        )
    ).scalar_one_or_none()

    if existing_event is not None:
        return WebhookEventResponse(
            status="duplicate",
            provider="razorpay",
            event_id=event_id,
            message="Event has already been processed.",
        )

    event_record = PaymentEvent(
        provider="razorpay",
        provider_event_id=event_id,
        event_type=event_type,
        signature_verified=True,
        payload=payload,
        processing_status="received",
    )
    db.add(event_record)
    db.flush()

    now = datetime.now(timezone.utc)
    payment_payload = payload.get("payload", {}).get("payment", {}).get("entity", {})
    sub_payload = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    notes = payment_payload.get("notes") or sub_payload.get("notes") or payload.get("notes", {})

    user_id_str = notes.get("user_id")
    plan_id_str = notes.get("plan_id")

    user: User | None = None
    if user_id_str:
        try:
            user = db.get(User, uuid.UUID(user_id_str))
        except ValueError:
            user = None

    plan: SubscriptionPlan | None = None
    if plan_id_str:
        try:
            plan = db.get(SubscriptionPlan, uuid.UUID(plan_id_str))
        except ValueError:
            plan = None

    # Handle event categories
    if event_type in {"subscription.activated", "subscription.charged", "payment.captured"}:
        amount_paise = payment_payload.get("amount") or sub_payload.get("amount") or 0
        amount = Decimal(amount_paise) / Decimal("100") if amount_paise else Decimal("0.00")
        currency = (payment_payload.get("currency") or "INR").upper()
        provider_payment_id = payment_payload.get("id") or f"pay_{uuid.uuid4().hex[:14]}"
        provider_sub_id = sub_payload.get("id") or payment_payload.get("order_id")

        # Resolve or create subscription
        subscription: Subscription | None = None
        if provider_sub_id:
            subscription = db.execute(
                select(Subscription).where(Subscription.provider_subscription_id == provider_sub_id)
            ).scalar_one_or_none()

        if subscription is None and user is not None:
            stmt = (
                select(Subscription)
                .where(Subscription.user_id == user.id)
                .order_by(Subscription.created_at.desc())
                .limit(1)
            )
            subscription = db.execute(stmt).scalar_one_or_none()

        if subscription is None and user is not None:
            if plan is None:
                plan = db.execute(
                    select(SubscriptionPlan).where(SubscriptionPlan.currency == currency).limit(1)
                ).scalar_one_or_none()
            if plan:
                subscription = Subscription(
                    user_id=user.id,
                    plan_id=plan.id,
                    provider="razorpay",
                    provider_subscription_id=provider_sub_id,
                    status="active",
                )
                db.add(subscription)
                db.flush()

        if subscription is not None:
            sub_plan = subscription.plan or plan
            grace_days = sub_plan.grace_period_days if sub_plan else 3
            billing_interval = sub_plan.billing_interval if sub_plan else "monthly"

            period_end, grace_until = calculate_period_end_and_grace(
                now, billing_interval=billing_interval, grace_days=grace_days
            )
            subscription.status = "active"
            subscription.current_period_start = now
            subscription.current_period_end = period_end
            subscription.grace_until = grace_until
            subscription.cancel_at_period_end = False

            # Ensure payment record
            existing_payment = db.execute(
                select(Payment).where(Payment.provider_payment_id == provider_payment_id)
            ).scalar_one_or_none()

            if existing_payment is None:
                payment = Payment(
                    user_id=subscription.user_id,
                    subscription_id=subscription.id,
                    provider="razorpay",
                    provider_payment_id=provider_payment_id,
                    invoice_number=generate_invoice_number("INV-RZP"),
                    amount=amount if amount > 0 else (sub_plan.price_amount if sub_plan else Decimal("0")),
                    tax_amount=Decimal("0.00"),
                    currency=currency,
                    status="succeeded",
                    receipt_url=payment_payload.get("invoice_id") or payment_payload.get("receipt"),
                    paid_at=now,
                )
                db.add(payment)

    elif event_type in {"subscription.halted", "payment.failed"}:
        provider_sub_id = sub_payload.get("id") or payment_payload.get("order_id")
        provider_payment_id = payment_payload.get("id") or f"pay_failed_{uuid.uuid4().hex[:10]}"

        subscription = None
        if provider_sub_id:
            subscription = db.execute(
                select(Subscription).where(Subscription.provider_subscription_id == provider_sub_id)
            ).scalar_one_or_none()

        if subscription is not None:
            # Check if within grace
            if subscription.grace_until and subscription.grace_until > now:
                subscription.status = "past_due"
            else:
                subscription.status = "expired"

            failure_msg = payment_payload.get("error_description") or "Payment processing failed"
            payment = Payment(
                user_id=subscription.user_id,
                subscription_id=subscription.id,
                provider="razorpay",
                provider_payment_id=provider_payment_id,
                invoice_number=generate_invoice_number("INV-RZP-FAIL"),
                amount=Decimal(payment_payload.get("amount", 0)) / Decimal("100"),
                currency=(payment_payload.get("currency") or "INR").upper(),
                status="failed",
                failure_reason=failure_msg,
                paid_at=None,
            )
            db.add(payment)

    elif event_type in {"subscription.cancelled"}:
        provider_sub_id = sub_payload.get("id")
        if provider_sub_id:
            sub = db.execute(
                select(Subscription).where(Subscription.provider_subscription_id == provider_sub_id)
            ).scalar_one_or_none()
            if sub:
                sub.status = "cancelled"
                sub.cancel_at_period_end = True
                sub.cancelled_at = now

    event_record.processing_status = "processed"
    event_record.processed_at = now
    db.commit()

    return WebhookEventResponse(status="success", provider="razorpay", event_id=event_id)


def process_stripe_webhook(
    db: DbSession,
    *,
    raw_body: bytes,
    signature_header: str | None,
    settings: Settings,
) -> WebhookEventResponse:
    """Cryptographically verify and idempotently process Stripe webhook notifications."""
    if not verify_stripe_webhook_signature(
        raw_body, signature_header, settings.stripe_webhook_secret
    ):
        logger.warning("Rejected Stripe webhook with invalid signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cryptographic signature verification failed for Stripe webhook.",
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON payload: {exc}",
        )

    event_id = payload.get("id") or f"evt_stripe_{uuid.uuid4().hex[:12]}"
    event_type = payload.get("type", "unknown")

    # Idempotency Check
    existing_event = db.execute(
        select(PaymentEvent).where(
            PaymentEvent.provider == "stripe",
            PaymentEvent.provider_event_id == event_id,
        )
    ).scalar_one_or_none()

    if existing_event is not None:
        return WebhookEventResponse(
            status="duplicate",
            provider="stripe",
            event_id=event_id,
            message="Event has already been processed.",
        )

    event_record = PaymentEvent(
        provider="stripe",
        provider_event_id=event_id,
        event_type=event_type,
        signature_verified=True,
        payload=payload,
        processing_status="received",
    )
    db.add(event_record)
    db.flush()

    now = datetime.now(timezone.utc)
    data_obj = payload.get("data", {}).get("object", {})
    metadata = data_obj.get("metadata", {})

    user_id_str = metadata.get("user_id") or data_obj.get("client_reference_id")
    plan_id_str = metadata.get("plan_id")

    user: User | None = None
    if user_id_str:
        try:
            user = db.get(User, uuid.UUID(user_id_str))
        except ValueError:
            user = None

    plan: SubscriptionPlan | None = None
    if plan_id_str:
        try:
            plan = db.get(SubscriptionPlan, uuid.UUID(plan_id_str))
        except ValueError:
            plan = None

    if event_type in {"checkout.session.completed", "invoice.payment_succeeded"}:
        provider_sub_id = data_obj.get("subscription") or data_obj.get("id")
        provider_payment_id = (
            data_obj.get("payment_intent")
            or data_obj.get("charge")
            or f"ch_{uuid.uuid4().hex[:14]}"
        )
        amount_cents = data_obj.get("amount_total") or data_obj.get("amount_paid") or 0
        amount = Decimal(amount_cents) / Decimal("100") if amount_cents else Decimal("0.00")
        currency = (data_obj.get("currency") or "USD").upper()

        subscription: Subscription | None = None
        if provider_sub_id:
            subscription = db.execute(
                select(Subscription).where(Subscription.provider_subscription_id == provider_sub_id)
            ).scalar_one_or_none()

        if subscription is None and user is not None:
            stmt = (
                select(Subscription)
                .where(Subscription.user_id == user.id)
                .order_by(Subscription.created_at.desc())
                .limit(1)
            )
            subscription = db.execute(stmt).scalar_one_or_none()

        if subscription is None and user is not None:
            if plan is None:
                plan = db.execute(
                    select(SubscriptionPlan).where(SubscriptionPlan.currency == currency).limit(1)
                ).scalar_one_or_none()
            if plan:
                subscription = Subscription(
                    user_id=user.id,
                    plan_id=plan.id,
                    provider="stripe",
                    provider_subscription_id=provider_sub_id,
                    status="active",
                )
                db.add(subscription)
                db.flush()

        if subscription is not None:
            sub_plan = subscription.plan or plan
            grace_days = sub_plan.grace_period_days if sub_plan else 3
            billing_interval = sub_plan.billing_interval if sub_plan else "monthly"

            period_end, grace_until = calculate_period_end_and_grace(
                now, billing_interval=billing_interval, grace_days=grace_days
            )
            subscription.status = "active"
            subscription.current_period_start = now
            subscription.current_period_end = period_end
            subscription.grace_until = grace_until
            subscription.cancel_at_period_end = False

            existing_payment = db.execute(
                select(Payment).where(Payment.provider_payment_id == provider_payment_id)
            ).scalar_one_or_none()

            if existing_payment is None:
                payment = Payment(
                    user_id=subscription.user_id,
                    subscription_id=subscription.id,
                    provider="stripe",
                    provider_payment_id=provider_payment_id,
                    invoice_number=generate_invoice_number("INV-STRIPE"),
                    amount=amount if amount > 0 else (sub_plan.price_amount if sub_plan else Decimal("0")),
                    tax_amount=Decimal("0.00"),
                    currency=currency,
                    status="succeeded",
                    receipt_url=data_obj.get("hosted_invoice_url") or data_obj.get("receipt_url"),
                    paid_at=now,
                )
                db.add(payment)

    elif event_type in {"invoice.payment_failed"}:
        provider_sub_id = data_obj.get("subscription")
        provider_payment_id = (
            data_obj.get("payment_intent") or f"ch_failed_{uuid.uuid4().hex[:10]}"
        )

        subscription = None
        if provider_sub_id:
            subscription = db.execute(
                select(Subscription).where(Subscription.provider_subscription_id == provider_sub_id)
            ).scalar_one_or_none()

        if subscription is not None:
            if subscription.grace_until and subscription.grace_until > now:
                subscription.status = "past_due"
            else:
                subscription.status = "expired"

            payment = Payment(
                user_id=subscription.user_id,
                subscription_id=subscription.id,
                provider="stripe",
                provider_payment_id=provider_payment_id,
                invoice_number=generate_invoice_number("INV-STRIPE-FAIL"),
                amount=Decimal(data_obj.get("amount_due", 0)) / Decimal("100"),
                currency=(data_obj.get("currency") or "USD").upper(),
                status="failed",
                failure_reason="Stripe automatic invoice charge failed",
                paid_at=None,
            )
            db.add(payment)

    elif event_type in {"customer.subscription.deleted"}:
        provider_sub_id = data_obj.get("id")
        if provider_sub_id:
            sub = db.execute(
                select(Subscription).where(Subscription.provider_subscription_id == provider_sub_id)
            ).scalar_one_or_none()
            if sub:
                sub.status = "cancelled"
                sub.cancel_at_period_end = True
                sub.cancelled_at = now

    event_record.processing_status = "processed"
    event_record.processed_at = now
    db.commit()

    return WebhookEventResponse(status="success", provider="stripe", event_id=event_id)
