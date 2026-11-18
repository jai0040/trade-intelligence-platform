"""Idempotent initial database seed script.

Seeds:
- RBAC roles: super_admin, admin, subscriber
- Markets: IN (INR, Asia/Kolkata), US (USD, America/New_York)
- Exchanges: NSE, BSE, NASDAQ, NYSE
- Global system_settings (kill_switch_enabled=false, trading_mode=SIGNALS_ONLY)
- Default Super Admin-editable subscription plans (INR & USD)

Usage:
    python -m database.seeds.seed_initial
"""

from __future__ import annotations

from datetime import time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Exchange, Market, Role, SubscriptionPlan, SystemSetting
from database.session import build_engine, build_session_factory


ROLES_SEED = [
    {
        "code": "super_admin",
        "name": "Super Administrator",
        "permissions": {"admin": True, "kill_switch": True, "manage_plans": True, "revoke_sessions": True},
    },
    {
        "code": "admin",
        "name": "Platform Administrator",
        "permissions": {"admin": True, "kill_switch": False, "manage_plans": False, "revoke_sessions": True},
    },
    {
        "code": "subscriber",
        "name": "Subscriber",
        "permissions": {"admin": False, "read_signals": True, "workspace": True},
    },
]

MARKETS_SEED = [
    {"code": "IN", "name": "Indian Equity Market", "currency": "INR", "timezone": "Asia/Kolkata"},
    {"code": "US", "name": "US Equity Market", "currency": "USD", "timezone": "America/New_York"},
]

EXCHANGES_SEED = [
    {
        "market_code": "IN",
        "code": "NSE",
        "mic_code": "XNSE",
        "name": "National Stock Exchange of India",
        "regular_open_local": time(9, 15),
        "regular_close_local": time(15, 30),
        "session_5m_bars": 75,
    },
    {
        "market_code": "IN",
        "code": "BSE",
        "mic_code": "XBOM",
        "name": "BSE Limited (Bombay Stock Exchange)",
        "regular_open_local": time(9, 15),
        "regular_close_local": time(15, 30),
        "session_5m_bars": 75,
    },
    {
        "market_code": "US",
        "code": "NASDAQ",
        "mic_code": "XNAS",
        "name": "Nasdaq Stock Market",
        "regular_open_local": time(9, 30),
        "regular_close_local": time(16, 0),
        "session_5m_bars": 78,
    },
    {
        "market_code": "US",
        "code": "NYSE",
        "mic_code": "XNYS",
        "name": "New York Stock Exchange",
        "regular_open_local": time(9, 30),
        "regular_close_local": time(16, 0),
        "session_5m_bars": 78,
    },
]

SYSTEM_SETTINGS_SEED = {
    "kill_switch_enabled": {"enabled": False, "reason": "Initial default state"},
    "trading_mode": {"mode": "SIGNALS_ONLY", "live_execution_allowed": False},
    "freshness_thresholds": {
        "quote_stale_threshold_seconds": 900,
        "signal_stale_threshold_seconds": 300,
    },
}

PLANS_SEED = [
    {
        "code": "india_pro_monthly_inr",
        "name": "India Markets Pro (Monthly)",
        "description": "NSE & BSE AI trading intelligence signals, scanner, news, and alerts (Signals-Only).",
        "currency": "INR",
        "price_amount": Decimal("1999.00"),
        "billing_interval": "monthly",
        "grace_period_days": 3,
        "entitled_markets": ["IN"],
        "features": {"ai_analyst_daily_queries": 50, "max_watchlists": 10},
    },
    {
        "code": "us_pro_monthly_usd",
        "name": "US Markets Pro (Monthly)",
        "description": "NASDAQ & NYSE AI trading intelligence signals, SEC filings, and Congressional PTR tracker.",
        "currency": "USD",
        "price_amount": Decimal("29.00"),
        "billing_interval": "monthly",
        "grace_period_days": 3,
        "entitled_markets": ["US"],
        "features": {"ai_analyst_daily_queries": 50, "max_watchlists": 10},
    },
    {
        "code": "global_all_markets_monthly_inr",
        "name": "Global All-Markets Pro (Monthly INR)",
        "description": "Full access to both India (NSE/BSE) and US (NASDAQ/NYSE) markets billed in INR.",
        "currency": "INR",
        "price_amount": Decimal("3499.00"),
        "billing_interval": "monthly",
        "grace_period_days": 3,
        "entitled_markets": ["IN", "US"],
        "features": {"ai_analyst_daily_queries": 120, "max_watchlists": 25},
    },
    {
        "code": "global_all_markets_monthly_usd",
        "name": "Global All-Markets Pro (Monthly USD)",
        "description": "Full access to both India (NSE/BSE) and US (NASDAQ/NYSE) markets billed in USD.",
        "currency": "USD",
        "price_amount": Decimal("49.00"),
        "billing_interval": "monthly",
        "grace_period_days": 3,
        "entitled_markets": ["IN", "US"],
        "features": {"ai_analyst_daily_queries": 120, "max_watchlists": 25},
    },
]


def seed_all(db: Session) -> dict[str, int]:
    inserted = {"roles": 0, "markets": 0, "exchanges": 0, "settings": 0, "plans": 0}

    for item in ROLES_SEED:
        if db.scalar(select(Role).where(Role.code == item["code"])) is None:
            db.add(Role(**item))
            inserted["roles"] += 1

    market_map: dict[str, Market] = {}
    for item in MARKETS_SEED:
        existing = db.scalar(select(Market).where(Market.code == item["code"]))
        if existing is None:
            existing = Market(**item)
            db.add(existing)
            db.flush()
            inserted["markets"] += 1
        market_map[item["code"]] = existing

    for item in EXCHANGES_SEED:
        if db.scalar(select(Exchange).where(Exchange.code == item["code"])) is None:
            data = {k: v for k, v in item.items() if k != "market_code"}
            db.add(Exchange(market_id=market_map[item["market_code"]].id, **data))
            inserted["exchanges"] += 1

    for key, value in SYSTEM_SETTINGS_SEED.items():
        if db.get(SystemSetting, key) is None:
            db.add(SystemSetting(key=key, value=value))
            inserted["settings"] += 1

    for item in PLANS_SEED:
        if db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == item["code"])) is None:
            db.add(SubscriptionPlan(**item))
            inserted["plans"] += 1

    db.commit()
    return inserted


def main() -> None:
    engine = build_engine()
    session_factory = build_session_factory(engine)
    with session_factory() as db:
        result = seed_all(db)
    print(f"Seed complete (idempotent): {result}")


if __name__ == "__main__":
    main()
