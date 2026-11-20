"""Backend Signals & Workflow Orchestration Hub bridging FastAPI, DB/Redis Kill Switch, and DAG Engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ai_analyst.service import AIAnalystService
from app.core.audit import record_audit_event
from app.core.redis import KILL_SWITCH_REDIS_KEY
from data_providers.base import MarketDataProvider
from domain.models import MarketCode
from signal_engine.outcome_tracker import summarize_performance
from workflows.dag_engine import WorkflowEngine, WorkflowExecutionReport

KILL_SWITCH_SETTING_KEY = "kill_switch_enabled"


def read_kill_switch(db: DbSession | None, redis_client: Any | None) -> bool:
    """Authoritatively read the Global Emergency Kill Switch (Redis mirror backed by DB system_settings)."""
    if redis_client is not None:
        try:
            val = redis_client.get(KILL_SWITCH_REDIS_KEY)
            if val is not None:
                return val == "1"
        except Exception:
            pass

    if db is not None:
        try:
            from database.models.signals import SystemSetting

            row = db.execute(
                select(SystemSetting).where(SystemSetting.key == KILL_SWITCH_SETTING_KEY)
            ).scalar_one_or_none()
            if row is not None and isinstance(row.value, dict):
                return bool(row.value.get("enabled", False))
        except Exception:
            pass
    return False


def update_kill_switch(
    db: DbSession,
    *,
    redis_client: Any | None,
    enabled: bool,
    actor_user_id: uuid.UUID,
    reason: str,
    ip_address: str | None = None,
) -> bool:
    """Persist kill-switch toggle to PostgreSQL system_settings, mirror to Redis, and write audit_logs."""
    from database.models.signals import SystemSetting

    row = db.execute(
        select(SystemSetting).where(SystemSetting.key == KILL_SWITCH_SETTING_KEY)
    ).scalar_one_or_none()
    payload = {
        "enabled": enabled,
        "reason": reason,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if row is None:
        db.add(
            SystemSetting(
                key=KILL_SWITCH_SETTING_KEY,
                value=payload,
                updated_by_user_id=actor_user_id,
            )
        )
    else:
        row.value = payload
        row.updated_by_user_id = actor_user_id

    record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="KILL_SWITCH_ENABLED" if enabled else "KILL_SWITCH_DISABLED",
        resource_type="system_setting",
        resource_id=KILL_SWITCH_SETTING_KEY,
        metadata={"enabled": enabled, "reason": reason},
        ip_address=ip_address,
    )
    db.commit()

    if redis_client is not None:
        try:
            redis_client.setex(KILL_SWITCH_REDIS_KEY, 86400 * 30, "1" if enabled else "0")
        except Exception:
            pass
    return enabled


class SignalsEngineHub:
    """Holds live DAG workflow execution results and exposes read/filter APIs for Phase 6 & 7."""

    def __init__(self, *, llm_provider: str = "mock") -> None:
        self.ai_analyst = AIAnalystService(llm_provider=llm_provider)
        self.workflow_reports: list[WorkflowExecutionReport] = []
        self.scanner_hits: list[dict[str, Any]] = []
        self.signals_by_id: dict[str, dict[str, Any]] = {}
        self.rejected_signals: list[dict[str, Any]] = []
        self.news_items: list[dict[str, Any]] = []
        self.fundamentals_by_symbol: dict[str, dict[str, Any]] = {}
        self.congress_disclosures: list[dict[str, Any]] = []
        self.outcomes: list[dict[str, Any]] = []
        self._engine = WorkflowEngine(ai_analyst=self.ai_analyst)

    def run_market_workflow(
        self,
        *,
        market_code: MarketCode,
        provider: MarketDataProvider,
        mode: str = "orb",
        triggered_by: str = "api",
        kill_switch_active: bool = False,
        as_of_utc: datetime | None = None,
        force_duplicate: bool = False,
    ) -> WorkflowExecutionReport:
        self._engine._kill_switch_checker = lambda: kill_switch_active
        report = self._engine.execute_market_workflow(
            market_code=market_code,
            workflow_type=f"{market_code.value.lower()}_{mode}_scan",
            data_provider=provider,
            as_of_utc=as_of_utc,
            triggered_by=triggered_by,
            mode=mode,
            existing_active_signals=list(self.signals_by_id.values()),
            force_duplicate=force_duplicate,
        )
        self.workflow_reports.insert(0, report)
        self.workflow_reports = self.workflow_reports[:100]

        if report.status == "SUCCEEDED":
            # Replace latest scanner hits for this market/mode
            self.scanner_hits = [
                h
                for h in self.scanner_hits
                if not (h["market_code"] == market_code.value and h["mode"] == mode)
            ] + list(report.scanner_hits)

            for sig in report.published_signals:
                self.signals_by_id[sig["id"]] = sig
            self.rejected_signals.extend(report.rejected_signals)

            existing_hashes = {n["dedupe_hash"] for n in self.news_items}
            for item in report.news_items:
                if item["dedupe_hash"] not in existing_hashes:
                    self.news_items.insert(0, item)
                    existing_hashes.add(item["dedupe_hash"])

            self.fundamentals_by_symbol.update(report.fundamentals)

            if report.congress_disclosures:
                existing_docs = {d["doc_id"] for d in self.congress_disclosures}
                for disc in report.congress_disclosures:
                    if disc["doc_id"] not in existing_docs:
                        self.congress_disclosures.insert(0, disc)
                        existing_docs.add(disc["doc_id"])

            self.outcomes.extend(report.signal_outcomes)

        return report

    def load_scanner_watchlist_from_disk(self, watchlist_path: Any = None) -> int:
        """Ingest live technical scanner hits generated by trader-scanner/scan.py into the platform."""
        import json
        from pathlib import Path
        path = Path(watchlist_path) if watchlist_path else Path("trader/watchlist.json")
        if not path.is_file():
            return 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except Exception:
            return 0

        names_map: dict[str, str] = {
            "RELIANCE": "Reliance Industries Ltd.",
            "TCS": "Tata Consultancy Services Ltd.",
            "INFY": "Infosys Ltd.",
            "HDFCBANK": "HDFC Bank Ltd.",
            "ICICIBANK": "ICICI Bank Ltd.",
            "TATAMOTORS": "Tata Motors Ltd.",
            "SBIN": "State Bank of India",
        }
        univ_path = Path("trader/universe.txt")
        if univ_path.is_file():
            try:
                with open(univ_path, "r", encoding="utf-8") as uf:
                    for line in uf:
                        parts = line.strip().split("|", 1)
                        if len(parts) == 2:
                            names_map[parts[0].strip()] = parts[1].strip()
            except Exception:
                pass

        hits = doc.get("hits") or []
        created_at = doc.get("created_at") or datetime.now(timezone.utc).isoformat()
        loaded_hits: list[dict[str, Any]] = []

        for h in hits:
            sym = str(h.get("symbol", "")).strip().upper()
            if not sym:
                continue
            is_india = sym.endswith(".NS") or sym.endswith(".BO") or sym in {
                "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "TATAMOTORS", "SBIN"
            }
            clean_sym = sym.replace(".NS", "").replace(".BO", "")
            mkt_code = "IN" if is_india else "US"
            exch_code = "NSE" if is_india else ("NYSE" if len(clean_sym) <= 3 else "NASDAQ")
            currency = "INR" if is_india else "USD"
            price = Decimal(str(h.get("price", 0)))
            setups = h.get("setups") or ["daily_setup"]
            setup_str = ", ".join(setups)
            bias = "BUY" if any(s in setup_str for s in ("breakout", "bounce", "oversold", "reclaimed")) else "WATCH"
            company_name = names_map.get(clean_sym) or f"{clean_sym} Inc."

            loaded_hits.append({
                "instrument_id": f"{mkt_code.lower()}_{clean_sym.lower()}",
                "market_code": mkt_code,
                "exchange_code": exch_code,
                "symbol": clean_sym,
                "canonical_code": f"{exch_code}:{clean_sym}",
                "company_name": company_name,
                "currency": currency,
                "mode": doc.get("mode", "daily"),
                "setup_type": setup_str,
                "signal_bias": bias,
                "level_price": price,
                "last_price": price,
                "atr_14": Decimal("0"),
                "sma_20": Decimal("0"),
                "rsi_14": Decimal(str(h.get("rsi", "30.0"))),
                "volume_ratio": Decimal(str(round(h.get("volume", 1000000) / 1000000, 2))),
                "quote_timestamp_utc": created_at,
                "source_provider": "yahoo_scanner",
            })

        if loaded_hits:
            existing_syms = {item["symbol"] for item in self.scanner_hits}
            new_hits = [h for h in loaded_hits if h["symbol"] not in existing_syms]
            self.scanner_hits = new_hits + self.scanner_hits
        return len(loaded_hits)

    def ensure_seeded_from_providers(
        self,
        *,
        providers: dict[MarketCode, MarketDataProvider],
        kill_switch_active: bool = False,
    ) -> None:
        """Bootstrap initial India & US signals once in non-kill-switch dev/test environments."""
        if self.workflow_reports or kill_switch_active:
            # Even if reports already exist, ensure disk watchlist is integrated
            self.load_scanner_watchlist_from_disk()
            return
        for mkt in (MarketCode.IN, MarketCode.US):
            prov = providers.get(mkt)
            if prov is not None:
                self.run_market_workflow(
                    market_code=mkt,
                    provider=prov,
                    mode="daily",
                    triggered_by="bootstrap",
                    kill_switch_active=kill_switch_active,
                )
        self.load_scanner_watchlist_from_disk()

    def list_published_signals(
        self,
        *,
        market: str = "ALL",
        signal_type: str | None = None,
        status: str | None = None,
        strategy: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return strictly risk-PASSED signals filtered by market, side, status, strategy, and query."""
        items = [
            s
            for s in self.signals_by_id.values()
            if s.get("risk_validation_status") == "PASSED"
        ]
        if market.upper() != "ALL":
            items = [s for s in items if s["market_code"] == market.upper()]
        if signal_type:
            items = [s for s in items if s["signal_type"] == signal_type.upper()]
        if status:
            items = [s for s in items if s["current_status"].lower() == status.lower()]
        if strategy:
            items = [s for s in items if s["strategy"].lower() == strategy.lower()]
        if search:
            needle = search.strip().upper()
            items = [
                s
                for s in items
                if needle in s["symbol"].upper() or needle in s["company_name"].upper()
            ]
        items.sort(key=lambda s: s["generated_at_utc"], reverse=True)
        return items

    def performance_summary(self, *, market: str = "ALL") -> dict[str, Any]:
        filtered = self.outcomes
        if market.upper() != "ALL":
            mkt_ids = {
                sid
                for sid, s in self.signals_by_id.items()
                if s["market_code"] == market.upper()
            }
            filtered = [o for o in filtered if o["signal_id"] in mkt_ids]
        return summarize_performance(filtered)
