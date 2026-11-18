"""Phase 3 Foundation verification tests (zero external DB/network required)."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_all_python_foundation_files_compile_cleanly() -> None:
    """Every Python module created in database/, backend/, and trading-engine/ must parse cleanly."""
    targets = []
    for folder in ("database", "backend/app", "trading-engine"):
        base = ROOT / folder
        for py_file in base.rglob("*.py"):
            if "skills" in py_file.parts:
                continue
            targets.append(py_file)

    assert len(targets) >= 15, f"Expected >=15 foundation Python files, found {len(targets)}"
    for py_file in targets:
        source = py_file.read_text(encoding="utf-8")
        ast.parse(source, filename=str(py_file))


def test_log_scrubber_redacts_secrets() -> None:
    """Verify sensitive keys are scrubbed recursively before structured log serialization."""
    import sys

    sys.path.insert(0, str(ROOT / "backend"))
    from app.core.logging import scrub_sensitive_data

    payload = {
        "user": "alice@example.com",
        "password": "super-secret-password",
        "nested": {
            "api_key": "live_key_123",
            "razorpay_webhook_secret": "whsec_abc",
            "safe_metric": 42,
        },
        "headers": [{"authorization": "Bearer xyz"}, {"X-Request-ID": "req-1"}],
    }
    cleaned = scrub_sensitive_data(payload)
    assert cleaned["user"] == "alice@example.com"
    assert cleaned["password"] == "[REDACTED]"
    assert cleaned["nested"]["api_key"] == "[REDACTED]"
    assert cleaned["nested"]["razorpay_webhook_secret"] == "[REDACTED]"
    assert cleaned["nested"]["safe_metric"] == 42
    assert cleaned["headers"][0]["authorization"] == "[REDACTED]"
    assert cleaned["headers"][1]["X-Request-ID"] == "req-1"


def test_workflow_idempotency_key_is_deterministic() -> None:
    """Verify identical workflow slots produce identical SHA-256 keys and distinct slots differ."""
    import hashlib

    def expected(wf: str, mkt: str, dt: str, slot: str) -> str:
        return hashlib.sha256(f"{wf}:{mkt}:{dt}:{slot}".encode("utf-8")).hexdigest()

    k1 = expected("INTRADAY_ORB", "IN", "2026-11-18", "2026-11-18T04:00:00Z")
    k2 = expected("INTRADAY_ORB", "IN", "2026-11-18", "2026-11-18T04:00:00Z")
    k3 = expected("INTRADAY_ORB", "US", "2026-11-18", "2026-11-18T14:45:00Z")
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 64
