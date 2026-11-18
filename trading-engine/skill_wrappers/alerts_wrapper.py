"""Stateless wrapper for trader-alerts evaluating signal lifecycle & user alert rules."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from domain.models import Instrument, SignalStatus, SignalType
from skill_wrappers.base import BaseSkill, SkillContext, SkillResult


class AlertsSkillWrapper(BaseSkill):
    """Evaluates active signals and custom price/threshold alerts against fresh quotes."""

    skill_name = "trader-alerts"

    def _execute(self, ctx: SkillContext, payload: dict[str, Any]) -> SkillResult:
        signals: list[dict[str, Any]] = list(payload.get("active_signals") or [])
        user_alerts: list[dict[str, Any]] = list(payload.get("user_alerts") or [])
        instruments: list[Instrument] = list(payload.get("instruments") or [])

        quotes = (
            ctx.data_provider.get_quotes(instruments, as_of_utc=ctx.as_of_utc)
            if instruments
            else {}
        )

        signal_transitions: list[dict[str, Any]] = []
        triggered_alerts: list[dict[str, Any]] = []

        for sig in signals:
            inst_id = str(sig["instrument_id"])
            quote = quotes.get(inst_id)
            if quote is None:
                continue
            status = str(sig["current_status"])
            sig_type = str(sig["signal_type"]).upper()
            entry = Decimal(str(sig["entry_price"]))
            stop = Decimal(str(sig["stop_loss"]))
            target = Decimal(str(sig["target_price"]))
            expires_at = sig.get("expires_at_utc")

            new_status: str | None = None
            reason = ""

            if expires_at is not None and ctx.as_of_utc >= expires_at and status in {
                SignalStatus.PENDING.value,
                SignalStatus.ACTIVE.value,
            }:
                new_status = SignalStatus.EXPIRED.value
                reason = "Signal validity window expired before trigger."
            elif status == SignalStatus.ACTIVE.value:
                if (sig_type == SignalType.BUY.value and quote.last_price >= entry) or (
                    sig_type == SignalType.SELL.value and quote.last_price <= entry
                ):
                    new_status = SignalStatus.TRIGGERED.value
                    reason = f"Entry level {entry} triggered at {quote.last_price}."
            elif status == SignalStatus.TRIGGERED.value:
                if (sig_type == SignalType.BUY.value and quote.last_price <= stop) or (
                    sig_type == SignalType.SELL.value and quote.last_price >= stop
                ):
                    new_status = SignalStatus.STOP_LOSS_HIT.value
                    reason = f"Stop-loss level {stop} reached at {quote.last_price}."
                elif (sig_type == SignalType.BUY.value and quote.last_price >= target) or (
                    sig_type == SignalType.SELL.value and quote.last_price <= target
                ):
                    new_status = SignalStatus.TARGET_HIT.value
                    reason = f"Target level {target} reached at {quote.last_price}."

            if new_status is not None:
                signal_transitions.append(
                    {
                        "signal_id": sig["id"],
                        "previous_status": status,
                        "new_status": new_status,
                        "trigger_price": quote.last_price,
                        "bar_timestamp_utc": quote.quote_timestamp_utc,
                        "reason": reason,
                    }
                )

        for alert in user_alerts:
            if not alert.get("is_active", True):
                continue
            quote = quotes.get(str(alert.get("instrument_id", "")))
            if quote is None or alert.get("threshold_value") is None:
                continue
            rule = str(alert["rule_type"]).upper()
            threshold = Decimal(str(alert["threshold_value"]))
            fired = (rule == "PRICE_ABOVE" and quote.last_price >= threshold) or (
                rule == "PRICE_BELOW" and quote.last_price <= threshold
            )
            if fired:
                triggered_alerts.append(
                    {
                        "alert_id": alert["id"],
                        "user_id": alert["user_id"],
                        "rule_type": rule,
                        "threshold_value": str(threshold),
                        "observed_price": str(quote.last_price),
                        "triggered_at_utc": ctx.as_of_utc.isoformat(),
                    }
                )

        return SkillResult(
            skill_name=self.skill_name,
            status="SUCCEEDED",
            data={
                "signal_transitions": signal_transitions,
                "triggered_alerts": triggered_alerts,
            },
            metrics={
                "signals_evaluated": len(signals),
                "transitions_count": len(signal_transitions),
                "alerts_triggered": len(triggered_alerts),
            },
        )
