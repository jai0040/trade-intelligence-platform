"""Factory instantiating MarketDataProvider with mandatory production licensing enforcement."""

from __future__ import annotations

from typing import Any

from data_providers.base import MarketDataProvider
from data_providers.commercial_interfaces import (
    CommercialIndiaDataProvider,
    CommercialUSDataProvider,
    DevYahooDataProvider,
)
from data_providers.mock_provider import MockMarketDataProvider
from domain.errors import CommercialProviderPolicyError


def build_market_data_provider(
    provider_code: str,
    *,
    app_env: str = "development",
    **kwargs: Any,
) -> MarketDataProvider:
    """Build a MarketDataProvider and hard-block non-commercial providers in production."""
    code = provider_code.strip().lower()
    env = app_env.strip().lower()

    provider: MarketDataProvider
    if code == "mock":
        provider = MockMarketDataProvider(**kwargs)
    elif code in {"licensed_india", "kite", "upstox", "truedata"}:
        provider = CommercialIndiaDataProvider(**kwargs)
    elif code in {"licensed_us", "polygon", "databento", "alpaca"}:
        provider = CommercialUSDataProvider(**kwargs)
    elif code in {"dev_yahoo", "yahoo"}:
        provider = DevYahooDataProvider(app_env=env)
    else:
        raise ValueError(f"Unknown market data provider code: {provider_code!r}")

    if env == "production" and not provider.is_commercial_licensed:
        raise CommercialProviderPolicyError(
            f"Provider '{provider.provider_code}' is NOT commercially licensed and is prohibited in production."
        )
    return provider
