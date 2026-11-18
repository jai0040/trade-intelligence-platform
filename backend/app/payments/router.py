"""Payment endpoints: checkout sessions, payment history, and verified webhooks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session as DbSession

from app.authentication.dependencies import (
    AuthContext,
    get_app_settings,
    get_current_auth,
    get_db,
    require_csrf,
)
from app.core.config import Settings
from app.payments.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PaymentHistoryResponse,
    SubscriptionCancelRequest,
    SubscriptionCancelResponse,
    WebhookEventResponse,
)
from app.payments.service import (
    cancel_user_subscription,
    create_checkout_session,
    get_payment_history,
    process_razorpay_webhook,
    process_stripe_webhook,
)

router = APIRouter(tags=["payments"])


@router.post(
    "/subscriptions/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_csrf)],
)
def create_checkout(
    request_data: CheckoutRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> CheckoutResponse:
    """Create a checkout session for Razorpay (INR) or Stripe (USD).

    Requires authentication and double-submit CSRF token.
    """
    return create_checkout_session(
        db,
        user_id=auth.user.id,
        request=request_data,
        settings=settings,
    )


@router.post(
    "/subscriptions/cancel",
    response_model=SubscriptionCancelResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_csrf)],
)
def cancel_subscription(
    request_data: SubscriptionCancelRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> SubscriptionCancelResponse:
    """Schedule user subscription cancellation at the end of the billing period."""
    return cancel_user_subscription(
        db,
        user_id=auth.user.id,
        reason=request_data.reason,
    )


@router.get(
    "/payments/history",
    response_model=PaymentHistoryResponse,
    status_code=status.HTTP_200_OK,
)
def list_payments(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> PaymentHistoryResponse:
    """List authenticated user's historical invoices and receipts (strictly user-isolated)."""
    return get_payment_history(
        db,
        user_id=auth.user.id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/webhooks/razorpay",
    response_model=WebhookEventResponse,
    status_code=status.HTTP_200_OK,
)
async def razorpay_webhook(
    request: Request,
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WebhookEventResponse:
    """Public webhook receiver for Razorpay payments and subscriptions.

    Cryptographically verified via constant-time HMAC-SHA256 signature and deduplicated via PaymentEvents.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    return process_razorpay_webhook(
        db,
        raw_body=raw_body,
        signature=signature,
        settings=settings,
    )


@router.post(
    "/webhooks/stripe",
    response_model=WebhookEventResponse,
    status_code=status.HTTP_200_OK,
)
async def stripe_webhook(
    request: Request,
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WebhookEventResponse:
    """Public webhook receiver for Stripe payments and subscriptions.

    Cryptographically verified via Stripe-Signature header with timestamp tolerance and deduplicated via PaymentEvents.
    """
    raw_body = await request.body()
    signature_header = request.headers.get("Stripe-Signature")
    return process_stripe_webhook(
        db,
        raw_body=raw_body,
        signature_header=signature_header,
        settings=settings,
    )
