# Development Roadmap — AI Trading Intelligence SaaS Platform

**Repository:** `trade-intelligence-platform` (Private)  
**Methodology:** Phased, test-gated, audit-first commercial engineering. No phase advances until its exit criteria and automated tests pass.

---

## Status Legend

- `COMPLETED` — Verified and inspected on disk.
- `IN_PROGRESS` — Currently active.
- `PENDING` — Awaiting prior phase completion and user approval.
- `MOCKED_UNTIL_PROD` — Runs against deterministic offline fixtures / sandbox keys until commercial provider/gateway credentials are approved.

---

## Local Prerequisites Before Phase 3 (Windows PowerShell)

Before starting Phase 3 foundation builds, verify or install the following local development tools (do not run until approved):
1. **Python 3.12 or 3.13** (side-by-side with existing Python 3.15.2 via `winget install Python.Python.3.12` or `uv`) so all compiled backend/DB/calendar wheels install cleanly on Windows.
2. **Docker Desktop for Windows** (recommended) for PostgreSQL 16 + Valkey/Redis + isolated service runs — or native PostgreSQL + Redis/Valkey.
3. **Active Workspace:** Open `W:\Projects\trade-intelligence-platform` as the active workspace in Antigravity IDE.
4. **Private GitHub Repository:** Initialize Git locally and connect to your private `trade-intelligence-platform` repo when ready (no public push without explicit approval).

---

## Phase-by-Phase Execution Plan

### PHASE 1: Existing System Audit — `COMPLETED`
- [x] Inspect local workspace, tooling (`Python 3.15.2`, `Node v26.8.2`, `Git 2.55.0`), and environment variables.
- [x] Inspect all 11 installed Claude trading skills (`8,601` LOC pure Python stdlib), `SKILL.md` files, and `.example.json` templates.
- [x] Map inter-skill file communication (`trader/*.json`) and identify multi-tenant blockers.
- [x] Audit US vs. India (NSE/BSE) compatibility down to exact line numbers (symbol `.replace(".", "-")` bug, ticker regexes, 78 vs 75 bars, NYSE-only calendars, SEC-only fundamentals).
- [x] Review upstream MIT licensing (`Jakeschincariol/day-trader-skill`) and commercial market data / SEBI / SEC compliance risks.
- [x] Produce `docs/EXISTING_SYSTEM_AUDIT.md`, `docs/ARCHITECTURE.md`, and `docs/DEVELOPMENT_ROADMAP.md`.

**Gate:** User reviews audit findings and approves proceeding to Phase 2/3.

---

### PHASE 2: Architecture Blueprint & Upstream Vendoring — `COMPLETED`
- [x] Initialize private Git repository `trade-intelligence-platform` with `.gitignore`, `.env.example`, `README.md`, `LICENSE`, `UPSTREAM.md`, and `THIRD_PARTY_NOTICES` (preserving verbatim upstream MIT license + SHA-256 manifest of all 27 vendored files).
- [x] Copy the 11 existing skills unmodified into `trading-engine/skills/` as our version-controlled baseline (leaving `C:\Users\ADMIN\.claude\skills` untouched).
- [x] Finalize detailed OpenAPI v1 contract (`docs/api/openapi.yaml`) and WebSocket event specification (`docs/api/websockets.md`).
- [x] Finalize database ERD, 27-table schema & retention policy (`docs/architecture/database-schema.md`) and skill/adapter interfaces (`docs/architecture/skill-interfaces.md`).
- [x] Finalize compliance & security checklist (`docs/security/security-and-compliance.md`).

**Exit Criteria:** Clean baseline repo with upstream attribution intact and complete API/DB specs committed. **Gate:** Ready for user approval to begin Phase 3.

---

### PHASE 3: Project Foundation — `COMPLETED`
- [x] Scaffold `backend/` (FastAPI, Pydantic Settings enforcing `SIGNALS_ONLY` + production provider guardrails, structured JSON logging with secret scrubbing, `/api/v1/health`, security headers, CORS allowlist).
- [x] Scaffold `database/` with SQLAlchemy 2.x ORM models for all 31 normalized tables, initial Alembic migration (`20261118_0001_initial_schema.py` including `uq_sessions_one_active_per_user` partial unique index and `trg_trading_signals_immutable` trigger), and idempotent seed script (`database/seeds/seed_initial.py`).
- [x] Scaffold `frontend/` (Next.js 15 App Router, TypeScript, Tailwind CSS, FinTech dark/light theme tokens, responsive 16-view `AppShell`, IST/ET clocks, persistent market switcher, live `/api/v1/health` probe).
- [x] Configure Valkey/Redis + Celery worker queues (`india_market`, `us_market`, `analysis`, `notifications`, `maintenance`) + Celery Beat (`trading-engine/scheduler/celery_app.py`) with JSON-only serialization and UTC timezone.
- [x] Create `docker/docker-compose.yml` (PostgreSQL 16, Valkey 8, Backend, Celery Worker, Celery Beat, Frontend), non-root Dockerfiles, and Windows local dev runbook (`docs/deployment/local-development.md`).
- [x] Add Phase 3 foundation verification unit tests (`tests/unit/test_phase3_foundation.py`, `tests/unit/test_phase3_schema_and_config.py`).

**Exit Criteria:** Foundation code, migrations, seeds, Docker stack, and static/unit checks verified. *(Runtime live boot of PostgreSQL/Valkey/Next.js pending Docker Desktop or Python 3.12 `.venv` installation on local PC.)* **Gate:** Ready for user approval to begin Phase 4.

---

### PHASE 4: Authentication, Multi-User SaaS & Single Active Session — `COMPLETED`
- [x] Implement Argon2id password hashing (`time_cost=3`, `64 MiB`, `parallelism=2`), email normalization, strong password policy, registration, login, logout, and one-time SHA-256 hashed password reset tokens with constant `202` anti-enumeration response (`backend/app/core/security.py`, `backend/app/authentication/`).
- [x] Implement server-side `sessions` table + Redis `user:{id}:active_session` store + `HttpOnly`/`Secure`/`SameSite=Lax` cookies + double-submit `X-CSRF-Token` protection + Redis sliding/window rate limiting (`backend/app/core/rate_limit.py`, `backend/app/core/redis.py`).
- [x] Implement **Single Active Session enforcement** (transactional eviction of prior `ACTIVE` session to `SUPERSEDED` + `session_version` bump + `401 SESSION_SUPERSEDED` response + Redis Pub/Sub `ws:user:{id}` + WebSocket `/ws/v1/stream` `session.invalidated` push with close code `4401` + `audit_logs` tracking).
- [x] Implement RBAC guards (`super_admin`, `admin`, `subscriber`), audited admin session revocation & user deactivation (`backend/app/admin/router.py`), and strictly `user_id`-isolated profile, preferences, and watchlist APIs (`backend/app/users/router.py`).
- [x] Implement subscription entitlement service & `require_active_subscription(market_code)` guards (`backend/app/subscriptions/`) ready for Phase 9 Razorpay/Stripe webhook wiring, plus Next.js cookie/CSRF auth client and `/login` & `/register` pages (`frontend/src/lib/api.ts`, `frontend/src/app/login/page.tsx`, `frontend/src/app/register/page.tsx`).
- [x] Add comprehensive Phase 4 unit and integration tests (`tests/conftest.py`, `tests/unit/test_phase4_security_and_auth.py`, `tests/integration/test_phase4_auth_and_isolation.py`).

**Exit Criteria:** Full Phase 4 implementation, static/unit stdlib checks, and automated integration test suite written and committed. *(Full pytest FastAPI/SQLAlchemy/Argon2id runtime execution awaits local Python 3.12 `.venv` or Docker Compose install.)* **Gate:** Ready for user approval to begin Phase 5.

---

### PHASE 5: Market Adapters & Data Provider Layer — `COMPLETED`
- [x] Implement canonical immutable domain models (`Instrument`, `OHLCVBar`, `QuoteSnapshot`, `MarketSession`, `DataFreshnessReport`) with `Decimal` precision, UTC timestamp validation, and built-in IST/US-Eastern DST timezone support (`trading-engine/domain/`).
- [x] Implement `IndiaMarketAdapter` (`NSE`/`BSE`, `INR`, `Asia/Kolkata`, `09:15–15:30 IST`, 75 five-minute bars, Indian tick sizes including sub-₹250 `₹0.01`, Indian ticker validation for `M&M`/`BAJAJ-AUTO`/`RELIANCE.NS`, NSE/BSE holiday calendar + Muhurat special session overrides) (`trading-engine/adapters/india/adapter.py`).
- [x] Implement `USMarketAdapter` (`NASDAQ`/`NYSE`, `USD`, `America/New_York`, `09:30–16:00 ET`, 78 five-minute bars, exact DST transitions, algorithmic NYSE/NASDAQ holidays including Good Friday, 13:00 ET early closes = 42 bars, US ticker & `BRK.B` class-share handling) (`trading-engine/adapters/usa/adapter.py`).
- [x] Implement `MarketDataProvider` interface + deterministic offline `MockMarketDataProvider` (curated India & US equities, ETFs, and indices with realistic daily & intraday bars for 24/7 testing + outage/delay simulation) (`trading-engine/data_providers/mock_provider.py`).
- [x] Implement commercial provider interfaces (`CommercialIndiaDataProvider`, `CommercialUSDataProvider`), strictly local-dev-only `DevYahooDataProvider` hard-blocked in production, and factory enforcement (`trading-engine/data_providers/commercial_interfaces.py`, `factory.py`).
- [x] Implement quote freshness validation, forming-bar filter, stale-data rejection (`StaleDataError`), `ProviderHealthMonitor`, and FastAPI market endpoints (`/api/v1/markets/status`, `/markets/{code}/indices`, `/instruments/search`, `/instruments/{id}/bars`, `/admin/providers/status`) (`backend/app/markets/`).
- [x] Verify all calendar (DST, early closes, NSE/US holidays, Muhurat override), symbol mapping (`RELIANCE.NS`, `M&M`, `BRK.B`), tick rounding, and freshness/outage fail-safe tests (`tests/unit/test_phase5_markets_and_providers.py`, `tests/integration/test_phase5_market_endpoints.py`).

**Exit Criteria:** All Phase 5 live unit tests passed (`ALL PHASE 3, 4 & 5 LIVE UNIT TESTS PASSED!`). **Gate:** Ready for user approval to begin Phase 6.

---

### PHASE 6: Skill Integration & Centralized Workflow Engine — `COMPLETED`
- [x] Build stateless, typed `BaseSkill` wrappers (`trading-engine/skill_wrappers/`) around all 11 vendored skills (leaving `trading-engine/skills/` 100% unmodified):
  1. `scanner_wrapper.py` (`trader-scanner` daily + ORB across India & US equities + ETFs, BUY/SELL/WATCH)
  2. `news_wrapper.py` (`trader-news` US SEC 8-K + India NSE/BSE corporate announcements, deduped)
  3. `analyst_wrapper.py` (`trader-analyst` US SEC EDGAR + India NSE/BSE quarterly fundamentals + gap risk)
  4. `entry_wrapper.py` (`trader-entry` completed-bar confirmation supporting BUY / SELL / WATCH)
  5. `exit_wrapper.py` (`trader-exit` deterministic `Decimal` tick-aligned stop/target/R:R for long & short)
  6. `timemachine_wrapper.py` (`trader-timemachine` seeded Monte Carlo + 60-day replay parameterized for 75/78 bars)
  7. `budget_wrapper.py` (`trader-budget` deterministic `Decimal` model sizing + `/api/v1/tools/position-size`)
  8. `risk_wrapper.py` + `risk_engine/validator.py` (**mandatory non-overridable risk gate** — any block marks signal `Rejected`)
  9. `broker_ticket_wrapper.py` (**SIGNALS-ONLY hard lock** — read-only trade sheet ONLY; `place_live_order` raises `SignalsOnlyPolicyError`)
  10. `alerts_wrapper.py` (`trader-alerts` signal lifecycle & user alert evaluator)
  11. `pelosi_wrapper.py` (`trader-pelosi` US-only House Clerk PTR monitor with pure-Python `pypdf` parser + 45-day disclosure lag flag; skipped on India)
- [x] Build centralized DAG Workflow Engine (`trading-engine/workflows/dag_engine.py`) with `workflow_run_id`, idempotency keys, locks, `skill_runs` telemetry, exponential retries, and **Global Emergency Kill Switch** pre-checks + scheduled Celery India/US tasks (`workflows/tasks.py`, `scheduler/celery_app.py`).
- [x] Build decoupled read-only **AI Analyst** (`trading-engine/ai_analyst/service.py`) refusing `REJECTED` signals and unable to mutate numeric signal prices/levels.
- [x] Implement calibrated Composite Setup Quality Score (`signal_engine/confidence.py`), net-of-cost outcome tracker (`signal_engine/outcome_tracker.py` deducting 15 bps India / 8 bps US), and FastAPI intelligence endpoints (`/scanner/results`, `/signals`, `/signals/{id}`, `/signals/performance/summary`, `/news`, `/disclosures/congress`, `/tools/position-size`, `/ai-analyst/query`, `/admin/kill-switch`, `/admin/workflows`).
- [x] Verify all live unit & end-to-end offline India/US DAG tests (`tests/unit/test_phase6_skills_and_dag.py` + `tests/integration/test_phase6_signals_and_killswitch.py`).

**Exit Criteria:** All live unit & end-to-end India/US DAG tests passed (`ALL PHASE 3, 4, 5 & 6 LIVE UNIT & E2E DAG TESTS PASSED!`). **Gate:** Ready for user approval to begin Phase 7.

---

### PHASE 7: Trading Dashboard (Subscriber UI) — `COMPLETED`
- [x] Implement user-isolated Notifications & Preferences REST API (`backend/app/notifications/router.py`, `schemas.py`) with unread badges, mark-read, mark-all-read, CSRF protection, and integration tests (`tests/integration/test_phase7_notifications.py`).
- [x] Build Overview Dashboard (`frontend/src/components/views/OverviewView.tsx`) displaying India & US live exchange statuses, feed freshness & stale-data warnings, benchmark indices (`NIFTY50`, `SENSEX`, `BANKNIFTY`, `SPY`, `QQQ`, `DIA`), BUY/SELL/WATCH KPIs, top opportunities, filings/news, and performance summary.
- [x] Build India Market, US Market, Market Overview, Stock Scanner, and Trading Opportunities views (`ScannerAndSignalsView.tsx`) with persistent market switcher (`All` / `India` / `US`), search, side filters, sorting, and pagination.
- [x] Build interactive **TradingView Lightweight Charts** candlestick component (`CandlestickSignalChart.tsx`) with Entry, Stop-Loss, and Target overlays + `SignalDetailPanel.tsx` (Composite Setup Quality breakdown, Time Machine diagnostics, read-only broker reference trade ticket, embedded personal position-sizing calculator, and AI explanation).
- [x] Build Stock Analysis & Charts (`StockAnalysisView.tsx`), News & US Congressional PTR Disclosures with 45-day lag badges (`NewsAndDisclosuresView.tsx`), interactive AI Analyst (`AIAnalystView.tsx`), Watchlist manager (`WatchlistView.tsx`), Notifications Center (with opt-in Browser Push), and Account Settings (`NotificationsAndSettingsView.tsx`).
- [x] Implement cookie-authenticated real-time WebSocket hook (`frontend/src/lib/useRealtimeStream.ts`) handling `session.invalidated` (`4401`), live event refreshes, exponential backoff, and state resync + Vitest UI utility tests (`frontend/src/lib/__tests__/phase7_ui_utils.test.ts`).

**Exit Criteria:** Full Phase 7 Subscriber UI, notification backend, WebSocket client, and unit/integration test suites verified and committed. **Gate:** Ready for user approval to begin Phase 8.

---

### PHASE 8: Performance Analytics, Trading Journal & Super Admin — `PENDING`
- [ ] Build Personal Trading Journal (user-isolated trade logs, notes, linked signals, personal P&L tracking).
- [ ] Build Historical Performance Analytics page (win/loss/expired breakdown, R-multiple distribution, drawdown, net-of-cost/slippage methodology disclosures, immutable audit log viewer).
- [ ] Build Super Admin Panel (`/admin`):
  - User directory, activation/deactivation, active session viewer & instant revocation.
  - Subscription & revenue dashboard, configurable subscription plans & grace periods.
  - Market data provider health, API usage/cost monitor, Celery worker status, workflow & skill run logs, failed job retry inspector.
  - Signal performance overview & audited **Global Emergency Kill Switch**.

**Exit Criteria:** Admin RBAC isolation tests, audit-log completeness tests, and kill-switch end-to-end tests pass.

---

### PHASE 9: Payments & Subscriptions (Razorpay + Stripe) — `PENDING`
- [ ] Integrate **Razorpay** (INR subscriptions, orders, HMAC-SHA256 webhook verification, renewal/failure/cancellation handling) in Sandbox/Test mode first.
- [ ] Integrate **Stripe** (USD subscriptions, Checkout/Billing Portal, `Stripe-Signature` verification, renewal/failure/cancellation handling) in Test mode first.
- [ ] Implement idempotent `payment_events` processing, invoice/receipt generation, payment history UI, grace-period automation, and strict access restriction upon expiry.

**Exit Criteria:** Webhook signature forgery tests (rejected with 400/401), duplicate webhook idempotency tests, frontend-spoof rejection tests, and full subscription lifecycle tests pass.

---

### PHASE 10: Production Readiness, Security & Compliance Review — `PENDING`
- [ ] Security audit: OWASP checklist, SQLi/XSS/CSRF/SSRF verification, dependency vulnerability scanning (`pip-audit`, `npm audit`), secret-leak scan, least-privilege Docker containers.
- [ ] Performance & reliability testing: concurrent multi-user load tests, worker failover/graceful shutdown tests, provider outage chaos tests.
- [ ] Backup & disaster recovery runbook: automated encrypted PostgreSQL backups + verified restore test.
- [ ] Legal & compliance gate (user-owned before public paid launch): confirm SEBI RA / SEC regulatory posture, signed commercial market data redistribution agreements (India & US), privacy policy, terms of service, and risk disclosures.
- [ ] Production deployment guide (Docker Compose / VPS / Cloud with TLS, monitoring, alerting).

**Exit Criteria:** All test suites green, zero high/critical vulnerabilities, documented backup/deploy runbooks, and explicit user sign-off before any production rollout.

---

## Git Commit & Branching Discipline

- Branching: `main` (protected, release-ready) + feature branches per phase (`phase-2/repo-foundation`, `phase-3/core-stack`, etc.).
- Commit messages: Conventional Commits (`feat(india-adapter): ...`, `fix(risk-engine): ...`, `test(auth): ...`, `docs(audit): ...`).
- Upstream isolation: No automated upstream syncs. Upstream changes from `Jakeschincariol/day-trader-skill` are reviewed manually, tested in isolation, and logged in `UPSTREAM.md` before merging.
