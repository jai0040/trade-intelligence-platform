"""Centralized multi-market DAG Workflow Engine orchestrating all 11 skills, Risk Gate, and AI Analyst."""

from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from adapters.registry import get_market_adapter
from ai_analyst.service import AIAnalystService
from data_providers.base import MarketDataProvider
from data_providers.freshness import evaluate_quote_freshness
from domain.models import Instrument, MarketCode, SignalStatus, SignalType
from signal_engine.confidence import CONFIDENCE_LABEL, compute_composite_confidence
from signal_engine.outcome_tracker import compute_signal_outcome
from skill_wrappers.alerts_wrapper import AlertsSkillWrapper
from skill_wrappers.analyst_wrapper import AnalystSkillWrapper
from skill_wrappers.base import BaseSkill, SkillContext, SkillResult
from skill_wrappers.broker_ticket_wrapper import BrokerTicketSkillWrapper
from skill_wrappers.budget_wrapper import BudgetSkillWrapper
from skill_wrappers.entry_wrapper import EntrySkillWrapper
from skill_wrappers.exit_wrapper import ExitSkillWrapper
from skill_wrappers.news_wrapper import NewsSkillWrapper
from skill_wrappers.pelosi_wrapper import PelosiSkillWrapper
from skill_wrappers.risk_wrapper import RiskSkillWrapper
from skill_wrappers.scanner_wrapper import ScannerSkillWrapper
from skill_wrappers.timemachine_wrapper import TimeMachineSkillWrapper


def compute_workflow_idempotency_key(
    workflow_type: str,
    market_code: str,
    session_date_iso: str,
    slot_utc_iso: str,
) -> str:
    raw = f"{workflow_type}:{market_code.upper()}:{session_date_iso}:{slot_utc_iso}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_signal_idempotency_key(
    market_code: str,
    instrument_id: str,
    strategy: str,
    session_date_iso: str,
    signal_type: str,
) -> str:
    raw = f"{market_code.upper()}:{instrument_id}:{strategy}:{session_date_iso}:{signal_type.upper()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class SkillRunLog:
    id: str
    workflow_run_id: str
    skill_name: str
    status: str
    retry_count: int
    duration_ms: int
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    error_trace: str | None
    started_at_utc: str
    finished_at_utc: str


@dataclass
class WorkflowExecutionReport:
    workflow_run_id: str
    workflow_type: str
    market_code: str
    idempotency_key: str
    status: str  # "SUCCEEDED" | "ABORTED_KILL_SWITCH" | "SKIPPED_DUPLICATE" | "FAILED"
    triggered_by: str
    started_at_utc: str
    finished_at_utc: str
    skill_runs: list[SkillRunLog] = field(default_factory=list)
    scanner_hits: list[dict[str, Any]] = field(default_factory=list)
    published_signals: list[dict[str, Any]] = field(default_factory=list)
    rejected_signals: list[dict[str, Any]] = field(default_factory=list)
    news_items: list[dict[str, Any]] = field(default_factory=list)
    fundamentals: dict[str, dict[str, Any]] = field(default_factory=dict)
    congress_disclosures: list[dict[str, Any]] = field(default_factory=list)
    signal_transitions: list[dict[str, Any]] = field(default_factory=list)
    signal_outcomes: list[dict[str, Any]] = field(default_factory=list)
    error_message: str | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "workflow_run_id": self.workflow_run_id,
            "workflow_type": self.workflow_type,
            "market_code": self.market_code,
            "status": self.status,
            "scanner_hits": len(self.scanner_hits),
            "published_signals": len(self.published_signals),
            "rejected_signals": len(self.rejected_signals),
            "news_items": len(self.news_items),
            "congress_disclosures": len(self.congress_disclosures),
            "signal_transitions": len(self.signal_transitions),
            "skill_runs_count": len(self.skill_runs),
        }


class WorkflowEngine:
    """Deterministic multi-market DAG engine with kill-switch, locks, retries, and risk gate."""

    def __init__(
        self,
        *,
        kill_switch_checker: Callable[[], bool] | None = None,
        ai_analyst: AIAnalystService | None = None,
        max_retries: int = 2,
    ) -> None:
        self._kill_switch_checker = kill_switch_checker or (lambda: False)
        self._ai_analyst = ai_analyst or AIAnalystService(llm_provider="mock")
        self._max_retries = max(0, max_retries)

        # In-memory deduplication registries (backed by DB unique constraints in full stack)
        self._completed_workflow_keys: set[str] = set()
        self._published_signal_keys: set[str] = set()
        self._active_locks: set[str] = set()

        # Instantiate stateless wrappers for all 11 vendored skills
        self._scanner = ScannerSkillWrapper()
        self._news = NewsSkillWrapper()
        self._analyst = AnalystSkillWrapper()
        self._entry = EntrySkillWrapper()
        self._exit = ExitSkillWrapper()
        self._timemachine = TimeMachineSkillWrapper()
        self._budget = BudgetSkillWrapper()
        self._risk = RiskSkillWrapper()
        self._broker = BrokerTicketSkillWrapper()
        self._alerts = AlertsSkillWrapper()
        self._pelosi = PelosiSkillWrapper()

    def _run_skill_with_retries(
        self,
        skill: BaseSkill,
        ctx: SkillContext,
        payload: dict[str, Any],
        skill_runs: list[SkillRunLog],
        *,
        input_summary: dict[str, Any],
    ) -> SkillResult:
        attempt = 0
        last_res: SkillResult | None = None
        started = datetime.now(timezone.utc)

        while attempt <= self._max_retries:
            res = skill.run(ctx, payload)
            last_res = res
            if res.status != "FAILED":
                break
            attempt += 1
            if attempt <= self._max_retries:
                time.sleep(0.01 * (2 ** (attempt - 1)))

        assert last_res is not None
        finished = datetime.now(timezone.utc)
        skill_runs.append(
            SkillRunLog(
                id=str(uuid.uuid4()),
                workflow_run_id=ctx.workflow_run_id,
                skill_name=skill.skill_name,
                status=last_res.status,
                retry_count=min(attempt, self._max_retries),
                duration_ms=int(last_res.metrics.get("duration_ms", 1)),
                input_summary=input_summary,
                output_summary={"metrics": last_res.metrics, "warnings": last_res.warnings[:5]},
                error_trace=last_res.error_message,
                started_at_utc=started.isoformat(),
                finished_at_utc=finished.isoformat(),
            )
        )
        return last_res

    def execute_market_workflow(
        self,
        *,
        market_code: MarketCode | str,
        workflow_type: str,
        data_provider: MarketDataProvider,
        as_of_utc: datetime | None = None,
        triggered_by: str = "scheduler",
        mode: str = "orb",
        config: dict[str, Any] | None = None,
        existing_active_signals: list[dict[str, Any]] | None = None,
        existing_user_alerts: list[dict[str, Any]] | None = None,
        force_duplicate: bool = False,
    ) -> WorkflowExecutionReport:
        """Run the end-to-end deterministic market analysis DAG for India or US."""
        mkt = market_code if isinstance(market_code, MarketCode) else MarketCode(market_code.upper())
        now = as_of_utc or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)

        adapter = get_market_adapter(mkt)
        local_date = now.astimezone(adapter.local_timezone()).date()
        slot_iso = now.replace(second=0, microsecond=0).isoformat()
        idem_key = compute_workflow_idempotency_key(
            workflow_type, mkt.value, local_date.isoformat(), slot_iso
        )
        workflow_run_id = str(uuid.uuid4())
        started_iso = now.isoformat()

        # 1. Global Emergency Kill Switch pre-check (never deletes or modifies historical data)
        if self._kill_switch_checker():
            return WorkflowExecutionReport(
                workflow_run_id=workflow_run_id,
                workflow_type=workflow_type,
                market_code=mkt.value,
                idempotency_key=idem_key,
                status="ABORTED_KILL_SWITCH",
                triggered_by=triggered_by,
                started_at_utc=started_iso,
                finished_at_utc=datetime.now(timezone.utc).isoformat(),
                error_message="Aborted: Global Emergency Kill Switch is active.",
            )

        # 2. Idempotency & distributed lock guard
        if not force_duplicate and (
            idem_key in self._completed_workflow_keys or idem_key in self._active_locks
        ):
            return WorkflowExecutionReport(
                workflow_run_id=workflow_run_id,
                workflow_type=workflow_type,
                market_code=mkt.value,
                idempotency_key=idem_key,
                status="SKIPPED_DUPLICATE",
                triggered_by=triggered_by,
                started_at_utc=started_iso,
                finished_at_utc=datetime.now(timezone.utc).isoformat(),
            )

        self._active_locks.add(idem_key)
        skill_runs: list[SkillRunLog] = []
        run_config = dict(config or {})
        run_config.setdefault("trading_mode", "SIGNALS_ONLY")
        run_config.setdefault("quote_stale_threshold_seconds", 900)

        ctx = SkillContext(
            workflow_run_id=workflow_run_id,
            market_adapter=adapter,
            data_provider=data_provider,
            as_of_utc=now,
            config=run_config,
        )

        try:
            # Stage 1: Market Scanner
            scan_res = self._run_skill_with_retries(
                self._scanner,
                ctx,
                {"mode": mode},
                skill_runs,
                input_summary={"market": mkt.value, "mode": mode},
            )
            if scan_res.status == "FAILED":
                return WorkflowExecutionReport(
                    workflow_run_id=workflow_run_id,
                    workflow_type=workflow_type,
                    market_code=mkt.value,
                    idempotency_key=idem_key,
                    status="FAILED",
                    triggered_by=triggered_by,
                    started_at_utc=started_iso,
                    finished_at_utc=datetime.now(timezone.utc).isoformat(),
                    skill_runs=skill_runs,
                    error_message=scan_res.error_message,
                )

            raw_hits: list[dict[str, Any]] = list(scan_res.data.get("hits") or [])
            hit_instruments: list[Instrument] = [h["instrument"] for h in raw_hits]

            # Stage 2: News, Fundamentals & US Congressional Disclosures
            news_res = self._run_skill_with_retries(
                self._news,
                ctx,
                {"instruments": hit_instruments},
                skill_runs,
                input_summary={"symbols": [i.canonical_code for i in hit_instruments]},
            )
            analyst_res = self._run_skill_with_retries(
                self._analyst,
                ctx,
                {"instruments": hit_instruments},
                skill_runs,
                input_summary={"symbols": [i.canonical_code for i in hit_instruments]},
            )
            pelosi_res = self._run_skill_with_retries(
                self._pelosi,
                ctx,
                {},
                skill_runs,
                input_summary={"market": mkt.value},
            )

            news_by_symbol: dict[str, list[dict[str, Any]]] = news_res.data.get("by_symbol") or {}
            fundamentals_map: dict[str, dict[str, Any]] = analyst_res.data.get("fundamentals") or {}

            # Stage 3-5: Per-candidate Entry -> Exit -> TimeMachine -> Budget -> MANDATORY RISK GATE -> Broker Ticket -> AI Analyst
            published_signals: list[dict[str, Any]] = []
            rejected_signals: list[dict[str, Any]] = []
            serialized_hits: list[dict[str, Any]] = []

            session_window = adapter.get_session_window(
                adapter.supported_exchanges[0], local_date
            )
            default_expiry = (
                session_window.close_utc
                if session_window.close_utc is not None and session_window.close_utc > now
                else now + timedelta(hours=6)
            )

            quotes_cache = data_provider.get_quotes(hit_instruments, as_of_utc=now) if hit_instruments else {}

            for hit in raw_hits:
                inst: Instrument = hit["instrument"]
                serialized_hits.append({k: v for k, v in hit.items() if k != "instrument"})

                entry_res = self._run_skill_with_retries(
                    self._entry,
                    ctx,
                    {
                        "instrument": inst,
                        "level_price": hit["level_price"],
                        "signal_bias": hit["signal_bias"],
                        "setup_type": hit["setup_type"],
                        "timeframe": "5m" if mode == "orb" else "1d",
                    },
                    skill_runs,
                    input_summary={"symbol": inst.canonical_code, "setup": hit["setup_type"]},
                )
                if entry_res.status == "FAILED":
                    continue

                entry_price = Decimal(str(entry_res.data["entry_price"]))
                sig_type = str(entry_res.data["signal_type"]).upper()
                entry_state = str(entry_res.data.get("state", "WAITING"))

                exit_res = self._run_skill_with_retries(
                    self._exit,
                    ctx,
                    {
                        "instrument": inst,
                        "signal_type": sig_type,
                        "entry_price": entry_price,
                        "atr_14": hit["atr_14"],
                        "target_rr": run_config.get("target_rr", "2.0"),
                    },
                    skill_runs,
                    input_summary={"symbol": inst.canonical_code, "signal_type": sig_type},
                )
                if exit_res.status == "FAILED":
                    continue

                stop_loss = Decimal(str(exit_res.data["stop_loss"]))
                target_price = Decimal(str(exit_res.data["target_price"]))
                rr_ratio = Decimal(str(exit_res.data["risk_reward_ratio"]))

                tm_res = self._run_skill_with_retries(
                    self._timemachine,
                    ctx,
                    {
                        "instrument": inst,
                        "signal_type": sig_type,
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                        "target_price": target_price,
                        "mc_paths": int(run_config.get("mc_paths", 1000)),
                    },
                    skill_runs,
                    input_summary={"symbol": inst.canonical_code},
                )

                budget_res = self._run_skill_with_retries(
                    self._budget,
                    ctx,
                    {
                        "instrument": inst,
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                    },
                    skill_runs,
                    input_summary={"symbol": inst.canonical_code},
                )

                quote = quotes_cache.get(inst.instrument_id)
                freshness = evaluate_quote_freshness(
                    quote,
                    provider_code=data_provider.provider_code,
                    now_utc=now,
                    max_age_seconds=int(run_config["quote_stale_threshold_seconds"]),
                )

                # MANDATORY NON-OVERRIDABLE RISK GATE
                risk_res = self._run_skill_with_retries(
                    self._risk,
                    ctx,
                    {
                        "instrument": inst,
                        "signal_type": sig_type,
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                        "target_price": target_price,
                        "risk_reward_ratio": rr_ratio,
                        "quote_is_stale": freshness.is_stale,
                        "enforce_entry_window": bool(run_config.get("enforce_entry_window", False)),
                        "recommended_shares": budget_res.data.get("recommended_shares"),
                    },
                    skill_runs,
                    input_summary={"symbol": inst.canonical_code, "signal_type": sig_type},
                )

                risk_status = str(risk_res.data.get("risk_validation_status", "REJECTED"))
                sig_idem_key = compute_signal_idempotency_key(
                    mkt.value, inst.instrument_id, hit["setup_type"], local_date.isoformat(), sig_type
                )
                if not force_duplicate and sig_idem_key in self._published_signal_keys:
                    continue

                inst_news = news_by_symbol.get(inst.canonical_code, [])
                inst_fund = fundamentals_map.get(inst.canonical_code, {})
                conf_score, conf_breakdown = compute_composite_confidence(
                    entry_state=entry_state,
                    volume_ratio=Decimal(str(hit["volume_ratio"])),
                    risk_reward_ratio=rr_ratio,
                    timemachine_data=tm_res.data,
                    catalyst_risk=inst_news[0]["catalyst_risk"] if inst_news else "LOW",
                    overnight_earnings_gap_risk=bool(inst_fund.get("overnight_earnings_gap_risk", False)),
                )

                signal_snapshot: dict[str, Any] = {
                    "id": str(uuid.uuid4()),
                    "workflow_run_id": workflow_run_id,
                    "idempotency_key": sig_idem_key,
                    "instrument_id": inst.instrument_id,
                    "market_code": inst.market_code.value,
                    "exchange_code": inst.exchange_code.value,
                    "symbol": inst.symbol,
                    "canonical_code": inst.canonical_code,
                    "company_name": inst.company_name,
                    "currency": inst.currency,
                    "strategy": hit["setup_type"],
                    "signal_type": sig_type,
                    "entry_price": str(entry_price),
                    "stop_loss": str(stop_loss),
                    "target_price": str(target_price),
                    "risk_reward_ratio": str(rr_ratio),
                    "confidence_score": float(conf_score),
                    "confidence_label": CONFIDENCE_LABEL,
                    "confidence_breakdown": conf_breakdown,
                    "technical_indicators": {
                        "atr_14": str(hit["atr_14"]),
                        "sma_20": str(hit["sma_20"]),
                        "rsi_14": str(hit["rsi_14"]),
                        "volume_ratio": str(hit["volume_ratio"]),
                        "entry_state": entry_state,
                    },
                    "news_context": {
                        "count": len(inst_news),
                        "headlines": [n["headline"] for n in inst_news[:3]],
                    },
                    "fundamentals_summary": inst_fund or None,
                    "timemachine_summary": tm_res.data,
                    "reference_sizing": budget_res.data,
                    "risk_validation_status": risk_status,
                    "risk_validation_details": risk_res.data,
                    "broker_ticket_preview": None,
                    "ai_reasoning": None,
                    "ai_explanation": None,
                    "data_source_provider": data_provider.provider_code,
                    "data_as_of_utc": (
                        quote.quote_timestamp_utc.isoformat() if quote else now.isoformat()
                    ),
                    "current_status": (
                        SignalStatus.REJECTED.value
                        if risk_status != "PASSED"
                        else (
                            SignalStatus.TRIGGERED.value
                            if entry_state == "TRIGGERED" and sig_type != SignalType.WATCH.value
                            else SignalStatus.ACTIVE.value
                        )
                    ),
                    "generated_at_utc": now.isoformat(),
                    "last_updated_at_utc": now.isoformat(),
                    "expires_at_utc": default_expiry.isoformat(),
                }

                if risk_status != "PASSED":
                    # Rejected signals NEVER reach broker ticket preview, AI Analyst, or subscribers
                    rejected_signals.append(signal_snapshot)
                    continue

                # Stage 5 (PASSED signals only): Read-only broker ticket preview + Decoupled AI Analyst
                ticket_res = self._run_skill_with_retries(
                    self._broker,
                    ctx,
                    {
                        "instrument": inst,
                        "signal_type": sig_type,
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                        "target_price": target_price,
                        "risk_reward_ratio": rr_ratio,
                        "recommended_shares": budget_res.data.get("recommended_shares", 0),
                        "risk_validation_status": risk_status,
                        "risk_fingerprint": risk_res.data.get("risk_fingerprint", ""),
                    },
                    skill_runs,
                    input_summary={"symbol": inst.canonical_code, "mode": "SIGNALS_ONLY_PREVIEW"},
                )
                signal_snapshot["broker_ticket_preview"] = ticket_res.data.get("ticket")

                explanation = self._ai_analyst.explain_signal(signal_snapshot)
                signal_snapshot["ai_explanation"] = explanation.to_dict()
                signal_snapshot["ai_reasoning"] = (
                    f"{explanation.thesis} {explanation.key_levels_summary}"
                )

                self._published_signal_keys.add(sig_idem_key)
                published_signals.append(signal_snapshot)

            # Stage 6: Lifecycle alerts & outcome tracking for any previously active signals
            transitions: list[dict[str, Any]] = []
            outcomes: list[dict[str, Any]] = []
            if existing_active_signals or existing_user_alerts:
                all_univ = data_provider.get_universe(mkt)
                alerts_res = self._run_skill_with_retries(
                    self._alerts,
                    ctx,
                    {
                        "active_signals": existing_active_signals or [],
                        "user_alerts": existing_user_alerts or [],
                        "instruments": all_univ,
                    },
                    skill_runs,
                    input_summary={"active_signals": len(existing_active_signals or [])},
                )
                transitions = list(alerts_res.data.get("signal_transitions") or [])
                sig_by_id = {s["id"]: s for s in (existing_active_signals or [])}
                for tr in transitions:
                    if tr["new_status"] in {
                        SignalStatus.TARGET_HIT.value,
                        SignalStatus.STOP_LOSS_HIT.value,
                        SignalStatus.EXPIRED.value,
                    }:
                        orig = sig_by_id[tr["signal_id"]]
                        outcomes.append(
                            compute_signal_outcome(
                                signal_id=orig["id"],
                                signal_type=orig["signal_type"],
                                final_status=tr["new_status"],
                                entry_price=Decimal(str(orig["entry_price"])),
                                stop_loss=Decimal(str(orig["stop_loss"])),
                                assumed_exit_price=Decimal(str(tr["trigger_price"])),
                                market_adapter=adapter,
                                triggered_at_utc=now - timedelta(minutes=30),
                                closed_at_utc=now,
                            )
                        )

            self._completed_workflow_keys.add(idem_key)
            return WorkflowExecutionReport(
                workflow_run_id=workflow_run_id,
                workflow_type=workflow_type,
                market_code=mkt.value,
                idempotency_key=idem_key,
                status="SUCCEEDED",
                triggered_by=triggered_by,
                started_at_utc=started_iso,
                finished_at_utc=datetime.now(timezone.utc).isoformat(),
                skill_runs=skill_runs,
                scanner_hits=serialized_hits,
                published_signals=published_signals,
                rejected_signals=rejected_signals,
                news_items=list(news_res.data.get("news_items") or []),
                fundamentals=fundamentals_map,
                congress_disclosures=list(pelosi_res.data.get("disclosures") or []),
                signal_transitions=transitions,
                signal_outcomes=outcomes,
            )
        finally:
            self._active_locks.discard(idem_key)
