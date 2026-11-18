"""Pydantic v2 schemas for scanner hits, signals, news, disclosures, position sizing, and AI queries."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class PositionSizeRequest(BaseModel):
    market_code: Literal["IN", "US"]
    exchange_code: Literal["NSE", "BSE", "NASDAQ", "NYSE"]
    symbol: str = Field(..., min_length=1, max_length=24)
    signal_type: Literal["BUY", "SELL"] = "BUY"
    entry_price: Decimal = Field(..., gt=0)
    stop_loss: Decimal = Field(..., gt=0)
    target_price: Decimal = Field(..., gt=0)
    capital_budget: Decimal = Field(..., gt=0)
    max_loss_amount: Decimal = Field(..., gt=0)
    max_position_pct: Decimal = Field(default=Decimal("0.25"), gt=0, le=Decimal("1.0"))
    lot_size: int = Field(default=1, ge=1)


class PositionSizeResponse(BaseModel):
    mode: str = "SIGNALS_ONLY_CALCULATOR"
    order_placed: bool = False
    sizing: dict[str, Any]
    risk_validation: dict[str, Any]
    disclaimer: str


class AIAnalystQueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=600)
    market_code: Literal["ALL", "IN", "US"] = "ALL"


class AIAnalystQueryResponse(BaseModel):
    provider: str
    question: str
    market_scope: str
    referenced_signal_ids: list[str]
    answer: str
    disclaimer: str


class KillSwitchUpdateRequest(BaseModel):
    enabled: bool
    reason: str = Field(..., min_length=3, max_length=256)


class KillSwitchResponse(BaseModel):
    enabled: bool
    reason: str
    message: str


class ManualWorkflowTriggerRequest(BaseModel):
    market_code: Literal["IN", "US"]
    mode: Literal["daily", "orb"] = "orb"
