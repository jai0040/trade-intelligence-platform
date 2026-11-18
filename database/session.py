"""SQLAlchemy 2.x Engine and Session Factory shared by FastAPI Backend and Celery Workers."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is required. Copy .env.example to .env and configure PostgreSQL."
        )
    return url


def build_engine(database_url: str | None = None) -> Engine:
    return create_engine(
        database_url or get_database_url(),
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        future=True,
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def check_database_health(engine: Engine) -> tuple[bool, str]:
    """Run a lightweight SELECT 1 probe against PostgreSQL."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:  # pragma: no cover - integration failure path
        return False, str(exc)


def db_session_dependency(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
