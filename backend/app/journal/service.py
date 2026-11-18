"""User-isolated Trading Journal domain service and realized P&L calculations."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.core.errors import APIError
from app.journal.math import calculate_realized_pnl
from app.journal.schemas import (
    JournalEntryCreateRequest,
    JournalEntryResponse,
    JournalEntryUpdateRequest,
    JournalStatsResponse,
)
from database.models.markets import Instrument, Market
from database.models.workspace import UserTradingJournal


def serialize_journal_entry(row: UserTradingJournal) -> JournalEntryResponse:
    return JournalEntryResponse(
        id=row.id,
        user_id=row.user_id,
        instrument_id=row.instrument_id,
        market_id=row.market_id,
        signal_id=row.signal_id,
        side=row.side,
        entry_price=row.entry_price,
        exit_price=row.exit_price,
        quantity=row.quantity,
        planned_stop=row.planned_stop,
        planned_target=row.planned_target,
        realized_pnl=row.realized_pnl,
        currency=row.currency,
        emotions_tags=list(row.emotions_tags or []),
        notes=row.notes,
        entered_at_utc=row.entered_at_utc,
        exited_at_utc=row.exited_at_utc,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def compute_journal_stats(entries: list[UserTradingJournal]) -> JournalStatsResponse:
    total_trades = len(entries)
    open_trades = sum(1 for e in entries if e.exit_price is None)
    closed_trades = sum(1 for e in entries if e.exit_price is not None)

    winning = 0
    losing = 0
    total_inr = Decimal("0.00")
    total_usd = Decimal("0.00")
    gross_gains = Decimal("0.00")
    gross_losses = Decimal("0.00")
    emotion_counter: Counter[str] = Counter()

    for e in entries:
        for tag in e.emotions_tags or []:
            emotion_counter[str(tag).upper()] += 1

        if e.realized_pnl is not None:
            if e.realized_pnl > Decimal("0"):
                winning += 1
                gross_gains += e.realized_pnl
            elif e.realized_pnl < Decimal("0"):
                losing += 1
                gross_losses += abs(e.realized_pnl)

            if e.currency == "INR":
                total_inr += e.realized_pnl
            else:
                total_usd += e.realized_pnl

    win_rate = (
        (Decimal(winning) / Decimal(closed_trades) * Decimal("100")).quantize(Decimal("0.01"))
        if closed_trades > 0
        else Decimal("0.00")
    )
    profit_factor = (
        (gross_gains / gross_losses).quantize(Decimal("0.01"))
        if gross_losses > Decimal("0")
        else None
    )

    return JournalStatsResponse(
        total_trades=total_trades,
        open_trades=open_trades,
        closed_trades=closed_trades,
        winning_trades=winning,
        losing_trades=losing,
        win_rate_pct=win_rate,
        total_realized_pnl_inr=total_inr.quantize(Decimal("0.01")),
        total_realized_pnl_usd=total_usd.quantize(Decimal("0.01")),
        profit_factor=profit_factor,
        top_emotions=dict(emotion_counter.most_common(5)),
    )


def create_entry(
    db: DbSession,
    *,
    user_id: uuid.UUID,
    payload: JournalEntryCreateRequest,
) -> UserTradingJournal:
    # Verify instrument and market exist
    inst = db.execute(
        select(Instrument).where(Instrument.id == payload.instrument_id)
    ).scalar_one_or_none()
    if inst is None:
        raise APIError(status_code=404, code="NOT_FOUND", message="Instrument not found.")

    mkt = db.execute(select(Market).where(Market.id == payload.market_id)).scalar_one_or_none()
    if mkt is None:
        raise APIError(status_code=404, code="NOT_FOUND", message="Market not found.")

    pnl = calculate_realized_pnl(
        payload.side, payload.entry_price, payload.exit_price, payload.quantity
    )
    now = datetime.now(timezone.utc)
    entry_time = payload.entered_at_utc or now

    entry = UserTradingJournal(
        user_id=user_id,
        instrument_id=payload.instrument_id,
        market_id=payload.market_id,
        signal_id=payload.signal_id,
        side=payload.side,
        entry_price=payload.entry_price,
        exit_price=payload.exit_price,
        quantity=payload.quantity,
        planned_stop=payload.planned_stop,
        planned_target=payload.planned_target,
        realized_pnl=pnl,
        currency=payload.currency,
        emotions_tags=[t.strip().upper() for t in payload.emotions_tags if t.strip()],
        notes=payload.notes,
        entered_at_utc=entry_time,
        exited_at_utc=payload.exited_at_utc,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_entry_or_404(
    db: DbSession,
    *,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> UserTradingJournal:
    """Strictly user_id-scoped retrieval; returns 404 for other tenants."""
    entry = db.execute(
        select(UserTradingJournal).where(
            UserTradingJournal.id == entry_id,
            UserTradingJournal.user_id == user_id,
        )
    ).scalar_one_or_none()
    if entry is None:
        raise APIError(status_code=404, code="NOT_FOUND", message="Journal entry not found.")
    return entry


def update_entry(
    db: DbSession,
    *,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    payload: JournalEntryUpdateRequest,
) -> UserTradingJournal:
    entry = get_entry_or_404(db, user_id=user_id, entry_id=entry_id)

    if payload.exit_price is not None:
        entry.exit_price = payload.exit_price
        entry.realized_pnl = calculate_realized_pnl(
            entry.side, entry.entry_price, entry.exit_price, entry.quantity
        )
        if entry.exited_at_utc is None and payload.exited_at_utc is None:
            entry.exited_at_utc = datetime.now(timezone.utc)
    if payload.planned_stop is not None:
        entry.planned_stop = payload.planned_stop
    if payload.planned_target is not None:
        entry.planned_target = payload.planned_target
    if payload.emotions_tags is not None:
        entry.emotions_tags = [t.strip().upper() for t in payload.emotions_tags if t.strip()]
    if payload.notes is not None:
        entry.notes = payload.notes
    if payload.exited_at_utc is not None:
        entry.exited_at_utc = payload.exited_at_utc

    db.commit()
    db.refresh(entry)
    return entry


def delete_entry(
    db: DbSession,
    *,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> None:
    entry = get_entry_or_404(db, user_id=user_id, entry_id=entry_id)
    db.delete(entry)
    db.commit()


def list_entries(
    db: DbSession,
    *,
    user_id: uuid.UUID,
    side: str | None = None,
    currency: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[UserTradingJournal], JournalStatsResponse, int]:
    stmt = (
        select(UserTradingJournal)
        .where(UserTradingJournal.user_id == user_id)
        .order_by(UserTradingJournal.entered_at_utc.desc())
    )
    if side:
        stmt = stmt.where(UserTradingJournal.side == side.upper())
    if currency:
        stmt = stmt.where(UserTradingJournal.currency == currency.upper())

    all_user_entries = list(
        db.execute(
            select(UserTradingJournal).where(UserTradingJournal.user_id == user_id)
        )
        .scalars()
        .all()
    )
    stats = compute_journal_stats(all_user_entries)

    paged_entries = list(db.execute(stmt.limit(limit).offset(offset)).scalars().all())
    total = len(all_user_entries) if not side and not currency else len(paged_entries)

    return paged_entries, stats, total
