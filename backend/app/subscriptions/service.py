"""Subscription entitlement evaluation and plan listing service (Phase 9 payment-ready)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, joinedload

from database.models.billing import Subscription, SubscriptionPlan

ADMIN_ROLES = frozenset({"super_admin", "admin"})
VALID_MARKETS = ("IN", "US")


@dataclass(frozen=True)
class UserEntitlement:
    subscription_status: str
    entitled_markets: list[str]
    is_entitled: bool
    subscription: Subscription | None = None


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_user_entitlement(
    db: DbSession,
    *,
    user_id: uuid.UUID,
    role_code: str,
    now: datetime | None = None,
) -> UserEntitlement:
    """Compute a user's authoritative subscription status and entitled markets.

    Privileged platform administrators receive read access to both markets while
    retaining any underlying subscription record if present.
    """
    current_time = now or datetime.now(timezone.utc)

    stmt = (
        select(Subscription)
        .options(joinedload(Subscription.plan))
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.updated_at.desc(), Subscription.created_at.desc())
        .limit(1)
    )
    latest = db.execute(stmt).scalar_one_or_none()

    if role_code in ADMIN_ROLES:
        return UserEntitlement(
            subscription_status="active",
            entitled_markets=list(VALID_MARKETS),
            is_entitled=True,
            subscription=latest,
        )

    if latest is None:
        return UserEntitlement(
            subscription_status="none",
            entitled_markets=[],
            is_entitled=False,
            subscription=None,
        )

    raw_status = (latest.status or "none").lower()
    period_end = _ensure_utc(latest.current_period_end)
    grace_until = _ensure_utc(latest.grace_until)
    plan_markets = [
        str(m).upper()
        for m in (latest.plan.entitled_markets if latest.plan else [])
        if str(m).upper() in VALID_MARKETS
    ]

    if raw_status in {"active", "trialing"}:
        if period_end is None or period_end > current_time:
            return UserEntitlement(
                subscription_status=raw_status,
                entitled_markets=plan_markets,
                is_entitled=bool(plan_markets),
                subscription=latest,
            )
        if grace_until is not None and grace_until > current_time:
            return UserEntitlement(
                subscription_status="past_due",
                entitled_markets=plan_markets,
                is_entitled=bool(plan_markets),
                subscription=latest,
            )
        return UserEntitlement(
            subscription_status="expired",
            entitled_markets=[],
            is_entitled=False,
            subscription=latest,
        )

    if raw_status == "past_due":
        if grace_until is not None and grace_until > current_time:
            return UserEntitlement(
                subscription_status="past_due",
                entitled_markets=plan_markets,
                is_entitled=bool(plan_markets),
                subscription=latest,
            )
        return UserEntitlement(
            subscription_status="expired",
            entitled_markets=[],
            is_entitled=False,
            subscription=latest,
        )

    if raw_status == "cancelled":
        if period_end is not None and period_end > current_time:
            return UserEntitlement(
                subscription_status="cancelled",
                entitled_markets=plan_markets,
                is_entitled=bool(plan_markets),
                subscription=latest,
            )
        return UserEntitlement(
            subscription_status="expired",
            entitled_markets=[],
            is_entitled=False,
            subscription=latest,
        )

    normalized = raw_status if raw_status in {"expired", "none"} else "none"
    return UserEntitlement(
        subscription_status=normalized,
        entitled_markets=[],
        is_entitled=False,
        subscription=latest,
    )


def list_active_plans(db: DbSession) -> list[SubscriptionPlan]:
    """Return active public subscription plans ordered by currency and price."""
    stmt = (
        select(SubscriptionPlan)
        .where(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.currency.asc(), SubscriptionPlan.price_amount.asc())
    )
    return list(db.execute(stmt).scalars().all())
