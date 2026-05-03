import { cn } from "@/lib/utils";
import type { ConvictionLevel } from "@/lib/api";

/**
 * ConvictionBadge — Revolut badge-feature token.
 *
 * Colours are sourced from the signal CSS variables defined in globals.css:
 *   --signal-diamond  #a5f3fc  (cyan-200)
 *   --signal-platinum #c4b5fd  (violet-300)
 *   --signal-gold     #fcd34d  (amber-300)
 *   --signal-silver   #cbd5e1  (slate-300)
 *   --signal-bronze   #fdba74  (orange-300)
 *   --signal-unranked #64748b  (slate-500)
 *
 * Shape: pill (border-radius 9999px), 1px border at 35% alpha of the signal
 * colour, background at 12% alpha, text is the signal colour itself.
 * No drop shadows — Revolut elevation is colour-block only.
 */

interface ConvictionBadgeProps {
  level: ConvictionLevel;
  size?: "sm" | "md";
}

const CONVICTION_CONFIG: Record<
  ConvictionLevel,
  {
    colorVar: string;        // CSS variable for the signal colour
    bgAlpha: string;         // rgba for background
    borderAlpha: string;     // rgba for border
    label: string;
    detail: string;
  }
> = {
  DIAMOND: {
    colorVar:    "var(--signal-diamond)",
    bgAlpha:     "rgba(165,243,252,0.10)",
    borderAlpha: "rgba(165,243,252,0.28)",
    label:       "Diamond",
    detail:      "Top-tier alignment",
  },
  PLATINUM: {
    colorVar:    "var(--signal-platinum)",
    bgAlpha:     "rgba(196,181,253,0.10)",
    borderAlpha: "rgba(196,181,253,0.28)",
    label:       "Platinum",
    detail:      "Elite prospects",
  },
  GOLD: {
    colorVar:    "var(--signal-gold)",
    bgAlpha:     "rgba(252,211,77,0.10)",
    borderAlpha: "rgba(252,211,77,0.28)",
    label:       "Gold",
    detail:      "Actionable setup",
  },
  SILVER: {
    colorVar:    "var(--signal-silver)",
    bgAlpha:     "rgba(203,213,225,0.10)",
    borderAlpha: "rgba(203,213,225,0.24)",
    label:       "Silver",
    detail:      "Promising watch",
  },
  BRONZE: {
    colorVar:    "var(--signal-bronze)",
    bgAlpha:     "rgba(253,186,116,0.10)",
    borderAlpha: "rgba(253,186,116,0.24)",
    label:       "Bronze",
    detail:      "Developing case",
  },
  UNRANKED: {
    colorVar:    "var(--signal-unranked)",
    bgAlpha:     "rgba(100,116,139,0.10)",
    borderAlpha: "rgba(100,116,139,0.20)",
    label:       "Unranked",
    detail:      "Below threshold",
  },
};

export function ConvictionBadge({ level, size = "md" }: ConvictionBadgeProps) {
  const config = CONVICTION_CONFIG[level];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium uppercase",
        size === "sm"
          ? "px-2.5 py-1 text-[0.62rem] tracking-[0.14em]"
          : "px-3 py-1.5 text-[0.68rem] tracking-[0.16em]"
      )}
      style={{
        background:  config.bgAlpha,
        borderColor: config.borderAlpha,
        color:       config.colorVar,
      }}
      title={config.detail}
    >
      {/* Signal dot */}
      <span
        aria-hidden="true"
        style={{
          display:      "inline-block",
          width:        6,
          height:       6,
          borderRadius: "50%",
          background:   config.colorVar,
          flexShrink:   0,
        }}
      />
      <span>{config.label}</span>
    </span>
  );
}
