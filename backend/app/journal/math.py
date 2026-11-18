"""Pure Decimal math for realized P&L calculations (zero external dependencies)."""

from __future__ import annotations

from decimal import Decimal


def calculate_realized_pnl(
    side: str,
    entry_price: Decimal,
    exit_price: Decimal | None,
    quantity: Decimal,
) -> Decimal | None:
    """Compute realized P&L based on trade side, entry price, exit price, and quantity."""
    if exit_price is None:
        return None
    side_clean = side.strip().upper()
    if side_clean == "BUY":
        return ((exit_price - entry_price) * quantity).quantize(Decimal("0.0001"))
    elif side_clean == "SELL":
        return ((entry_price - exit_price) * quantity).quantize(Decimal("0.0001"))
    return None
