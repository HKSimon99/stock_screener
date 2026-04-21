/**
 * @consensus/ui-tokens — shared design tokens
 *
 * All values expressed in hex / plain numbers so they work in both
 * React Native (StyleSheet / NativeWind) and web (Tailwind / CSS).
 *
 * Web uses the OKLCH equivalents via globals.css CSS custom properties;
 * mobile consumes these hex values directly.
 *
 * Hex values are faithful approximations of the OKLCH originals.
 */

// ── Conviction ────────────────────────────────────────────────────────────────

export type ConvictionLevel =
  | "DIAMOND"
  | "PLATINUM"
  | "GOLD"
  | "SILVER"
  | "BRONZE"
  | "UNRANKED";

/** Hex text colours for each conviction level (both web + mobile). */
export const CONVICTION_COLORS: Record<ConvictionLevel, string> = {
  DIAMOND:  "#a5f3fc",  // cyan-200
  PLATINUM: "#e9d5ff",  // violet-200
  GOLD:     "#fde68a",  // amber-200
  SILVER:   "#e2e8f0",  // slate-200
  BRONZE:   "#fed7aa",  // orange-200
  UNRANKED: "#94a3b8",  // slate-400
};

/** Tailwind bg+text class pairs for the web conviction badge. */
export const CONVICTION_TAILWIND_BG: Record<ConvictionLevel, string> = {
  DIAMOND:  "bg-cyan-200 text-cyan-900",
  PLATINUM: "bg-violet-200 text-violet-900",
  GOLD:     "bg-amber-200 text-amber-900",
  SILVER:   "bg-slate-200 text-slate-700",
  BRONZE:   "bg-orange-200 text-orange-900",
  UNRANKED: "bg-slate-100 text-slate-500",
};

// ── Regime ────────────────────────────────────────────────────────────────────

export type RegimeState =
  | "CONFIRMED_UPTREND"
  | "UPTREND_UNDER_PRESSURE"
  | "MARKET_IN_CORRECTION";

export const REGIME_COLORS: Record<RegimeState, string> = {
  CONFIRMED_UPTREND:         "#4ade80",  // green-400
  UPTREND_UNDER_PRESSURE:    "#facc15",  // yellow-400
  MARKET_IN_CORRECTION:      "#f87171",  // red-400
};

// ── Palette ───────────────────────────────────────────────────────────────────
//
// Hex approximations of the web globals.css OKLCH palette.
// Used directly in React Native StyleSheet and NativeWind tailwind.config.js.

export const COLORS = {
  // ── Surfaces (dark theme) ──────────────────────────────────────────────────
  // Web equiv: --surface-0 … --surface-3
  surface0:  "#10121c",   // oklch(0.145 0.012 250) — page/app background
  surface1:  "#161925",   // oklch(0.19 0.017 248)  — base panel
  surface2:  "#1c1f2e",   // oklch(0.235 0.02 248)  — elevated panel
  surface3:  "#23263a",   // oklch(0.285 0.025 248)  — top-level card

  // ── Text ───────────────────────────────────────────────────────────────────
  // Web equiv: --foreground, --text-quiet, --text-faint
  foreground: "#f4f3ee",  // oklch(0.95 0.012 92)  — primary text
  textQuiet:  "#b4b2a5",  // oklch(0.72 0.015 88)  — secondary text
  textFaint:  "#8a897d",  // oklch(0.56 0.014 92)  — placeholder / labels

  // ── Brand ──────────────────────────────────────────────────────────────────
  // Web equiv: --primary (amber accent)
  primary:    "#cfb041",  // oklch(0.8 0.118 84)   — amber/gold accent
  primaryFg:  "#181610",  // oklch(0.16 0.01 248)  — text on primary bg

  // Web equiv: --accent (cyan)
  accent:     "#64c4b9",  // oklch(0.78 0.075 184) — cyan accent
  accentFg:   "#10181a",  // oklch(0.16 0.012 248) — text on accent bg

  // ── Borders ────────────────────────────────────────────────────────────────
  // Web equiv: --border
  border:     "#2d3045",  // oklch(0.33 0.022 248) — default border
  borderSoft: "#1e2030",  // slightly subtler

  // ── Signal / semantic ──────────────────────────────────────────────────────
  // Web equiv: --signal-*
  emerald:    "#51c96a",  // oklch(0.77 0.145 150) — positive / uptrend
  amber:      "#f5c543",  // oklch(0.82 0.155 78)  — warning
  crimson:    "#e8503e",  // oklch(0.68 0.185 28)  — danger / correction
  bronze:     "#c07040",  // oklch(0.68 0.12 58)   — bronze conviction
  silver:     "#b0b8cc",  // oklch(0.75 0.025 240) — silver conviction
  diamond:    "#76d4ca",  // oklch(0.82 0.1 196)   — diamond conviction

  // ── Conviction aliases (for NativeWind token convenience) ─────────────────
  convictionDiamond:  "#a5f3fc",
  convictionPlatinum: "#e9d5ff",
  convictionGold:     "#fde68a",
  convictionSilver:   "#e2e8f0",
  convictionBronze:   "#fed7aa",
  convictionUnranked: "#94a3b8",
} as const;

// ── Radius ────────────────────────────────────────────────────────────────────
//
// Matches the web --radius scale. Values in logical pixels.
// Web: --radius: 1rem → 16px base; scaled variants below.

export const RADIUS = {
  sm:   10,   // --radius-sm  ≈ 0.6rem
  md:   13,   // --radius-md  ≈ 0.8rem
  lg:   16,   // --radius-lg  = 1rem   (base)
  xl:   22,   // --radius-xl  ≈ 1.35rem
  "2xl": 29,  // --radius-2xl ≈ 1.8rem
  "3xl": 36,  // used by large panels
  full: 9999,
} as const;

// ── Typography ────────────────────────────────────────────────────────────────

export const FONT_SIZE = {
  "2xs": 10,
  xs:    12,
  sm:    13,
  base:  15,
  lg:    17,
  xl:    20,
  "2xl": 24,
  "3xl": 30,
  "4xl": 36,
  "5xl": 48,
} as const;

export const FONT_WEIGHT = {
  normal:    "400",
  medium:    "500",
  semibold:  "600",
  bold:      "700",
} as const;

// ── Spacing ───────────────────────────────────────────────────────────────────
//
// 4px base unit — same grid as Tailwind's default spacing scale.

export const SPACING = {
  0:    0,
  0.5:  2,
  1:    4,
  1.5:  6,
  2:    8,
  2.5:  10,
  3:    12,
  3.5:  14,
  4:    16,
  5:    20,
  6:    24,
  7:    28,
  8:    32,
  9:    36,
  10:   40,
  12:   48,
  14:   56,
  16:   64,
} as const;

// ── Score thresholds ──────────────────────────────────────────────────────────

export const SCORE_THRESHOLDS = {
  HIGH:   70,
  MEDIUM: 40,
  LOW:    0,
} as const;

// ── Misc ──────────────────────────────────────────────────────────────────────

export const APP_NAME = "Consensus";
export const API_DEFAULT_BASE_URL = "http://localhost:8000/api/v1";
