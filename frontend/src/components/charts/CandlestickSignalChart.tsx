"use client";

import React, { useEffect, useRef } from "react";
import { createChart, ColorType, LineStyle, type UTCTimestamp } from "lightweight-charts";
import type { OHLCVBarItem } from "@/lib/api";

interface CandlestickSignalChartProps {
  bars: OHLCVBarItem[];
  entryPrice?: number;
  stopLoss?: number;
  targetPrice?: number;
  currency: "INR" | "USD";
  height?: number;
}

export function CandlestickSignalChart({
  bars,
  entryPrice,
  stopLoss,
  targetPrice,
  currency,
  height = 460,
}: CandlestickSignalChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || bars.length === 0) return;

    // Clean previous chart instance if any
    container.innerHTML = "";

    const isDark = document.documentElement.classList.contains("dark");
    const chart = createChart(container, {
      height,
      width: container.clientWidth || 640,
      layout: {
        background: { type: ColorType.Solid, color: "#131722" },
        textColor: isDark ? "#94A3B8" : "#475569",
      },
      grid: {
        vertLines: { color: isDark ? "rgba(148,163,184,0.08)" : "rgba(15,23,42,0.08)" },
        horzLines: { color: isDark ? "rgba(148,163,184,0.08)" : "rgba(15,23,42,0.08)" },
      },
      rightPriceScale: {
        borderColor: isDark ? "rgba(148,163,184,0.18)" : "rgba(15,23,42,0.18)",
        autoScale: true,
        scaleMargins: {
          top: 0.08,
          bottom: 0.08,
        },
      },
      timeScale: {
        borderColor: isDark ? "rgba(148,163,184,0.18)" : "rgba(15,23,42,0.18)",
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#10B981",
      downColor: "#EF4444",
      borderUpColor: "#10B981",
      borderDownColor: "#EF4444",
      wickUpColor: "#10B981",
      wickDownColor: "#EF4444",
    });

    // Deduplicate and sort strictly ascending by UTC epoch seconds as required by Lightweight Charts
    const seen = new Set<number>();
    const seriesData = bars
      .map((bar) => ({
        time: Math.floor(new Date(bar.bar_start_utc).getTime() / 1000) as UTCTimestamp,
        open: Number(bar.open),
        high: Number(bar.high),
        low: Number(bar.low),
        close: Number(bar.close),
      }))
      .filter((pt) => {
        if (!Number.isFinite(pt.time) || seen.has(pt.time)) return false;
        seen.add(pt.time);
        return true;
      })
      .sort((a, b) => a.time - b.time);

    candleSeries.setData(seriesData);

    const sym = currency === "INR" ? "₹" : "$";

    // Create Entry Price Line
    if (entryPrice && Number.isFinite(entryPrice)) {
      candleSeries.createPriceLine({
        price: entryPrice,
        color: "#38BDF8",
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: true,
        title: `ENTRY ${sym}${entryPrice.toFixed(2)}`,
      });
    }

    // Create Target Price Line
    if (targetPrice && Number.isFinite(targetPrice)) {
      candleSeries.createPriceLine({
        price: targetPrice,
        color: "#10B981",
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: `TARGET ${sym}${targetPrice.toFixed(2)}`,
      });
    }

    // Create Stop Loss Line
    if (stopLoss && Number.isFinite(stopLoss)) {
      candleSeries.createPriceLine({
        price: stopLoss,
        color: "#EF4444",
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: `STOP ${sym}${stopLoss.toFixed(2)}`,
      });
    }

    // Guarantee that Entry, Stop-Loss, and Target lines are all strictly within
    // the vertical viewport by expanding price scale bounds via an invisible anchor series
    if (seriesData.length >= 2) {
      let minPrice = Math.min(...seriesData.map((d) => d.low));
      let maxPrice = Math.max(...seriesData.map((d) => d.high));

      if (entryPrice && Number.isFinite(entryPrice)) {
        minPrice = Math.min(minPrice, entryPrice);
        maxPrice = Math.max(maxPrice, entryPrice);
      }
      if (stopLoss && Number.isFinite(stopLoss)) {
        minPrice = Math.min(minPrice, stopLoss);
        maxPrice = Math.max(maxPrice, stopLoss);
      }
      if (targetPrice && Number.isFinite(targetPrice)) {
        minPrice = Math.min(minPrice, targetPrice);
        maxPrice = Math.max(maxPrice, targetPrice);
      }

      const padding = (maxPrice - minPrice) * 0.05 || 1;
      minPrice -= padding;
      maxPrice += padding;

      const boundsSeries = chart.addLineSeries({
        color: "transparent",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });

      boundsSeries.setData([
        { time: seriesData[0].time, value: minPrice },
        { time: seriesData[seriesData.length - 1].time, value: maxPrice },
      ]);
    }

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry && entry.contentRect.width > 0) {
        chart.applyOptions({ width: Math.floor(entry.contentRect.width) });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [bars, entryPrice, stopLoss, targetPrice, currency, height]);

  if (bars.length === 0) {
    return (
      <div
        style={{ height }}
        className="rounded-xl border border-dashed border-border bg-[#131722] flex items-center justify-center text-xs text-muted-foreground"
      >
        Completed OHLCV bars unavailable for this timeframe.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="w-full rounded-xl overflow-hidden border border-border bg-[#131722]"
      style={{ height, minHeight: height }}
    />
  );
}
