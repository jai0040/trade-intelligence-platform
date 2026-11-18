"""User-isolated Trading Journal REST router."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session as DbSession

from app.authentication.dependencies import (
    AuthContext,
    get_current_auth,
    get_db,
    require_csrf,
)
from app.journal.schemas import (
    JournalEntryCreateRequest,
    JournalEntryResponse,
    JournalEntryUpdateRequest,
    JournalListResponse,
)
from app.journal.service import (
    create_entry,
    delete_entry,
    get_entry_or_404,
    list_entries,
    serialize_journal_entry,
    update_entry,
)

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("", response_model=JournalListResponse)
def get_user_journal(
    side: str | None = Query(default=None),
    currency: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> JournalListResponse:
    """List current user's journal entries and overall trading performance statistics."""
    entries, stats, total = list_entries(
        db,
        user_id=auth.user.id,
        side=side,
        currency=currency,
        limit=limit,
        offset=offset,
    )
    return JournalListResponse(
        total=total,
        stats=stats,
        items=[serialize_journal_entry(e) for e in entries],
    )


@router.post(
    "",
    response_model=JournalEntryResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_journal_entry(
    payload: JournalEntryCreateRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> JournalEntryResponse:
    """Create a personal trading journal entry."""
    entry = create_entry(db, user_id=auth.user.id, payload=payload)
    return serialize_journal_entry(entry)


@router.get("/{journal_id}", response_model=JournalEntryResponse)
def get_single_journal_entry(
    journal_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> JournalEntryResponse:
    """Fetch a single journal entry strictly scoped to the authenticated user."""
    entry = get_entry_or_404(db, user_id=auth.user.id, entry_id=journal_id)
    return serialize_journal_entry(entry)


@router.patch(
    "/{journal_id}",
    response_model=JournalEntryResponse,
    dependencies=[Depends(require_csrf)],
)
def update_single_journal_entry(
    journal_id: uuid.UUID,
    payload: JournalEntryUpdateRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> JournalEntryResponse:
    """Update a journal entry (e.g. record exit price, tags, or notes)."""
    entry = update_entry(db, user_id=auth.user.id, entry_id=journal_id, payload=payload)
    return serialize_journal_entry(entry)


@router.delete(
    "/{journal_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
def delete_single_journal_entry(
    journal_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: DbSession = Depends(get_db),
) -> Response:
    """Delete a journal entry owned by the authenticated user."""
    delete_entry(db, user_id=auth.user.id, entry_id=journal_id)
    return Response(status_code=204)
