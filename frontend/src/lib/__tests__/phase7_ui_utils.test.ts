import { describe, expect, it } from "vitest";
import { readCookieFromString } from "../api";
import { formatCurrencyPrice, formatMarketClock } from "../utils";

describe("Phase 7 Frontend UI & Security Utilities", () => {
  it("formats INR and USD prices with proper currency symbols and 2 decimals", () => {
    expect(formatCurrencyPrice("2945.5", "INR")).toContain("₹");
    expect(formatCurrencyPrice("2945.5", "INR")).toContain("2,945.50");
    expect(formatCurrencyPrice("364.18", "USD")).toBe("$364.18");
  });

  it("reads tip_csrf cookie cleanly for double-submit CSRF header attachment", () => {
    const cookieHeader = "theme=dark; tip_csrf=abc123_token%2Bval; other=1";
    expect(readCookieFromString(cookieHeader, "tip_csrf")).toBe("abc123_token+val");
    expect(readCookieFromString(cookieHeader, "missing_cookie")).toBeNull();
  });

  it("formats IST and US Eastern 24-hour market clocks deterministically", () => {
    const fixedUtc = new Date("2026-11-18T14:30:00Z"); // 20:00 IST, 09:30 EST
    expect(formatMarketClock("Asia/Kolkata", fixedUtc)).toBe("20:00:00");
    expect(formatMarketClock("America/New_York", fixedUtc)).toBe("09:30:00");
  });
});
