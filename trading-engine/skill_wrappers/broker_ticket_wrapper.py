"""Stateless wrapper for trader-broker: READ-ONLY trade ticket preview ONLY (SIGNALS-ONLY hard lock)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from domain.errors import SignalsOnlyPolicyError
from domain.models import Instrument, SignalType
from skill_wrappers.base import BaseSkill, SkillContext, SkillResult


class BrokerTicketSkillWrapper(BaseSkill):
    """Generates a read-only broker reference trade sheet. Live order submission is hard-prohibited."""

    skill_name = "trader-broker"

    def place_live_order(self, *args: Any, **kwargs: Any) -> None:
        """Hard-blocked method guaranteeing live broker order placement can never be invoked."""
        raise SignalsOnlyPolicyError(
            "Automated live broker order placement is strictly prohibited in SIGNALS_ONLY mode. "
            "Review the reference trade sheet and execute manually in your own broker if desired."
        )

    submit_order = place_live_order

    def _execute(self, ctx: SkillContext, payload: dict[str, Any]) -> SkillResult:
        if payload.get("execute_live") or payload.get("submit_order"):
            self.place_live_order()

        if payload.get("risk_validation_status") != "PASSED":
            return SkillResult(
                skill_name=self.skill_name,
                status="SKIPPED",
                data={"ticket": None},
                warnings=["Ticket preview skipped because trader-risk did not PASS."],
            )

        inst: Instrument = payload["instrument"]
        signal_type = str(payload["signal_type"]).upper()
        entry_price = Decimal(str(payload["entry_price"]))
        stop_loss = Decimal(str(payload["stop_loss"]))
        target_price = Decimal(str(payload["target_price"]))
        shares = int(payload.get("recommended_shares", 0))
        rr = str(payload.get("risk_reward_ratio", "2.00"))
        risk_fingerprint = str(payload.get("risk_fingerprint", ""))

        order_side = "SELL" if signal_type == SignalType.SELL.value else "BUY"
        currency_symbol = "₹" if inst.currency == "INR" else "$"

        ticket = {
            "mode": "SIGNALS_ONLY_READ_ONLY_PREVIEW",
            "auto_executed": False,
            "exchange": inst.exchange_code.value,
            "symbol": inst.symbol,
            "canonical_code": inst.canonical_code,
            "side": order_side,
            "order_type": "LIMIT",
            "product_type": "MIS / INTRADAY" if inst.currency == "INR" else "DAY",
            "currency": inst.currency,
            "reference_quantity": shares,
            "limit_entry_price": str(entry_price),
            "stop_loss_trigger": str(stop_loss),
            "target_price": str(target_price),
            "risk_reward_ratio": rr,
            "risk_fingerprint": risk_fingerprint,
            "formatted_summary": (
                f"[READ-ONLY TICKET] {order_side} {inst.canonical_code} @ "
                f"{currency_symbol}{entry_price} | SL {currency_symbol}{stop_loss} | "
                f"Target {currency_symbol}{target_price} (R:R {rr}x) — NOT PLACED"
            ),
            "disclaimer": (
                "Reference trade ticket only. No broker connection or automated order execution exists. "
                "Educational & informational signals only; not investment advice."
            ),
        }

        return SkillResult(
            skill_name=self.skill_name,
            status="SUCCEEDED",
            data={"ticket": ticket},
            metrics={"auto_executed": False},
        )
