"""Initial schema: 31 normalized tables, single-active-session index, and immutable signal trigger.

Revision ID: 20261118_0001
Revises: None
Create Date: 2026-11-18 21:40:00+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from database.models import Base

revision: str = "20261118_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

IMMUTABLE_SIGNAL_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION enforce_trading_signal_immutability()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.entry_price IS DISTINCT FROM OLD.entry_price
       OR NEW.stop_loss IS DISTINCT FROM OLD.stop_loss
       OR NEW.target_price IS DISTINCT FROM OLD.target_price
       OR NEW.risk_reward_ratio IS DISTINCT FROM OLD.risk_reward_ratio
       OR NEW.signal_type IS DISTINCT FROM OLD.signal_type
       OR NEW.strategy IS DISTINCT FROM OLD.strategy
       OR NEW.risk_validation_status IS DISTINCT FROM OLD.risk_validation_status
       OR NEW.generated_at_utc IS DISTINCT FROM OLD.generated_at_utc THEN
        RAISE EXCEPTION 'trading_signals snapshots are immutable; record status transitions in signal_updates.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_trading_signals_immutable
    BEFORE UPDATE ON trading_signals
    FOR EACH ROW
    EXECUTE FUNCTION enforce_trading_signal_immutability();
"""

DROP_IMMUTABLE_SIGNAL_TRIGGER_SQL = """
DROP TRIGGER IF EXISTS trg_trading_signals_immutable ON trading_signals;
DROP FUNCTION IF EXISTS enforce_trading_signal_immutability();
"""


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")
    # Initial baseline schema creation for all 31 normalized tables & indexes
    # (including partial unique index uq_sessions_one_active_per_user).
    # All subsequent migrations (0002+) MUST use explicit op.add_column / op.create_table DDL.
    Base.metadata.create_all(bind=bind, checkfirst=True)
    op.execute(IMMUTABLE_SIGNAL_TRIGGER_SQL)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(DROP_IMMUTABLE_SIGNAL_TRIGGER_SQL)
    Base.metadata.drop_all(bind=bind, checkfirst=True)
