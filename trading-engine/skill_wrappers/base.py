"""Standardized stateless BaseSkill contract for all 11 vendored trading skills."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from adapters.base import MarketAdapter
from data_providers.base import MarketDataProvider


@dataclass(frozen=True)
class SkillContext:
    """Stateless execution context injected into every skill wrapper (zero shared local files)."""

    workflow_run_id: str
    market_adapter: MarketAdapter
    data_provider: MarketDataProvider
    as_of_utc: datetime
    config: dict[str, Any] = field(default_factory=dict)
    user_id: str | None = None


@dataclass(frozen=True)
class SkillResult:
    """Typed structured output from a skill wrapper execution."""

    skill_name: str
    status: str  # "SUCCEEDED" | "PARTIAL" | "FAILED" | "SKIPPED"
    data: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


class BaseSkill(ABC):
    """Base class for all 11 stateless, multi-tenant-safe trading skill wrappers."""

    skill_name: str

    def run(self, ctx: SkillContext, payload: dict[str, Any] | None = None) -> SkillResult:
        """Execute skill with timing telemetry and consistent error capture."""
        t0 = time.perf_counter()
        try:
            result = self._execute(ctx, payload or {})
        except Exception as exc:
            duration_ms = max(1, int((time.perf_counter() - t0) * 1000))
            return SkillResult(
                skill_name=self.skill_name,
                status="FAILED",
                data={},
                warnings=[],
                metrics={"duration_ms": duration_ms},
                error_message=str(exc),
            )
        duration_ms = max(1, int((time.perf_counter() - t0) * 1000))
        metrics = dict(result.metrics)
        metrics["duration_ms"] = duration_ms
        return SkillResult(
            skill_name=result.skill_name,
            status=result.status,
            data=result.data,
            warnings=list(result.warnings),
            metrics=metrics,
            error_message=result.error_message,
        )

    @abstractmethod
    def _execute(self, ctx: SkillContext, payload: dict[str, Any]) -> SkillResult:
        """Implement deterministic skill logic using ctx.market_adapter and ctx.data_provider."""
