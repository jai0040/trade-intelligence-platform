"""Authentication REST API router matching docs/api/openapi.yaml."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session as DbSession

from app.authentication.dependencies import (
    AuthContext,
    get_app_settings,
    get_current_auth,
    get_db,
    get_redis,
    get_ws_manager,
    require_csrf,
)
from app.authentication.schemas import (
    LoginRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    UserProfileResponse,
)
from app.authentication.service import (
    authenticate_and_create_session,
    confirm_password_reset,
    logout_session,
    register_user,
    request_password_reset,
)
from app.core.config import Settings
from app.core.rate_limit import enforce_rate_limit, extract_client_ip
from app.realtime.ws_manager import WebSocketManager
from app.subscriptions.service import get_user_entitlement

router = APIRouter(prefix="/auth", tags=["authentication"])


def _set_auth_cookies(
    response: Response,
    *,
    settings: Settings,
    raw_session_token: str,
    csrf_token: str,
) -> None:
    max_age = settings.session_ttl_hours * 3600
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def _clear_auth_cookies(response: Response, *, settings: Settings) -> None:
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    response.delete_cookie(key=settings.csrf_cookie_name, path="/")


@router.post("/register", response_model=UserProfileResponse, status_code=201)
def register_endpoint(
    payload: RegisterRequest,
    request: Request,
    db: DbSession = Depends(get_db),
    redis_client: Any | None = Depends(get_redis),
    settings: Settings = Depends(get_app_settings),
) -> UserProfileResponse:
    """Register a new subscriber account."""
    client_ip = extract_client_ip(request)
    enforce_rate_limit(
        redis_client,
        scope="auth_register",
        identifier=client_ip,
        limit=settings.rate_limit_register_max,
        window_seconds=settings.rate_limit_register_window_seconds,
    )
    user = register_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        country_code=payload.country_code,
        ip_address=client_ip,
    )
    entitlement = get_user_entitlement(db, user_id=user.id, role_code="subscriber")
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role="subscriber",
        country_code=user.country_code,
        is_active=user.is_active,
        is_email_verified=user.is_email_verified,
        subscription_status=entitlement.subscription_status,
        entitled_markets=entitlement.entitled_markets,
        last_login_at=user.last_login_at,
    )


@router.post("/login", response_model=UserProfileResponse)
def login_endpoint(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
    redis_client: Any | None = Depends(get_redis),
    ws_manager: WebSocketManager | None = Depends(get_ws_manager),
    settings: Settings = Depends(get_app_settings),
) -> UserProfileResponse:
    """Authenticate user, enforce Single Active Session, and issue HttpOnly + CSRF cookies."""
    client_ip = extract_client_ip(request)
    enforce_rate_limit(
        redis_client,
        scope="auth_login",
        identifier=f"{client_ip}:{payload.email}",
        limit=settings.rate_limit_login_max,
        window_seconds=settings.rate_limit_login_window_seconds,
    )

    result = authenticate_and_create_session(
        db,
        redis_client=redis_client,
        ws_manager=ws_manager,
        settings=settings,
        email=payload.email,
        password=payload.password,
        ip_address=client_ip,
        user_agent=request.headers.get("User-Agent"),
    )
    _set_auth_cookies(
        response,
        settings=settings,
        raw_session_token=result.raw_session_token,
        csrf_token=result.csrf_token,
    )
    entitlement = get_user_entitlement(
        db, user_id=result.user.id, role_code=result.role_code
    )
    return UserProfileResponse(
        id=result.user.id,
        email=result.user.email,
        full_name=result.user.full_name,
        role=result.role_code,
        country_code=result.user.country_code,
        is_active=result.user.is_active,
        is_email_verified=result.user.is_email_verified,
        subscription_status=entitlement.subscription_status,
        entitled_markets=entitlement.entitled_markets,
        last_login_at=result.user.last_login_at,
    )


@router.post("/logout", status_code=204, response_class=Response, dependencies=[Depends(require_csrf)])
def logout_endpoint(
    request: Request,
    response: Response,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
    redis_client: Any | None = Depends(get_redis),
    settings: Settings = Depends(get_app_settings),
) -> None:
    """Revoke current server-side session and clear auth cookies."""
    logout_session(
        db,
        redis_client=redis_client,
        session=auth.session,
        ip_address=extract_client_ip(request),
    )
    _clear_auth_cookies(response, settings=settings)


@router.get("/me", response_model=UserProfileResponse)
def me_endpoint(auth: AuthContext = Depends(get_current_auth)) -> UserProfileResponse:
    """Return authenticated user profile and entitlement state."""
    return UserProfileResponse(
        id=auth.user.id,
        email=auth.user.email,
        full_name=auth.user.full_name,
        role=auth.role_code,
        country_code=auth.user.country_code,
        is_active=auth.user.is_active,
        is_email_verified=auth.user.is_email_verified,
        subscription_status=auth.subscription_status,
        entitled_markets=auth.entitled_markets,
        last_login_at=auth.user.last_login_at,
    )


@router.post("/password-reset/request", response_model=MessageResponse, status_code=202)
def password_reset_request_endpoint(
    payload: PasswordResetRequest,
    request: Request,
    db: DbSession = Depends(get_db),
    redis_client: Any | None = Depends(get_redis),
    settings: Settings = Depends(get_app_settings),
) -> MessageResponse:
    """Request a time-limited password reset token with constant response to prevent enumeration."""
    client_ip = extract_client_ip(request)
    enforce_rate_limit(
        redis_client,
        scope="auth_password_reset",
        identifier=client_ip,
        limit=settings.rate_limit_reset_max,
        window_seconds=settings.rate_limit_reset_window_seconds,
    )
    raw_token, user = request_password_reset(
        db,
        settings=settings,
        email=payload.email,
        ip_address=client_ip,
    )
    notifier = getattr(request.app.state, "password_reset_notifier", None)
    if raw_token is not None and user is not None and callable(notifier):
        notifier(user.email, raw_token)

    return MessageResponse(
        message="If an account matches that email, a password reset link has been sent."
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
def password_reset_confirm_endpoint(
    payload: PasswordResetConfirmRequest,
    request: Request,
    db: DbSession = Depends(get_db),
    redis_client: Any | None = Depends(get_redis),
    ws_manager: WebSocketManager | None = Depends(get_ws_manager),
    settings: Settings = Depends(get_app_settings),
) -> MessageResponse:
    """Confirm one-time password reset token and revoke all existing sessions."""
    client_ip = extract_client_ip(request)
    enforce_rate_limit(
        redis_client,
        scope="auth_password_reset_confirm",
        identifier=client_ip,
        limit=settings.rate_limit_reset_max,
        window_seconds=settings.rate_limit_reset_window_seconds,
    )
    confirm_password_reset(
        db,
        redis_client=redis_client,
        ws_manager=ws_manager,
        raw_token=payload.token,
        new_password=payload.new_password,
        ip_address=client_ip,
    )
    return MessageResponse(
        message="Password updated successfully. All active sessions have been signed out."
    )
