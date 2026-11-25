"use client";

import React, { useEffect, useRef, memo } from "react";

interface TradingViewWidgetProps {
  symbol: string;
  theme?: "dark" | "light";
  height?: number | string;
  interval?: string;
  timezone?: string;
}

export const TradingViewWidget = memo(function TradingViewWidget({
  symbol = "NSE:RELIANCE",
  theme = "dark",
  height = 580,
  interval = "5",
  timezone,
}: TradingViewWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Normalize symbol for TradingView:
  // e.g. "RELIANCE" -> "NSE:RELIANCE", "NSE:TCS" -> "NSE:TCS", "AMD" -> "NASDAQ:AMD"
  const formattedSymbol = React.useMemo(() => {
    if (!symbol) return "NSE:RELIANCE";
    const s = symbol.trim().toUpperCase();
    if (s.includes(":")) return s;

    // Common Indian tickers
    const indianTickers = [
      "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
      "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT",
      "TATAMOTORS", "MARUTI", "AXISBANK", "WIPRO", "BAJFINANCE",
      "HINDUNILVR", "ASIANPAINT", "SUNPHARMA", "TITAN", "ULTRACEMCO",
      "NIFTYBEES", "BANKBEES", "GOLDBEES", "M&M"
    ];
    if (indianTickers.includes(s)) {
      return `NSE:${s}`;
    }

    // Common US tickers
    const nasdaqTickers = [
      "NVDA", "AAPL", "MSFT", "TSLA", "GOOG", "GOOGL",
      "AMZN", "META", "AMD", "INTC", "NFLX", "QCOM",
      "AVGO", "COST", "CSCO", "ADBE"
    ];
    if (nasdaqTickers.includes(s)) {
      return `NASDAQ:${s}`;
    }

    const nyseTickers = [
      "BRK.A", "BRK.B", "UNH", "JNJ", "JPM", "V", "PG", "MA", "DIS", "XOM"
    ];
    if (nyseTickers.includes(s)) {
      return `NYSE:${s}`;
    }

    // Default to NSE for Indian-focused workspace
    return `NSE:${s}`;
  }, [symbol]);

  const heightValue = typeof height === "number" ? `${height}px` : height;

  const resolvedTimezone = React.useMemo(() => {
    if (timezone) return timezone;
    return formattedSymbol.startsWith("NSE:") || formattedSymbol.startsWith("BSE:")
      ? "Asia/Kolkata"
      : "America/New_York";
  }, [timezone, formattedSymbol]);

  const resolvedInterval = React.useMemo(() => {
    if (interval === "1d" || interval === "D" || interval === "1D") return "D";
    if (interval === "1w" || interval === "W") return "W";
    if (interval === "15m" || interval === "15") return "15";
    if (interval === "1m" || interval === "1") return "1";
    return interval || "5";
  }, [interval]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Reset container contents
    container.innerHTML = "";

    const widgetDiv = document.createElement("div");
    widgetDiv.className = "tradingview-widget-container__widget";
    widgetDiv.style.height = "100%";
    widgetDiv.style.width = "100%";
    container.appendChild(widgetDiv);

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: formattedSymbol,
      interval: resolvedInterval,
      timezone: resolvedTimezone,
      theme: theme,
      style: "1",
      locale: "en",
      enable_publishing: false,
      hide_top_toolbar: false,
      allow_symbol_change: true,
      save_image: true,
      calendar: false,
      studies: ["STD;RSI", "STD;SMA"],
      support_host: "https://www.tradingview.com",
    });

    container.appendChild(script);

    return () => {
      if (container) {
        container.innerHTML = "";
      }
    };
  }, [formattedSymbol, resolvedInterval, theme, resolvedTimezone]);

  return (
    <div
      className="w-full rounded-xl overflow-hidden border border-border bg-[#131722] shadow-2xl relative"
      style={{
        height: heightValue,
        minHeight: heightValue,
        width: "100%",
      }}
    >
      <div
        ref={containerRef}
        key={`${formattedSymbol}-${resolvedInterval}-${theme}`}
        className="tradingview-widget-container"
        style={{ height: "100%", width: "100%" }}
      />
    </div>
  );
});
