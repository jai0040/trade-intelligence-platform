"""Pydantic v2 schemas for subscription plans and user entitlements."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class SubscriptionPlanResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str
    currency: str
    price_amount: Decimal
    billing_interval: str
    grace_period_days: int
    entitled_markets: list[str]
    features: dict[str, Any]
    is_active: bool


class UserSubscriptionResponse(BaseModel):
    subscription_status: str
    entitled_markets: list[str]
    is_entitled: bool
    plan: SubscriptionPlanResponse | None = None
    provider: str | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    grace_until: datetime | None = None
    cancel_at_period_end: bool = False
