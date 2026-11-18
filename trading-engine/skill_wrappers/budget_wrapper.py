"""Stateless wrapper for trader-budget: deterministic Decimal position sizing (model & personal)."""

from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR
from typing import Any

from domain.models import Instrument, MarketCode
from skill_wrappers.base import BaseSkill, SkillContext, SkillResult


def calculate_position_size(
    *,
    entry_price: Decimal,
    stop_loss: Decimal,
    capital_budget: Decimal,
    max_loss_amount: Decimal,
    max_position_pct: Decimal = Decimal("0.25"),
    lot_size: int = 1,
    currency: str = "INR",
) -> dict[str, Any]:
    """Deterministic Decimal share sizing respecting risk cap, capital cap, position cap, and lot size."""
    if entry_price <= Decimal("0"):
        raise ValueError("entry_price must be positive.")
    if capital_budget <= Decimal("0"):
        raise ValueError("capital_budget must be positive.")
    if max_loss_amount <= Decimal("0"):
        raise ValueError("max_loss_amount must be positive.")
    if lot_size < 1:
        raise ValueError("lot_size must be >= 1.")

    risk_per_share = abs(entry_price - stop_loss)
    if risk_per_share <= Decimal("0"):
        raise ValueError("stop_loss cannot equal entry_price.")

    shares_by_risk = int((max_loss_amount / risk_per_share).to_integral_value(rounding=ROUND_FLOOR))
    shares_by_capital = int((capital_budget / entry_price).to_integral_value(rounding=ROUND_FLOOR))
    max_pos_notional = capital_budget * max_position_pct
    shares_by_pos_cap = int((max_pos_notional / entry_price).to_integral_value(rounding=ROUND_FLOOR))

    raw_shares = min(shares_by_risk, shares_by_capital, shares_by_pos_cap)
    # Round down to valid exchange lot size multiple
    recommended_shares = (raw_shares // lot_size) * lot_size

    if recommended_shares <= 0:
        binding_limit = "INSUFFICIENT_BUDGET_OR_RISK_CAP"
    elif shares_by_risk <= shares_by_capital and shares_by_risk <= shares_by_pos_cap:
        binding_limit = "RISK_CAP"
    elif shares_by_pos_cap <= shares_by_capital:
        binding_limit = "POSITION_PCT_CAP"
    else:
        binding_limit = "CAPITAL_CAP"

    position_notional = (Decimal(recommended_shares) * entry_price).quantize(Decimal("0.01"))
    max_dollar_risk = (Decimal(recommended_shares) * risk_per_share).quantize(Decimal("0.01"))
    capital_utilization_pct = (
        (position_notional / capital_budget) * Decimal("100")
    ).quantize(Decimal("0.01"))

    return {
        "currency": currency,
        "recommended_shares": recommended_shares,
        "lot_size": lot_size,
        "binding_limit": binding_limit,
        "shares_by_risk_cap": shares_by_risk,
        "shares_by_capital_cap": shares_by_capital,
        "shares_by_position_pct_cap": shares_by_pos_cap,
        "risk_per_share": risk_per_share.quantize(Decimal("0.0001")),
        "position_notional": position_notional,
        "estimated_max_loss": max_dollar_risk,
        "capital_utilization_pct": capital_utilization_pct,
    }


class BudgetSkillWrapper(BaseSkill):
    """Computes reference model sizing for signals or personal sizing for a subscriber."""

    skill_name = "trader-budget"

    def _execute(self, ctx: SkillContext, payload: dict[str, Any]) -> SkillResult:
        inst: Instrument = payload["instrument"]
        entry_price = Decimal(str(payload["entry_price"]))
        stop_loss = Decimal(str(payload["stop_loss"]))

        default_budget = Decimal("200000.00") if inst.market_code == MarketCode.IN else Decimal("5000.00")
        default_max_loss = Decimal("2000.00") if inst.market_code == MarketCode.IN else Decimal("50.00")

        capital_budget = Decimal(str(payload.get("capital_budget", default_budget)))
        max_loss_amount = Decimal(str(payload.get("max_loss_amount", default_max_loss)))
        max_position_pct = Decimal(str(payload.get("max_position_pct", "0.25")))

        sizing = calculate_position_size(
            entry_price=entry_price,
            stop_loss=stop_loss,
            capital_budget=capital_budget,
            max_loss_amount=max_loss_amount,
            max_position_pct=max_position_pct,
            lot_size=inst.lot_size,
            currency=inst.currency,
        )
        return SkillResult(
            skill_name=self.skill_name,
            status="SUCCEEDED",
            data=sizing,
            metrics={"recommended_shares": sizing["recommended_shares"]},
        )
