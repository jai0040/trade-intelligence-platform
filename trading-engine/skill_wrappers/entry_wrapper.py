"""Stateless wrapper for trader-entry enforcing completed-bar confirmation for BUY, SELL, and WATCH."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from data_providers.freshness import filter_completed_bars
from domain.models import Instrument, SignalType
from skill_wrappers.base import BaseSkill, SkillContext, SkillResult


class EntrySkillWrapper(BaseSkill):
    """Confirms entry strictly on completed bars (never triggers early on forming bars)."""

    skill_name = "trader-entry"

    def _execute(self, ctx: SkillContext, payload: dict[str, Any]) -> SkillResult:
        inst: Instrument = payload["instrument"]
        level_price = Decimal(str(payload["level_price"]))
        signal_bias = str(payload.get("signal_bias", SignalType.BUY.value)).upper()
        setup_type = str(payload.get("setup_type", "orb_15m"))
        timeframe = str(payload.get("timeframe", "5m"))
        min_volume_x = Decimal(str(payload.get("min_volume_x", "0.80")))

        lookback_days = 10 if timeframe == "1d" else 3
        raw_bars = ctx.data_provider.get_bars(
            inst,
            timeframe,
            ctx.as_of_utc - timedelta(days=lookback_days),
            ctx.as_of_utc,
        )
        bars = filter_completed_bars(raw_bars, as_of_utc=ctx.as_of_utc)
        if len(bars) < 4:
            return SkillResult(
                skill_name=self.skill_name,
                status="PARTIAL",
                data={"state": "WAITING", "reason": "Insufficient completed bars"},
                warnings=["Fewer than 4 completed bars available"],
            )

        or_bars = bars[:3]
        or_high = max(b.high for b in or_bars)
        or_low = min(b.low for b in or_bars)
        or_avg_vol = sum(b.volume for b in or_bars) / max(1, len(or_bars))

        effective_level = (
            or_high
            if setup_type.startswith("orb") and signal_bias == SignalType.BUY.value
            else or_low
            if setup_type.startswith("orb") and signal_bias == SignalType.SELL.value
            else level_price
        )

        triggered_bar = None
        trigger_vol_x = Decimal("0")
        for bar in bars[3:]:
            vol_x = Decimal(str(round(bar.volume / max(1.0, or_avg_vol), 2)))
            if signal_bias == SignalType.BUY.value and bar.close > effective_level and vol_x >= min_volume_x:
                triggered_bar = bar
                trigger_vol_x = vol_x
                break
            if signal_bias == SignalType.SELL.value and bar.close < effective_level and vol_x >= min_volume_x:
                triggered_bar = bar
                trigger_vol_x = vol_x
                break

        latest_bar = bars[-1]
        if triggered_bar is not None:
            entry_price = ctx.market_adapter.round_to_tick(triggered_bar.close, inst, "nearest")
            return SkillResult(
                skill_name=self.skill_name,
                status="SUCCEEDED",
                data={
                    "state": "TRIGGERED",
                    "signal_type": signal_bias,
                    "entry_price": entry_price,
                    "reference_level": ctx.market_adapter.round_to_tick(effective_level, inst, "nearest"),
                    "opening_range_high": or_high,
                    "opening_range_low": or_low,
                    "trigger_bar_end_utc": triggered_bar.bar_end_utc,
                    "trigger_volume_x": trigger_vol_x,
                    "timeframe": timeframe,
                },
                metrics={"completed_bars_evaluated": len(bars)},
            )

        # Not yet triggered -> emit WATCH candidate using current close / breakout level
        watch_price = ctx.market_adapter.round_to_tick(latest_bar.close, inst, "nearest")
        distance_pct = (
            abs(effective_level - latest_bar.close) / max(Decimal("0.01"), latest_bar.close)
        ) * Decimal("100")
        return SkillResult(
            skill_name=self.skill_name,
            status="SUCCEEDED",
            data={
                "state": "WAITING",
                "signal_type": SignalType.WATCH.value if signal_bias == SignalType.WATCH.value else signal_bias,
                "entry_price": watch_price,
                "reference_level": ctx.market_adapter.round_to_tick(effective_level, inst, "nearest"),
                "opening_range_high": or_high,
                "opening_range_low": or_low,
                "trigger_bar_end_utc": latest_bar.bar_end_utc,
                "trigger_volume_x": Decimal("1.00"),
                "distance_to_level_pct": distance_pct.quantize(Decimal("0.01")),
                "timeframe": timeframe,
            },
            metrics={"completed_bars_evaluated": len(bars)},
        )
