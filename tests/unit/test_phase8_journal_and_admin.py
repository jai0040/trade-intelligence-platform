"""Phase 8 unit tests: Journal realized P&L calculations, emotion metrics, and static integrity."""

from __future__ import annotations

import ast
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "backend"), str(ROOT / "trading-engine")):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_all_phase8_files_compile_cleanly() -> None:
    targets: list[Path] = []
    for folder in ("backend/app/journal", "backend/app/admin"):
        for py_file in (ROOT / folder).rglob("*.py"):
            targets.append(py_file)
    assert len(targets) >= 6
    for py_file in targets:
        ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))


def test_realized_pnl_calculation_buy_and_sell() -> None:
    from app.journal.math import calculate_realized_pnl

    # 1. Open trade (no exit price) -> None
    assert calculate_realized_pnl("BUY", Decimal("100.00"), None, Decimal("10")) is None

    # 2. Profitable Long (BUY): entry 2940, exit 2970, qty 10 -> (2970 - 2940) * 10 = +300.00
    pnl_long_win = calculate_realized_pnl("BUY", Decimal("2940.00"), Decimal("2970.00"), Decimal("10"))
    assert pnl_long_win == Decimal("300.0000")

    # 3. Losing Long (BUY): entry 2940, exit 2910, qty 10 -> (2910 - 2940) * 10 = -300.00
    pnl_long_loss = calculate_realized_pnl("BUY", Decimal("2940.00"), Decimal("2910.00"), Decimal("10"))
    assert pnl_long_loss == Decimal("-300.0000")

    # 4. Profitable Short (SELL): entry 360.00, exit 350.00, qty 5 -> (360 - 350) * 5 = +50.00
    pnl_short_win = calculate_realized_pnl("SELL", Decimal("360.00"), Decimal("350.00"), Decimal("5"))
    assert pnl_short_win == Decimal("50.0000")

    # 5. Losing Short (SELL): entry 360.00, exit 370.00, qty 5 -> (360 - 370) * 5 = -50.00
    pnl_short_loss = calculate_realized_pnl("SELL", Decimal("360.00"), Decimal("370.00"), Decimal("5"))
    assert pnl_short_loss == Decimal("-50.0000")
