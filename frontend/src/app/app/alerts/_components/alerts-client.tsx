"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Bell, Info, Zap } from "lucide-react";
import { buildInstrumentPath, fetchAlerts, type Alert, type AlertsResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

interface AlertsClientProps {
  initialData: AlertsResponse | null;
}

function severityIcon(severity: Alert["severity"]) {
  if (severity === "CRITICAL") return <Zap className="size-4 shrink-0 text-[oklch(0.85_0.12_28)]" />;
  if (severity === "WARNING") return <AlertTriangle className="size-4 shrink-0 text-[oklch(0.9_0.06_75)]" />;
  return <Info className="size-4 shrink-0 text-faint" />;
}

function severityBorder(severity: Alert["severity"]): string {
  if (severity === "CRITICAL") return "border-l-[oklch(0.85_0.12_28_/_0.5)]";
  if (severity === "WARNING") return "border-l-[oklch(0.9_0.06_55_/_0.5)]";
  return "border-l-white/10";
}

function relativeTime(iso: string): string {
  const delta = Date.now() - new Date(iso).getTime();
  const h = Math.floor(delta / 3600000);
  if (h < 1) return `${Math.floor(delta / 60000)}m ago`;
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function AlertsClient({ initialData }: AlertsClientProps) {
  const { data, isFetching } = useQuery({
    queryKey: ["alerts", 30, 100],
    queryFn: () => fetchAlerts({ days: 30, limit: 100 }),
    initialData: initialData ?? undefined,
    staleTime: 60_000,
  });

  const critical = data?.items.filter((a) => a.severity === "CRITICAL") ?? [];
  const warnings = data?.items.filter((a) => a.severity === "WARNING") ?? [];
  const info = data?.items.filter((a) => a.severity === "INFO") ?? [];

  return (
    <div className="app-shell space-y-4 py-4 sm:py-6">
      {/* Header */}
      <div className="surface-panel rounded-[1.65rem] px-5 py-5">
        <div className="tiny-label">Alert Centre</div>
        <h1 className="mt-2 font-heading text-4xl uppercase tracking-[0.04em] text-white">
          Active Alerts
        </h1>
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-faint">
          <span>{data?.critical ?? 0} critical</span>
          <span>{data?.warnings ?? 0} warnings</span>
          <span>{data?.total ?? 0} total</span>
          {isFetching && <span>· refreshing…</span>}
        </div>
      </div>

      {/* Empty state */}
      {data?.items.length === 0 && (
        <div className="surface-panel flex flex-col items-center gap-3 rounded-[1.65rem] px-5 py-12 text-center">
          <Bell className="size-8 text-faint/40" />
          <div className="text-sm text-quiet">No alerts in the past 30 days.</div>
        </div>
      )}

      {/* Alert groups */}
      {[
        { label: "Critical", items: critical },
        { label: "Warnings", items: warnings },
        { label: "Info", items: info },
      ]
        .filter((g) => g.items.length > 0)
        .map((group) => (
          <section key={group.label}>
            <div className="mb-2 px-1 text-[0.68rem] uppercase tracking-widest text-faint">
              {group.label}
            </div>
            <div className="space-y-2">
              {group.items.map((alert) => (
                <div
                  key={alert.id}
                  className={cn(
                    "surface-panel rounded-[1.45rem] border-l-4 px-5 py-4",
                    severityBorder(alert.severity)
                  )}
                >
                  <div className="flex items-start gap-3">
                    {severityIcon(alert.severity)}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-white">
                          {alert.title ?? alert.alert_type.replace(/_/g, " ")}
                        </span>
                        {alert.ticker && alert.market && (
                          <Link
                            href={buildInstrumentPath(alert.ticker, alert.market)}
                            className="rounded-full border border-white/10 px-2 py-0.5 text-[0.65rem] uppercase tracking-widest text-faint transition-colors hover:text-white"
                          >
                            {alert.market} {alert.ticker}
                          </Link>
                        )}
                      </div>
                      {alert.detail && (
                        <p className="mt-1 text-xs text-quiet">{alert.detail}</p>
                      )}
                      {(alert.threshold_value != null || alert.actual_value != null) && (
                        <div className="mt-1 text-xs text-faint">
                          {alert.threshold_value != null && `Threshold: ${alert.threshold_value}`}
                          {alert.threshold_value != null && alert.actual_value != null && " · "}
                          {alert.actual_value != null && `Actual: ${alert.actual_value.toFixed(2)}`}
                        </div>
                      )}
                    </div>
                    <div className="shrink-0 text-xs text-faint">{relativeTime(alert.created_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
    </div>
  );
}
