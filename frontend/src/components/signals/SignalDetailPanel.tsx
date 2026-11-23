"use client";

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  AlertCircle,
  Bot,
  Calculator,
  Check,
  Copy,
  FileText,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { TradingViewWidget } from "@/components/charts/TradingViewWidget";
const CandlestickSignalChart = dynamic(
  () => import("@/components/charts/CandlestickSignalChart").then((m) => m.CandlestickSignalChart),
  {
    ssr: false,
    loading: () => (
      <div className="h-[340px] flex items-center justify-center text-xs text-muted-foreground animate-pulse">
        Loading interactive chart...
      </div>
    ),
  }
);
import {
  calculatePositionSize,
  fetchInstrumentBars,
  type OHLCVBarItem,
  type TradingSignalItem,
} from "@/lib/api";
import { cn, formatCurrencyPrice, formatUtcTimestamp } from "@/lib/utils";

interface SignalDetailPanelProps {
  signal: TradingSignalItem;
  onClose: () => void;
}

export function SignalDetailPanel({ signal, onClose }: SignalDetailPanelProps) {
  const [chartView, setChartView] = useState<"tradingview" | "levels">("tradingview");
  const [timeframe, setTimeframe] = useState<"1d" | "15m" | "5m">("5m");
  const [bars, setBars] = useState<OHLCVBarItem[]>([]);
  const [barsLoading, setBarsLoading] = useState(true);
  const [barsError, setBarsError] = useState<string | null>(null);
  const [copiedTicket, setCopiedTicket] = useState(false);

  // Personal position sizing calculator state (never places orders)
  const [budget, setBudget] = useState(signal.currency === "INR" ? "200000" : "5000");
  const [maxLoss, setMaxLoss] = useState(signal.currency === "INR" ? "2000" : "50");
  const [sizingResult, setSizingResult] = useState<{
    shares: string | number;
    binding: string | number;
    notional: string | number;
    riskStatus: string;
  } | null>(null);
  const [sizingError, setSizingError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setBarsLoading(true);
    setBarsError(null);
    fetchInstrumentBars(signal.instrument_id, timeframe, 120)
      .then((res) => {
        if (active) setBars(res.bars);
      })
      .catch((err: unknown) => {
        if (active) {
          setBars([]);
          setBarsError(err instanceof Error ? err.message : "Bars unavailable");
        }
      })
      .finally(() => {
        if (active) setBarsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [signal.instrument_id, timeframe]);

  const handleCalculateSize = async (e: React.FormEvent) => {
    e.preventDefault();
    setSizingError(null);
    try {
      const res = await calculatePositionSize({
        market_code: signal.market_code,
        exchange_code: signal.exchange_code,
        symbol: signal.symbol,
        signal_type: signal.signal_type === "SELL" ? "SELL" : "BUY",
        entry_price: signal.entry_price,
        stop_loss: signal.stop_loss,
        target_price: signal.target_price,
        capital_budget: budget,
        max_loss_amount: maxLoss,
      });
      setSizingResult({
        shares: res.sizing.recommended_shares,
        binding: res.sizing.binding_limit,
        notional: res.sizing.position_notional,
        riskStatus: res.risk_validation.status,
      });
    } catch (err: unknown) {
      setSizingError(err instanceof Error ? err.message : "Calculation failed");
    }
  };

  const ticketSummary = String(signal.broker_ticket_preview?.formatted_summary ?? "");
  const copyTicket = () => {
    if (!ticketSummary) return;
    navigator.clipboard?.writeText(ticketSummary);
    setCopiedTicket(true);
    setTimeout(() => setCopiedTicket(false), 1800);
  };

  const tm = signal.timemachine_summary as Record<string, string | number> | undefined;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-3xl bg-background border-l border-border h-full overflow-y-auto p-5 lg:p-6 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className={cn(
                  "px-2.5 py-0.5 rounded-md text-xs font-mono font-semibold",
                  signal.signal_type === "BUY"
                    ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                    : signal.signal_type === "SELL"
                      ? "bg-red-500/15 text-red-400 border border-red-500/30"
                      : "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                )}
              >
                {signal.signal_type}
              </span>
              <h2 className="text-xl font-semibold font-mono">{signal.canonical_code}</h2>
              <span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground font-mono">
                {signal.strategy}
              </span>
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-mono">
                RISK: {signal.risk_validation_status}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              {signal.company_name} • Source: {signal.data_source_provider} • Generated{" "}
              {formatUtcTimestamp(signal.generated_at_utc)}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg border border-border hover:bg-muted"
            aria-label="Close signal details"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Exact Levels Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono tabular-nums">
          <div className="rounded-lg border border-border bg-card p-3">
            <div className="text-[11px] text-muted-foreground">Entry Price</div>
            <div className="text-base font-semibold text-sky-400 mt-0.5">
              {formatCurrencyPrice(signal.entry_price, signal.currency)}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card p-3">
            <div className="text-[11px] text-muted-foreground">Stop-Loss</div>
            <div className="text-base font-semibold text-red-400 mt-0.5">
              {formatCurrencyPrice(signal.stop_loss, signal.currency)}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card p-3">
            <div className="text-[11px] text-muted-foreground">Target Price</div>
            <div className="text-base font-semibold text-emerald-400 mt-0.5">
              {formatCurrencyPrice(signal.target_price, signal.currency)}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card p-3">
            <div className="text-[11px] text-muted-foreground">Risk / Reward</div>
            <div className="text-base font-semibold mt-0.5">{signal.risk_reward_ratio}R</div>
          </div>
        </div>

        {/* Real-time TradingView & Levels Chart */}
        <section className="rounded-xl border border-border bg-card p-4 space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="text-sm font-semibold">Interactive Chart &amp; Levels</h3>
              <p className="text-[11px] text-muted-foreground">
                {chartView === "tradingview"
                  ? "TradingView live cloud feed with real-time indicators"
                  : "Completed bars with Entry, Stop-Loss & Target overlays"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5 text-xs font-mono">
                <button
                  type="button"
                  onClick={() => setChartView("tradingview")}
                  className={cn(
                    "px-2.5 py-1 rounded flex items-center gap-1 transition-colors font-medium",
                    chartView === "tradingview"
                      ? "bg-accent text-accent-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Sparkles className="h-3 w-3" />
                  TradingView Live
                </button>
                <button
                  type="button"
                  onClick={() => setChartView("levels")}
                  className={cn(
                    "px-2.5 py-1 rounded transition-colors font-medium",
                    chartView === "levels"
                      ? "bg-accent text-accent-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Signals &amp; Levels
                </button>
              </div>

              {chartView === "levels" && (
                <div className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5 text-xs font-mono">
                  {(["5m", "15m", "1d"] as const).map((tf) => (
                    <button
                      key={tf}
                      type="button"
                      onClick={() => setTimeframe(tf)}
                      className={cn(
                        "px-2.5 py-1 rounded",
                        timeframe === tf
                          ? "bg-card text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {tf}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {chartView === "tradingview" ? (
            <TradingViewWidget
              key={signal.canonical_code}
              symbol={signal.canonical_code}
              height={460}
              interval={timeframe === "1d" ? "D" : timeframe === "15m" ? "15" : "5"}
            />
          ) : barsLoading ? (
            <div className="h-[340px] flex items-center justify-center text-xs text-muted-foreground">
              Loading completed OHLCV bars...
            </div>
          ) : barsError ? (
            <div className="h-[200px] flex items-center justify-center gap-2 text-xs text-amber-400">
              <AlertCircle className="h-4 w-4" />
              <span>{barsError}</span>
            </div>
          ) : (
            <CandlestickSignalChart
              bars={bars}
              entryPrice={Number(signal.entry_price)}
              stopLoss={Number(signal.stop_loss)}
              targetPrice={Number(signal.target_price)}
              currency={signal.currency}
            />
          )}
        </section>

        {/* Composite Setup Quality & Time Machine Replay */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <section className="rounded-xl border border-border bg-card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Setup Quality Score</h3>
              <span className="text-lg font-mono font-bold text-accent">
                {signal.confidence_score}/100
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground">{signal.confidence_label}</p>
            <div className="space-y-2">
              {Object.entries(signal.confidence_breakdown?.components ?? {}).map(([key, comp]) => {
                const pct = Math.min(100, Math.round((comp.score / comp.max) * 100));
                return (
                  <div key={key} className="space-y-1 text-xs">
                    <div className="flex justify-between font-mono">
                      <span className="capitalize text-muted-foreground">
                        {key.replaceAll("_", " ")}
                      </span>
                      <span>
                        {comp.score}/{comp.max}
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                      <div className="h-full bg-accent rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="rounded-xl border border-border bg-card p-4 space-y-3">
            <h3 className="text-sm font-semibold">Time Machine Diagnostics</h3>
            {tm ? (
              <div className="grid grid-cols-2 gap-2.5 text-xs font-mono tabular-nums">
                <div className="p-2.5 rounded-lg bg-muted/40">
                  <div className="text-muted-foreground">MC Target Reach</div>
                  <div className="text-sm font-semibold text-emerald-400">
                    {tm.mc_target_hit_prob_pct}%
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-muted/40">
                  <div className="text-muted-foreground">MC Stop Hit</div>
                  <div className="text-sm font-semibold text-red-400">
                    {tm.mc_stop_hit_prob_pct}%
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-muted/40">
                  <div className="text-muted-foreground">Expected R</div>
                  <div className="text-sm font-semibold">{tm.expected_r_multiple}R</div>
                </div>
                <div className="p-2.5 rounded-lg bg-muted/40">
                  <div className="text-muted-foreground">Session 5m Bars</div>
                  <div className="text-sm font-semibold">{tm.session_5m_bars_used} bars</div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">No Time Machine replay available.</p>
            )}
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              Statistical simulation diagnostic only — never a guarantee of future performance.
            </p>
          </section>
        </div>

        {/* AI Analyst Structured Reasoning */}
        {signal.ai_explanation && (
          <section className="rounded-xl border border-border bg-card p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-accent" />
              <h3 className="text-sm font-semibold">AI Analyst Explanation (Read-Only)</h3>
            </div>
            <p className="text-xs leading-relaxed">{signal.ai_explanation.thesis}</p>
            <p className="text-xs font-mono text-muted-foreground">
              {signal.ai_explanation.key_levels_summary}
            </p>
            <ul className="list-disc pl-4 space-y-1 text-xs text-muted-foreground">
              {signal.ai_explanation.risk_factors.map((rf, i) => (
                <li key={i}>{rf}</li>
              ))}
            </ul>
            <p className="text-[11px] text-amber-300/90 border-t border-border pt-2">
              {signal.ai_explanation.disclaimer}
            </p>
          </section>
        )}

        {/* Read-Only Broker Reference Ticket */}
        {signal.broker_ticket_preview && (
          <section className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4 space-y-2.5">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-emerald-400">
                <FileText className="h-4 w-4" />
                <h3 className="text-sm font-semibold">
                  Broker-Ready Reference Ticket (NOT EXECUTED)
                </h3>
              </div>
              <button
                type="button"
                onClick={copyTicket}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-border bg-card text-xs hover:bg-muted"
              >
                {copiedTicket ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copiedTicket ? "Copied" : "Copy"}</span>
              </button>
            </div>
            <pre className="text-xs font-mono bg-background/80 rounded-lg p-3 border border-border overflow-x-auto">
              {ticketSummary}
            </pre>
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
              <span>
                SIGNALS-ONLY mode: No live broker integration exists. Execute manually in your own
                broker if you choose.
              </span>
            </div>
          </section>
        )}

        {/* Personal Position Sizing Calculator */}
        <section className="rounded-xl border border-border bg-card p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Calculator className="h-4 w-4 text-accent" />
            <h3 className="text-sm font-semibold">
              Personal Position Size Calculator ({signal.currency})
            </h3>
          </div>
          <form onSubmit={handleCalculateSize} className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-[11px] text-muted-foreground block mb-1">
                Capital Budget ({signal.currency})
              </label>
              <input
                type="number"
                step="any"
                required
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-mono"
              />
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground block mb-1">
                Max Loss Per Trade ({signal.currency})
              </label>
              <input
                type="number"
                step="any"
                required
                value={maxLoss}
                onChange={(e) => setMaxLoss(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-mono"
              />
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                className="w-full rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-accent-foreground hover:opacity-90"
              >
                Calculate Shares
              </button>
            </div>
          </form>
          {sizingError && <p className="text-xs text-red-400">{sizingError}</p>}
          {sizingResult && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono pt-2 border-t border-border">
              <div>
                <div className="text-muted-foreground">Recommended Qty</div>
                <div className="font-semibold text-accent">{sizingResult.shares} shares</div>
              </div>
              <div>
                <div className="text-muted-foreground">Binding Cap</div>
                <div className="font-semibold">{sizingResult.binding}</div>
              </div>
              <div>
                <div className="text-muted-foreground">Notional</div>
                <div className="font-semibold">
                  {formatCurrencyPrice(sizingResult.notional, signal.currency)}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Risk Gate</div>
                <div className="font-semibold text-emerald-400">{sizingResult.riskStatus}</div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
