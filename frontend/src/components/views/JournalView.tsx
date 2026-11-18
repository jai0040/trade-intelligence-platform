"use client";

import React, { useEffect, useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  DollarSign,
  Plus,
  Smile,
  Trash2,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";
import {
  createJournalEntry,
  deleteJournalEntry,
  fetchJournal,
  searchInstruments,
  updateJournalEntry,
  type InstrumentSummary,
  type JournalEntry,
  type JournalStats,
} from "@/lib/api";
import { cn, formatCurrencyPrice, formatUtcTimestamp } from "@/lib/utils";

const PRESET_EMOTIONS = [
  "FOLLOWED_PLAN",
  "PATIENT",
  "FOMO",
  "EARLY_EXIT",
  "REVENGE",
  "OVERCONFIDENT",
  "HESITANT",
  "DISCIPLINED",
];

export function JournalView() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [stats, setStats] = useState<JournalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [sideFilter, setSideFilter] = useState<string>("");
  const [currencyFilter, setCurrencyFilter] = useState<string>("");

  // New trade entry form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [instrumentQuery, setInstrumentQuery] = useState("");
  const [instrumentMatches, setInstrumentMatches] = useState<InstrumentSummary[]>([]);
  const [selectedInstrument, setSelectedInstrument] = useState<InstrumentSummary | null>(null);
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [entryPrice, setEntryPrice] = useState("");
  const [quantity, setQuantity] = useState("10");
  const [currency, setCurrency] = useState<"INR" | "USD">("INR");
  const [plannedStop, setPlannedStop] = useState("");
  const [plannedTarget, setPlannedTarget] = useState("");
  const [notes, setNotes] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>(["FOLLOWED_PLAN"]);
  const [submitting, setSubmitting] = useState(false);

  // Close trade modal state
  const [closingEntry, setClosingEntry] = useState<JournalEntry | null>(null);
  const [exitPriceInput, setExitPriceInput] = useState("");
  const [closingTags, setClosingTags] = useState<string[]>([]);
  const [closingNotes, setClosingNotes] = useState("");

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await fetchJournal({
        side: sideFilter || undefined,
        currency: currencyFilter || undefined,
        limit: 100,
      });
      setEntries(res.items);
      setStats(res.stats);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load journal");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sideFilter, currencyFilter]);

  const handleInstrumentSearch = async (val: string) => {
    setInstrumentQuery(val);
    if (val.trim().length >= 1) {
      try {
        const matches = await searchInstruments(val.trim());
        setInstrumentMatches(matches.slice(0, 5));
      } catch {
        setInstrumentMatches([]);
      }
    } else {
      setInstrumentMatches([]);
    }
  };

  const toggleTag = (tag: string, list: string[], setter: (v: string[]) => void) => {
    if (list.includes(tag)) {
      setter(list.filter((t) => t !== tag));
    } else {
      setter([...list, tag]);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInstrument) {
      setError("Please search and select an instrument.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await createJournalEntry({
        instrument_id: selectedInstrument.instrument_id,
        market_id: selectedInstrument.market_code === "IN" ? "00000000-0000-0000-0000-000000000001" : "00000000-0000-0000-0000-000000000002",
        side,
        entry_price: entryPrice,
        quantity,
        currency,
        planned_stop: plannedStop || null,
        planned_target: plannedTarget || null,
        emotions_tags: selectedTags,
        notes: notes || null,
      });
      setShowAddForm(false);
      setSelectedInstrument(null);
      setInstrumentQuery("");
      setEntryPrice("");
      setPlannedStop("");
      setPlannedTarget("");
      setNotes("");
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create entry");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCloseTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!closingEntry || !exitPriceInput) return;
    try {
      await updateJournalEntry(closingEntry.id, {
        exit_price: exitPriceInput,
        emotions_tags: closingTags,
        notes: closingNotes || closingEntry.notes,
      });
      setClosingEntry(null);
      setExitPriceInput("");
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to close trade");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteJournalEntry(id);
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete entry");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-accent" />
            Personal Trading Journal
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Strictly isolated to your account. Track your executed trades, emotions, and net realized P&amp;L.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowAddForm(!showAddForm)}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-accent text-accent-foreground text-xs font-semibold hover:opacity-90 transition-opacity self-start sm:self-auto"
        >
          <Plus className="h-4 w-4" />
          <span>{showAddForm ? "Cancel" : "Log Trade"}</span>
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-300">
          {error}
        </div>
      )}

      {/* KPI Cards */}
      {stats && (
        <section className="grid grid-cols-2 lg:grid-cols-5 gap-3 font-mono tabular-nums">
          <div className="rounded-xl border border-border bg-card p-4 space-y-1">
            <div className="text-[11px] text-muted-foreground">Total / Open</div>
            <div className="text-xl font-bold">
              {stats.total_trades} <span className="text-xs text-muted-foreground font-normal">({stats.open_trades} open)</span>
            </div>
            <div className="text-[10px] text-muted-foreground">Recorded trades</div>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 space-y-1">
            <div className="text-[11px] text-muted-foreground">Win Rate</div>
            <div className="text-xl font-bold text-accent">{stats.win_rate_pct}%</div>
            <div className="text-[10px] text-muted-foreground">
              {stats.winning_trades}W / {stats.losing_trades}L
            </div>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 space-y-1">
            <div className="text-[11px] text-muted-foreground">Realized P&amp;L (INR)</div>
            <div className={cn("text-xl font-bold", Number(stats.total_realized_pnl_inr) >= 0 ? "text-emerald-400" : "text-red-400")}>
              {formatCurrencyPrice(stats.total_realized_pnl_inr, "INR")}
            </div>
            <div className="text-[10px] text-muted-foreground">Closed NSE/BSE</div>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 space-y-1">
            <div className="text-[11px] text-muted-foreground">Realized P&amp;L (USD)</div>
            <div className={cn("text-xl font-bold", Number(stats.total_realized_pnl_usd) >= 0 ? "text-emerald-400" : "text-red-400")}>
              {formatCurrencyPrice(stats.total_realized_pnl_usd, "USD")}
            </div>
            <div className="text-[10px] text-muted-foreground">Closed US</div>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 space-y-1">
            <div className="text-[11px] text-muted-foreground">Profit Factor</div>
            <div className="text-xl font-bold">
              {stats.profit_factor ? `${stats.profit_factor}x` : "—"}
            </div>
            <div className="text-[10px] text-muted-foreground">Gains / Losses ratio</div>
          </div>
        </section>
      )}

      {/* Log Trade Form */}
      {showAddForm && (
        <form onSubmit={handleCreate} className="rounded-xl border border-accent/40 bg-card p-5 space-y-4">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Plus className="h-4 w-4 text-accent" />
            Log New Trade Entry
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="relative">
              <label className="text-[11px] text-muted-foreground block mb-1">Search Instrument</label>
              <input
                type="text"
                value={selectedInstrument ? selectedInstrument.canonical_code : instrumentQuery}
                onChange={(e) => {
                  setSelectedInstrument(null);
                  void handleInstrumentSearch(e.target.value);
                }}
                placeholder="e.g. RELIANCE, TSLA, NVDA"
                required
                className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-mono"
              />
              {instrumentMatches.length > 0 && !selectedInstrument && (
                <div className="absolute left-0 right-0 top-full mt-1 z-20 rounded-lg border border-border bg-card shadow-lg overflow-hidden">
                  {instrumentMatches.map((inst) => (
                    <button
                      key={inst.instrument_id}
                      type="button"
                      onClick={() => {
                        setSelectedInstrument(inst);
                        setCurrency(inst.currency);
                        setInstrumentMatches([]);
                      }}
                      className="w-full text-left px-3 py-2 text-xs hover:bg-muted flex items-center justify-between"
                    >
                      <span className="font-mono font-semibold">{inst.canonical_code}</span>
                      <span className="text-[10px] text-muted-foreground">{inst.company_name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div>
              <label className="text-[11px] text-muted-foreground block mb-1">Side</label>
              <select
                value={side}
                onChange={(e) => setSide(e.target.value as "BUY" | "SELL")}
                className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-mono"
              >
                <option value="BUY">BUY (Long)</option>
                <option value="SELL">SELL (Short)</option>
              </select>
            </div>

            <div>
              <label className="text-[11px] text-muted-foreground block mb-1">Currency</label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value as "INR" | "USD")}
                className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-mono"
              >
                <option value="INR">INR (₹)</option>
                <option value="USD">USD ($)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
            <div>
              <label className="text-[11px] text-muted-foreground block mb-1">Entry Price</label>
              <input
                type="number"
                step="any"
                required
                value={entryPrice}
                onChange={(e) => setEntryPrice(e.target.value)}
                placeholder="2940.00"
                className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs"
              />
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground block mb-1">Quantity</label>
              <input
                type="number"
                step="any"
                required
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="10"
                className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs"
              />
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground block mb-1">Planned Stop (optional)</label>
              <input
                type="number"
                step="any"
                value={plannedStop}
                onChange={(e) => setPlannedStop(e.target.value)}
                placeholder="2900.00"
                className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs"
              />
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground block mb-1">Planned Target (optional)</label>
              <input
                type="number"
                step="any"
                value={plannedTarget}
                onChange={(e) => setPlannedTarget(e.target.value)}
                placeholder="3020.00"
                className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs"
              />
            </div>
          </div>

          <div>
            <label className="text-[11px] text-muted-foreground block mb-1.5">Trade Psychology &amp; Emotion Tags</label>
            <div className="flex flex-wrap gap-1.5">
              {PRESET_EMOTIONS.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => toggleTag(tag, selectedTags, setSelectedTags)}
                  className={cn(
                    "px-2.5 py-1 rounded-md text-[11px] font-mono transition-colors",
                    selectedTags.includes(tag)
                      ? "bg-accent text-accent-foreground font-semibold"
                      : "border border-border bg-background text-muted-foreground hover:text-foreground"
                  )}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-[11px] text-muted-foreground block mb-1">Trade Notes / Execution Review</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Thesis, catalyst, setup reasoning, or market conditions..."
              rows={2}
              className="w-full rounded-lg border border-border bg-background p-2.5 text-xs outline-none focus:border-accent"
            />
          </div>

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowAddForm(false)}
              className="px-3 py-1.5 rounded-lg border border-border text-xs hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-1.5 rounded-lg bg-accent text-accent-foreground text-xs font-semibold hover:opacity-90 disabled:opacity-50"
            >
              {submitting ? "Saving..." : "Save Trade Entry"}
            </button>
          </div>
        </form>
      )}

      {/* Filters Strip */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <select
            value={sideFilter}
            onChange={(e) => setSideFilter(e.target.value)}
            className="rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs font-mono"
          >
            <option value="">All Sides</option>
            <option value="BUY">BUY Only</option>
            <option value="SELL">SELL Only</option>
          </select>
          <select
            value={currencyFilter}
            onChange={(e) => setCurrencyFilter(e.target.value)}
            className="rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs font-mono"
          >
            <option value="">All Currencies</option>
            <option value="INR">INR (₹)</option>
            <option value="USD">USD ($)</option>
          </select>
        </div>
        <span className="text-xs text-muted-foreground font-mono">
          Showing {entries.length} trade record(s)
        </span>
      </div>

      {/* Trade Log Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono tabular-nums">
            <thead className="bg-muted/40 text-muted-foreground text-[11px]">
              <tr>
                <th className="px-4 py-2.5">Date</th>
                <th className="px-4 py-2.5">Side</th>
                <th className="px-4 py-2.5 text-right">Entry</th>
                <th className="px-4 py-2.5 text-right">Exit</th>
                <th className="px-4 py-2.5 text-right">Qty</th>
                <th className="px-4 py-2.5 text-right">Realized P&amp;L</th>
                <th className="px-4 py-2.5">Emotions</th>
                <th className="px-4 py-2.5">Notes</th>
                <th className="px-4 py-2.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {entries.map((entry) => {
                const isOpen = entry.exit_price === null;
                const pnl = Number(entry.realized_pnl ?? 0);
                const isProfitable = pnl > 0;
                return (
                  <tr key={entry.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-sans text-muted-foreground">
                      {formatUtcTimestamp(entry.entered_at_utc)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-[11px] font-semibold",
                          entry.side === "BUY"
                            ? "bg-emerald-500/15 text-emerald-400"
                            : "bg-red-500/15 text-red-400"
                        )}
                      >
                        {entry.side}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {formatCurrencyPrice(entry.entry_price, entry.currency)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {isOpen ? (
                        <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 text-[10px]">
                          OPEN
                        </span>
                      ) : (
                        formatCurrencyPrice(entry.exit_price!, entry.currency)
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">{entry.quantity}</td>
                    <td className="px-4 py-3 text-right font-semibold">
                      {isOpen ? (
                        <span className="text-muted-foreground font-normal">—</span>
                      ) : (
                        <span className={isProfitable ? "text-emerald-400" : "text-red-400"}>
                          {isProfitable ? "+" : ""}
                          {formatCurrencyPrice(entry.realized_pnl!, entry.currency)}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {entry.emotions_tags.map((tag) => (
                          <span
                            key={tag}
                            className="px-1.5 py-0.5 rounded bg-muted text-[10px] text-muted-foreground"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-sans text-muted-foreground max-w-[200px] truncate">
                      {entry.notes || "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {isOpen ? (
                          <button
                            type="button"
                            onClick={() => {
                              setClosingEntry(entry);
                              setClosingTags(entry.emotions_tags);
                              setClosingNotes(entry.notes || "");
                            }}
                            className="px-2 py-1 rounded bg-accent/15 text-accent hover:bg-accent/25 text-[11px]"
                          >
                            Close
                          </button>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => handleDelete(entry.id)}
                          className="p-1 rounded text-muted-foreground hover:text-red-400"
                          title="Delete trade entry"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {entries.length === 0 && !loading && (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-muted-foreground font-sans">
                    No trading journal entries found. Log your first trade above to start building your personal performance audit trail.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Close Trade Modal */}
      {closingEntry && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <form
            onSubmit={handleCloseTrade}
            className="w-full max-w-md rounded-2xl border border-border bg-card p-6 space-y-4 shadow-xl"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold">Record Trade Exit</h3>
              <button
                type="button"
                onClick={() => setClosingEntry(null)}
                className="p-1 rounded hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="text-xs text-muted-foreground font-mono">
              Entry: {formatCurrencyPrice(closingEntry.entry_price, closingEntry.currency)} ({closingEntry.side} {closingEntry.quantity} qty)
            </p>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Exit Price</label>
              <input
                type="number"
                step="any"
                required
                value={exitPriceInput}
                onChange={(e) => setExitPriceInput(e.target.value)}
                placeholder="2965.50"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs font-mono"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Emotions / Post-Trade Tags</label>
              <div className="flex flex-wrap gap-1.5">
                {PRESET_EMOTIONS.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => toggleTag(tag, closingTags, setClosingTags)}
                    className={cn(
                      "px-2 py-0.5 rounded text-[10px] font-mono",
                      closingTags.includes(tag) ? "bg-accent text-accent-foreground font-semibold" : "bg-muted text-muted-foreground"
                    )}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Exit Reflection Notes</label>
              <textarea
                value={closingNotes}
                onChange={(e) => setClosingNotes(e.target.value)}
                rows={2}
                placeholder="What went well? Did you exit per plan?"
                className="w-full rounded-lg border border-border bg-background p-2 text-xs"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setClosingEntry(null)}
                className="px-3 py-1.5 rounded-lg border border-border text-xs hover:bg-muted"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 rounded-lg bg-accent text-accent-foreground text-xs font-semibold hover:opacity-90"
              >
                Save &amp; Calculate P&amp;L
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
