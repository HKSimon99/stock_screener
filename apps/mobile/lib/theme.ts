export const FONTS = {
  headingBold: "SpaceGrotesk_700Bold",
  headingSemiBold: "SpaceGrotesk_600SemiBold",
  headingMedium: "SpaceGrotesk_500Medium",
  monoRegular: "JetBrainsMono_400Regular",
  monoMedium: "JetBrainsMono_500Medium",
  monoSemiBold: "JetBrainsMono_600SemiBold",
  serif: "InstrumentSerif_400Regular",
} as const;

export const THEMES = {
  dark: {
    bg0: "#0e1116",
    bg1: "rgba(34,38,48,0.92)",
    bg2: "rgba(42,48,60,0.94)",
    bg3: "rgba(50,56,72,0.6)",
    panel: "rgba(38,44,57,0.96)",
    panelAlt: "rgba(44,51,66,0.92)",
    line: "rgba(140,145,165,0.22)",
    lineSoft: "rgba(140,145,165,0.14)",
    text: "#f4f2ec",
    quiet: "rgba(205,205,200,0.78)",
    faint: "rgba(160,160,160,0.58)",
    primary: "#e8b867",
    primaryDim: "rgba(232,184,103,0.18)",
    primaryLine: "rgba(232,184,103,0.42)",
    accent: "#8cd9cf",
    green: "#74d39b",
    amber: "#e8bc4f",
    red: "#e78576",
    conviction: {
      DIAMOND: { bg: "rgba(140,217,207,0.14)", line: "rgba(140,217,207,0.4)", text: "#a5e8df" },
      PLATINUM: { bg: "rgba(192,160,240,0.14)", line: "rgba(192,160,240,0.4)", text: "#c8aef0" },
      GOLD: { bg: "rgba(232,188,79,0.14)", line: "rgba(232,188,79,0.42)", text: "#e8c874" },
      SILVER: { bg: "rgba(190,195,210,0.12)", line: "rgba(190,195,210,0.32)", text: "#c6cad5" },
      BRONZE: { bg: "rgba(220,145,100,0.14)", line: "rgba(220,145,100,0.4)", text: "#e5a78a" },
      UNRANKED: { bg: "rgba(120,125,140,0.1)", line: "rgba(120,125,140,0.22)", text: "#8a8d95" },
    },
    chartFill: "rgba(232,184,103,0.14)",
    chartLine: "#e8b867",
    shadow: "rgba(0,0,0,0.28)",
  },
  light: {
    bg0: "#f6f3ec",
    bg1: "rgba(255,255,255,0.88)",
    bg2: "#ffffff",
    bg3: "rgba(245,240,230,0.8)",
    panel: "#ffffff",
    panelAlt: "#fbf8f1",
    line: "rgba(30,25,20,0.1)",
    lineSoft: "rgba(30,25,20,0.06)",
    text: "#1a1612",
    quiet: "rgba(60,52,42,0.78)",
    faint: "rgba(80,72,60,0.5)",
    primary: "#a8731e",
    primaryDim: "rgba(168,115,30,0.12)",
    primaryLine: "rgba(168,115,30,0.4)",
    accent: "#2f8376",
    green: "#2d8856",
    amber: "#a67e1f",
    red: "#b84b38",
    conviction: {
      DIAMOND: { bg: "rgba(47,131,118,0.12)", line: "rgba(47,131,118,0.4)", text: "#1f6b5e" },
      PLATINUM: { bg: "rgba(119,86,183,0.12)", line: "rgba(119,86,183,0.38)", text: "#563a99" },
      GOLD: { bg: "rgba(168,115,30,0.14)", line: "rgba(168,115,30,0.42)", text: "#7d530b" },
      SILVER: { bg: "rgba(85,90,110,0.1)", line: "rgba(85,90,110,0.26)", text: "#474a55" },
      BRONZE: { bg: "rgba(168,90,45,0.12)", line: "rgba(168,90,45,0.38)", text: "#83411a" },
      UNRANKED: { bg: "rgba(120,120,120,0.08)", line: "rgba(120,120,120,0.2)", text: "#787878" },
    },
    chartFill: "rgba(168,115,30,0.14)",
    chartLine: "#a8731e",
    shadow: "rgba(28,24,18,0.08)",
  },
} as const;

export type AppThemeName = keyof typeof THEMES;
export type AppTheme = (typeof THEMES)[AppThemeName];

export const SPACING = {
  screen: 20,
  card: 16,
  gap: 12,
  radius: 20,
  pill: 999,
} as const;

export function getTheme(name?: AppThemeName): AppTheme {
  return THEMES[name ?? "dark"] ?? THEMES.dark;
}

