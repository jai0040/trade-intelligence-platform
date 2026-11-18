"""FastAPI dependency guards for active subscription and per-market entitlement enforcement."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from app.authentication.dependencies import AuthContext, get_current_auth
from app.core.errors import APIError


def require_active_subscription(
    market_code: str | None = None,
) -> Callable[[AuthContext], AuthContext]:
    """Require an active/trialing/grace-period subscription, optionally for a specific market."""
    required_market = market_code.upper() if market_code else None

    def _guard(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
        if not auth.is_entitled:
            raise APIError(
                status_code=403,
                code="SUBSCRIPTION_REQUIRED",
                message="An active subscription is required to access this feature.",
                details={"subscription_status": auth.subscription_status},
            )
        if required_market and required_market not in auth.entitled_markets:
            raise APIError(
                status_code=403,
                code="MARKET_NOT_ENTITLED",
                message=f"Your current subscription plan does not include the {required_market} market.",
                details={
                    "required_market": required_market,
                    "entitled_markets": auth.entitled_markets,
                },
            )
        return auth

    return _guard
