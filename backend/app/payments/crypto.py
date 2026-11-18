"""Cryptographic signature verification, invoice numbering, and period calculations for payments."""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta, timezone


def verify_razorpay_webhook_signature(
    raw_body: bytes,
    signature: str | None,
    secret: str,
) -> bool:
    """Verify Razorpay webhook signature using constant-time HMAC-SHA256 comparison.

    Razorpay delivers the signature in the 'X-Razorpay-Signature' header as a hex-encoded SHA256 HMAC
    of the raw request body.
    """
    if not signature or not secret:
        return False

    computed = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed.strip().lower(), signature.strip().lower())


def verify_stripe_webhook_signature(
    raw_body: bytes,
    signature_header: str | None,
    secret: str,
    *,
    tolerance_seconds: int = 300,
    current_timestamp: int | None = None,
) -> bool:
    """Verify Stripe webhook signature header ('Stripe-Signature') with timestamp freshness.

    Stripe-Signature header format:
        t=1614000000,v1=5257a869e7ecebeda32affa62cdca3fa51cad7e77a0e56ff536d0ce8e108d8bd
    Scheme:
        Signed payload is f"{timestamp}.{raw_body.decode('utf-8')}".
    """
    if not signature_header or not secret:
        return False

    elements = {}
    for part in signature_header.split(","):
        kv = part.strip().split("=", 1)
        if len(kv) == 2:
            elements[kv[0].strip()] = kv[1].strip()

    timestamp_str = elements.get("t")
    v1_sig = elements.get("v1")

    if not timestamp_str or not v1_sig:
        return False

    try:
        ts = int(timestamp_str)
    except ValueError:
        return False

    now_ts = current_timestamp if current_timestamp is not None else int(time.time())
    if abs(now_ts - ts) > tolerance_seconds:
        return False

    signed_payload = f"{timestamp_str}.".encode("utf-8") + raw_body
    computed = hmac.new(
        key=secret.encode("utf-8"),
        msg=signed_payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed.strip().lower(), v1_sig.strip().lower())


def generate_invoice_number(prefix: str = "INV") -> str:
    """Generate a clean unique human-readable invoice identifier."""
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:6].upper()
    return f"{prefix}-{date_part}-{random_part}"


def calculate_period_end_and_grace(
    start_time: datetime,
    billing_interval: str,
    grace_days: int = 3,
) -> tuple[datetime, datetime]:
    """Calculate the subscription period end datetime and grace expiration datetime.

    Intervals:
    - 'annual': +365 days
    - 'monthly' (or other): +30 days
    """
    start_utc = start_time if start_time.tzinfo is not None else start_time.replace(tzinfo=timezone.utc)
    interval = (billing_interval or "monthly").lower().strip()

    if interval == "annual":
        period_end = start_utc + timedelta(days=365)
    else:
        period_end = start_utc + timedelta(days=30)

    grace_until = period_end + timedelta(days=max(0, grace_days))
    return period_end, grace_until
