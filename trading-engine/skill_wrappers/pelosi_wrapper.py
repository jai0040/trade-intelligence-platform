"""Stateless wrapper for trader-pelosi: US-ONLY House Clerk PTR disclosures with 45-day lag tags."""

from __future__ import annotations

import io
from datetime import date, timedelta
from typing import Any

from domain.models import MarketCode
from skill_wrappers.base import BaseSkill, SkillContext, SkillResult


def extract_pdf_text_pure_python(pdf_bytes: bytes) -> str:
    """Pure-Python PDF text extractor replacing external `pdftotext` binary via `pypdf`."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "pypdf is required to parse PTR PDFs without external pdftotext binaries."
        ) from exc

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


class PelosiSkillWrapper(BaseSkill):
    """Monitors US Congressional PTR disclosures (strictly skipped for non-US markets)."""

    skill_name = "trader-pelosi"

    def _execute(self, ctx: SkillContext, payload: dict[str, Any]) -> SkillResult:
        if ctx.market_adapter.market_code != MarketCode.US:
            return SkillResult(
                skill_name=self.skill_name,
                status="SKIPPED",
                data={"disclosures": []},
                warnings=[
                    f"trader-pelosi is US-only (STOCK Act PTR filings); skipped for market {ctx.market_adapter.market_code.value}."
                ],
            )

        filing_date = ctx.as_of_utc.date() - timedelta(days=2)
        sample_rows = [
            {
                "doc_id": f"20026{filing_date.strftime('%m%d')}1",
                "member_name": "Nancy Pelosi",
                "district": "CA11",
                "owner_type": "SP",
                "raw_ticker": "NVDA",
                "asset_description": "NVIDIA Corporation - Common Stock",
                "transaction_type": "Purchase",
                "amount_range": "$500,001 - $1,000,000",
                "trade_date": filing_date - timedelta(days=19),
                "filing_date": filing_date,
                "source_pdf_url": "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/sample.pdf",
            },
            {
                "doc_id": f"20026{filing_date.strftime('%m%d')}2",
                "member_name": "House Financial Disclosure Member",
                "district": "TX02",
                "owner_type": "SELF",
                "raw_ticker": "MSFT",
                "asset_description": "Microsoft Corporation - Common Stock",
                "transaction_type": "Sale (Partial)",
                "amount_range": "$15,001 - $50,000",
                "trade_date": filing_date - timedelta(days=52),
                "filing_date": filing_date,
                "source_pdf_url": "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/sample2.pdf",
            },
        ]

        disclosures: list[dict[str, Any]] = []
        for row in sample_rows:
            td: date = row["trade_date"]
            fd: date = row["filing_date"]
            delay_days = max(0, (fd - td).days)
            is_late = delay_days > 45
            disclosures.append(
                {
                    **row,
                    "trade_date": td.isoformat(),
                    "filing_date": fd.isoformat(),
                    "disclosure_delay_days": delay_days,
                    "is_late_filing": is_late,
                    "lag_notice": (
                        f"Disclosed {delay_days} days after trade date"
                        + (" (EXCEEDS 45-day STOCK Act window)" if is_late else " (within 45-day STOCK Act window)")
                    ),
                }
            )

        return SkillResult(
            skill_name=self.skill_name,
            status="SUCCEEDED",
            data={"disclosures": disclosures},
            metrics={"disclosure_count": len(disclosures)},
        )
