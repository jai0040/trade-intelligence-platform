"""Append-only security, authentication, and Super Admin audit logging helpers."""

from __future__ import annotations

import ipaddress
import uuid
from typing import Any

from sqlalchemy.orm import Session as DbSession

from app.core.logging import scrub_sensitive_data
from database.models.identity import AuditLog


def normalize_inet_ip(ip_address: str | None) -> str | None:
    """Return canonical IPv4/IPv6 string suitable for PostgreSQL INET, or None if invalid."""
    if not ip_address:
        return None
    try:
        return str(ipaddress.ip_address(ip_address.strip()))
    except ValueError:
        return None


def record_audit_event(
    db: DbSession,
    *,
    action: str,
    resource_type: str,
    actor_user_id: uuid.UUID | None = None,
    resource_id: str | uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Stage an immutable audit_logs entry with automatic sensitive-field scrubbing."""
    clean_meta = scrub_sensitive_data(metadata or {})
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        metadata_json=clean_meta if isinstance(clean_meta, dict) else {},
        ip_address=normalize_inet_ip(ip_address),
    )
    db.add(entry)
    return entry
