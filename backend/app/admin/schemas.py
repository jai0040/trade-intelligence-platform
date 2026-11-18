"""Pydantic v2 schemas for RBAC-protected Admin user & session controls and Super Admin platform management."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class AdminUserStatusUpdateRequest(BaseModel):
    is_active: bool
    reason: str = Field(default="Administrative status update", min_length=3, max_length=256)


class AdminRevokeSessionRequest(BaseModel):
    reason: str = Field(default="Session revoked by administrator", min_length=3, max_length=256)


class AdminRevokeSessionResponse(BaseModel):
    user_id: uuid.UUID
    revoked_sessions_count: int
    message: str


class AdminUserStatusResponse(BaseModel):
    user_id: uuid.UUID
    is_active: bool
    revoked_sessions_count: int


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    metadata: dict[str, Any]
    ip_address: str | None
    created_at: datetime


class AdminOverviewResponse(BaseModel):
    total_users: int
    active_users: int
    inactive_users: int
    subscriptions_by_status: dict[str, int]
    mrr_inr: Decimal
    mrr_usd: Decimal
    active_sessions_count: int
    kill_switch: dict[str, Any]
    trading_mode: str


class AdminUserListItemResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    country_code: str
    is_active: bool
    is_email_verified: bool
    created_at: datetime
    last_login_at: datetime | None
    active_session: dict[str, Any] | None = None
    subscription: dict[str, Any] | None = None


class AdminUserListResponse(BaseModel):
    total: int
    items: list[AdminUserListItemResponse]


class AdminPlanCreateRequest(BaseModel):
    code: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=3, max_length=120)
    description: str = Field(default="", max_length=500)
    currency: Literal["INR", "USD"]
    price_amount: Decimal = Field(..., ge=0)
    billing_interval: Literal["monthly", "yearly"] = "monthly"
    grace_period_days: int = Field(default=3, ge=0, le=30)
    entitled_markets: list[Literal["IN", "US"]] = Field(..., min_length=1)
    features: dict[str, Any] = Field(default_factory=dict)


class AdminPlanResponse(BaseModel):
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
    created_at: datetime
