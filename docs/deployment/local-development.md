# Local Development Runbook (Windows PowerShell)

This guide explains how to boot the full Phase 3 stack locally on Windows using either **Docker Compose (recommended)** or native virtual environments.

---

## 1. Environment Preparation

Copy `.env.example` to `.env` (never commit `.env`):

```powershell
Set-Location C:\Users\ADMIN\.gemini\antigravity\scratch\trade-intelligence-platform
Copy-Item .env.example .env
```

---

## 2. Recommended: Full Stack via Docker Compose

Install Docker Desktop if not installed yet:

```powershell
winget install Docker.DockerDesktop
```

Boot PostgreSQL 16, Valkey 8, FastAPI Backend, Celery Worker, Celery Beat, and Next.js Frontend:

```powershell
docker compose -f docker/docker-compose.yml up --build -d
```

Run Alembic database migrations and seed initial roles, markets (`IN`, `US`), exchanges (`NSE`, `BSE`, `NASDAQ`, `NYSE`), settings, and default plans:

```powershell
docker compose -f docker/docker-compose.yml exec backend alembic -c database/alembic.ini upgrade head
docker compose -f docker/docker-compose.yml exec backend python -m database.seeds.seed_initial
```

Verify health:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
```

Open the dashboard at `http://localhost:3000` and API docs at `http://localhost:8000/api/docs`.

---

## 3. Native Python Virtual Environment & Frontend Dev

Install Python 3.12 (recommended alongside Python 3.15 for full Windows binary wheel support):

```powershell
winget install Python.Python.3.12
```

Create a project virtual environment (never install packages globally):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Run backend & worker tests:

```powershell
$env:PYTHONPATH = ".;backend;trading-engine"
.\.venv\Scripts\pytest.exe tests/unit/
```

Run frontend locally:

```powershell
Set-Location frontend
npm install
npm run typecheck
npm run dev
```
