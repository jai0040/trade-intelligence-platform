"""AngelOne SmartAPI live market data provider for India NSE/BSE equities.

Official API: https://smartapi.angelbroking.com
Documentation: https://smartapi.angelbroking.com/docs
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import struct
import time
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from data_providers.base import MarketDataProvider
from domain.errors import ProviderUnavailableError
from domain.models import (
    AssetType,
    ExchangeCode,
    Instrument,
    MarketCode,
    OHLCVBar,
    QuoteSnapshot,
)

logger = logging.getLogger("trade_intelligence.angelone")

ANGELONE_BASE_URL = "https://apiconnect.angelbroking.com"

# Representative mapping of top liquid NSE equities to AngelOne symbol tokens
ANGELONE_NSE_SCRIP_TOKENS: dict[str, dict[str, Any]] = {
    "RELIANCE": {"token": "2885", "symbol": "RELIANCE-EQ", "name": "Reliance Industries Ltd.", "tick": Decimal("0.05")},
    "TCS": {"token": "11536", "symbol": "TCS-EQ", "name": "Tata Consultancy Services Ltd.", "tick": Decimal("0.05")},
    "INFY": {"token": "1594", "symbol": "INFY-EQ", "name": "Infosys Ltd.", "tick": Decimal("0.05")},
    "HDFCBANK": {"token": "1333", "symbol": "HDFCBANK-EQ", "name": "HDFC Bank Ltd.", "tick": Decimal("0.05")},
    "ICICIBANK": {"token": "4963", "symbol": "ICICIBANK-EQ", "name": "ICICI Bank Ltd.", "tick": Decimal("0.05")},
    "SBIN": {"token": "3045", "symbol": "SBIN-EQ", "name": "State Bank of India", "tick": Decimal("0.05")},
    "TATAMOTORS": {"token": "3456", "symbol": "TATAMOTORS-EQ", "name": "Tata Motors Ltd.", "tick": Decimal("0.05")},
    "BHARTIARTL": {"token": "10604", "symbol": "BHARTIARTL-EQ", "name": "Bharti Airtel Ltd.", "tick": Decimal("0.05")},
    "ITC": {"token": "1660", "symbol": "ITC-EQ", "name": "ITC Ltd.", "tick": Decimal("0.05")},
    "KOTAKBANK": {"token": "1922", "symbol": "KOTAKBANK-EQ", "name": "Kotak Mahindra Bank Ltd.", "tick": Decimal("0.05")},
    "LT": {"token": "11483", "symbol": "LT-EQ", "name": "Larsen & Toubro Ltd.", "tick": Decimal("0.05")},
    "AXISBANK": {"token": "5900", "symbol": "AXISBANK-EQ", "name": "Axis Bank Ltd.", "tick": Decimal("0.05")},
    "MARUTI": {"token": "10999", "symbol": "MARUTI-EQ", "name": "Maruti Suzuki India Ltd.", "tick": Decimal("0.05")},
    "BAJFINANCE": {"token": "317", "symbol": "BAJFINANCE-EQ", "name": "Bajaj Finance Ltd.", "tick": Decimal("0.05")},
    "ASIANPAINT": {"token": "236", "symbol": "ASIANPAINT-EQ", "name": "Asian Paints Ltd.", "tick": Decimal("0.05")},
    "TITAN": {"token": "3506", "symbol": "TITAN-EQ", "name": "Titan Company Ltd.", "tick": Decimal("0.05")},
    "WIPRO": {"token": "3787", "symbol": "WIPRO-EQ", "name": "Wipro Ltd.", "tick": Decimal("0.05")},
    "SUNPHARMA": {"token": "3351", "symbol": "SUNPHARMA-EQ", "name": "Sun Pharmaceutical Industries Ltd.", "tick": Decimal("0.05")},
}


def generate_totp_code(secret: str) -> str:
    """Generate 6-digit TOTP code using RFC 6238 without requiring third-party libraries."""
    cleaned = secret.strip().replace(" ", "").upper()
    missing_padding = len(cleaned) % 8
    if missing_padding:
        cleaned += "=" * (8 - missing_padding)
    key = base64.b32decode(cleaned, casefold=True)
    counter = int(time.time() // 30)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % 1000000).zfill(6)


class AngelOneSmartAPIProvider(MarketDataProvider):
    """Production-ready AngelOne SmartAPI client for Indian equities."""

    provider_code = "angelone"
    is_commercial_licensed = True
    supported_markets = (MarketCode.IN,)

    def __init__(
        self,
        *,
        api_key: str = "",
        client_code: str = "",
        pin: str = "",
        totp_secret: str = "",
        jwt_token: str = "",
    ) -> None:
        self.api_key = api_key.strip()
        self.client_code = client_code.strip()
        self.pin = pin.strip()
        self.totp_secret = totp_secret.strip()
        self.jwt_token = jwt_token.strip()
        self._cached_jwt: str | None = None
        self._jwt_expires_at: float = 0.0

    @property
    def is_configured(self) -> bool:
        return bool(self.jwt_token or (self.api_key and self.client_code and self.pin))

    def _get_auth_headers(self) -> dict[str, str]:
        token = self._ensure_jwt()
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "106.193.147.98",
            "X-MACAddress": "fe80::216e:6507:4b9c:9045",
            "X-PrivateKey": self.api_key,
            "Authorization": f"Bearer {token}",
        }

    def _ensure_jwt(self) -> str:
        """Authenticate with SmartAPI and cache the active JWT token."""
        if self.jwt_token:
            return self.jwt_token
        if self._cached_jwt and time.time() < self._jwt_expires_at:
            return self._cached_jwt

        if not (self.api_key and self.client_code and self.pin):
            raise ProviderUnavailableError(
                self.provider_code,
                "AngelOne credentials (ANGELONE_API_KEY, ANGELONE_CLIENT_CODE, ANGELONE_PIN) are not configured.",
            )

        totp = generate_totp_code(self.totp_secret) if self.totp_secret else ""
        payload = {
            "clientcode": self.client_code,
            "password": self.pin,
            "totp": totp,
        }

        url = f"{ANGELONE_BASE_URL}/rest/auth/partner/v1/loginByPassword"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "127.0.0.1",
                "X-ClientPublicIP": "106.193.147.98",
                "X-MACAddress": "fe80::216e:6507:4b9c:9045",
                "X-PrivateKey": self.api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise ProviderUnavailableError(
                self.provider_code, f"Failed to authenticate with AngelOne SmartAPI: {e}"
            ) from e

        if not data.get("status") or not data.get("data", {}).get("jwtToken"):
            msg = data.get("message", "Authentication rejected by AngelOne SmartAPI")
            raise ProviderUnavailableError(self.provider_code, f"AngelOne login failed: {msg}")

        jwt = str(data["data"]["jwtToken"])
        self._cached_jwt = jwt
        self._jwt_expires_at = time.time() + 3600 * 8  # 8 hours validity
        return jwt

    def get_universe(self, market_code: MarketCode) -> list[Instrument]:
        if market_code != MarketCode.IN:
            return []
        instruments: list[Instrument] = []
        for sym, meta in ANGELONE_NSE_SCRIP_TOKENS.items():
            instruments.append(
                Instrument(
                    instrument_id=f"in_{sym.lower()}",
                    market_code=MarketCode.IN,
                    exchange_code=ExchangeCode.NSE,
                    symbol=sym,
                    canonical_code=f"NSE:{sym}",
                    company_name=meta["name"],
                    asset_type=AssetType.EQUITY.value,
                    currency="INR",
                    tick_size=meta["tick"],
                    lot_size=1,
                    sector="Equity",
                    provider_symbols={
                        "angelone": meta["token"],
                        "angelone_symbol": meta["symbol"],
                    },
                )
            )
        return instruments

    def get_quotes(
        self, instruments: list[Instrument], *, as_of_utc: datetime | None = None
    ) -> dict[str, QuoteSnapshot]:
        headers = self._get_auth_headers()
        url = f"{ANGELONE_BASE_URL}/rest/secure/angelbroking/market/v1/quote/"
        now = datetime.now(timezone.utc)
        snapshots: dict[str, QuoteSnapshot] = {}

        # Collect tokens
        tokens_by_id = {
            inst.instrument_id: inst.provider_symbols.get("angelone")
            or ANGELONE_NSE_SCRIP_TOKENS.get(inst.symbol, {}).get("token")
            for inst in instruments
            if inst.market_code == MarketCode.IN
        }
        tokens = [t for t in tokens_by_id.values() if t]
        if not tokens:
            return {}

        payload = {"mode": "FULL", "exchangeTokens": {"NSE": tokens}}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise ProviderUnavailableError(
                self.provider_code, f"Failed to fetch quotes from AngelOne SmartAPI: {e}"
            ) from e

        items = data.get("data", {}).get("fetched", [])
        items_by_token = {str(item.get("symbolToken")): item for item in items}

        for inst in instruments:
            tok = tokens_by_id.get(inst.instrument_id)
            if not tok or tok not in items_by_token:
                continue
            item = items_by_token[tok]
            ltp = Decimal(str(item.get("ltp") or item.get("close") or "0"))
            prev_close = Decimal(str(item.get("close") or ltp))
            vol = int(item.get("tradeVolume") or item.get("volume") or 0)
            if ltp <= Decimal("0"):
                continue

            snapshots[inst.instrument_id] = QuoteSnapshot(
                instrument_id=inst.instrument_id,
                last_price=ltp,
                prev_close=prev_close,
                volume=vol,
                quote_timestamp_utc=now,
                fetched_at_utc=now,
                source_provider=self.provider_code,
                is_delayed=False,
                delay_seconds=0,
            )

        return snapshots

    def get_bars(
        self,
        instrument: Instrument,
        timeframe: str,
        start_utc: datetime,
        end_utc: datetime,
    ) -> list[OHLCVBar]:
        headers = self._get_auth_headers()
        url = f"{ANGELONE_BASE_URL}/rest/secure/angelbroking/historical/v1/getCandleData"
        tok = instrument.provider_symbols.get("angelone") or ANGELONE_NSE_SCRIP_TOKENS.get(
            instrument.symbol, {}
        ).get("token")
        if not tok:
            raise ProviderUnavailableError(
                self.provider_code, f"No AngelOne token mapped for instrument {instrument.symbol}"
            )

        interval_map = {
            "1m": "ONE_MINUTE",
            "5m": "FIVE_MINUTE",
            "15m": "FIFTEEN_MINUTE",
            "1d": "ONE_DAY",
        }
        angel_interval = interval_map.get(timeframe, "FIVE_MINUTE")

        # Format dates in IST
        from_str = start_utc.strftime("%Y-%m-%d %H:%M")
        to_str = end_utc.strftime("%Y-%m-%d %H:%M")

        payload = {
            "exchange": "NSE",
            "symboltoken": tok,
            "interval": angel_interval,
            "fromdate": from_str,
            "todate": to_str,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise ProviderUnavailableError(
                self.provider_code, f"Failed to fetch historical candles from AngelOne: {e}"
            ) from e

        candles = data.get("data") or []
        bars: list[OHLCVBar] = []
        now = datetime.now(timezone.utc)

        for row in candles:
            # Expected format: [timestamp_iso_string, open, high, low, close, volume]
            if len(row) < 6:
                continue
            try:
                # Timestamp parsing
                ts_str = row[0]
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)

                o, h, l, c = (
                    Decimal(str(row[1])),
                    Decimal(str(row[2])),
                    Decimal(str(row[3])),
                    Decimal(str(row[4])),
                )
                v = int(row[5])
                if l <= Decimal("0") or h < max(o, c) or l > min(o, c):
                    continue

                bars.append(
                    OHLCVBar(
                        instrument_id=instrument.instrument_id,
                        timeframe=timeframe,
                        bar_start_utc=dt,
                        bar_end_utc=dt,  # Completed bar point
                        open=o,
                        high=h,
                        low=l,
                        close=c,
                        volume=v,
                        is_complete=True,
                        source_provider=self.provider_code,
                        fetched_at_utc=now,
                    )
                )
            except Exception:
                continue

        return bars

    def health_check(self) -> dict[str, Any]:
        return {
            "provider_code": self.provider_code,
            "is_commercial_licensed": True,
            "configured": self.is_configured,
            "detail": "ready" if self.is_configured else "credentials_not_configured",
        }
