"""Decoupled read-only AI Analyst explanation layer.

Architectural Guarantee:
- Receives ONLY a frozen deep copy of a risk-PASSED signal snapshot.
- Refuses to analyze REJECTED signals.
- Returns strictly structured prose commentary; NEVER mutates entry, stop-loss, target, or risk status.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

STANDARD_DISCLAIMER = (
    "Educational & informational market intelligence only — not personalized investment advice "
    "or a guarantee of profit. This platform operates strictly in SIGNALS-ONLY mode."
)


@dataclass(frozen=True)
class AIExplanation:
    thesis: str
    key_levels_summary: str
    risk_factors: list[str]
    catalyst_notes: str
    disclaimer: str = STANDARD_DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        return {
            "thesis": self.thesis,
            "key_levels_summary": self.key_levels_summary,
            "risk_factors": list(self.risk_factors),
            "catalyst_notes": self.catalyst_notes,
            "disclaimer": self.disclaimer,
        }


class AIAnalystService:
    """Generates structured natural-language commentary from deterministic skill outputs."""

    def __init__(self, llm_provider: str = "mock") -> None:
        self.llm_provider = llm_provider.strip().lower()

    def explain_signal(self, signal_snapshot: dict[str, Any]) -> AIExplanation:
        """Produce read-only explanation for a risk-PASSED signal without touching numeric fields."""
        frozen = copy.deepcopy(signal_snapshot)
        if frozen.get("risk_validation_status") != "PASSED":
            raise ValueError(
                "AIAnalystService refuses to explain a signal that did not PASS trader-risk."
            )

        symbol = frozen["canonical_code"]
        sig_type = frozen["signal_type"]
        strategy = frozen["strategy"]
        currency_sym = "₹" if frozen.get("currency") == "INR" else "$"
        entry = frozen["entry_price"]
        stop = frozen["stop_loss"]
        target = frozen["target_price"]
        rr = frozen["risk_reward_ratio"]
        conf = frozen["confidence_score"]

        tm = frozen.get("timemachine_summary") or {}
        news = frozen.get("news_context") or {}
        tech = frozen.get("technical_indicators") or {}

        thesis = (
            f"{symbol} matched the deterministic '{strategy}' rule with a {sig_type} bias "
            f"(Composite Setup Quality Score: {conf}/100, Volume Ratio: {tech.get('volume_ratio', 'N/A')}x). "
            f"All mandatory trader-risk validations passed."
        )
        key_levels = (
            f"Entry {currency_sym}{entry} | Stop-Loss {currency_sym}{stop} | "
            f"Target {currency_sym}{target} (Planned R:R {rr}x). "
            f"Time Machine diagnostic ({tm.get('mc_paths', 0)} paths, "
            f"{tm.get('session_5m_bars_used', 'N/A')} bars/session): "
            f"target-reach rate {tm.get('mc_target_hit_prob_pct', 'N/A')}%, "
            f"expected R {tm.get('expected_r_multiple', 'N/A')}."
        )

        risk_factors = [
            "Intraday stops do not protect against sudden liquidity gaps or trading halts.",
            "Setup quality scores measure rule alignment and historical diagnostics, not guaranteed win odds.",
        ]
        if frozen.get("market_code") == "IN":
            risk_factors.append(
                "NSE/BSE intraday MIS sessions close by 15:30 IST; respect exchange square-off windows."
            )
        else:
            risk_factors.append(
                "US NASDAQ/NYSE regular hours close at 16:00 ET (13:00 ET on early-close days)."
            )

        headlines = news.get("headlines") or []
        catalyst_notes = (
            f"Latest filing/news check: {headlines[0]}"
            if headlines
            else "No adverse breaking regulatory filings detected at scan time."
        )

        return AIExplanation(
            thesis=thesis,
            key_levels_summary=key_levels,
            risk_factors=risk_factors,
            catalyst_notes=catalyst_notes,
        )

    def answer_user_query(
        self,
        *,
        question: str,
        context_signals: list[dict[str, Any]],
        market_code: str = "ALL",
    ) -> dict[str, Any]:
        """Answer a subscriber's analytical question strictly grounded in deterministic context."""
        cleaned_q = question.strip()
        if not cleaned_q:
            raise ValueError("Question cannot be empty.")

        matching = [
            s
            for s in context_signals
            if s.get("risk_validation_status") == "PASSED"
            and (market_code == "ALL" or s.get("market_code") == market_code)
        ]
        highlighted = matching[:3]

        if highlighted:
            lines = [
                f"- {s['canonical_code']} ({s['signal_type']} via {s['strategy']}): "
                f"Entry {s['entry_price']}, SL {s['stop_loss']}, Target {s['target_price']} "
                f"(R:R {s['risk_reward_ratio']}x, Score {s['confidence_score']}/100)"
                for s in highlighted
            ]
            answer = (
                f"Based on {len(matching)} risk-validated signal(s) in scope ({market_code}) "
                f"for your query \"{cleaned_q}\":\n" + "\n".join(lines)
            )
        else:
            answer = (
                f"No risk-validated active signals currently match scope '{market_code}' "
                f"for your query \"{cleaned_q}\". Wait for the next scheduled market scan."
            )

        return {
            "provider": self.llm_provider,
            "question": cleaned_q,
            "market_scope": market_code,
            "referenced_signal_ids": [s["id"] for s in highlighted],
            "answer": answer,
            "disclaimer": STANDARD_DISCLAIMER,
        }
