"""Commercial India/US provider interfaces and strictly dev-only Yahoo fallback guard."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from data_providers.base import MarketDataProvider
from domain.errors import CommercialProviderPolicyError, ProviderUnavailableError
from domain.models import Instrument, MarketCode, OHLCVBar, QuoteSnapshot


class CommercialIndiaDataProvider(MarketDataProvider):
    """Commercial NSE/BSE redistribution-licensed provider interface (e.g., TrueData / GlobalDataFeeds).

    Fails closed with ProviderUnavailableError if commercial API credentials are not configured —
    never fabricates prices or silently falls back to unofficial endpoints.
    """

    provider_code = "licensed_india"
    is_commercial_licensed = True
    supported_markets = (MarketCode.IN,)

    def __init__(self, *, api_key: str = "", base_url: str = "") -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.strip()

    def _require_configured(self) -> None:
        if not self.api_key or not self.base_url:
            raise ProviderUnavailableError(
                self.provider_code,
                "Commercial India NSE/BSE market data credentials (INDIA_PROVIDER_API_KEY / base URL) "
                "are not configured. Configure a licensed vendor before enabling live India feeds.",
            )

    def get_universe(self, market_code: MarketCode) -> list[Instrument]:
        self._require_configured()
        raise ProviderUnavailableError(self.provider_code, "Vendor HTTP client transport not bound.")

    def get_quotes(
        self, instruments: list[Instrument], *, as_of_utc: datetime | None = None
    ) -> dict[str, QuoteSnapshot]:
        self._require_configured()
        raise ProviderUnavailableError(self.provider_code, "Vendor HTTP client transport not bound.")

    def get_bars(
        self,
        instrument: Instrument,
        timeframe: str,
        start_utc: datetime,
        end_utc: datetime,
    ) -> list[OHLCVBar]:
        self._require_configured()
        raise ProviderUnavailableError(self.provider_code, "Vendor HTTP client transport not bound.")

    def health_check(self) -> dict[str, Any]:
        configured = bool(self.api_key and self.base_url)
        return {
            "provider_code": self.provider_code,
            "is_commercial_licensed": True,
            "ok": configured,
            "detail": "configured" if configured else "credentials_not_configured",
        }


class CommercialUSDataProvider(MarketDataProvider):
    """Commercial US NASDAQ/NYSE redistribution-licensed provider interface (Polygon Business / Databento).

    Fails closed with ProviderUnavailableError if credentials are missing — never fabricates data.
    """

    provider_code = "licensed_us"
    is_commercial_licensed = True
    supported_markets = (MarketCode.US,)

    def __init__(self, *, api_key: str = "", base_url: str = "") -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.strip()

    def _require_configured(self) -> None:
        if not self.api_key or not self.base_url:
            raise ProviderUnavailableError(
                self.provider_code,
                "Commercial US NASDAQ/NYSE market data credentials (US_PROVIDER_API_KEY / base URL) "
                "are not configured. Configure Polygon Business / Databento before production launch.",
            )

    def get_universe(self, market_code: MarketCode) -> list[Instrument]:
        self._require_configured()
        raise ProviderUnavailableError(self.provider_code, "Vendor HTTP client transport not bound.")

    def get_quotes(
        self, instruments: list[Instrument], *, as_of_utc: datetime | None = None
    ) -> dict[str, QuoteSnapshot]:
        self._require_configured()
        raise ProviderUnavailableError(self.provider_code, "Vendor HTTP client transport not bound.")

    def get_bars(
        self,
        instrument: Instrument,
        timeframe: str,
        start_utc: datetime,
        end_utc: datetime,
    ) -> list[OHLCVBar]:
        self._require_configured()
        raise ProviderUnavailableError(self.provider_code, "Vendor HTTP client transport not bound.")

    def health_check(self) -> dict[str, Any]:
        configured = bool(self.api_key and self.base_url)
        return {
            "provider_code": self.provider_code,
            "is_commercial_licensed": True,
            "ok": configured,
            "detail": "configured" if configured else "credentials_not_configured",
        }


class DevYahooDataProvider(MarketDataProvider):
    """STRICTLY LOCAL-DEV-ONLY unofficial adapter — hard-blocked in production environments."""

    provider_code = "dev_yahoo"
    is_commercial_licensed = False
    supported_markets = (MarketCode.IN, MarketCode.US)

    def __init__(self, *, app_env: str = "development") -> None:
        if app_env.strip().lower() == "production":
            raise CommercialProviderPolicyError(
                "DevYahooDataProvider is strictly prohibited in production. "
                "Redistribution of unofficial Yahoo Finance feeds violates commercial terms."
            )
        self.app_env = app_env

    def get_universe(self, market_code: MarketCode) -> list[Instrument]:
        raise ProviderUnavailableError(
            self.provider_code,
            "Local dev Yahoo adapter requires explicit online fetch opt-in; use 'mock' for offline tests.",
        )

    def get_quotes(
        self, instruments: list[Instrument], *, as_of_utc: datetime | None = None
    ) -> dict[str, QuoteSnapshot]:
        raise ProviderUnavailableError(
            self.provider_code,
            "Local dev Yahoo adapter is disabled in offline mode; never fabricates prices.",
        )

    def get_bars(
        self,
        instrument: Instrument,
        timeframe: str,
        start_utc: datetime,
        end_utc: datetime,
    ) -> list[OHLCVBar]:
        raise ProviderUnavailableError(
            self.provider_code,
            "Local dev Yahoo adapter is disabled in offline mode; never fabricates prices.",
        )

    def health_check(self) -> dict[str, Any]:
        return {
            "provider_code": self.provider_code,
            "is_commercial_licensed": False,
            "ok": False,
            "detail": "local_dev_only_offline",
        }
