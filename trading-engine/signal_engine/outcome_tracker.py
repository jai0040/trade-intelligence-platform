"""Deterministic signal outcome calculation with transparent gross vs. net-of-cost methodology."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from adapters.base import MarketAdapter
from domain.models import SignalStatus, SignalType

METHODOLOGY_VERSION = "v1.0-net-bps"


def compute_signal_outcome(
    *,
    signal_id: str,
    signal_type: str,
    final_status: str,
    entry_price: Decimal,
    stop_loss: Decimal,
    assumed_exit_price: Decimal,
    market_adapter: MarketAdapter,
    triggered_at_utc: datetime | None,
    closed_at_utc: datetime,
) -> dict[str, Any]:
    """Compute gross return %, net return % (after market cost bps), and realized R-multiple."""
    sig_upper = signal_type.upper()
    risk_per_share = abs(entry_price - stop_loss)
    if entry_price <= Decimal("0") or risk_per_share <= Decimal("0"):
        raise ValueError("Invalid entry_price or stop_loss for outcome computation.")

    cost_bps = market_adapter.get_cost_model_bps()
    cost_pct = cost_bps / Decimal("100")  # e.g., 15 bps == 0.15%

    if final_status in {SignalStatus.EXPIRED.value, SignalStatus.CANCELLED.value}:
        gross_return_pct = Decimal("0.0000")
        net_return_pct = Decimal("0.0000")
        realized_r = Decimal("0.000")
    else:
        if sig_upper == SignalType.SELL.value:
            pnl_per_share = entry_price - assumed_exit_price
        else:
            pnl_per_share = assumed_exit_price - entry_price
        gross_return_pct = ((pnl_per_share / entry_price) * Decimal("100")).quantize(
            Decimal("0.0001")
        )
        net_return_pct = (gross_return_pct - cost_pct).quantize(Decimal("0.0001"))
        cost_per_share = entry_price * (cost_bps / Decimal("10000"))
        realized_r = ((pnl_per_share - cost_per_share) / risk_per_share).quantize(Decimal("0.001"))

    return {
        "signal_id": signal_id,
        "final_status": final_status,
        "triggered_at_utc": triggered_at_utc.isoformat() if triggered_at_utc else None,
        "closed_at_utc": closed_at_utc.isoformat(),
        "assumed_entry_price": str(entry_price),
        "assumed_exit_price": str(assumed_exit_price),
        "estimated_cost_bps": str(cost_bps),
        "gross_return_pct": str(gross_return_pct),
        "net_return_pct": str(net_return_pct),
        "realized_r_multiple": str(realized_r),
        "methodology_version": METHODOLOGY_VERSION,
    }


def summarize_performance(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate immutable signal outcomes into transparent historical performance analytics."""
    total = len(outcomes)
    target_hits = sum(1 for o in outcomes if o["final_status"] == SignalStatus.TARGET_HIT.value)
    stop_hits = sum(1 for o in outcomes if o["final_status"] == SignalStatus.STOP_LOSS_HIT.value)
    expired = sum(1 for o in outcomes if o["final_status"] == SignalStatus.EXPIRED.value)
    closed_trades = target_hits + stop_hits

    win_rate = round((target_hits / closed_trades) * 100.0, 2) if closed_trades > 0 else 0.0
    avg_net_return = (
        round(sum(float(o["net_return_pct"]) for o in outcomes) / total, 4) if total > 0 else 0.0
    )
    avg_r = (
        round(sum(float(o["realized_r_multiple"]) for o in outcomes) / closed_trades, 3)
        if closed_trades > 0
        else 0.0
    )

    return {
        "total_outcomes": total,
        "closed_trades": closed_trades,
        "target_hits": target_hits,
        "stop_loss_hits": stop_hits,
        "expired_untriggered": expired,
        "win_rate_pct": win_rate,
        "avg_net_return_pct": avg_net_return,
        "avg_realized_r_multiple": avg_r,
        "methodology_version": METHODOLOGY_VERSION,
        "methodology_disclosure": (
            "Outcomes are computed strictly on immutable published signals after deducting "
            "documented market cost models (15 bps India / 8 bps US). Past outcomes do not guarantee future results."
        ),
    }
