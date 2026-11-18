"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertCircle, Lock, ShieldCheck } from "lucide-react";
import { ApiRequestError, loginAccount } from "@/lib/api";

function LoginFormContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const reason = searchParams.get("reason");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sessionNotice =
    reason === "session_superseded"
      ? "You were signed out because your account was signed in from another device or browser."
      : reason === "session_revoked"
        ? "Your session was revoked. Please sign in again."
        : null;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await loginAccount({ email, password });
      router.push("/");
    } catch (err: unknown) {
      if (err instanceof ApiRequestError) {
        setError(err.message);
      } else {
        setError("Unable to sign in right now. Please check your connection.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-8 shadow-xl space-y-6">
        <div className="space-y-2 text-center">
          <div className="mx-auto inline-flex h-11 w-11 items-center justify-center rounded-xl bg-accent/15 text-accent">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Sign in to AI Trading Intelligence
          </h1>
          <p className="text-sm text-muted-foreground">
            Multi-Market Signals-Only Platform (India NSE/BSE &amp; US NASDAQ/NYSE)
          </p>
        </div>

        {sessionNotice && (
          <div
            role="status"
            className="flex items-start gap-2.5 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200"
          >
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0 text-amber-400" />
            <span>{sessionNotice}</span>
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="flex items-start gap-2.5 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300"
          >
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-sm font-medium">
              Email Address
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="trader@example.com"
              className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm outline-none focus:border-accent"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-sm font-medium">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm outline-none focus:border-accent"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground transition hover:opacity-90 disabled:opacity-50"
          >
            <Lock className="h-4 w-4" />
            {submitting ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <div className="border-t border-border pt-4 text-center text-xs text-muted-foreground space-y-2">
          <p>
            Single Active Session security is enforced: signing in here will sign out any
            earlier device automatically.
          </p>
          <p>
            New to the platform?{" "}
            <Link href="/register" className="font-medium text-accent hover:underline">
              Create an account
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-background" />}>
      <LoginFormContent />
    </Suspense>
  );
}
