"""Pydantic schemas for checkout, payment history, and webhook responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: uuid.UUID
    provider: Literal["razorpay", "stripe"]
    return_url: str | None = Field(default=None, max_length=1024)


class CheckoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    checkout_url: str | None = None
    provider: str
    provider_session_id: str | None = None
    provider_order_id: str | None = None
    public_key: str
    currency: str
    amount: Decimal
    plan_id: uuid.UUID
    plan_name: str
    plan_code: str


class SubscriptionCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class SubscriptionCancelResponse(BaseModel):
    status: str
    cancel_at_period_end: bool
    cancelled_at: datetime | None
    current_period_end: datetime | None
    message: str


class PaymentHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str
    provider: str
    provider_payment_id: str
    amount: Decimal
    tax_amount: Decimal
    currency: str
    status: str
    failure_reason: str | None = None
    receipt_url: str | None = None
    paid_at: datetime | None = None
    created_at: datetime
    plan_name: str | None = None


class PaymentHistoryResponse(BaseModel):
    items: list[PaymentHistoryItem]
    total: int


class WebhookEventResponse(BaseModel):
    status: str
    provider: str
    event_id: str
    message: str | None = None
