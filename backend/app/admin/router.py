"""RBAC-protected Super Admin & Admin session control and audit log endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.admin.schemas import (
    AdminRevokeSessionRequest,
    AdminRevokeSessionResponse,
    AdminUserStatusResponse,
    AdminUserStatusUpdateRequest,
    AuditLogResponse,
)
from app.authentication.dependencies import (
    AuthContext,
    get_db,
    get_redis,
    get_ws_manager,
    require_csrf,
    require_roles,
)
from app.authentication.service import revoke_user_sessions
from app.core.audit import record_audit_event
from app.core.errors import APIError
from app.core.rate_limit import extract_client_ip
from app.realtime.ws_manager import WebSocketManager
from database.models.identity import AuditLog, User

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_ONLY = require_roles("super_admin", "admin")


@router.post(
    "/users/{user_id}/revoke-session",
    response_model=AdminRevokeSessionResponse,
    dependencies=[Depends(require_csrf)],
)
def admin_revoke_user_session(
    user_id: uuid.UUID,
    request: Request,
    payload: AdminRevokeSessionRequest | None = Body(default=None),
    auth: AuthContext = Depends(ADMIN_ONLY),
    db: DbSession = Depends(get_db),
    redis_client: Any | None = Depends(get_redis),
    ws_manager: WebSocketManager | None = Depends(get_ws_manager),
) -> AdminRevokeSessionResponse:
    """Immediately revoke a user's active session via DB + Redis + WebSocket (audited)."""
    reason = payload.reason if payload else "Session revoked by administrator"
    count = revoke_user_sessions(
        db,
        redis_client=redis_client,
        ws_manager=ws_manager,
        target_user_id=user_id,
        actor_user_id=auth.user.id,
        action="ADMIN_SESSION_REVOKED",
        code="SESSION_REVOKED",
        reason=reason,
        revoked_by="admin",
        ip_address=extract_client_ip(request),
    )
    return AdminRevokeSessionResponse(
        user_id=user_id,
        revoked_sessions_count=count,
        message="User active sessions revoked.",
    )


@router.patch(
    "/users/{user_id}/status",
    response_model=AdminUserStatusResponse,
    dependencies=[Depends(require_csrf)],
)
def admin_update_user_status(
    user_id: uuid.UUID,
    payload: AdminUserStatusUpdateRequest,
    request: Request,
    auth: AuthContext = Depends(ADMIN_ONLY),
    db: DbSession = Depends(get_db),
    redis_client: Any | None = Depends(get_redis),
    ws_manager: WebSocketManager | None = Depends(get_ws_manager),
) -> AdminUserStatusResponse:
    """Activate or deactivate a user account; deactivation immediately revokes active sessions."""
    if user_id == auth.user.id and not payload.is_active:
        raise APIError(
            status_code=400,
            code="SELF_DEACTIVATION_FORBIDDEN",
            message="Administrators cannot deactivate their own account.",
        )

    target = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if target is None:
        raise APIError(status_code=404, code="NOT_FOUND", message="User not found.")

    target.is_active = payload.is_active
    record_audit_event(
        db,
        actor_user_id=auth.user.id,
        action="ADMIN_USER_ACTIVATED" if payload.is_active else "ADMIN_USER_DEACTIVATED",
        resource_type="user",
        resource_id=target.id,
        metadata={"is_active": payload.is_active, "reason": payload.reason},
        ip_address=extract_client_ip(request),
    )
    db.commit()

    revoked_count = 0
    if not payload.is_active:
        revoked_count = revoke_user_sessions(
            db,
            redis_client=redis_client,
            ws_manager=ws_manager,
            target_user_id=target.id,
            actor_user_id=auth.user.id,
            action="ADMIN_DEACTIVATION_SESSION_REVOKED",
            code="SESSION_REVOKED",
            reason="Your account has been deactivated by an administrator.",
            revoked_by="admin",
            ip_address=extract_client_ip(request),
        )

    return AdminUserStatusResponse(
        user_id=target.id,
        is_active=target.is_active,
        revoked_sessions_count=revoked_count,
    )


@router.get("/audit-logs", response_model=list[AuditLogResponse])
def admin_list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None),
    _auth: AuthContext = Depends(ADMIN_ONLY),
    db: DbSession = Depends(get_db),
) -> list[AuditLogResponse]:
    """Query immutable admin and security audit log entries."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    rows = list(db.execute(stmt).scalars().all())
    return [
        AuditLogResponse(
            id=row.id,
            actor_user_id=row.actor_user_id,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            metadata=dict(row.metadata_json or {}),
            ip_address=str(row.ip_address) if row.ip_address is not None else None,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/providers/status")
def admin_provider_status(
    request: Request,
    _auth: AuthContext = Depends(ADMIN_ONLY),
) -> dict[str, Any]:
    """Inspect market data provider health, licensing status, latency, and daily API calls."""
    providers = getattr(request.app.state, "market_providers", {})
    monitor = getattr(request.app.state, "provider_health_monitor", None)
    return {
        "configured_providers": {
            mkt.value: prov.health_check() for mkt, prov in providers.items()
        },
        "telemetry": monitor.snapshot() if monitor is not None else [],
    }
