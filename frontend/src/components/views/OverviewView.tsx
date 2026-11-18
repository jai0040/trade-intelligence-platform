"use client";

import React from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Newspaper,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import type {
  IndexSnapshot,
  MarketNewsItem,
  MarketStatusItem,
  PerformanceSummary,
  TradingSignalItem,
} from "@/lib/api";
import type { MarketScope } from "@/components/layout/AppShell";
import { cn, formatCurrencyPrice, formatUtcTimestamp } from "@/lib/utils";

interface OverviewViewProps {
  marketScope: MarketScope;
  marketStatuses: MarketStatusItem[];
  indices: IndexSnapshot[];
  signals: TradingSignalItem[];
  news: MarketNewsItem[];
  performance: PerformanceSummary | null;
  onSelectSignal: (signal: TradingSignalItem) => void;
  onOpenScanner: () => void;
}

export function OverviewView({
  marketScope,
  marketStatuses,
  indices,
  signals,
  news,
  performance,
  onSelectSignal,
  onOpenScanner,
}: OverviewViewProps) {
  const scopedStatuses = marketStatuses.filter(
    (m) => marketScope === "ALL" || m.market_code === marketScope
  );
  const scopedIndices = indices.filter(
    (idx) => marketScope === "ALL" || idx.market_code === marketScope
  );
  const scopedSignals = signals.filter(
    (s) => marketScope === "ALL" || s.market_code === marketScope
  );
  const scopedNews = news.filter(
    (n) => marketScope === "ALL" || n.market_code === marketScope
  );

  const buyCount = scopedSignals.filter((s) => s.signal_type === "BUY").length;
  const sellCount = scopedSignals.filter((s) => s.signal_type === "SELL").length;
  const watchCount = scopedSignals.filter((s) => s.signal_type === "WATCH").length;
  const anyStale = scopedStatuses.some((m) => m.data_freshness.is_stale);

  return (
    <div className="space-y-6">
      {anyStale && (
        <div
          role="status"
          className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-xs text-amber-200 flex items-center gap-2.5"
        >
          <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
          <span>
            One or more market data feeds are reporting delayed or stale quotes. New signal
            triggers are automatically blocked by trader-risk until fresh data resumes.
          </span>
        </div>
      )}

      {/* KPI Summary Row */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border bg-card p-4 space-y-1">
          <div className="text-xs text-muted-foreground">Risk-Validated Signals</div>
          <div className="text-2xl font-bold font-mono tabular-nums">{scopedSignals.length}</div>
          <div className="text-[11px] text-emerald-400 flex items-center gap-1">
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>100% trader-risk PASSED</span>
          </div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 space-y-1">
          <div className="text-xs text-muted-foreground">BUY / SELL / WATCH</div>
          <div className="text-2xl font-bold font-mono tabular-nums flex items-center gap-2">
            <span className="text-emerald-400">{buyCount}</span>
            <span className="text-muted-foreground text-base">/</span>
            <span className="text-red-400">{sellCount}</span>
            <span className="text-muted-foreground text-base">/</span>
            <span className="text-amber-400">{watchCount}</span>
          </div>
          <div className="text-[11px] text-muted-foreground">Signals-Only • Never auto-traded</div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 space-y-1">
          <div className="text-xs text-muted-foreground">Historical Win Rate</div>
          <div className="text-2xl font-bold font-mono tabular-nums">
            {performance ? `${performance.win_rate_pct}%` : "—"}
          </div>
          <div className="text-[11px] text-muted-foreground">
            {performance ? `${performance.closed_trades} closed outcomes (net of bps)` : "Awaiting outcomes"}
          </div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 space-y-1">
          <div className="text-xs text-muted-foreground">Avg Realized R</div>
          <div className="text-2xl font-bold font-mono tabular-nums">
            {performance ? `${performance.avg_realized_r_multiple}R` : "—"}
          </div>
          <div className="text-[11px] text-muted-foreground">15 bps IN / 8 bps US cost model</div>
        </div>
      </section>

      {/* Exchange Live Status & Benchmark Indices */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-border bg-card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <Clock className="h-4 w-4 text-accent" />
              Exchange Session Status &amp; Feed Freshness
            </h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {scopedStatuses.map((ms) => (
              <div
                key={ms.exchange_code}
                className="rounded-lg border border-border bg-background/60 p-3 space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-semibold">
                    {ms.exchange_code} ({ms.market_code})
                  </span>
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded-full text-[10px] font-mono",
                      ms.is_open
                        ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                        : "bg-muted text-muted-foreground"
                    )}
                  >
                    {ms.session_phase}
                  </span>
                </div>
                <div className="text-[11px] text-muted-foreground truncate">
                  {ms.session_reason} • {ms.session_5m_bars} bars
                </div>
                <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground">
                  <span>Feed: {ms.data_freshness.provider}</span>
                  <span
                    className={
                      ms.data_freshness.is_stale ? "text-amber-400" : "text-emerald-400"
                    }
                  >
                    {ms.data_freshness.status} ({ms.data_freshness.delay_seconds}s)
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-5 space-y-3">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-accent" />
            Benchmark Indices
          </h2>
          {scopedIndices.length === 0 ? (
            <p className="text-xs text-muted-foreground py-6 text-center">
              Benchmark index quotes unavailable.
            </p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {scopedIndices.map((idx) => {
                const positive = Number(idx.change) >= 0;
                return (
                  <div
                    key={idx.canonical_code}
                    className="rounded-lg border border-border bg-background/60 p-3 space-y-1 font-mono tabular-nums"
                  >
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-semibold text-foreground">{idx.symbol}</span>
                      <span className="text-[10px] text-muted-foreground">{idx.market_code}</span>
                    </div>
                    <div className="text-sm font-bold">
                      {formatCurrencyPrice(idx.last_price, idx.currency)}
                    </div>
                    <div
                      className={cn(
                        "text-[11px] flex items-center gap-0.5",
                        positive ? "text-emerald-400" : "text-red-400"
                      )}
                    >
                      {positive ? (
                        <ArrowUpRight className="h-3 w-3" />
                      ) : (
                        <ArrowDownRight className="h-3 w-3" />
                      )}
                      <span>
                        {positive ? "+" : ""}
                        {idx.change_pct}%
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* Top Risk-Validated Trading Opportunities */}
      <section className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-accent" />
              Top Trading Opportunities (Click any row for Chart, Ticket &amp; Sizing)
            </h2>
            <p className="text-[11px] text-muted-foreground">
              Deterministic levels validated by trader-risk • Composite Quality Score ≠ win probability
            </p>
          </div>
          <button
            type="button"
            onClick={onOpenScanner}
            className="text-xs font-medium text-accent hover:underline"
          >
            View All →
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/40 text-muted-foreground font-mono text-[11px]">
              <tr>
                <th className="px-4 py-2.5">Instrument</th>
                <th className="px-4 py-2.5">Side</th>
                <th className="px-4 py-2.5">Strategy</th>
                <th className="px-4 py-2.5 text-right">Entry</th>
                <th className="px-4 py-2.5 text-right">Stop-Loss</th>
                <th className="px-4 py-2.5 text-right">Target</th>
                <th className="px-4 py-2.5 text-right">R:R</th>
                <th className="px-4 py-2.5 text-right">Quality</th>
                <th className="px-4 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono tabular-nums">
              {scopedSignals.slice(0, 8).map((sig) => (
                <tr
                  key={sig.id}
                  onClick={() => onSelectSignal(sig)}
                  className="hover:bg-muted/40 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3">
                    <div className="font-semibold text-foreground">{sig.canonical_code}</div>
                    <div className="font-sans text-[11px] text-muted-foreground truncate max-w-[180px]">
                      {sig.company_name}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "px-2 py-0.5 rounded text-[11px] font-semibold",
                        sig.signal_type === "BUY"
                          ? "bg-emerald-500/15 text-emerald-400"
                          : sig.signal_type === "SELL"
                            ? "bg-red-500/15 text-red-400"
                            : "bg-amber-500/15 text-amber-400"
                      )}
                    >
                      {sig.signal_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{sig.strategy}</td>
                  <td className="px-4 py-3 text-right text-sky-400">
                    {formatCurrencyPrice(sig.entry_price, sig.currency)}
                  </td>
                  <td className="px-4 py-3 text-right text-red-400">
                    {formatCurrencyPrice(sig.stop_loss, sig.currency)}
                  </td>
                  <td className="px-4 py-3 text-right text-emerald-400">
                    {formatCurrencyPrice(sig.target_price, sig.currency)}
                  </td>
                  <td className="px-4 py-3 text-right">{sig.risk_reward_ratio}R</td>
                  <td className="px-4 py-3 text-right font-semibold text-accent">
                    {sig.confidence_score}
                  </td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded bg-muted text-[11px]">
                      {sig.current_status}
                    </span>
                  </td>
                </tr>
              ))}
              {scopedSignals.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center font-sans text-muted-foreground">
                    No active risk-validated signals in this market scope yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Latest Market News & Regulatory Filings Preview */}
      <section className="rounded-xl border border-border bg-card p-5 space-y-3">
        <h2 className="text-sm font-semibold flex items-center gap-2">
          <Newspaper className="h-4 w-4 text-accent" />
          Latest Filings &amp; Catalyst Headlines
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {scopedNews.slice(0, 4).map((item, idx) => (
            <div
              key={`${item.canonical_code}-${idx}`}
              className="rounded-lg border border-border bg-background/60 p-3 space-y-1"
            >
              <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground">
                <span className="text-accent">{item.canonical_code}</span>
                <span>
                  {item.source} • {formatUtcTimestamp(item.published_at_utc)}
                </span>
              </div>
              <div className="text-xs font-medium leading-snug">{item.headline}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
