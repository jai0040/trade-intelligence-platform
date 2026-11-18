"""Stateless wrapper for trader-scanner supporting India & US daily and ORB setups (BUY/SELL/WATCH)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from data_providers.freshness import evaluate_quote_freshness, filter_completed_bars
from domain.models import AssetType, OHLCVBar, SignalType
from skill_wrappers.base import BaseSkill, SkillContext, SkillResult


def _sma(values: list[Decimal], period: int) -> Decimal:
    window = values[-period:]
    return sum(window, Decimal("0")) / Decimal(len(window))


def _atr(bars: list[OHLCVBar], period: int = 14) -> Decimal:
    if len(bars) < 2:
        return Decimal("0")
    trs: list[Decimal] = []
    for idx in range(1, len(bars)):
        curr = bars[idx]
        prev_close = bars[idx - 1].close
        tr = max(
            curr.high - curr.low,
            abs(curr.high - prev_close),
            abs(curr.low - prev_close),
        )
        trs.append(tr)
    window = trs[-period:]
    return sum(window, Decimal("0")) / Decimal(len(window))


def _rsi(closes: list[Decimal], period: int = 14) -> Decimal:
    if len(closes) <= period:
        return Decimal("50")
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for idx in range(len(closes) - period, len(closes)):
        delta = closes[idx] - closes[idx - 1]
        gains.append(max(delta, Decimal("0")))
        losses.append(max(-delta, Decimal("0")))
    avg_gain = sum(gains, Decimal("0")) / Decimal(period)
    avg_loss = sum(losses, Decimal("0")) / Decimal(period)
    if avg_loss == Decimal("0"):
        return Decimal("100")
    rs = avg_gain / avg_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + rs))


class ScannerSkillWrapper(BaseSkill):
    """Scans India & US equities and ETFs for daily technical setups and intraday ORB setups."""

    skill_name = "trader-scanner"

    def _execute(self, ctx: SkillContext, payload: dict[str, Any]) -> SkillResult:
        mode = str(payload.get("mode", "daily")).lower()
        max_stale_seconds = int(ctx.config.get("quote_stale_threshold_seconds", 900))
        universe = [
            inst
            for inst in ctx.data_provider.get_universe(ctx.market_adapter.market_code)
            if inst.asset_type in {AssetType.EQUITY.value, AssetType.ETF.value}
        ]
        quotes = ctx.data_provider.get_quotes(universe, as_of_utc=ctx.as_of_utc)

        hits: list[dict[str, Any]] = []
        warnings: list[str] = []
        usable_count = 0

        for inst in universe:
            quote = quotes.get(inst.instrument_id)
            freshness = evaluate_quote_freshness(
                quote,
                provider_code=ctx.data_provider.provider_code,
                now_utc=ctx.as_of_utc,
                max_age_seconds=max_stale_seconds,
            )
            if freshness.is_stale or quote is None:
                warnings.append(f"{inst.canonical_code}: skipped due to stale/missing quote")
                continue

            daily_start = ctx.as_of_utc - timedelta(days=90)
            raw_daily = ctx.data_provider.get_bars(inst, "1d", daily_start, ctx.as_of_utc)
            daily_bars = filter_completed_bars(raw_daily)
            if len(daily_bars) < 22:
                continue
            usable_count += 1

            closes = [b.close for b in daily_bars]
            last_bar = daily_bars[-1]
            prev_20_high = max(b.close for b in daily_bars[-21:-1])
            prev_20_low = min(b.close for b in daily_bars[-21:-1])
            sma_20 = _sma(closes, 20)
            atr_14 = _atr(daily_bars, 14)
            rsi_14 = _rsi(closes, 14)
            avg_vol_20 = sum(b.volume for b in daily_bars[-21:-1]) / max(1, len(daily_bars[-21:-1]))
            vol_ratio = Decimal(str(round(last_bar.volume / max(1.0, avg_vol_20), 2)))

            setup_type: str | None = None
            signal_bias: str = SignalType.WATCH.value
            level_price: Decimal = last_bar.close

            if mode == "orb":
                intraday_start = ctx.as_of_utc - timedelta(days=2)
                raw_5m = ctx.data_provider.get_bars(inst, "5m", intraday_start, ctx.as_of_utc)
                bars_5m = filter_completed_bars(raw_5m, as_of_utc=ctx.as_of_utc)
                if len(bars_5m) >= 4:
                    # First 3 five-minute bars define the 15-minute opening range
                    or_bars = bars_5m[:3]
                    or_high = max(b.high for b in or_bars)
                    or_low = min(b.low for b in or_bars)
                    latest_5m = bars_5m[-1]
                    if latest_5m.close > or_high:
                        setup_type = "orb_15m_breakout"
                        signal_bias = SignalType.BUY.value
                        level_price = or_high
                    elif latest_5m.close < or_low:
                        setup_type = "orb_15m_breakdown"
                        signal_bias = SignalType.SELL.value
                        level_price = or_low
                    elif latest_5m.close >= or_high * Decimal("0.996"):
                        setup_type = "orb_15m_approaching"
                        signal_bias = SignalType.WATCH.value
                        level_price = or_high

            # Daily setups (also fallback if mode == 'daily')
            if setup_type is None:
                if last_bar.close > prev_20_high:
                    setup_type = "20d_breakout"
                    signal_bias = SignalType.BUY.value
                    level_price = prev_20_high
                elif last_bar.close < prev_20_low:
                    setup_type = "20d_breakdown"
                    signal_bias = SignalType.SELL.value
                    level_price = prev_20_low
                elif last_bar.close > sma_20 and daily_bars[-2].close <= sma_20:
                    setup_type = "reclaim_20sma"
                    signal_bias = SignalType.BUY.value
                    level_price = sma_20
                elif rsi_14 < Decimal("38") and last_bar.close > last_bar.open:
                    setup_type = "oversold_bounce"
                    signal_bias = SignalType.BUY.value
                    level_price = last_bar.low
                elif last_bar.close > sma_20 and vol_ratio >= Decimal("1.10"):
                    setup_type = "bull_flag"
                    signal_bias = SignalType.WATCH.value
                    level_price = max(b.high for b in daily_bars[-5:])

            if setup_type is not None:
                hits.append(
                    {
                        "instrument": inst,
                        "instrument_id": inst.instrument_id,
                        "market_code": inst.market_code.value,
                        "exchange_code": inst.exchange_code.value,
                        "symbol": inst.symbol,
                        "canonical_code": inst.canonical_code,
                        "company_name": inst.company_name,
                        "currency": inst.currency,
                        "mode": mode,
                        "setup_type": setup_type,
                        "signal_bias": signal_bias,
                        "level_price": ctx.market_adapter.round_to_tick(level_price, inst, "nearest"),
                        "last_price": quote.last_price,
                        "atr_14": atr_14.quantize(Decimal("0.0001")),
                        "sma_20": sma_20.quantize(Decimal("0.0001")),
                        "rsi_14": rsi_14.quantize(Decimal("0.01")),
                        "volume_ratio": vol_ratio,
                        "quote_timestamp_utc": quote.quote_timestamp_utc,
                        "source_provider": quote.source_provider,
                    }
                )

        return SkillResult(
            skill_name=self.skill_name,
            status="SUCCEEDED",
            data={"mode": mode, "hits": hits},
            warnings=warnings,
            metrics={
                "scanned_symbols": len(universe),
                "usable_charts": usable_count,
                "matched_count": len(hits),
            },
        )
