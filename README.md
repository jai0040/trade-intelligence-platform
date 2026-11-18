# AI Trading Intelligence — Multi-Market SaaS Platform

A production-oriented, multi-user, subscription-based AI Trading Intelligence SaaS platform supporting both the **Indian stock market (NSE / BSE)** and the **US stock market (NASDAQ / NYSE)**.

> **OPERATING MODE — STRICT SIGNALS-ONLY**
> This platform operates strictly in **SIGNALS-ONLY MODE**. It does **not** place, modify, or cancel live broker orders. All final trading decisions remain solely with the user. `trader-broker` is restricted to generating read-only, broker-ready trade tickets for manual inspection.

---

## Product Capabilities

- **Dual Independent Markets:** Native adapters for **India (`NSE`/`BSE`, `INR`, `Asia/Kolkata`, `09:15–15:30 IST`)** and **United States (`NASDAQ`/`NYSE`, `USD`, `America/New_York`, `09:30–16:00 ET`)**, backed by authoritative exchange calendars and pluggable licensed data provider interfaces.
- **11 Integrated Trading Skills:** Preserves and wraps the deterministic trading intelligence logic from `trader-scanner`, `trader-news`, `trader-analyst`, `trader-entry`, `trader-exit`, `trader-timemachine`, `trader-budget`, `trader-risk`, `trader-broker` (ticket-only), `trader-alerts`, and `trader-pelosi` (US-only).
- **Deterministic Math vs. AI Reasoning Separation:** All position sizing, stop-loss, target, R:R, expiry, and risk checks run in deterministic `Decimal` Python code. LLMs provide structured explanations and synthesis only and can never override a mandatory `trader-risk` rejection.
- **Multi-User SaaS & Single Active Session:** Strict `user_id` isolation for private watchlists, journals, preferences, alerts, and payments, plus database- and Redis-enforced **Single Active Session** per user with real-time WebSocket invalidation.
- **Dual-Gateway Subscriptions:** Razorpay (India / INR) and Stripe (International / USD) with cryptographically verified, idempotent webhook processing.
- **Super Admin Panel & Emergency Kill Switch:** Centralized administration, session revocation, provider health monitoring, workflow/skill audit logs, and an audited global emergency kill switch.

---

## Repository Structure

```text
trade-intelligence-platform/
├── frontend/                  # Next.js (App Router), TypeScript, Tailwind, shadcn/ui, Lightweight Charts
├── backend/                   # FastAPI REST API, WebSockets, Auth, Billing, Admin
├── trading-engine/
│   ├── skills/                # Preserved upstream 11 skills (vendored baseline)
│   ├── skill_wrappers/        # Typed service adapters around each skill
│   ├── domain/                # Canonical Instrument, OHLCVBar, QuoteSnapshot, Signal models
│   ├── adapters/              # Independent india/ and usa/ market adapters
│   ├── data_providers/        # Pluggable commercial provider interfaces + deterministic mocks
│   ├── signal_engine/         # BUY/SELL/WATCH generation & calibrated composite scoring
│   ├── risk_engine/           # Mandatory non-overridable deterministic risk gate
│   ├── ai_analyst/            # Decoupled LLM explanation service
│   ├── scheduler/             # Market-calendar-aware Celery Beat triggers
│   └── workflows/             # Idempotent DAG orchestration & skill execution logging
├── database/                  # SQLAlchemy 2.x models, Alembic migrations, seeds
├── tests/                     # Unit, integration, API, security, and frontend suites
├── docker/                    # Dockerfiles and Docker Compose definitions
└── docs/                      # Audit, architecture, API, DB schema, roadmap, security
```

---

## Documentation Index

- [Existing System Audit](docs/EXISTING_SYSTEM_AUDIT.md) — Phase 1 audit of the local setup, all 11 skills, India/US compatibility, and risks.
- [System Architecture Blueprint](docs/ARCHITECTURE.md) — High-level architecture, workflow DAG, auth/session model, and frontend design.
- [Database Schema Specification](docs/architecture/database-schema.md) — Complete normalized PostgreSQL 16 schema, constraints, indexes, and retention policy.
- [Skill Interfaces & Workflow Contracts](docs/architecture/skill-interfaces.md) — Python interfaces for Market Adapters, Data Providers, Skill Wrappers, and Risk Gate.
- [OpenAPI v1 Specification](docs/api/openapi.yaml) — REST API contract for subscriber, webhook, and Super Admin endpoints.
- [WebSocket Protocol Specification](docs/api/websockets.md) — Real-time stream events including instant single-session invalidation.
- [Security & Compliance Specification](docs/security/security-and-compliance.md) — Security controls, threat model, and SEBI/SEC/market-data compliance gates.
- [Development Roadmap](docs/DEVELOPMENT_ROADMAP.md) — 10-phase implementation plan and verification gates.
- [Upstream Provenance](UPSTREAM.md) & [Third-Party Notices](THIRD_PARTY_NOTICES) — Licensing and upstream isolation policy.

---

## Regulatory & Commercial Data Notice

This software is a financial information and trading intelligence platform. Before offering paid stock-specific recommendations or redistributing market data commercially, you must complete legal and regulatory review (including SEBI Research Analyst / Investment Adviser rules in India, US SEC/FINRA rules, and signed commercial redistribution agreements with licensed Indian and US market data vendors). Unofficial free feeds must never be used in commercial production.
