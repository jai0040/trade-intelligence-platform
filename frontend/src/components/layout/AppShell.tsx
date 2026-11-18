"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  CreditCard,
  Globe,
  LayoutDashboard,
  LineChart,
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
  X,
} from "lucide-react";
import { cn, formatMarketClock } from "@/lib/utils";

export type MarketScope = "ALL" | "IN" | "US";

interface NavItem {
  id: string;
  label: string;
  phase: string;
  icon: React.ComponentType<{ className?: string }>;
}

const SUBSCRIBER_NAV: NavItem[] = [
  { id: "overview", label: "Overview Dashboard", phase: "P7", icon: LayoutDashboard },
  { id: "india-market", label: "India Market (NSE/BSE)", phase: "P7", icon: TrendingUp },
  { id: "us-market", label: "US Market (NASDAQ/NYSE)", phase: "P7", icon: Globe },
  { id: "market-overview", label: "Market Overview", phase: "P7", icon: Activity },
  { id: "scanner", label: "Stock Scanner", phase: "P7", icon: Radar },
  { id: "opportunities", label: "Trading Opportunities", phase: "P7", icon: Sparkles },
  { id: "stock-analysis", label: "Stock Analysis & Charts", phase: "P7", icon: LineChart },
  { id: "news", label: "Market News & Filings", phase: "P7", icon: Newspaper },
  { id: "ai-analyst", label: "AI Analyst", phase: "P7", icon: Bot },
  { id: "watchlist", label: "Portfolio / Watchlist", phase: "P7", icon: Star },
  { id: "journal", label: "Trading Journal", phase: "P8", icon: BookOpen },
  { id: "performance", label: "Historical Performance", phase: "P8", icon: BarChart3 },
  { id: "notifications", label: "Notifications", phase: "P7", icon: Bell },
  { id: "subscription", label: "Subscription & Billing", phase: "P9", icon: CreditCard },
  { id: "settings", label: "Account Settings", phase: "P4", icon: Settings },
  { id: "admin", label: "Super Admin Panel", phase: "P8", icon: ShieldAlert },
];

interface AppShellProps {
  children: React.ReactNode;
  marketScope: MarketScope;
  onMarketScopeChange: (scope: MarketScope) => void;
}

export function AppShell({ children, marketScope, onMarketScopeChange }: AppShellProps) {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeNav, setActiveNav] = useState("overview");
  const [clocks, setClocks] = useState<{ ist: string; et: string }>({ ist: "--:--:--", et: "--:--:--" });

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
          {SUBSCRIBER_NAV.map((item) => {
            const Icon = item.icon;
            const isActive = activeNav === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveNav(item.id)}
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
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                  {item.phase}
                </span>
              </button>
            );
          })}
        </nav>

        <div className="p-3 border-t border-border text-[11px] text-muted-foreground space-y-1">
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
              {SUBSCRIBER_NAV.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setActiveNav(item.id);
                      setMobileMenuOpen(false);
                    }}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    <span className="flex items-center gap-2.5">
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </span>
                    <span className="text-[10px] font-mono">{item.phase}</span>
                  </button>
                );
              })}
            </nav>
          </div>
        </div>
      )}

      {/* Main Content Column */}
      <div className="flex-1 flex flex-col min-w-0">
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
                    "px-3 py-1.5 rounded-md font-medium transition-colors",
                    marketScope === scope
                      ? "bg-card text-foreground shadow-sm border border-border"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {scope === "ALL" ? "All Markets" : scope === "IN" ? "India (NSE/BSE)" : "US (NASDAQ/NYSE)"}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Dual Market Clock Pills */}
            <div className="hidden md:flex items-center gap-2 text-xs font-mono tabular-nums">
              <div className="px-2.5 py-1 rounded-md bg-muted/60 border border-border flex items-center gap-1.5">
                <span className="text-muted-foreground">IST</span>
                <span className="text-foreground">{clocks.ist}</span>
              </div>
              <div className="px-2.5 py-1 rounded-md bg-muted/60 border border-border flex items-center gap-1.5">
                <span className="text-muted-foreground">ET</span>
                <span className="text-foreground">{clocks.et}</span>
              </div>
            </div>

            <button
              type="button"
              onClick={toggleTheme}
              className="p-2 rounded-lg border border-border hover:bg-muted transition-colors"
              aria-label="Toggle theme"
              title="Toggle Dark / Light Theme"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-6 max-w-7xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}
