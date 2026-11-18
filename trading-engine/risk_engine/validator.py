"""Mandatory non-overridable deterministic Risk Engine validator.

No candidate signal may be published to subscribers or sent to the AI Analyst unless
`validate_signal_risk(...)` returns `status == "PASSED"`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from adapters.base import MarketAdapter
from domain.models import Instrument, SignalType


@dataclass(frozen=True)
class RiskCheckResult:
    status: str  # "PASSED" | "REJECTED"
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    risk_fingerprint: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "PASSED"


def validate_signal_risk(
    *,
    instrument: Instrument,
    market_adapter: MarketAdapter,
    signal_type: str,
    entry_price: Decimal,
    stop_loss: Decimal,
    target_price: Decimal,
    risk_reward_ratio: Decimal,
    quote_is_stale: bool,
    as_of_utc: datetime,
    trading_mode: str = "SIGNALS_ONLY",
    min_risk_reward: Decimal = Decimal("1.50"),
    max_stop_distance_pct: Decimal = Decimal("8.00"),
    enforce_entry_window: bool = False,
    recommended_shares: int | None = None,
) -> RiskCheckResult:
    """Run all hard deterministic risk checks and produce a SHA-256 risk fingerprint."""
    blocks: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}

    # 1. Hard operating policy check
    mode_ok = trading_mode.strip().upper() == "SIGNALS_ONLY"
    checks["signals_only_mode"] = mode_ok
    if not mode_ok:
        blocks.append("TRADING_MODE is not SIGNALS_ONLY.")

    # 2. Exchange symbol validity
    sym_ok = market_adapter.validate_symbol(instrument.symbol, instrument.exchange_code)
    checks["valid_symbol"] = sym_ok
    if not sym_ok:
        blocks.append(f"Symbol {instrument.symbol!r} failed {instrument.exchange_code.value} validation.")

    # 3. Quote freshness check
    fresh_ok = not quote_is_stale
    checks["fresh_market_data"] = fresh_ok
    if not fresh_ok:
        blocks.append("Underlying market data quote is stale; signal publication blocked.")

    # 4. Positive finite prices & directional stop/target geometry
    prices_pos = (
        entry_price > Decimal("0") and stop_loss > Decimal("0") and target_price > Decimal("0")
    )
    checks["positive_prices"] = prices_pos
    if not prices_pos:
        blocks.append("Entry, stop-loss, and target prices must all be strictly positive.")

    sig_upper = signal_type.strip().upper()
    geom_ok = False
    if prices_pos:
        if sig_upper == SignalType.SELL.value:
            geom_ok = target_price < entry_price < stop_loss
        else:
            geom_ok = stop_loss < entry_price < target_price
    checks["directional_geometry"] = geom_ok
    if not geom_ok:
        blocks.append(
            f"Invalid {sig_upper} price geometry (entry={entry_price}, stop={stop_loss}, target={target_price})."
        )

    # 5. Stop distance ceiling
    stop_dist_pct = (
        (abs(entry_price - stop_loss) / entry_price) * Decimal("100")
        if entry_price > Decimal("0")
        else Decimal("100")
    )
    stop_dist_ok = stop_dist_pct <= max_stop_distance_pct
    checks["stop_distance_limit"] = stop_dist_ok
    if not stop_dist_ok:
        blocks.append(
            f"Stop distance {stop_dist_pct:.2f}% exceeds maximum allowed {max_stop_distance_pct:.2f}%."
        )

    # 6. Minimum Risk-to-Reward ratio
    rr_ok = risk_reward_ratio >= min_risk_reward
    checks["min_risk_reward"] = rr_ok
    if not rr_ok:
        blocks.append(
            f"Risk-to-reward ratio {risk_reward_ratio} is below minimum {min_risk_reward}."
        )

    # 7. Optional intraday market entry window check
    if enforce_entry_window and sig_upper in {SignalType.BUY.value, SignalType.SELL.value}:
        win_ok, win_reason = market_adapter.is_within_entry_window(
            instrument.exchange_code, as_of_utc
        )
        checks["entry_window"] = win_ok
        if not win_ok:
            blocks.append(f"Outside market entry window: {win_reason}")
    else:
        checks["entry_window"] = True

    # 8. Optional position sizing sanity
    if recommended_shares is not None and recommended_shares <= 0:
        warnings.append("Reference model budget yields 0 shares at current entry/stop levels.")

    status = "PASSED" if not blocks else "REJECTED"

    fingerprint_payload = {
        "canonical_code": instrument.canonical_code,
        "signal_type": sig_upper,
        "entry_price": str(entry_price),
        "stop_loss": str(stop_loss),
        "target_price": str(target_price),
        "risk_reward_ratio": str(risk_reward_ratio),
        "status": status,
        "as_of_date": as_of_utc.date().isoformat(),
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return RiskCheckResult(
        status=status,
        blocking_reasons=blocks,
        warnings=warnings,
        checks=checks,
        risk_fingerprint=fingerprint,
    )
