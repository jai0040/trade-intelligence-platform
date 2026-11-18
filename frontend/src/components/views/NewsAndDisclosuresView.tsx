"use client";

import React from "react";
import { AlertTriangle, ExternalLink, Landmark, Newspaper } from "lucide-react";
import type { MarketScope } from "@/components/layout/AppShell";
import type { CongressDisclosureItem, MarketNewsItem } from "@/lib/api";
import { cn, formatUtcTimestamp } from "@/lib/utils";

interface NewsAndDisclosuresViewProps {
  marketScope: MarketScope;
  news: MarketNewsItem[];
  disclosures: CongressDisclosureItem[];
  stockActNotice: string;
}

export function NewsAndDisclosuresView({
  marketScope,
  news,
  disclosures,
  stockActNotice,
}: NewsAndDisclosuresViewProps) {
  const scopedNews = news.filter(
    (n) => marketScope === "ALL" || n.market_code === marketScope
  );
  const showCongress = marketScope === "ALL" || marketScope === "US";

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Newspaper className="h-5 w-5 text-accent" />
            Market News &amp; Regulatory Filings
          </h1>
          <p className="text-xs text-muted-foreground">
            India NSE/BSE corporate announcements and US SEC EDGAR 8-K filings
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {scopedNews.map((item, idx) => (
            <article
              key={`${item.canonical_code}-${idx}`}
              className="rounded-xl border border-border bg-card p-4 space-y-2"
            >
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="px-2 py-0.5 rounded bg-accent/15 text-accent">
                  {item.canonical_code}
                </span>
                <span className="text-muted-foreground">
                  {item.source} • {formatUtcTimestamp(item.published_at_utc)}
                </span>
              </div>
              <h3 className="text-sm font-medium leading-snug">{item.headline}</h3>
              <p className="text-xs text-muted-foreground">{item.summary}</p>
              <div className="flex items-center justify-between pt-1">
                <div className="flex flex-wrap gap-1">
                  {item.tags.slice(0, 3).map((tag) => (
                    <span
                      key={tag}
                      className="px-1.5 py-0.5 rounded bg-muted text-[10px] font-mono text-muted-foreground"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                >
                  Source <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </article>
          ))}
        </div>
      </section>

      {showCongress && (
        <section className="space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div>
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Landmark className="h-5 w-5 text-accent" />
                US Congressional PTR Disclosures (US Market Only)
              </h2>
              <p className="text-xs text-amber-300/90 flex items-center gap-1.5 mt-0.5">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                <span>{stockActNotice}</span>
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/40 text-muted-foreground font-mono text-[11px]">
                  <tr>
                    <th className="px-4 py-2.5">Member</th>
                    <th className="px-4 py-2.5">Ticker</th>
                    <th className="px-4 py-2.5">Transaction</th>
                    <th className="px-4 py-2.5">Amount Range</th>
                    <th className="px-4 py-2.5">Trade Date</th>
                    <th className="px-4 py-2.5">Filed</th>
                    <th className="px-4 py-2.5">Disclosure Lag</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border font-mono tabular-nums">
                  {disclosures.map((d) => (
                    <tr key={d.doc_id}>
                      <td className="px-4 py-3 font-sans font-medium">
                        {d.member_name}{" "}
                        <span className="text-muted-foreground text-[11px]">({d.district})</span>
                      </td>
                      <td className="px-4 py-3 text-accent font-semibold">{d.raw_ticker}</td>
                      <td className="px-4 py-3">{d.transaction_type}</td>
                      <td className="px-4 py-3">{d.amount_range}</td>
                      <td className="px-4 py-3">{d.trade_date}</td>
                      <td className="px-4 py-3">{d.filing_date}</td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "px-2 py-0.5 rounded text-[11px]",
                            d.is_late_filing
                              ? "bg-red-500/15 text-red-400 border border-red-500/30"
                              : "bg-amber-500/15 text-amber-300"
                          )}
                        >
                          {d.disclosure_delay_days}d lag
                          {d.is_late_filing ? " (LATE)" : ""}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
