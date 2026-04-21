"use client";

/**
 * RankingRow — shared row component used in both consensus rankings and
 * per-strategy rankings (CANSLIM, Piotroski, Minervini).
 *
 * Accepts a normalized RankingRowData shape so both RankingItem (full
 * consensus data) and StrategyRankingItem (lighter, strategy-specific)
 * can be rendered without separate components.
 */

import Link from "next/link";
import { Pin } from "lucide-react";
import { buildInstrumentPath } from "@/lib/api";
import { useUIStore } from "@/lib/store";
import { cn } from "@/lib/utils";

// ── Shared data shape ─────────────────────────────────────────────────────────

export interface RankingRowData {
  rank: number;
  ticker: string;
  name?: string;
  market: "US" | "KR";
  exchange?: string;
  /** Only present for consensus rankings (not strategy-specific views) */
  conviction_level?: string;
  /** The score to display — final_score for consensus, strategy score otherwise */
  final_score: number;
  /** Strategy pass count from consensus ranking */
  strategy_pass_count?: number;
  /** Whether a regime warning is active */
  regime_warning?: boolean;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function convictionColor(level: string): string {
  const colorMap: Record<string, string> = {
    DIAMOND:  "text-cyan-300",
    PLATINUM: "text-violet-300",
    GOLD:     "text-amber-300",
    SILVER:   "text-slate-300",
    BRONZE:   "text-orange-300",
    UNRANKED: "text-slate-400",
  };
  return colorMap[level] ?? "text-faint";
}

function ScoreBar({ score }: { score: number }) {
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

// ── Component ─────────────────────────────────────────────────────────────────

interface RankingRowProps {
  item: RankingRowData;
  /** Whether to show the pin button (default: true) */
  showPin?: boolean;
}

export function RankingRow({ item, showPin = true }: RankingRowProps) {
  const togglePinned = useUIStore((state) => state.togglePinnedInstrument);
  const isPinned     = useUIStore((state) => state.isPinned);
  const pinned       = isPinned(item.ticker, item.market);

  return (
    <div className="surface-panel rounded-[1.45rem] px-4 py-4 sm:px-5">
      <div className="flex items-start gap-4">
        {/* ── Rank ─────────────────────────────────────────────────────── */}
        <div className="w-10 shrink-0 text-right font-mono text-lg text-faint">
          {item.rank}
        </div>

        {/* ── Name + meta ──────────────────────────────────────────────── */}
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

          {/* Conviction + strategy count — only rendered when conviction is present */}
          {item.conviction_level && (
            <div
              className={cn(
                "mt-1 text-[0.68rem] uppercase tracking-widest",
                convictionColor(item.conviction_level)
              )}
            >
              {item.conviction_level} conviction
              {item.strategy_pass_count != null && ` · ${item.strategy_pass_count} strategies`}
              {item.regime_warning && (
                <span className="ml-2 text-[oklch(0.9_0.06_75)]">⚠ regime</span>
              )}
            </div>
          )}
        </div>

        {/* ── Score + pin ───────────────────────────────────────────────── */}
        <div className="flex shrink-0 flex-col items-end gap-2">
          <div className="text-right">
            <div className="font-mono text-lg text-white">
              {item.final_score.toFixed(1)}
            </div>
            <ScoreBar score={item.final_score} />
          </div>

          {showPin && (
            <button
              type="button"
              onClick={() =>
                togglePinned({
                  ticker:   item.ticker,
                  market:   item.market,
                  name:     item.name ?? item.ticker,
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
          )}
        </div>
      </div>
    </div>
  );
}
