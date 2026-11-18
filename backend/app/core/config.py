"""Application settings with mandatory Signals-Only and commercial provider guardrails."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = "TradeIntelligencePlatform"
    app_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"

    # HARD-LOCKED OPERATING POLICY
    trading_mode: str = "SIGNALS_ONLY"

    # Security
    secret_key: str = Field(default="dev-only-insecure-placeholder-replace-me")
    field_encryption_key: str = Field(default="")
    session_cookie_name: str = "tip_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_ttl_hours: int = 24
    csrf_cookie_name: str = "tip_csrf"
    cors_allowed_origins: str = "http://localhost:3000"

    # Persistence & Broker
    database_url: str = "postgresql+psycopg://tip_app:replace_me@localhost:5432/trade_intelligence"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Market Data Providers
    market_data_provider_in: str = "mock"
    market_data_provider_us: str = "mock"
    quote_stale_threshold_seconds: int = 900
    signal_stale_threshold_seconds: int = 300

    # AI Analyst
    llm_provider: str = "mock"

    @field_validator("trading_mode")
    @classmethod
    def enforce_signals_only(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized != "SIGNALS_ONLY":
            raise ValueError(
                "TRADING_MODE is hard-locked to 'SIGNALS_ONLY'. Automated live broker execution is prohibited."
            )
        return normalized

    @model_validator(mode="after")
    def enforce_production_guardrails(self) -> Settings:
        if self.app_env == "production":
            if not self.session_cookie_secure:
                raise ValueError("SESSION_COOKIE_SECURE must be True in production.")
            if "placeholder" in self.secret_key.lower() or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be a strong >=32-char secret in production.")
            for field_name, provider in (
                ("MARKET_DATA_PROVIDER_IN", self.market_data_provider_in),
                ("MARKET_DATA_PROVIDER_US", self.market_data_provider_us),
            ):
                if provider.lower() in {"dev_yahoo", "yahoo", "mock"}:
                    raise ValueError(
                        f"{field_name}='{provider}' is prohibited in production; configure a licensed commercial provider."
                    )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
