/**
 * Cookie-authenticated API client with automatic double-submit CSRF header support.
 * Zero session tokens are ever stored in localStorage or sessionStorage.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: Record<string, unknown>;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = payload.code;
    this.details = payload.details;
  }
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: "super_admin" | "admin" | "subscriber";
  country_code: string;
  is_active: boolean;
  is_email_verified: boolean;
  subscription_status: "none" | "trialing" | "active" | "past_due" | "cancelled" | "expired";
  entitled_markets: Array<"IN" | "US">;
  last_login_at?: string | null;
}

export interface DataFreshness {
  provider: string;
  status: "HEALTHY" | "DEGRADED" | "DOWN";
  last_quote_utc: string | null;
  delay_seconds: number;
  is_stale: boolean;
  stale_reason?: string | null;
}

export interface MarketStatusItem {
  market_code: "IN" | "US";
  exchange_code: "NSE" | "BSE" | "NASDAQ" | "NYSE";
  is_open: boolean;
  session_phase: "PRE_OPEN" | "REGULAR" | "EARLY_CLOSE" | "CLOSED" | "HOLIDAY";
  timezone: string;
  local_time: string;
  next_open_utc: string | null;
  session_reason: string;
  session_5m_bars: number;
  data_freshness: DataFreshness;
}

export interface IndexSnapshot {
  instrument_id: string;
  market_code: "IN" | "US";
  exchange_code: string;
  symbol: string;
  canonical_code: string;
  company_name: string;
  currency: "INR" | "USD";
  last_price: string;
  prev_close: string;
  change: string;
  change_pct: string;
  quote_timestamp_utc: string;
  source_provider: string;
  is_delayed: boolean;
  delay_seconds: number;
  is_stale: boolean;
}

export interface InstrumentSummary {
  instrument_id: string;
  market_code: "IN" | "US";
  exchange_code: "NSE" | "BSE" | "NASDAQ" | "NYSE";
  symbol: string;
  canonical_code: string;
  company_name: string;
  asset_type: string;
  currency: "INR" | "USD";
  tick_size: string;
  lot_size: number;
  sector?: string | null;
}

export interface OHLCVBarItem {
  bar_start_utc: string;
  bar_end_utc: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: number;
  is_complete: boolean;
}

export interface InstrumentBarsResponse {
  instrument: InstrumentSummary;
  timeframe: "1m" | "5m" | "15m" | "1d";
  source_provider: string;
  bar_count: number;
  data_freshness: DataFreshness;
  bars: OHLCVBarItem[];
}

export interface ScannerHit {
  instrument_id: string;
  market_code: "IN" | "US";
  exchange_code: string;
  symbol: string;
  canonical_code: string;
  company_name: string;
  currency: "INR" | "USD";
  mode: string;
  setup_type: string;
  signal_bias: "BUY" | "SELL" | "WATCH";
  level_price: string;
  last_price: string;
  atr_14: string;
  sma_20: string;
  rsi_14: string;
  volume_ratio: string;
  quote_timestamp_utc: string;
  source_provider: string;
}

export interface TradingSignalItem {
  id: string;
  workflow_run_id: string;
  instrument_id: string;
  market_code: "IN" | "US";
  exchange_code: string;
  symbol: string;
  canonical_code: string;
  company_name: string;
  currency: "INR" | "USD";
  strategy: string;
  signal_type: "BUY" | "SELL" | "WATCH";
  entry_price: string;
  stop_loss: string;
  target_price: string;
  risk_reward_ratio: string;
  confidence_score: number;
  confidence_label: string;
  confidence_breakdown: {
    label: string;
    total_score: number;
    components: Record<string, { score: number; max: number }>;
  };
  technical_indicators: Record<string, string>;
  news_context: { count: number; headlines: string[] };
  timemachine_summary?: Record<string, unknown> | null;
  broker_ticket_preview?: Record<string, unknown> | null;
  ai_reasoning?: string | null;
  ai_explanation?: {
    thesis: string;
    key_levels_summary: string;
    risk_factors: string[];
    catalyst_notes: string;
    disclaimer: string;
  } | null;
  risk_validation_status: "PASSED" | "REJECTED";
  current_status: string;
  data_source_provider: string;
  data_as_of_utc: string;
  generated_at_utc: string;
  expires_at_utc: string;
}

export interface PaginatedResponse<T> {
  page: number;
  page_size: number;
  total: number;
  items: T[];
}

export interface MarketNewsItem {
  instrument_id: string;
  market_code: "IN" | "US";
  symbol: string;
  canonical_code: string;
  source: string;
  headline: string;
  summary: string;
  url: string;
  tags: string[];
  is_regulatory_filing: boolean;
  filing_type: string | null;
  published_at_utc: string;
}

export interface CongressDisclosureItem {
  doc_id: string;
  member_name: string;
  district: string | null;
  owner_type: string;
  raw_ticker: string;
  asset_description: string;
  transaction_type: string;
  amount_range: string;
  trade_date: string;
  filing_date: string;
  disclosure_delay_days: number;
  is_late_filing: boolean;
  lag_notice: string;
  source_pdf_url: string;
}

export interface WatchlistItem {
  id: string;
  watchlist_id: string;
  instrument_id: string;
  notes: string | null;
  created_at: string;
}

export interface Watchlist {
  id: string;
  name: string;
  market_scope: "ALL" | "IN" | "US";
  is_default: boolean;
  created_at: string;
  updated_at: string;
  items: WatchlistItem[];
}

export interface NotificationItem {
  id: string;
  category: string;
  title: string;
  body: string;
  payload: Record<string, unknown>;
  is_read: boolean;
  read_at_utc: string | null;
  created_at_utc: string;
}

export interface NotificationPreferences {
  in_app_enabled: boolean;
  browser_push_enabled: boolean;
  email_enabled: boolean;
  notify_new_signals: boolean;
  notify_entry_hit: boolean;
  notify_target_hit: boolean;
  notify_stop_hit: boolean;
  notify_signal_expiry: boolean;
  notify_market_news: boolean;
  notify_market_reports: boolean;
  market_filter: "ALL" | "IN" | "US";
  quiet_hours_json: Record<string, unknown>;
  updated_at: string;
}

export interface UserPreferences {
  default_market: "ALL" | "IN" | "US";
  theme: "dark" | "light";
  display_timezone: string;
  default_budget_inr: string;
  default_max_loss_inr: string;
  default_budget_usd: string;
  default_max_loss_usd: string;
  updated_at: string;
}

export interface PerformanceSummary {
  total_outcomes: number;
  closed_trades: number;
  target_hits: number;
  stop_loss_hits: number;
  expired_untriggered: number;
  win_rate_pct: number;
  avg_net_return_pct: number;
  avg_realized_r_multiple: number;
  methodology_version: string;
  methodology_disclosure: string;
}

export function readCookieFromString(cookieStr: string, name: string): string | null {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = cookieStr.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  return readCookieFromString(document.cookie, name);
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfToken = readCookie("tip_csrf");
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const data = await response.json().catch(() => ({
    code: "HTTP_ERROR",
    message: `Request failed with status ${response.status}`,
  }));

  if (!response.ok) {
    const err = new ApiRequestError(response.status, data as ApiErrorPayload);
    if (
      typeof window !== "undefined" &&
      err.status === 401 &&
      (err.code === "SESSION_SUPERSEDED" || err.code === "SESSION_REVOKED") &&
      !window.location.pathname.startsWith("/login")
    ) {
      const reason =
        err.code === "SESSION_SUPERSEDED" ? "session_superseded" : "session_revoked";
      window.location.assign(`/login?reason=${reason}`);
    }
    throw err;
  }

  return data as T;
}

// --- Auth ---
export const registerAccount = (payload: {
  email: string;
  password: string;
  full_name: string;
  country_code: string;
}) =>
  apiFetch<UserProfile>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const loginAccount = (payload: { email: string; password: string }) =>
  apiFetch<UserProfile>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const logoutAccount = () => apiFetch<void>("/api/v1/auth/logout", { method: "POST" });
export const fetchCurrentUser = () => apiFetch<UserProfile>("/api/v1/auth/me");
export const requestPasswordReset = (email: string) =>
  apiFetch<{ message: string }>("/api/v1/auth/password-reset/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });

// --- Markets & Instruments ---
export const fetchMarketsStatus = () => apiFetch<MarketStatusItem[]>("/api/v1/markets/status");
export const fetchMarketIndices = (market: "IN" | "US") =>
  apiFetch<IndexSnapshot[]>(`/api/v1/markets/${market}/indices`);
export const searchInstruments = (q: string, market: "ALL" | "IN" | "US" = "ALL") =>
  apiFetch<InstrumentSummary[]>(
    `/api/v1/instruments/search?q=${encodeURIComponent(q)}&market=${market}`
  );
export const fetchInstrumentBars = (
  instrumentId: string,
  timeframe: "1m" | "5m" | "15m" | "1d" = "5m",
  limit = 150
) =>
  apiFetch<InstrumentBarsResponse>(
    `/api/v1/instruments/${encodeURIComponent(instrumentId)}/bars?timeframe=${timeframe}&limit=${limit}`
  );

// --- Scanner, Signals, News, Disclosures, Sizing, AI ---
export const fetchScannerResults = (params: {
  market?: "ALL" | "IN" | "US";
  mode?: "daily" | "orb" | "all";
  setup?: string;
  page?: number;
  page_size?: number;
}) => {
  const sp = new URLSearchParams();
  if (params.market) sp.set("market", params.market);
  if (params.mode) sp.set("mode", params.mode);
  if (params.setup) sp.set("setup", params.setup);
  if (params.page) sp.set("page", String(params.page));
  if (params.page_size) sp.set("page_size", String(params.page_size));
  return apiFetch<PaginatedResponse<ScannerHit>>(`/api/v1/scanner/results?${sp.toString()}`);
};

export const fetchSignals = (params: {
  market?: "ALL" | "IN" | "US";
  signal_type?: string;
  status?: string;
  strategy?: string;
  search?: string;
  page?: number;
  page_size?: number;
}) => {
  const sp = new URLSearchParams();
  if (params.market) sp.set("market", params.market);
  if (params.signal_type) sp.set("signal_type", params.signal_type);
  if (params.status) sp.set("status", params.status);
  if (params.strategy) sp.set("strategy", params.strategy);
  if (params.search) sp.set("search", params.search);
  if (params.page) sp.set("page", String(params.page));
  if (params.page_size) sp.set("page_size", String(params.page_size));
  return apiFetch<PaginatedResponse<TradingSignalItem>>(`/api/v1/signals?${sp.toString()}`);
};

export const fetchPerformanceSummary = (market: "ALL" | "IN" | "US" = "ALL") =>
  apiFetch<PerformanceSummary>(`/api/v1/signals/performance/summary?market=${market}`);

export const fetchMarketNews = (market: "ALL" | "IN" | "US" = "ALL", symbol?: string) => {
  const sp = new URLSearchParams({ market });
  if (symbol) sp.set("symbol", symbol);
  return apiFetch<{ total: number; items: MarketNewsItem[] }>(`/api/v1/news?${sp.toString()}`);
};

export const fetchCongressDisclosures = () =>
  apiFetch<{
    market_code: string;
    stock_act_notice: string;
    total: number;
    items: CongressDisclosureItem[];
  }>("/api/v1/disclosures/congress");

export const calculatePositionSize = (payload: {
  market_code: "IN" | "US";
  exchange_code: string;
  symbol: string;
  signal_type: "BUY" | "SELL";
  entry_price: string;
  stop_loss: string;
  target_price: string;
  capital_budget: string;
  max_loss_amount: string;
  lot_size?: number;
}) =>
  apiFetch<{
    mode: string;
    order_placed: boolean;
    sizing: Record<string, string | number>;
    risk_validation: {
      status: string;
      passed: boolean;
      blocking_reasons: string[];
      warnings: string[];
      risk_fingerprint: string;
    };
    disclaimer: string;
  }>("/api/v1/tools/position-size", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const queryAIAnalyst = (question: string, market_code: "ALL" | "IN" | "US" = "ALL") =>
  apiFetch<{
    provider: string;
    question: string;
    market_scope: string;
    referenced_signal_ids: string[];
    answer: string;
    disclaimer: string;
  }>("/api/v1/ai-analyst/query", {
    method: "POST",
    body: JSON.stringify({ question, market_code }),
  });

// --- Watchlists, Preferences & Notifications ---
export const fetchWatchlists = () => apiFetch<Watchlist[]>("/api/v1/watchlists");
export const createWatchlist = (name: string, market_scope: "ALL" | "IN" | "US") =>
  apiFetch<Watchlist>("/api/v1/watchlists", {
    method: "POST",
    body: JSON.stringify({ name, market_scope }),
  });
export const deleteWatchlist = (watchlistId: string) =>
  apiFetch<void>(`/api/v1/watchlists/${watchlistId}`, { method: "DELETE" });

export const fetchNotifications = () =>
  apiFetch<{ unread_count: number; total: number; items: NotificationItem[] }>(
    "/api/v1/notifications"
  );
export const markNotificationRead = (notificationId: string) =>
  apiFetch<NotificationItem>(`/api/v1/notifications/${notificationId}/read`, { method: "POST" });
export const markAllNotificationsRead = () =>
  apiFetch<{ marked_read: number }>("/api/v1/notifications/read-all", { method: "POST" });
export const fetchNotificationPreferences = () =>
  apiFetch<NotificationPreferences>("/api/v1/notifications/preferences");
export const updateNotificationPreferences = (patch: Partial<NotificationPreferences>) =>
  apiFetch<NotificationPreferences>("/api/v1/notifications/preferences", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const fetchUserPreferences = () =>
  apiFetch<UserPreferences>("/api/v1/users/me/preferences");
export const updateUserPreferences = (patch: Partial<UserPreferences>) =>
  apiFetch<UserPreferences>("/api/v1/users/me/preferences", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
export const updateUserProfile = (patch: { full_name?: string; country_code?: string }) =>
  apiFetch<UserProfile>("/api/v1/users/me/profile", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

// --- Phase 8: Trading Journal Types & APIs ---
export interface JournalEntry {
  id: string;
  user_id: string;
  instrument_id: string;
  market_id: string;
  signal_id: string | null;
  side: "BUY" | "SELL";
  entry_price: string;
  exit_price: string | null;
  quantity: string;
  planned_stop: string | null;
  planned_target: string | null;
  realized_pnl: string | null;
  currency: "INR" | "USD";
  emotions_tags: string[];
  notes: string | null;
  entered_at_utc: string;
  exited_at_utc: string | null;
  created_at: string;
  updated_at: string;
}

export interface JournalStats {
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  total_realized_pnl_inr: string;
  total_realized_pnl_usd: string;
  profit_factor: number | null;
  top_emotions: Record<string, number>;
}

export interface JournalListResponse {
  total: number;
  stats: JournalStats;
  items: JournalEntry[];
}

export const fetchJournal = (params?: {
  side?: string;
  currency?: string;
  limit?: number;
  offset?: number;
}) => {
  const sp = new URLSearchParams();
  if (params?.side) sp.set("side", params.side);
  if (params?.currency) sp.set("currency", params.currency);
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.offset) sp.set("offset", String(params.offset));
  const query = sp.toString() ? `?${sp.toString()}` : "";
  return apiFetch<JournalListResponse>(`/api/v1/journal${query}`);
};

export const createJournalEntry = (payload: {
  instrument_id: string;
  market_id: string;
  signal_id?: string | null;
  side: "BUY" | "SELL";
  entry_price: string;
  quantity: string;
  currency: "INR" | "USD";
  exit_price?: string | null;
  planned_stop?: string | null;
  planned_target?: string | null;
  emotions_tags?: string[];
  notes?: string | null;
}) =>
  apiFetch<JournalEntry>("/api/v1/journal", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const updateJournalEntry = (
  journalId: string,
  payload: {
    exit_price?: string | null;
    planned_stop?: string | null;
    planned_target?: string | null;
    emotions_tags?: string[];
    notes?: string | null;
    exited_at_utc?: string | null;
  }
) =>
  apiFetch<JournalEntry>(`/api/v1/journal/${journalId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const deleteJournalEntry = (journalId: string) =>
  apiFetch<void>(`/api/v1/journal/${journalId}`, { method: "DELETE" });

// --- Phase 8: Super Admin Types & APIs ---
export interface AdminOverview {
  total_users: number;
  active_users: number;
  inactive_users: number;
  subscriptions_by_status: Record<string, number>;
  mrr_inr: string;
  mrr_usd: string;
  active_sessions_count: number;
  kill_switch: { enabled: boolean; source: string };
  trading_mode: string;
}

export interface AdminUserItem {
  id: string;
  email: string;
  full_name: string;
  role: string;
  country_code: string;
  is_active: boolean;
  is_email_verified: boolean;
  created_at: string;
  last_login_at: string | null;
  active_session?: {
    id: string;
    ip_address: string | null;
    user_agent: string | null;
    created_at: string;
    last_seen_at: string;
  } | null;
  subscription?: {
    id: string;
    plan_code: string;
    plan_name: string;
    status: string;
    currency: string;
    current_period_end: string | null;
  } | null;
}

export interface AdminUserListResponse {
  total: number;
  items: AdminUserItem[];
}

export interface AdminPlanItem {
  id: string;
  code: string;
  name: string;
  description: string;
  currency: string;
  price_amount: string;
  billing_interval: string;
  grace_period_days: number;
  entitled_markets: string[];
  features: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
}

export interface AuditLogItem {
  id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export interface WorkflowRunItem {
  workflow_run_id: string;
  workflow_type: string;
  market_code: string;
  status: string;
  idempotency_key: string;
  triggered_by: string;
  started_at_utc: string;
  finished_at_utc: string;
  error_message: string | null;
  skill_runs: Array<{
    id: string;
    skill_name: string;
    status: string;
    retry_count: number;
    duration_ms: number;
    error_trace: string | null;
  }>;
}

export const fetchAdminOverview = () => apiFetch<AdminOverview>("/api/v1/admin/overview");

export const fetchAdminUsers = (params?: {
  search?: string;
  role?: string;
  is_active?: boolean;
  limit?: number;
  offset?: number;
}) => {
  const sp = new URLSearchParams();
  if (params?.search) sp.set("search", params.search);
  if (params?.role) sp.set("role", params.role);
  if (params?.is_active !== undefined) sp.set("is_active", String(params.is_active));
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.offset) sp.set("offset", String(params.offset));
  const query = sp.toString() ? `?${sp.toString()}` : "";
  return apiFetch<AdminUserListResponse>(`/api/v1/admin/users${query}`);
};

export const updateAdminUserStatus = (userId: string, is_active: boolean, reason?: string) =>
  apiFetch<{ user_id: string; is_active: boolean; revoked_sessions_count: number }>(
    `/api/v1/admin/users/${userId}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({ is_active, reason: reason ?? "Admin update" }),
    }
  );

export const revokeAdminUserSession = (userId: string, reason?: string) =>
  apiFetch<{ user_id: string; revoked_sessions_count: number; message: string }>(
    `/api/v1/admin/users/${userId}/revoke-session`,
    {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? "Session revoked by administrator" }),
    }
  );

export const createAdminPlan = (payload: {
  code: string;
  name: string;
  description?: string;
  currency: "INR" | "USD";
  price_amount: string;
  billing_interval?: "monthly" | "yearly";
  grace_period_days?: number;
  entitled_markets: Array<"IN" | "US">;
  features?: Record<string, unknown>;
}) =>
  apiFetch<AdminPlanItem>("/api/v1/admin/plans", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchAdminAuditLogs = (params?: {
  limit?: number;
  offset?: number;
  action?: string;
}) => {
  const sp = new URLSearchParams();
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.offset) sp.set("offset", String(params.offset));
  if (params?.action) sp.set("action", params.action);
  const query = sp.toString() ? `?${sp.toString()}` : "";
  return apiFetch<AuditLogItem[]>(`/api/v1/admin/audit-logs${query}`);
};

export const fetchAdminProviderStatus = () =>
  apiFetch<{
    configured_providers: Record<string, unknown>;
    telemetry: Array<{
      provider_code: string;
      market_code: string;
      status: string;
      last_success_at: string | null;
      last_error_at: string | null;
      last_error_message: string | null;
      avg_latency_ms: number | null;
      daily_api_calls: number;
      consecutive_failures: number;
    }>;
  }>("/api/v1/admin/providers/status");

export const toggleAdminKillSwitch = (enabled: boolean, reason: string) =>
  apiFetch<{ enabled: boolean; reason: string; message: string }>("/api/v1/admin/kill-switch", {
    method: "POST",
    body: JSON.stringify({ enabled, reason }),
  });

export const fetchAdminWorkflows = () =>
  apiFetch<{ total: number; workflows: WorkflowRunItem[] }>("/api/v1/admin/workflows");

export const triggerAdminWorkflow = (marketCode: "IN" | "US", mode: "daily" | "orb" = "orb") =>
  apiFetch<Record<string, unknown>>("/api/v1/admin/workflows/trigger", {
    method: "POST",
    body: JSON.stringify({ market_code: marketCode, mode }),
  });

// --- Phase 9: Payments & Subscriptions (Razorpay & Stripe) ---

export interface SubscriptionPlanItem {
  id: string;
  code: string;
  name: string;
  description: string;
  currency: string;
  price_amount: string | number;
  billing_interval: string;
  grace_period_days: number;
  entitled_markets: Array<"IN" | "US">;
  features: Record<string, unknown>;
  is_active: boolean;
}

export interface UserSubscriptionDetail {
  subscription_status: "none" | "trialing" | "active" | "past_due" | "cancelled" | "expired";
  entitled_markets: string[];
  is_entitled: boolean;
  plan: SubscriptionPlanItem | null;
  provider: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  grace_until: string | null;
  cancel_at_period_end: boolean;
}

export interface CheckoutSessionResult {
  checkout_url: string | null;
  provider: "razorpay" | "stripe";
  provider_session_id: string | null;
  provider_order_id: string | null;
  public_key: string;
  currency: string;
  amount: string | number;
  plan_id: string;
  plan_name: string;
  plan_code: string;
}

export interface PaymentHistoryItem {
  id: string;
  invoice_number: string;
  provider: string;
  provider_payment_id: string;
  amount: string | number;
  tax_amount: string | number;
  currency: string;
  status: "succeeded" | "failed" | "pending" | "refunded";
  failure_reason: string | null;
  receipt_url: string | null;
  paid_at: string | null;
  created_at: string;
  plan_name: string | null;
}

export interface PaymentHistoryResponse {
  items: PaymentHistoryItem[];
  total: number;
}

export const fetchSubscriptionPlans = () =>
  apiFetch<SubscriptionPlanItem[]>("/api/v1/subscriptions/plans");

export const fetchMySubscription = () =>
  apiFetch<UserSubscriptionDetail>("/api/v1/subscriptions/me");

export const createCheckoutSession = (payload: {
  plan_id: string;
  provider: "razorpay" | "stripe";
  return_url?: string;
}) =>
  apiFetch<CheckoutSessionResult>("/api/v1/subscriptions/checkout", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const cancelSubscription = (reason?: string) =>
  apiFetch<{
    status: string;
    cancel_at_period_end: boolean;
    cancelled_at: string | null;
    current_period_end: string | null;
    message: string;
  }>("/api/v1/subscriptions/cancel", {
    method: "POST",
    body: JSON.stringify({ reason }),
  });

export const fetchPaymentHistory = (limit = 50, offset = 0) =>
  apiFetch<PaymentHistoryResponse>(`/api/v1/payments/history?limit=${limit}&offset=${offset}`);

