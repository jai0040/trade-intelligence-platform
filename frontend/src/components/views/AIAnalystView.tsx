"use client";

import React, { useState } from "react";
import { Bot, Send, ShieldCheck } from "lucide-react";
import type { MarketScope } from "@/components/layout/AppShell";
import { queryAIAnalyst } from "@/lib/api";

interface AIAnalystViewProps {
  marketScope: MarketScope;
}

interface QAEntry {
  question: string;
  answer: string;
  disclaimer: string;
  scope: string;
}

const QUICK_PROMPTS = [
  "Summarize the highest-quality setups right now",
  "Compare risk/reward ratios on today's India setups",
  "What are the top US breakout opportunities?",
];

export function AIAnalystView({ marketScope }: AIAnalystViewProps) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<QAEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submitQuestion = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await queryAIAnalyst(q.trim(), marketScope);
      setHistory((prev) => [
        {
          question: res.question,
          answer: res.answer,
          disclaimer: res.disclaimer,
          scope: res.market_scope,
        },
        ...prev,
      ]);
      setQuestion("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "AI query failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5 max-w-4xl">
      <div>
        <h1 className="text-xl font-semibold flex items-center gap-2">
          <Bot className="h-5 w-5 text-accent" />
          AI Analyst (Read-Only Explanation Layer)
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          Grounded exclusively in deterministic, trader-risk PASSED signals. Cannot modify entry,
          stop-loss, or target prices or bypass risk rejections.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => submitQuestion(prompt)}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg border border-border bg-card text-xs text-muted-foreground hover:text-foreground hover:border-accent/50 transition-colors"
          >
            {prompt}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submitQuestion(question);
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about active India/US setups, R:R geometry, or catalysts..."
          className="flex-1 rounded-xl border border-border bg-card px-4 py-2.5 text-sm outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-xs font-semibold text-accent-foreground hover:opacity-90 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
          <span>{loading ? "Analyzing..." : "Ask AI"}</span>
        </button>
      </form>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-300">
          {error}
        </div>
      )}

      <div className="space-y-4">
        {history.map((entry, idx) => (
          <article key={idx} className="rounded-xl border border-border bg-card p-5 space-y-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">Q: {entry.question}</span>
              <span className="font-mono px-2 py-0.5 rounded bg-muted">Scope: {entry.scope}</span>
            </div>
            <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed text-foreground/95 bg-background/60 p-3.5 rounded-lg border border-border">
              {entry.answer}
            </pre>
            <div className="flex items-center gap-1.5 text-[11px] text-amber-300/90">
              <ShieldCheck className="h-3.5 w-3.5 shrink-0" />
              <span>{entry.disclaimer}</span>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
