"use client";

/**
 * useChart — lightweight-charts v5 lifecycle manager
 *
 * Responsibilities:
 *  1. Create the chart instance when the container element mounts
 *  2. Destroy it on unmount (prevents memory leaks during SPA navigation)
 *  3. Let lightweight-charts' built-in autoSize handle all resize events
 *     (uses ResizeObserver internally — no manual listener needed)
 *
 * Returns:
 *  containerRef — attach to the <div> that should host the chart
 *  chart        — the IChartApi instance (null while unmounted)
 *
 * Usage:
 *  const { containerRef, chart } = useChart(options);
 *  useEffect(() => {
 *    if (!chart) return;
 *    const series = chart.addSeries(candlestickSeries, { ... });
 *    series.setData(bars);
 *    return () => chart.removeSeries(series);
 *  }, [chart, bars]);
 */

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, type IChartApi, type DeepPartial, type ChartOptions } from "lightweight-charts";

export type UseChartOptions = DeepPartial<ChartOptions>;

export interface UseChartResult {
  containerRef: React.RefObject<HTMLDivElement | null>;
  chart: IChartApi | null;
}

export function useChart(options?: UseChartOptions): UseChartResult {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [chart, setChart] = useState<IChartApi | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const instance = createChart(container, {
      // autoSize: true lets lightweight-charts observe the container with
      // ResizeObserver and resize itself — no manual window listener needed.
      autoSize: true,

      // Dark theme defaults matching the app's color palette (converted to hex for lightweight-charts compatibility)
      layout: {
        background: {
          type: ColorType.Solid,
          color: "#10121c", // surface0 (oklch(0.11 0.01 240))
        },
        textColor: "#f4f3ee", // foreground (oklch(0.65 0.012 92))
        fontSize: 12,
        fontFamily:
          "'Inter', 'system-ui', '-apple-system', 'Segoe UI', sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.06)" },
        horzLines: { color: "rgba(255, 255, 255, 0.06)" },
      },
      crosshair: {
        vertLine: {
          color: "rgba(255, 255, 255, 0.3)",
          labelBackgroundColor: "#1c1f2e", // surface2 (oklch(0.20 0.02 240))
        },
        horzLine: {
          color: "rgba(255, 255, 255, 0.3)",
          labelBackgroundColor: "#1c1f2e", // surface2
        },
      },
      timeScale: {
        borderColor: "rgba(255, 255, 255, 0.1)",
        timeVisible: false,
      },
      rightPriceScale: {
        borderColor: "rgba(255, 255, 255, 0.1)",
      },
      // Allow caller to override any defaults
      ...options,
    });

    setChart(instance);

    return () => {
      instance.remove();
      setChart(null);
    };
    // options is intentionally not in the dep-array: chart options are set
    // once at creation. Callers should use chart.applyOptions() for live
    // updates rather than remounting the chart on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { containerRef, chart };
}
