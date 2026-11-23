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
  height = 540,
  interval = "5",
  timezone = "Asia/Kolkata",
}: TradingViewWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Normalize symbol for TradingView:
  // e.g. "RELIANCE" -> "NSE:RELIANCE", "NSE:TCS" -> "NSE:TCS", "TSLA" -> "NASDAQ:TSLA"
  const formattedSymbol = React.useMemo(() => {
    const s = symbol.trim().toUpperCase();
    if (s.includes(":")) return s;
    if (["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "TATAMOTORS", "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK"].includes(s)) {
      return `NSE:${s}`;
    }
    if (["NVDA", "AAPL", "MSFT", "TSLA", "GOOG", "AMZN", "META", "AMD", "INTC"].includes(s)) {
      return `NASDAQ:${s}`;
    }
    return `NSE:${s}`;
  }, [symbol]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Clear previous widget
    container.innerHTML = "";

    const widgetHolder = document.createElement("div");
    widgetHolder.className = "tradingview-widget-container__widget";
    widgetHolder.style.height = typeof height === "number" ? `${height}px` : height;
    widgetHolder.style.width = "100%";
    container.appendChild(widgetHolder);

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: formattedSymbol,
      interval: interval,
      timezone: timezone,
      theme: theme,
      style: "1",
      locale: "en",
      enable_publishing: false,
      allow_symbol_change: true,
      calendar: false,
      support_host: "https://www.tradingview.com",
      hide_side_toolbar: false,
      withdateranges: true,
      hide_volume: false,
      studies: [
        "RSI@tv-basicstudies",
        "MASimple@tv-basicstudies"
      ],
    });

    container.appendChild(script);

    return () => {
      if (container) {
        container.innerHTML = "";
      }
    };
  }, [formattedSymbol, theme, height, interval, timezone]);

  return (
    <div
      className="tradingview-widget-container rounded-xl overflow-hidden border border-border"
      ref={containerRef}
      style={{ height, width: "100%" }}
    />
  );
});
