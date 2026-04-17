"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Pin, Search, Sparkles } from "lucide-react";
import {
  APIError,
  buildInstrumentPath,
  fetchInstrumentSearch,
  type SearchResult,
} from "@/lib/api";
import { SavedInstrument, useUIStore } from "@/lib/store";
import { cn } from "@/lib/utils";

interface SearchClientProps {
  initialQuery: string;
  initialMarket?: "US" | "KR";
  initialAssetType?: "stock" | "etf";
}

function coverageTone(state: SearchResult["coverage_state"]): string {
  if (state === "ranked") return "text-[oklch(0.92_0.04_150)]";
  if (state === "fundamentals_ready") return "text-[oklch(0.94_0.04_88)]";
  if (state === "price_ready") return "text-[oklch(0.9_0.03_192)]";
  return "text-faint";
}

export function SearchClient({
  initialQuery,
  initialMarket,
  initialAssetType,
}: SearchClientProps) {
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);
  const deferredQuery = useDeferredValue(query);
  const [market, setMarket] = useState<"US" | "KR" | "ALL">(initialMarket ?? "ALL");
  const [assetType, setAssetType] = useState<"stock" | "etf" | "ALL">(initialAssetType ?? "ALL");
  const recentSearches = useUIStore((state) => state.recentSearches);
  const pinned = useUIStore((state) => state.pinnedInstruments);
  const addRecentSearch = useUIStore((state) => state.addRecentSearch);
  const togglePinned = useUIStore((state) => state.togglePinnedInstrument);
  const isPinned = useUIStore((state) => state.isPinned);

  useEffect(() => {
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    if (market !== "ALL") params.set("market", market);
    if (assetType !== "ALL") params.set("asset_type", assetType);
    const qs = params.toString();
    router.replace(qs ? `/app/search?${qs}` : "/app/search", { scroll: false });
  }, [assetType, market, query, router]);

  const { data, isFetching, error } = useQuery({
    queryKey: ["search", deferredQuery, market, assetType],
    queryFn: () =>
      fetchInstrumentSearch({
        q: deferredQuery.trim(),
        market: market === "ALL" ? undefined : market,
        asset_type: assetType === "ALL" ? undefined : assetType,
        limit: 24,
      }),
    enabled: deferredQuery.trim().length > 0,
  });

  const spotlight = useMemo(() => pinned.slice(0, 4), [pinned]);

  function remember(item: SavedInstrument) {
    addRecentSearch(item);
  }

  return (
    <div className="app-shell py-4 sm:py-6">
      <section className="surface-panel rounded-[2rem] px-5 py-5 sm:px-6">
        <div className="section-kicker">Symbol Search</div>
        <h1 className="mt-3 font-heading text-5xl uppercase tracking-[0.03em] text-white">
          Search the covered universe first.
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-quiet">
          Search by ticker, company, Korean name, or exchange. The result list shows whether a symbol
          is only searchable, price-ready, fundamentals-ready, or fully ranked.
        </p>

        <div className="mt-6 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto]">
          <label className="relative">
            <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-faint" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="AAPL, Samsung, semiconductors, NYSE..."
              className="w-full rounded-[1.4rem] border border-white/10 bg-black/18 py-4 pl-11 pr-4 text-sm text-white outline-none transition-colors placeholder:text-faint focus:border-[oklch(0.78_0.11_84_/_0.42)]"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            {(["ALL", "US", "KR"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setMarket(value)}
                className="filter-chip px-4 py-2 text-sm font-medium"
                data-active={market === value}
              >
                {value === "ALL" ? "All Markets" : value}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {(["ALL", "stock", "etf"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setAssetType(value)}
                className="filter-chip px-4 py-2 text-sm font-medium"
                data-active={assetType === value}
              >
                {value === "ALL" ? "All Types" : value.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </section>

      {(spotlight.length > 0 || recentSearches.length > 0) && (
        <section className="mt-6 grid gap-4 xl:grid-cols-2">
          <article className="surface-panel rounded-[1.8rem] px-5 py-5">
            <div className="tiny-label">Pinned symbols</div>
            <div className="mt-4 flex flex-wrap gap-2">
              {spotlight.length > 0 ? (
                spotlight.map((item) => (
                  <Link
                    key={`${item.market}-${item.ticker}`}
                    href={buildInstrumentPath(item.ticker, item.market)}
                    className="rounded-full border border-white/10 px-4 py-2 text-sm text-faint transition-colors hover:text-white"
                  >
                    {item.market} {item.ticker}
                  </Link>
                ))
              ) : (
                <div className="text-sm text-quiet">Pin symbols from a result row to keep them nearby.</div>
              )}
            </div>
          </article>

          <article className="surface-panel rounded-[1.8rem] px-5 py-5">
            <div className="tiny-label">Recent searches</div>
            <div className="mt-4 flex flex-wrap gap-2">
              {recentSearches.length > 0 ? (
                recentSearches.map((item) => (
                  <Link
                    key={`${item.market}-${item.ticker}`}
                    href={buildInstrumentPath(item.ticker, item.market)}
                    className="rounded-full border border-white/10 px-4 py-2 text-sm text-faint transition-colors hover:text-white"
                  >
                    {item.market} {item.ticker}
                  </Link>
                ))
              ) : (
                <div className="text-sm text-quiet">Your recent search trail will appear here.</div>
              )}
            </div>
          </article>
        </section>
      )}

      <section className="mt-6 surface-panel rounded-[1.8rem] px-5 py-5 sm:px-6">
        <div className="flex items-center justify-between gap-3">
          <div className="tiny-label">Results</div>
          <div className="text-sm text-faint">
            {isFetching ? "Searching..." : `${data?.total ?? 0} matches`}
          </div>
        </div>

        {error ? (
          <div className="mt-5 rounded-[1.4rem] border border-[oklch(0.68_0.18_28_/_0.3)] bg-[oklch(0.31_0.06_28_/_0.14)] px-5 py-4 text-sm text-[oklch(0.89_0.04_24)]">
            {(error as APIError).detail ?? "Search is temporarily unavailable."}
          </div>
        ) : !query.trim() ? (
          <div className="mt-5 rounded-[1.4rem] border border-white/10 bg-black/14 px-5 py-6">
            <div className="flex items-center gap-3 text-white">
              <Sparkles className="size-5" />
              Start with a ticker, company, or Korean name.
            </div>
          </div>
        ) : data && data.items.length === 0 ? (
          <div className="mt-5 rounded-[1.4rem] border border-white/10 bg-black/14 px-5 py-6 text-sm text-quiet">
            No matching symbols were found in the current covered universe.
          </div>
        ) : (
          <div className="mt-5 grid gap-3">
            {data?.items.map((item) => {
              const pinnedState = isPinned(item.ticker, item.market);
              return (
                <div
                  key={`${item.market}-${item.ticker}`}
                  className="surface-panel-soft flex flex-col gap-4 rounded-[1.45rem] px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <Link
                      href={buildInstrumentPath(item.ticker, item.market)}
                      onClick={() =>
                        remember({
                          ticker: item.ticker,
                          market: item.market,
                          name: item.name,
                          exchange: item.exchange,
                        })
                      }
                      className="flex flex-wrap items-center gap-2"
                    >
                      <span className="font-heading text-3xl uppercase leading-none text-white">
                        {item.ticker}
                      </span>
                      <span className="rounded-full border border-white/10 px-2 py-1 text-[0.68rem] uppercase tracking-[0.16em] text-faint">
                        {item.market} / {item.exchange}
                      </span>
                    </Link>
                    <div className="mt-2 text-sm text-quiet">
                      {item.name}
                      {item.name_kr ? ` · ${item.name_kr}` : ""}
                    </div>
                    <div className={cn("mt-2 text-[0.72rem] uppercase tracking-[0.16em]", coverageTone(item.coverage_state))}>
                      {item.coverage_state.replaceAll("_", " ")}
                    </div>
                    {item.ranking_eligibility.reasons.length > 0 && (
                      <div className="mt-2 text-xs text-faint">
                        {item.ranking_eligibility.reasons.join(" · ")}
                      </div>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() =>
                      togglePinned({
                        ticker: item.ticker,
                        market: item.market,
                        name: item.name,
                        exchange: item.exchange,
                      })
                    }
                    className={cn(
                      "inline-flex items-center gap-2 self-start rounded-full border px-4 py-2 text-[0.72rem] uppercase tracking-[0.16em] transition-colors",
                      pinnedState
                        ? "border-[oklch(0.78_0.11_84_/_0.42)] bg-[oklch(0.8_0.11_84_/_0.14)] text-white"
                        : "border-white/10 text-faint hover:text-white"
                    )}
                  >
                    <Pin className="size-3.5" />
                    {pinnedState ? "Pinned" : "Pin"}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
