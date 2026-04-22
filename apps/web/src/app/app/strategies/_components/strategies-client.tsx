"use client";

/**
 * StrategiesClient — 3-tab strategy breakdown page
 *
 * Tabs:
 *  • CANSLIM   — US-only (growth-stock strategy designed for US markets)
 *  • Piotroski — US + KR (fundamental health score, F-score 0–9)
 *  • Minervini — US + KR (SEPA trend-template, technical + fundamental)
 *
 * Each tab fetches strategy-specific rankings via fetchStrategyRankings()
 * and renders items with the shared RankingRow component.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  APIError,
  fetchStrategyRankings,
  type StrategyRankingsResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { RankingRow } from "@/components/ranking-row";
import { CanslimTab } from "@/app/app/strategies/_components/canslim-filter-builder";

// ── Types ─────────────────────────────────────────────────────────────────────

type StrategyTab = "canslim" | "piotroski" | "minervini";

const TAB_LABELS: Record<StrategyTab, string> = {
  canslim:    "CANSLIM",
  piotroski:  "Piotroski",
  minervini:  "Minervini",
};

/** Markets available per strategy (CANSLIM is US-only) */
const STRATEGY_MARKETS: Record<StrategyTab, Array<"US" | "KR">> = {
  canslim:   ["US"],
  piotroski: ["US", "KR"],
  minervini: ["US", "KR"],
};

// ── Sub-component: strategy list ──────────────────────────────────────────────

interface StrategyListProps {
  strategy: StrategyTab;
  market: "US" | "KR";
  initialData?: StrategyRankingsResponse;
}

function StrategyList({ strategy, market, initialData }: StrategyListProps) {
  const { data, error, isFetching } = useQuery({
    queryKey: ["strategy-rankings", strategy, market],
    queryFn:  () => fetchStrategyRankings(strategy, market),
    initialData,
    staleTime: 60_000,
    retry: (failureCount, queryError) =>
      queryError instanceof APIError && queryError.status >= 500 && failureCount < 2,
  });

  if (isFetching && !data) {
    return (
      <div className="surface-panel rounded-[1.65rem] px-5 py-8 text-center text-sm text-quiet">
        Loading…
      </div>
    );
  }

  if (error) {
    return (
      <div className="surface-panel rounded-[1.65rem] border border-[oklch(0.68_0.18_28_/_0.3)] bg-[oklch(0.31_0.06_28_/_0.14)] px-5 py-5 text-sm text-[oklch(0.89_0.04_24)]">
        {error instanceof APIError
          ? error.detail ?? `${TAB_LABELS[strategy]} rankings are temporarily unavailable.`
          : `${TAB_LABELS[strategy]} rankings are temporarily unavailable.`}
      </div>
    );
  }

  if (!data?.items?.length) {
    return (
      <div className="surface-panel rounded-[1.65rem] px-5 py-8 text-center text-sm text-quiet">
        No {TAB_LABELS[strategy]} rankings available for {market}.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {isFetching && (
        <div className="text-right text-[0.65rem] text-faint">refreshing…</div>
      )}
      {data.items.map((item) => (
        <RankingRow
          key={`${item.market}-${item.ticker}`}
          item={{
            rank:        item.rank,
            ticker:      item.ticker,
            name:        item.name,
            market:      item.market,
            // StrategyRankingItem has no exchange field — omit
            final_score: item.score ?? 0,
          }}
        />
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface StrategiesClientProps {
  initialData?: Partial<Record<string, StrategyRankingsResponse>>;
}

export function StrategiesClient({ initialData = {} }: StrategiesClientProps) {
  const [activeTab, setActiveTab] = useState<StrategyTab>("canslim");
  const [market, setMarket]       = useState<"US" | "KR">("US");

  const availableMarkets = STRATEGY_MARKETS[activeTab];

  // When switching to CANSLIM, force US (it's US-only)
  function handleTabChange(tab: StrategyTab) {
    setActiveTab(tab);
    if (STRATEGY_MARKETS[tab].length === 1) {
      setMarket(STRATEGY_MARKETS[tab][0]);
    }
  }

  const cacheKey = `${activeTab}-${market}`;

  return (
    <div className="app-shell space-y-4 py-4 sm:py-6">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="surface-panel rounded-[1.65rem] px-5 py-5">
        <div className="tiny-label">Strategies</div>
        <h1 className="mt-2 font-heading text-4xl uppercase tracking-[0.04em] text-white">
          Strategy Rankings
        </h1>
        <p className="mt-1 text-xs text-faint">
          Per-strategy scores ranked independently — drill into each methodology.
        </p>

        {/* ── Tab bar ────────────────────────────────────────────────── */}
        <div className="mt-5 flex flex-wrap gap-2">
          <div className="flex gap-0.5 rounded-full border border-white/8 p-0.5">
            {(Object.keys(TAB_LABELS) as StrategyTab[]).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => handleTabChange(tab)}
                className={cn(
                  "rounded-full px-4 py-1.5 text-[0.72rem] uppercase tracking-[0.14em] transition-colors",
                  activeTab === tab
                    ? "bg-white/10 text-white"
                    : "text-faint hover:text-quiet"
                )}
              >
                {TAB_LABELS[tab]}
              </button>
            ))}
          </div>

          {/* Market selector — hidden for CANSLIM (US-only) */}
          {availableMarkets.length > 1 && (
            <div className="flex gap-0.5 rounded-full border border-white/8 p-0.5">
              {availableMarkets.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMarket(m)}
                  className={cn(
                    "rounded-full px-4 py-1.5 text-[0.72rem] uppercase tracking-[0.14em] transition-colors",
                    market === m
                      ? "bg-white/10 text-white"
                      : "text-faint hover:text-quiet"
                  )}
                >
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Context note */}
        {activeTab === "canslim" && (
          <div className="mt-3 text-[0.65rem] text-faint">
            CANSLIM is designed for US growth stocks — KR market not included.
          </div>
        )}
      </div>

      {/* ── Strategy list ──────────────────────────────────────────────── */}
      {activeTab === "canslim" ? (
        <CanslimTab initialData={initialData["canslim-US"]} />
      ) : (
        <StrategyList
          key={cacheKey}
          strategy={activeTab}
          market={market}
          initialData={initialData[cacheKey]}
        />
      )}
    </div>
  );
}
