# Security & Regulatory Compliance Specification

This document defines mandatory security controls, verification tests, and legal/regulatory pre-launch gates for the commercial **AI Trading Intelligence SaaS Platform**.

---

## 1. Mandatory Application Security Controls

| Control Area | Production Requirement | Verification Test |
| --- | --- | --- |
| **Password Storage** | `Argon2id` (`argon2-cffi`, time_cost ≥ 3, memory_cost ≥ 64 MiB, parallelism ≥ 2). Passwords never logged or serialized. | Unit test verifies Argon2id prefix & non-plaintext storage |
| **Session Management** | 256-bit cryptographically random opaque token; only SHA-256 `token_hash` stored in DB; `HttpOnly`, `Secure` (prod), `SameSite=Lax` cookies. Zero tokens in `localStorage`. | Auth API tests verify cookie flags & DB hash-only storage |
| **Single Active Session** | Atomic DB transaction increments `users.session_version`, revokes prior active session, enforces `UNIQUE(user_id) WHERE status='ACTIVE'`, updates Redis, and pushes WS `session.invalidated`. | Concurrent multi-device login test confirms Device 1 gets `401 SESSION_SUPERSEDED` |
| **CSRF Protection** | Synchronizer / double-submit `X-CSRF-Token` required on all state-changing routes (`POST`/`PUT`/`PATCH`/`DELETE`) using session cookies. | Security test confirms missing/invalid CSRF token returns `403` |
| **RBAC & Multi-Tenant Isolation** | Backend dependency guards (`require_role`, `require_active_subscription`) + mandatory `WHERE user_id = :current_user_id` scoping on all private tables (`watchlists`, `journal`, `alerts`, `notifications`, `payments`, `preferences`). | Cross-tenant isolation test confirms User A gets `403`/`404` on User B's IDs |
| **Input & SQLi/XSS Protection** | Strict Pydantic v2 schemas, parameterized SQLAlchemy 2.x queries only (zero raw string SQL interpolation), React auto-escaping + strict Content Security Policy (CSP). | Security test suite injects SQLi/XSS payloads and verifies rejection/escaping |
| **Rate Limiting** | Redis sliding-window rate limits on `/auth/login`, `/auth/register`, `/auth/password-reset`, `/ai-analyst/query`, and general API routes. | Rate-limit test confirms `429 Too Many Requests` after threshold |
| **Payment Webhook Security** | Razorpay verified via constant-time `hmac.compare_digest` (`X-Razorpay-Signature`); Stripe verified via `stripe.Webhook.construct_event` with replay tolerance; idempotency enforced via `payment_events(provider, provider_event_id)`. Frontend callbacks **never** activate subscriptions. | Forged-signature test (`400`), replay/duplicate event test, spoofed-frontend test |
| **Secrets & Encryption** | All secrets injected via environment variables / host secret store; `.env` gitignored; sensitive DB credentials (if any) encrypted with Fernet/AES-GCM (`FIELD_ENCRYPTION_KEY`); sensitive fields scrubbed from JSON logs. | CI secret scan + log-scrubbing test |
| **Signals-Only Guardrail** | No live broker API keys accepted or stored; no broker order-submission modules installed; `TRADING_MODE=SIGNALS_ONLY` asserted at startup. | Startup & unit test verifies `trader-broker` wrapper refuses execution |
| **Admin Auditability** | Every Super Admin action (user activation/deactivation, session revocation, plan price change, emergency kill switch) writes an immutable row to `audit_logs`. | Admin API tests verify audit row creation on every privileged mutation |
| **Supply Chain & Containers** | Pinned dependencies, periodic `pip-audit` & `npm audit`, non-root Docker container users, read-only root filesystem where feasible, internal-only DB/Valkey networks. | CI vulnerability & Dockerfile lint checks |

---

## 2. Emergency Kill Switch Behavior

When a Super Admin activates the **Global Emergency Kill Switch** (`POST /api/v1/admin/kill-switch`):
1. PostgreSQL `system_settings['kill_switch_enabled']` is set to `true` and Redis `system:kill_switch` is updated atomically.
2. An `audit_logs` record (`KILL_SWITCH_ENABLED`, actor, reason, IP, timestamp) is persisted.
3. All scheduled Celery workflows immediately abort before scanning or signal publication (`workflow_runs.status = 'ABORTED_KILL_SWITCH'`).
4. **Zero historical data is deleted or modified.** Existing signals, outcomes, user journals, and dashboards remain readable with a clear platform notice banner.

---

## 3. Pre-Launch Legal & Regulatory Compliance Gates (User-Owned)

> **IMPORTANT:** A generic disclaimer is **not** sufficient for legal compliance. Do **not** launch paid public signal subscriptions until the items below are reviewed and signed off by qualified legal counsel.

### 3.1 India (SEBI & Payment Compliance)
- [ ] **SEBI Research Analyst (RA) Regulations:** Determine whether publishing paid stock-specific BUY/SELL signals with entry, stop-loss, and target levels for NSE/BSE equities requires SEBI RA registration (or whether operating under a registered RA entity / strictly educational model is required).
- [ ] **SEBI Investment Adviser (IA) Boundary:** Confirm personalized position sizing tools remain user-input deterministic calculators and do not cross into individualized investment advice without IA registration.
- [ ] **Indian Market Data Redistribution:** Execute commercial data-redistribution licensing agreement with an NSE/BSE-authorized market data vendor before displaying live/delayed quotes to paying users.
- [ ] **DPDP Act & GST Invoicing:** Implement Digital Personal Data Protection (DPDP) consent/deletion workflows and GST-compliant Razorpay invoicing for Indian subscribers.

### 3.2 United States (SEC / FINRA & Data Licensing)
- [ ] **Investment Advisers Act of 1940:** Obtain legal opinion on applicability of the bona fide publisher's exclusion (impersonal, regular schedule, non-tailored commentary) vs. RIA registration for US paid subscribers.
- [ ] **US Market Data Redistribution:** Execute commercial redistribution license (e.g., Polygon Business / Databento / exchange-licensed feed) for NASDAQ/NYSE quotes and bars. Never redistribute Yahoo Finance unofficial feeds.
- [ ] **SEC EDGAR & STOCK Act Attribution:** Maintain compliant `SEC_USER_AGENT` identification (<10 req/s) and retain mandatory 45-day disclosure lag notices on all Congressional PTR data (`trader-pelosi`).

### 3.3 Software Licensing & Disclosures
- [ ] Preserve `THIRD_PARTY_NOTICES` and `UPSTREAM.md` (MIT attribution for `Jakeschincariol/day-trader-skill`).
- [ ] Display required TradingView Lightweight Charts Apache-2.0 attribution in the dashboard footer/about section.
- [ ] Publish Terms of Service, Privacy Policy, Refund/Cancellation Policy, Historical Performance Methodology Disclosure, and prominent Non-Guarantee / Signals-Only Risk Disclosure.
