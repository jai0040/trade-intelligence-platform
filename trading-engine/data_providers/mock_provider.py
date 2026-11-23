"""Deterministic offline MockMarketDataProvider for 24/7 India & US testing and local development."""

from __future__ import annotations

import hashlib
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from adapters.registry import get_market_adapter
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

# Deterministic namespace UUID so instrument_id values are stable across restarts and tests
_NS_INSTRUMENT = uuid.UUID("a3e41200-4a8b-4f10-9c5d-8842a0011200")


def _det_id(canonical_code: str) -> str:
    return str(uuid.uuid5(_NS_INSTRUMENT, canonical_code))


def _seed_float(key: str) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


# Curated India (NSE/BSE) & US (NASDAQ/NYSE) fixtures with realistic price/volatility/setup profiles
_FIXTURE_SPECS: list[dict[str, Any]] = [
    # --- INDIA NSE EQUITIES, ETFs & INDICES ---
    {
        "market": MarketCode.IN,
        "exchange": ExchangeCode.NSE,
        "symbol": "RELIANCE",
        "name": "Reliance Industries Limited",
        "asset_type": AssetType.EQUITY.value,
        "sector": "Energy",
        "base_price": Decimal("1375.00"),
        "tick": Decimal("0.05"),
        "pattern": "breakout",
        "base_vol": 420_000,
    },
    {
        "market": MarketCode.IN,
        "exchange": ExchangeCode.NSE,
        "symbol": "TCS",
        "name": "Tata Consultancy Services Limited",
        "asset_type": AssetType.EQUITY.value,
        "sector": "IT Services",
        "base_price": Decimal("4125.00"),
        "tick": Decimal("0.05"),
        "pattern": "bull_flag",
        "base_vol": 210_000,
    },
    {
        "market": MarketCode.IN,
        "exchange": ExchangeCode.NSE,
        "symbol": "HDFCBANK",
        "name": "HDFC Bank Limited",
        "asset_type": AssetType.EQUITY.value,
        "sector": "Banking",
        "base_price": Decimal("1745.00"),
        "tick": Decimal("0.05"),
        "pattern": "reclaim",
        "base_vol": 680_000,
    },
    {
        "market": MarketCode.IN,
        "exchange": ExchangeCode.NSE,
        "symbol": "INFY",
        "name": "Infosys Limited",
        "asset_type": AssetType.EQUITY.value,
        "sector": "IT Services",
        "base_price": Decimal("1890.00"),
        "tick": Decimal("0.05"),
        "pattern": "oversold_bounce",
        "base_vol": 390_000,
    },
    {
        "market": MarketCode.IN,
        "exchange": ExchangeCode.NSE,
        "symbol": "ICICIBANK",
        "name": "ICICI Bank Limited",
        "asset_type": AssetType.EQUITY.value,
        "sector": "Banking",
        "base_price": Decimal("1295.00"),
        "tick": Decimal("0.05"),
        "pattern": "breakout",
        "base_vol": 550_000,
    },
    {
        "market": MarketCode.IN,
        "exchange": ExchangeCode.NSE,
        "symbol": "M&M",
        "name": "Mahindra & Mahindra Limited",
        "asset_type": AssetType.EQUITY.value,
        "sector": "Automotive",
        "base_price": Decimal("3015.00"),
        "tick": Decimal("0.05"),
        "pattern": "breakout",
        "base_vol": 260_000,
    },
    {
        "market": MarketCode.IN,
        "exchange": ExchangeCode.NSE,
        "symbol": "BAJAJ-AUTO",
        "name": "Bajaj Auto Limited",
        "asset_type": AssetType.EQUITY.value,
        "sector": "Automotive",
        "base_price": Decimal("9850.00"),
        "tick": Decimal("0.05"),
        "pattern": "breakdown",
        "base_vol": 95_000,
    },
    {
        "market": MarketCode.IN,
        "exchange": ExchangeCode.NSE,
        "symbol": "SBIN",
        "name": "State Bank of India",
        "asset_type": AssetType.EQUITY.value,
        "sector": "Banking",
        "base_price": Decimal("842.50"),
        "tick": Decimal("0.05"),
        "pattern": "bull_flag",
        "base_vol": 720_000,
    },
    {
        "market": MarketCode.IN,
        "exchange": ExchangeCode.NSE,
        "symbol": "NIFTYBEES",
        "name": "Nippon India ETF Nifty 50 BeES",
        "asset_type": AssetType.ETF.value,
        "sector": "Broad Market ETF",
        "base_price": Decimal("274.20"),
        "tick": Decimal("0.05"),
        "pattern": "reclaim",
        "base_vol": 1_100_000,
    },
    {
        "market": MarketCode.IN,
        "exchange": ExchangeCode.NSE,
        "symbol": "NIFTY50",
        "name": "NIFTY 50 Index",
        "asset_type": AssetType.INDEX.value,
        "sector": "Benchmark Index",
        "base_price": Decimal("24485.00"),
        "tick": Decimal("0.05"),
        "pattern": "reclaim",
        "base_vol": 0,
    },
    {
        "market": MarketCode.IN,
        "exchange": ExchangeCode.BSE,
        "symbol": "SENSEX",
        "name": "BSE SENSEX Index",
        "asset_type": AssetType.INDEX.value,
        "sector": "Benchmark Index",
        "base_price": Decimal("80320.00"),
        "tick": Decimal("0.05"),
        "pattern": "reclaim",
        "base_vol": 0,
    },
    {
        "market": MarketCode.IN,
        "exchange": ExchangeCode.NSE,
        "symbol": "BANKNIFTY",
        "name": "NIFTY Bank Index",
        "asset_type": AssetType.INDEX.value,
        "sector": "Benchmark Index",
        "base_price": Decimal("52140.00"),
        "tick": Decimal("0.05"),
        "pattern": "breakout",
        "base_vol": 0,
    },
    # --- US NASDAQ/NYSE EQUITIES, ETFs & INDICES ---
    {
        "market": MarketCode.US,
        "exchange": ExchangeCode.NASDAQ,
        "symbol": "TSLA",
        "name": "Tesla, Inc.",
        "asset_type": AssetType.EQUITY.value,
        "sector": "Automotive",
        "base_price": Decimal("362.00"),
        "tick": Decimal("0.01"),
        "pattern": "breakout",
        "base_vol": 1_800_000,
    },
    {
        "market": MarketCode.US,
        "exchange": ExchangeCode.NASDAQ,
        "symbol": "NVDA",
        "name": "NVIDIA Corporation",
        "asset_type": AssetType.EQUITY.value,
        "sector": "Semiconductors",
        "base_price": Decimal("144.50"),
        "tick": Decimal("0.01"),
        "pattern": "bull_flag",
        "base_vol": 3_400_000,
    },
    {
        "market": MarketCode.US,
        "exchange": ExchangeCode.NASDAQ,
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "asset_type": AssetType.EQUITY.value,
        "sector": "Technology",
        "base_price": Decimal("234.80"),
        "tick": Decimal("0.01"),
        "pattern": "reclaim",
        "base_vol": 1_500_000,
    },
    {
        "market": MarketCode.US,
        "exchange": ExchangeCode.NASDAQ,
        "symbol": "MSFT",
        "name": "Microsoft Corporation",
        "asset_type": AssetType.EQUITY.value,
        "sector": "Technology",
        "base_price": Decimal("428.00"),
        "tick": Decimal("0.01"),
        "pattern": "breakout",
        "base_vol": 920_000,
    },
    {
        "market": MarketCode.US,
        "exchange": ExchangeCode.NYSE,
        "symbol": "BRK.B",
        "name": "Berkshire Hathaway Inc. Class B",
        "asset_type": AssetType.EQUITY.value,
        "sector": "Financials",
        "base_price": Decimal("468.25"),
        "tick": Decimal("0.01"),
        "pattern": "reclaim",
        "base_vol": 410_000,
    },
    {
        "market": MarketCode.US,
        "exchange": ExchangeCode.NYSE,
        "symbol": "JPM",
        "name": "JPMorgan Chase & Co.",
        "asset_type": AssetType.EQUITY.value,
        "sector": "Banking",
        "base_price": Decimal("241.60"),
        "tick": Decimal("0.01"),
        "pattern": "oversold_bounce",
        "base_vol": 620_000,
    },
    {
        "market": MarketCode.US,
        "exchange": ExchangeCode.NASDAQ,
        "symbol": "AMD",
        "name": "Advanced Micro Devices, Inc.",
        "asset_type": AssetType.EQUITY.value,
        "sector": "Semiconductors",
        "base_price": Decimal("452.40"),
        "tick": Decimal("0.01"),
        "pattern": "breakdown",
        "base_vol": 1_250_000,
    },
    {
        "market": MarketCode.US,
        "exchange": ExchangeCode.NYSE,
        "symbol": "SPY",
        "name": "SPDR S&P 500 ETF Trust",
        "asset_type": AssetType.ETF.value,
        "sector": "Benchmark ETF",
        "base_price": Decimal("594.20"),
        "tick": Decimal("0.01"),
        "pattern": "reclaim",
        "base_vol": 2_900_000,
    },
    {
        "market": MarketCode.US,
        "exchange": ExchangeCode.NASDAQ,
        "symbol": "QQQ",
        "name": "Invesco QQQ Trust",
        "asset_type": AssetType.ETF.value,
        "sector": "Benchmark ETF",
        "base_price": Decimal("508.75"),
        "tick": Decimal("0.01"),
        "pattern": "breakout",
        "base_vol": 2_100_000,
    },
    {
        "market": MarketCode.US,
        "exchange": ExchangeCode.NYSE,
        "symbol": "DIA",
        "name": "SPDR Dow Jones Industrial Average ETF Trust",
        "asset_type": AssetType.ETF.value,
        "sector": "Benchmark ETF",
        "base_price": Decimal("437.60"),
        "tick": Decimal("0.01"),
        "pattern": "reclaim",
        "base_vol": 520_000,
    },
]


class MockMarketDataProvider(MarketDataProvider):
    """Deterministic offline provider supporting 24/7 development, backtests, and outage simulations."""

    provider_code = "mock"
    is_commercial_licensed = False
    supported_markets = (MarketCode.IN, MarketCode.US)

    def __init__(
        self,
        *,
        simulate_outage: bool = False,
        outage_reason: str = "Simulated provider outage",
        simulated_delay_seconds: int = 2,
    ) -> None:
        self.simulate_outage = simulate_outage
        self.outage_reason = outage_reason
        self.simulated_delay_seconds = max(0, simulated_delay_seconds)
        self._instruments: dict[str, Instrument] = {}
        self._specs_by_id: dict[str, dict[str, Any]] = {}

        for spec in _FIXTURE_SPECS:
            market: MarketCode = spec["market"]
            exchange: ExchangeCode = spec["exchange"]
            symbol: str = spec["symbol"]
            canonical = f"{exchange.value}:{symbol}"
            inst_id = _det_id(canonical)
            currency = "INR" if market == MarketCode.IN else "USD"
            yahoo_sym = (
                f"{symbol}.NS"
                if exchange == ExchangeCode.NSE
                else f"{symbol}.BO"
                if exchange == ExchangeCode.BSE
                else symbol.replace(".", "-")
            )
            inst = Instrument(
                instrument_id=inst_id,
                market_code=market,
                exchange_code=exchange,
                symbol=symbol,
                canonical_code=canonical,
                company_name=spec["name"],
                asset_type=spec["asset_type"],
                currency=currency,
                tick_size=spec["tick"],
                lot_size=1,
                sector=spec["sector"],
                provider_symbols={"mock": canonical, "dev_yahoo": yahoo_sym},
            )
            self._instruments[inst_id] = inst
            self._specs_by_id[inst_id] = spec

    def _check_outage(self) -> None:
        if self.simulate_outage:
            raise ProviderUnavailableError(self.provider_code, self.outage_reason)

    def get_universe(self, market_code: MarketCode) -> list[Instrument]:
        self._check_outage()
        return [
            inst for inst in self._instruments.values() if inst.market_code == market_code
        ]

    def get_instrument_by_code(self, canonical_code: str) -> Instrument | None:
        return self._instruments.get(_det_id(canonical_code.upper()))

    def get_quotes(
        self, instruments: list[Instrument], *, as_of_utc: datetime | None = None
    ) -> dict[str, QuoteSnapshot]:
        self._check_outage()
        now = (
            datetime.now(timezone.utc)
            if as_of_utc is None
            else (as_of_utc.replace(tzinfo=timezone.utc) if as_of_utc.tzinfo is None else as_of_utc.astimezone(timezone.utc))
        )
        quote_ts = now - timedelta(seconds=self.simulated_delay_seconds)
        results: dict[str, QuoteSnapshot] = {}

        for inst in instruments:
            spec = self._specs_by_id.get(inst.instrument_id)
            if spec is None:
                continue
            adapter = get_market_adapter(inst.market_code)
            base: Decimal = spec["base_price"]
            pattern: str = spec["pattern"]
            drift_pct = {
                "breakout": Decimal("0.0185"),
                "bull_flag": Decimal("0.0110"),
                "reclaim": Decimal("0.0065"),
                "oversold_bounce": Decimal("0.0090"),
                "breakdown": Decimal("-0.0175"),
            }.get(pattern, Decimal("0.0025"))

            prev_close = adapter.round_to_tick(base, inst, "nearest")
            last_price = adapter.round_to_tick(base * (Decimal("1") + drift_pct), inst, "nearest")
            results[inst.instrument_id] = QuoteSnapshot(
                instrument_id=inst.instrument_id,
                last_price=last_price,
                prev_close=prev_close,
                volume=int(spec["base_vol"] * 1.45),
                quote_timestamp_utc=quote_ts,
                fetched_at_utc=now,
                source_provider=self.provider_code,
                is_delayed=self.simulated_delay_seconds > 0,
                delay_seconds=self.simulated_delay_seconds,
            )
        return results

    def _generate_daily_bars(
        self,
        instrument: Instrument,
        spec: dict[str, Any],
        start_utc: datetime,
        end_utc: datetime,
    ) -> list[OHLCVBar]:
        adapter = get_market_adapter(instrument.market_code)
        tz = adapter.local_timezone()
        start_d = start_utc.astimezone(tz).date()
        end_d = end_utc.astimezone(tz).date()
        trading_dates: list[date] = []
        cursor = start_d
        while cursor <= end_d:
            sess = adapter.get_session_window(instrument.exchange_code, cursor)
            if sess.is_trading_day and sess.open_utc is not None and sess.close_utc is not None:
                trading_dates.append(cursor)
            cursor += timedelta(days=1)

        if not trading_dates:
            return []

        base = float(spec["base_price"])
        pattern = str(spec["pattern"])
        base_vol = int(spec["base_vol"])
        n = len(trading_dates)
        bars: list[OHLCVBar] = []
        fetched_at = datetime.now(timezone.utc)

        prev_close_f = base * 0.96
        for idx, d in enumerate(trading_dates):
            sess = adapter.get_session_window(instrument.exchange_code, d)
            assert sess.open_utc is not None and sess.close_utc is not None
            r = _seed_float(f"{instrument.canonical_code}:1d:{d.isoformat()}")
            wave = math.sin(idx / 5.0) * 0.006 + (r - 0.5) * 0.008

            # Shape final 5 bars cleanly according to the configured deterministic setup pattern
            days_from_end = (n - 1) - idx
            if pattern == "breakout" and days_from_end == 0:
                move = 0.028
                vol_mult = 2.1
            elif pattern == "breakdown" and days_from_end == 0:
                move = -0.026
                vol_mult = 1.9
            elif pattern == "bull_flag":
                if 3 <= days_from_end <= 6:
                    move = 0.015
                    vol_mult = 1.6
                elif days_from_end in (1, 2):
                    move = -0.004
                    vol_mult = 0.8
                elif days_from_end == 0:
                    move = 0.012
                    vol_mult = 1.5
                else:
                    move = wave
                    vol_mult = 1.0
            elif pattern == "oversold_bounce":
                if 2 <= days_from_end <= 5:
                    move = -0.016
                    vol_mult = 1.2
                elif days_from_end == 0:
                    move = 0.019
                    vol_mult = 1.7
                else:
                    move = wave
                    vol_mult = 1.0
            else:
                move = wave + (0.006 if days_from_end == 0 else 0.001)
                vol_mult = 1.2 if days_from_end == 0 else 1.0

            open_f = prev_close_f * (1.0 + (r - 0.5) * 0.003)
            close_f = max(1.0, open_f * (1.0 + move))
            high_f = max(open_f, close_f) * (1.0 + 0.004 + r * 0.004)
            low_f = max(0.5, min(open_f, close_f) * (1.0 - 0.004 - (1.0 - r) * 0.004))

            open_d = adapter.round_to_tick(Decimal(str(open_f)), instrument, "nearest")
            close_d = adapter.round_to_tick(Decimal(str(close_f)), instrument, "nearest")
            high_d = max(open_d, close_d, adapter.round_to_tick(Decimal(str(high_f)), instrument, "up"))
            low_d = min(open_d, close_d, adapter.round_to_tick(Decimal(str(low_f)), instrument, "down"))
            low_d = max(instrument.tick_size, low_d)

            bars.append(
                OHLCVBar(
                    instrument_id=instrument.instrument_id,
                    timeframe="1d",
                    bar_start_utc=sess.open_utc,
                    bar_end_utc=sess.close_utc,
                    open=open_d,
                    high=high_d,
                    low=low_d,
                    close=close_d,
                    volume=max(0, int(base_vol * vol_mult * (0.85 + r * 0.3))),
                    is_complete=True,
                    source_provider=self.provider_code,
                    fetched_at_utc=fetched_at,
                )
            )
            prev_close_f = float(close_d)

        return bars

    def _generate_intraday_bars(
        self,
        instrument: Instrument,
        spec: dict[str, Any],
        timeframe: str,
        start_utc: datetime,
        end_utc: datetime,
    ) -> list[OHLCVBar]:
        step_minutes = {"1m": 1, "5m": 5, "15m": 15}[timeframe]
        adapter = get_market_adapter(instrument.market_code)
        tz = adapter.local_timezone()

        start_d = start_utc.astimezone(tz).date()
        end_d = end_utc.astimezone(tz).date()
        base = float(spec["base_price"])
        pattern = str(spec["pattern"])
        per_bar_vol = max(100, int(spec["base_vol"] / max(1, (375 // step_minutes))))
        fetched_at = datetime.now(timezone.utc)

        bars: list[OHLCVBar] = []
        cursor = start_d
        while cursor <= end_d:
            sess = adapter.get_session_window(instrument.exchange_code, cursor)
            if sess.is_trading_day and sess.open_utc is not None and sess.close_utc is not None:
                slot = sess.open_utc
                bar_idx = 0
                running_price = base
                while slot < sess.close_utc:
                    slot_end = min(slot + timedelta(minutes=step_minutes), sess.close_utc)
                    if slot_end > start_utc and slot < end_utc:
                        r = _seed_float(
                            f"{instrument.canonical_code}:{timeframe}:{slot.isoformat()}"
                        )
                        # Opening range bars (first 15m): tight consolidation; breakout after bar 3
                        if bar_idx < (15 // step_minutes):
                            delta = (r - 0.5) * 0.0025
                            vol_mult = 1.25
                        elif bar_idx == (15 // step_minutes) + 2 and pattern == "breakout":
                            delta = 0.0095
                            vol_mult = 2.6
                        elif bar_idx == (15 // step_minutes) + 2 and pattern == "breakdown":
                            delta = -0.0095
                            vol_mult = 2.4
                        else:
                            trend = 0.0004 if pattern != "breakdown" else -0.0004
                            delta = trend + (r - 0.5) * 0.0022
                            vol_mult = 0.9 + r * 0.5

                        open_f = running_price
                        close_f = max(1.0, open_f * (1.0 + delta))
                        high_f = max(open_f, close_f) * (1.0 + 0.0012 + r * 0.0012)
                        low_f = max(0.5, min(open_f, close_f) * (1.0 - 0.0012 - (1.0 - r) * 0.0012))

                        open_d = adapter.round_to_tick(Decimal(str(open_f)), instrument, "nearest")
                        close_d = adapter.round_to_tick(Decimal(str(close_f)), instrument, "nearest")
                        high_d = max(
                            open_d,
                            close_d,
                            adapter.round_to_tick(Decimal(str(high_f)), instrument, "up"),
                        )
                        low_d = min(
                            open_d,
                            close_d,
                            adapter.round_to_tick(Decimal(str(low_f)), instrument, "down"),
                        )
                        low_d = max(instrument.tick_size, low_d)

                        is_complete = slot_end <= end_utc
                        bars.append(
                            OHLCVBar(
                                instrument_id=instrument.instrument_id,
                                timeframe=timeframe,
                                bar_start_utc=slot,
                                bar_end_utc=slot_end,
                                open=open_d,
                                high=high_d,
                                low=low_d,
                                close=close_d,
                                volume=int(per_bar_vol * vol_mult),
                                is_complete=is_complete,
                                source_provider=self.provider_code,
                                fetched_at_utc=fetched_at,
                            )
                        )
                        running_price = float(close_d)
                    slot = slot_end
                    bar_idx += 1
            cursor += timedelta(days=1)

        return bars

    def get_bars(
        self,
        instrument: Instrument,
        timeframe: str,
        start_utc: datetime,
        end_utc: datetime,
    ) -> list[OHLCVBar]:
        self._check_outage()
        if timeframe not in {"1m", "5m", "15m", "1d"}:
            raise ValueError(f"Unsupported timeframe: {timeframe!r}")
        spec = self._specs_by_id.get(instrument.instrument_id)
        if spec is None:
            raise ProviderUnavailableError(
                self.provider_code, f"Instrument {instrument.canonical_code} not in mock fixtures"
            )
        if timeframe == "1d":
            return self._generate_daily_bars(instrument, spec, start_utc, end_utc)
        return self._generate_intraday_bars(instrument, spec, timeframe, start_utc, end_utc)

    def health_check(self) -> dict[str, Any]:
        return {
            "provider_code": self.provider_code,
            "is_commercial_licensed": self.is_commercial_licensed,
            "ok": not self.simulate_outage,
            "detail": self.outage_reason if self.simulate_outage else "ok (deterministic offline fixture)",
            "simulated_delay_seconds": self.simulated_delay_seconds,
        }
