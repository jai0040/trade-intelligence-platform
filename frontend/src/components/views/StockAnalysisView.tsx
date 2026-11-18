"use client";

import React, { useEffect, useState } from "react";
import { LineChart, Search } from "lucide-react";
import { CandlestickSignalChart } from "@/components/charts/CandlestickSignalChart";
import type { MarketScope } from "@/components/layout/AppShell";
import {
  fetchInstrumentBars,
  searchInstruments,
  type InstrumentSummary,
  type OHLCVBarItem,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface StockAnalysisViewProps {
  marketScope: MarketScope;
}

export function StockAnalysisView({ marketScope }: StockAnalysisViewProps) {
  const [query, setQuery] = useState("RELIANCE");
  const [results, setResults] = useState<InstrumentSummary[]>([]);
  const [selected, setSelected] = useState<InstrumentSummary | null>(null);
  const [timeframe, setTimeframe] = useState<"1d" | "15m" | "5m">("5m");
  const [bars, setBars] = useState<OHLCVBarItem[]>([]);
  const [loading, setLoading] = useState(false);

  const runSearch = async (q: string) => {
    if (!q.trim()) return;
    try {
      const list = await searchInstruments(q.trim(), marketScope);
      setResults(list);
      if (list.length > 0 && !selected) {
        setSelected(list[0]);
      }
    } catch {
      setResults([]);
    }
  };

  useEffect(() => {
    runSearch(marketScope === "US" ? "TSLA" : "RELIANCE");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [marketScope]);

  useEffect(() => {
    if (!selected) return;
    let active = true;
    setLoading(true);
    fetchInstrumentBars(selected.instrument_id, timeframe, 150)
      .then((res) => {
        if (active) setBars(res.bars);
      })
      .catch(() => {
        if (active) setBars([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selected, timeframe]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <LineChart className="h-5 w-5 text-accent" />
            Stock Analysis &amp; TradingView Charts
          </h1>
          <p className="text-xs text-muted-foreground">
            Search NSE/BSE (e.g. RELIANCE, M&amp;M, NIFTYBEES) or NASDAQ/NYSE (e.g. TSLA, NVDA, BRK.B)
          </p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            runSearch(query);
          }}
          className="flex gap-2"
        >
          <div className="relative">
            <Search className="h-3.5 w-3.5 text-muted-foreground absolute left-2.5 top-2.5" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ticker (M&M, BRK.B...)"
              className="pl-8 pr-3 py-1.5 rounded-lg border border-border bg-card text-xs outline-none focus:border-accent"
            />
          </div>
          <button
            type="submit"
            className="px-3 py-1.5 rounded-lg bg-accent text-accent-foreground text-xs font-semibold"
          >
            Search
          </button>
        </form>
      </div>

      {results.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {results.slice(0, 10).map((inst) => (
            <button
              key={inst.instrument_id}
              type="button"
              onClick={() => setSelected(inst)}
              className={cn(
                "px-3 py-1.5 rounded-lg border text-xs font-mono transition-colors",
                selected?.instrument_id === inst.instrument_id
                  ? "border-accent bg-accent/15 text-accent"
                  : "border-border bg-card text-muted-foreground hover:text-foreground"
              )}
            >
              {inst.canonical_code}
            </button>
          ))}
        </div>
      )}

      {selected && (
        <section className="rounded-xl border border-border bg-card p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold font-mono">{selected.canonical_code}</h2>
              <p className="text-xs text-muted-foreground">
                {selected.company_name} • {selected.asset_type} • Tick {selected.tick_size}{" "}
                {selected.currency} • {selected.sector ?? "Equity"}
              </p>
            </div>
            <div className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5 text-xs font-mono">
              {(["5m", "15m", "1d"] as const).map((tf) => (
                <button
                  key={tf}
                  type="button"
                  onClick={() => setTimeframe(tf)}
                  className={cn(
                    "px-2.5 py-1 rounded",
                    timeframe === tf ? "bg-card text-foreground" : "text-muted-foreground"
                  )}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="h-[380px] flex items-center justify-center text-xs text-muted-foreground">
              Loading completed bars...
            </div>
          ) : (
            <CandlestickSignalChart
              bars={bars}
              currency={selected.currency}
              height={380}
            />
          )}
        </section>
      )}
    </div>
  );
}
