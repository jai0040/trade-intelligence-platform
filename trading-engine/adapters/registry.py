"""Singleton registry returning the appropriate MarketAdapter for IN or US."""

from __future__ import annotations

from adapters.base import MarketAdapter
from adapters.india.adapter import IndiaMarketAdapter
from adapters.usa.adapter import USMarketAdapter
from domain.models import MarketCode

_ADAPTERS: dict[MarketCode, MarketAdapter] = {
    MarketCode.IN: IndiaMarketAdapter(),
    MarketCode.US: USMarketAdapter(),
}


def get_market_adapter(market_code: MarketCode | str) -> MarketAdapter:
    code = market_code if isinstance(market_code, MarketCode) else MarketCode(market_code.upper())
    return _ADAPTERS[code]
