"""Live Market Scanner CLI runner for Trade Intelligence Platform.

Fetches live market data from Yahoo spark API and updates trader/watchlist.json,
which is instantly served to the web dashboard (Stock Scanner & Opportunities views).

Usage:
    python scripts/run_scanner.py daily
    python scripts/run_scanner.py daily --symbols NVDA,GOOG,TSLA,RELIANCE.NS,TCS.NS
    python scripts/run_scanner.py orb
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_PY = ROOT / "trading-engine" / "skills" / "trader-scanner" / "scan.py"


def main() -> int:
    args = sys.argv[1:] if len(sys.argv) > 1 else ["daily"]
    cmd = [sys.executable, str(SCAN_PY)] + args
    print(f"Running Live Market Scanner: {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
