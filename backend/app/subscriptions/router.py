"""Public plan catalog and authenticated user entitlement endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.authentication.dependencies import AuthContext, get_current_auth, get_db
from app.subscriptions.schemas import SubscriptionPlanResponse, UserSubscriptionResponse
from app.subscriptions.service import get_user_entitlement, list_active_plans

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _serialize_plan(plan) -> SubscriptionPlanResponse:
    return SubscriptionPlanResponse(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        description=plan.description,
        currency=plan.currency,
        price_amount=plan.price_amount,
        billing_interval=plan.billing_interval,
        grace_period_days=plan.grace_period_days,
        entitled_markets=list(plan.entitled_markets or []),
        features=dict(plan.features or {}),
        is_active=plan.is_active,
    )


@router.get("/plans", response_model=list[SubscriptionPlanResponse])
def get_subscription_plans(db: DbSession = Depends(get_db)) -> list[SubscriptionPlanResponse]:
    """List active public subscription plans (INR & USD)."""
    plans = list_active_plans(db)
    return [_serialize_plan(p) for p in plans]


@router.get("/me", response_model=UserSubscriptionResponse)
def get_my_subscription(
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> UserSubscriptionResponse:
    """Return the authenticated user's current subscription and market entitlements."""
    entitlement = get_user_entitlement(db, user_id=auth.user.id, role_code=auth.role_code)
    sub = entitlement.subscription
    return UserSubscriptionResponse(
        subscription_status=entitlement.subscription_status,
        entitled_markets=entitlement.entitled_markets,
        is_entitled=entitlement.is_entitled,
        plan=_serialize_plan(sub.plan) if sub and sub.plan else None,
        provider=sub.provider if sub else None,
        current_period_start=sub.current_period_start if sub else None,
        current_period_end=sub.current_period_end if sub else None,
        grace_until=sub.grace_until if sub else None,
        cancel_at_period_end=sub.cancel_at_period_end if sub else False,
    )
