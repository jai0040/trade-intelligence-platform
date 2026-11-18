"""FastAPI authentication, CSRF double-submit, DB/Redis injection, and RBAC dependencies."""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Request
from sqlalchemy.orm import Session as DbSession

from app.authentication.service import validate_session_token
from app.core.config import Settings, get_settings
from app.core.errors import APIError
from app.core.security import constant_time_equals
from app.realtime.ws_manager import WebSocketManager
from app.subscriptions.service import get_user_entitlement
from database.models.identity import Session, User


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: Session
    role_code: str
    subscription_status: str
    entitled_markets: list[str]
    is_entitled: bool


def get_app_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", None) or get_settings()


def get_db(request: Request) -> Generator[DbSession, None, None]:
    session_factory = request.app.state.db_session_factory
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def get_redis(request: Request) -> Any | None:
    return getattr(request.app.state, "redis_client", None)


def get_ws_manager(request: Request) -> WebSocketManager | None:
    return getattr(request.app.state, "ws_manager", None)


def require_csrf(
    request: Request,
    settings: Settings = Depends(get_app_settings),
) -> None:
    """Enforce double-submit CSRF verification on state-changing cookie-authenticated requests."""
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get("X-CSRF-Token")
    if not constant_time_equals(cookie_token, header_token):
        raise APIError(
            status_code=403,
            code="CSRF_INVALID",
            message="Missing or invalid CSRF token.",
        )


def get_current_auth(
    request: Request,
    db: DbSession = Depends(get_db),
    redis_client: Any | None = Depends(get_redis),
    settings: Settings = Depends(get_app_settings),
) -> AuthContext:
    """Authenticate request strictly via HttpOnly session cookie (never query string)."""
    raw_token = request.cookies.get(settings.session_cookie_name)
    user, session, role_code = validate_session_token(
        db,
        redis_client=redis_client,
        raw_token=raw_token,
    )
    entitlement = get_user_entitlement(db, user_id=user.id, role_code=role_code)
    return AuthContext(
        user=user,
        session=session,
        role_code=role_code,
        subscription_status=entitlement.subscription_status,
        entitled_markets=entitlement.entitled_markets,
        is_entitled=entitlement.is_entitled,
    )


def require_roles(*allowed_roles: str) -> Callable[[AuthContext], AuthContext]:
    """RBAC dependency guard enforcing role membership."""
    allowed = frozenset(allowed_roles)

    def _guard(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
        if auth.role_code not in allowed:
            raise APIError(
                status_code=403,
                code="FORBIDDEN",
                message="You do not have permission to perform this action.",
                details={"required_roles": sorted(allowed)},
            )
        return auth

    return _guard
