"use client";

import Link from "next/link";
import { ArrowUpRight, Pin } from "lucide-react";
import { buildInstrumentPath } from "@/lib/api";
import { useUIStore } from "@/lib/store";
import { cn } from "@/lib/utils";

export interface RankingRowData {
  rank: number;
  ticker: string;
  name?: string;
  market: "US" | "KR";
  exchange?: string;
  conviction_level?: string;
  final_score: number;
  strategy_pass_count?: number;
  regime_warning?: boolean;
}

interface RankingRowProps {
  item: RankingRowData;
  showPin?: boolean;
}

function scoreColor(score: number) {
  if (score >= 80) return "text-[oklch(0.58_0.13_175)]";
  if (score >= 65) return "text-[oklch(0.62_0.13_92)]";
  if (score >= 50) return "text-[var(--rv-primary)]";
  return "text-[var(--rv-danger)]";
}

export function RankingRow({ item, showPin = true }: RankingRowProps) {
  const togglePinned = useUIStore((state) => state.togglePinnedInstrument);
  const isPinned = useUIStore((state) => state.isPinned);
  const pinned = isPinned(item.ticker, item.market);
  const score = Math.max(0, Math.min(100, item.final_score));

  return (
    <article className="motion-card group rounded-xl border border-[rgba(15,23,42,0.08)] bg-white p-3 shadow-[0_10px_28px_rgba(15,23,42,0.05)] sm:p-4">
      <div className="grid grid-cols-[2.25rem_minmax(0,1fr)_auto] items-center gap-3">
        <div className="text-right font-mono text-xs font-semibold text-[var(--rv-stone)]">
          #{item.rank}
        </div>

        <Link href={buildInstrumentPath(item.ticker, item.market)} transitionTypes={["nav-forward"]} className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate font-heading text-xl font-bold uppercase text-[var(--rv-ink)] sm:text-2xl">
              {item.ticker}
            </span>
            <ArrowUpRight className="motion-link-arrow size-3.5 shrink-0 text-[var(--rv-stone)] opacity-0 group-hover:opacity-100" />
          </div>
          <div className="mt-0.5 truncate text-sm text-[var(--rv-mute)]">
            {item.name ?? item.exchange ?? item.market}
          </div>
          {(item.conviction_level || item.strategy_pass_count != null || item.regime_warning) && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[0.62rem] font-bold uppercase tracking-[0.12em] text-[var(--rv-stone)]">
              {item.conviction_level && <span>{item.conviction_level}</span>}
              {item.strategy_pass_count != null && <span>{item.strategy_pass_count} strategies</span>}
              {item.regime_warning && <span className="text-[var(--rv-warning)]">regime</span>}
            </div>
          )}
        </Link>

        <div className="flex min-w-[4.5rem] flex-col items-end gap-1">
          <div className={cn("font-mono text-2xl font-bold leading-none tabular-nums", scoreColor(score))}>
            {score.toFixed(score >= 10 ? 0 : 1)}
          </div>
          <div className="h-1 w-16 overflow-hidden rounded-full bg-[var(--rv-surface-soft)]">
            <div
              className="score-bar-fill h-full rounded-full bg-[var(--rv-teal)]"
              style={{ width: `${score}%` }}
            />
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between gap-3 border-t border-[rgba(15,23,42,0.07)] pt-3">
        <div className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--rv-stone)]">
          {item.market}
          {item.exchange ? ` / ${item.exchange}` : ""}
        </div>
        {showPin && (
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
            className="btn-pill-sm min-h-9 px-3 py-1 text-[0.68rem]"
            data-active={pinned ? "true" : undefined}
          >
            <Pin className="size-3" />
            {pinned ? "Pinned" : "Pin"}
          </button>
        )}
      </div>
    </article>
  );
}
