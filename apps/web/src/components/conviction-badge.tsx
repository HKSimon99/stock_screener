import { cn } from "@/lib/utils";
import type { ConvictionLevel } from "@/lib/api";

/**
 * Compact conviction badge using the shared signal tokens in globals.css.
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
        "inline-flex items-center gap-1.5 rounded-full border font-medium uppercase transition-transform duration-150 ease-out group-hover:scale-[1.01]",
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
