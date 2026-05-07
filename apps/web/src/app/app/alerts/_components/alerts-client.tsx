"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Bell, Info, Zap } from "lucide-react";
import { buildInstrumentPath, fetchAlerts, type Alert, type AlertsResponse } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useT } from "@/hooks/use-t";

interface AlertsClientProps {
  initialData: AlertsResponse | null;
}

function severityIcon(severity: Alert["severity"]) {
  if (severity === "CRITICAL") return <Zap className="size-4 shrink-0 text-[oklch(0.85_0.12_28)]" />;
  if (severity === "WARNING") return <AlertTriangle className="size-4 shrink-0 text-[oklch(0.9_0.06_75)]" />;
  return <Info className="size-4 shrink-0 text-faint" />;
}

function severityTone(severity: Alert["severity"]): string {
  if (severity === "CRITICAL") {
    return "border-[rgba(239,68,68,0.35)] bg-[rgba(239,68,68,0.08)]";
  }
  if (severity === "WARNING") {
    return "border-[rgba(245,158,11,0.34)] bg-[rgba(245,158,11,0.08)]";
  }
  return "border-white/10 bg-white/[0.04]";
}

export function AlertsClient({ initialData }: AlertsClientProps) {
  const { t, lang } = useT();

  const { data, isFetching } = useQuery({
    queryKey: ["alerts", 30, 100],
    queryFn: () => fetchAlerts({ days: 30, limit: 100 }),
    initialData: initialData ?? undefined,
    staleTime: 60_000,
  });

  function relativeTime(iso: string): string {
    const delta = Date.now() - new Date(iso).getTime();
    const h = Math.floor(delta / 3600000);
    if (h < 1) {
      const m = Math.floor(delta / 60000);
      return lang === "ko" ? `${m}${t("alerts.relative.minutes")}` : `${m}${t("alerts.relative.minutes")}`;
    }
    if (h < 24) return `${h}${t("alerts.relative.hours")}`;
    return `${Math.floor(h / 24)}${t("alerts.relative.days")}`;
  }

  const critical = data?.items.filter((a) => a.severity === "CRITICAL") ?? [];
  const warnings = data?.items.filter((a) => a.severity === "WARNING") ?? [];
  const info = data?.items.filter((a) => a.severity === "INFO") ?? [];

  const groups = [
    { label: t("alerts.group.critical"), items: critical },
    { label: t("alerts.group.warnings"), items: warnings },
    { label: t("alerts.group.info"),     items: info },
  ];

  return (
    <div className="app-shell mobile-safe-bottom space-y-4 py-4 sm:py-6">
      {/* Header */}
      <div className="surface-panel rounded-2xl px-5 py-5">
        <div className="tiny-label">{t("alerts.center")}</div>
        <h1 className="mt-2 font-heading text-4xl font-bold uppercase text-white">
          {t("alerts.active")}
        </h1>
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-faint">
          <span>{data?.critical ?? 0} {t("alerts.count.critical")}</span>
          <span>{data?.warnings ?? 0} {t("alerts.count.warnings")}</span>
          <span>{data?.total ?? 0} {t("alerts.count.total")}</span>
          {isFetching && <span>· {t("alerts.refreshing")}</span>}
        </div>
      </div>

      {/* Empty state */}
      {data?.items.length === 0 && (
        <div className="surface-panel flex flex-col items-center gap-3 rounded-2xl px-5 py-12 text-center">
          <Bell className="size-8 text-faint/40" />
          <div className="text-sm text-quiet">{t("alerts.empty")}</div>
        </div>
      )}

      {/* Alert groups */}
      {groups
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
                    "motion-card surface-panel rounded-xl px-5 py-4",
                    severityTone(alert.severity)
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
                            transitionTypes={["nav-forward"]}
                            className="motion-press rounded-full border border-white/10 px-2 py-0.5 text-[0.65rem] uppercase tracking-widest text-faint transition-colors hover:text-white"
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
                          {alert.threshold_value != null && `${t("alerts.threshold")}: ${alert.threshold_value}`}
                          {alert.threshold_value != null && alert.actual_value != null && " · "}
                          {alert.actual_value != null && `${t("alerts.actual")}: ${alert.actual_value.toFixed(2)}`}
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
