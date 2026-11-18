"use client";

import React, { useState } from "react";
import { Plus, Star, Trash2 } from "lucide-react";
import { createWatchlist, deleteWatchlist, type Watchlist } from "@/lib/api";

interface WatchlistViewProps {
  watchlists: Watchlist[];
  onRefresh: () => Promise<void>;
}

export function WatchlistView({ watchlists, onRefresh }: WatchlistViewProps) {
  const [name, setName] = useState("");
  const [scope, setScope] = useState<"ALL" | "IN" | "US">("ALL");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await createWatchlist(name.trim(), scope);
      setName("");
      await onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not create watchlist");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    setError(null);
    try {
      await deleteWatchlist(id);
      await onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not delete watchlist");
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold flex items-center gap-2">
          <Star className="h-5 w-5 text-accent" />
          Personal Portfolio &amp; Watchlists
        </h1>
        <p className="text-xs text-muted-foreground">
          Strictly isolated to your account (`user_id` scoped). Other subscribers can never view or
          modify your lists.
        </p>
      </div>

      <form
        onSubmit={handleCreate}
        className="rounded-xl border border-border bg-card p-4 flex flex-col sm:flex-row gap-3"
      >
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New watchlist name (e.g. India ORB Focus)"
          required
          className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs outline-none focus:border-accent"
        />
        <select
          value={scope}
          onChange={(e) => setScope(e.target.value as "ALL" | "IN" | "US")}
          className="rounded-lg border border-border bg-background px-3 py-2 text-xs"
        >
          <option value="ALL">All Markets</option>
          <option value="IN">India (NSE/BSE)</option>
          <option value="US">US (NASDAQ/NYSE)</option>
        </select>
        <button
          type="submit"
          disabled={saving}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-accent-foreground hover:opacity-90 disabled:opacity-50"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>Create Watchlist</span>
        </button>
      </form>

      {error && <p className="text-xs text-red-400">{error}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {watchlists.map((wl) => (
          <div key={wl.id} className="rounded-xl border border-border bg-card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold flex items-center gap-2">
                  <span>{wl.name}</span>
                  {wl.is_default && (
                    <span className="px-1.5 py-0.5 rounded bg-accent/15 text-accent text-[10px] font-mono">
                      DEFAULT
                    </span>
                  )}
                </h2>
                <p className="text-[11px] font-mono text-muted-foreground">
                  Market Scope: {wl.market_scope} • {wl.items.length} instrument(s)
                </p>
              </div>
              {!wl.is_default && (
                <button
                  type="button"
                  onClick={() => handleDelete(wl.id)}
                  className="p-1.5 rounded-md text-muted-foreground hover:text-red-400 hover:bg-muted"
                  aria-label={`Delete ${wl.name}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>

            {wl.items.length === 0 ? (
              <p className="text-xs text-muted-foreground border-t border-border pt-3">
                No instruments pinned yet.
              </p>
            ) : (
              <ul className="divide-y divide-border border-t border-border text-xs">
                {wl.items.map((it) => (
                  <li key={it.id} className="py-2 flex items-center justify-between font-mono">
                    <span>{it.instrument_id}</span>
                    {it.notes && <span className="font-sans text-muted-foreground">{it.notes}</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
