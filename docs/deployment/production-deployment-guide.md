# Production Deployment & Operations Guide

**Platform:** AI Trading Intelligence SaaS Platform  
**Target Environment:** Linux (Ubuntu 24.04 LTS / Debian 12 / AWS Linux 2023)  
**Security Profile:** Strict OWASP Top 10 Hardened, Non-Root Containers, Signals-Only Hard Lock

---

## 1. Production Architecture Overview

```
                                      [ Internet Clients ]
                                                │
                                                ▼
                          +───────────────────────────────────────────+
                          |      Edge CDN / Cloudflare WAF / DDoS     |
                          +───────────────────────────────────────────+
                                                │ HTTPS (TLS 1.3)
                                                ▼
                          +───────────────────────────────────────────+
                          |   Reverse Proxy (Caddy / Nginx)           |
                          |   - Automatic Let's Encrypt TLS           |
                          |   - Strict Security Headers & Rate Limits |
                          |   - WebSocket WSS Upgrade Proxy           |
                          +───────────────────────────────────────────+
                                         │             │
                    API & WebSockets (/api, /ws)       │ Web App Static (/)
                                         │             │
                                         ▼             ▼
          +────────────────────────────────────+   +───────────────────────+
          |  FastAPI Backend (Gunicorn/Uvicorn)|   | Next.js App Router UI |
          |  - 4-8 Async Workers (Non-Root)    |   | - Standalone Node.js  |
          |  - SIGNALS_ONLY Hard Lock Asserted |   | - Port 3000           |
          +────────────────────────────────────+   +───────────────────────+
                        │                 │
                        │ SQL Connections │ Redis Pub/Sub & Queues
                        ▼                 ▼
          +────────────────────────+   +───────────────────────────────────+
          | PostgreSQL 16 Cluster  |   | Valkey 8 / Redis Broker & State   |
          | - 31 Normalized Tables |   | - Database 0: Cache & Sessions    |
          | - PgBouncer Pooling    |   | - Database 1: Celery Broker       |
          | - WAL Archiving / PITR |   | - Database 2: Celery Results      |
          +────────────────────────+   +───────────────────────────────────+
                                                  ▲
                                                  │ Task Consumption
                                       +───────────────────────+
                                       | Celery Worker Cluster |
                                       | - queue: india_market |
                                       | - queue: us_market    |
                                       | - queue: analysis     |
                                       | - queue: notification |
                                       +───────────────────────+
```

---

## 2. Production Environment Configuration (`.env.production`)

```ini
# ==============================================================================
# TRADE INTELLIGENCE PLATFORM — PRODUCTION CONFIGURATION
# ==============================================================================

# Core Application
APP_ENV=production
APP_NAME=TradeIntelligencePlatform
APP_BASE_URL=https://tradeintel.example.com
API_BASE_URL=https://tradeintel.example.com
LOG_LEVEL=INFO

# HARD-LOCKED OPERATING POLICY (DO NOT ALTER)
TRADING_MODE=SIGNALS_ONLY

# Security & Secrets (Must be generated via 'openssl rand -hex 32')
SECRET_KEY=generate_via_openssl_rand_hex_32_in_production
FIELD_ENCRYPTION_KEY=generate_via_fernet_generate_key
SESSION_COOKIE_NAME=tip_session
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=lax
SESSION_TTL_HOURS=24
PASSWORD_RESET_TTL_MINUTES=15
CSRF_COOKIE_NAME=tip_csrf
CORS_ALLOWED_ORIGINS=https://tradeintel.example.com

# Persistence & Message Broker
DATABASE_URL=postgresql+psycopg://tip_prod_app:STRONGLY_GENERATED_PASSWORD@postgres:5432/trade_intelligence_prod
REDIS_URL=rediss://:REDIS_AUTH_TOKEN@valkey:6379/0
CELERY_BROKER_URL=rediss://:REDIS_AUTH_TOKEN@valkey:6379/1
CELERY_RESULT_BACKEND=rediss://:REDIS_AUTH_TOKEN@valkey:6379/2

# Licensed Commercial Market Data Providers (Mock & Yahoo blocked in production)
MARKET_DATA_PROVIDER_IN=commercial_in
MARKET_DATA_PROVIDER_US=commercial_us
QUOTE_STALE_THRESHOLD_SECONDS=900
SIGNAL_STALE_THRESHOLD_SECONDS=300

# Payment Gateways (Live Credentials)
RAZORPAY_KEY_ID=your_razorpay_key_id_here
RAZORPAY_KEY_SECRET=your_razorpay_key_secret_here
RAZORPAY_WEBHOOK_SECRET=your_razorpay_webhook_secret_here
STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key_here
STRIPE_SECRET_KEY=your_stripe_secret_key_here
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret_here
```

---

## 3. Pre-Flight Production Verification Checklist

1. [ ] **Signals-Only Verification:** `Settings.enforce_signals_only()` is confirmed active.
2. [ ] **HTTPS Enforced:** TLS 1.3 with HSTS (`max-age=63072000; includeSubDomains; preload`).
3. [ ] **Session & Cookie Security:** `SESSION_COOKIE_SECURE=true`, `HttpOnly=true`, and `SameSite=lax`.
4. [ ] **Double-Submit CSRF Verification:** Confirmed active on all mutation APIs.
5. [ ] **Single Active Session:** Real-time eviction confirmed across multi-device logins.
6. [ ] **Non-Root Execution:** All Docker containers run as unprivileged `appuser`.
7. [ ] **Database Connection Pooling:** PgBouncer configured with max 100 pooled connections.
8. [ ] **Automated Backups:** Daily cron active with SHA-256 verification and cloud sync.

---

## 4. Zero-Downtime Deployment Procedure

```bash
# 1. Pull latest verified release tag
git checkout tags/v1.0.0

# 2. Build release container images
docker compose -f docker/docker-compose.yml build

# 3. Apply Alembic database migrations
docker compose run --rm backend alembic upgrade head

# 4. Perform graceful rolling restart of API services
docker compose up -d --no-deps --scale backend=2 --no-recreate backend
docker compose stop backend_old
docker compose up -d worker celery_beat frontend

# 5. Execute live health smoke test
curl -f https://tradeintel.example.com/api/v1/health || exit 1
```
