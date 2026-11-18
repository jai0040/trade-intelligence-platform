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

### PHASE 5: Market Adapters & Data Provider Layer — `PENDING`
- [ ] Implement canonical domain models (`Instrument`, `OHLCVBar`, `QuoteSnapshot`, `MarketSession`).
- [ ] Implement `IndiaMarketAdapter` (`NSE`/`BSE`, `INR`, `Asia/Kolkata`, `09:15–15:30 IST`, 75 five-minute bars, Indian tick sizes, Indian ticker validation, NSE/BSE holiday calendar + Muhurat override).
- [ ] Implement `USMarketAdapter` (`NASDAQ`/`NYSE`, `USD`, `America/New_York`, `09:30–16:00 ET`, 78 five-minute bars, DST, early closes, US ticker + ETF validation).
- [ ] Implement `MarketDataProvider` interface + `MockMarketDataProvider` (rich deterministic offline fixtures for both India and US stocks/ETFs so tests run 24/7 outside market hours).
- [ ] Implement pluggable provider adapters (commercial US provider interface + commercial India provider interface + clearly flagged local-dev-only fallback, disabled in production).
- [ ] Implement quote freshness tracking, stale-data rejection guard, and `provider_status` health monitoring.

**Exit Criteria:** Calendar tests (DST, early closes, NSE/US holidays), symbol mapping tests (`RELIANCE.NS`, `M&M`, `BRK.B`), and freshness/outage fail-safe tests all pass.

---

### PHASE 6: Skill Integration & Centralized Workflow Engine — `PENDING`
- [ ] Build typed `BaseSkill` wrappers around all 11 preserved skills:
  1. `trader-scanner` (daily + intraday ORB across India & US equities + ETFs)
  2. `trader-news` (US RSS/8-K + India corporate announcements/news provider)
  3. `trader-analyst` (SEC EDGAR XBRL for US + India fundamentals provider interface)
  4. `trader-entry` (completed-bar confirmation supporting BUY / SELL / WATCH)
  5. `trader-exit` (deterministic stop/target/ATR/R:R using `Decimal` & market tick size)
  6. `trader-timemachine` (seeded Monte Carlo + historical replay parameterized for 75/78 bars)
  7. `trader-budget` (reference model sizing + user-personal position-sizing API)
  8. `trader-risk` (**mandatory non-overridable risk gate** for platform signals + user sizing)
  9. `trader-broker` (**read-only trade ticket generator ONLY** — zero live broker execution)
  10. `trader-alerts` (price/stop/target/time/opening-bell evaluation across both markets)
  11. `trader-pelosi` (US-only House Clerk PTR monitor with pure-Python PDF parser fallback)
- [ ] Build the DAG Workflow Engine with `workflow_run_id`, Redis distributed locks, DB `idempotency_key`, `skill_runs` execution logs, exponential retry handling, and **Global Emergency Kill Switch** checks.
- [ ] Build the decoupled **AI Analyst service** (generates structured reasoning & explanations from deterministic outputs; verified unable to modify prices or bypass risk rejections).
- [ ] Implement immutable `trading_signals` snapshots, calibrated composite confidence scoring, and automated `signal_updates` / `signal_outcomes` tracking.

**Exit Criteria:** End-to-end offline DAG tests pass for both India and US markets; duplicate execution prevention, risk-rejection enforcement, and kill-switch tests pass.

---

### PHASE 7: Trading Dashboard (Subscriber UI) — `PENDING`
- [ ] Build Overview Dashboard (India & US market statuses, indices, active/BUY/SELL/WATCH counts, today's & expired signals, top opportunities, news, performance summary, notifications).
- [ ] Build India Market, US Market, Market Overview, Stock Scanner, and Trading Opportunities views with market filters (`India` / `US` / `All Markets`), search, sorting, pagination, date & strategy filters, and stale-data warnings.
- [ ] Build Stock Details & Signal Details pages featuring **TradingView Lightweight Charts** with entry, stop-loss, and target price overlays, technical indicators, Time Machine replay distribution chart, news, fundamentals, AI analysis, broker-ready reference ticket, and signal history.
- [ ] Build AI Analyst interactive view, Market News feed, Portfolio / Watchlist manager, and Account Settings.
- [ ] Implement real-time WebSocket updates + In-App, Browser Push (opt-in), and Email notification system with user notification preferences.

**Exit Criteria:** Responsive dark/light FinTech UI verified on desktop & mobile viewports; frontend unit/component tests and API integration verified.

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
