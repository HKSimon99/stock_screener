/**
 * Shared design tokens — conviction colours, regime colours, score thresholds.
 * Used by both web (Tailwind class names) and mobile (React Native StyleSheet).
 */

export type ConvictionLevel = "DIAMOND" | "GOLD" | "SILVER" | "BRONZE" | "UNRANKED";

/** Hex colours for each conviction level. */
export const CONVICTION_COLORS: Record<ConvictionLevel, string> = {
  DIAMOND: "#a5f3fc", // cyan-200
  GOLD: "#fde68a",    // amber-200
  SILVER: "#e2e8f0",  // slate-200
  BRONZE: "#fed7aa",  // orange-200
  UNRANKED: "#94a3b8", // slate-400
};

/** Tailwind bg-class names for the web app badge. */
export const CONVICTION_TAILWIND_BG: Record<ConvictionLevel, string> = {
  DIAMOND: "bg-cyan-200 text-cyan-900",
  GOLD: "bg-amber-200 text-amber-900",
  SILVER: "bg-slate-200 text-slate-700",
  BRONZE: "bg-orange-200 text-orange-900",
  UNRANKED: "bg-slate-100 text-slate-500",
};

export type RegimeState =
  | "CONFIRMED_UPTREND"
  | "UPTREND_UNDER_PRESSURE"
  | "MARKET_IN_CORRECTION";

export const REGIME_COLORS: Record<RegimeState, string> = {
  CONFIRMED_UPTREND: "#4ade80",        // green-400
  UPTREND_UNDER_PRESSURE: "#facc15",   // yellow-400
  MARKET_IN_CORRECTION: "#f87171",     // red-400
};

/** Score thresholds for rendering gauge indicators. */
export const SCORE_THRESHOLDS = {
  HIGH: 70,
  MEDIUM: 40,
  LOW: 0,
} as const;

export const APP_NAME = "Consensus";
export const API_DEFAULT_BASE_URL = "http://localhost:8000/api/v1";
