"""FastAPI application entrypoint with security headers, CORS allowlist, routers, and clean lifespan."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine
from sqlalchemy.orm import Session as DbSession, sessionmaker

from app.admin.router import router as admin_router
from app.api.v1.health import router as health_router
from app.authentication.router import router as auth_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.redis import build_redis_client
from app.journal.router import router as journal_router
from app.markets.router import router as markets_router
from app.notifications.router import router as notifications_router
from app.realtime.router import router as realtime_router
from app.realtime.ws_manager import WebSocketManager
from app.signals.router import router as signals_router
from app.signals.service import SignalsEngineHub
from app.subscriptions.router import router as subscriptions_router
from app.users.router import router as users_router
from data_providers.base import MarketDataProvider
from data_providers.factory import build_market_data_provider
from data_providers.freshness import ProviderHealthMonitor
from database.session import build_engine, build_session_factory
from domain.models import MarketCode

logger = logging.getLogger("trade_intelligence.api")


def create_app(
    settings: Settings | None = None,
    *,
    db_engine: Engine | None = None,
    db_session_factory: sessionmaker[DbSession] | None = None,
    redis_client: Any | None = None,
    market_providers: dict[MarketCode, MarketDataProvider] | None = None,
) -> FastAPI:
    cfg = settings or get_settings()
    configure_logging(cfg.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owns_engine = db_engine is None and db_session_factory is None
        owns_redis = redis_client is None

        app.state.settings = cfg
        if not hasattr(app.state, "ws_manager") or app.state.ws_manager is None:
            app.state.ws_manager = WebSocketManager()
        app.state.provider_health_monitor = ProviderHealthMonitor()
        app.state.signals_hub = SignalsEngineHub(llm_provider=cfg.llm_provider)
        app.state.market_providers = market_providers or {
            MarketCode.IN: build_market_data_provider(
                cfg.market_data_provider_in, app_env=cfg.app_env
            ),
            MarketCode.US: build_market_data_provider(
                cfg.market_data_provider_us, app_env=cfg.app_env
            ),
        }
        app.state.db_engine = db_engine or build_engine(cfg.database_url)
        app.state.db_session_factory = db_session_factory or build_session_factory(
            app.state.db_engine
        )
        app.state.redis_client = (
            redis_client if redis_client is not None else build_redis_client(cfg.redis_url)
        )

        logger.info(
            "Backend starting",
            extra={
                "context": {
                    "env": cfg.app_env,
                    "trading_mode": cfg.trading_mode,
                    "provider_in": cfg.market_data_provider_in,
                    "provider_us": cfg.market_data_provider_us,
                }
            },
        )
        try:
            yield
        finally:
            if owns_engine and app.state.db_engine is not None:
                app.state.db_engine.dispose()
            if owns_redis and app.state.redis_client is not None:
                close_fn = getattr(app.state.redis_client, "close", None)
                if callable(close_fn):
                    close_fn()
            logger.info("Backend shut down cleanly")

    app = FastAPI(
        title="AI Trading Intelligence SaaS Platform API",
        version="0.2.0",
        description=(
            "Multi-Market (India NSE/BSE & US NASDAQ/NYSE) Signals-Only "
            "Trading Intelligence SaaS Platform."
        ),
        docs_url="/api/docs" if cfg.app_env != "production" else None,
        redoc_url="/api/redoc" if cfg.app_env != "production" else None,
        lifespan=lifespan,
    )

    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )

    @app.middleware("http")
    async def security_and_correlation_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Trading-Mode"] = cfg.trading_mode
        if cfg.app_env == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(subscriptions_router, prefix="/api/v1")
    app.include_router(markets_router, prefix="/api/v1")
    app.include_router(signals_router, prefix="/api/v1")
    app.include_router(journal_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(realtime_router)
    return app


app = create_app()
