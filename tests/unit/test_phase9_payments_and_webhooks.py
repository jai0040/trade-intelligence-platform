"""Phase 9 unit tests: Cryptographic webhook verification, invoice generator, and period calculations."""

from __future__ import annotations

import ast
import hashlib
import hmac
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "backend"), str(ROOT / "trading-engine")):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_all_phase9_files_compile_cleanly() -> None:
    targets: list[Path] = []
    for py_file in (ROOT / "backend/app/payments").rglob("*.py"):
        targets.append(py_file)
    assert len(targets) >= 4
    for py_file in targets:
        ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))


def test_razorpay_hmac_signature_verification() -> None:
    from app.payments.crypto import verify_razorpay_webhook_signature

    secret = "rzp_secret_test_key_12345"
    payload = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_test_001","amount":199900}}}}'

    valid_signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    # 1. Valid signature -> True
    assert verify_razorpay_webhook_signature(payload, valid_signature, secret) is True

    # 2. Tampered payload -> False
    tampered_payload = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_test_001","amount":999900}}}}'
    assert verify_razorpay_webhook_signature(tampered_payload, valid_signature, secret) is False

    # 3. Wrong secret -> False
    assert verify_razorpay_webhook_signature(payload, valid_signature, "wrong_secret") is False

    # 4. Missing or None signature -> False
    assert verify_razorpay_webhook_signature(payload, None, secret) is False
    assert verify_razorpay_webhook_signature(payload, "", secret) is False


def test_stripe_signature_verification_and_replay_protection() -> None:
    from app.payments.crypto import verify_stripe_webhook_signature

    secret = "whsec_test_stripe_secret_67890"
    payload = b'{"id":"evt_test_001","type":"checkout.session.completed"}'
    now_ts = int(time.time())

    # Build valid Stripe-Signature header: t={ts},v1={sig}
    signed_content = f"{now_ts}.".encode("utf-8") + payload
    valid_sig = hmac.new(secret.encode("utf-8"), signed_content, hashlib.sha256).hexdigest()
    header = f"t={now_ts},v1={valid_sig}"

    # 1. Valid signature within tolerance -> True
    assert verify_stripe_webhook_signature(payload, header, secret, tolerance_seconds=300, current_timestamp=now_ts) is True

    # 2. Replay attack: timestamp older than tolerance -> False
    assert verify_stripe_webhook_signature(payload, header, secret, tolerance_seconds=300, current_timestamp=now_ts + 500) is False

    # 3. Tampered payload -> False
    tampered_payload = b'{"id":"evt_test_001","type":"customer.subscription.deleted"}'
    assert verify_stripe_webhook_signature(tampered_payload, header, secret, tolerance_seconds=300, current_timestamp=now_ts) is False

    # 4. Forged v1 signature -> False
    forged_header = f"t={now_ts},v1=deadbeefcafebabe0123456789abcdef"
    assert verify_stripe_webhook_signature(payload, forged_header, secret, tolerance_seconds=300, current_timestamp=now_ts) is False

    # 5. Malformed header -> False
    assert verify_stripe_webhook_signature(payload, "invalid_header", secret) is False
    assert verify_stripe_webhook_signature(payload, None, secret) is False


def test_invoice_number_generation() -> None:
    from app.payments.crypto import generate_invoice_number

    inv1 = generate_invoice_number("INV-RZP")
    inv2 = generate_invoice_number("INV-STRIPE")

    assert inv1.startswith("INV-RZP-")
    assert inv2.startswith("INV-STRIPE-")
    assert inv1 != inv2
    # Check date part format
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    assert today_str in inv1
    assert today_str in inv2


def test_period_end_and_grace_calculation() -> None:
    from app.payments.crypto import calculate_period_end_and_grace

    start = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Monthly interval (30 days + 3 days grace)
    end_monthly, grace_monthly = calculate_period_end_and_grace(start, "monthly", grace_days=3)
    assert (end_monthly - start).days == 30
    assert (grace_monthly - end_monthly).days == 3

    # Annual interval (365 days + 7 days grace)
    end_annual, grace_annual = calculate_period_end_and_grace(start, "annual", grace_days=7)
    assert (end_annual - start).days == 365
    assert (grace_annual - end_annual).days == 7
