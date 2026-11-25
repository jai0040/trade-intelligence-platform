"""Local zero-dependency standalone backend runner for development & testing.

Starts FastAPI on port 8000 using persistent SQLite and embedded Redis double.
Enables full registration, login, market data browsing, trading journal, and billing
without requiring external PostgreSQL or Docker services.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from datetime import datetime, time as dt_time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "backend"), str(ROOT / "trading-engine")):
    if p not in sys.path:
        sys.path.insert(0, p)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("trade_intelligence.local_dev")


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
    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}
        self.published: list[tuple[str, str]] = []

    def ping(self) -> bool:
        return True

    def _prune(self, key: str) -> None:
        item = self._store.get(key)
        if item is not None and item[1] is not None and time.monotonic() >= item[1]:
            self._store.pop(key, None)

    def get(self, key: str) -> str | None:
        self._prune(key)
        item = self._store.get(key)
        return item[0] if item is not None else None

    def setex(self, key: str, ttl_seconds: int, value: str) -> bool:
        self._store[key] = (str(value), time.monotonic() + ttl_seconds)
        return True

    def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0

    def incr(self, key: str, amount: int = 1) -> int:
        self._prune(key)
        item = self._store.get(key)
        if item is None:
            self._store[key] = (str(amount), None)
            return amount
        new_val = int(item[0]) + amount
        self._store[key] = (str(new_val), item[1])
        return new_val

    def expire(self, key: str, ttl_seconds: int) -> bool:
        self._prune(key)
        item = self._store.get(key)
        if item is None:
            return False
        self._store[key] = (item[0], time.monotonic() + ttl_seconds)
        return True

    def ttl(self, key: str) -> int:
        self._prune(key)
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
        pass


def _register_sqlite_pg_compilers() -> None:
    from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB, UUID as PG_UUID
    from sqlalchemy.ext.compiler import compiles

    @compiles(CITEXT, "sqlite")
    def _c_citext(_type: Any, _compiler: Any, **_kw: Any) -> str:
        return "VARCHAR(255)"

    @compiles(INET, "sqlite")
    def _c_inet(_type: Any, _compiler: Any, **_kw: Any) -> str:
        return "VARCHAR(45)"

    @compiles(JSONB, "sqlite")
    def _c_jsonb(_type: Any, _compiler: Any, **_kw: Any) -> str:
        return "JSON"

    @compiles(PG_UUID, "sqlite")
    def _c_uuid(_type: Any, _compiler: Any, **_kw: Any) -> str:
        return "CHAR(36)"


def _normalize_sqlite_server_defaults(metadata: Any) -> None:
    from sqlalchemy import text

    for table in metadata.tables.values():
        for col in table.columns:
            if col.server_default is not None and hasattr(col.server_default, "arg"):
                arg_text = str(col.server_default.arg)
                if "::jsonb" in arg_text:
                    col.server_default.arg = text(arg_text.replace("::jsonb", ""))


def seed_database(session_factory: Any) -> None:
    from app.core.security import hash_password, password_needs_rehash
    from database.models import Base
    from database.models.billing import SubscriptionPlan
    from database.models.identity import Role, User
    from database.models.markets import Exchange, Instrument, Market
    from database.models.signals import SystemSetting

    with session_factory() as db:
        # 1. Roles
        existing_role = db.query(Role).first()
        if not existing_role:
            roles = [
                Role(code="super_admin", name="Super Administrator", permissions={"all": True}),
                Role(code="admin", name="Platform Administrator", permissions={"admin_read": True}),
                Role(code="subscriber", name="Subscriber", permissions={"signals_read": True}),
            ]
            db.add_all(roles)
            db.flush()

        # 2. Markets
        existing_market = db.query(Market).first()
        if not existing_market:
            in_m = Market(code="IN", name="Indian Equity Market", currency="INR", timezone="Asia/Kolkata", is_enabled=True)
            us_m = Market(code="US", name="US Equity Market", currency="USD", timezone="America/New_York", is_enabled=True)
            db.add_all([in_m, us_m])
            db.flush()

            nse = Exchange(market_id=in_m.id, code="NSE", mic_code="XNSE", name="National Stock Exchange of India", regular_open_local=dt_time(9, 15), regular_close_local=dt_time(15, 30), session_5m_bars=75)
            bse = Exchange(market_id=in_m.id, code="BSE", mic_code="XBOM", name="BSE Limited", regular_open_local=dt_time(9, 15), regular_close_local=dt_time(15, 30), session_5m_bars=75)
            nasdaq = Exchange(market_id=us_m.id, code="NASDAQ", mic_code="XNAS", name="NASDAQ Stock Market", regular_open_local=dt_time(9, 30), regular_close_local=dt_time(16, 0), session_5m_bars=78)
            nyse = Exchange(market_id=us_m.id, code="NYSE", mic_code="XNYS", name="New York Stock Exchange", regular_open_local=dt_time(9, 30), regular_close_local=dt_time(16, 0), session_5m_bars=78)
            db.add_all([nse, bse, nasdaq, nyse])
            db.flush()

            # Seed representative instruments
            instruments = [
                Instrument(market_id=in_m.id, exchange_id=nse.id, symbol="RELIANCE", canonical_code="NSE:RELIANCE", company_name="Reliance Industries Ltd.", asset_type="EQUITY", sector="Energy", currency="INR", tick_size=Decimal("0.0500"), lot_size=1, provider_symbols={"mock": "RELIANCE.NS"}),
                Instrument(market_id=in_m.id, exchange_id=nse.id, symbol="TCS", canonical_code="NSE:TCS", company_name="Tata Consultancy Services Ltd.", asset_type="EQUITY", sector="Technology", currency="INR", tick_size=Decimal("0.0500"), lot_size=1, provider_symbols={"mock": "TCS.NS"}),
                Instrument(market_id=in_m.id, exchange_id=nse.id, symbol="INFY", canonical_code="NSE:INFY", company_name="Infosys Ltd.", asset_type="EQUITY", sector="Technology", currency="INR", tick_size=Decimal("0.0500"), lot_size=1, provider_symbols={"mock": "INFY.NS"}),
                Instrument(market_id=in_m.id, exchange_id=nse.id, symbol="HDFCBANK", canonical_code="NSE:HDFCBANK", company_name="HDFC Bank Ltd.", asset_type="EQUITY", sector="Financials", currency="INR", tick_size=Decimal("0.0500"), lot_size=1, provider_symbols={"mock": "HDFCBANK.NS"}),
                Instrument(market_id=us_m.id, exchange_id=nasdaq.id, symbol="TSLA", canonical_code="NASDAQ:TSLA", company_name="Tesla, Inc.", asset_type="EQUITY", sector="Automotive", currency="USD", tick_size=Decimal("0.0100"), lot_size=1, provider_symbols={"mock": "TSLA"}),
                Instrument(market_id=us_m.id, exchange_id=nasdaq.id, symbol="AAPL", canonical_code="NASDAQ:AAPL", company_name="Apple Inc.", asset_type="EQUITY", sector="Technology", currency="USD", tick_size=Decimal("0.0100"), lot_size=1, provider_symbols={"mock": "AAPL"}),
                Instrument(market_id=us_m.id, exchange_id=nasdaq.id, symbol="NVDA", canonical_code="NASDAQ:NVDA", company_name="NVIDIA Corporation", asset_type="EQUITY", sector="Semiconductors", currency="USD", tick_size=Decimal("0.0100"), lot_size=1, provider_symbols={"mock": "NVDA"}),
                Instrument(market_id=us_m.id, exchange_id=nasdaq.id, symbol="MSFT", canonical_code="NASDAQ:MSFT", company_name="Microsoft Corporation", asset_type="EQUITY", sector="Technology", currency="USD", tick_size=Decimal("0.0100"), lot_size=1, provider_symbols={"mock": "MSFT"}),
            ]
            db.add_all(instruments)

        # 3. Subscription Plans
        existing_plan = db.query(SubscriptionPlan).first()
        if not existing_plan:
            plans = [
                SubscriptionPlan(code="india_pro_monthly_inr", name="India Markets Pro (Monthly)", description="NSE & BSE AI trading intelligence signals, scanner, news, and alerts (Signals-Only).", currency="INR", price_amount=Decimal("1999.00"), billing_interval="monthly", grace_period_days=3, entitled_markets=["IN"], features={"ai_analyst_daily_queries": 50, "max_watchlists": 10}, is_active=True),
                SubscriptionPlan(code="us_pro_monthly_usd", name="US Markets Pro (Monthly)", description="NASDAQ & NYSE AI trading intelligence signals, SEC filings, and Congressional PTR tracker.", currency="USD", price_amount=Decimal("29.00"), billing_interval="monthly", grace_period_days=3, entitled_markets=["US"], features={"ai_analyst_daily_queries": 50, "max_watchlists": 10}, is_active=True),
                SubscriptionPlan(code="global_all_markets_monthly_inr", name="Global All-Markets Pro (Monthly INR)", description="Full access to both India (NSE/BSE) and US (NASDAQ/NYSE) markets billed in INR.", currency="INR", price_amount=Decimal("3499.00"), billing_interval="monthly", grace_period_days=3, entitled_markets=["IN", "US"], features={"ai_analyst_daily_queries": 120, "max_watchlists": 25}, is_active=True),
                SubscriptionPlan(code="global_all_markets_monthly_usd", name="Global All-Markets Pro (Monthly USD)", description="Full access to both India (NSE/BSE) and US (NASDAQ/NYSE) markets billed in USD.", currency="USD", price_amount=Decimal("49.00"), billing_interval="monthly", grace_period_days=3, entitled_markets=["IN", "US"], features={"ai_analyst_daily_queries": 120, "max_watchlists": 25}, is_active=True),
            ]
            db.add_all(plans)

        # 4. Super Admin user demo account
        admin_user = db.query(User).filter(User.email == "admin@tradeintel.com").first()
        if not admin_user:
            super_role = db.query(Role).filter(Role.code == "super_admin").first()
            if super_role:
                admin_user = User(
                    role_id=super_role.id,
                    email="admin@tradeintel.com",
                    password_hash=hash_password("AdminPass123!"),
                    full_name="Super Administrator",
                    country_code="IN",
                    is_active=True,
                    is_email_verified=True,
                )
                db.add(admin_user)
        else:
            if password_needs_rehash(admin_user.password_hash):
                admin_user.password_hash = hash_password("AdminPass123!")

        db.commit()
    logger.info("Database seeding complete.")


def run_server() -> None:
    import uvicorn
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker

    from app.core.config import Settings
    from app.main import create_app
    from database.models import Base

    db_path = ROOT / "trade_intelligence_local.db"
    sqlite_url = f"sqlite:///{db_path}"
    logger.info("Initializing local SQLite database: %s", db_path)

    _register_sqlite_pg_compilers()
    _normalize_sqlite_server_defaults(Base.metadata)

    engine = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_con: Any, _con_record: Any) -> None:
        cur = dbapi_con.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    seed_database(session_factory)
    fake_redis = FakeRedis()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)

    import os
    env_provider_in = os.getenv("MARKET_DATA_PROVIDER_IN")
    if not env_provider_in:
        env_provider_in = "angelone" if (os.getenv("ANGELONE_API_KEY") or os.getenv("ANGELONE_JWT_TOKEN")) else "mock"

    settings = Settings(
        app_env="development",
        trading_mode="SIGNALS_ONLY",
        session_cookie_secure=False,
        session_cookie_samesite="lax",
        cors_allowed_origins="http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000",
        market_data_provider_in=env_provider_in,
        market_data_provider_us=os.getenv("MARKET_DATA_PROVIDER_US", "mock"),
        angelone_api_key=os.getenv("ANGELONE_API_KEY", ""),
        angelone_client_code=os.getenv("ANGELONE_CLIENT_CODE", ""),
        angelone_pin=os.getenv("ANGELONE_PIN", ""),
        angelone_totp_secret=os.getenv("ANGELONE_TOTP_SECRET", ""),
        angelone_jwt_token=os.getenv("ANGELONE_JWT_TOKEN", ""),
    )

    app = create_app(
        settings=settings,
        db_engine=engine,
        db_session_factory=session_factory,
        redis_client=fake_redis,
    )

    logger.info("Starting Trade Intelligence Backend on http://localhost:8000")
    logger.info("Demo Super Admin Account: admin@tradeintel.com / AdminPass123!")
    logger.info("Signals-Only hard lock: ACTIVE")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    run_server()
