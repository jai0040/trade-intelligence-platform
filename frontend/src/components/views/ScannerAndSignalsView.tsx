"use client";

import React, { useMemo, useState } from "react";
import { Filter, Search } from "lucide-react";
import type { MarketScope } from "@/components/layout/AppShell";
import type { ScannerHit, TradingSignalItem } from "@/lib/api";
import { cn, formatCurrencyPrice } from "@/lib/utils";

interface ScannerAndSignalsViewProps {
  mode: "scanner" | "opportunities";
  title: string;
  marketScope: MarketScope;
  scannerHits: ScannerHit[];
  signals: TradingSignalItem[];
  onSelectSignal: (signal: TradingSignalItem) => void;
}

export function ScannerAndSignalsView({
  mode,
  title,
  marketScope,
  scannerHits,
  signals,
  onSelectSignal,
}: ScannerAndSignalsViewProps) {
  const [search, setSearch] = useState("");
  const [sideFilter, setSideFilter] = useState<"ALL" | "BUY" | "SELL" | "WATCH">("ALL");
  const [sortBy, setSortBy] = useState<"confidence" | "rr" | "symbol">("confidence");
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const filteredSignals = useMemo(() => {
    const q = search.trim().toUpperCase();
    const list = signals.filter((s) => {
      if (marketScope !== "ALL" && s.market_code !== marketScope) return false;
      if (sideFilter !== "ALL" && s.signal_type !== sideFilter) return false;
      if (q && !s.symbol.toUpperCase().includes(q) && !s.company_name.toUpperCase().includes(q)) {
        return false;
      }
      return true;
    });
    return list.sort((a, b) => {
      if (sortBy === "rr") return Number(b.risk_reward_ratio) - Number(a.risk_reward_ratio);
      if (sortBy === "symbol") return a.symbol.localeCompare(b.symbol);
      return b.confidence_score - a.confidence_score;
    });
  }, [signals, marketScope, sideFilter, search, sortBy]);

  const filteredHits = useMemo(() => {
    const q = search.trim().toUpperCase();
    return scannerHits.filter((h) => {
      if (marketScope !== "ALL" && h.market_code !== marketScope) return false;
      if (sideFilter !== "ALL" && h.signal_bias !== sideFilter) return false;
      if (q && !h.symbol.toUpperCase().includes(q) && !h.company_name.toUpperCase().includes(q)) {
        return false;
      }
      return true;
    });
  }, [scannerHits, marketScope, sideFilter, search]);

  const totalItems = mode === "scanner" ? filteredHits.length : filteredSignals.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const safePage = Math.min(page, totalPages);

  return (
    <div className="space-y-4">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          <p className="text-xs text-muted-foreground">
            Scope: {marketScope === "ALL" ? "India + US Markets" : marketScope === "IN" ? "India (NSE/BSE)" : "US (NASDAQ/NYSE)"} • {totalItems} matched entries
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="h-3.5 w-3.5 text-muted-foreground absolute left-2.5 top-2.5" />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search ticker or company..."
              className="pl-8 pr-3 py-1.5 rounded-lg border border-border bg-card text-xs outline-none focus:border-accent"
            />
          </div>

          <div className="inline-flex items-center rounded-lg border border-border bg-card p-0.5 text-xs">
            <Filter className="h-3.5 w-3.5 text-muted-foreground mx-1.5" />
            {(["ALL", "BUY", "SELL", "WATCH"] as const).map((side) => (
              <button
                key={side}
                type="button"
                onClick={() => {
                  setSideFilter(side);
                  setPage(1);
                }}
                className={cn(
                  "px-2 py-1 rounded font-mono text-[11px]",
                  sideFilter === side
                    ? "bg-accent/15 text-accent"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {side}
              </button>
            ))}
          </div>

          {mode === "opportunities" && (
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as "confidence" | "rr" | "symbol")}
              className="rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs"
            >
              <option value="confidence">Sort: Quality Score</option>
              <option value="rr">Sort: Risk/Reward</option>
              <option value="symbol">Sort: Symbol A-Z</option>
            </select>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="overflow-x-auto">
          {mode === "scanner" ? (
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/40 text-muted-foreground font-mono text-[11px]">
                <tr>
                  <th className="px-4 py-2.5">Symbol</th>
                  <th className="px-4 py-2.5">Market</th>
                  <th className="px-4 py-2.5">Bias</th>
                  <th className="px-4 py-2.5">Rule Matched</th>
                  <th className="px-4 py-2.5 text-right">Last Price</th>
                  <th className="px-4 py-2.5 text-right">Key Level</th>
                  <th className="px-4 py-2.5 text-right">Vol Ratio</th>
                  <th className="px-4 py-2.5 text-right">RSI(14)</th>
                  <th className="px-4 py-2.5">Provider</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border font-mono tabular-nums">
                {filteredHits
                  .slice((safePage - 1) * pageSize, safePage * pageSize)
                  .map((hit, idx) => (
                    <tr key={`${hit.canonical_code}-${hit.setup_type}-${idx}`} className="hover:bg-muted/30">
                      <td className="px-4 py-3">
                        <div className="font-semibold">{hit.canonical_code}</div>
                        <div className="font-sans text-[11px] text-muted-foreground">
                          {hit.company_name}
                        </div>
                      </td>
                      <td className="px-4 py-3">{hit.market_code}</td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "px-2 py-0.5 rounded text-[11px] font-semibold",
                            hit.signal_bias === "BUY"
                              ? "bg-emerald-500/15 text-emerald-400"
                              : hit.signal_bias === "SELL"
                                ? "bg-red-500/15 text-red-400"
                                : "bg-amber-500/15 text-amber-400"
                          )}
                        >
                          {hit.signal_bias}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{hit.setup_type}</td>
                      <td className="px-4 py-3 text-right">
                        {formatCurrencyPrice(hit.last_price, hit.currency)}
                      </td>
                      <td className="px-4 py-3 text-right text-sky-400">
                        {formatCurrencyPrice(hit.level_price, hit.currency)}
                      </td>
                      <td className="px-4 py-3 text-right">{hit.volume_ratio}x</td>
                      <td className="px-4 py-3 text-right">{hit.rsi_14}</td>
                      <td className="px-4 py-3 text-muted-foreground">{hit.source_provider}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          ) : (
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
                {filteredSignals
                  .slice((safePage - 1) * pageSize, safePage * pageSize)
                  .map((sig) => (
                    <tr
                      key={sig.id}
                      onClick={() => onSelectSignal(sig)}
                      className="hover:bg-muted/40 cursor-pointer"
                    >
                      <td className="px-4 py-3">
                        <div className="font-semibold">{sig.canonical_code}</div>
                        <div className="font-sans text-[11px] text-muted-foreground">
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
                      <td className="px-4 py-3">{sig.current_status}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination Footer */}
        <div className="px-4 py-3 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Page {safePage} of {totalPages} ({totalItems} records)
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={safePage <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="px-2.5 py-1 rounded border border-border disabled:opacity-40 hover:bg-muted"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={safePage >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="px-2.5 py-1 rounded border border-border disabled:opacity-40 hover:bg-muted"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
