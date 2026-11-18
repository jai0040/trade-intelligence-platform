"""Phase 6 live unit & end-to-end offline DAG tests for all 11 skills, Risk Gate, AI, and Kill Switch."""

from __future__ import annotations

import ast
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "backend"), str(ROOT / "trading-engine")):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_all_phase6_files_compile_and_11_wrappers_registered() -> None:
    targets: list[Path] = []
    for folder in (
        "trading-engine/skill_wrappers",
        "trading-engine/risk_engine",
        "trading-engine/signal_engine",
        "trading-engine/ai_analyst",
        "trading-engine/workflows",
        "backend/app/signals",
    ):
        for py_file in (ROOT / folder).rglob("*.py"):
            targets.append(py_file)
    assert len(targets) >= 20
    for py_file in targets:
        ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))

    from skill_wrappers import ALL_SKILL_WRAPPERS

    names = {cls.skill_name for cls in ALL_SKILL_WRAPPERS}
    assert len(names) == 11
    assert names == {
        "trader-scanner",
        "trader-news",
        "trader-analyst",
        "trader-entry",
        "trader-exit",
        "trader-timemachine",
        "trader-budget",
        "trader-risk",
        "trader-broker",
        "trader-alerts",
        "trader-pelosi",
    }


def test_signals_only_hard_lock_on_broker_wrapper() -> None:
    from domain.errors import SignalsOnlyPolicyError
    from skill_wrappers.broker_ticket_wrapper import BrokerTicketSkillWrapper

    broker = BrokerTicketSkillWrapper()
    for method_name in ("place_live_order", "submit_order"):
        try:
            getattr(broker, method_name)("NSE:RELIANCE", qty=10)
            raise AssertionError(f"Expected SignalsOnlyPolicyError from {method_name}")
        except SignalsOnlyPolicyError:
            pass


def test_mandatory_risk_gate_and_ai_immutability_boundary() -> None:
    from adapters.india.adapter import IndiaMarketAdapter
    from ai_analyst.service import AIAnalystService
    from domain.models import ExchangeCode, Instrument, MarketCode
    from risk_engine.validator import validate_signal_risk

    adapter = IndiaMarketAdapter()
    inst = Instrument(
        instrument_id="inst-rel",
        market_code=MarketCode.IN,
        exchange_code=ExchangeCode.NSE,
        symbol="RELIANCE",
        canonical_code="NSE:RELIANCE",
        company_name="Reliance Industries Limited",
        asset_type="EQUITY",
        currency="INR",
        tick_size=Decimal("0.05"),
    )
    now = datetime(2026, 11, 18, 6, 0, tzinfo=timezone.utc)  # 11:30 IST

    # 1. Invalid geometry (stop above entry on BUY) -> REJECTED
    bad_geom = validate_signal_risk(
        instrument=inst,
        market_adapter=adapter,
        signal_type="BUY",
        entry_price=Decimal("2950.00"),
        stop_loss=Decimal("2980.00"),
        target_price=Decimal("3050.00"),
        risk_reward_ratio=Decimal("2.00"),
        quote_is_stale=False,
        as_of_utc=now,
    )
    assert bad_geom.status == "REJECTED"
    assert bad_geom.passed is False
    assert bad_geom.checks["directional_geometry"] is False

    # 2. Stale quote -> REJECTED
    stale_check = validate_signal_risk(
        instrument=inst,
        market_adapter=adapter,
        signal_type="BUY",
        entry_price=Decimal("2950.00"),
        stop_loss=Decimal("2900.00"),
        target_price=Decimal("3050.00"),
        risk_reward_ratio=Decimal("2.00"),
        quote_is_stale=True,
        as_of_utc=now,
    )
    assert stale_check.status == "REJECTED"
    assert stale_check.checks["fresh_market_data"] is False

    # 3. Low R:R (<1.50) -> REJECTED
    low_rr = validate_signal_risk(
        instrument=inst,
        market_adapter=adapter,
        signal_type="BUY",
        entry_price=Decimal("2950.00"),
        stop_loss=Decimal("2900.00"),
        target_price=Decimal("2990.00"),
        risk_reward_ratio=Decimal("0.80"),
        quote_is_stale=False,
        as_of_utc=now,
    )
    assert low_rr.status == "REJECTED"
    assert low_rr.checks["min_risk_reward"] is False

    # 4. AI Analyst refuses REJECTED signals and cannot mutate PASSED signals
    ai = AIAnalystService(llm_provider="mock")
    try:
        ai.explain_signal({"canonical_code": "NSE:RELIANCE", "risk_validation_status": "REJECTED"})
        raise AssertionError("Expected AIAnalystService to refuse REJECTED signal")
    except ValueError:
        pass

    passed_snapshot = {
        "canonical_code": "NSE:RELIANCE",
        "market_code": "IN",
        "currency": "INR",
        "signal_type": "BUY",
        "strategy": "orb_15m_breakout",
        "entry_price": "2950.00",
        "stop_loss": "2900.00",
        "target_price": "3050.00",
        "risk_reward_ratio": "2.000",
        "confidence_score": 78.5,
        "risk_validation_status": "PASSED",
    }
    explanation = ai.explain_signal(passed_snapshot)
    assert "NSE:RELIANCE" in explanation.thesis
    assert passed_snapshot["entry_price"] == "2950.00"
    assert passed_snapshot["stop_loss"] == "2900.00"
    assert passed_snapshot["target_price"] == "3050.00"


def test_end_to_end_india_and_us_dag_idempotency_and_kill_switch() -> None:
    from data_providers.mock_provider import MockMarketDataProvider
    from domain.models import MarketCode
    from workflows.dag_engine import WorkflowEngine

    provider = MockMarketDataProvider(simulated_delay_seconds=3)
    kill_state = {"enabled": False}
    engine = WorkflowEngine(kill_switch_checker=lambda: kill_state["enabled"])

    # 1. End-to-end INDIA DAG (11:30 IST == 06:00 UTC on Wed 2026-11-18)
    in_now = datetime(2026, 11, 18, 6, 0, tzinfo=timezone.utc)
    in_report = engine.execute_market_workflow(
        market_code=MarketCode.IN,
        workflow_type="india_intraday_orb",
        data_provider=provider,
        as_of_utc=in_now,
        mode="orb",
        config={"mc_paths": 300},
    )
    assert in_report.status == "SUCCEEDED"
    assert len(in_report.published_signals) >= 1
    assert in_report.congress_disclosures == []  # trader-pelosi strictly US-only
    assert any(sr.skill_name == "trader-pelosi" and sr.status == "SKIPPED" for sr in in_report.skill_runs)

    for sig in in_report.published_signals:
        assert sig["market_code"] == "IN"
        assert sig["currency"] == "INR"
        assert sig["risk_validation_status"] == "PASSED"
        assert sig["timemachine_summary"]["session_5m_bars_used"] == 75
        assert sig["broker_ticket_preview"]["auto_executed"] is False
        assert sig["ai_reasoning"] is not None
        assert 0.0 <= sig["confidence_score"] <= 100.0

    # 2. Duplicate prevention: exact same slot skips cleanly
    dup_report = engine.execute_market_workflow(
        market_code=MarketCode.IN,
        workflow_type="india_intraday_orb",
        data_provider=provider,
        as_of_utc=in_now,
        mode="orb",
    )
    assert dup_report.status == "SKIPPED_DUPLICATE"
    assert dup_report.published_signals == []

    # 3. End-to-end US DAG (11:00 EST == 16:00 UTC on Wed 2026-11-18)
    us_now = datetime(2026, 11, 18, 16, 0, tzinfo=timezone.utc)
    us_report = engine.execute_market_workflow(
        market_code=MarketCode.US,
        workflow_type="us_intraday_orb",
        data_provider=provider,
        as_of_utc=us_now,
        mode="orb",
        config={"mc_paths": 300},
    )
    assert us_report.status == "SUCCEEDED"
    assert len(us_report.published_signals) >= 1
    assert len(us_report.congress_disclosures) >= 1
    assert any(d["is_late_filing"] is True for d in us_report.congress_disclosures)

    for sig in us_report.published_signals:
        assert sig["market_code"] == "US"
        assert sig["currency"] == "USD"
        assert sig["timemachine_summary"]["session_5m_bars_used"] == 78

    # 4. Global Emergency Kill Switch immediately aborts without touching prior data
    kill_state["enabled"] = True
    aborted = engine.execute_market_workflow(
        market_code=MarketCode.US,
        workflow_type="us_intraday_orb",
        data_provider=provider,
        as_of_utc=us_now + timedelta(minutes=5),
        mode="orb",
    )
    assert aborted.status == "ABORTED_KILL_SWITCH"
    assert aborted.published_signals == []
    assert aborted.skill_runs == []


def test_signal_lifecycle_alerts_and_net_outcome_accounting() -> None:
    from adapters.india.adapter import IndiaMarketAdapter
    from data_providers.mock_provider import MockMarketDataProvider
    from domain.models import MarketCode, SignalStatus
    from signal_engine.outcome_tracker import compute_signal_outcome, summarize_performance
    from skill_wrappers.alerts_wrapper import AlertsSkillWrapper
    from skill_wrappers.base import SkillContext

    provider = MockMarketDataProvider()
    adapter = IndiaMarketAdapter()
    reliance = provider.get_instrument_by_code("NSE:RELIANCE")
    assert reliance is not None
    now = datetime(2026, 11, 18, 8, 0, tzinfo=timezone.utc)
    quote = provider.get_quotes([reliance], as_of_utc=now)[reliance.instrument_id]

    # Create a Triggered BUY signal whose target is already below quote.last_price -> Target Hit
    target_px = quote.last_price - Decimal("1.00")
    entry_px = quote.last_price - Decimal("51.00")
    stop_px = quote.last_price - Decimal("76.00")

    ctx = SkillContext(
        workflow_run_id="wf-alerts-1",
        market_adapter=adapter,
        data_provider=provider,
        as_of_utc=now,
    )
    res = AlertsSkillWrapper().run(
        ctx,
        {
            "instruments": [reliance],
            "active_signals": [
                {
                    "id": "sig-1",
                    "instrument_id": reliance.instrument_id,
                    "signal_type": "BUY",
                    "current_status": SignalStatus.TRIGGERED.value,
                    "entry_price": str(entry_px),
                    "stop_loss": str(stop_px),
                    "target_price": str(target_px),
                    "expires_at_utc": now + timedelta(hours=2),
                }
            ],
        },
    )
    assert res.status == "SUCCEEDED"
    assert len(res.data["signal_transitions"]) == 1
    assert res.data["signal_transitions"][0]["new_status"] == SignalStatus.TARGET_HIT.value

    outcome = compute_signal_outcome(
        signal_id="sig-1",
        signal_type="BUY",
        final_status=SignalStatus.TARGET_HIT.value,
        entry_price=entry_px,
        stop_loss=stop_px,
        assumed_exit_price=target_px,
        market_adapter=adapter,
        triggered_at_utc=now - timedelta(minutes=20),
        closed_at_utc=now,
    )
    assert Decimal(outcome["estimated_cost_bps"]) == Decimal("15.0")
    assert Decimal(outcome["net_return_pct"]) < Decimal(outcome["gross_return_pct"])

    summary = summarize_performance([outcome])
    assert summary["win_rate_pct"] == 100.0
    assert summary["target_hits"] == 1
