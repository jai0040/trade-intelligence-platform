"""Quote/bar freshness validation, forming-bar filtering, and provider_status health monitor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from domain.errors import StaleDataError
from domain.models import DataFreshnessReport, OHLCVBar, ProviderHealthStatus, QuoteSnapshot


def _utc_now(now_utc: datetime | None = None) -> datetime:
    if now_utc is None:
        return datetime.now(timezone.utc)
    return now_utc.replace(tzinfo=timezone.utc) if now_utc.tzinfo is None else now_utc.astimezone(timezone.utc)


def evaluate_quote_freshness(
    quote: QuoteSnapshot | None,
    *,
    provider_code: str,
    now_utc: datetime | None = None,
    max_age_seconds: int = 900,
    provider_status: ProviderHealthStatus = ProviderHealthStatus.HEALTHY,
) -> DataFreshnessReport:
    """Evaluate quote age against staleness threshold and return a structured freshness report."""
    now = _utc_now(now_utc)
    if quote is None:
        return DataFreshnessReport(
            provider=provider_code,
            status=ProviderHealthStatus.DOWN if provider_status == ProviderHealthStatus.HEALTHY else provider_status,
            last_quote_utc=None,
            delay_seconds=max_age_seconds + 1,
            is_stale=True,
            stale_reason="No quote timestamp available from provider.",
        )

    age_seconds = max(0, int((now - quote.quote_timestamp_utc).total_seconds()))
    effective_delay = max(age_seconds, quote.delay_seconds)
    is_stale = effective_delay > max_age_seconds
    status = provider_status
    stale_reason: str | None = None
    if is_stale:
        stale_reason = (
            f"Quote age ({effective_delay}s) exceeds staleness threshold ({max_age_seconds}s)."
        )
        if status == ProviderHealthStatus.HEALTHY:
            status = ProviderHealthStatus.DEGRADED

    return DataFreshnessReport(
        provider=quote.source_provider,
        status=status,
        last_quote_utc=quote.quote_timestamp_utc,
        delay_seconds=effective_delay,
        is_stale=is_stale,
        stale_reason=stale_reason,
    )


def assert_fresh_quote(
    quote: QuoteSnapshot,
    *,
    now_utc: datetime | None = None,
    max_age_seconds: int = 900,
) -> QuoteSnapshot:
    """Enforce mandatory freshness guard; raises StaleDataError if quote is stale."""
    report = evaluate_quote_freshness(
        quote,
        provider_code=quote.source_provider,
        now_utc=now_utc,
        max_age_seconds=max_age_seconds,
    )
    if report.is_stale:
        raise StaleDataError(quote.source_provider, report.delay_seconds, max_age_seconds)
    return quote


def filter_completed_bars(
    bars: list[OHLCVBar],
    *,
    as_of_utc: datetime | None = None,
) -> list[OHLCVBar]:
    """Strip any in-progress/forming bars and return strictly completed bars ordered chronologically."""
    cutoff = _utc_now(as_of_utc) if as_of_utc is not None else None
    completed = [
        bar
        for bar in bars
        if bar.is_complete and (cutoff is None or bar.bar_end_utc <= cutoff)
    ]
    completed.sort(key=lambda b: b.bar_start_utc)
    return completed


@dataclass
class ProviderMetricsRecord:
    provider_code: str
    market_code: str
    status: ProviderHealthStatus = ProviderHealthStatus.HEALTHY
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_message: str | None = None
    avg_latency_ms: int | None = None
    daily_api_calls: int = 0
    consecutive_failures: int = 0


class ProviderHealthMonitor:
    """In-memory and DB-syncable health monitor tracking provider availability and latency."""

    def __init__(self, degraded_threshold: int = 1, down_threshold: int = 3) -> None:
        self._degraded_threshold = degraded_threshold
        self._down_threshold = down_threshold
        self._records: dict[str, ProviderMetricsRecord] = {}

    def _get_or_create(self, provider_code: str, market_code: str) -> ProviderMetricsRecord:
        key = f"{provider_code}:{market_code.upper()}"
        rec = self._records.get(key)
        if rec is None:
            rec = ProviderMetricsRecord(
                provider_code=provider_code,
                market_code=market_code.upper(),
            )
            self._records[key] = rec
        return rec

    def record_success(
        self,
        provider_code: str,
        market_code: str,
        *,
        latency_ms: int,
        now_utc: datetime | None = None,
    ) -> ProviderMetricsRecord:
        now = _utc_now(now_utc)
        rec = self._get_or_create(provider_code, market_code)
        rec.status = ProviderHealthStatus.HEALTHY
        rec.last_success_at = now
        rec.consecutive_failures = 0
        rec.daily_api_calls += 1
        rec.avg_latency_ms = (
            latency_ms
            if rec.avg_latency_ms is None
            else int((rec.avg_latency_ms * 0.7) + (latency_ms * 0.3))
        )
        return rec

    def record_failure(
        self,
        provider_code: str,
        market_code: str,
        *,
        error_message: str,
        now_utc: datetime | None = None,
    ) -> ProviderMetricsRecord:
        now = _utc_now(now_utc)
        rec = self._get_or_create(provider_code, market_code)
        rec.last_error_at = now
        rec.last_error_message = error_message[:500]
        rec.consecutive_failures += 1
        rec.daily_api_calls += 1
        if rec.consecutive_failures >= self._down_threshold:
            rec.status = ProviderHealthStatus.DOWN
        elif rec.consecutive_failures >= self._degraded_threshold:
            rec.status = ProviderHealthStatus.DEGRADED
        return rec

    def get_record(self, provider_code: str, market_code: str) -> ProviderMetricsRecord:
        return self._get_or_create(provider_code, market_code)

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "provider_code": r.provider_code,
                "market_code": r.market_code,
                "status": r.status.value,
                "last_success_at": r.last_success_at.isoformat() if r.last_success_at else None,
                "last_error_at": r.last_error_at.isoformat() if r.last_error_at else None,
                "last_error_message": r.last_error_message,
                "avg_latency_ms": r.avg_latency_ms,
                "daily_api_calls": r.daily_api_calls,
                "consecutive_failures": r.consecutive_failures,
            }
            for r in self._records.values()
        ]
