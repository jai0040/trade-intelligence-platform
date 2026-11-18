"""Structured JSON logging with automatic sensitive-field scrubbing."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "private_key",
    "webhook_secret",
)


def scrub_sensitive_data(payload: Any) -> Any:
    """Recursively redact sensitive keys so credentials never reach structured logs."""
    if isinstance(payload, dict):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            lower_key = str(key).lower()
            if any(fragment in lower_key for fragment in SENSITIVE_KEY_FRAGMENTS):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = scrub_sensitive_data(value)
        return sanitized
    if isinstance(payload, list):
        return [scrub_sensitive_data(item) for item in payload]
    return payload


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra_context = getattr(record, "context", None)
        if isinstance(extra_context, dict):
            log_entry["context"] = scrub_sensitive_data(extra_context)
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)
