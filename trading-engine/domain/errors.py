"""Domain exception hierarchy for market adapters, providers, and Signals-Only enforcement."""

from __future__ import annotations


class TradingEngineError(Exception):
    """Base exception for deterministic trading engine domain failures."""


class SignalsOnlyPolicyError(TradingEngineError):
    """Raised if any code attempts live broker order placement under SIGNALS_ONLY mode."""


class SymbolValidationError(TradingEngineError):
    """Raised when an instrument symbol violates exchange-specific ticker rules."""


class CommercialProviderPolicyError(TradingEngineError):
    """Raised when a non-commercial or mock data provider is selected in production."""


class ProviderUnavailableError(TradingEngineError):
    """Raised when a market data provider fails or is unconfigured (never fabricates prices)."""

    def __init__(self, provider_code: str, reason: str) -> None:
        super().__init__(f"Provider '{provider_code}' unavailable: {reason}")
        self.provider_code = provider_code
        self.reason = reason


class StaleDataError(TradingEngineError):
    """Raised when quote or bar data exceeds configured staleness thresholds."""

    def __init__(self, provider_code: str, age_seconds: int, threshold_seconds: int) -> None:
        super().__init__(
            f"Stale data from '{provider_code}': age={age_seconds}s exceeds limit={threshold_seconds}s"
        )
        self.provider_code = provider_code
        self.age_seconds = age_seconds
        self.threshold_seconds = threshold_seconds
