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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-2 sm:p-4 lg:p-6"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-7xl max-h-[94vh] bg-background border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Sticky Header */}
        <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4 bg-card/70 backdrop-blur-sm shrink-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span
              className={cn(
                "px-2.5 py-0.5 rounded-md text-xs font-mono font-bold uppercase",
                signal.signal_type === "BUY"
                  ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                  : signal.signal_type === "SELL"
                    ? "bg-red-500/15 text-red-400 border border-red-500/30"
                    : "bg-amber-500/15 text-amber-400 border border-amber-500/30"
              )}
            >
              {signal.signal_type}
            </span>
            <h2 className="text-xl font-bold font-mono tracking-tight">{signal.canonical_code}</h2>
            <span className="text-xs px-2.5 py-0.5 rounded-md bg-muted text-muted-foreground font-mono">
              {signal.strategy}
            </span>
            <span className="text-xs px-2.5 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-mono">
              RISK: {signal.risk_validation_status}
            </span>
            <span className="text-xs text-muted-foreground hidden sm:inline">
              {signal.company_name} • {signal.data_source_provider === "angelone" ? "AngelOne Live" : "Data Provider: " + signal.data_source_provider}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {ticketSummary && (
              <button
                type="button"
                onClick={copyTicket}
                className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card text-xs font-medium hover:bg-muted transition-colors"
              >
                {copiedTicket ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copiedTicket ? "Ticket Copied" : "Copy Ticket"}</span>
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg border border-border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
              aria-label="Close signal details"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Scrollable 2-Column Workstation Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* LEFT COLUMN: Chart, Levels & Execution Tools (7 Cols) */}
            <div className="lg:col-span-7 space-y-4">
              {/* Exact Levels Strip */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono tabular-nums">
                <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
                  <div className="text-[11px] text-muted-foreground uppercase font-medium">Entry Price</div>
                  <div className="text-base font-bold text-sky-400 mt-0.5">
                    {formatCurrencyPrice(signal.entry_price, signal.currency)}
                  </div>
                </div>
                <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
                  <div className="text-[11px] text-muted-foreground uppercase font-medium">Stop-Loss</div>
                  <div className="text-base font-bold text-red-400 mt-0.5">
                    {formatCurrencyPrice(signal.stop_loss, signal.currency)}
                  </div>
                </div>
                <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
                  <div className="text-[11px] text-muted-foreground uppercase font-medium">Target Price</div>
                  <div className="text-base font-bold text-emerald-400 mt-0.5">
                    {formatCurrencyPrice(signal.target_price, signal.currency)}
                  </div>
                </div>
                <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
                  <div className="text-[11px] text-muted-foreground uppercase font-medium">Risk / Reward</div>
                  <div className="text-base font-bold text-foreground mt-0.5">{signal.risk_reward_ratio}R</div>
                </div>
              </div>

              {/* Interactive Chart & Levels */}
              <section className="rounded-xl border border-border bg-card p-4 space-y-3 shadow-sm">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <h3 className="text-sm font-semibold flex items-center gap-1.5">
                      Interactive Chart &amp; Levels
                    </h3>
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

                    <div className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5 text-xs font-mono">
                      {(["5m", "15m", "1d"] as const).map((tf) => (
                        <button
                          key={tf}
                          type="button"
                          onClick={() => setTimeframe(tf)}
                          className={cn(
                            "px-2 py-1 rounded",
                            timeframe === tf
                              ? "bg-card text-foreground shadow-sm font-semibold"
                              : "text-muted-foreground hover:text-foreground"
                          )}
                        >
                          {tf}
                        </button>
                      ))}
                    </div>
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
                
                <div className="text-[11px] text-muted-foreground bg-muted/30 rounded-lg px-3 py-2 flex items-center justify-between">
                  <span>
                    {chartView === "tradingview"
                      ? "⚡ Live Cloud Feed: Real-time exchange quotes. Switch to 'Signals & Levels' to view exact entry/stop overlays."
                      : "🎯 Quant Model Replay: Plots completed bars with Entry, Stop-Loss, and Target price overlays."}
                  </span>
                  <span className="font-mono text-[10px]">As of {formatUtcTimestamp(signal.generated_at_utc)}</span>
                </div>
              </section>

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
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-border bg-card text-xs hover:bg-muted transition-colors font-medium"
                    >
                      {copiedTicket ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                      <span>{copiedTicket ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                  <pre className="text-xs font-mono bg-background/90 rounded-lg p-3 border border-border overflow-x-auto select-all">
                    {ticketSummary}
                  </pre>
                  <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <ShieldCheck className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                    <span>
                      SIGNALS-ONLY mode: No live broker orders are placed automatically. Execute manually in your own broker.
                    </span>
                  </div>
                </section>
              )}

              {/* Position Sizing Calculator */}
              <section className="rounded-xl border border-border bg-card p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Calculator className="h-4 w-4 text-accent" />
                  <h3 className="text-sm font-semibold">
                    Position Size Calculator ({signal.currency})
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
                      className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-mono outline-none focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-muted-foreground block mb-1">
                      Max Loss Budget ({signal.currency})
                    </label>
                    <input
                      type="number"
                      step="any"
                      required
                      value={maxLoss}
                      onChange={(e) => setMaxLoss(e.target.value)}
                      className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-mono outline-none focus:border-accent"
                    />
                  </div>
                  <div className="flex items-end">
                    <button
                      type="submit"
                      className="w-full rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-accent-foreground hover:opacity-90 transition-opacity"
                    >
                      Calculate Shares
                    </button>
                  </div>
                </form>
                {sizingError && <p className="text-xs text-red-400">{sizingError}</p>}
                {sizingResult && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono pt-2 border-t border-border">
                    <div>
                      <div className="text-muted-foreground">Shares</div>
                      <div className="font-semibold text-accent">{sizingResult.shares} shares</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Binding Limit</div>
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

            {/* RIGHT COLUMN: AI Analyst, Scores & Time Machine (5 Cols) */}
            <div className="lg:col-span-5 space-y-4">
              {/* Setup Quality Score Card */}
              <section className="rounded-xl border border-border bg-card p-4 space-y-3 shadow-sm">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold">Setup Quality Score</h3>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-mono font-bold text-accent">
                      {signal.confidence_score}
                    </span>
                    <span className="text-xs text-muted-foreground font-mono">/100</span>
                  </div>
                </div>
                <p className="text-[11px] text-muted-foreground">{signal.confidence_label}</p>
                <div className="space-y-2 pt-1">
                  {Object.entries(signal.confidence_breakdown?.components ?? {}).map(([key, comp]) => {
                    const pct = Math.min(100, Math.round((comp.score / comp.max) * 100));
                    return (
                      <div key={key} className="space-y-1 text-xs">
                        <div className="flex justify-between font-mono">
                          <span className="capitalize text-muted-foreground">
                            {key.replaceAll("_", " ")}
                          </span>
                          <span className="font-semibold">
                            {comp.score}/{comp.max}
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                          <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Time Machine Diagnostics */}
              <section className="rounded-xl border border-border bg-card p-4 space-y-3 shadow-sm">
                <h3 className="text-sm font-semibold">Time Machine Diagnostics</h3>
                {tm ? (
                  <div className="grid grid-cols-2 gap-2.5 text-xs font-mono tabular-nums">
                    <div className="p-2.5 rounded-lg bg-muted/40">
                      <div className="text-muted-foreground text-[11px]">MC Target Reach</div>
                      <div className="text-base font-bold text-emerald-400">
                        {tm.mc_target_hit_prob_pct}%
                      </div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-muted/40">
                      <div className="text-muted-foreground text-[11px]">MC Stop Hit</div>
                      <div className="text-base font-bold text-red-400">
                        {tm.mc_stop_hit_prob_pct}%
                      </div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-muted/40">
                      <div className="text-muted-foreground text-[11px]">Expected R</div>
                      <div className="text-base font-bold">{tm.expected_r_multiple}R</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-muted/40">
                      <div className="text-muted-foreground text-[11px]">Session 5m Bars</div>
                      <div className="text-base font-bold">{tm.session_5m_bars_used} bars</div>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">No Time Machine replay available.</p>
                )}
                <p className="text-[10px] text-muted-foreground leading-relaxed">
                  Statistical simulation diagnostic only — never a guarantee of future performance.
                </p>
              </section>

              {/* AI Analyst Structured Reasoning */}
              {signal.ai_explanation && (
                <section className="rounded-xl border border-border bg-card p-4 space-y-3 shadow-sm">
                  <div className="flex items-center gap-2 text-accent">
                    <Bot className="h-4 w-4" />
                    <h3 className="text-sm font-semibold text-foreground">AI Analyst Explanation (Read-Only)</h3>
                  </div>
                  <p className="text-xs leading-relaxed text-foreground/90 font-medium">{signal.ai_explanation.thesis}</p>
                  <p className="text-xs font-mono text-muted-foreground bg-muted/40 p-2 rounded-lg">
                    {signal.ai_explanation.key_levels_summary}
                  </p>
                  <div>
                    <div className="text-[11px] font-semibold text-muted-foreground mb-1.5 uppercase">Key Risk Factors:</div>
                    <ul className="list-disc pl-4 space-y-1 text-xs text-muted-foreground">
                      {signal.ai_explanation.risk_factors.map((rf, i) => (
                        <li key={i}>{rf}</li>
                      ))}
                    </ul>
                  </div>
                  <p className="text-[11px] text-amber-300/90 border-t border-border pt-2 leading-relaxed">
                    {signal.ai_explanation.disclaimer}
                  </p>
                </section>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
