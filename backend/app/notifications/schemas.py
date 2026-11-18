"""Pydantic v2 schemas for user-isolated in-app notifications and delivery preferences."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: uuid.UUID
    category: str
    title: str
    body: str
    payload: dict[str, Any]
    is_read: bool
    read_at_utc: datetime | None
    created_at_utc: datetime


class NotificationListResponse(BaseModel):
    unread_count: int
    total: int
    items: list[NotificationResponse]


class NotificationPreferencesResponse(BaseModel):
    in_app_enabled: bool
    browser_push_enabled: bool
    email_enabled: bool
    notify_new_signals: bool
    notify_entry_hit: bool
    notify_target_hit: bool
    notify_stop_hit: bool
    notify_signal_expiry: bool
    notify_market_news: bool
    notify_market_reports: bool
    market_filter: str
    quiet_hours_json: dict[str, Any]
    updated_at: datetime


class NotificationPreferencesUpdateRequest(BaseModel):
    in_app_enabled: bool | None = None
    browser_push_enabled: bool | None = None
    email_enabled: bool | None = None
    notify_new_signals: bool | None = None
    notify_entry_hit: bool | None = None
    notify_target_hit: bool | None = None
    notify_stop_hit: bool | None = None
    notify_signal_expiry: bool | None = None
    notify_market_news: bool | None = None
    notify_market_reports: bool | None = None
    market_filter: Literal["ALL", "IN", "US"] | None = None
    quiet_hours_json: dict[str, Any] | None = Field(default=None)
