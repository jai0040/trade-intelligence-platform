"use client";

import React, { memo } from "react";

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
  timezone = "Asia/Kolkata",
}: TradingViewWidgetProps) {
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

  const iframeSrc = React.useMemo(() => {
    const params = new URLSearchParams({
      frameElementId: "tradingview_advanced_chart",
      symbol: formattedSymbol,
      interval: interval,
      hidesidetoolbar: "0",
      symboledit: "1",
      saveimage: "1",
      toolbarbg: theme === "dark" ? "131722" : "f1f3f6",
      theme: theme,
      style: "1",
      timezone: timezone,
      withdateranges: "1",
      hideideas: "1",
      studies: JSON.stringify([
        "RSI@tv-basicstudies",
        "MASimple@tv-basicstudies"
      ]),
      locale: "en",
      utm_source: "tradeintel.platform",
    });
    return `https://s.tradingview.com/widgetembed/?${params.toString()}`;
  }, [formattedSymbol, interval, theme, timezone]);

  return (
    <div
      className="w-full rounded-xl overflow-hidden border border-border bg-[#131722] shadow-2xl relative"
      style={{
        height: heightValue,
        minHeight: heightValue,
        width: "100%",
      }}
    >
      <iframe
        key={`${formattedSymbol}-${interval}-${theme}`}
        title={`TradingView Advanced Chart - ${formattedSymbol}`}
        src={iframeSrc}
        className="w-full h-full block border-0"
        style={{
          width: "100%",
          height: heightValue,
          minHeight: heightValue,
          border: "none",
        }}
        allowFullScreen
      />
    </div>
  );
});
