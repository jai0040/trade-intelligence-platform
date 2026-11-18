"""Shared pytest fixtures: SQLite/PostgreSQL ORM harness, FakeRedis with Pub/Sub, and TestClient."""

from __future__ import annotations

import sys
import time
import uuid
from datetime import time as dt_time
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for path_entry in (str(ROOT), str(ROOT / "backend"), str(ROOT / "trading-engine")):
    if path_entry not in sys.path:
        sys.path.insert(0, path_entry)


class FakeRedisPipeline:
    def __init__(self, client: FakeRedis) -> None:
        self._client = client
        self._ops: list[tuple[str, tuple[Any, ...]]] = []

    def incr(self, key: str, amount: int = 1) -> FakeRedisPipeline:
        self._ops.append(("incr", (key, amount)))
        return self

    def ttl(self, key: str) -> FakeRedisPipeline:
        self._ops.append(("ttl", (key,)))
        return self

    def execute(self) -> list[Any]:
        results: list[Any] = []
        for op, args in self._ops:
            results.append(getattr(self._client, op)(*args))
        self._ops.clear()
        return results


class FakeRedis:
    """Thread-safe in-memory Redis/Valkey test double supporting TTL, pipelines, and Pub/Sub."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}
        self.published: list[tuple[str, str]] = []

    def ping(self) -> bool:
        return True

    def _prune_if_expired(self, key: str) -> None:
        item = self._store.get(key)
        if item is not None and item[1] is not None and time.monotonic() >= item[1]:
            self._store.pop(key, None)

    def get(self, key: str) -> str | None:
        self._prune_if_expired(key)
        item = self._store.get(key)
        return item[0] if item is not None else None

    def setex(self, key: str, ttl_seconds: int, value: str) -> bool:
        self._store[key] = (str(value), time.monotonic() + ttl_seconds)
        return True

    def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0

    def incr(self, key: str, amount: int = 1) -> int:
        self._prune_if_expired(key)
        item = self._store.get(key)
        if item is None:
            new_val = amount
            self._store[key] = (str(new_val), None)
            return new_val
        new_val = int(item[0]) + amount
        self._store[key] = (str(new_val), item[1])
        return new_val

    def expire(self, key: str, ttl_seconds: int) -> bool:
        self._prune_if_expired(key)
        item = self._store.get(key)
        if item is None:
            return False
        self._store[key] = (item[0], time.monotonic() + ttl_seconds)
        return True

    def ttl(self, key: str) -> int:
        self._prune_if_expired(key)
        item = self._store.get(key)
        if item is None:
            return -2
        if item[1] is None:
            return -1
        return max(0, int(item[1] - time.monotonic()))

    def pipeline(self) -> FakeRedisPipeline:
        return FakeRedisPipeline(self)

    def publish(self, channel: str, message: str) -> int:
        self.published.append((channel, message))
        return 1

    def close(self) -> None:
        return None


def _register_sqlite_pg_compilers() -> None:
    """Allow PostgreSQL-typed ORM models to compile cleanly on SQLite during local unit tests."""
    from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB, UUID as PG_UUID
    from sqlalchemy.ext.compiler import compiles

    @compiles(CITEXT, "sqlite")
    def _compile_citext_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
        return "VARCHAR(255)"

    @compiles(INET, "sqlite")
    def _compile_inet_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
        return "VARCHAR(45)"

    @compiles(JSONB, "sqlite")
    def _compile_jsonb_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
        return "JSON"

    @compiles(PG_UUID, "sqlite")
    def _compile_uuid_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
        return "CHAR(36)"


def _normalize_sqlite_server_defaults(metadata: Any) -> None:
    """Replace PostgreSQL '::jsonb' server defaults with plain JSON strings for SQLite DDL."""
    from sqlalchemy import text

    for table in metadata.tables.values():
        for col in table.columns:
            if col.server_default is not None and hasattr(col.server_default, "arg"):
                arg_text = str(col.server_default.arg)
                if "::jsonb" in arg_text:
                    cleaned = arg_text.replace("::jsonb", "")
                    col.server_default.arg = text(cleaned)


def build_test_app_context(rate_limit_login_max: int = 10) -> dict[str, Any]:
    """Create an isolated SQLite DB + FakeRedis + seeded FastAPI app for integration tests."""
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.config import Settings
    from app.core.rate_limit import reset_in_memory_rate_limits
    from app.main import create_app
    from database.models import Base
    from database.models.billing import SubscriptionPlan
    from database.models.identity import Role
    from database.models.markets import Exchange, Instrument, Market

    reset_in_memory_rate_limits()
    _register_sqlite_pg_compilers()
    _normalize_sqlite_server_defaults(Base.metadata)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    # Seed roles, markets, exchanges, sample instruments, and subscription plans
    with session_factory() as db:
        roles = [
            Role(code="super_admin", name="Super Administrator", permissions={"all": True}),
            Role(code="admin", name="Platform Administrator", permissions={"admin_read": True}),
            Role(code="subscriber", name="Subscriber", permissions={"signals_read": True}),
        ]
        db.add_all(roles)

        in_market = Market(
            code="IN", name="India Equities", currency="INR", timezone="Asia/Kolkata", is_enabled=True
        )
        us_market = Market(
            code="US", name="US Equities", currency="USD", timezone="America/New_York", is_enabled=True
        )
        db.add_all([in_market, us_market])
        db.flush()

        nse = Exchange(
            market_id=in_market.id,
            code="NSE",
            mic_code="XNSE",
            name="National Stock Exchange of India",
            regular_open_local=dt_time(9, 15),
            regular_close_local=dt_time(15, 30),
            session_5m_bars=75,
        )
        nasdaq = Exchange(
            market_id=us_market.id,
            code="NASDAQ",
            mic_code="XNAS",
            name="NASDAQ Stock Market",
            regular_open_local=dt_time(9, 30),
            regular_close_local=dt_time(16, 0),
            session_5m_bars=78,
        )
        db.add_all([nse, nasdaq])
        db.flush()

        reliance = Instrument(
            market_id=in_market.id,
            exchange_id=nse.id,
            symbol="RELIANCE",
            canonical_code="NSE:RELIANCE",
            company_name="Reliance Industries Limited",
            asset_type="EQUITY",
            sector="Energy",
            currency="INR",
            tick_size=Decimal("0.0500"),
            lot_size=1,
            provider_symbols={"mock": "RELIANCE.NS"},
        )
        tsla = Instrument(
            market_id=us_market.id,
            exchange_id=nasdaq.id,
            symbol="TSLA",
            canonical_code="NASDAQ:TSLA",
            company_name="Tesla, Inc.",
            asset_type="EQUITY",
            sector="Automotive",
            currency="USD",
            tick_size=Decimal("0.0100"),
            lot_size=1,
            provider_symbols={"mock": "TSLA"},
        )
        db.add_all([reliance, tsla])

        plan_in = SubscriptionPlan(
            code="india_monthly_inr",
            name="India Market Monthly",
            description="NSE & BSE signals",
            currency="INR",
            price_amount=Decimal("2499.00"),
            billing_interval="monthly",
            grace_period_days=3,
            entitled_markets=["IN"],
            features={"signals": True},
            is_active=True,
        )
        plan_global = SubscriptionPlan(
            code="global_pro_inr",
            name="Global Pro (India + US)",
            description="NSE/BSE + NASDAQ/NYSE signals",
            currency="INR",
            price_amount=Decimal("4499.00"),
            billing_interval="monthly",
            grace_period_days=3,
            entitled_markets=["IN", "US"],
            features={"signals": True, "ai_analyst": True},
            is_active=True,
        )
        db.add_all([plan_in, plan_global])
        db.commit()

        seed_ids = {
            "reliance_id": reliance.id,
            "tsla_id": tsla.id,
            "plan_in_id": plan_in.id,
            "plan_global_id": plan_global.id,
        }

    fake_redis = FakeRedis()
    settings = Settings(
        app_env="test",
        trading_mode="SIGNALS_ONLY",
        session_cookie_secure=False,
        cors_allowed_origins="http://localhost:3000,http://testserver",
        rate_limit_login_max=rate_limit_login_max,
        rate_limit_register_max=50,
        rate_limit_reset_max=50,
    )
    app = create_app(
        settings=settings,
        db_engine=engine,
        db_session_factory=session_factory,
        redis_client=fake_redis,
    )
    return {
        "app": app,
        "engine": engine,
        "session_factory": session_factory,
        "redis": fake_redis,
        "settings": settings,
        "seed_ids": seed_ids,
    }
