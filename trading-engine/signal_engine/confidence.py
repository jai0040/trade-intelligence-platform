"""Calibrated Composite Setup Quality Score (0-100) — explicitly NOT a win probability."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

CONFIDENCE_LABEL = "Composite Setup Quality Score (not a win probability)"


def compute_composite_confidence(
    *,
    entry_state: str,
    volume_ratio: Decimal,
    risk_reward_ratio: Decimal,
    timemachine_data: dict[str, Any] | None,
    catalyst_risk: str = "LOW",
    overnight_earnings_gap_risk: bool = False,
) -> tuple[Decimal, dict[str, Any]]:
    """Compute a transparent, bounded [0, 100] setup quality score with full component breakdown."""
    # 1. Entry confirmation (max 25 pts)
    entry_pts = 24.0 if entry_state == "TRIGGERED" else 14.0

    # 2. Volume confirmation (max 20 pts)
    vol_f = float(volume_ratio)
    vol_pts = min(20.0, max(4.0, round(vol_f * 10.0, 2)))

    # 3. Risk/Reward geometry (max 20 pts)
    rr_f = float(risk_reward_ratio)
    rr_pts = min(20.0, max(5.0, round((rr_f / 2.5) * 20.0, 2)))

    # 4. Time Machine statistical edge (max 20 pts)
    tm_pts = 10.0
    if timemachine_data:
        exp_r = float(timemachine_data.get("expected_r_multiple", 0.0))
        mc_hit = float(timemachine_data.get("mc_target_hit_prob_pct", 30.0))
        tm_pts = min(20.0, max(2.0, round(8.0 + (exp_r * 6.0) + (mc_hit / 12.0), 2)))

    # 5. Catalyst & filing clarity (max 15 pts)
    cat_pts = {"LOW": 14.0, "MEDIUM": 9.0, "HIGH": 4.0}.get(catalyst_risk.upper(), 10.0)
    if overnight_earnings_gap_risk:
        cat_pts = max(2.0, cat_pts - 6.0)

    total = min(100.0, max(0.0, round(entry_pts + vol_pts + rr_pts + tm_pts + cat_pts, 2)))
    score_dec = Decimal(str(total)).quantize(Decimal("0.01"))

    breakdown = {
        "label": CONFIDENCE_LABEL,
        "components": {
            "entry_confirmation": {"score": entry_pts, "max": 25},
            "volume_confirmation": {"score": vol_pts, "max": 20},
            "risk_reward_geometry": {"score": rr_pts, "max": 20},
            "timemachine_diagnostics": {"score": tm_pts, "max": 20},
            "catalyst_clarity": {"score": cat_pts, "max": 15},
        },
        "total_score": float(score_dec),
    }
    return score_dec, breakdown
