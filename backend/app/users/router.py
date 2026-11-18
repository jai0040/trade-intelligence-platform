"""Strictly user_id-isolated profile, preferences, and watchlist endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.authentication.dependencies import (
    AuthContext,
    get_current_auth,
    get_db,
    require_csrf,
)
from app.authentication.schemas import UserProfileResponse
from app.core.audit import record_audit_event
from app.core.errors import APIError
from app.core.rate_limit import extract_client_ip
from app.users.schemas import (
    ProfileUpdateRequest,
    UserPreferencesResponse,
    UserPreferencesUpdateRequest,
    WatchlistCreateRequest,
    WatchlistItemCreateRequest,
    WatchlistItemResponse,
    WatchlistResponse,
    WatchlistUpdateRequest,
)
from database.models.markets import Instrument
from database.models.workspace import UserPreference, Watchlist, WatchlistItem

router = APIRouter(tags=["user-workspace"])


def _serialize_watchlist(
    wl: Watchlist, items: list[WatchlistItem] | None = None
) -> WatchlistResponse:
    return WatchlistResponse(
        id=wl.id,
        name=wl.name,
        market_scope=wl.market_scope,
        is_default=wl.is_default,
        created_at=wl.created_at,
        updated_at=wl.updated_at,
        items=[
            WatchlistItemResponse(
                id=item.id,
                watchlist_id=item.watchlist_id,
                instrument_id=item.instrument_id,
                notes=item.notes,
                created_at=item.created_at,
            )
            for item in (items or [])
        ],
    )


def _get_owned_watchlist_or_404(
    db: DbSession, *, user_id: uuid.UUID, watchlist_id: uuid.UUID
) -> Watchlist:
    """Fetch a watchlist strictly scoped to the authenticated user_id (never leaks other tenants)."""
    wl = db.execute(
        select(Watchlist).where(Watchlist.id == watchlist_id, Watchlist.user_id == user_id)
    ).scalar_one_or_none()
    if wl is None:
        raise APIError(status_code=404, code="NOT_FOUND", message="Watchlist not found.")
    return wl


@router.get("/users/me/profile", response_model=UserProfileResponse)
def get_my_profile(auth: AuthContext = Depends(get_current_auth)) -> UserProfileResponse:
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


@router.patch(
    "/users/me/profile",
    response_model=UserProfileResponse,
    dependencies=[Depends(require_csrf)],
)
def update_my_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> UserProfileResponse:
    """Update only safe editable profile fields for the authenticated user."""
    user = auth.user
    changed_fields: list[str] = []
    if payload.full_name is not None:
        user.full_name = payload.full_name
        changed_fields.append("full_name")
    if payload.country_code is not None:
        user.country_code = payload.country_code
        changed_fields.append("country_code")

    if changed_fields:
        record_audit_event(
            db,
            actor_user_id=user.id,
            action="USER_PROFILE_UPDATED",
            resource_type="user",
            resource_id=user.id,
            metadata={"fields": changed_fields},
            ip_address=extract_client_ip(request),
        )
        db.commit()
        db.refresh(user)

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=auth.role_code,
        country_code=user.country_code,
        is_active=user.is_active,
        is_email_verified=user.is_email_verified,
        subscription_status=auth.subscription_status,
        entitled_markets=auth.entitled_markets,
        last_login_at=user.last_login_at,
    )


@router.get("/users/me/preferences", response_model=UserPreferencesResponse)
def get_my_preferences(
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> UserPreferencesResponse:
    pref = db.execute(
        select(UserPreference).where(UserPreference.user_id == auth.user.id)
    ).scalar_one_or_none()
    if pref is None:
        pref = UserPreference(user_id=auth.user.id)
        db.add(pref)
        db.commit()
        db.refresh(pref)

    return UserPreferencesResponse(
        default_market=pref.default_market,
        theme=pref.theme,
        display_timezone=pref.display_timezone,
        default_budget_inr=pref.default_budget_inr,
        default_max_loss_inr=pref.default_max_loss_inr,
        default_budget_usd=pref.default_budget_usd,
        default_max_loss_usd=pref.default_max_loss_usd,
        updated_at=pref.updated_at,
    )


@router.patch(
    "/users/me/preferences",
    response_model=UserPreferencesResponse,
    dependencies=[Depends(require_csrf)],
)
def update_my_preferences(
    payload: UserPreferencesUpdateRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> UserPreferencesResponse:
    pref = db.execute(
        select(UserPreference).where(UserPreference.user_id == auth.user.id)
    ).scalar_one_or_none()
    if pref is None:
        pref = UserPreference(user_id=auth.user.id)
        db.add(pref)

    updates = payload.model_dump(exclude_unset=True)
    for field_name, field_value in updates.items():
        if field_value is not None:
            setattr(pref, field_name, field_value)

    db.commit()
    db.refresh(pref)
    return UserPreferencesResponse(
        default_market=pref.default_market,
        theme=pref.theme,
        display_timezone=pref.display_timezone,
        default_budget_inr=pref.default_budget_inr,
        default_max_loss_inr=pref.default_max_loss_inr,
        default_budget_usd=pref.default_budget_usd,
        default_max_loss_usd=pref.default_max_loss_usd,
        updated_at=pref.updated_at,
    )


@router.get("/watchlists", response_model=list[WatchlistResponse])
def list_my_watchlists(
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> list[WatchlistResponse]:
    watchlists = list(
        db.execute(
            select(Watchlist)
            .where(Watchlist.user_id == auth.user.id)
            .order_by(Watchlist.is_default.desc(), Watchlist.created_at.asc())
        )
        .scalars()
        .all()
    )
    items = list(
        db.execute(
            select(WatchlistItem)
            .where(WatchlistItem.user_id == auth.user.id)
            .order_by(WatchlistItem.created_at.asc())
        )
        .scalars()
        .all()
    )
    items_by_wl: dict[uuid.UUID, list[WatchlistItem]] = {}
    for item in items:
        items_by_wl.setdefault(item.watchlist_id, []).append(item)

    return [_serialize_watchlist(wl, items_by_wl.get(wl.id, [])) for wl in watchlists]


@router.post(
    "/watchlists",
    response_model=WatchlistResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_watchlist(
    payload: WatchlistCreateRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> WatchlistResponse:
    wl = Watchlist(
        user_id=auth.user.id,
        name=payload.name,
        market_scope=payload.market_scope,
        is_default=False,
    )
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return _serialize_watchlist(wl, [])


@router.get("/watchlists/{watchlist_id}", response_model=WatchlistResponse)
def get_watchlist(
    watchlist_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> WatchlistResponse:
    wl = _get_owned_watchlist_or_404(db, user_id=auth.user.id, watchlist_id=watchlist_id)
    items = list(
        db.execute(
            select(WatchlistItem)
            .where(
                WatchlistItem.watchlist_id == wl.id,
                WatchlistItem.user_id == auth.user.id,
            )
            .order_by(WatchlistItem.created_at.asc())
        )
        .scalars()
        .all()
    )
    return _serialize_watchlist(wl, items)


@router.patch(
    "/watchlists/{watchlist_id}",
    response_model=WatchlistResponse,
    dependencies=[Depends(require_csrf)],
)
def update_watchlist(
    watchlist_id: uuid.UUID,
    payload: WatchlistUpdateRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> WatchlistResponse:
    wl = _get_owned_watchlist_or_404(db, user_id=auth.user.id, watchlist_id=watchlist_id)
    if payload.name is not None:
        wl.name = payload.name
    if payload.market_scope is not None:
        wl.market_scope = payload.market_scope
    db.commit()
    db.refresh(wl)

    items = list(
        db.execute(
            select(WatchlistItem).where(
                WatchlistItem.watchlist_id == wl.id,
                WatchlistItem.user_id == auth.user.id,
            )
        )
        .scalars()
        .all()
    )
    return _serialize_watchlist(wl, items)


@router.delete(
    "/watchlists/{watchlist_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
def delete_watchlist(
    watchlist_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> Response:
    wl = _get_owned_watchlist_or_404(db, user_id=auth.user.id, watchlist_id=watchlist_id)
    db.delete(wl)
    db.commit()
    return Response(status_code=204)


@router.post(
    "/watchlists/{watchlist_id}/items",
    response_model=WatchlistItemResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def add_watchlist_item(
    watchlist_id: uuid.UUID,
    payload: WatchlistItemCreateRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> WatchlistItemResponse:
    wl = _get_owned_watchlist_or_404(db, user_id=auth.user.id, watchlist_id=watchlist_id)
    instrument = db.execute(
        select(Instrument).where(Instrument.id == payload.instrument_id)
    ).scalar_one_or_none()
    if instrument is None:
        raise APIError(status_code=404, code="NOT_FOUND", message="Instrument not found.")

    item = WatchlistItem(
        watchlist_id=wl.id,
        user_id=auth.user.id,
        instrument_id=instrument.id,
        notes=payload.notes,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(
            status_code=409,
            code="CONFLICT",
            message="Instrument is already in this watchlist.",
        ) from None

    db.refresh(item)
    return WatchlistItemResponse(
        id=item.id,
        watchlist_id=item.watchlist_id,
        instrument_id=item.instrument_id,
        notes=item.notes,
        created_at=item.created_at,
    )


@router.delete(
    "/watchlists/{watchlist_id}/items/{item_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
def remove_watchlist_item(
    watchlist_id: uuid.UUID,
    item_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> Response:
    _get_owned_watchlist_or_404(db, user_id=auth.user.id, watchlist_id=watchlist_id)
    item = db.execute(
        select(WatchlistItem).where(
            WatchlistItem.id == item_id,
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.user_id == auth.user.id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise APIError(status_code=404, code="NOT_FOUND", message="Watchlist item not found.")
    db.delete(item)
    db.commit()
    return Response(status_code=204)
