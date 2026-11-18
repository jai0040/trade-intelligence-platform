# Existing System Audit — AI Trading Intelligence SaaS Platform

**Audit Date:** 2026-11-18  
**Target Repository (Proposed):** `trade-intelligence-platform` (Private)  
**Audit Scope:** Local Windows development environment, installed Claude trading skills (`C:\Users\ADMIN\.claude\skills\trader-*`), upstream source analysis (`Jakeschincariol/day-trader-skill`), India/US market readiness, dependencies, risks, and licensing.

---

## 1. Executive Summary

All **11 existing trading skills** from `day-trader-skill` (v2.0) are installed locally at `C:\Users\ADMIN\.claude\skills\trader-*` and consist of **8,601 lines of pure Python standard-library code** (zero third-party Python dependencies). Every script executes cleanly (`--help` exit code `0`) on the locally installed Python runtime.

However, the existing system is a **single-user, CLI-driven, US-market-only, file-based prototype** built around unofficial free Yahoo Finance endpoints and a local relative `trader/` directory. It has **no web frontend, no backend API, no database, no multi-user isolation, no background worker infrastructure, no payment/subscription layer, and 0% native Indian market (NSE/BSE) compatibility**.

The deterministic trading math (opening-range breakout detection, ATR/R-multiple exit planning, 4-limit position sizing, Monte Carlo + historical replay, cryptographic order fingerprinting, and pre-trade risk rule enforcement) is clean, well-structured, and **highly reusable** once wrapped behind market adapters, licensed data provider interfaces, and multi-tenant database storage.

---

## 2. Local Environment & Workspace Inspection

### 2.1 Active Workspace & Folder Structure
- **Active Workspace:** None configured in Antigravity IDE at audit time.
- **Default Scratch Directory:** `C:\Users\ADMIN\.gemini\antigravity\scratch` was empty prior to creating `trade-intelligence-platform\docs\`.
- **Existing Application Code:** None. No `trade-intelligence-platform` repository, no local Git clone of `day-trader-skill`, and no local `trader/` runtime state folder were found under `C:\Users\ADMIN`, `Documents`, or `Desktop`.
- **Claude Desktop Config:** `%APPDATA%\Claude\claude_desktop_config.json` does not exist (`False`).
- **Installed Skills Location:** `C:\Users\ADMIN\.claude\skills\` (11 folders, installed `2026-11-01`).

### 2.2 Installed Tooling & Versions

| Tool | Status | Version / Location | Audit Notes |
| --- | --- | --- | --- |
| **OS** | Available | Windows (64-bit), PowerShell | Local dev workstation |
| **Python** | Available (with PATH caveat) | `3.15.2` (`C:\Users\ADMIN\AppData\Local\Python\bin\python.exe` -> `pythoncore-3.15-64\python.exe`) + older `3.15.0rc3` (`AppData\Local\Programs\Python\Python315\python.exe`) | **Two Risks:** (1) `WindowsApps\python.exe` App Execution Alias precedes real Python in `PATH` (causing bare `python` to fail in restricted shells) and `py -0p` reports no registered Pythons. (2) Python 3.15 is bleeding-edge; many compiled FastAPI/DB/FinTech wheels target **Python 3.12 or 3.13**. Recommend pinning **Python 3.12/3.13** in project `.venv` & Docker. |
| **pip** | Available | `26.2.2` | Only `pip` is installed globally; **0 third-party packages** installed. |
| **Node.js / npm** | Available | Node `v26.8.2`, npm `11.19.1` | Recommend pinning **Node 22 LTS / 24 LTS** in Docker & CI for Next.js production stability. |
| **Git** | Available | `2.55.0.windows.3` | Ready for repository initialization. |
| **Docker** | **Missing** | Not on PATH | Needed for PostgreSQL, Redis, Celery workers, and reproducible deployment. |
| **PostgreSQL (`psql`)** | **Missing** | Not on PATH | Needed for relational persistence (or via Docker Compose). |
| **Redis (`redis-cli`)** | **Missing** | Not on PATH | Needed for Celery broker, session/cache, and distributed locks (or via Docker Compose). |
| **uv / pnpm** | **Missing** | Not on PATH | Optional modern package managers (Python `venv`/`uv`, Node `npm`/`pnpm`). |
| **GitHub CLI (`gh`)** | **Missing** | Not on PATH | Optional for managing the private GitHub repository. |
| **`pdftotext` (poppler)** | **Missing** | Not on PATH | Optional binary used by `trader-pelosi/ptr.py` to extract rows from downloaded House PTR PDFs. |

### 2.3 Environment Variables
- Audited environment variable names (values never printed or logged).
- **Finding:** No trading, market data, SEC EDGAR (`SEC_USER_AGENT`), broker (`ALPACA_*`), payment (`RAZORPAY_*`, `STRIPE_*`), database (`DATABASE_URL`), or Redis (`REDIS_URL`) environment variables are currently set.

---

## 3. Inventory of Existing 11 Trading Skills

All 11 skills live under `C:\Users\ADMIN\.claude\skills\`. Each skill contains a `SKILL.md` instruction file, one standalone Python script, and (for 4 skills) `.example.json` templates.

| # | Skill Folder | Script (Lines) | `--help` Check | Primary Responsibility | External Data Sources | State Files Read / Written |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `trader-scanner` | `scan.py` (1,083) | PASS (0) | Builds US stock universe; pre-market daily scan (`breakout_20d`, `bull_flag`, `reclaim_ma20`, `oversold`, `oversold_bounce`); intraday 5m ORB scan | Nasdaq Trader `SymDir` (`nasdaqlisted.txt`, `otherlisted.txt`); Yahoo `v7/finance/spark` & `v8/finance/chart` | Reads `trader/config.json`, `trader/universe.txt`; writes `trader/universe.txt`, `trader/watchlist.json` |
| 2 | `trader-news` | `news.py` (546) | PASS (0) | Tracks ticker headlines, SEC 8-K filings, and ≥3% intraday price moves (`MOVING`); keyword-tags items | Yahoo Finance RSS (`region=US&lang=en-US`); Yahoo `v8/finance/chart`; SEC EDGAR Atom feed & `company_tickers.json` | Reads `watchlist.json`, `plan.json`, `portfolio.json`, `config.json`; writes `trader/state/news.json` |
| 3 | `trader-analyst` | `facts.py` (548) | PASS (0) | Extracts quarterly & TTM revenue, margins, net income, diluted EPS, YoY growth, and 8-K EX-99.1 earnings press release links | SEC EDGAR XBRL `companyfacts`, `submissions`, `Archives`, `company_tickers.json` | Reads `trader/config.json` (`sec_user_agent`); writes `trader/metrics.json` |
| 4 | `trader-entry` | `entry.py` (960) | PASS (0) | Evaluates 1m/5m completed bars for Opening-Range Breakout (`orb`) or `level` breakout with optional volume multiplier; supports polling `watch` loop | Yahoo `v8/finance/chart` (`range=1d&interval=5m|1m`) | Reads `watchlist.json`, `config.json`; writes `trader/entry.json` |
| 5 | `trader-exit` | `exit.py` (735) | PASS (0) | Computes deterministic stop (`or-mid`, `or-low`, `price:X`, `pct:X`, `atr:K`) and target (`1R`, `2R`, `price:X`) using `Decimal` rounding; enforces ≥0.05% min risk | Yahoo `v8/finance/chart` (only for `atr:K` stop) | Reads `trader/entry.json`, `trader/config.json`; writes `trader/plan.json` |
| 6 | `trader-timemachine` | `timemachine.py` (956) | PASS (0) | Runs seeded 10,000-path intraday Monte Carlo bootstrap + historical replay across last 60 days of full 5m sessions; produces target/stop/neither odds & verdict | Yahoo `v8/finance/chart` (`range=60d&interval=5m`) | Reads `trader/plan.json`; writes `trader/timemachine.json` |
| 7 | `trader-budget` | `size.py` (881) | PASS (0) | Computes whole-share position sizing across 4 caps (max loss, position cap, max order, cash buffer) + legacy `--weights` allocation; outputs Alpaca bracket JSON | None (offline deterministic) | Reads `config.json`, `plan.json`, `prices.json`, `portfolio.json`; writes `trader/orders.json` |
| 8 | `trader-risk` | `check.py` (819) | PASS (0) | Mandatory pre-trade rule gate (16 checks: format, asset, short, blocked, size, position, cash, stop, max loss, min R:R, daily loss, trades/day, entry window, PDT, duplicate, daily order limit); SHA-256 order fingerprinting | None (offline deterministic) | Reads `orders.json`, `config.json`, `portfolio.json`, `prices.json`, `state/broker.json`; writes `trader/state/risk.json` |
| 9 | `trader-broker` | `ticket.py` (720) | PASS (0) | Renders plain-English trade tickets + Alpaca `place_stock_order` JSON; verifies risk fingerprint & explicit user yes; builds flatten tickets; logs fills. **Does NOT talk to broker directly** (relies on Claude MCP connector) | None (offline deterministic) | Reads `orders.json`, `state/risk.json`, `plan.json`, `config.json`; writes `state/broker.json`, `portfolio.json`, `orders.json` (on flatten) |
| 10 | `trader-alerts` | `alerts.py` (787) | PASS (0) | NYSE market clock + one-shot alert evaluator (`above`, `below`, `stop`, `target`, `pct_move`, `time`, `opening_bell`) + quote fetcher writing `prices.json` | Yahoo `v8/finance/chart`; Stooq CSV (currently 404 per upstream notes) | Reads `plan.json`, `portfolio.json`, `alerts.json`; writes `alerts.json`, `state/alerts.json`, `prices.json` |
| 11 | `trader-pelosi` | `ptr.py` (566) | PASS (0) | Monitors US House Clerk STOCK Act Periodic Transaction Reports (ZIP/XML index + PTR PDFs); parses transactions via `pdftotext` | `disclosures-clerk.house.gov` (`<YEAR>FD.zip`, `ptr-pdfs/<YEAR>/<DocID>.pdf`) | Reads `portfolio.json`; writes `state/pelosi.json`, `state/ptr-pdfs/*.pdf` |

**Total Codebase Audited:** 11 Python scripts (`8,601` LOC), 11 `SKILL.md` files, 5 `.example.json` files.

---

## 4. Inter-Skill Communication & Data Flow (Current State)

Currently, skills communicate exclusively through **shared mutable JSON/text files in a relative `./trader/` working directory**, orchestrated manually by a user typing commands in Claude or Terminal:

```text
trader-scanner (universe -> daily / orb)
    └─> trader/watchlist.json
            ├──> trader-news (headlines + 8-K + move%) ──> trader/state/news.json
            └──> trader-entry (bar-close trigger)
                    └─> trader/entry.json
                            └─> trader-exit (stop + target + R:R)
                                    └─> trader/plan.json
                                            ├──> trader-timemachine (10k MC + 60d history) ──> trader/timemachine.json
                                            ├──> trader-alerts (stop/target/flat-by + quotes) ──> trader/prices.json, alerts.json
                                            └──> trader-budget (4-limit sizing)
                                                    └─> trader/orders.json
                                                            └─> trader-risk (16 checks + fingerprint)
                                                                    └─> trader/state/risk.json
                                                                            └─> trader-broker (ticket rendering only)
                                                                                    └─> trader/state/broker.json, portfolio.json

Independent schedules:
- trader-analyst -> trader/metrics.json (SEC XBRL quarterly facts)
- trader-pelosi  -> trader/state/pelosi.json (US House PTR disclosures)
```

### Critical Architectural Findings on Communication
1. **No Concurrency Safety:** Relative `./trader/*.json` files have no locking, transactions, or tenant partitioning. Running two scans or serving two users simultaneously corrupts state.
2. **Single-Symbol Bottleneck in Pipeline:** `trader-entry`, `trader-exit`, `trader-timemachine`, `trader-budget`, and `trader-alerts --from-plan` operate on a single `trader/entry.json` and `trader/plan.json` at a time rather than a batch of multi-symbol signals.
3. **Signals-Only Policy Alignment:** Notably, `trader-broker/ticket.py` itself **never connects to a broker** — live execution only existed via Claude Desktop's external Alpaca/IBKR MCP server. In our SaaS platform, we will **explicitly disable/omit all broker order-submission connectors** and use `trader-broker` solely to generate **broker-ready reference trade sheets** (signals-only mode).

---

## 5. What Works, What Can Be Reused, and What Needs Modification

### 5.1 What Works & Can Be Reused Directly (Core Domain Logic)
- **Deterministic Math & Validation Engines:**
  - `trader-exit/exit.py`: `Decimal`-based rounding (`ROUND_FLOOR` away from entry for stops, `ROUND_HALF_UP` for targets), 14-bar ATR calculation, 0.05% spread-noise floor, and R-multiple math.
  - `trader-budget/size.py`: 4-limit position sizing (`max_loss`, `position_cap`, `max_order`, `cash_buffer`) and iterative weight-cap reallocation algorithm.
  - `trader-risk/check.py`: Comprehensive 16-rule deterministic risk gate, cumulative batch simulation, 15-minute quote staleness protection (taking the conservative `max(plan_entry, fresh_price)`), and SHA-256 order fingerprinting.
  - `trader-timemachine/timemachine.py`: Seeded (`random.Random(seed)`) intraday ratio-bootstrap Monte Carlo engine (10,000 paths, conservative stop-before-target tie-breaking, 24-bin histogram, percentile fan bands) and exact historical strategy replay.
  - `trader-scanner/scan.py`: Wilder RSI-14, 20-day closing-high breakout, bull flag, 20-day MA reclaim, oversold/bounce detectors, and two-stage ORB scan logic.
  - `trader-entry/entry.py`: Strict completed-bar close confirmation (rejects forming bars and off-grid live ticks), optional volume ratio filter, and simulated-clock replay (`SimClock`) — ideal for deterministic unit tests.
  - `trader-analyst/facts.py`: SEC XBRL concept fallback hierarchy, Q4 derivation from `10-K - (Q1+Q2+Q3)`, restatement deduplication, and bank/insurer margin handling.
  - `trader-news/news.py`: 8-K item severity mapping (`IMPORTANT_ITEMS`), keyword categorization, and deduplication fingerprinting.
  - `trader-alerts/alerts.py`: Alert rule types (`above`, `below`, `stop`, `target`, `pct_move`, `time`, `opening_bell`) with one-shot/rearm semantics.
  - `trader-pelosi/ptr.py`: House Clerk ZIP/XML index parsing and PTR row extraction logic.
- **Offline Testing Mode:** Almost every script supports `--offline` and `--now` flags, which aligns closely with our requirement to run automated test suites outside market hours without live data.

### 5.2 What Needs Modification / Refactoring (via Wrapper & Adapter Layer)
To preserve upstream logic without reckless rewrites, we will vendor the original scripts into `trading-engine/skills/` (immutable reference + minimal audited compatibility patches where strictly required) and build clean Python service interfaces around them:

1. **Decouple Data Fetching from Calculations:** Separate Yahoo/Stooq/Nasdaq/SEC HTTP calls from pure calculation functions so licensed commercial data providers can be injected via `MarketDataProvider` interfaces.
2. **Eliminate Duplicated Calendar & Timezone Code:** `_nth_sunday`, `eastern_offset`, `NYSE_HOLIDAYS`, and `NYSE_EARLY_CLOSE` are copy-pasted across **7 separate scripts** (`alerts.py`, `entry.py`, `exit.py`, `check.py`, `scan.py`, `timemachine.py`, `news.py`, plus partial copies in `size.py` and `ticket.py`) and only cover 2026–2027. Replace with a centralized `MarketCalendar` service backed by `exchange-calendars` + IANA `zoneinfo` (`America/New_York`, `Asia/Kolkata`).
3. **Fix Symbol Normalization & Validation Bugs:** Remove destructive `.replace(".", "-")` transformations and US-only ticker regexes (`^[A-Z]{1,5}$`); use canonical `Instrument(market, exchange, symbol, provider_symbol)` objects.
4. **Currency, Precision & Tick-Size Parameterization:** Replace hardcoded `$` / `*_usd` keys and `$0.01` rounding with market-specific currency (`INR` / `USD`) and exchange tick sizes (`₹0.05` / `₹0.01` on NSE/BSE, `$0.01` on US). Also migrate `trader-budget/size.py` and `trader-risk/check.py` monetary math from `float` to `Decimal` (matching `trader-exit/exit.py` and PostgreSQL `NUMERIC`).
5. **Support BUY, SELL, and WATCH Signals:** Existing `entry.py`, `exit.py`, `size.py`, and `scan.py` are **long-only** (`v2 plans longs only`). Extend the Signal Engine to support short/bearish setups (`SELL` signals for intraday/exit alerts) and `WATCH` signals (approaching trigger / pre-market setups) while keeping risk rules strictly deterministic.
6. **Multi-Symbol Batch Execution & Database Persistence:** Replace `./trader/*.json` file I/O with PostgreSQL repositories keyed by `workflow_run_id`, `idempotency_key`, and `market_id` (shared signals) or `user_id` (private sizing/watchlists/alerts).
7. **Include ETFs in Universe:** `scan.py` explicitly excludes ETFs (rule 1: `not an ETF`); the platform requires both stocks and ETFs for India and US.
8. **Remove PDF Binary Dependency for `trader-pelosi`:** Add pure-Python PDF text extraction fallback (e.g., `pypdf`/`pdfplumber`) so PTR parsing works reliably in Windows and Docker without requiring system `poppler` (`pdftotext`).

---

## 6. Market Compatibility Assessment

### 6.1 US Market Compatibility (NASDAQ / NYSE) — **PARTIAL (Research-Ready, Not SaaS-Ready)**

| Capability | Current Status | Gap for Commercial SaaS |
| --- | --- | --- |
| Symbol Universe | Works via Nasdaq Trader `SymDir` (~5,943 stocks) | Excludes ETFs; needs ETF inclusion + corporate action / delisting tracking |
| Trading Hours & Holidays | Hardcoded NYSE 2026–2027 + custom DST math | Expires Jan 1, 2028; no pre-market / after-hours session modeling |
| Quotes & Intraday Bars | Unofficial Yahoo Finance v7/v8 + broken Stooq (404) | **Not licensed for commercial redistribution**; delayed; rate-limited; replace with licensed US provider (Polygon.io / Databento / Alpaca Business / Twelve Data) |
| Fundamentals (`trader-analyst`) | SEC EDGAR XBRL + 8-K EX-99.1 (public government data) | Works well; needs centralized `SEC_USER_AGENT` and DB caching to respect SEC 10 req/s limit |
| News (`trader-news`) | Yahoo US RSS + SEC 8-K Atom | Yahoo RSS not licensed for commercial resale; pair SEC 8-K with licensed news API (Benzinga / Polygon / Finnhub commercial) |
| Congressional Disclosures (`trader-pelosi`) | US House Clerk PTRs (public government data) | Works well (needs Python PDF parser); Senate remains manual due to site terms |
| Signal Direction | Long-only (`BUY` breakouts only) | Needs `SELL` and `WATCH` signal classification |

### 6.2 Indian Market Compatibility (NSE / BSE) — **INCOMPATIBLE (0% Native Support)**

Every verified incompatibility found in the source code:

| Area | Code Evidence in Existing Skills | Impact on India (NSE/BSE) | Required Engineering Work |
| --- | --- | --- | --- |
| **Symbol Corruption Bug** | `scan.py:271`, `entry.py:231`, `exit.py:394`, `news.py:195`, `alerts.py:197,201`, `timemachine.py:190,689` all execute `.replace(".", "-")` | Silently corrupts `RELIANCE.NS` → `RELIANCE-NS` and `TCS.BO` → `TCS-BO`, breaking lookups | Build `IndiaMarketAdapter` with canonical `(exchange, symbol)` → provider symbol mapping |
| **Ticker Regex Rejection** | `check.py:87`: `^[A-Z]{1,5}([.\-][A-Z]{1,2})?$`<br>`scan.py:400`: `^[A-Z]{1,5}$\|^[A-Z]{1,4}\.[A-Z]$` | Rejects almost all major Indian tickers (`RELIANCE`, `HDFCBANK`, `BAJFINANCE`, `ICICIBANK`, `M&M`, `BAJAJ-AUTO`) | Market-specific ticker validation rules in `IndiaMarketAdapter` (up to 20 chars, `&`, `-`) |
| **Timezone & Trading Hours** | Hardcoded `eastern_offset` (UTC-4/-5), `09:30–16:00 ET`, `SESSION_BARS = 78` (`timemachine.py:86`) | NSE/BSE trades `09:15–15:30 IST` (UTC+05:30, no DST) = **75** 5-minute bars (plus `09:00–09:15` pre-open) | Parameterize session open/close, bar count (75 vs 78), and timezone (`Asia/Kolkata`) via Market Adapter |
| **Exchange Holidays** | Hardcoded `NYSE_HOLIDAYS` 2026–2027 only | Completely misses NSE/BSE holidays (Republic Day, Holi, Diwali, Mahashivratri, Independence Day Aug 15, Gandhi Jayanti, etc.) and Muhurat trading sessions | Integrate authoritative NSE/BSE exchange calendar (`XBOM` / `XNSE`) + admin holiday override table |
| **Instrument Universe** | `scan.py` only fetches `nasdaqtrader.com/dynamic/SymDir/` | Zero Indian equities or ETFs | Build NSE/BSE instrument master sync (NIFTY 50, NIFTY 500, NSE EQ series, BSE Group A/B, Indian ETFs) |
| **Market Data Feed** | Unofficial Yahoo (`region=US`) & Stooq (`.us`) | No licensed real-time/delayed commercial NSE/BSE feed | Plug in authorized Indian market data vendor (e.g., TrueData / Global Datafeeds / exchange-authorized data partner) |
| **Fundamentals (`trader-analyst`)** | Hardcoded to US `sec.gov` XBRL | Indian companies do not file 10-K/10-Q/8-K with the US SEC | Implement India Fundamentals Provider (NSE/BSE corporate results/XBRL filings or licensed vendor) |
| **News (`trader-news`)** | Hardcoded `region=US&lang=en-US` + SEC 8-K | Misses NSE/BSE corporate announcements, board meetings, RBI policy, SEBI actions | Add India News & Corporate Announcements Provider (NSE/BSE disclosures + licensed news feed) |
| **Currency & Risk Config** | Hardcoded `*_usd` keys (`max_order_usd`, `max_loss_per_trade_usd`) & `$` output | Cannot represent INR sizing, Indian tick sizes (`₹0.05`), or circuit-filter awareness | Currency-agnostic config (`currency: INR|USD`, `max_order_amount`, `max_loss_per_trade`) |
| **Pelosi Tracker (`trader-pelosi`)** | US House Clerk STOCK Act only | Not applicable to Indian equities | Scope `trader-pelosi` strictly to US market; optionally add SEBI SAST/PIT Insider Disclosure tracker in a later phase |

---

## 7. Missing Functionality (Gap Analysis for SaaS Product)

Everything required by the SaaS vision that does **not** exist anywhere today:
1. **Web Application Frontend:** Next.js + TypeScript + Tailwind + shadcn/ui + TradingView Lightweight Charts (16 user dashboard views + Super Admin panel).
2. **Backend API & Real-Time Layer:** FastAPI REST API + WebSocket server for live signal updates, alerts, and real-time single-session invalidation.
3. **Database & Migrations:** PostgreSQL + SQLAlchemy + Alembic (23+ normalized tables with UTC timestamps, row ownership constraints, immutable signal snapshots, and audit logs).
4. **Distributed Scheduling & Workers:** Celery + Redis workers, market-calendar-aware scheduler, distributed locks, unique `workflow_run_id`, idempotency keys, dead-letter/retry handling, and global emergency kill switch.
5. **Authentication & Single Active Session:** Server-side session table + Redis active-session registry, Argon2id password hashing, HttpOnly/Secure/SameSite cookies, CSRF protection, RBAC (`super_admin`, `admin`, `subscriber`), and automatic prior-session eviction on new login.
6. **Multi-User Subscription & Payments:** Razorpay (India/INR) + Stripe (International/USD) integrations, HMAC/signature-verified webhooks, subscription lifecycle (active, grace period, past_due, cancelled, expired), invoices/receipts, and Super Admin configurable plans.
7. **Signal Lifecycle & Performance Engine:** Immutable signal snapshots, deterministic status transitions (`Pending` → `Active` → `Triggered` → `Target Hit` / `Stop Loss Hit` / `Expired` / `Cancelled` / `Rejected`), calibrated confidence scoring methodology, and auditable historical outcome tracking (accounting for slippage/costs).
8. **AI Analysis Layer (Decoupled from Math):** Structured LLM explanation & synthesis service consuming deterministic outputs from scanner/news/analyst/exit/timemachine without ever overriding deterministic risk validation.
9. **Multi-Channel Notifications:** In-app notification center, Web Push / browser notifications, transactional email, per-user notification preferences, and deduplication.
10. **Super Admin & Observability:** User/session management, revenue & subscription dashboards, provider health/freshness monitor, skill & workflow execution monitor, API cost tracking, structured JSON logging, and global emergency kill switch.
11. **Automated Test Suite & CI:** Unit, integration, multi-tenant isolation, session eviction, webhook verification, market calendar, deterministic calculation, and frontend tests with offline mock market fixtures.

---

## 8. Dependencies Analysis

### 8.1 Existing Skills Dependencies
- **Python runtime:** Standard library only (`argparse`, `csv`, `datetime`, `decimal`, `email`, `gzip`, `hashlib`, `io`, `json`, `math`, `os`, `random`, `re`, `shutil`, `statistics`, `subprocess`, `sys`, `time`, `urllib`, `xml`, `zipfile`).
- **Optional OS binary:** `pdftotext` (Poppler — GPLv2/GPLv3 if bundled, safe as external CLI; better replaced in Python with MIT/BSD `pypdf` for clean commercial licensing).

### 8.2 Target SaaS Platform Dependencies (Pinned & License-Screened)
- **Backend:** FastAPI (MIT), Uvicorn (BSD), Pydantic v2 (MIT), SQLAlchemy 2.x (MIT), Alembic (MIT), psycopg 3 (LGPL-3.0 — dynamic link compliant), Celery (BSD), Redis-py (MIT), Argon2-cffi (MIT), httpx (BSD), `exchange-calendars` (Apache-2.0), `pypdf` (BSD-3), Stripe SDK (MIT), Razorpay SDK (MIT).
- **Frontend:** Next.js (MIT), React (MIT), TypeScript (Apache-2.0), Tailwind CSS (MIT), shadcn/ui / Radix UI (MIT), TradingView Lightweight Charts (Apache-2.0 — requires attribution notice per Apache-2.0 & TradingView guidelines).
- **Infrastructure:** PostgreSQL (PostgreSQL License), Redis (RSALv2/SSPLv1 or Valkey BSD-3 — **recommend Valkey or Redis 7.2 BSD** to avoid SSPL commercial ambiguity).

---

## 9. Risks & Licensing / Compliance Observations

### 9.1 Licensing Observations
1. **Upstream Repository (`Jakeschincariol/day-trader-skill`):** Published under the **MIT License**. Commercial use, modification, and inclusion in a private repository (`trade-intelligence-platform`) are permitted **provided the original copyright notice and MIT license text are retained**.
2. **Missing Local Attribution Files:** The local copy in `C:\Users\ADMIN\.claude\skills` lacks the upstream `LICENSE` file and exact Git commit SHA. **Action required before Phase 3:** Record the exact upstream commit SHA and verbatim MIT license text in `UPSTREAM.md` and `THIRD_PARTY_NOTICES`.
3. **Commercial Market Data Redistribution (HIGHEST TECHNICAL/LEGAL RISK):** Yahoo Finance's unofficial `query1`/`query2` endpoints and RSS feeds do **not** grant commercial redistribution rights and violate Yahoo's Terms of Service if resold in a paid SaaS. They may only be used for personal/local R&D validation; production must use properly licensed commercial providers for both India and US.
4. **Redis Licensing:** Redis ≥7.4 moved to RSALv2/SSPLv1. Using **Valkey** (Linux Foundation, BSD-3-Clause, drop-in Redis protocol compatible) or Redis 7.2 avoids commercial license risk.

### 9.2 Regulatory & Legal Risks
1. **India (SEBI):** Generating and monetizing stock-specific BUY/SELL signals with entry, stop-loss, and target prices for NSE/BSE stocks generally requires **SEBI Research Analyst (RA)** registration (and Investment Adviser registration if personalized). Launching paid Indian stock signals without regulatory counsel/registration carries severe enforcement risk.
2. **United States (SEC / FINRA):** Monetizing stock-specific signals requires legal review under the **Investment Advisers Act of 1940** (the publisher's exclusion has strict criteria: bona fide, impersonal, regular schedule, non-tailored).
3. **Signals-Only Guardrail:** Retaining strict **signals-only mode** (zero automated broker order execution, zero user broker credential custody) significantly reduces broker-dealer / algorithmic-trading regulatory exposure, though research/advisory rules still apply.

### 9.3 Technical & Operational Risks
1. **Python 3.15 Wheel Compatibility:** Local machine runs Python 3.15.2; production & dev virtual environments should standardize on **Python 3.12 LTS / 3.13** to guarantee wheel availability for `pydantic-core`, `psycopg`, `cryptography`, and `exchange-calendars`.
2. **No Local Docker / DB / Redis:** Running the full SaaS stack locally requires installing Docker Desktop (recommended) or native PostgreSQL + Valkey/Redis.
3. **Stale Data & Provider Outages:** Free feeds silently lag or return partial bars. Production must attach `(provider, fetched_at_utc, data_timestamp_utc, delay_seconds)` to every quote/bar and refuse signal generation when data exceeds market freshness thresholds.
4. **Signal Integrity & Calibration:** Arbitrary LLM confidence scores must never be presented as win probabilities. Confidence scores must be derived from explicit, documented, backtested rule components (scanner strength, volume confirmation, timemachine historical expectancy, news risk penalty).
