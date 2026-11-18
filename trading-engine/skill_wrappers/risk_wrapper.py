"""Stateless wrapper for trader-risk delegating to the mandatory non-overridable Risk Engine."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from domain.models import Instrument
from risk_engine.validator import validate_signal_risk
from skill_wrappers.base import BaseSkill, SkillContext, SkillResult


class RiskSkillWrapper(BaseSkill):
    """Mandatory non-overridable risk validation gate for platform signals and personal sizing."""

    skill_name = "trader-risk"

    def _execute(self, ctx: SkillContext, payload: dict[str, Any]) -> SkillResult:
        inst: Instrument = payload["instrument"]
        res = validate_signal_risk(
            instrument=inst,
            market_adapter=ctx.market_adapter,
            signal_type=str(payload["signal_type"]),
            entry_price=Decimal(str(payload["entry_price"])),
            stop_loss=Decimal(str(payload["stop_loss"])),
            target_price=Decimal(str(payload["target_price"])),
            risk_reward_ratio=Decimal(str(payload["risk_reward_ratio"])),
            quote_is_stale=bool(payload.get("quote_is_stale", False)),
            as_of_utc=ctx.as_of_utc,
            trading_mode=str(ctx.config.get("trading_mode", "SIGNALS_ONLY")),
            min_risk_reward=Decimal(str(ctx.config.get("min_risk_reward", "1.50"))),
            max_stop_distance_pct=Decimal(str(ctx.config.get("max_stop_distance_pct", "8.00"))),
            enforce_entry_window=bool(payload.get("enforce_entry_window", False)),
            recommended_shares=payload.get("recommended_shares"),
        )
        return SkillResult(
            skill_name=self.skill_name,
            status="SUCCEEDED",
            data={
                "risk_validation_status": res.status,
                "passed": res.passed,
                "blocking_reasons": res.blocking_reasons,
                "checks": res.checks,
                "risk_fingerprint": res.risk_fingerprint,
            },
            warnings=res.warnings,
            metrics={"passed": res.passed, "block_count": len(res.blocking_reasons)},
        )
