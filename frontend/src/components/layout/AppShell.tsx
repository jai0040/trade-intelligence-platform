"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  CreditCard,
  Globe,
  LayoutDashboard,
  LineChart,
  LogIn,
  LogOut,
  Menu,
  Moon,
  Newspaper,
  Radar,
  Settings,
  ShieldAlert,
  Sparkles,
  Star,
  Sun,
  TrendingUp,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import type { UserProfile } from "@/lib/api";
import type { StreamConnectionState } from "@/lib/useRealtimeStream";
import { cn, formatMarketClock } from "@/lib/utils";

export type MarketScope = "ALL" | "IN" | "US";

export type NavSectionId =
  | "overview"
  | "india-market"
  | "us-market"
  | "market-overview"
  | "scanner"
  | "opportunities"
  | "stock-analysis"
  | "news"
  | "ai-analyst"
  | "watchlist"
  | "journal"
  | "performance"
  | "notifications"
  | "subscription"
  | "settings"
  | "admin";

interface NavItem {
  id: NavSectionId;
  label: string;
  badge?: string;
  adminOnly?: boolean;
  icon: React.ComponentType<{ className?: string }>;
}

const SUBSCRIBER_NAV: NavItem[] = [
  { id: "overview", label: "Overview Dashboard", icon: LayoutDashboard },
  { id: "india-market", label: "India Market (NSE/BSE)", icon: TrendingUp },
  { id: "us-market", label: "US Market (NASDAQ/NYSE)", icon: Globe },
  { id: "market-overview", label: "Market Overview", icon: Activity },
  { id: "scanner", label: "Stock Scanner", icon: Radar },
  { id: "opportunities", label: "Trading Opportunities", icon: Sparkles },
  { id: "stock-analysis", label: "Stock Analysis & Charts", icon: LineChart },
  { id: "news", label: "News & Filings", icon: Newspaper },
  { id: "ai-analyst", label: "AI Analyst", icon: Bot },
  { id: "watchlist", label: "Portfolio / Watchlist", icon: Star },
  { id: "journal", label: "Trading Journal", icon: BookOpen },
  { id: "performance", label: "Historical Performance", icon: BarChart3 },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "subscription", label: "Subscription & Billing", badge: "P9", icon: CreditCard },
  { id: "settings", label: "Account Settings", icon: Settings },
  { id: "admin", label: "Super Admin Panel", adminOnly: true, icon: ShieldAlert },
];

interface AppShellProps {
  children: React.ReactNode;
  activeNav: NavSectionId;
  onNavChange: (nav: NavSectionId) => void;
  marketScope: MarketScope;
  onMarketScopeChange: (scope: MarketScope) => void;
  user: UserProfile | null;
  onLogout?: () => void;
  unreadNotifications?: number;
  streamState?: StreamConnectionState;
  killSwitchEnabled?: boolean;
}

export function AppShell({
  children,
  activeNav,
  onNavChange,
  marketScope,
  onMarketScopeChange,
  user,
  onLogout,
  unreadNotifications = 0,
  streamState = "offline",
  killSwitchEnabled = false,
}: AppShellProps) {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [clocks, setClocks] = useState<{ ist: string; et: string }>({
    ist: "--:--:--",
    et: "--:--:--",
  });

  useEffect(() => {
    const updateClocks = () => {
      const now = new Date();
      setClocks({
        ist: formatMarketClock("Asia/Kolkata", now),
        et: formatMarketClock("America/New_York", now),
      });
    };
    updateClocks();
    const timer = setInterval(updateClocks, 1000);
    return () => clearInterval(timer);
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.classList.toggle("dark", next === "dark");
  };

  const visibleNav = SUBSCRIBER_NAV.filter(
    (item) => !item.adminOnly || user?.role === "super_admin" || user?.role === "admin"
  );

  const handleNavSelect = (id: NavSectionId) => {
    onNavChange(id);
    if (id === "india-market") onMarketScopeChange("IN");
    if (id === "us-market") onMarketScopeChange("US");
    setMobileMenuOpen(false);
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex lg:w-64 lg:flex-col border-r border-border bg-card/70 backdrop-blur">
        <div className="h-16 px-5 flex items-center justify-between border-b border-border">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-accent/15 border border-accent/40 flex items-center justify-center">
              <Activity className="h-4 w-4 text-accent" />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight">TradeIntel AI</div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                Multi-Market SaaS
              </div>
            </div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {visibleNav.map((item) => {
            const Icon = item.icon;
            const isActive = activeNav === item.id;
            const showUnread = item.id === "notifications" && unreadNotifications > 0;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleNavSelect(item.id)}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-colors",
                  isActive
                    ? "bg-accent/15 text-accent border border-accent/30"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                )}
              >
                <span className="flex items-center gap-2.5 truncate">
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </span>
                {showUnread ? (
                  <span className="px-1.5 py-0.5 rounded-full bg-accent text-accent-foreground text-[10px] font-mono tabular-nums">
                    {unreadNotifications}
                  </span>
                ) : item.badge ? (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                    {item.badge}
                  </span>
                ) : null}
              </button>
            );
          })}
        </nav>

        <div className="p-3 border-t border-border text-[11px] text-muted-foreground space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-medium text-foreground">Mode</span>
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-mono text-[10px]">
              SIGNALS-ONLY
            </span>
          </div>
          <p className="text-[10px] leading-relaxed">
            No live broker execution. Charts powered by TradingView Lightweight Charts (Apache-2.0).
          </p>
        </div>
      </aside>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div className="fixed inset-0 bg-black/60" onClick={() => setMobileMenuOpen(false)} />
          <div className="relative z-10 w-72 max-w-[85vw] bg-card border-r border-border flex flex-col">
            <div className="h-16 px-4 flex items-center justify-between border-b border-border">
              <span className="text-sm font-semibold">TradeIntel AI</span>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="p-1.5 rounded-md hover:bg-muted"
                aria-label="Close navigation menu"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <nav className="flex-1 overflow-y-auto p-3 space-y-1">
              {visibleNav.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => handleNavSelect(item.id)}
                    className={cn(
                      "w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs",
                      activeNav === item.id
                        ? "bg-accent/15 text-accent"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                  >
                    <span className="flex items-center gap-2.5">
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </span>
                    {item.badge && <span className="text-[10px] font-mono">{item.badge}</span>}
                  </button>
                );
              })}
            </nav>
          </div>
        </div>
      )}

      {/* Main Content Column */}
      <div className="flex-1 flex flex-col min-w-0">
        {killSwitchEnabled && (
          <div
            role="alert"
            className="bg-red-500/15 border-b border-red-500/40 px-4 py-2 text-xs text-red-200 flex items-center justify-center gap-2"
          >
            <AlertTriangle className="h-4 w-4 text-red-400 shrink-0" />
            <span>
              <strong>Global Emergency Kill Switch Active:</strong> Automated signal publishing is
              temporarily paused by administration. Historical signals remain readable.
            </span>
          </div>
        )}

        {/* Top Bar */}
        <header className="h-16 border-b border-border bg-card/60 backdrop-blur px-4 lg:px-6 flex items-center justify-between gap-3 sticky top-0 z-30">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden p-2 rounded-lg border border-border hover:bg-muted"
              aria-label="Open navigation menu"
            >
              <Menu className="h-4 w-4" />
            </button>

            {/* Persistent Market Switcher */}
            <div className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5 text-xs">
              {(["ALL", "IN", "US"] as const).map((scope) => (
                <button
                  key={scope}
                  type="button"
                  onClick={() => onMarketScopeChange(scope)}
                  className={cn(
                    "px-2.5 sm:px-3 py-1.5 rounded-md font-medium transition-colors",
                    marketScope === scope
                      ? "bg-card text-foreground shadow-sm border border-border"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {scope === "ALL" ? "All Markets" : scope === "IN" ? "India" : "US"}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Dual Market Clock Pills */}
            <div className="hidden xl:flex items-center gap-2 text-xs font-mono tabular-nums">
              <div className="px-2.5 py-1 rounded-md bg-muted/60 border border-border flex items-center gap-1.5">
                <span className="text-muted-foreground">IST</span>
                <span className="text-foreground">{clocks.ist}</span>
              </div>
              <div className="px-2.5 py-1 rounded-md bg-muted/60 border border-border flex items-center gap-1.5">
                <span className="text-muted-foreground">ET</span>
                <span className="text-foreground">{clocks.et}</span>
              </div>
            </div>

            {/* Stream Status Pill */}
            {user && (
              <div
                title={`Real-time stream: ${streamState}`}
                className={cn(
                  "hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[11px] font-mono",
                  streamState === "connected"
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                    : "border-border bg-muted/40 text-muted-foreground"
                )}
              >
                {streamState === "connected" ? (
                  <Wifi className="h-3.5 w-3.5" />
                ) : (
                  <WifiOff className="h-3.5 w-3.5" />
                )}
                <span className="uppercase">{streamState}</span>
              </div>
            )}

            {/* Notifications Bell */}
            {user && (
              <button
                type="button"
                onClick={() => onNavChange("notifications")}
                className="relative p-2 rounded-lg border border-border hover:bg-muted transition-colors"
                aria-label="Open notifications"
              >
                <Bell className="h-4 w-4" />
                {unreadNotifications > 0 && (
                  <span className="absolute -top-1 -right-1 h-4 min-w-[16px] px-1 rounded-full bg-accent text-accent-foreground text-[10px] font-mono flex items-center justify-center">
                    {unreadNotifications}
                  </span>
                )}
              </button>
            )}

            <button
              type="button"
              onClick={toggleTheme}
              className="p-2 rounded-lg border border-border hover:bg-muted transition-colors"
              aria-label="Toggle theme"
              title="Toggle Dark / Light Theme"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>

            {user ? (
              <button
                type="button"
                onClick={onLogout}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border text-xs hover:bg-muted transition-colors"
                title={`Signed in as ${user.email}`}
              >
                <LogOut className="h-3.5 w-3.5" />
                <span className="hidden md:inline">Sign Out</span>
              </button>
            ) : (
              <Link
                href="/login"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent text-accent-foreground text-xs font-semibold hover:opacity-90"
              >
                <LogIn className="h-3.5 w-3.5" />
                <span>Sign In</span>
              </Link>
            )}
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-6 max-w-7xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}
