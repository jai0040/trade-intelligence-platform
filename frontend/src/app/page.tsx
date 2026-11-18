"use client";

import React, { useEffect, useState } from "react";
import { Activity, CheckCircle2, Database, Layers, Server, ShieldCheck, XCircle } from "lucide-react";
import { AppShell, type MarketScope } from "@/components/layout/AppShell";

interface HealthResponse {
  status: string;
  service: string;
  environment: string;
  trading_mode: string;
  kill_switch: { enabled: boolean; source: string };
  timestamp_utc: string;
  dependencies: {
    postgresql: { ok: boolean; detail: string };
    valkey_redis: { ok: boolean; detail: string };
  };
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function FoundationOverviewPage() {
  const [marketScope, setMarketScope] = useState<MarketScope>("ALL");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/api/v1/health`, { credentials: "include" })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<HealthResponse>;
      })
      .then((data) => {
        if (active) {
          setHealth(data);
          setHealthError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setHealthError(err instanceof Error ? err.message : "Backend unreachable");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const showIndia = marketScope === "ALL" || marketScope === "IN";
  const showUS = marketScope === "ALL" || marketScope === "US";

  return (
    <AppShell marketScope={marketScope} onMarketScopeChange={setMarketScope}>
      <div className="space-y-6">
        {/* Header Banner */}
        <section className="rounded-xl border border-border bg-card p-6">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="space-y-1">
              <div className="inline-flex items-center gap-2 text-xs font-mono text-accent">
                <Layers className="h-3.5 w-3.5" />
                <span>PHASE 3: PROJECT FOUNDATION SHELL</span>
              </div>
              <h1 className="text-2xl font-semibold tracking-tight">
                AI Trading Intelligence Control Plane
              </h1>
              <p className="text-sm text-muted-foreground max-w-2xl">
                Strict Signals-Only multi-market SaaS foundation. Live market feeds, authentication,
                and the 11-skill workflow engine are wired in Phases 4–7 — zero synthetic or fake
                market prices are displayed here.
              </p>
            </div>
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-xs font-mono">
              <ShieldCheck className="h-4 w-4 shrink-0" />
              <span>SIGNALS-ONLY POLICY ACTIVE</span>
            </div>
          </div>
        </section>

        {/* Live Backend & Infrastructure Connectivity */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-xl border border-border bg-card p-5 space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="flex items-center gap-2 font-medium text-foreground">
                <Server className="h-4 w-4 text-accent" />
                FastAPI Backend
              </span>
              {health ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              ) : (
                <XCircle className="h-4 w-4 text-amber-400" />
              )}
            </div>
            <div className="text-lg font-semibold font-mono tabular-nums">
              {health ? health.status.toUpperCase() : "OFFLINE / NOT STARTED"}
            </div>
            <p className="text-xs text-muted-foreground">
              {health
                ? `Mode: ${health.trading_mode} • Env: ${health.environment}`
                : healthError ?? "Checking /api/v1/health..."}
            </p>
          </div>

          <div className="rounded-xl border border-border bg-card p-5 space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="flex items-center gap-2 font-medium text-foreground">
                <Database className="h-4 w-4 text-accent" />
                PostgreSQL 16 (31 Tables)
              </span>
              {health?.dependencies.postgresql.ok ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              ) : (
                <XCircle className="h-4 w-4 text-amber-400" />
              )}
            </div>
            <div className="text-lg font-semibold font-mono tabular-nums">
              {health?.dependencies.postgresql.ok ? "CONNECTED" : "AWAITING STARTUP"}
            </div>
            <p className="text-xs text-muted-foreground">
              Normalized multi-tenant schema + immutable signal trigger via Alembic.
            </p>
          </div>

          <div className="rounded-xl border border-border bg-card p-5 space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="flex items-center gap-2 font-medium text-foreground">
                <Activity className="h-4 w-4 text-accent" />
                Valkey / Redis & Celery
              </span>
              {health?.dependencies.valkey_redis.ok ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              ) : (
                <XCircle className="h-4 w-4 text-amber-400" />
              )}
            </div>
            <div className="text-lg font-semibold font-mono tabular-nums">
              {health?.dependencies.valkey_redis.ok ? "CONNECTED" : "AWAITING STARTUP"}
            </div>
            <p className="text-xs text-muted-foreground">
              5 isolated queues: india_market, us_market, analysis, notifications, maintenance.
            </p>
          </div>
        </section>

        {/* Independent Market Environment Cards */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {showIndia && (
            <div className="rounded-xl border border-border bg-card p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold">India Market Environment</h2>
                  <p className="text-xs text-muted-foreground">NSE • BSE • INR (₹) • Asia/Kolkata</p>
                </div>
                <span className="px-2.5 py-1 rounded-full text-[11px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/30">
                  Adapter Pending (Phase 5)
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3 pt-2 border-t border-border text-xs">
                <div>
                  <div className="text-muted-foreground">Regular Session</div>
                  <div className="font-mono tabular-nums mt-0.5">09:15 – 15:30 IST</div>
                </div>
                <div>
                  <div className="text-muted-foreground">5m Session Bars</div>
                  <div className="font-mono tabular-nums mt-0.5">75 bars</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Payments</div>
                  <div className="font-mono mt-0.5">Razorpay (INR)</div>
                </div>
              </div>
            </div>
          )}

          {showUS && (
            <div className="rounded-xl border border-border bg-card p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold">US Market Environment</h2>
                  <p className="text-xs text-muted-foreground">
                    NASDAQ • NYSE • USD ($) • America/New_York
                  </p>
                </div>
                <span className="px-2.5 py-1 rounded-full text-[11px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/30">
                  Adapter Pending (Phase 5)
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3 pt-2 border-t border-border text-xs">
                <div>
                  <div className="text-muted-foreground">Regular Session</div>
                  <div className="font-mono tabular-nums mt-0.5">09:30 – 16:00 ET</div>
                </div>
                <div>
                  <div className="text-muted-foreground">5m Session Bars</div>
                  <div className="font-mono tabular-nums mt-0.5">78 bars (DST auto)</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Payments</div>
                  <div className="font-mono mt-0.5">Stripe (USD)</div>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
