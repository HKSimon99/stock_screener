"use client";

/**
 * RankingRow — Revolut surface-elevated card.
 *
 * Revolut rules applied:
 *  - surface-panel token (#16181a bg, 1px hairline-dark border, radius-lg)
 *  - No drop shadows — elevation is colour-block only
 *  - Score bar uses rv-primary (#494fdf) at 55% alpha
 *  - Pin pill uses btn-pill-sm token (active = rv-primary bg)
 *  - Conviction inline text uses signal CSS variables
 *  - Rank number is font-mono text-faint (rv-stone)
 */

import Link from "next/link";
import { Pin } from "lucide-react";
import { buildInstrumentPath } from "@/lib/api";
import { useUIStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { SparklineChart } from "@/components/sparkline-chart";

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

/** Map conviction level to its signal CSS variable (defined in globals.css) */
function convictionColor(level: string): string {
  const map: Record<string, string> = {
    DIAMOND:  "var(--signal-diamond)",
    PLATINUM: "var(--signal-platinum)",
    GOLD:     "var(--signal-gold)",
    SILVER:   "var(--signal-silver)",
    BRONZE:   "var(--signal-bronze)",
    UNRANKED: "var(--signal-unranked)",
  };
  return map[level] ?? "var(--rv-stone)";
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, score)).toFixed(0);
  return (
    <div
      style={{
        position:     "relative",
        marginTop:    4,
        height:       3,
        width:        96,
        borderRadius: 9999,
        background:   "rgba(255,255,255,0.07)",
        overflow:     "hidden",
      }}
    >
      <div
        style={{
          position:     "absolute",
          insetBlock:   0,
          left:         0,
          borderRadius: 9999,
          background:   "rgba(73,79,223,0.55)",
          width:        `${pct}%`,
          transition:   "width 300ms ease",
        }}
      />
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

interface RankingRowProps {
  item: RankingRowData;
  showPin?: boolean;
}

export function RankingRow({ item, showPin = true }: RankingRowProps) {
  const togglePinned = useUIStore((state) => state.togglePinnedInstrument);
  const isPinned     = useUIStore((state) => state.isPinned);
  const pinned       = isPinned(item.ticker, item.market);

  return (
    <div
      className="surface-panel"
      style={{
        borderRadius: "var(--radius-lg)",   /* 20px */
        padding:      "var(--sp-lg)",       /* 16px */
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>

        {/* ── Rank ─────────────────────────────────────────────────────── */}
        <div
          className="font-mono"
          style={{
            width:        36,
            flexShrink:   0,
            textAlign:    "right",
            fontSize:     "1.0625rem",
            color:        "var(--rv-stone)",
            lineHeight:   1,
            paddingTop:   4,
          }}
        >
          {item.rank}
        </div>

        {/* ── Name + meta ──────────────────────────────────────────────── */}
        <div style={{ minWidth: 0, flex: 1 }}>
          <Link
            href={buildInstrumentPath(item.ticker, item.market)}
            style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}
          >
            <span
              className="font-heading text-white"
              style={{
                fontSize:       "1.375rem",
                fontWeight:     600,
                textTransform:  "uppercase",
                letterSpacing:  "-0.01em",
              }}
            >
              {item.ticker}
            </span>
            {item.exchange && (
              <span
                style={{
                  borderRadius: 9999,
                  border:       "1px solid rgba(255,255,255,0.10)",
                  padding:      "2px 8px",
                  fontSize:     "0.625rem",
                  textTransform: "uppercase",
                  letterSpacing: "0.14em",
                  color:        "var(--rv-stone)",
                }}
              >
                {item.market} / {item.exchange}
              </span>
            )}
          </Link>

          {item.name && (
            <div
              style={{
                marginTop:    2,
                fontSize:     "0.875rem",
                color:        "var(--rv-on-dark-mute)",
                overflow:     "hidden",
                textOverflow: "ellipsis",
                whiteSpace:   "nowrap",
              }}
            >
              {item.name}
            </div>
          )}

          {item.conviction_level && (
            <div
              style={{
                marginTop:     6,
                fontSize:      "0.65rem",
                textTransform: "uppercase",
                letterSpacing: "0.14em",
                color:         convictionColor(item.conviction_level),
                display:       "flex",
                alignItems:    "center",
                gap:           6,
                flexWrap:      "wrap",
              }}
            >
              <span>{item.conviction_level} conviction</span>
              {item.strategy_pass_count != null && (
                <span style={{ color: "var(--rv-stone)" }}>
                  · {item.strategy_pass_count} strategies
                </span>
              )}
              {item.regime_warning && (
                <span style={{ color: "var(--rv-warning)" }}>⚠ regime</span>
              )}
            </div>
          )}
        </div>

        {/* ── Score + sparkline + pin ───────────────────────────────────── */}
        <div
          style={{
            flexShrink:     0,
            display:        "flex",
            flexDirection:  "column",
            alignItems:     "flex-end",
            gap:            8,
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-end", gap: 12 }}>
            <SparklineChart
              ticker={item.ticker}
              market={item.market}
              width={72}
              height={28}
            />
            <div style={{ textAlign: "right" }}>
              <div
                className="font-mono text-white"
                style={{ fontSize: "1.0625rem", lineHeight: 1.2 }}
              >
                {item.final_score.toFixed(1)}
              </div>
              <ScoreBar score={item.final_score} />
            </div>
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
                "btn-pill-sm",
                /* override the default height/padding to keep it compact here */
              )}
              data-active={pinned ? "true" : undefined}
              style={{ height: 30, padding: "0 12px", fontSize: "0.65rem" }}
            >
              <Pin style={{ width: 11, height: 11 }} />
              {pinned ? "Pinned" : "Pin"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
