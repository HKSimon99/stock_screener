"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRightLeft,
  ShieldCheck,
  ShieldX,
} from "lucide-react";
import {
  fetchMarketRegime,
  formatSnapshotDate,
  type MarketRegime,
  type RegimeState,
} from "@/lib/api";

interface RegimeBannerProps {
  market: "US" | "KR";
}

const REGIME_CONFIG: Record<
  RegimeState,
  {
    title: string;
    shell: string;
    eyebrow: string;
    icon: typeof ShieldCheck;
  }
> = {
  CONFIRMED_UPTREND: {
    title: "Confirmed Uptrend",
    shell:
      "border-[oklch(0.77_0.145_150_/_0.34)] bg-[oklch(0.32_0.06_150_/_0.18)] text-[oklch(0.92_0.04_150)]",
    eyebrow: "Risk budget open",
    icon: ShieldCheck,
  },
  UPTREND_UNDER_PRESSURE: {
    title: "Uptrend Under Pressure",
    shell:
      "border-[oklch(0.82_0.15_78_/_0.38)] bg-[oklch(0.36_0.055_78_/_0.18)] text-[oklch(0.94_0.04_88)]",
    eyebrow: "Reduce size, demand confirmation",
    icon: AlertTriangle,
  },
  MARKET_IN_CORRECTION: {
    title: "Market In Correction",
    shell:
      "border-[oklch(0.68_0.18_28_/_0.4)] bg-[oklch(0.31_0.06_28_/_0.18)] text-[oklch(0.9_0.04_24)]",
    eyebrow: "Capital preservation mode",
    icon: ShieldX,
  },
};

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-white/8 bg-black/10 px-3 py-2">
      <div className="tiny-label">{label}</div>
      <div className="mt-1 text-sm font-medium text-current">{value}</div>
    </div>
  );
}

function RegimeBannerContent({ regime }: { regime: MarketRegime }) {
  const config = REGIME_CONFIG[regime.state];
  const Icon = config.icon;

  return (
    <section className={`surface-panel overflow-hidden ${config.shell}`}>
      <div className="grid gap-4 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:px-5">
        <div className="flex items-start gap-3">
          <div className="flex size-11 shrink-0 items-center justify-center rounded-2xl border border-white/12 bg-black/12">
            <Icon className="size-5" />
          </div>
          <div className="space-y-2">
            <div className="tiny-label text-current/70">{config.eyebrow}</div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-heading text-2xl uppercase tracking-[0.04em]">
                {regime.market} {config.title}
              </h2>
              {regime.prior_state && (
                <span className="inline-flex items-center gap-1 rounded-full border border-white/12 bg-black/10 px-2.5 py-1 text-[0.68rem] font-medium uppercase tracking-[0.16em] text-current/80">
                  <ArrowRightLeft className="size-3" />
                  From {regime.prior_state.replaceAll("_", " ")}
                </span>
              )}
            </div>
            <p className="max-w-3xl text-sm leading-6 text-current/78">
              {regime.trigger_reason ??
                "No explicit trigger reason was provided by the backend for this state change."}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:min-w-[30rem]">
          <Metric
            label="Effective"
            value={formatSnapshotDate(regime.effective_date)}
          />
          <Metric
            label="Distribution"
            value={`${regime.distribution_day_count ?? 0} days`}
          />
          <Metric
            label="Drawdown"
            value={
              regime.drawdown_from_high != null
                ? `${regime.drawdown_from_high.toFixed(1)}%`
                : "n/a"
            }
          />
          <Metric
            label="Follow Through"
            value={regime.follow_through_day ? "Confirmed" : "No"}
          />
        </div>
      </div>
    </section>
  );
}

export function RegimeBanner({ market }: RegimeBannerProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["market-regime", market],
    queryFn: () => fetchMarketRegime(market),
  });

  if (isLoading) {
    return <div className="surface-panel h-32 animate-pulse" />;
  }

  if (isError || !data) {
    return (
      <section className="surface-panel px-4 py-4 text-sm text-faint">
        Market regime data is unavailable right now.
      </section>
    );
  }

  return <RegimeBannerContent regime={data} />;
}
