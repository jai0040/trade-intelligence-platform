"""Pydantic v2 schemas for user-isolated Trading Journal entries and analytics."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class JournalEntryCreateRequest(BaseModel):
    instrument_id: uuid.UUID
    market_id: uuid.UUID
    signal_id: uuid.UUID | None = None
    side: Literal["BUY", "SELL"]
    entry_price: Decimal = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0)
    currency: Literal["INR", "USD"] = "INR"
    exit_price: Decimal | None = Field(default=None, gt=0)
    planned_stop: Decimal | None = Field(default=None, gt=0)
    planned_target: Decimal | None = Field(default=None, gt=0)
    emotions_tags: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)
    entered_at_utc: datetime | None = None
    exited_at_utc: datetime | None = None


class JournalEntryUpdateRequest(BaseModel):
    exit_price: Decimal | None = Field(default=None, gt=0)
    planned_stop: Decimal | None = Field(default=None, gt=0)
    planned_target: Decimal | None = Field(default=None, gt=0)
    emotions_tags: list[str] | None = None
    notes: str | None = Field(default=None, max_length=2000)
    exited_at_utc: datetime | None = None


class JournalEntryResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    instrument_id: uuid.UUID
    market_id: uuid.UUID
    signal_id: uuid.UUID | None
    side: str
    entry_price: Decimal
    exit_price: Decimal | None
    quantity: Decimal
    planned_stop: Decimal | None
    planned_target: Decimal | None
    realized_pnl: Decimal | None
    currency: str
    emotions_tags: list[str]
    notes: str | None
    entered_at_utc: datetime
    exited_at_utc: datetime | None
    created_at: datetime
    updated_at: datetime


class JournalStatsResponse(BaseModel):
    total_trades: int
    open_trades: int
    closed_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal
    total_realized_pnl_inr: Decimal
    total_realized_pnl_usd: Decimal
    profit_factor: Decimal | None = None
    top_emotions: dict[str, int] = Field(default_factory=dict)


class JournalListResponse(BaseModel):
    total: int
    stats: JournalStatsResponse
    items: list[JournalEntryResponse]
