"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchMarketRegimeBoard, type MarketRegime, type MarketRegimeBoard } from "@/lib/api";
import { cn } from "@/lib/utils";

interface MarketRegimeClientProps {
  initialData: MarketRegimeBoard | null;
}

function regimeColor(state?: string): string {
  if (!state) return "text-faint";
  if (state === "BULL") return "text-[oklch(0.92_0.04_150)]";
  if (state === "BEAR") return "text-[oklch(0.85_0.12_28)]";
  if (state === "CORRECTION") return "text-[oklch(0.9_0.06_75)]";
  return "text-[oklch(0.9_0.03_192)]";
}

function regimeBg(state?: string): string {
  if (!state) return "";
  if (state === "BULL") return "border-[oklch(0.92_0.04_150_/_0.25)] bg-[oklch(0.92_0.04_150_/_0.06)]";
  if (state === "BEAR") return "border-[oklch(0.85_0.12_28_/_0.3)] bg-[oklch(0.85_0.12_28_/_0.07)]";
  if (state === "CORRECTION") return "border-[oklch(0.9_0.06_75_/_0.3)] bg-[oklch(0.9_0.06_75_/_0.06)]";
  return "border-white/10 bg-white/4";
}

function RegimeCard({ regime, market }: { regime: MarketRegime | null; market: string }) {
  if (!regime) {
    return (
      <div className="surface-panel rounded-[1.65rem] px-5 py-5">
        <div className="tiny-label">{market} Market</div>
        <div className="mt-3 text-sm text-quiet">No regime data available.</div>
      </div>
    );
  }

  return (
    <div className={cn("rounded-[1.65rem] border px-5 py-5", regimeBg(regime.state))}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="tiny-label">{market} Market</div>
          <div className={cn("mt-2 font-heading text-4xl uppercase tracking-[0.04em]", regimeColor(regime.state))}>
            {regime.state}
          </div>
          {regime.prior_state && (
            <div className="mt-1 text-xs text-faint">
              Prior: {regime.prior_state}
            </div>
          )}
        </div>
        <div className="text-right text-xs text-faint">
          <div>Since {regime.effective_date}</div>
          {regime.follow_through_day && (
            <div className="mt-1 text-[oklch(0.92_0.04_150)] uppercase tracking-widest">
              Follow-through day
            </div>
          )}
        </div>
      </div>

      {regime.trigger_reason && (
        <p className="mt-3 text-sm text-quiet">{regime.trigger_reason}</p>
      )}

      <div className="mt-4 flex flex-wrap gap-4 text-xs">
        {regime.drawdown_from_high != null && (
          <div>
            <span className="text-faint">Drawdown from high </span>
            <span className={regime.drawdown_from_high < -10 ? "text-[oklch(0.85_0.12_28)]" : "text-white"}>
              {(regime.drawdown_from_high * 100).toFixed(1)}%
            </span>
          </div>
        )}
        {regime.distribution_day_count != null && (
          <div>
            <span className="text-faint">Distribution days </span>
            <span className={regime.distribution_day_count >= 5 ? "text-[oklch(0.9_0.06_75)]" : "text-white"}>
              {regime.distribution_day_count}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export function MarketRegimeClient({ initialData }: MarketRegimeClientProps) {
  const { data, isFetching } = useQuery({
    queryKey: ["market-regime-board", 8],
    queryFn: () => fetchMarketRegimeBoard(8),
    initialData: initialData ?? undefined,
    staleTime: 300_000, // regime changes infrequently
  });

  return (
    <div className="app-shell space-y-4 py-4 sm:py-6">
      {/* Header */}
      <div className="surface-panel rounded-[1.65rem] px-5 py-5">
        <div className="tiny-label">Market Regime</div>
        <h1 className="mt-2 font-heading text-4xl uppercase tracking-[0.04em] text-white">
          Regime Dashboard
        </h1>
        {isFetching && <div className="mt-1 text-xs text-faint">Refreshing…</div>}
      </div>

      {/* Current regimes */}
      <div className="grid gap-4 md:grid-cols-2">
        <RegimeCard regime={data?.us ?? null} market="US" />
        <RegimeCard regime={data?.kr ?? null} market="KR" />
      </div>

      {/* History */}
      {(data?.history?.length ?? 0) > 0 && (
        <div className="surface-panel rounded-[1.65rem] px-5 py-5">
          <div className="tiny-label mb-4">Recent History</div>
          <div className="space-y-3">
            {data!.history.map((entry, i) => (
              <div key={i} className="flex items-center gap-4 text-sm">
                <span className="w-6 text-center font-mono text-xs text-faint">
                  {entry.market}
                </span>
                <span className={cn("w-28 uppercase tracking-wide text-xs", regimeColor(entry.state))}>
                  {entry.state}
                </span>
                <span className="text-quiet">{entry.effective_date}</span>
                {entry.trigger_reason && (
                  <span className="flex-1 truncate text-xs text-faint">{entry.trigger_reason}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
