# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/backend:/app/trading-engine

WORKDIR /app

RUN groupadd --system workergroup && useradd --system --gid workergroup --create-home workeruser

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/backend/requirements.txt

COPY database /app/database
COPY backend /app/backend
COPY trading-engine /app/trading-engine

RUN chown -R workeruser:workergroup /app
USER workeruser

CMD ["celery", "-A", "scheduler.celery_app:celery_app", "worker", "-l", "info", "-Q", "india_market,us_market,analysis,notifications,maintenance", "--concurrency=2"]
