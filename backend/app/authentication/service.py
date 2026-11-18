"""Authentication, Argon2id credentials, Password Reset, and Single Active Session service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession, joinedload

from app.core.audit import normalize_inet_ip, record_audit_event
from app.core.config import Settings
from app.core.errors import APIError
from app.core.redis import (
    clear_active_session_cache,
    get_active_session_cache,
    publish_session_invalidated,
    set_active_session_cache,
)
from app.core.security import (
    dummy_password_verify,
    generate_opaque_token,
    hash_password,
    hash_token,
    normalize_email,
    password_needs_rehash,
    verify_password,
)
from app.realtime.ws_manager import WebSocketManager
from database.models.identity import PasswordResetToken, Role, Session, User
from database.models.workspace import NotificationPreference, UserPreference, Watchlist


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _country_code_2(country_code: str) -> str:
    cleaned = country_code.strip().upper()
    return cleaned[:2] if len(cleaned) >= 2 else "IN"


@dataclass(frozen=True)
class LoginResult:
    user: User
    role_code: str
    session: Session
    raw_session_token: str
    csrf_token: str
    evicted_session_ids: list[str]


def register_user(
    db: DbSession,
    *,
    email: str,
    password: str,
    full_name: str,
    country_code: str = "IN",
    ip_address: str | None = None,
) -> User:
    """Register a new subscriber with Argon2id password and isolated default workspace."""
    canonical_email = normalize_email(email)

    existing = db.execute(
        select(User).where(func.lower(User.email) == canonical_email)
    ).scalar_one_or_none()
    if existing is not None:
        raise APIError(
            status_code=409,
            code="CONFLICT",
            message="An account with this email address is already registered.",
        )

    subscriber_role = db.execute(
        select(Role).where(Role.code == "subscriber")
    ).scalar_one_or_none()
    if subscriber_role is None:
        raise APIError(
            status_code=500,
            code="ROLE_NOT_SEEDED",
            message="Platform roles are not initialized. Run database seed_initial first.",
        )

    cc = _country_code_2(country_code)
    default_tz = "Asia/Kolkata" if cc == "IN" else "America/New_York"

    user = User(
        role_id=subscriber_role.id,
        email=canonical_email,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        country_code=cc,
        is_active=True,
        is_email_verified=False,
        session_version=1,
    )
    db.add(user)
    db.flush()

    db.add(
        UserPreference(
            user_id=user.id,
            default_market="ALL",
            theme="dark",
            display_timezone=default_tz,
        )
    )
    db.add(NotificationPreference(user_id=user.id))
    db.add(
        Watchlist(
            user_id=user.id,
            name="My Watchlist",
            market_scope="ALL",
            is_default=True,
        )
    )

    record_audit_event(
        db,
        actor_user_id=user.id,
        action="USER_REGISTERED",
        resource_type="user",
        resource_id=user.id,
        metadata={"country_code": cc},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    return user


def authenticate_and_create_session(
    db: DbSession,
    *,
    redis_client: Any | None,
    ws_manager: WebSocketManager | None,
    settings: Settings,
    email: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> LoginResult:
    """Verify credentials and atomically enforce Single Active Session per user.

    Any previously ACTIVE session for this user is marked SUPERSEDED inside the
    same DB transaction before creating the new ACTIVE session, followed by
    updating Redis and pushing a real-time `session.invalidated` WebSocket event.
    """
    canonical_email = normalize_email(email)

    stmt = (
        select(User)
        .options(joinedload(User.role))
        .where(func.lower(User.email) == canonical_email)
    )
    bind = db.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""
    if dialect_name == "postgresql":
        stmt = stmt.with_for_update()

    user = db.execute(stmt).scalar_one_or_none()
    if user is None:
        dummy_password_verify(password)
        raise APIError(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Invalid email or password.",
        )

    if not verify_password(user.password_hash, password):
        record_audit_event(
            db,
            actor_user_id=user.id,
            action="LOGIN_FAILED",
            resource_type="user",
            resource_id=user.id,
            metadata={"reason": "invalid_password"},
            ip_address=ip_address,
        )
        db.commit()
        raise APIError(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Invalid email or password.",
        )

    if not user.is_active:
        record_audit_event(
            db,
            actor_user_id=user.id,
            action="LOGIN_BLOCKED_INACTIVE",
            resource_type="user",
            resource_id=user.id,
            ip_address=ip_address,
        )
        db.commit()
        raise APIError(
            status_code=403,
            code="ACCOUNT_INACTIVE",
            message="Your account has been deactivated. Contact support or an administrator.",
        )

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    now = _utc_now()
    ttl_seconds = settings.session_ttl_hours * 3600
    expires_at = now + timedelta(seconds=ttl_seconds)

    # Atomic single-session eviction: increment session_version & supersede any prior ACTIVE session
    user.session_version += 1
    user.last_login_at = now

    prior_active_sessions = list(
        db.execute(
            select(Session).where(Session.user_id == user.id, Session.status == "ACTIVE")
        )
        .scalars()
        .all()
    )
    evicted_session_ids: list[str] = []
    for prior in prior_active_sessions:
        prior.status = "SUPERSEDED"
        prior.revoked_at = now
        evicted_session_ids.append(str(prior.id))

    # Flush eviction before inserting the new ACTIVE row to satisfy uq_sessions_one_active_per_user
    db.flush()

    raw_session_token = generate_opaque_token(32)
    token_digest = hash_token(raw_session_token)
    csrf_token = generate_opaque_token(32)

    new_session = Session(
        user_id=user.id,
        token_hash=token_digest,
        session_version=user.session_version,
        status="ACTIVE",
        ip_address=normalize_inet_ip(ip_address),
        user_agent=(user_agent or "")[:512] or None,
        last_seen_at=now,
        expires_at=expires_at,
    )
    db.add(new_session)
    db.flush()

    if evicted_session_ids:
        record_audit_event(
            db,
            actor_user_id=user.id,
            action="SESSION_SUPERSEDED",
            resource_type="session",
            resource_id=new_session.id,
            metadata={
                "evicted_session_ids": evicted_session_ids,
                "new_session_version": user.session_version,
            },
            ip_address=ip_address,
        )

    record_audit_event(
        db,
        actor_user_id=user.id,
        action="USER_LOGIN",
        resource_type="session",
        resource_id=new_session.id,
        metadata={"session_version": user.session_version},
        ip_address=ip_address,
    )
    db.commit()

    # Mirror active session in Redis and notify any evicted device via Pub/Sub + WS Hub
    set_active_session_cache(
        redis_client,
        user_id=user.id,
        session_id=new_session.id,
        token_hash=token_digest,
        session_version=user.session_version,
        ttl_seconds=ttl_seconds,
    )

    if evicted_session_ids:
        envelope = publish_session_invalidated(
            redis_client,
            user_id=user.id,
            code="SESSION_SUPERSEDED",
            reason="Your account was signed in from another device or browser.",
            revoked_by="new_login",
            revoked_session_ids=evicted_session_ids,
        )
        if ws_manager is not None:
            ws_manager.notify_session_invalidated(
                user_id=user.id,
                revoked_session_ids=evicted_session_ids,
                envelope=envelope,
            )

    return LoginResult(
        user=user,
        role_code=user.role.code,
        session=new_session,
        raw_session_token=raw_session_token,
        csrf_token=csrf_token,
        evicted_session_ids=evicted_session_ids,
    )


def validate_session_token(
    db: DbSession,
    *,
    redis_client: Any | None,
    raw_token: str | None,
) -> tuple[User, Session, str]:
    """Validate opaque session token against DB & Redis with explicit eviction diagnostics."""
    if not raw_token:
        raise APIError(
            status_code=401,
            code="UNAUTHORIZED",
            message="Authentication is required.",
        )

    token_digest = hash_token(raw_token)
    session = db.execute(
        select(Session)
        .options(joinedload(Session.user).joinedload(User.role))
        .where(Session.token_hash == token_digest)
    ).scalar_one_or_none()

    if session is None or session.user is None:
        raise APIError(
            status_code=401,
            code="UNAUTHORIZED",
            message="Invalid or unknown session.",
        )

    user = session.user
    now = _utc_now()

    if session.status == "SUPERSEDED" or session.session_version < user.session_version:
        raise APIError(
            status_code=401,
            code="SESSION_SUPERSEDED",
            message="Your account was signed in from another device or browser.",
        )

    if session.status == "REVOKED":
        raise APIError(
            status_code=401,
            code="SESSION_REVOKED",
            message="This session has been revoked. Please sign in again.",
        )

    if session.status != "ACTIVE" or _as_utc(session.expires_at) <= now:
        if session.status == "ACTIVE":
            session.status = "EXPIRED"
            db.commit()
        raise APIError(
            status_code=401,
            code="SESSION_EXPIRED",
            message="Your session has expired. Please sign in again.",
        )

    if not user.is_active:
        raise APIError(
            status_code=403,
            code="ACCOUNT_INACTIVE",
            message="Your account is inactive.",
        )

    # Cross-check Redis mirror when populated (detects cross-node eviction immediately)
    cached = get_active_session_cache(redis_client, user.id)
    if cached is not None:
        if (
            cached.get("session_id") != str(session.id)
            or cached.get("token_hash") != token_digest
            or int(cached.get("session_version", -1)) != session.session_version
        ):
            raise APIError(
                status_code=401,
                code="SESSION_SUPERSEDED",
                message="Your account was signed in from another device or browser.",
            )

    # Throttle last_seen_at writes to avoid unnecessary DB churn on rapid API calls
    if (now - _as_utc(session.last_seen_at)).total_seconds() >= 60:
        session.last_seen_at = now
        db.commit()

    return user, session, user.role.code


def logout_session(
    db: DbSession,
    *,
    redis_client: Any | None,
    session: Session,
    ip_address: str | None = None,
) -> None:
    """Revoke the user's current active session and remove its Redis pointer."""
    now = _utc_now()
    session.status = "REVOKED"
    session.revoked_at = now
    session.revoked_by_user_id = session.user_id

    record_audit_event(
        db,
        actor_user_id=session.user_id,
        action="USER_LOGOUT",
        resource_type="session",
        resource_id=session.id,
        ip_address=ip_address,
    )
    db.commit()
    clear_active_session_cache(redis_client, session.user_id)


def revoke_user_sessions(
    db: DbSession,
    *,
    redis_client: Any | None,
    ws_manager: WebSocketManager | None,
    target_user_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    action: str,
    code: str = "SESSION_REVOKED",
    reason: str = "Your session was revoked.",
    revoked_by: str = "admin",
    ip_address: str | None = None,
) -> int:
    """Revoke all active sessions for a user, bump session_version, and push WS eviction."""
    user = db.execute(select(User).where(User.id == target_user_id)).scalar_one_or_none()
    if user is None:
        raise APIError(status_code=404, code="NOT_FOUND", message="User not found.")

    now = _utc_now()
    user.session_version += 1

    active_sessions = list(
        db.execute(
            select(Session).where(Session.user_id == target_user_id, Session.status == "ACTIVE")
        )
        .scalars()
        .all()
    )
    revoked_ids: list[str] = []
    for sess in active_sessions:
        sess.status = "REVOKED"
        sess.revoked_at = now
        sess.revoked_by_user_id = actor_user_id
        revoked_ids.append(str(sess.id))

    record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action=action,
        resource_type="user",
        resource_id=target_user_id,
        metadata={"revoked_session_ids": revoked_ids, "reason": reason},
        ip_address=ip_address,
    )
    db.commit()

    clear_active_session_cache(redis_client, target_user_id)
    envelope = publish_session_invalidated(
        redis_client,
        user_id=target_user_id,
        code=code,
        reason=reason,
        revoked_by=revoked_by,
        revoked_session_ids=revoked_ids,
    )
    if ws_manager is not None:
        ws_manager.notify_session_invalidated(
            user_id=target_user_id,
            revoked_session_ids=revoked_ids or None,
            envelope=envelope,
        )
    return len(revoked_ids)


def request_password_reset(
    db: DbSession,
    *,
    settings: Settings,
    email: str,
    ip_address: str | None = None,
) -> tuple[str | None, User | None]:
    """Create a one-time hashed password reset token if the email exists and is active.

    Returns (raw_token, user) for internal email delivery only. The HTTP endpoint
    must NEVER return the raw token or indicate whether the email exists.
    """
    canonical_email = normalize_email(email)
    user = db.execute(
        select(User).where(func.lower(User.email) == canonical_email)
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        return None, None

    now = _utc_now()
    # Expire any prior unused reset tokens for this user
    prior_tokens = list(
        db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
        )
        .scalars()
        .all()
    )
    for old_tok in prior_tokens:
        old_tok.used_at = now

    raw_token = generate_opaque_token(32)
    reset_record = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=now + timedelta(minutes=settings.password_reset_ttl_minutes),
    )
    db.add(reset_record)
    record_audit_event(
        db,
        actor_user_id=user.id,
        action="PASSWORD_RESET_REQUESTED",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
    )
    db.commit()
    return raw_token, user


def confirm_password_reset(
    db: DbSession,
    *,
    redis_client: Any | None,
    ws_manager: WebSocketManager | None,
    raw_token: str,
    new_password: str,
    ip_address: str | None = None,
) -> None:
    """Validate one-time reset token, update Argon2id password, and revoke all sessions."""
    token_digest = hash_token(raw_token)
    reset_row = db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_digest)
    ).scalar_one_or_none()

    now = _utc_now()
    if (
        reset_row is None
        or reset_row.used_at is not None
        or _as_utc(reset_row.expires_at) <= now
    ):
        raise APIError(
            status_code=400,
            code="INVALID_RESET_TOKEN",
            message="Password reset token is invalid or has expired.",
        )

    user = db.execute(select(User).where(User.id == reset_row.user_id)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise APIError(
            status_code=400,
            code="INVALID_RESET_TOKEN",
            message="Password reset token is invalid or has expired.",
        )

    user.password_hash = hash_password(new_password)
    reset_row.used_at = now
    db.flush()

    revoke_user_sessions(
        db,
        redis_client=redis_client,
        ws_manager=ws_manager,
        target_user_id=user.id,
        actor_user_id=user.id,
        action="PASSWORD_RESET_COMPLETED",
        code="SESSION_REVOKED",
        reason="Your password was reset. Please sign in with your new password.",
        revoked_by="password_reset",
        ip_address=ip_address,
    )
