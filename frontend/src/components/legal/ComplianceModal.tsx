"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  FileText,
  Globe,
  Lock,
  Scale,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ComplianceModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type TabId = "terms" | "risk" | "sebi-sec" | "data-licenses" | "privacy";

export function ComplianceModal({ isOpen, onClose }: ComplianceModalProps) {
  const [activeTab, setActiveTab] = useState<TabId>("terms");

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
      <div className="rounded-xl border border-border bg-card max-w-3xl w-full max-h-[85vh] flex flex-col shadow-2xl animate-in fade-in zoom-in-95">
        {/* Header */}
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Scale className="w-5 h-5 text-primary" />
            <div>
              <h2 className="text-base font-bold text-foreground">
                Legal, Regulatory &amp; Compliance Disclosures
              </h2>
              <p className="text-2xs text-muted-foreground">
                Operating Policy: <strong>HARD-LOCKED SIGNALS-ONLY MODE</strong> (NSE/BSE &amp; NASDAQ/NYSE)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted"
            aria-label="Close legal modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab navigation */}
        <div className="flex border-b border-border bg-muted/30 px-3 overflow-x-auto text-xs">
          <button
            onClick={() => setActiveTab("terms")}
            className={cn(
              "px-3 py-2.5 font-medium border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5",
              activeTab === "terms"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            <FileText className="w-3.5 h-3.5" />
            Terms of Service
          </button>
          <button
            onClick={() => setActiveTab("risk")}
            className={cn(
              "px-3 py-2.5 font-medium border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5",
              activeTab === "risk"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            Risk &amp; Non-Guarantee
          </button>
          <button
            onClick={() => setActiveTab("sebi-sec")}
            className={cn(
              "px-3 py-2.5 font-medium border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5",
              activeTab === "sebi-sec"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            <Scale className="w-3.5 h-3.5" />
            SEBI &amp; SEC Regulatory
          </button>
          <button
            onClick={() => setActiveTab("data-licenses")}
            className={cn(
              "px-3 py-2.5 font-medium border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5",
              activeTab === "data-licenses"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            <Globe className="w-3.5 h-3.5" />
            Market Data &amp; Licenses
          </button>
          <button
            onClick={() => setActiveTab("privacy")}
            className={cn(
              "px-3 py-2.5 font-medium border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5",
              activeTab === "privacy"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            <Lock className="w-3.5 h-3.5" />
            Privacy (DPDP &amp; GDPR)
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-4 text-xs text-muted-foreground leading-relaxed">
          {activeTab === "terms" && (
            <div className="space-y-3">
              <h3 className="text-sm font-bold text-foreground">1. Nature of the SaaS Platform</h3>
              <p>
                The Trade Intelligence Platform provides quantitative algorithms, technical analysis patterns, mathematical indicators, and read-only signal reference sheets for Indian (NSE/BSE) and US (NASDAQ/NYSE) equities.
              </p>
              <div className="p-3.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-300">
                <strong className="text-emerald-400">Strict Signals-Only Architecture:</strong> The Platform never connects to live broker accounts, never routes electronic orders, and never holds client capital or securities. All trade sheets are strictly read-only for educational and analytical purposes.
              </div>
              <h3 className="text-sm font-bold text-foreground pt-2">2. Independent User Discretion</h3>
              <p>
                Any transaction entered by a user on third-party brokerage platforms is executed solely at the user&apos;s independent judgment and risk. The Platform and its developers disclaim any liability for trading losses, slippage, or exchange outages.
              </p>
            </div>
          )}

          {activeTab === "risk" && (
            <div className="space-y-3">
              <div className="p-3.5 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-300 flex items-start gap-2.5">
                <ShieldAlert className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
                <div>
                  <strong className="text-rose-300">High-Risk Financial Disclosure:</strong> Trading equities and derivatives carries substantial risk of capital loss. You may lose all of your deposited capital. Never risk funds you cannot afford to lose.
                </div>
              </div>
              <h3 className="text-sm font-bold text-foreground pt-1">No Guarantee of Profitability</h3>
              <p>
                Past performance, backtest simulations, setup quality scores (0–100), and historical win-rates do not guarantee future profitability. Realized outcomes are subject to spread costs, execution latency, market gaps, and price slippage.
              </p>
              <h3 className="text-sm font-bold text-foreground pt-1">Impersonal Analytics</h3>
              <p>
                Algorithms evaluate publicly available exchange ticks. Signals do not consider your individual financial standing, tax status, risk profile, or investment goals.
              </p>
            </div>
          )}

          {activeTab === "sebi-sec" && (
            <div className="space-y-3">
              <h3 className="text-sm font-bold text-foreground">India: SEBI Regulatory Posture</h3>
              <p>
                The Platform operates strictly as a quantitative algorithmic data processing tool. It is <strong>not</strong> registered as an Investment Adviser (IA) under SEBI (Investment Advisers) Regulations 2013, nor as a Portfolio Manager (PMS) under SEBI Regulations 2020.
              </p>
              <p>
                Position-sizing features are deterministic mathematical calculators based on user-entered risk inputs, not personalized financial advice.
              </p>

              <h3 className="text-sm font-bold text-foreground pt-2">United States: SEC Publisher&apos;s Exclusion</h3>
              <p>
                Under Section 202(a)(11)(D) of the Investment Advisers Act of 1940 and Supreme Court precedent (<em>Lowe v. SEC</em>, 472 U.S. 181), the Platform operates as a bona fide impersonal publisher of regular market statistics and computational data.
              </p>
              <p>
                Congressional stock transaction records (PTRs) are public records from the US House Clerk. Notice: filings may carry up to a <strong>45-day statutory disclosure lag</strong> under the STOCK Act of 2012.
              </p>
            </div>
          )}

          {activeTab === "data-licenses" && (
            <div className="space-y-3">
              <h3 className="text-sm font-bold text-foreground">Commercial Market Data Redistribution</h3>
              <p>
                Market data feeds for NSE, BSE, NASDAQ, and NYSE are delivered under licensed commercial agreements. Scraping, unauthorized redistribution, automated polling beyond API limits, or reverse-engineering is strictly prohibited.
              </p>
              <h3 className="text-sm font-bold text-foreground pt-2">Open Source Attributions</h3>
              <ul className="list-disc pl-5 space-y-1.5">
                <li>
                  <strong>TradingView Lightweight Charts:</strong> Licensed under Apache-2.0. Copyright &copy; TradingView, Inc.
                </li>
                <li>
                  <strong>Day Trader Skill:</strong> Licensed under MIT License. Copyright &copy; 2024 Jake Schincariol. Verbatim notices preserved in <code>THIRD_PARTY_NOTICES</code>.
                </li>
              </ul>
            </div>
          )}

          {activeTab === "privacy" && (
            <div className="space-y-3">
              <h3 className="text-sm font-bold text-foreground">DPDP Act (India) &amp; GDPR (EU) Compliance</h3>
              <p>
                We adhere to strict data minimization. Personal trading journal entries, watchlist items, and notification settings are strictly tenant-isolated via row-level security constraints (<code>WHERE user_id = :current_user_id</code>).
              </p>
              <h3 className="text-sm font-bold text-foreground pt-1">Cryptographic Security</h3>
              <p>
                User passwords are protected by memory-hard <strong>Argon2id</strong> hashing. Server sessions are cryptographically randomized opaque tokens. Double-submit CSRF tokens protect all state-changing requests.
              </p>
              <h3 className="text-sm font-bold text-foreground pt-1">Data Erasure &amp; Portability</h3>
              <p>
                Subscribers may export their trading journals or request complete account erasure by contacting support or via account settings.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border flex items-center justify-between bg-muted/20">
          <div className="flex items-center gap-1.5 text-2xs text-muted-foreground">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Fully compliant with SEBI, SEC publisher exclusion &amp; DPDP standards.</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold"
          >
            I Understand &amp; Agree
          </button>
        </div>
      </div>
    </div>
  );
}
