"""Pydantic v2 schemas for strictly user-isolated profile, preferences, and watchlists."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    country_code: Literal["IN", "US", "GB", "SG", "AE", "CA", "AU"] | None = None

    @field_validator("full_name")
    @classmethod
    def check_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        return cleaned


class UserPreferencesResponse(BaseModel):
    default_market: str
    theme: str
    display_timezone: str
    default_budget_inr: Decimal
    default_max_loss_inr: Decimal
    default_budget_usd: Decimal
    default_max_loss_usd: Decimal
    updated_at: datetime


class UserPreferencesUpdateRequest(BaseModel):
    default_market: Literal["ALL", "IN", "US"] | None = None
    theme: Literal["dark", "light"] | None = None
    display_timezone: str | None = Field(default=None, min_length=3, max_length=64)
    default_budget_inr: Decimal | None = Field(default=None, gt=0, le=Decimal("1000000000"))
    default_max_loss_inr: Decimal | None = Field(default=None, gt=0, le=Decimal("100000000"))
    default_budget_usd: Decimal | None = Field(default=None, gt=0, le=Decimal("100000000"))
    default_max_loss_usd: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000"))


class WatchlistCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    market_scope: Literal["ALL", "IN", "US"] = "ALL"

    @field_validator("name")
    @classmethod
    def check_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Watchlist name cannot be blank.")
        return cleaned


class WatchlistUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    market_scope: Literal["ALL", "IN", "US"] | None = None

    @field_validator("name")
    @classmethod
    def check_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Watchlist name cannot be blank.")
        return cleaned


class WatchlistItemCreateRequest(BaseModel):
    instrument_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=1000)


class WatchlistItemResponse(BaseModel):
    id: uuid.UUID
    watchlist_id: uuid.UUID
    instrument_id: uuid.UUID
    notes: str | None
    created_at: datetime


class WatchlistResponse(BaseModel):
    id: uuid.UUID
    name: str
    market_scope: str
    is_default: bool
    created_at: datetime
    updated_at: datetime
    items: list[WatchlistItemResponse] = Field(default_factory=list)
