"use client";

import React, { useState } from "react";
import { Bell, CheckCheck, Save, Settings } from "lucide-react";
import {
  markAllNotificationsRead,
  markNotificationRead,
  updateNotificationPreferences,
  updateUserPreferences,
  updateUserProfile,
  type NotificationItem,
  type NotificationPreferences,
  type UserPreferences,
  type UserProfile,
} from "@/lib/api";
import { cn, formatUtcTimestamp } from "@/lib/utils";

interface NotificationsViewProps {
  notifications: NotificationItem[];
  unreadCount: number;
  prefs: NotificationPreferences | null;
  onRefresh: () => Promise<void>;
}

export function NotificationsView({
  notifications,
  unreadCount,
  prefs,
  onRefresh,
}: NotificationsViewProps) {
  const [pushStatus, setPushStatus] = useState<string | null>(null);

  const handleTogglePref = async (key: keyof NotificationPreferences, value: boolean) => {
    if (!prefs) return;
    if (key === "browser_push_enabled" && value && typeof Notification !== "undefined") {
      const perm = await Notification.requestPermission();
      setPushStatus(`Browser permission: ${perm}`);
      if (perm !== "granted") return;
    }
    await updateNotificationPreferences({ [key]: value });
    await onRefresh();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Bell className="h-5 w-5 text-accent" />
            Notifications Center ({unreadCount} unread)
          </h1>
          <p className="text-xs text-muted-foreground">
            Real-time in-app alerts, opt-in browser push, and email delivery controls
          </p>
        </div>
        {unreadCount > 0 && (
          <button
            type="button"
            onClick={async () => {
              await markAllNotificationsRead();
              await onRefresh();
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card text-xs hover:bg-muted"
          >
            <CheckCheck className="h-3.5 w-3.5" />
            <span>Mark All Read</span>
          </button>
        )}
      </div>

      {prefs && (
        <section className="rounded-xl border border-border bg-card p-5 space-y-3">
          <h2 className="text-sm font-semibold">Alert Channels &amp; Event Preferences</h2>
          {pushStatus && <p className="text-xs text-accent">{pushStatus}</p>}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
            {(
              [
                ["in_app_enabled", "In-App Alerts"],
                ["browser_push_enabled", "Browser Push (Opt-In)"],
                ["email_enabled", "Email Notifications"],
                ["notify_new_signals", "New Risk-Passed Signals"],
                ["notify_entry_hit", "Entry Triggered Alerts"],
                ["notify_target_hit", "Target Reached Alerts"],
                ["notify_stop_hit", "Stop-Loss Alerts"],
                ["notify_signal_expiry", "Signal Expiry Notices"],
                ["notify_market_news", "Important News & Filings"],
              ] as Array<[keyof NotificationPreferences, string]>
            ).map(([key, label]) => (
              <label
                key={key}
                className="flex items-center justify-between rounded-lg border border-border bg-background/60 px-3 py-2 cursor-pointer"
              >
                <span>{label}</span>
                <input
                  type="checkbox"
                  checked={Boolean(prefs[key])}
                  onChange={(e) => handleTogglePref(key, e.target.checked)}
                  className="accent-sky-400 h-4 w-4"
                />
              </label>
            ))}
          </div>
        </section>
      )}

      <section className="space-y-2">
        {notifications.length === 0 ? (
          <div className="rounded-xl border border-border bg-card p-8 text-center text-xs text-muted-foreground">
            No notifications yet. New signals, target hits, and important market updates will appear
            here in real time.
          </div>
        ) : (
          notifications.map((n) => (
            <div
              key={n.id}
              className={cn(
                "rounded-xl border p-4 flex items-start justify-between gap-4",
                n.is_read
                  ? "border-border bg-card/60 text-muted-foreground"
                  : "border-accent/40 bg-card"
              )}
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-[11px] font-mono">
                  <span className="px-2 py-0.5 rounded bg-accent/15 text-accent">{n.category}</span>
                  <span>{formatUtcTimestamp(n.created_at_utc)}</span>
                </div>
                <div className="text-sm font-medium text-foreground">{n.title}</div>
                <p className="text-xs">{n.body}</p>
              </div>
              {!n.is_read && (
                <button
                  type="button"
                  onClick={async () => {
                    await markNotificationRead(n.id);
                    await onRefresh();
                  }}
                  className="text-xs text-accent hover:underline shrink-0"
                >
                  Mark Read
                </button>
              )}
            </div>
          ))
        )}
      </section>
    </div>
  );
}

interface AccountSettingsViewProps {
  user: UserProfile;
  userPrefs: UserPreferences | null;
  onRefresh: () => Promise<void>;
}

export function AccountSettingsView({ user, userPrefs, onRefresh }: AccountSettingsViewProps) {
  const [fullName, setFullName] = useState(user.full_name);
  const [budgetInr, setBudgetInr] = useState(userPrefs?.default_budget_inr ?? "200000.00");
  const [maxLossInr, setMaxLossInr] = useState(userPrefs?.default_max_loss_inr ?? "2000.00");
  const [budgetUsd, setBudgetUsd] = useState(userPrefs?.default_budget_usd ?? "5000.00");
  const [maxLossUsd, setMaxLossUsd] = useState(userPrefs?.default_max_loss_usd ?? "50.00");
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavedMsg(null);
    await updateUserProfile({ full_name: fullName });
    await updateUserPreferences({
      default_budget_inr: budgetInr,
      default_max_loss_inr: maxLossInr,
      default_budget_usd: budgetUsd,
      default_max_loss_usd: maxLossUsd,
    });
    await onRefresh();
    setSavedMsg("Profile and default risk sizing preferences saved.");
  };

  return (
    <div className="space-y-5 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold flex items-center gap-2">
          <Settings className="h-5 w-5 text-accent" />
          Account &amp; Risk Preferences
        </h1>
        <p className="text-xs text-muted-foreground">
          {user.email} • Role: {user.role} • Subscription: {user.subscription_status}
        </p>
      </div>

      <form onSubmit={handleSave} className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="space-y-1.5">
          <label className="text-xs font-medium">Full Name</label>
          <input
            type="text"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-mono">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Default India Budget (INR)</label>
            <input
              type="number"
              step="0.01"
              value={budgetInr}
              onChange={(e) => setBudgetInr(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Default India Max Loss (INR)</label>
            <input
              type="number"
              step="0.01"
              value={maxLossInr}
              onChange={(e) => setMaxLossInr(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Default US Budget (USD)</label>
            <input
              type="number"
              step="0.01"
              value={budgetUsd}
              onChange={(e) => setBudgetUsd(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Default US Max Loss (USD)</label>
            <input
              type="number"
              step="0.01"
              value={maxLossUsd}
              onChange={(e) => setMaxLossUsd(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs"
            />
          </div>
        </div>

        {savedMsg && <p className="text-xs text-emerald-400">{savedMsg}</p>}

        <button
          type="submit"
          className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-accent-foreground hover:opacity-90"
        >
          <Save className="h-3.5 w-3.5" />
          <span>Save Settings</span>
        </button>
      </form>
    </div>
  );
}
