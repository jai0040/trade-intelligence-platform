"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  Clock,
  CreditCard,
  Database,
  DollarSign,
  KeyRound,
  Play,
  Plus,
  RefreshCw,
  Search,
  Server,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  Users,
  UserX,
  XCircle,
} from "lucide-react";
import {
  createAdminPlan,
  fetchAdminAuditLogs,
  fetchAdminOverview,
  fetchAdminProviderStatus,
  fetchAdminUsers,
  fetchAdminWorkflows,
  revokeAdminUserSession,
  toggleAdminKillSwitch,
  triggerAdminWorkflow,
  updateAdminUserStatus,
  type AdminOverview,
  type AdminUserItem,
  type AuditLogItem,
  type WorkflowRunItem,
} from "@/lib/api";
import { cn, formatCurrencyPrice, formatUtcTimestamp } from "@/lib/utils";

type AdminTab = "overview" | "users" | "workflows" | "providers" | "plans" | "audit" | "killswitch";

export function SuperAdminView() {
  const [activeTab, setActiveTab] = useState<AdminTab>("overview");
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [userSearch, setUserSearch] = useState("");
  const [userRoleFilter, setUserRoleFilter] = useState("");
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowRunItem[]>([]);
  const [providerTelemetry, setProviderTelemetry] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Plan creation form
  const [newPlanCode, setNewPlanCode] = useState("");
  const [newPlanName, setNewPlanName] = useState("");
  const [newPlanCurrency, setNewPlanCurrency] = useState<"INR" | "USD">("INR");
  const [newPlanPrice, setNewPlanPrice] = useState("2999.00");
  const [newPlanMarkets, setNewPlanMarkets] = useState<Array<"IN" | "US">>(["IN"]);

  // Kill Switch state
  const [killReason, setKillReason] = useState("Administrative emergency halt");

  const loadAll = async () => {
    setLoading(true);
    try {
      const [ovRes, uRes, wRes, pRes, aRes] = await Promise.allSettled([
        fetchAdminOverview(),
        fetchAdminUsers({ search: userSearch || undefined, role: userRoleFilter || undefined }),
        fetchAdminWorkflows(),
        fetchAdminProviderStatus(),
        fetchAdminAuditLogs({ limit: 50 }),
      ]);

      if (ovRes.status === "fulfilled") setOverview(ovRes.value);
      if (uRes.status === "fulfilled") setUsers(uRes.value.items);
      if (wRes.status === "fulfilled") setWorkflows(wRes.value.workflows);
      if (pRes.status === "fulfilled") setProviderTelemetry(pRes.value.telemetry);
      if (aRes.status === "fulfilled") setAuditLogs(aRes.value);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userSearch, userRoleFilter]);

  const handleRevokeSession = async (userId: string) => {
    try {
      await revokeAdminUserSession(userId, "Session revoked from Super Admin control plane");
      setMessage("User session revoked immediately across DB, Redis, and WebSocket.");
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to revoke session");
    }
  };

  const handleToggleUserStatus = async (userId: string, currentStatus: boolean) => {
    try {
      await updateAdminUserStatus(userId, !currentStatus, "Administrative status toggle");
      setMessage(`User ${!currentStatus ? "activated" : "deactivated"} successfully.`);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update user status");
    }
  };

  const handleCreatePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createAdminPlan({
        code: newPlanCode.trim().toLowerCase(),
        name: newPlanName.trim(),
        currency: newPlanCurrency,
        price_amount: newPlanPrice,
        entitled_markets: newPlanMarkets,
      });
      setMessage(`Plan '${newPlanCode}' created and persisted.`);
      setNewPlanCode("");
      setNewPlanName("");
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create plan");
    }
  };

  const handleToggleKillSwitch = async (targetEnabled: boolean) => {
    try {
      const res = await toggleAdminKillSwitch(targetEnabled, killReason);
      setMessage(res.message);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Kill switch toggle failed");
    }
  };

  const handleTriggerWorkflow = async (mkt: "IN" | "US", mode: "daily" | "orb") => {
    try {
      const res = await triggerAdminWorkflow(mkt, mode);
      setMessage(`Workflow triggered manually for ${mkt}: ${JSON.stringify(res)}`);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Workflow trigger failed");
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-accent" />
            Super Admin Control Plane
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Central administration: multi-tenant users, session eviction, kill-switch, provider telemetry, and immutable audit logs.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadAll()}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card text-xs hover:bg-muted self-start sm:self-auto"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          <span>Refresh</span>
        </button>
      </div>

      {message && (
        <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3 text-xs text-emerald-300 flex items-center justify-between">
          <span>{message}</span>
          <button type="button" onClick={() => setMessage(null)} className="text-muted-foreground hover:text-foreground">
            ×
          </button>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-300 flex items-center justify-between">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)} className="text-muted-foreground hover:text-foreground">
            ×
          </button>
        </div>
      )}

      {/* Admin Navigation Tabs */}
      <div className="border-b border-border flex gap-2 overflow-x-auto text-xs font-mono">
        {[
          ["overview", "Overview KPIs"],
          ["users", "User Directory"],
          ["workflows", "Workflow Engine"],
          ["providers", "Provider Telemetry"],
          ["plans", "Plan Configurator"],
          ["audit", "Audit Logs"],
          ["killswitch", "Emergency Kill Switch"],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setActiveTab(key as AdminTab)}
            className={cn(
              "px-3 py-2 border-b-2 font-medium whitespace-nowrap transition-colors",
              activeTab === key
                ? "border-accent text-accent"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab 1: Overview KPIs */}
      {activeTab === "overview" && overview && (
        <div className="space-y-4">
          <section className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono tabular-nums">
            <div className="rounded-xl border border-border bg-card p-4 space-y-1">
              <div className="text-[11px] text-muted-foreground">Total Users</div>
              <div className="text-2xl font-bold">{overview.total_users}</div>
              <div className="text-[10px] text-emerald-400">{overview.active_users} active • {overview.inactive_users} disabled</div>
            </div>
            <div className="rounded-xl border border-border bg-card p-4 space-y-1">
              <div className="text-[11px] text-muted-foreground">Active Sessions</div>
              <div className="text-2xl font-bold text-accent">{overview.active_sessions_count}</div>
              <div className="text-[10px] text-muted-foreground">Single session enforced</div>
            </div>
            <div className="rounded-xl border border-border bg-card p-4 space-y-1">
              <div className="text-[11px] text-muted-foreground">Estimated MRR (INR)</div>
              <div className="text-2xl font-bold text-emerald-400">
                {formatCurrencyPrice(overview.mrr_inr, "INR")}
              </div>
              <div className="text-[10px] text-muted-foreground">India subscribers</div>
            </div>
            <div className="rounded-xl border border-border bg-card p-4 space-y-1">
              <div className="text-[11px] text-muted-foreground">Estimated MRR (USD)</div>
              <div className="text-2xl font-bold text-emerald-400">
                {formatCurrencyPrice(overview.mrr_usd, "USD")}
              </div>
              <div className="text-[10px] text-muted-foreground">US subscribers</div>
            </div>
          </section>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-xl border border-border bg-card p-5 space-y-3">
              <h3 className="text-sm font-semibold">Subscription Status Breakdown</h3>
              <div className="space-y-2 text-xs font-mono">
                {Object.entries(overview.subscriptions_by_status).map(([st, cnt]) => (
                  <div key={st} className="flex justify-between p-2 rounded bg-background/60 border border-border">
                    <span className="uppercase text-muted-foreground">{st}</span>
                    <span className="font-semibold">{cnt}</span>
                  </div>
                ))}
                {Object.keys(overview.subscriptions_by_status).length === 0 && (
                  <p className="text-xs text-muted-foreground">No subscriber records yet.</p>
                )}
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-5 space-y-3">
              <h3 className="text-sm font-semibold">Security &amp; Operating Mode</h3>
              <div className="space-y-2 text-xs font-mono">
                <div className="flex justify-between p-2 rounded bg-background/60 border border-border">
                  <span className="text-muted-foreground">Operating Mode</span>
                  <span className="text-emerald-400 font-semibold">{overview.trading_mode}</span>
                </div>
                <div className="flex justify-between p-2 rounded bg-background/60 border border-border">
                  <span className="text-muted-foreground">Kill Switch State</span>
                  <span className={overview.kill_switch.enabled ? "text-red-400 font-semibold" : "text-emerald-400 font-semibold"}>
                    {overview.kill_switch.enabled ? "ACTIVE (PAUSED)" : "DISABLED (NORMAL)"}
                  </span>
                </div>
                <div className="flex justify-between p-2 rounded bg-background/60 border border-border">
                  <span className="text-muted-foreground">Single Active Session</span>
                  <span className="text-accent font-semibold">ENFORCED (DB + Redis + WS)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: User Directory */}
      {activeTab === "users" && (
        <div className="space-y-4">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="h-3.5 w-3.5 text-muted-foreground absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={userSearch}
                onChange={(e) => setUserSearch(e.target.value)}
                placeholder="Search user email or name..."
                className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-border bg-card text-xs outline-none focus:border-accent"
              />
            </div>
            <select
              value={userRoleFilter}
              onChange={(e) => setUserRoleFilter(e.target.value)}
              className="rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs font-mono"
            >
              <option value="">All Roles</option>
              <option value="super_admin">Super Admin</option>
              <option value="admin">Admin</option>
              <option value="subscriber">Subscriber</option>
            </select>
          </div>

          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono tabular-nums">
                <thead className="bg-muted/40 text-muted-foreground text-[11px]">
                  <tr>
                    <th className="px-4 py-2.5">User</th>
                    <th className="px-4 py-2.5">Role</th>
                    <th className="px-4 py-2.5">Status</th>
                    <th className="px-4 py-2.5">Subscription</th>
                    <th className="px-4 py-2.5">Active Session</th>
                    <th className="px-4 py-2.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {users.map((u) => (
                    <tr key={u.id} className="hover:bg-muted/30">
                      <td className="px-4 py-3">
                        <div className="font-semibold text-foreground font-sans">{u.full_name}</div>
                        <div className="text-[11px] text-muted-foreground">{u.email}</div>
                      </td>
                      <td className="px-4 py-3 font-semibold uppercase">{u.role}</td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "px-2 py-0.5 rounded text-[10px]",
                            u.is_active ? "bg-emerald-500/15 text-emerald-400" : "bg-red-500/15 text-red-400"
                          )}
                        >
                          {u.is_active ? "ACTIVE" : "DISABLED"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {u.subscription ? (
                          <div>
                            <span className="font-semibold">{u.subscription.plan_name}</span>
                            <div className="text-[10px] text-muted-foreground uppercase">{u.subscription.status}</div>
                          </div>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-[11px]">
                        {u.active_session ? (
                          <div>
                            <span className="text-accent font-semibold">{u.active_session.ip_address || "Local"}</span>
                            <div className="text-[10px] text-muted-foreground">
                              Seen {formatUtcTimestamp(u.active_session.last_seen_at)}
                            </div>
                          </div>
                        ) : (
                          <span className="text-muted-foreground">Offline</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {u.active_session && (
                            <button
                              type="button"
                              onClick={() => handleRevokeSession(u.id)}
                              className="px-2 py-1 rounded border border-border hover:bg-muted text-[10px]"
                              title="Evict active session immediately"
                            >
                              Revoke
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => handleToggleUserStatus(u.id, u.is_active)}
                            className={cn(
                              "px-2 py-1 rounded text-[10px] font-semibold",
                              u.is_active
                                ? "bg-red-500/15 text-red-400 hover:bg-red-500/25"
                                : "bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25"
                            )}
                          >
                            {u.is_active ? "Deactivate" : "Activate"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Workflow Engine & Telemetry */}
      {activeTab === "workflows" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h2 className="text-sm font-semibold">Celery DAG Workflow Invocations</h2>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => handleTriggerWorkflow("IN", "orb")}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent text-accent-foreground text-xs font-semibold hover:opacity-90"
              >
                <Play className="h-3.5 w-3.5" />
                <span>Trigger India ORB</span>
              </button>
              <button
                type="button"
                onClick={() => handleTriggerWorkflow("US", "orb")}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card text-xs font-semibold hover:bg-muted"
              >
                <Play className="h-3.5 w-3.5" />
                <span>Trigger US ORB</span>
              </button>
            </div>
          </div>

          <div className="space-y-3">
            {workflows.map((wf) => (
              <div key={wf.workflow_run_id} className="rounded-xl border border-border bg-card p-4 space-y-2">
                <div className="flex items-center justify-between font-mono text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{wf.workflow_type}</span>
                    <span className="px-1.5 py-0.5 rounded bg-muted text-[10px]">{wf.market_code}</span>
                  </div>
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded text-[10px] font-semibold",
                      wf.status === "SUCCEEDED"
                        ? "bg-emerald-500/15 text-emerald-400"
                        : wf.status === "ABORTED_KILL_SWITCH"
                          ? "bg-red-500/15 text-red-400"
                          : "bg-muted text-muted-foreground"
                    )}
                  >
                    {wf.status}
                  </span>
                </div>
                <div className="text-[11px] text-muted-foreground font-mono">
                  Triggered by: {wf.triggered_by} • {formatUtcTimestamp(wf.started_at_utc)}
                </div>
                {wf.skill_runs && wf.skill_runs.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {wf.skill_runs.map((sr) => (
                      <span
                        key={sr.id}
                        className={cn(
                          "px-2 py-0.5 rounded text-[10px] font-mono",
                          sr.status === "SUCCEEDED"
                            ? "bg-background border border-border text-foreground"
                            : sr.status === "SKIPPED"
                              ? "bg-muted/40 text-muted-foreground"
                              : "bg-red-500/15 text-red-400"
                        )}
                      >
                        {sr.skill_name} ({sr.duration_ms}ms)
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 4: Provider Telemetry */}
      {activeTab === "providers" && (
        <div className="space-y-4">
          <h2 className="text-sm font-semibold">Market Data Providers Health &amp; Daily API Calls</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {providerTelemetry.map((pt, i) => (
              <div key={i} className="rounded-xl border border-border bg-card p-4 space-y-2 font-mono text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-foreground">{String(pt.provider_code)}</span>
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded text-[10px]",
                      pt.status === "HEALTHY"
                        ? "bg-emerald-500/15 text-emerald-400"
                        : "bg-red-500/15 text-red-400"
                    )}
                  >
                    {String(pt.status)}
                  </span>
                </div>
                <div className="text-muted-foreground">Market: {String(pt.market_code)}</div>
                <div className="text-muted-foreground">Daily API Calls: {String(pt.daily_api_calls)}</div>
                <div className="text-muted-foreground">Avg Latency: {String(pt.avg_latency_ms)}ms</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 5: Plan Configurator */}
      {activeTab === "plans" && (
        <div className="space-y-6 max-w-2xl">
          <form onSubmit={handleCreatePlan} className="rounded-xl border border-border bg-card p-5 space-y-4">
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <Plus className="h-4 w-4 text-accent" />
              Create Subscription Plan Pricing
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-muted-foreground block mb-1">Plan Code</label>
                <input
                  type="text"
                  required
                  value={newPlanCode}
                  onChange={(e) => setNewPlanCode(e.target.value)}
                  placeholder="india_annual_inr"
                  className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-mono"
                />
              </div>
              <div>
                <label className="text-[11px] text-muted-foreground block mb-1">Plan Display Name</label>
                <input
                  type="text"
                  required
                  value={newPlanName}
                  onChange={(e) => setNewPlanName(e.target.value)}
                  placeholder="India Market Annual"
                  className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-muted-foreground block mb-1">Currency</label>
                <select
                  value={newPlanCurrency}
                  onChange={(e) => setNewPlanCurrency(e.target.value as "INR" | "USD")}
                  className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-mono"
                >
                  <option value="INR">INR (₹)</option>
                  <option value="USD">USD ($)</option>
                </select>
              </div>
              <div>
                <label className="text-[11px] text-muted-foreground block mb-1">Price Amount</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={newPlanPrice}
                  onChange={(e) => setNewPlanPrice(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-mono"
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] text-muted-foreground block mb-1">Entitled Markets</label>
              <div className="flex gap-4 text-xs font-mono">
                <label className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={newPlanMarkets.includes("IN")}
                    onChange={(e) =>
                      setNewPlanMarkets((prev) =>
                        e.target.checked ? [...prev, "IN"] : prev.filter((m) => m !== "IN")
                      )
                    }
                    className="accent-sky-400"
                  />
                  <span>India (NSE/BSE)</span>
                </label>
                <label className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={newPlanMarkets.includes("US")}
                    onChange={(e) =>
                      setNewPlanMarkets((prev) =>
                        e.target.checked ? [...prev, "US"] : prev.filter((m) => m !== "US")
                      )
                    }
                    className="accent-sky-400"
                  />
                  <span>US (NASDAQ/NYSE)</span>
                </label>
              </div>
            </div>

            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-accent text-accent-foreground text-xs font-semibold hover:opacity-90"
            >
              Create Subscription Plan
            </button>
          </form>
        </div>
      )}

      {/* Tab 6: Audit Logs */}
      {activeTab === "audit" && (
        <div className="space-y-4">
          <h2 className="text-sm font-semibold">Immutable Security &amp; Admin Audit Trail</h2>
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono tabular-nums">
                <thead className="bg-muted/40 text-muted-foreground text-[11px]">
                  <tr>
                    <th className="px-4 py-2.5">Timestamp</th>
                    <th className="px-4 py-2.5">Action</th>
                    <th className="px-4 py-2.5">Resource</th>
                    <th className="px-4 py-2.5">Actor User</th>
                    <th className="px-4 py-2.5">IP Address</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-muted/30">
                      <td className="px-4 py-2.5 font-sans text-muted-foreground">
                        {formatUtcTimestamp(log.created_at)}
                      </td>
                      <td className="px-4 py-2.5 font-semibold text-accent">{log.action}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {log.resource_type}:{log.resource_id || "—"}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {log.actor_user_id ? log.actor_user_id.slice(0, 8) : "System"}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">{log.ip_address || "Local"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 7: Emergency Kill Switch */}
      {activeTab === "killswitch" && overview && (
        <div className="space-y-6 max-w-2xl">
          <div className="rounded-xl border border-red-500/40 bg-red-500/5 p-6 space-y-4">
            <div className="flex items-center gap-3 text-red-400">
              <AlertOctagon className="h-6 w-6" />
              <div>
                <h2 className="text-base font-semibold">Global Emergency Kill Switch</h2>
                <p className="text-xs text-muted-foreground">
                  Immediately halts all automated market scanning, Celery workflows, and signal publication.
                </p>
              </div>
            </div>

            <div className="space-y-2 text-xs">
              <label className="text-muted-foreground block">Reason for emergency toggle (audited):</label>
              <input
                type="text"
                value={killReason}
                onChange={(e) => setKillReason(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs"
              />
            </div>

            <div className="flex items-center gap-3 pt-2">
              {overview.kill_switch.enabled ? (
                <button
                  type="button"
                  onClick={() => handleToggleKillSwitch(false)}
                  className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700"
                >
                  Deactivate Kill Switch (Resume Normal Operations)
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => handleToggleKillSwitch(true)}
                  className="px-4 py-2 rounded-lg bg-red-600 text-white text-xs font-semibold hover:bg-red-700"
                >
                  ACTIVATE EMERGENCY KILL SWITCH
                </button>
              )}
            </div>

            <p className="text-[11px] text-muted-foreground">
              Zero historical signals or subscriber data is deleted. Existing signals and user journals remain accessible.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
