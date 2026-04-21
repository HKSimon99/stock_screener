"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Pin } from "lucide-react";
import {
  APIError,
  fetchInstrument,
  fetchInstrumentChart,
  type InstrumentChart,
  type InstrumentDetail,
} from "@/lib/api";
import { useUIStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { InstrumentChart as InstrumentChartComponent, type ChartInterval, type ChartRangeDays } from "@/components/instrument-chart";

interface InstrumentDetailClientProps {
  ticker: string;
  market: "US" | "KR";
  initialData: InstrumentDetail | null;
  initialChartData: InstrumentChart | null;
}

function scoreChip(label: string, score?: number, max = 100) {
  const hasScore = typeof score === "number" && Number.isFinite(score);
  const safeScore = hasScore ? score : 0;
  const pct = hasScore ? Math.min(100, Math.max(0, (safeScore / max) * 100)) : 0;
  return (
    <div className="surface-panel-soft rounded-[1.2rem] px-4 py-3">
      <div className="text-[0.65rem] uppercase tracking-widest text-faint">{label}</div>
      <div className="mt-1 font-mono text-lg text-white">{hasScore ? safeScore.toFixed(1) : "—"}</div>
      <div className="relative mt-2 h-1 w-full overflow-hidden rounded-full bg-white/8">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-[oklch(0.78_0.11_84_/_0.6)]"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function convictionBadge(level: string) {
  const colorMap: Record<string, string> = {
    DIAMOND: "border-cyan-400/40 bg-cyan-400/10 text-cyan-300",
    PLATINUM: "border-violet-400/40 bg-violet-400/10 text-violet-300",
    GOLD: "border-amber-400/40 bg-amber-400/10 text-amber-300",
    SILVER: "border-slate-400/40 bg-slate-400/10 text-slate-300",
    BRONZE: "border-orange-400/40 bg-orange-400/10 text-orange-300",
    UNRANKED: "border-slate-600/40 bg-slate-600/10 text-slate-400",
  };
  const color = colorMap[level] || "border-white/10 text-faint";
  return (
    <span
      className={cn(
        "inline-flex rounded-full border px-3 py-1 text-[0.68rem] uppercase tracking-widest",
        color
      )}
    >
      {level}
    </span>
  );
}

export function InstrumentDetailClient({
  ticker,
  market,
  initialData,
  initialChartData,
}: InstrumentDetailClientProps) {
  const [chartInterval, setChartInterval] = useState<ChartInterval>("1d");
  const [chartRangeDays, setChartRangeDays] = useState<ChartRangeDays>(365);

  const togglePinned = useUIStore((state) => state.togglePinnedInstrument);
  const isPinned = useUIStore((state) => state.isPinned);
  const pinned = isPinned(ticker, market);

  const {
    data,
    error,
    isPending,
    isFetching,
  } = useQuery({
    queryKey: ["instrument", ticker, market],
    queryFn: () => fetchInstrument(ticker, market),
    initialData: initialData ?? undefined,
    staleTime: initialData ? 30_000 : 0,
    refetchOnMount: false,
    retry: (failureCount, queryError) =>
      queryError instanceof APIError && queryError.status >= 500 && failureCount < 2,
  });

  const { data: chart, isFetching: chartFetching } = useQuery({
    queryKey: ["instrument-chart", ticker, market, chartInterval, chartRangeDays],
    queryFn: () =>
      fetchInstrumentChart(ticker, market, {
        interval: chartInterval,
        range_days: chartRangeDays,
        include_indicators: true,
      }),
    initialData:
      chartInterval === "1d" && chartRangeDays === 365
        ? (initialChartData ?? undefined)
        : undefined,
    staleTime: chartInterval === "1d" && chartRangeDays === 365 && initialChartData ? 30_000 : 0,
    refetchOnMount: false,
  });

  if (isPending && !data) {
    return (
      <div className="app-shell py-12 text-center">
        <div className="text-sm text-quiet">Loading instrument data…</div>
      </div>
    );
  }

  if (!data) {
    const detail =
      error instanceof APIError
        ? error.detail ?? "This instrument detail request failed."
        : "Instrument detail is temporarily unavailable.";

    return (
      <div className="app-shell py-12">
        <div className="surface-panel rounded-[1.65rem] px-5 py-5 text-sm text-[oklch(0.9_0.03_88)]">
          {detail}
        </div>
      </div>
    );
  }

  const isRanked = data.coverage_state === "ranked" && data.conviction_level !== "UNRANKED";

  return (
    <div className="app-shell space-y-4 py-4 sm:py-6">
      {/* Header */}
      <div className="surface-panel rounded-[1.65rem] px-5 py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <div className="tiny-label">
                {market} / {data.exchange ?? ""}
              </div>
            </div>
            <h1 className="mt-2 font-heading text-5xl uppercase tracking-[0.03em] text-white">
              {ticker}
            </h1>
            {data.name && (
              <div className="mt-1 text-sm text-quiet">
                {data.name}
                {data.name_kr ? ` · ${data.name_kr}` : ""}
              </div>
            )}
            {isFetching && (
              <div className="mt-2 text-xs uppercase tracking-[0.16em] text-faint">
                Refreshing…
              </div>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {convictionBadge(data.conviction_level)}
              {data.sector && (
                <span className="rounded-full border border-white/10 px-3 py-1 text-[0.68rem] uppercase tracking-widest text-faint">
                  {data.sector}
                </span>
              )}
              {data.regime_warning && (
                <span className="rounded-full border border-[oklch(0.9_0.06_75_/_0.4)] bg-[oklch(0.9_0.06_75_/_0.08)] px-3 py-1 text-[0.68rem] uppercase tracking-widest text-[oklch(0.9_0.06_75)]">
                  ⚠ Regime warning
                </span>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={() =>
              togglePinned({
                ticker,
                market,
                name: data.name ?? ticker,
                exchange: data.exchange ?? "",
              })
            }
            className={cn(
              "inline-flex shrink-0 items-center gap-2 rounded-full border px-4 py-2 text-[0.72rem] uppercase tracking-[0.16em] transition-colors",
              pinned
                ? "border-[oklch(0.78_0.11_84_/_0.42)] bg-[oklch(0.8_0.11_84_/_0.14)] text-white"
                : "border-white/8 text-faint hover:text-white"
            )}
          >
            <Pin className="size-3.5" />
            {pinned ? "Pinned" : "Pin"}
          </button>
        </div>
      </div>

      {!isRanked && (
        <div className="surface-panel rounded-[1.65rem] border border-[oklch(0.9_0.03_88_/_0.18)] px-5 py-4">
          <div className="tiny-label">Coverage Status</div>
          <div className="mt-2 text-sm leading-6 text-quiet">
            This symbol is in the universe, but the full ranking model has not scored it yet. We’re
            showing available identity, freshness, and chart data while scoring catches up.
          </div>
          {data.ranking_eligibility?.reasons && data.ranking_eligibility.reasons.length > 0 && (
            <div className="mt-3 text-xs text-faint">
              {data.ranking_eligibility.reasons.join(" · ")}
            </div>
          )}
        </div>
      )}

      {/* Scores grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {scoreChip("Consensus", isRanked ? data.final_score : undefined)}
        {scoreChip("CANSLIM", typeof data.canslim_score === "number" && data.canslim_score > 0 ? data.canslim_score : undefined)}
        {scoreChip(
          "Piotroski",
          typeof data.piotroski_score === "number" && data.piotroski_score > 0
            ? (data.piotroski_score / 9) * 100
            : undefined,
          100
        )}
        {scoreChip(
          "Minervini",
          typeof data.minervini_score === "number" && data.minervini_score > 0
            ? (data.minervini_score / 8) * 100
            : undefined,
          100
        )}
        {scoreChip("Weinstein", typeof data.weinstein_score === "number" && data.weinstein_score > 0 ? data.weinstein_score : undefined)}
      </div>

      {/* Strategy passes */}
      <div className="surface-panel rounded-[1.65rem] px-5 py-5">
        <div className="tiny-label mb-4">Strategy Breakdown</div>
        <div className="grid gap-3 sm:grid-cols-2">
          {/* CANSLIM */}
          {data.canslim_breakdown && (
            <div>
              <div className="mb-2 text-xs text-faint uppercase tracking-widest">CANSLIM</div>
              <div className="flex flex-wrap gap-1">
                {data.canslim_breakdown.map((c) => (
                  <span
                    key={c.key}
                    className={cn(
                      "rounded border px-2 py-0.5 text-[0.65rem] font-mono uppercase",
                      c.score > 0
                        ? "border-[oklch(0.92_0.04_150_/_0.4)] text-[oklch(0.92_0.04_150)]"
                        : "border-white/10 text-faint"
                    )}
                    title={c.label}
                  >
                    {c.key}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Piotroski */}
          {data.piotroski_detail && (
            <div>
              <div className="mb-2 text-xs text-faint uppercase tracking-widest">
                Piotroski F-Score: {data.piotroski_detail.f_score}/9
              </div>
              <div className="flex flex-wrap gap-1">
                {(Object.entries(data.piotroski_detail) as [string, boolean | number][])
                  .filter(([k]) => k.startsWith("f") && k !== "f_score")
                  .map(([k, v]) => (
                    <span
                      key={k}
                      className={cn(
                        "rounded border px-2 py-0.5 text-[0.65rem] font-mono uppercase",
                        v
                          ? "border-[oklch(0.92_0.04_150_/_0.4)] text-[oklch(0.92_0.04_150)]"
                          : "border-white/10 text-faint"
                      )}
                    >
                      {k.toUpperCase()}
                    </span>
                  ))}
              </div>
            </div>
          )}

          {/* Minervini */}
          {data.minervini_detail && (
            <div>
              <div className="mb-2 text-xs text-faint uppercase tracking-widest">
                Minervini: {data.minervini_detail.count_passing}/8
              </div>
              <div className="flex flex-wrap gap-1">
                {(Object.entries(data.minervini_detail) as [string, boolean | number][])
                  .filter(([k]) => k.startsWith("t"))
                  .map(([k, v]) => (
                    <span
                      key={k}
                      className={cn(
                        "rounded border px-2 py-0.5 text-[0.65rem] font-mono uppercase",
                        v
                          ? "border-[oklch(0.92_0.04_150_/_0.4)] text-[oklch(0.92_0.04_150)]"
                          : "border-white/10 text-faint"
                      )}
                    >
                      {k.toUpperCase()}
                    </span>
                  ))}
              </div>
            </div>
          )}

          {/* Weinstein */}
          {data.weinstein_detail && (
            <div>
              <div className="mb-2 text-xs text-faint uppercase tracking-widest">Weinstein</div>
              <div className="text-sm text-white">
                Stage {data.weinstein_detail.stage}
                {data.weinstein_detail.sub_stage ? ` · ${data.weinstein_detail.sub_stage}` : ""}
              </div>
              <div className="mt-1 text-xs text-faint">
                MA slope {data.weinstein_detail.ma_slope.toFixed(2)} ·{" "}
                {data.weinstein_detail.price_vs_ma > 0 ? "+" : ""}
                {(data.weinstein_detail.price_vs_ma * 100).toFixed(1)}% vs MA
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Price chart */}
      <InstrumentChartComponent
        data={chart ?? null}
        interval={chartInterval}
        rangeDays={chartRangeDays}
        onIntervalChange={setChartInterval}
        onRangeChange={setChartRangeDays}
        isFetching={chartFetching}
      />

      {/* Freshness */}
      {data.freshness && (
        <div className="surface-panel rounded-[1.65rem] px-5 py-4">
          <div className="tiny-label mb-2">Data Freshness</div>
          <div className="flex flex-wrap gap-4 text-xs text-faint">
            {Object.entries(data.freshness).map(([k, v]) => (
              <span key={k}>
                <span className="capitalize">{k.replace(/_/g, " ")}</span>:{" "}
                <span className={v ? "text-white" : "text-faint"}>{v ?? "—"}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
