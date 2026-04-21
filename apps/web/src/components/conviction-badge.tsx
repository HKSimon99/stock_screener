import { cn } from "@/lib/utils";
import type { ConvictionLevel } from "@/lib/api";

interface ConvictionBadgeProps {
  level: ConvictionLevel;
  size?: "sm" | "md";
}

const CONVICTION_CONFIG: Record<
  ConvictionLevel,
  {
    dot: string;
    shell: string;
    label: string;
    detail: string;
  }
> = {
  DIAMOND: {
    dot: "bg-[oklch(0.84_0.09_196)]",
    shell:
      "border-[oklch(0.84_0.09_196_/_0.45)] bg-[oklch(0.32_0.04_196_/_0.22)] text-[oklch(0.93_0.03_192)]",
    label: "Diamond",
    detail: "Top-tier alignment",
  },
  PLATINUM: {
    dot: "bg-[oklch(0.85_0.06_280)]",
    shell:
      "border-[oklch(0.85_0.06_280_/_0.45)] bg-[oklch(0.35_0.03_280_/_0.22)] text-[oklch(0.92_0.02_275)]",
    label: "Platinum",
    detail: "Elite prospects",
  },
  GOLD: {
    dot: "bg-[oklch(0.82_0.15_78)]",
    shell:
      "border-[oklch(0.82_0.15_78_/_0.42)] bg-[oklch(0.38_0.05_78_/_0.2)] text-[oklch(0.94_0.04_88)]",
    label: "Gold",
    detail: "Actionable setup",
  },
  SILVER: {
    dot: "bg-[oklch(0.78_0.03_235)]",
    shell:
      "border-[oklch(0.78_0.03_235_/_0.3)] bg-[oklch(0.36_0.02_235_/_0.18)] text-[oklch(0.9_0.02_230)]",
    label: "Silver",
    detail: "Promising watch",
  },
  BRONZE: {
    dot: "bg-[oklch(0.72_0.11_58)]",
    shell:
      "border-[oklch(0.72_0.11_58_/_0.35)] bg-[oklch(0.34_0.04_58_/_0.18)] text-[oklch(0.89_0.03_70)]",
    label: "Bronze",
    detail: "Developing case",
  },
  UNRANKED: {
    dot: "bg-[oklch(0.62_0.01_240)]",
    shell:
      "border-[oklch(0.62_0.01_240_/_0.24)] bg-[oklch(0.27_0.015_248_/_0.68)] text-[oklch(0.78_0.012_88)]",
    label: "Unranked",
    detail: "Below threshold",
  },
};

export function ConvictionBadge({ level, size = "md" }: ConvictionBadgeProps) {
  const config = CONVICTION_CONFIG[level];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border font-medium tracking-[0.16em] uppercase",
        config.shell,
        size === "sm" ? "px-2.5 py-1 text-[0.62rem]" : "px-3 py-1.5 text-[0.68rem]"
      )}
      title={config.detail}
    >
      <span className={cn("size-1.5 rounded-full", config.dot)} aria-hidden="true" />
      <span>{config.label}</span>
    </span>
  );
}
