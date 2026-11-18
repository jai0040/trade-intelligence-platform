"""Pydantic v2 schemas for RBAC-protected Admin user & session controls."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

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
