"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle2, UserPlus } from "lucide-react";
import { ApiRequestError, registerAccount } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [countryCode, setCountryCode] = useState("IN");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await registerAccount({
        full_name: fullName,
        email,
        password,
        country_code: countryCode,
      });
      setCreated(true);
      setTimeout(() => router.push("/login"), 1200);
    } catch (err: unknown) {
      if (err instanceof ApiRequestError) {
        setError(err.message);
      } else {
        setError("Unable to create account right now.");
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
            <UserPlus className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Create Subscriber Account</h1>
          <p className="text-sm text-muted-foreground">
            Signals-only intelligence for Indian &amp; US equity markets. Never executes live orders.
          </p>
        </div>

        {created && (
          <div className="flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-300">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>Account created! Redirecting to sign in...</span>
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
            <label htmlFor="fullName" className="text-sm font-medium">
              Full Name
            </label>
            <input
              id="fullName"
              type="text"
              required
              minLength={2}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Aarav Mehta"
              className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm outline-none focus:border-accent"
            />
          </div>

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
            <label htmlFor="country" className="text-sm font-medium">
              Primary Region
            </label>
            <select
              id="country"
              value={countryCode}
              onChange={(e) => setCountryCode(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm outline-none focus:border-accent"
            >
              <option value="IN">India (INR / IST)</option>
              <option value="US">United States (USD / ET)</option>
              <option value="GB">United Kingdom</option>
              <option value="SG">Singapore</option>
              <option value="AE">United Arab Emirates</option>
              <option value="CA">Canada</option>
              <option value="AU">Australia</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-sm font-medium">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={10}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm outline-none focus:border-accent"
            />
            <p className="text-xs text-muted-foreground">
              Minimum 10 characters including uppercase, lowercase, number, and symbol.
            </p>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground transition hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? "Creating account..." : "Create Account"}
          </button>
        </form>

        <p className="text-center text-xs text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-accent hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
