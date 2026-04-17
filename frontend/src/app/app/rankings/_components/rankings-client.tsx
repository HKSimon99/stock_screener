"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Pin } from "lucide-react";
import {
  buildInstrumentPath,
  fetchRankings,
  type RankingItem,
  type RankingsResponse,
} from "@/lib/api";
import { useUIStore } from "@/lib/store";
import { cn } from "@/lib/utils";

interface RankingsClientProps {
  initialFilters: {
    market: "US" | "KR";
    assetType: "stock" | "etf";
    conviction: string;
    limit: number;
  };
  initialData: RankingsResponse | null;
}

function convictionColor(level: string): string {
  if (level === "HIGH") return "text-[oklch(0.92_0.04_150)]";
  if (level === "MEDIUM") return "text-[oklch(0.94_0.04_88)]";
  return "text-faint";
}

function scoreBar(score: number) {
  const pct = Math.min(100, Math.max(0, score)).toFixed(0);
  return (
    <div className="relative mt-1 h-1 w-24 overflow-hidden rounded-full bg-white/8">
      <div
        className="absolute inset-y-0 left-0 rounded-full bg-[oklch(0.78_0.11_84_/_0.6)]"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function RankingsClient({ initialFilters, initialData }: RankingsClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const market = (searchParams.get("market") as "US" | "KR") ?? initialFilters.market;
  const assetType = (searchParams.get("asset_type") as "stock" | "etf") ?? initialFilters.assetType;
  const togglePinned = useUIStore((state) => state.togglePinnedInstrument);
  const isPinned = useUIStore((state) => state.isPinned);

  const { data, isFetching } = useQuery({
    queryKey: ["rankings", market, assetType, initialFilters.limit],
    queryFn: () =>
      fetchRankings({ market, asset_type: assetType, limit: initialFilters.limit }),
    initialData: initialData ?? undefined,
    staleTime: 60_000,
  });

  function setFilter(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set(key, value);
    router.replace(`/app/rankings?${params.toString()}`, { scroll: false });
  }

  return (
    <div className="app-shell space-y-4 py-4 sm:py-6">
      {/* Header */}
      <div className="surface-panel rounded-[1.65rem] px-5 py-5">
        <div className="tiny-label">Consensus Rankings</div>
        <h1 className="mt-2 font-heading text-4xl uppercase tracking-[0.04em] text-white">
          {market} {assetType === "etf" ? "ETF" : "Stock"} Rankings
        </h1>
        {data && (
          <div className="mt-2 text-xs text-faint">
            {data.total} instruments · scored {data.score_date}
            {isFetching && " · refreshing…"}
          </div>
        )}

        {/* Filters */}
        <div className="mt-4 flex flex-wrap gap-2">
          {(["US", "KR"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setFilter("market", m)}
              className={cn(
                "rounded-full border px-4 py-2 text-[0.72rem] uppercase tracking-[0.16em] transition-colors",
                market === m
                  ? "border-[oklch(0.78_0.11_84_/_0.42)] bg-[oklch(0.8_0.11_84_/_0.12)] text-white"
                  : "border-white/8 text-faint hover:text-white"
              )}
            >
              {m}
            </button>
          ))}
          {(["stock", "etf"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setFilter("asset_type", t)}
              className={cn(
                "rounded-full border px-4 py-2 text-[0.72rem] uppercase tracking-[0.16em] transition-colors",
                assetType === t
                  ? "border-[oklch(0.78_0.11_84_/_0.42)] bg-[oklch(0.8_0.11_84_/_0.12)] text-white"
                  : "border-white/8 text-faint hover:text-white"
              )}
            >
              {t.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Regime warning */}
      {(data?.regime_warning_count ?? 0) > 0 && (
        <div className="flex items-center gap-3 rounded-[1.65rem] border border-[oklch(0.78_0.18_55_/_0.35)] bg-[oklch(0.35_0.07_55_/_0.15)] px-5 py-3 text-sm text-[oklch(0.9_0.06_75)]">
          <AlertTriangle className="size-4 shrink-0" />
          {data!.regime_warning_count} instruments have an active regime warning.
        </div>
      )}

      {/* List */}
      <div className="space-y-2">
        {data?.items.map((item: RankingItem) => {
          const pinned = isPinned(item.ticker, item.market);
          return (
            <div
              key={`${item.market}-${item.ticker}`}
              className="surface-panel rounded-[1.45rem] px-4 py-4 sm:px-5"
            >
              <div className="flex items-start gap-4">
                {/* Rank */}
                <div className="w-10 shrink-0 text-right font-mono text-lg text-faint">
                  {item.rank}
                </div>

                {/* Name + scores */}
                <div className="min-w-0 flex-1">
                  <Link
                    href={buildInstrumentPath(item.ticker, item.market)}
                    className="flex flex-wrap items-center gap-2"
                  >
                    <span className="font-heading text-2xl uppercase text-white">
                      {item.ticker}
                    </span>
                    {item.exchange && (
                      <span className="rounded-full border border-white/10 px-2 py-0.5 text-[0.65rem] uppercase tracking-widest text-faint">
                        {item.market} / {item.exchange}
                      </span>
                    )}
                  </Link>
                  {item.name && (
                    <div className="mt-0.5 truncate text-sm text-quiet">{item.name}</div>
                  )}
                  <div className={cn("mt-1 text-[0.68rem] uppercase tracking-widest", convictionColor(item.conviction_level))}>
                    {item.conviction_level} conviction · {item.strategy_pass_count} strategies
                    {item.regime_warning && (
                      <span className="ml-2 text-[oklch(0.9_0.06_75)]">⚠ regime</span>
                    )}
                  </div>
                </div>

                {/* Score + pin */}
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <div className="text-right">
                    <div className="font-mono text-lg text-white">
                      {item.final_score.toFixed(1)}
                    </div>
                    {scoreBar(item.final_score)}
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      togglePinned({
                        ticker: item.ticker,
                        market: item.market,
                        name: item.name ?? item.ticker,
                        exchange: item.exchange ?? "",
                      })
                    }
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[0.65rem] uppercase tracking-[0.14em] transition-colors",
                      pinned
                        ? "border-[oklch(0.78_0.11_84_/_0.42)] bg-[oklch(0.8_0.11_84_/_0.14)] text-white"
                        : "border-white/8 text-faint hover:text-white"
                    )}
                  >
                    <Pin className="size-3" />
                    {pinned ? "Pinned" : "Pin"}
                  </button>
                </div>
              </div>
            </div>
          );
        })}

        {!data?.items.length && !isFetching && (
          <div className="surface-panel rounded-[1.65rem] px-5 py-8 text-center text-sm text-quiet">
            No ranked instruments found for the current filters.
          </div>
        )}
      </div>
    </div>
  );
}
