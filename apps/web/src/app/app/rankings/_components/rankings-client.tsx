"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import {
  APIError,
  fetchRankings,
  type RankingItem,
  type RankingsResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { RankingRow } from "@/components/ranking-row";

interface RankingsClientProps {
  initialFilters: {
    market: "US" | "KR";
    assetType: "stock" | "etf";
    conviction: string;
    limit: number;
  };
  initialData: RankingsResponse | null;
}

export function RankingsClient({ initialFilters, initialData }: RankingsClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const market = (searchParams.get("market") as "US" | "KR") ?? initialFilters.market;
  const assetType = (searchParams.get("asset_type") as "stock" | "etf") ?? initialFilters.assetType;
  const conviction = searchParams.get("conviction") ?? initialFilters.conviction;

  const { data, error, isFetching } = useQuery({
    queryKey: ["rankings", market, assetType, conviction, initialFilters.limit],
    queryFn: () =>
      fetchRankings({
        market,
        asset_type: assetType,
        conviction: conviction || undefined,
        limit: initialFilters.limit,
      }),
    initialData: initialData ?? undefined,
    staleTime: 0,
    refetchOnMount: "always",
    retry: (failureCount, queryError) =>
      queryError instanceof APIError && queryError.status >= 500 && failureCount < 2,
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
        {error && (
          <div className="surface-panel rounded-[1.65rem] border border-[oklch(0.68_0.18_28_/_0.3)] bg-[oklch(0.31_0.06_28_/_0.14)] px-5 py-5 text-sm text-[oklch(0.89_0.04_24)]">
            {error instanceof APIError
              ? error.detail ?? "Rankings are temporarily unavailable."
              : "Rankings are temporarily unavailable."}
          </div>
        )}

        {data?.items.map((item: RankingItem) => (
          <RankingRow
            key={`${item.market}-${item.ticker}`}
            item={{
              rank:                 item.rank,
              ticker:               item.ticker,
              name:                 item.name,
              market:               item.market,
              exchange:             item.exchange,
              conviction_level:     item.conviction_level,
              final_score:          item.final_score,
              strategy_pass_count:  item.strategy_pass_count,
              regime_warning:       item.regime_warning,
            }}
          />
        ))}

        {!error && !data?.items.length && !isFetching && (
          <div className="surface-panel rounded-[1.65rem] px-5 py-8 text-center text-sm text-quiet">
            No ranked instruments found for the current filters.
          </div>
        )}
      </div>
    </div>
  );
}
