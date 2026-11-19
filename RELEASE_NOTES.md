# Release v1.0.0 — AI Trading Intelligence SaaS Platform

**Date:** November 19, 2026  
**Status:** Commercial Production-Ready Release  
**Repository:** `jai0040/trade-intelligence-platform`  
**License:** Proprietary SaaS (with vendored open-source attributions in `THIRD_PARTY_NOTICES`)

---

## Overview

The **AI Trading Intelligence SaaS Platform** is a commercial multi-market quantitative analysis and signal intelligence system designed for both Indian (NSE/BSE) and US (NASDAQ/NYSE) equity markets.

The system integrates 11 quantitative trading intelligence skills into a cohesive, test-gated SaaS architecture while strictly adhering to a **HARD-LOCKED SIGNALS-ONLY OPERATING POLICY**.

---

## Key Features & Capabilities

### 1. Dual Market Architecture (NSE/BSE + NASDAQ/NYSE)
- **Indian Equities:** Full support for 75 five-minute bars (`09:15–15:30 IST`), ₹0.01 tick rounding for sub-₹250 stocks, Muhurat trading override calendar, and NSE corporate filing news.
- **US Equities:** Full support for 78 five-minute bars (`09:30–16:00 ET`), exact DST rules, NYSE/NASDAQ holiday schedules, 13:00 ET early close calendars (42 bars), SEC EDGAR 8-K filings, and Congressional PTR disclosures.

### 2. Algorithmic Signal Engine & Quantitative Wrappers
- 11 stateless wrappers around unmodified core trading skills:
  - `ScannerSkillWrapper`: Daily High/Low and 5m Opening Range Breakout (ORB) scanning.
  - `NewsSkillWrapper`: High-impact corporate news filtering and deduplication.
  - `AnalystSkillWrapper`: Fundamental balance sheet and earnings gap risk assessment.
  - `EntrySkillWrapper` & `ExitSkillWrapper`: Deterministic entry, target, and stop-loss calculations supporting both BUY and SELL sides.
  - `TimeMachineSkillWrapper`: Monte Carlo simulation and 60-day historical pattern replay.
  - `BudgetSkillWrapper`: Risk-budgeted position sizing calculator.
  - `RiskSkillWrapper`: Mandatory, non-overridable risk validator.
  - `BrokerTicketSkillWrapper`: Read-only broker ticket generator hard-locked against live execution.
  - `AlertsSkillWrapper`: Real-time price threshold monitoring.
  - `PelosiSkillWrapper`: US Congressional PTR disclosure monitor with statutory 45-day filing lag notices.
- Centralized DAG Workflow Engine with distributed locks, exponential retries, and Global Emergency Kill Switch pre-checks.
- Calibrated Setup Quality Score (`0–100`) and net-of-cost outcome tracker (15 bps India / 8 bps US).

### 3. Subscriber Web Application (Next.js 15 App Router)
- **Interactive Candlestick Charts:** TradingView Lightweight Charts (Apache-2.0) with real-time entry, stop-loss, and target overlays.
- **11 Dedicated Views:** Overview Dashboard, India Market (NSE/BSE), US Market (NASDAQ/NYSE), Market Overview, Stock Scanner, Trading Opportunities, Stock Analysis & Charts, News & Disclosures, AI Analyst, Watchlists, and Notifications.
- **Personal Trading Journal:** Realized P&L calculations for long & short trades, psychological emotion tags, and performance statistics.
- **Real-Time Streaming:** Cookie-authenticated WebSockets with automatic reconnection, heartbeat, and single-session eviction notifications.
- **Dual Live Clocks:** Persistent IST and US-Eastern market clocks with session countdowns.

### 4. Enterprise Multi-Tenant SaaS, Auth & Single Active Session
- Argon2id password hashing, single-use SHA-256 password reset tokens with constant-time anti-enumeration.
- Server-side session store with Valkey/Redis integration.
- Single Active Session enforcement: supersedes prior sessions in real-time, closes superseded WebSockets (`4401`), and guarantees single-device subscription compliance.
- Double-submit CSRF protection on all state-changing endpoints.
- Role-Based Access Control (RBAC): `super_admin`, `admin`, `subscriber`.

### 5. Multi-Gateway Subscription Billing
- **Razorpay (INR):** Seamless recurring subscription billing for Indian subscribers, verified via constant-time HMAC-SHA256 signatures.
- **Stripe (USD):** Recurring subscription billing for US and global subscribers, verified via `Stripe-Signature` with timestamp freshness guards.
- **Deduplicated Webhooks:** Cryptographic idempotency via `PaymentEvent` table preventing duplicate charges or state corruption.
- **Grace Period Automation:** Preserves signal access during configured grace periods before revocation.

### 6. Security, Disaster Recovery & Compliance
- **Audit-Verified:** Zero hardcoded secrets, zero SQL injection risks, and 100% enforced SIGNALS-ONLY hard lock.
- **Disaster Recovery:** Automated Gzip database backups with SHA-256 integrity manifests and grandfather-father-son retention pruning.
- **Statutory Disclosures:** Comprehensive Terms of Service, Risk Disclosures, SEBI non-advisory technology status, SEC Publisher's Exclusion (*Lowe v. SEC*), and DPDP Act 2023 / GDPR tenant privacy provisions.

---

## Verification & Test Results
- All unit and integration test suites across Phases 3 through 10 passed with **100% success**.
