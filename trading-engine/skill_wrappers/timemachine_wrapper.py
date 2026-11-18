"""Stateless wrapper for trader-timemachine: seeded Monte Carlo + 60d historical replay (75/78 bars)."""

from __future__ import annotations

import hashlib
import math
import random
from datetime import timedelta
from decimal import Decimal
from typing import Any

from data_providers.freshness import filter_completed_bars
from domain.models import Instrument, SignalType
from skill_wrappers.base import BaseSkill, SkillContext, SkillResult


class TimeMachineSkillWrapper(BaseSkill):
    """Runs deterministic seeded Monte Carlo and historical bar replay parameterized by market bars."""

    skill_name = "trader-timemachine"

    def _execute(self, ctx: SkillContext, payload: dict[str, Any]) -> SkillResult:
        inst: Instrument = payload["instrument"]
        signal_type = str(payload.get("signal_type", SignalType.BUY.value)).upper()
        entry_price = float(Decimal(str(payload["entry_price"])))
        stop_loss = float(Decimal(str(payload["stop_loss"])))
        target_price = float(Decimal(str(payload["target_price"])))
        mc_paths = int(payload.get("mc_paths", 2000))
        session_bars = ctx.market_adapter.session_5m_bar_count  # 75 (India) | 78 (US)

        raw_daily = ctx.data_provider.get_bars(
            inst,
            "1d",
            ctx.as_of_utc - timedelta(days=95),
            ctx.as_of_utc,
        )
        daily_bars = filter_completed_bars(raw_daily)
        if len(daily_bars) < 15:
            return SkillResult(
                skill_name=self.skill_name,
                status="PARTIAL",
                data={"sample_size": len(daily_bars), "session_5m_bars_used": session_bars},
                warnings=["Insufficient historical daily bars for replay"],
            )

        # Estimate empirical daily log-return drift & volatility from historical bars
        log_rets: list[float] = []
        for idx in range(1, len(daily_bars)):
            prev_c = float(daily_bars[idx - 1].close)
            curr_c = float(daily_bars[idx].close)
            if prev_c > 0 and curr_c > 0:
                log_rets.append(math.log(curr_c / prev_c))

        mean_daily = sum(log_rets) / max(1, len(log_rets))
        var_daily = sum((r - mean_daily) ** 2 for r in log_rets) / max(1, len(log_rets) - 1)
        sigma_daily = max(0.005, math.sqrt(max(0.0, var_daily)))

        # Historical directional replay over trailing 60 daily bars
        replay_window = daily_bars[-60:]
        risk_pct = abs(entry_price - stop_loss) / max(0.01, entry_price)
        reward_pct = abs(target_price - entry_price) / max(0.01, entry_price)

        hist_target_hits = 0
        hist_stop_hits = 0
        for bar in replay_window:
            o = float(bar.open)
            h = float(bar.high)
            l = float(bar.low)
            if signal_type == SignalType.SELL.value:
                hit_stop = h >= o * (1.0 + risk_pct)
                hit_target = l <= o * (1.0 - reward_pct)
            else:
                hit_stop = l <= o * (1.0 - risk_pct)
                hit_target = h >= o * (1.0 + reward_pct)
            if hit_stop:
                hist_stop_hits += 1
            elif hit_target:
                hist_target_hits += 1

        sample_size = len(replay_window)
        hist_hit_rate = round((hist_target_hits / max(1, sample_size)) * 100.0, 2)

        # Seeded intraday Monte Carlo over remaining 5-minute bars in a market session
        seed_input = f"{inst.canonical_code}:{signal_type}:{entry_price:.4f}:{stop_loss:.4f}:{target_price:.4f}:{session_bars}"
        seed = int.from_bytes(hashlib.sha256(seed_input.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)

        steps = max(12, session_bars - 3)
        dt_frac = 1.0 / float(session_bars)
        mu_step = mean_daily * dt_frac
        sigma_step = sigma_daily * math.sqrt(dt_frac)

        mc_target_hits = 0
        mc_stop_hits = 0
        mc_r_multiples: list[float] = []
        risk_abs = max(1e-6, abs(entry_price - stop_loss))

        for _ in range(mc_paths):
            px = entry_price
            outcome_r: float | None = None
            for _step in range(steps):
                z = rng.gauss(0.0, 1.0)
                px *= math.exp((mu_step - 0.5 * sigma_step * sigma_step) + sigma_step * z)
                if signal_type == SignalType.SELL.value:
                    if px >= stop_loss:
                        mc_stop_hits += 1
                        outcome_r = -1.0
                        break
                    if px <= target_price:
                        mc_target_hits += 1
                        outcome_r = abs(entry_price - target_price) / risk_abs
                        break
                else:
                    if px <= stop_loss:
                        mc_stop_hits += 1
                        outcome_r = -1.0
                        break
                    if px >= target_price:
                        mc_target_hits += 1
                        outcome_r = abs(target_price - entry_price) / risk_abs
                        break
            if outcome_r is None:
                pnl = (entry_price - px) if signal_type == SignalType.SELL.value else (px - entry_price)
                outcome_r = pnl / risk_abs
            mc_r_multiples.append(outcome_r)

        mc_target_prob = round((mc_target_hits / max(1, mc_paths)) * 100.0, 2)
        mc_stop_prob = round((mc_stop_hits / max(1, mc_paths)) * 100.0, 2)
        mc_timeout_prob = round(max(0.0, 100.0 - mc_target_prob - mc_stop_prob), 2)
        expected_r = round(sum(mc_r_multiples) / max(1, len(mc_r_multiples)), 3)

        return SkillResult(
            skill_name=self.skill_name,
            status="SUCCEEDED",
            data={
                "market_code": inst.market_code.value,
                "session_5m_bars_used": session_bars,
                "historical_sample_days": sample_size,
                "historical_target_hit_rate_pct": hist_hit_rate,
                "historical_stop_hit_rate_pct": round((hist_stop_hits / max(1, sample_size)) * 100.0, 2),
                "mc_paths": mc_paths,
                "mc_target_hit_prob_pct": mc_target_prob,
                "mc_stop_hit_prob_pct": mc_stop_prob,
                "mc_session_timeout_prob_pct": mc_timeout_prob,
                "expected_r_multiple": expected_r,
                "annualized_vol_pct": round(sigma_daily * math.sqrt(252.0) * 100.0, 2),
                "methodology_note": (
                    "Seeded GBM Monte Carlo + trailing historical bar replay. "
                    "Simulation metrics are statistical diagnostics, never guarantees of future results."
                ),
            },
            metrics={"mc_paths": mc_paths, "session_5m_bars": session_bars},
        )
