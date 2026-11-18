"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  CreditCard,
  ExternalLink,
  FileText,
  Lock,
  RefreshCw,
  ShieldCheck,
  XCircle,
  Zap,
} from "lucide-react";
import {
  cancelSubscription,
  createCheckoutSession,
  fetchMySubscription,
  fetchPaymentHistory,
  fetchSubscriptionPlans,
  type CheckoutSessionResult,
  type PaymentHistoryItem,
  type SubscriptionPlanItem,
  type UserProfile,
  type UserSubscriptionDetail,
} from "@/lib/api";
import { cn, formatCurrencyPrice, formatUtcTimestamp } from "@/lib/utils";

interface SubscriptionBillingViewProps {
  user: UserProfile | null;
  onRefresh?: () => void;
}

export function SubscriptionBillingView({ user, onRefresh }: SubscriptionBillingViewProps) {
  const [plans, setPlans] = useState<SubscriptionPlanItem[]>([]);
  const [subscription, setSubscription] = useState<UserSubscriptionDetail | null>(null);
  const [payments, setPayments] = useState<PaymentHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currencyFilter, setCurrencyFilter] = useState<"ALL" | "INR" | "USD">("ALL");

  // Checkout modal state
  const [checkoutResult, setCheckoutResult] = useState<CheckoutSessionResult | null>(null);
  const [checkoutLoadingPlanId, setCheckoutLoadingPlanId] = useState<string | null>(null);

  // Cancellation state
  const [cancelling, setCancelling] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadBillingData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [plansRes, subRes, paymentsRes] = await Promise.all([
        fetchSubscriptionPlans(),
        fetchMySubscription(),
        fetchPaymentHistory(50, 0),
      ]);
      setPlans(plansRes);
      setSubscription(subRes);
      setPayments(paymentsRes.items);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load subscription data.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBillingData();
  }, [loadBillingData]);

  const handleStartCheckout = async (plan: SubscriptionPlanItem) => {
    setCheckoutLoadingPlanId(plan.id);
    setError(null);
    setActionMessage(null);
    try {
      const provider: "razorpay" | "stripe" = plan.currency === "INR" ? "razorpay" : "stripe";
      const result = await createCheckoutSession({
        plan_id: plan.id,
        provider,
      });
      setCheckoutResult(result);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to initiate checkout session.";
      setError(msg);
    } finally {
      setCheckoutLoadingPlanId(null);
    }
  };

  const handleConfirmCancel = async () => {
    setCancelling(true);
    setError(null);
    try {
      const res = await cancelSubscription(cancelReason || "User requested cancellation");
      setActionMessage(res.message);
      setShowCancelConfirm(false);
      await loadBillingData();
      if (onRefresh) onRefresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to cancel subscription.";
      setError(msg);
    } finally {
      setCancelling(false);
    }
  };

  const filteredPlans = plans.filter((p) => {
    if (currencyFilter === "ALL") return true;
    return p.currency === currencyFilter;
  });

  const statusColor = (st: string) => {
    switch (st) {
      case "active":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "past_due":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "trialing":
        return "bg-blue-500/10 text-blue-400 border-blue-500/30";
      case "cancelled":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      case "expired":
        return "bg-rose-500/10 text-rose-400 border-rose-500/30";
      default:
        return "bg-muted text-muted-foreground border-border";
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <CreditCard className="w-5 h-5 text-primary" />
            Subscription &amp; Billing
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Manage your multi-market intelligence subscription, invoices, and payment gateways.
          </p>
        </div>
        <button
          onClick={loadBillingData}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card hover:bg-accent text-xs font-medium transition-colors"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-300 text-xs flex items-start gap-3">
          <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1 font-medium">{error}</div>
        </div>
      )}

      {actionMessage && (
        <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-xs flex items-start gap-3">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1 font-medium">{actionMessage}</div>
        </div>
      )}

      {/* Current Subscription Status Card */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-border/50 pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold">Current Plan:</span>
              <span className="text-sm font-bold text-foreground">
                {subscription?.plan?.name || "Free Tier / No Active Subscription"}
              </span>
              <span
                className={cn(
                  "px-2 py-0.5 text-2xs uppercase tracking-wider font-semibold rounded-full border",
                  statusColor(subscription?.subscription_status || "none")
                )}
              >
                {subscription?.subscription_status || "none"}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Market Entitlements:{" "}
              {subscription?.entitled_markets && subscription.entitled_markets.length > 0 ? (
                <span className="font-semibold text-foreground">
                  {subscription.entitled_markets.join(", ")}
                </span>
              ) : (
                "None"
              )}{" "}
              • Gateway:{" "}
              <span className="uppercase font-semibold">
                {subscription?.provider || "N/A"}
              </span>
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            {subscription?.subscription_status === "active" && !subscription.cancel_at_period_end && (
              <button
                onClick={() => setShowCancelConfirm(true)}
                className="px-3 py-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-xs font-medium transition-colors"
              >
                Cancel Subscription
              </button>
            )}
            {subscription?.cancel_at_period_end && (
              <span className="text-xs text-purple-400 font-medium px-2.5 py-1 rounded-md border border-purple-500/30 bg-purple-500/10">
                Cancels at period end
              </span>
            )}
          </div>
        </div>

        {/* Period & Grace details */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div className="p-3 rounded-lg border border-border/60 bg-background/50">
            <div className="text-muted-foreground flex items-center gap-1.5 mb-1">
              <Calendar className="w-3.5 h-3.5" />
              Period Start
            </div>
            <div className="font-semibold text-foreground">
              {subscription?.current_period_start
                ? formatUtcTimestamp(subscription.current_period_start)
                : "—"}
            </div>
          </div>
          <div className="p-3 rounded-lg border border-border/60 bg-background/50">
            <div className="text-muted-foreground flex items-center gap-1.5 mb-1">
              <Calendar className="w-3.5 h-3.5" />
              Period End
            </div>
            <div className="font-semibold text-foreground">
              {subscription?.current_period_end
                ? formatUtcTimestamp(subscription.current_period_end)
                : "—"}
            </div>
          </div>
          <div className="p-3 rounded-lg border border-border/60 bg-background/50">
            <div className="text-muted-foreground flex items-center gap-1.5 mb-1">
              <Clock className="w-3.5 h-3.5" />
              Grace Until
            </div>
            <div className="font-semibold text-foreground">
              {subscription?.grace_until ? formatUtcTimestamp(subscription.grace_until) : "—"}
            </div>
          </div>
        </div>

        {/* Grace Warning Banner if in past_due */}
        {subscription?.subscription_status === "past_due" && (
          <div className="p-3.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-300 text-xs flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <div>
              <span className="font-semibold">Grace Period Active:</span> Your billing renewal failed or is pending. Your signals access remains open until the grace expiration timestamp above. Verified webhooks automatically renew your status upon receipt.
            </div>
          </div>
        )}

        {/* Signals-only compliance notice */}
        <div className="flex items-center gap-2 text-2xs text-muted-foreground pt-1">
          <Lock className="w-3.5 h-3.5 text-primary flex-shrink-0" />
          <span>
            Operating Policy: <strong>SIGNALS-ONLY MODE</strong>. All subscriptions provide algorithmic trading intelligence signals and reference sheets. No automated broker execution is supported.
          </span>
        </div>
      </div>

      {/* Available Plans Section */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Available Subscription Plans</h2>
            <p className="text-xs text-muted-foreground">
              Instant activation via verified server webhooks. No manual key exchange required.
            </p>
          </div>
          {/* Currency Toggle */}
          <div className="flex items-center rounded-lg border border-border bg-card p-0.5 text-xs">
            <button
              onClick={() => setCurrencyFilter("ALL")}
              className={cn(
                "px-3 py-1 rounded-md font-medium transition-colors",
                currencyFilter === "ALL"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              All Plans
            </button>
            <button
              onClick={() => setCurrencyFilter("INR")}
              className={cn(
                "px-3 py-1 rounded-md font-medium transition-colors",
                currencyFilter === "INR"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              India (INR / Razorpay)
            </button>
            <button
              onClick={() => setCurrencyFilter("USD")}
              className={cn(
                "px-3 py-1 rounded-md font-medium transition-colors",
                currencyFilter === "USD"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              US &amp; Global (USD / Stripe)
            </button>
          </div>
        </div>

        {/* Plans Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {filteredPlans.map((plan) => {
            const isCurrent = subscription?.plan?.id === plan.id;
            const isINR = plan.currency === "INR";
            return (
              <div
                key={plan.id}
                className={cn(
                  "rounded-xl border p-5 flex flex-col justify-between transition-all bg-card",
                  isCurrent
                    ? "border-primary/60 ring-1 ring-primary/40 bg-primary/5"
                    : "border-border hover:border-border/80"
                )}
              >
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-bold text-sm text-foreground">{plan.name}</span>
                    <span className="px-2 py-0.5 text-2xs font-semibold rounded-md uppercase border border-border bg-background">
                      {plan.currency}
                    </span>
                  </div>

                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-extrabold tracking-tight">
                      {formatCurrencyPrice(plan.price_amount, plan.currency as "INR" | "USD")}
                    </span>
                    <span className="text-xs text-muted-foreground">/{plan.billing_interval}</span>
                  </div>

                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {plan.description}
                  </p>

                  <div className="pt-2 border-t border-border/50 space-y-2 text-xs">
                    <div className="flex items-center gap-1.5 text-foreground font-medium">
                      <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                      Markets: {plan.entitled_markets.join(", ")}
                    </div>
                    <div className="flex items-center gap-1.5 text-muted-foreground">
                      <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                      Grace Period: {plan.grace_period_days} days
                    </div>
                    <div className="flex items-center gap-1.5 text-muted-foreground">
                      <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                      Gateway: {isINR ? "Razorpay" : "Stripe"}
                    </div>
                  </div>
                </div>

                <div className="pt-5">
                  {isCurrent ? (
                    <button
                      disabled
                      className="w-full py-2 rounded-lg bg-primary/20 text-primary border border-primary/40 text-xs font-semibold cursor-default flex items-center justify-center gap-1.5"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Active Plan
                    </button>
                  ) : (
                    <button
                      onClick={() => handleStartCheckout(plan)}
                      disabled={checkoutLoadingPlanId === plan.id}
                      className="w-full py-2 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-sm"
                    >
                      {checkoutLoadingPlanId === plan.id ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          Creating Session...
                        </>
                      ) : (
                        <>
                          <Zap className="w-3.5 h-3.5" />
                          Subscribe via {isINR ? "Razorpay" : "Stripe"}
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Payment & Invoices History Table */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold flex items-center gap-2">
              <FileText className="w-4 h-4 text-primary" />
              Invoice &amp; Payment History
            </h2>
            <p className="text-xs text-muted-foreground">
              All transactions recorded with cryptographic server webhook verification.
            </p>
          </div>
          <span className="text-xs text-muted-foreground font-mono">
            {payments.length} record{payments.length === 1 ? "" : "s"}
          </span>
        </div>

        {payments.length === 0 ? (
          <div className="text-center py-8 text-xs text-muted-foreground space-y-1">
            <FileText className="w-8 h-8 text-muted mx-auto mb-2 opacity-50" />
            <p>No payment records found yet.</p>
            <p className="text-2xs">Invoices and webhook receipts will appear here once charged.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-border/60 text-muted-foreground uppercase text-2xs font-semibold tracking-wider">
                  <th className="py-2.5 px-3">Date</th>
                  <th className="py-2.5 px-3">Invoice #</th>
                  <th className="py-2.5 px-3">Plan</th>
                  <th className="py-2.5 px-3">Gateway</th>
                  <th className="py-2.5 px-3">Amount</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Receipt</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 font-mono">
                {payments.map((p) => {
                  const isSucceeded = p.status === "succeeded";
                  return (
                    <tr key={p.id} className="hover:bg-accent/40 transition-colors">
                      <td className="py-2.5 px-3 text-muted-foreground font-sans">
                        {formatUtcTimestamp(p.paid_at || p.created_at)}
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-foreground">
                        {p.invoice_number}
                      </td>
                      <td className="py-2.5 px-3 font-sans text-foreground">
                        {p.plan_name || "Platform Subscription"}
                      </td>
                      <td className="py-2.5 px-3 uppercase text-2xs text-muted-foreground">
                        {p.provider}
                      </td>
                      <td className="py-2.5 px-3 font-bold text-foreground">
                        {formatCurrencyPrice(p.amount, p.currency as "INR" | "USD")}
                      </td>
                      <td className="py-2.5 px-3 font-sans">
                        <span
                          className={cn(
                            "px-2 py-0.5 rounded-full text-2xs font-semibold uppercase border",
                            isSucceeded
                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                              : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                          )}
                        >
                          {p.status}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-sans">
                        {p.receipt_url ? (
                          <a
                            href={p.receipt_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-primary hover:underline text-2xs font-medium"
                          >
                            View
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        ) : (
                          <span className="text-muted-foreground text-2xs">Generated</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Checkout Session Modal */}
      {checkoutResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
          <div className="rounded-xl border border-border bg-card p-6 max-w-lg w-full space-y-5 shadow-2xl animate-in fade-in zoom-in-95">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-bold flex items-center gap-2">
                  <CreditCard className="w-5 h-5 text-primary" />
                  Checkout Session Ready ({checkoutResult.provider.toUpperCase()})
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Plan: <strong>{checkoutResult.plan_name}</strong> • Amount:{" "}
                  <strong>
                    {formatCurrencyPrice(
                      checkoutResult.amount,
                      checkoutResult.currency as "INR" | "USD"
                    )}
                  </strong>
                </p>
              </div>
              <button
                onClick={() => setCheckoutResult(null)}
                className="text-muted-foreground hover:text-foreground p-1 rounded-md"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs bg-background/60 p-4 rounded-lg border border-border/80 font-mono">
              <div className="flex justify-between">
                <span className="text-muted-foreground font-sans">Gateway Provider:</span>
                <span className="uppercase font-bold text-foreground">
                  {checkoutResult.provider}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground font-sans">Session / Order ID:</span>
                <span className="text-foreground">
                  {checkoutResult.provider_session_id || checkoutResult.provider_order_id}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground font-sans">Public Key:</span>
                <span className="text-muted-foreground">{checkoutResult.public_key}</span>
              </div>
            </div>

            <div className="p-3.5 rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-300 text-xs flex items-start gap-2.5">
              <ShieldCheck className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
              <div>
                <strong>Security Guard:</strong> Client return callbacks never directly alter subscription status. Your account is automatically activated when the backend verifies the signed webhook from {checkoutResult.provider.toUpperCase()}.
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setCheckoutResult(null)}
                className="px-4 py-2 rounded-lg border border-border bg-card hover:bg-accent text-xs font-medium"
              >
                Close
              </button>
              {checkoutResult.checkout_url && (
                <a
                  href={checkoutResult.checkout_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-semibold flex items-center gap-1.5"
                >
                  Proceed to Payment Gateway
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Cancellation Confirmation Dialog */}
      {showCancelConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
          <div className="rounded-xl border border-border bg-card p-6 max-w-md w-full space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-rose-400 flex items-center gap-2">
              <AlertCircle className="w-5 h-5" />
              Confirm Subscription Cancellation
            </h3>
            <p className="text-xs text-muted-foreground">
              Are you sure you want to cancel your subscription? Your intelligence signals access will remain active until{" "}
              <strong>
                {subscription?.current_period_end
                  ? formatUtcTimestamp(subscription.current_period_end)
                  : "the end of your current billing period"}
              </strong>
              .
            </p>
            <div className="space-y-1">
              <label className="text-2xs font-semibold uppercase text-muted-foreground">
                Optional Reason
              </label>
              <textarea
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="Let us know why you're leaving..."
                rows={2}
                className="w-full text-xs p-2.5 rounded-lg border border-border bg-background text-foreground"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowCancelConfirm(false)}
                disabled={cancelling}
                className="px-3.5 py-1.5 rounded-lg border border-border bg-card hover:bg-accent text-xs font-medium"
              >
                Keep Subscription
              </button>
              <button
                onClick={handleConfirmCancel}
                disabled={cancelling}
                className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold flex items-center gap-1.5"
              >
                {cancelling ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Cancelling...
                  </>
                ) : (
                  "Confirm Cancellation"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
