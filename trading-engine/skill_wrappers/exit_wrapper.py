"""Stateless wrapper for trader-exit computing Decimal tick-aligned stop-loss and target levels."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from domain.models import Instrument, SignalType
from skill_wrappers.base import BaseSkill, SkillContext, SkillResult


class ExitSkillWrapper(BaseSkill):
    """Calculates deterministic Decimal stop-loss, target, and R:R for BUY, SELL, and WATCH setups."""

    skill_name = "trader-exit"

    def _execute(self, ctx: SkillContext, payload: dict[str, Any]) -> SkillResult:
        inst: Instrument = payload["instrument"]
        signal_type = str(payload.get("signal_type", SignalType.BUY.value)).upper()
        entry_price = Decimal(str(payload["entry_price"]))
        atr_14 = Decimal(str(payload.get("atr_14", "0")))
        target_rr = Decimal(str(payload.get("target_rr", "2.0")))
        atr_stop_mult = Decimal(str(payload.get("atr_stop_mult", "1.25")))

        if entry_price <= Decimal("0"):
            raise ValueError("entry_price must be strictly positive.")

        # Default fallback risk distance = 1.5% if ATR is tiny/missing
        raw_risk = atr_14 * atr_stop_mult if atr_14 > Decimal("0") else entry_price * Decimal("0.015")
        # Clamp raw risk between 0.5% and 5.0% of entry price for clean intraday geometry
        min_risk = entry_price * Decimal("0.005")
        max_risk = entry_price * Decimal("0.05")
        raw_risk = max(min_risk, min(max_risk, raw_risk))

        entry_rounded = ctx.market_adapter.round_to_tick(entry_price, inst, "nearest")

        if signal_type == SignalType.SELL.value:
            # Short trade: stop ABOVE entry (rounded UP conservatively), target BELOW entry (rounded UP)
            stop_loss = ctx.market_adapter.round_to_tick(entry_rounded + raw_risk, inst, "up")
            risk_per_share = stop_loss - entry_rounded
            target_price = ctx.market_adapter.round_to_tick(
                entry_rounded - (risk_per_share * target_rr), inst, "up"
            )
            reward_per_share = entry_rounded - target_price
        else:
            # Long (BUY / WATCH): stop BELOW entry (rounded DOWN conservatively), target ABOVE entry (rounded DOWN)
            stop_loss = ctx.market_adapter.round_to_tick(entry_rounded - raw_risk, inst, "down")
            risk_per_share = entry_rounded - stop_loss
            target_price = ctx.market_adapter.round_to_tick(
                entry_rounded + (risk_per_share * target_rr), inst, "down"
            )
            reward_per_share = target_price - entry_rounded

        if risk_per_share <= Decimal("0"):
            raise ValueError("Computed stop-loss yields non-positive risk per share.")

        rr_ratio = (reward_per_share / risk_per_share).quantize(Decimal("0.001"))
        stop_distance_pct = ((risk_per_share / entry_rounded) * Decimal("100")).quantize(
            Decimal("0.01")
        )

        return SkillResult(
            skill_name=self.skill_name,
            status="SUCCEEDED",
            data={
                "signal_type": signal_type,
                "entry_price": entry_rounded,
                "stop_loss": stop_loss,
                "target_price": target_price,
                "risk_per_share": risk_per_share,
                "reward_per_share": reward_per_share,
                "risk_reward_ratio": rr_ratio,
                "stop_distance_pct": stop_distance_pct,
                "currency": inst.currency,
            },
            metrics={"target_rr_requested": float(target_rr)},
        )
