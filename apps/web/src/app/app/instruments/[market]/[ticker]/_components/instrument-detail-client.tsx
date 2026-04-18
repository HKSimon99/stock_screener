"use client";

import { useQuery } from "@tanstack/react-query";
import { Pin } from "lucide-react";
import {
  fetchInstrument,
  fetchInstrumentChart,
  type InstrumentChart,
  type InstrumentDetail,
} from "@/lib/api";
import { useUIStore } from "@/lib/store";
import { cn } from "@/lib/utils";

interface InstrumentDetailClientProps {
  ticker: string;
  market: "US" | "KR";
  initialData: InstrumentDetail | null;
  initialChartData: InstrumentChart | null;
}

function scoreChip(label: string, score: number, max = 100) {
  const pct = Math.min(100, Math.max(0, (score / max) * 100));
  return (
    <div className="surface-panel-soft rounded-[1.2rem] px-4 py-3">
      <div className="text-[0.65rem] uppercase tracking-widest text-faint">{label}</div>
      <div className="mt-1 font-mono text-lg text-white">{score.toFixed(1)}</div>
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
  const color =
    level === "HIGH"
      ? "border-[oklch(0.92_0.04_150_/_0.4)] bg-[oklch(0.92_0.04_150_/_0.1)] text-[oklch(0.92_0.04_150)]"
      : level === "MEDIUM"
      ? "border-[oklch(0.94_0.04_88_/_0.4)] bg-[oklch(0.94_0.04_88_/_0.1)] text-[oklch(0.94_0.04_88)]"
      : "border-white/10 text-faint";
  return (
    <span
      className={cn(
        "inline-flex rounded-full border px-3 py-1 text-[0.68rem] uppercase tracking-widest",
        color
      )}
    >
      {level} conviction
    </span>
  );
}

export function InstrumentDetailClient({
  ticker,
  market,
  initialData,
  initialChartData,
}: InstrumentDetailClientProps) {
  const togglePinned = useUIStore((state) => state.togglePinnedInstrument);
  const isPinned = useUIStore((state) => state.isPinned);
  const pinned = isPinned(ticker, market);

  const { data } = useQuery({
    queryKey: ["instrument", ticker, market],
    queryFn: () => fetchInstrument(ticker, market),
    initialData: initialData ?? undefined,
    staleTime: 60_000,
  });

  const { data: chart } = useQuery({
    queryKey: ["instrument-chart", ticker, market],
    queryFn: () => fetchInstrumentChart(ticker, market),
    initialData: initialChartData ?? undefined,
    staleTime: 60_000,
  });

  if (!data) {
    return (
      <div className="app-shell py-12 text-center">
        <div className="text-sm text-quiet">Loading instrument data…</div>
      </div>
    );
  }

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

      {/* Scores grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {scoreChip("Consensus", data.final_score)}
        {scoreChip("CANSLIM", data.canslim_score)}
        {scoreChip("Piotroski", (data.piotroski_score / 9) * 100, 100)}
        {scoreChip("Minervini", (data.minervini_score / 8) * 100, 100)}
        {scoreChip("Weinstein", data.weinstein_score)}
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

          {/* Dual Momentum */}
          {data.dual_mom_detail && (
            <div>
              <div className="mb-2 text-xs text-faint uppercase tracking-widest">Dual Momentum</div>
              <div className="flex flex-wrap gap-1">
                <span
                  className={cn(
                    "rounded border px-2 py-0.5 text-[0.65rem] uppercase tracking-widest",
                    data.dual_mom_detail.abs_mom
                      ? "border-[oklch(0.92_0.04_150_/_0.4)] text-[oklch(0.92_0.04_150)]"
                      : "border-white/10 text-faint"
                  )}
                >
                  Abs
                </span>
                <span
                  className={cn(
                    "rounded border px-2 py-0.5 text-[0.65rem] uppercase tracking-widest",
                    data.dual_mom_detail.rel_mom
                      ? "border-[oklch(0.92_0.04_150_/_0.4)] text-[oklch(0.92_0.04_150)]"
                      : "border-white/10 text-faint"
                  )}
                >
                  Rel
                </span>
              </div>
              <div className="mt-1 text-xs text-faint">
                12m ret {data.dual_mom_detail.ret_12m > 0 ? "+" : ""}
                {(data.dual_mom_detail.ret_12m * 100).toFixed(1)}% · bmark{" "}
                {data.dual_mom_detail.benchmark_ret_12m > 0 ? "+" : ""}
                {(data.dual_mom_detail.benchmark_ret_12m * 100).toFixed(1)}%
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Chart summary (bars count) */}
      {chart && (
        <div className="surface-panel rounded-[1.65rem] px-5 py-5">
          <div className="tiny-label mb-2">Price Data</div>
          <div className="text-sm text-quiet">
            {chart.bars.length} {chart.interval} bars · {chart.range_days}d range
            {chart.patterns.length > 0 && ` · ${chart.patterns.length} pattern${chart.patterns.length !== 1 ? "s" : ""} detected`}
          </div>
          {chart.patterns.map((p, i) => (
            <div key={i} className="mt-2 text-xs text-faint">
              {p.pattern_type.replace(/_/g, " ")} · {(p.confidence * 100).toFixed(0)}% confidence
              {p.pivot_price != null && ` · pivot $${p.pivot_price.toFixed(2)}`}
            </div>
          ))}
        </div>
      )}

      {/* Freshness */}
      {data.freshness && (
        <div className="surface-panel rounded-[1.65rem] px-5 py-4">
          <div className="tiny-label mb-2">Data Freshness</div>
          <div className="flex flex-wrap gap-4 text-xs text-faint">
            {Object.entries(data.freshness).map(([k, v]) => (
              <span key={k}>
                <span className="capitalize">{k.replace(/_/g, " ")}</span>:{" "}
                <span className="text-white">{String(v)}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
