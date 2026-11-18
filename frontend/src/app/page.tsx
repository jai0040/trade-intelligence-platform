"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Lock, RefreshCw, ShieldCheck } from "lucide-react";
import { AppShell, type MarketScope, type NavSectionId } from "@/components/layout/AppShell";
import { SignalDetailPanel } from "@/components/signals/SignalDetailPanel";
import { AIAnalystView } from "@/components/views/AIAnalystView";
import { JournalView } from "@/components/views/JournalView";
import { NewsAndDisclosuresView } from "@/components/views/NewsAndDisclosuresView";
import {
  AccountSettingsView,
  NotificationsView,
} from "@/components/views/NotificationsAndSettingsView";
import { OverviewView } from "@/components/views/OverviewView";
import { PerformanceView } from "@/components/views/PerformanceView";
import { ScannerAndSignalsView } from "@/components/views/ScannerAndSignalsView";
import { StockAnalysisView } from "@/components/views/StockAnalysisView";
import { SubscriptionBillingView } from "@/components/views/SubscriptionBillingView";
import { SuperAdminView } from "@/components/views/SuperAdminView";
import { WatchlistView } from "@/components/views/WatchlistView";
import {
  API_BASE_URL,
  fetchCongressDisclosures,
  fetchCurrentUser,
  fetchMarketIndices,
  fetchMarketNews,
  fetchMarketsStatus,
  fetchNotificationPreferences,
  fetchNotifications,
  fetchPerformanceSummary,
  fetchScannerResults,
  fetchSignals,
  fetchUserPreferences,
  fetchWatchlists,
  logoutAccount,
  type CongressDisclosureItem,
  type IndexSnapshot,
  type MarketNewsItem,
  type MarketStatusItem,
  type NotificationItem,
  type NotificationPreferences,
  type PerformanceSummary,
  type ScannerHit,
  type TradingSignalItem,
  type UserPreferences,
  type UserProfile,
  type Watchlist,
} from "@/lib/api";
import { useRealtimeStream } from "@/lib/useRealtimeStream";

export default function TradingIntelligenceDashboardPage() {
  const [activeNav, setActiveNav] = useState<NavSectionId>("overview");
  const [marketScope, setMarketScope] = useState<MarketScope>("ALL");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [killSwitchEnabled, setKillSwitchEnabled] = useState(false);

  const [marketStatuses, setMarketStatuses] = useState<MarketStatusItem[]>([]);
  const [indices, setIndices] = useState<IndexSnapshot[]>([]);
  const [scannerHits, setScannerHits] = useState<ScannerHit[]>([]);
  const [signals, setSignals] = useState<TradingSignalItem[]>([]);
  const [news, setNews] = useState<MarketNewsItem[]>([]);
  const [disclosures, setDisclosures] = useState<CongressDisclosureItem[]>([]);
  const [stockActNotice, setStockActNotice] = useState(
    "US House Clerk PTR filings may carry up to a 45-day statutory disclosure lag."
  );
  const [performance, setPerformance] = useState<PerformanceSummary | null>(null);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifPrefs, setNotifPrefs] = useState<NotificationPreferences | null>(null);
  const [userPrefs, setUserPrefs] = useState<UserPreferences | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<TradingSignalItem | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadDashboardData = useCallback(async () => {
    setRefreshing(true);
    try {
      const [
        statusRes,
        inIdx,
        usIdx,
        scanRes,
        sigRes,
        newsRes,
        congressRes,
        perfRes,
        wlRes,
        notifRes,
        nPrefRes,
        uPrefRes,
      ] = await Promise.allSettled([
        fetchMarketsStatus(),
        fetchMarketIndices("IN"),
        fetchMarketIndices("US"),
        fetchScannerResults({ market: "ALL", page_size: 100 }),
        fetchSignals({ market: "ALL", page_size: 100 }),
        fetchMarketNews("ALL"),
        fetchCongressDisclosures(),
        fetchPerformanceSummary("ALL"),
        fetchWatchlists(),
        fetchNotifications(),
        fetchNotificationPreferences(),
        fetchUserPreferences(),
      ]);

      if (statusRes.status === "fulfilled") setMarketStatuses(statusRes.value);
      const mergedIndices: IndexSnapshot[] = [];
      if (inIdx.status === "fulfilled") mergedIndices.push(...inIdx.value);
      if (usIdx.status === "fulfilled") mergedIndices.push(...usIdx.value);
      setIndices(mergedIndices);
      if (scanRes.status === "fulfilled") setScannerHits(scanRes.value.items);
      if (sigRes.status === "fulfilled") setSignals(sigRes.value.items);
      if (newsRes.status === "fulfilled") setNews(newsRes.value.items);
      if (congressRes.status === "fulfilled") {
        setDisclosures(congressRes.value.items);
        setStockActNotice(congressRes.value.stock_act_notice);
      }
      if (perfRes.status === "fulfilled") setPerformance(perfRes.value);
      if (wlRes.status === "fulfilled") setWatchlists(wlRes.value);
      if (notifRes.status === "fulfilled") {
        setNotifications(notifRes.value.items);
        setUnreadCount(notifRes.value.unread_count);
      }
      if (nPrefRes.status === "fulfilled") setNotifPrefs(nPrefRes.value);
      if (uPrefRes.status === "fulfilled") setUserPrefs(uPrefRes.value);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/v1/health`, { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        if (data?.kill_switch?.enabled) setKillSwitchEnabled(true);
      })
      .catch(() => {});

    fetchCurrentUser()
      .then((u) => {
        setUser(u);
        setAuthChecked(true);
        void loadDashboardData();
      })
      .catch(() => {
        setUser(null);
        setAuthChecked(true);
      });
  }, [loadDashboardData]);

  const streamState = useRealtimeStream({
    enabled: Boolean(user),
    onEvent: (env) => {
      if (
        env.type === "signal.created" ||
        env.type === "signal.updated" ||
        env.type === "notification.created" ||
        env.type === "market.status"
      ) {
        void loadDashboardData();
      }
    },
    onResyncRequired: () => {
      void loadDashboardData();
    },
  });

  const handleLogout = async () => {
    try {
      await logoutAccount();
    } finally {
      setUser(null);
      window.location.assign("/login");
    }
  };

  return (
    <AppShell
      activeNav={activeNav}
      onNavChange={setActiveNav}
      marketScope={marketScope}
      onMarketScopeChange={setMarketScope}
      user={user}
      onLogout={handleLogout}
      unreadNotifications={unreadCount}
      streamState={streamState}
      killSwitchEnabled={killSwitchEnabled}
    >
      {!authChecked ? (
        <div className="py-24 text-center text-sm text-muted-foreground">
          Verifying secure session...
        </div>
      ) : !user ? (
        <section className="max-w-xl mx-auto my-12 rounded-2xl border border-border bg-card p-8 text-center space-y-5">
          <div className="mx-auto h-12 w-12 rounded-xl bg-accent/15 text-accent flex items-center justify-center">
            <Lock className="h-6 w-6" />
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight">
              AI Trading Intelligence Platform
            </h1>
            <p className="text-sm text-muted-foreground">
              Sign in with your subscriber account to access real-time India (NSE/BSE) &amp; US
              (NASDAQ/NYSE) stock scans, risk-validated signals, TradingView charts, and AI analysis.
            </p>
          </div>
          <div className="flex items-center justify-center gap-3">
            <Link
              href="/login"
              className="px-5 py-2.5 rounded-lg bg-accent text-accent-foreground text-sm font-semibold hover:opacity-90"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="px-5 py-2.5 rounded-lg border border-border text-sm font-medium hover:bg-muted"
            >
              Create Account
            </Link>
          </div>
          <div className="inline-flex items-center gap-2 text-xs text-emerald-400 font-mono pt-2">
            <ShieldCheck className="h-4 w-4" />
            <span>SIGNALS-ONLY • SINGLE ACTIVE SESSION ENFORCED</span>
          </div>
        </section>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-end">
            <button
              type="button"
              onClick={() => void loadDashboardData()}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-border bg-card text-xs text-muted-foreground hover:text-foreground"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
              <span>{refreshing ? "Syncing..." : "Refresh Data"}</span>
            </button>
          </div>

          {activeNav === "overview" || activeNav === "market-overview" ? (
            <OverviewView
              marketScope={marketScope}
              marketStatuses={marketStatuses}
              indices={indices}
              signals={signals}
              news={news}
              performance={performance}
              onSelectSignal={setSelectedSignal}
              onOpenScanner={() => setActiveNav("opportunities")}
            />
          ) : activeNav === "scanner" ? (
            <ScannerAndSignalsView
              mode="scanner"
              title="Multi-Market Stock Scanner"
              marketScope={marketScope}
              scannerHits={scannerHits}
              signals={signals}
              onSelectSignal={setSelectedSignal}
            />
          ) : activeNav === "opportunities" ||
            activeNav === "india-market" ||
            activeNav === "us-market" ? (
            <ScannerAndSignalsView
              mode="opportunities"
              title={
                activeNav === "india-market"
                  ? "India Market (NSE/BSE) Signals"
                  : activeNav === "us-market"
                    ? "US Market (NASDAQ/NYSE) Signals"
                    : "Trading Opportunities"
              }
              marketScope={marketScope}
              scannerHits={scannerHits}
              signals={signals}
              onSelectSignal={setSelectedSignal}
            />
          ) : activeNav === "stock-analysis" ? (
            <StockAnalysisView marketScope={marketScope} />
          ) : activeNav === "news" ? (
            <NewsAndDisclosuresView
              marketScope={marketScope}
              news={news}
              disclosures={disclosures}
              stockActNotice={stockActNotice}
            />
          ) : activeNav === "ai-analyst" ? (
            <AIAnalystView marketScope={marketScope} />
          ) : activeNav === "watchlist" ? (
            <WatchlistView watchlists={watchlists} onRefresh={loadDashboardData} />
          ) : activeNav === "notifications" ? (
            <NotificationsView
              notifications={notifications}
              unreadCount={unreadCount}
              prefs={notifPrefs}
              onRefresh={loadDashboardData}
            />
          ) : activeNav === "settings" ? (
            <AccountSettingsView
              user={user}
              userPrefs={userPrefs}
              onRefresh={loadDashboardData}
            />
          ) : activeNav === "journal" ? (
            <JournalView />
          ) : activeNav === "performance" ? (
            <PerformanceView marketScope={marketScope} />
          ) : activeNav === "admin" ? (
            <SuperAdminView />
          ) : activeNav === "subscription" ? (
            <SubscriptionBillingView user={user} onRefresh={loadDashboardData} />
          ) : (
            <div className="rounded-xl border border-border bg-card p-8 text-center space-y-2">
              <h2 className="text-lg font-semibold capitalize">{activeNav.replace("-", " ")}</h2>
              <p className="text-xs text-muted-foreground">
                Section content ready.
              </p>
            </div>
          )}
        </div>
      )}

      {selectedSignal && (
        <SignalDetailPanel signal={selectedSignal} onClose={() => setSelectedSignal(null)} />
      )}
    </AppShell>
  );
}
