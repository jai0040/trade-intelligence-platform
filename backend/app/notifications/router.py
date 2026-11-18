"""Strictly user_id-isolated Notifications & Notification Preferences REST API router."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session as DbSession

from app.authentication.dependencies import (
    AuthContext,
    get_current_auth,
    get_db,
    require_csrf,
)
from app.core.errors import APIError
from app.notifications.schemas import (
    NotificationListResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdateRequest,
    NotificationResponse,
)
from database.models.workspace import Notification, NotificationPreference

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _serialize_notification(row: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=row.id,
        category=row.category,
        title=row.title,
        body=row.body,
        payload=dict(row.payload or {}),
        is_read=row.is_read,
        read_at_utc=row.read_at_utc,
        created_at_utc=row.created_at_utc,
    )


def _serialize_pref(pref: NotificationPreference) -> NotificationPreferencesResponse:
    return NotificationPreferencesResponse(
        in_app_enabled=pref.in_app_enabled,
        browser_push_enabled=pref.browser_push_enabled,
        email_enabled=pref.email_enabled,
        notify_new_signals=pref.notify_new_signals,
        notify_entry_hit=pref.notify_entry_hit,
        notify_target_hit=pref.notify_target_hit,
        notify_stop_hit=pref.notify_stop_hit,
        notify_signal_expiry=pref.notify_signal_expiry,
        notify_market_news=pref.notify_market_news,
        notify_market_reports=pref.notify_market_reports,
        market_filter=pref.market_filter,
        quiet_hours_json=dict(pref.quiet_hours_json or {}),
        updated_at=pref.updated_at,
    )


@router.get("", response_model=NotificationListResponse)
def list_my_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> NotificationListResponse:
    """List current authenticated user's notifications with unread badge count."""
    base_filter = [Notification.user_id == auth.user.id]
    unread_count = int(
        db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == auth.user.id,
                Notification.is_read.is_(False),
            )
        ).scalar_one()
    )
    if unread_only:
        base_filter.append(Notification.is_read.is_(False))

    total = int(
        db.execute(select(func.count(Notification.id)).where(*base_filter)).scalar_one()
    )
    rows = list(
        db.execute(
            select(Notification)
            .where(*base_filter)
            .order_by(Notification.created_at_utc.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return NotificationListResponse(
        unread_count=unread_count,
        total=total,
        items=[_serialize_notification(r) for r in rows],
    )


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    dependencies=[Depends(require_csrf)],
)
def mark_notification_read(
    notification_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> NotificationResponse:
    """Mark a single notification owned by the current user as read."""
    row = db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == auth.user.id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise APIError(status_code=404, code="NOT_FOUND", message="Notification not found.")

    if not row.is_read:
        row.is_read = True
        row.read_at_utc = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
    return _serialize_notification(row)


@router.post("/read-all", dependencies=[Depends(require_csrf)])
def mark_all_notifications_read(
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> dict[str, int]:
    """Mark all unread notifications for the current user as read."""
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == auth.user.id, Notification.is_read.is_(False))
        .values(is_read=True, read_at_utc=now)
    )
    db.commit()
    return {"marked_read": int(result.rowcount or 0)}


@router.get("/preferences", response_model=NotificationPreferencesResponse)
def get_notification_preferences(
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """Return current user's notification channel and event preferences."""
    pref = db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == auth.user.id)
    ).scalar_one_or_none()
    if pref is None:
        pref = NotificationPreference(user_id=auth.user.id)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return _serialize_pref(pref)


@router.patch(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    dependencies=[Depends(require_csrf)],
)
def update_notification_preferences(
    payload: NotificationPreferencesUpdateRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """Update current user's notification preferences."""
    pref = db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == auth.user.id)
    ).scalar_one_or_none()
    if pref is None:
        pref = NotificationPreference(user_id=auth.user.id)
        db.add(pref)

    for key, val in payload.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(pref, key, val)

    db.commit()
    db.refresh(pref)
    return _serialize_pref(pref)
