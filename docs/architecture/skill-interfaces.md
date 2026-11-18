# Trading Engine Interfaces, Market Adapters & Workflow Contracts

This document defines the strict Python boundaries between the **preserved 11 upstream skills** (`trading-engine/skills/`), the **market adapters** (`trading-engine/adapters/`), the **data providers** (`trading-engine/data_providers/`), the **mandatory risk gate** (`trading-engine/risk_engine/`), and the **decoupled AI explanation layer** (`trading-engine/ai_analyst/`).

---

## 1. Canonical Internal Domain Models (`trading-engine/domain/`)

All components operate exclusively on strongly typed Pydantic / dataclass models using `Decimal` for monetary figures and timezone-aware UTC `datetime` objects.

```python
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any


class MarketCode(str, Enum):
    IN = "IN"
    US = "US"


class ExchangeCode(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NASDAQ = "NASDAQ"
    NYSE = "NYSE"


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WATCH = "WATCH"


class SignalStatus(str, Enum):
    PENDING = "Pending"
    ACTIVE = "Active"
    TRIGGERED = "Triggered"
    TARGET_HIT = "Target Hit"
    STOP_LOSS_HIT = "Stop Loss Hit"
    EXPIRED = "Expired"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"


@dataclass(frozen=True)
class Instrument:
    instrument_id: str
    market_code: MarketCode
    exchange_code: ExchangeCode
    symbol: str                    # Canonical exchange symbol: "RELIANCE", "M&M", "TSLA", "BRK.B"
    canonical_code: str            # "NSE:RELIANCE", "NASDAQ:TSLA"
    company_name: str
    asset_type: str                # "EQUITY" | "ETF" | "INDEX"
    currency: str                  # "INR" | "USD"
    tick_size: Decimal             # Decimal("0.05") for NSE/BSE, Decimal("0.01") for US
    lot_size: int
    provider_symbols: dict[str, str]


@dataclass(frozen=True)
class OHLCVBar:
    instrument_id: str
    timeframe: str                 # "1m" | "5m" | "15m" | "1d"
    bar_start_utc: datetime
    bar_end_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    is_complete: bool              # Forming/in-progress bars MUST be False and rejected by trigger logic
    source_provider: str
    fetched_at_utc: datetime


@dataclass(frozen=True)
class QuoteSnapshot:
    instrument_id: str
    last_price: Decimal
    prev_close: Decimal
    volume: int
    quote_timestamp_utc: datetime
    fetched_at_utc: datetime
    source_provider: str
    is_delayed: bool
    delay_seconds: int
```

---

## 2. Market Adapter Interface (`trading-engine/adapters/base.py`)

Each market (`IndiaMarketAdapter`, `USMarketAdapter`) implements `MarketAdapter` independently so no US-only assumptions leak into Indian equity processing (and vice versa).

```python
from abc import ABC, abstractmethod


class MarketAdapter(ABC):
    market_code: MarketCode
    currency: str
    timezone_name: str             # "Asia/Kolkata" | "America/New_York"
    session_5m_bar_count: int      # 75 (India) | 78 (US)

    @abstractmethod
    def validate_symbol(self, symbol: str, exchange: ExchangeCode) -> bool:
        """Market-specific ticker rules (e.g., permits '&', '-', up to 20 chars for NSE/BSE)."""

    @abstractmethod
    def to_provider_symbol(self, instrument: Instrument, provider_code: str) -> str:
        """Explicit symbol mapping without destructive global `.replace('.', '-')` mutations."""

    @abstractmethod
    def round_to_tick(self, price: Decimal, instrument: Instrument, direction: str) -> Decimal:
        """Round away from entry for stops ('down' for BUY, 'up' for SELL) to exchange tick size."""

    @abstractmethod
    def get_session_window(self, exchange: ExchangeCode, session_date: date) -> dict[str, Any]:
        """Returns open_utc, close_utc, is_trading_day, is_early_close, is_special_session, reason."""

    @abstractmethod
    def is_within_entry_window(self, exchange: ExchangeCode, now_utc: datetime) -> tuple[bool, str]:
        """Enforces market-specific entry cutoff (e.g., 09:30–15:00 IST, 09:45–15:30 ET)."""

    @abstractmethod
    def get_cost_model_bps(self) -> Decimal:
        """Documented slippage + statutory/brokerage cost basis points for net outcome tracking."""
```

---

## 3. Pluggable Market Data Provider Interface (`trading-engine/data_providers/base.py`)

```python
class MarketDataProvider(ABC):
    provider_code: str
    is_commercial_licensed: bool

    @abstractmethod
    def get_universe(self, market_code: MarketCode) -> list[Instrument]: ...

    @abstractmethod
    def get_quotes(self, instruments: list[Instrument]) -> dict[str, QuoteSnapshot]: ...

    @abstractmethod
    def get_bars(
        self,
        instrument: Instrument,
        timeframe: str,
        start_utc: datetime,
        end_utc: datetime,
    ) -> list[OHLCVBar]: ...

    @abstractmethod
    def health_check(self) -> dict[str, Any]: ...
```

### Mandatory Freshness & Production Guardrails
1. **Commercial Guard:** When `APP_ENV == "production"`, any provider with `is_commercial_licensed == False` (such as `dev_yahoo`) raises `RuntimeError` on startup.
2. **Staleness Guard:** Every quote/bar returned is checked against `now_utc - quote_timestamp_utc <= QUOTE_STALE_THRESHOLD_SECONDS`. Stale quotes are marked `STALE` and cannot trigger new signals.
3. **Zero Fabricated Prices:** Provider exceptions or empty responses propagate structured `ProviderUnavailableError` records into `provider_status` and render `"Data Unavailable"` in the dashboard.

---

## 4. Standardized Skill Wrapper Contract (`trading-engine/skill_wrappers/base.py`)

Instead of calling CLI scripts against shared `./trader/*.json` files, each of the 11 skills is wrapped in a stateless, thread-safe Python wrapper implementing `BaseSkill`:

```python
@dataclass(frozen=True)
class SkillContext:
    workflow_run_id: str
    market_adapter: MarketAdapter
    data_provider: MarketDataProvider
    as_of_utc: datetime
    config: dict[str, Any]
    user_id: str | None = None     # Populated ONLY for user-scoped tools (personal sizing, alerts)


@dataclass(frozen=True)
class SkillResult:
    skill_name: str
    status: str                    # "SUCCEEDED" | "PARTIAL" | "FAILED" | "SKIPPED"
    data: dict[str, Any]
    warnings: list[str]
    metrics: dict[str, Any]        # scanned_count, duration_ms, etc.
```

### Mapping All 11 Preserved Skills to Wrappers

| # | Preserved Skill | Wrapper Module | Markets Supported | Key Adaptation for Multi-User SaaS |
| --- | --- | --- | --- | --- |
| 1 | `trader-scanner` | `scanner_wrapper.py` | India & US | Injects `MarketDataProvider` bars (stocks + ETFs); supports both bullish (`BUY`/`WATCH`) and bearish (`SELL`/`WATCH`) setups; batch writes to DB instead of `watchlist.json` |
| 2 | `trader-news` | `news_wrapper.py` | India & US | US: licensed news + SEC 8-K Atom; India: NSE/BSE corporate announcements + licensed news; dedupes in `market_news` |
| 3 | `trader-analyst` | `analyst_wrapper.py` | India & US | US: SEC EDGAR XBRL (`facts.py` core logic); India: NSE/BSE financial results adapter; persists into `company_fundamentals` |
| 4 | `trader-entry` | `entry_wrapper.py` | India & US | Uses canonical completed bars only; supports `BUY` (breakout above), `SELL` (breakdown below), and `WATCH` (approaching level) |
| 5 | `trader-exit` | `exit_wrapper.py` | India & US | Preserves `Decimal` math from `exit.py`; parameterizes tick size (`₹0.05` / `$0.01`), supports both long & short stop/target geometry |
| 6 | `trader-timemachine` | `timemachine_wrapper.py` | India & US | Preserves seeded 10k MC + 60d historical replay; parameterizes `session_5m_bar_count` (`75` for India, `78` for US) |
| 7 | `trader-budget` | `budget_wrapper.py` | India & US | Migrates sizing math to `Decimal`; generates reference model sizing for signals AND serves the per-user personal position-size calculator API |
| 8 | `trader-risk` | `risk_wrapper.py` | India & US | **Mandatory non-overridable gate** (`Decimal` math, market-specific symbol/window/currency rules, SHA-256 fingerprint). Any `BLOCK` marks signal `Rejected` |
| 9 | `trader-broker` | `broker_ticket_wrapper.py` | India & US | **SIGNALS-ONLY HARD LOCK:** Generates read-only broker ticket preview JSON/text ONLY. Any attempt to invoke live order placement raises `SignalsOnlyPolicyError` |
| 10 | `trader-alerts` | `alerts_wrapper.py` | India & US | Evaluates user alert rules + signal lifecycle triggers (`Triggered`, `Target Hit`, `Stop Loss Hit`, `Expired`) against fresh quotes; dispatches via Notification Worker |
| 11 | `trader-pelosi` | `pelosi_wrapper.py` | **US Only** | Scheduled hourly on US weekdays; replaces external `pdftotext` dependency with pure-Python `pypdf` parser; tags explicit disclosure lag days |

---

## 5. Deterministic vs. AI Boundary Enforcement

1. **Deterministic Calculation Ownership:** `scanner_wrapper`, `entry_wrapper`, `exit_wrapper`, `timemachine_wrapper`, `budget_wrapper`, `risk_wrapper`, `signal_engine`, and `outcome_tracker` execute **100% deterministic Python** — zero LLM calls.
2. **Mandatory Risk Gate Ordering:** `risk_wrapper.validate(candidate_signal)` runs **before** `ai_analyst.explain(passed_signal)`. If `risk_wrapper` returns `REJECTED`, the signal is persisted with `current_status = 'Rejected'`, `ai_analyst` is skipped, and no subscriber notification is emitted.
3. **AI Analyst Input/Output Schema:** `ai_analyst` receives a frozen, read-only JSON summary of the passed signal's numbers, technicals, news, fundamentals, and Time Machine stats. Its output is strictly a structured explanation object (`thesis`, `key_levels_summary`, `risk_factors`, `catalyst_notes`, `disclaimer`) — it has no write access to numeric signal fields.

---

## 6. Workflow Idempotency & Concurrency Contract

```python
idempotency_key = sha256(
    f"{workflow_type}:{market_code}:{session_date.isoformat()}:{bar_slot_utc.isoformat()}".encode()
).hexdigest()
```

1. **Kill Switch Pre-Check:** Check Redis `system:kill_switch` (backed by PostgreSQL `system_settings`). If enabled, immediately record `workflow_runs.status = 'ABORTED_KILL_SWITCH'` and exit.
2. **Distributed Lock:** Acquire Redis lock `lock:workflow:{idempotency_key}` (`SET NX EX 600`). If lock already held by another worker, exit cleanly without error.
3. **DB Idempotency Guard:** Insert `workflow_runs` with `ON CONFLICT (workflow_type, market_id, idempotency_key) DO NOTHING`. If a `SUCCEEDED` run already exists, skip duplicate execution.
4. **Signal Deduplication:** Each candidate signal carries `signal_idempotency_key = sha256(f"{market_code}:{instrument_id}:{strategy}:{session_date}:{signal_type}")`, enforced by a PostgreSQL `UNIQUE` constraint so Celery task retries can never create duplicate signals or duplicate notifications.
