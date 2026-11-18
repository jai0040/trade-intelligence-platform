"""FastAPI application entrypoint with security headers, CORS allowlist, and clean lifespan."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.redis import build_redis_client
from database.session import build_engine, build_session_factory

logger = logging.getLogger("trade_intelligence.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    configure_logging(cfg.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = cfg
        app.state.db_engine = build_engine(cfg.database_url)
        app.state.db_session_factory = build_session_factory(app.state.db_engine)
        app.state.redis_client = build_redis_client(cfg.redis_url)
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
            app.state.db_engine.dispose()
            app.state.redis_client.close()
            logger.info("Backend shut down cleanly")

    app = FastAPI(
        title="AI Trading Intelligence SaaS Platform API",
        version="0.1.0",
        description="Multi-Market (India NSE/BSE & US NASDAQ/NYSE) Signals-Only Trading Intelligence Platform.",
        docs_url="/api/docs" if cfg.app_env != "production" else None,
        redoc_url="/api/redoc" if cfg.app_env != "production" else None,
        lifespan=lifespan,
    )

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
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response

    app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()
