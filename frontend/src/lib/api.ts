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

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
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

export function registerAccount(payload: {
  email: string;
  password: string;
  full_name: string;
  country_code: string;
}): Promise<UserProfile> {
  return apiFetch<UserProfile>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function loginAccount(payload: {
  email: string;
  password: string;
}): Promise<UserProfile> {
  return apiFetch<UserProfile>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logoutAccount(): Promise<void> {
  return apiFetch<void>("/api/v1/auth/logout", { method: "POST" });
}

export function fetchCurrentUser(): Promise<UserProfile> {
  return apiFetch<UserProfile>("/api/v1/auth/me");
}

export function requestPasswordReset(email: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>("/api/v1/auth/password-reset/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}
