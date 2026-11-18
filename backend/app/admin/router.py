"""RBAC-protected Super Admin & Admin session control and audit log endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from decimal import Decimal
from fastapi import APIRouter, Body, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession, joinedload

from app.admin.schemas import (
    AdminOverviewResponse,
    AdminPlanCreateRequest,
    AdminPlanResponse,
    AdminRevokeSessionRequest,
    AdminRevokeSessionResponse,
    AdminUserListItemResponse,
    AdminUserListResponse,
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
from app.core.config import get_settings
from app.core.errors import APIError
from app.core.rate_limit import extract_client_ip
from app.realtime.ws_manager import WebSocketManager
from app.signals.schemas import (
    KillSwitchResponse,
    KillSwitchUpdateRequest,
    ManualWorkflowTriggerRequest,
)
from app.signals.service import SignalsEngineHub, read_kill_switch, update_kill_switch
from database.models.billing import Subscription, SubscriptionPlan
from database.models.identity import AuditLog, Session, User
from domain.models import MarketCode

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_ONLY = require_roles("super_admin", "admin")
SUPER_ADMIN_ONLY = require_roles("super_admin")


@router.get("/overview", response_model=AdminOverviewResponse)
def admin_get_overview(
    request: Request,
    _auth: AuthContext = Depends(ADMIN_ONLY),
    db: DbSession = Depends(get_db),
    redis_client: Any | None = Depends(get_redis),
) -> AdminOverviewResponse:
    """Platform KPIs: users, active/expired subs, MRR, active workers, kill-switch status."""
    settings = getattr(request.app.state, "settings", None) or get_settings()

    total_users = int(db.execute(select(func.count(User.id))).scalar_one())
    active_users = int(db.execute(select(func.count(User.id)).where(User.is_active.is_(True))).scalar_one())
    inactive_users = total_users - active_users

    active_sessions_count = int(
        db.execute(select(func.count(Session.id)).where(Session.status == "ACTIVE")).scalar_one()
    )

    # Subscriptions & MRR calculation
    all_subs = list(
        db.execute(
            select(Subscription).options(joinedload(Subscription.plan))
        ).scalars().all()
    )
    subs_by_status: dict[str, int] = {}
    mrr_inr = Decimal("0.00")
    mrr_usd = Decimal("0.00")

    for s in all_subs:
        st = (s.status or "none").lower()
        subs_by_status[st] = subs_by_status.get(st, 0) + 1
        if st in {"active", "trialing"} and s.plan:
            if s.plan.currency == "INR":
                mrr_inr += s.plan.price_amount
            else:
                mrr_usd += s.plan.price_amount

    kill_switch_active = read_kill_switch(db, redis_client)

    return AdminOverviewResponse(
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        subscriptions_by_status=subs_by_status,
        mrr_inr=mrr_inr.quantize(Decimal("0.01")),
        mrr_usd=mrr_usd.quantize(Decimal("0.01")),
        active_sessions_count=active_sessions_count,
        kill_switch={"enabled": kill_switch_active, "source": "redis_db"},
        trading_mode=settings.trading_mode,
    )


@router.get("/users", response_model=AdminUserListResponse)
def admin_list_users(
    search: str | None = Query(default=None),
    role: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _auth: AuthContext = Depends(ADMIN_ONLY),
    db: DbSession = Depends(get_db),
) -> AdminUserListResponse:
    """Paginated user & subscription directory (no password hashes or secrets)."""
    stmt = select(User).options(joinedload(User.role)).order_by(User.created_at.desc())

    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where((func.lower(User.email).like(needle)) | (func.lower(User.full_name).like(needle)))
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    all_matching = list(db.execute(stmt).scalars().all())
    if role:
        all_matching = [u for u in all_matching if u.role.code == role.lower()]

    total = len(all_matching)
    paged = all_matching[offset : offset + limit]

    user_ids = [u.id for u in paged]
    active_sessions = list(
        db.execute(
            select(Session).where(Session.user_id.in_(user_ids), Session.status == "ACTIVE")
        ).scalars().all()
    ) if user_ids else []
    sess_by_user = {s.user_id: s for s in active_sessions}

    subs = list(
        db.execute(
            select(Subscription).options(joinedload(Subscription.plan)).where(Subscription.user_id.in_(user_ids))
        ).scalars().all()
    ) if user_ids else []
    sub_by_user = {s.user_id: s for s in subs}

    items: list[AdminUserListItemResponse] = []
    for u in paged:
        sess = sess_by_user.get(u.id)
        sub = sub_by_user.get(u.id)
        sess_dict = (
            {
                "id": str(sess.id),
                "ip_address": str(sess.ip_address) if sess.ip_address else None,
                "user_agent": sess.user_agent,
                "created_at": sess.created_at.isoformat(),
                "last_seen_at": sess.last_seen_at.isoformat(),
            }
            if sess
            else None
        )
        sub_dict = (
            {
                "id": str(sub.id),
                "plan_code": sub.plan.code if sub.plan else "unknown",
                "plan_name": sub.plan.name if sub.plan else "Unknown",
                "status": sub.status,
                "currency": sub.plan.currency if sub.plan else "INR",
                "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            }
            if sub
            else None
        )

        items.append(
            AdminUserListItemResponse(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=u.role.code,
                country_code=u.country_code,
                is_active=u.is_active,
                is_email_verified=u.is_email_verified,
                created_at=u.created_at,
                last_login_at=u.last_login_at,
                active_session=sess_dict,
                subscription=sub_dict,
            )
        )

    return AdminUserListResponse(total=total, items=items)


@router.post(
    "/plans",
    response_model=AdminPlanResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def admin_create_plan(
    payload: AdminPlanCreateRequest,
    request: Request,
    auth: AuthContext = Depends(SUPER_ADMIN_ONLY),
    db: DbSession = Depends(get_db),
) -> AdminPlanResponse:
    """Create or configure subscription plan pricing (Super Admin only, audited)."""
    existing = db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.code == payload.code.strip().lower())
    ).scalar_one_or_none()
    if existing is not None:
        raise APIError(status_code=409, code="CONFLICT", message=f"Plan code '{payload.code}' already exists.")

    plan = SubscriptionPlan(
        code=payload.code.strip().lower(),
        name=payload.name.strip(),
        description=payload.description.strip(),
        currency=payload.currency,
        price_amount=payload.price_amount,
        billing_interval=payload.billing_interval,
        grace_period_days=payload.grace_period_days,
        entitled_markets=[m for m in payload.entitled_markets],
        features=dict(payload.features or {}),
        is_active=True,
    )
    db.add(plan)
    record_audit_event(
        db,
        actor_user_id=auth.user.id,
        action="ADMIN_PLAN_CREATED",
        resource_type="subscription_plan",
        resource_id=plan.code,
        metadata={"name": plan.name, "currency": plan.currency, "price": str(plan.price_amount)},
        ip_address=extract_client_ip(request),
    )
    db.commit()
    db.refresh(plan)

    return AdminPlanResponse(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        description=plan.description,
        currency=plan.currency,
        price_amount=plan.price_amount,
        billing_interval=plan.billing_interval,
        grace_period_days=plan.grace_period_days,
        entitled_markets=list(plan.entitled_markets),
        features=dict(plan.features),
        is_active=plan.is_active,
        created_at=plan.created_at,
    )


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


@router.post(
    "/kill-switch",
    response_model=KillSwitchResponse,
    dependencies=[Depends(require_csrf)],
)
def admin_toggle_kill_switch(
    payload: KillSwitchUpdateRequest,
    request: Request,
    auth: AuthContext = Depends(ADMIN_ONLY),
    db: DbSession = Depends(get_db),
    redis_client: Any | None = Depends(get_redis),
) -> KillSwitchResponse:
    """Toggle Global Emergency Kill Switch (halts automated analysis without deleting any data; audited)."""
    enabled = update_kill_switch(
        db,
        redis_client=redis_client,
        enabled=payload.enabled,
        actor_user_id=auth.user.id,
        reason=payload.reason,
        ip_address=extract_client_ip(request),
    )
    msg = (
        "Global Emergency Kill Switch ENABLED: automated scans and signal publishing halted; historical data preserved."
        if enabled
        else "Global Emergency Kill Switch DISABLED: automated market workflows resumed."
    )
    return KillSwitchResponse(enabled=enabled, reason=payload.reason, message=msg)


@router.get("/workflows")
def admin_list_workflows(
    request: Request,
    _auth: AuthContext = Depends(ADMIN_ONLY),
) -> dict[str, Any]:
    """Inspect recent workflow_runs and per-skill execution telemetry."""
    hub: SignalsEngineHub = request.app.state.signals_hub
    return {
        "total": len(hub.workflow_reports),
        "workflows": [
            {
                **r.summary(),
                "idempotency_key": r.idempotency_key,
                "triggered_by": r.triggered_by,
                "started_at_utc": r.started_at_utc,
                "finished_at_utc": r.finished_at_utc,
                "error_message": r.error_message,
                "skill_runs": [
                    {
                        "id": sr.id,
                        "skill_name": sr.skill_name,
                        "status": sr.status,
                        "retry_count": sr.retry_count,
                        "duration_ms": sr.duration_ms,
                        "error_trace": sr.error_trace,
                    }
                    for sr in r.skill_runs
                ],
            }
            for r in hub.workflow_reports[:25]
        ],
    }


@router.post(
    "/workflows/trigger",
    dependencies=[Depends(require_csrf)],
)
def admin_trigger_workflow(
    payload: ManualWorkflowTriggerRequest,
    request: Request,
    _auth: AuthContext = Depends(ADMIN_ONLY),
    db: DbSession = Depends(get_db),
    redis_client: Any | None = Depends(get_redis),
) -> dict[str, Any]:
    """Manually trigger an India or US market DAG workflow (honors Kill Switch)."""
    hub: SignalsEngineHub = request.app.state.signals_hub
    mkt = MarketCode(payload.market_code)
    provider = request.app.state.market_providers[mkt]
    kill_active = read_kill_switch(db, redis_client)
    report = hub.run_market_workflow(
        market_code=mkt,
        provider=provider,
        mode=payload.mode,
        triggered_by="admin_manual",
        kill_switch_active=kill_active,
        force_duplicate=True,
    )
    return report.summary()
