"use client";

/**
 * InstrumentChart — lightweight-charts v5 price chart component
 *
 * Renders:
 *  • Candlestick series (price bars)
 *  • SMA 50 / 150 / 200 line overlays (pre-computed by the API)
 *  • RS line on a secondary right-axis scale (when data.rs_line is non-empty)
 *  • Pattern markers via createSeriesMarkers
 *  • Interval buttons (1D / 1W / 1M) and range buttons (6M / 1Y / 2Y)
 *  • Loading skeleton while isFetching
 */

import { useEffect } from "react";
import {
  CandlestickSeries,
  LineSeries,
  createSeriesMarkers,
  type Time,
  type SeriesMarker,
} from "lightweight-charts";
import type { InstrumentChart as InstrumentChartData } from "@/lib/api";
import { useChart } from "@/hooks/use-chart";
import { cn } from "@/lib/utils";

// ── Visual constants ──────────────────────────────────────────────────────────
// Converted from OKLCH to hex for lightweight-charts compatibility

const CANDLE_UP   = "#51c96a"; // green (oklch(0.72 0.14 150))
const CANDLE_DOWN = "#e8503e"; // red (oklch(0.60 0.18 15))

const MA_COLORS = {
  sma50:  "#3b82f6",  // blue (oklch(0.68 0.16 240))
  sma150: "#f59e0b", // orange (oklch(0.75 0.13 60))
  sma200: "#ef4444", // red (oklch(0.62 0.18 15))
} as const;

const RS_COLOR = "#d8b4fe"; // soft lavender (oklch(0.80 0.06 290))

/** Map pattern_type to a marker colour */
const PATTERN_COLOR: Record<string, string> = {
  cup_with_handle:   "#fbbf24", // amber/gold (oklch(0.88 0.12 85))
  flat_base:         "#3b82f6", // blue (oklch(0.68 0.16 240))
  double_bottom:     "#51c96a", // green (oklch(0.72 0.14 150))
  ascending_base:    "#51c96a", // green
  high_tight_flag:   "#06b6d4", // cyan (oklch(0.88 0.10 195))
};
const PATTERN_COLOR_DEFAULT = "#ea580c"; // bronze (oklch(0.78 0.09 55))

// ── Types ─────────────────────────────────────────────────────────────────────

export type ChartInterval = "1d" | "1w" | "1m";
export type ChartRangeDays = 180 | 365 | 730;

interface InstrumentChartProps {
  data: InstrumentChartData | null;
  interval: ChartInterval;
  rangeDays: ChartRangeDays;
  onIntervalChange: (interval: ChartInterval) => void;
  onRangeChange: (days: ChartRangeDays) => void;
  isFetching?: boolean;
}

// ── Label maps ────────────────────────────────────────────────────────────────

const INTERVAL_LABELS: Record<ChartInterval, string> = {
  "1d": "1D",
  "1w": "1W",
  "1m": "1M",
};
const RANGE_LABELS: Record<ChartRangeDays, string> = {
  180: "6M",
  365: "1Y",
  730: "2Y",
};

function chartEmptyCopy(data: InstrumentChartData | null) {
  const market = data?.market;
  if (market === "KR") {
    return {
      title: "차트 데이터가 아직 없습니다",
      body: data?.benchmark_note ?? "가격 수집이 완료되면 캔들, 이동평균선, RS 라인이 표시됩니다.",
      action: "새로고침 대기열은 다음 단계에서 연결됩니다.",
    };
  }
  return {
    title: "Chart candles are not available yet",
    body: data?.benchmark_note ?? "Once price ingestion is complete, candles, moving averages, and the RS line will appear here.",
    action: "The manual refresh queue connects in the next phase.",
  };
}

// ── Component ─────────────────────────────────────────────────────────────────

export function InstrumentChart({
  data,
  interval,
  rangeDays,
  onIntervalChange,
  onRangeChange,
  isFetching = false,
}: InstrumentChartProps) {
  const { containerRef, chart } = useChart();
  const emptyCopy = chartEmptyCopy(data);

  // ── Data layer: rebuild all series whenever chart instance or data changes ──
  useEffect(() => {
    if (!chart || !data?.bars?.length) return;

    // ── 1. Candlestick ────────────────────────────────────────────────────────
    const candle = chart.addSeries(CandlestickSeries, {
      upColor:        CANDLE_UP,
      downColor:      CANDLE_DOWN,
      borderUpColor:  CANDLE_UP,
      borderDownColor: CANDLE_DOWN,
      wickUpColor:    CANDLE_UP,
      wickDownColor:  CANDLE_DOWN,
    });
    candle.setData(
      data.bars.map((b) => ({
        time:  b.time as Time,
        open:  b.open,
        high:  b.high,
        low:   b.low,
        close: b.close,
      }))
    );

    // ── 2. SMA overlays (pre-computed by the API — share the candle pane) ────
    const commonLineOpts = {
      lineWidth:         1 as const,
      priceLineVisible:  false,
      lastValueVisible:  false,
      crosshairMarkerVisible: false,
    };

    const sma50Series = chart.addSeries(LineSeries, {
      ...commonLineOpts,
      color: MA_COLORS.sma50,
    });
    sma50Series.setData(
      data.bars
        .filter((b) => b.sma_50 != null)
        .map((b) => ({ time: b.time as Time, value: b.sma_50! }))
    );

    const sma150Series = chart.addSeries(LineSeries, {
      ...commonLineOpts,
      color: MA_COLORS.sma150,
    });
    sma150Series.setData(
      data.bars
        .filter((b) => b.sma_150 != null)
        .map((b) => ({ time: b.time as Time, value: b.sma_150! }))
    );

    const sma200Series = chart.addSeries(LineSeries, {
      ...commonLineOpts,
      color: MA_COLORS.sma200,
    });
    sma200Series.setData(
      data.bars
        .filter((b) => b.sma_200 != null)
        .map((b) => ({ time: b.time as Time, value: b.sma_200! }))
    );

    // ── 3. Pattern markers ────────────────────────────────────────────────────
    if (data.patterns?.length) {
      const markers: SeriesMarker<Time>[] = data.patterns
        .filter((p) => p.start_date != null)
        .map((p) => ({
          time:     p.start_date as Time,
          position: "belowBar" as const,
          shape:    "arrowUp" as const,
          color:    PATTERN_COLOR[p.pattern_type] ?? PATTERN_COLOR_DEFAULT,
          text:     p.pattern_type.replace(/_/g, " "),
          size:     1,
        }));
      createSeriesMarkers(candle, markers);
    }

    // ── 4. RS line — secondary right-axis (only when data is available) ───────
    let rsSeries: ReturnType<typeof chart.addSeries> | null = null;
    if (data.rs_line?.length) {
      rsSeries = chart.addSeries(LineSeries, {
        color:             RS_COLOR,
        lineWidth:         1 as const,
        // Dedicated price scale so the RS normalised 0–200 range doesn't
        // distort the candlestick y-axis.
        priceScaleId:      "rs",
        priceLineVisible:  false,
        lastValueVisible:  true,
      });
      rsSeries.setData(
        data.rs_line.map((p) => ({ time: p.time as Time, value: p.value }))
      );
      // Keep the RS scale narrow and unobtrusive on the right edge
      chart.priceScale("rs").applyOptions({
        scaleMargins: { top: 0.7, bottom: 0 },
        visible: false, // hide the axis labels — RS value visible in tooltip
      });
    }

    // Fit everything into view after all series are added
    chart.timeScale().fitContent();

    // ── Cleanup: remove series in reverse creation order ─────────────────────
    return () => {
      if (rsSeries) {
        try { chart.removeSeries(rsSeries); } catch { /* already removed */ }
      }
      try { chart.removeSeries(sma200Series); } catch { /* already removed */ }
      try { chart.removeSeries(sma150Series); } catch { /* already removed */ }
      try { chart.removeSeries(sma50Series);  } catch { /* already removed */ }
      try { chart.removeSeries(candle);       } catch { /* already removed */ }
    };
  }, [chart, data]);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="surface-panel overflow-hidden rounded-[1.65rem]">
      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-5 pb-2 pt-4">
        <div className="flex items-center gap-3">
          <span className="tiny-label">Price Chart</span>
          {/* MA legend */}
          <div className="hidden items-center gap-2 sm:flex">
            {(
              [
                ["50", MA_COLORS.sma50],
                ["150", MA_COLORS.sma150],
                ["200", MA_COLORS.sma200],
              ] as [string, string][]
            ).map(([label, color]) => (
              <span key={label} className="flex items-center gap-1">
                <span
                  className="inline-block h-px w-4"
                  style={{ backgroundColor: color, height: 2 }}
                />
                <span className="text-[0.62rem] text-faint">MA{label}</span>
              </span>
            ))}
            {data?.rs_line?.length ? (
              <span className="flex items-center gap-1">
                <span
                  className="inline-block w-4"
                  style={{ backgroundColor: RS_COLOR, height: 2 }}
                />
                <span className="text-[0.62rem] text-faint">RS</span>
              </span>
            ) : null}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Interval chips */}
          <div className="flex gap-0.5 rounded-full border border-white/8 p-0.5">
            {(["1d", "1w", "1m"] as ChartInterval[]).map((iv) => (
              <button
                key={iv}
                type="button"
                onClick={() => onIntervalChange(iv)}
                className={cn(
                  "rounded-full px-2.5 py-1 text-[0.65rem] uppercase tracking-widest transition-colors",
                  interval === iv
                    ? "bg-white/10 text-white"
                    : "text-faint hover:text-quiet"
                )}
              >
                {INTERVAL_LABELS[iv]}
              </button>
            ))}
          </div>
          {/* Range chips */}
          <div className="flex gap-0.5 rounded-full border border-white/8 p-0.5">
            {([180, 365, 730] as ChartRangeDays[]).map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => onRangeChange(d)}
                className={cn(
                  "rounded-full px-2.5 py-1 text-[0.65rem] uppercase tracking-widest transition-colors",
                  rangeDays === d
                    ? "bg-white/10 text-white"
                    : "text-faint hover:text-quiet"
                )}
              >
                {RANGE_LABELS[d]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Chart canvas area ────────────────────────────────────────────── */}
      <div className="relative">
        {/* Skeleton / loading overlay */}
        {isFetching && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/75">
            <div className="text-xs text-faint">Loading…</div>
          </div>
        )}

        {/* lightweight-charts mounts here */}
        <div
          ref={containerRef}
          className="w-full"
          style={{ height: 400 }}
        />

        {/* Empty state: no data or empty bars array */}
        {(!data || !data.bars?.length) && !isFetching && (
          <div className="absolute inset-0 flex items-center justify-center p-6">
            <div className="max-w-md rounded-[1.35rem] border border-white/10 bg-black/40 px-5 py-5 text-center shadow-2xl backdrop-blur">
              <div className="text-sm font-medium text-white">{emptyCopy.title}</div>
              <div className="mt-2 text-xs leading-5 text-faint">{emptyCopy.body}</div>
              <div className="mt-3 rounded-full border border-white/10 px-3 py-1.5 text-[0.62rem] uppercase tracking-[0.16em] text-faint">
                {emptyCopy.action}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Benchmark note ───────────────────────────────────────────────── */}
      {data?.benchmark_note && data.bars?.length > 0 && (
        <div className="px-5 pb-3 pt-1 text-[0.62rem] text-faint">
          {data.benchmark_note}
        </div>
      )}
    </div>
  );
}
