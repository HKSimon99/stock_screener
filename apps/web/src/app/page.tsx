"use client";

import Link from "next/link";
import { ArrowRight, BarChart3, Bell, Search, ShieldCheck, Sparkles } from "lucide-react";
import { SiteChrome } from "@/components/site-chrome";
import { useT } from "@/hooks/use-t";

const FEATURE_ICONS = [Search, ShieldCheck, BarChart3, Bell] as const;

export default function Home() {
  const { t } = useT();

  const features = [
    { icon: FEATURE_ICONS[0], titleKey: "home.features.search.title", bodyKey: "home.features.search.body" },
    { icon: FEATURE_ICONS[1], titleKey: "home.features.coverage.title", bodyKey: "home.features.coverage.body" },
    { icon: FEATURE_ICONS[2], titleKey: "home.features.chart.title", bodyKey: "home.features.chart.body" },
    { icon: FEATURE_ICONS[3], titleKey: "home.features.regime.title", bodyKey: "home.features.regime.body" },
  ] as const;

  const stats = [
    { labelKey: "home.stats.universe.label", valueKey: "home.stats.universe.value", subKey: "home.stats.universe.sub" },
    { labelKey: "home.stats.strategies.label", valueKey: "home.stats.strategies.value", subKey: "home.stats.strategies.sub" },
    { labelKey: "home.stats.data.label", valueKey: "home.stats.data.value", subKey: "home.stats.data.sub" },
  ] as const;

  return (
    <div className="min-h-screen pb-16">
      <SiteChrome />

      <main>
        <section className="app-shell grid min-h-[calc(100svh-4rem)] items-center gap-8 py-10 lg:grid-cols-[minmax(0,0.9fr)_minmax(24rem,0.78fr)] lg:gap-14 lg:py-14">
          <div className="animate-rise">
            <div className="inline-flex items-center gap-2 rounded-full border border-[rgba(15,23,42,0.1)] bg-white/80 px-3 py-2 text-[0.72rem] font-bold uppercase tracking-[0.14em] text-[var(--rv-mute)]">
              <Sparkles className="size-3.5 text-[var(--rv-teal)]" />
              {t("home.kicker")}
            </div>
            <h1 className="mt-6 max-w-[11ch] font-heading text-[clamp(3.2rem,7vw,6.2rem)] font-bold uppercase leading-[0.95] text-[var(--rv-ink)]">
              {t("home.headline1")}{" "}
              <span className="text-[var(--rv-mute)]">{t("home.headline2")}</span>
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-8 text-[var(--rv-mute)] sm:text-lg">
              {t("home.sub")}
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link href="/rankings" transitionTypes={["nav-forward"]} className="btn-primary">
                {t("home.cta.app")}
                <ArrowRight className="size-4" />
              </Link>
              <Link href="/methodology" className="btn-outline">
                {t("home.cta.methodology")}
              </Link>
            </div>
          </div>

          <div className="animate-rise surface-panel rounded-2xl p-4 sm:p-5" style={{ animationDelay: "120ms" }}>
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <div className="tiny-label">Live research desk</div>
                <div className="mt-1 font-heading text-2xl font-bold uppercase text-white">US leaderboard</div>
              </div>
              <span className="rounded-full bg-[rgba(15,186,157,0.14)] px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-[oklch(0.84_0.1_175)]">
                ranked
              </span>
            </div>
            <div className="space-y-2">
              {[
                ["#1", "NVDA", "92", "Diamond"],
                ["#2", "MSFT", "88", "Platinum"],
                ["#3", "AAPL", "81", "Gold"],
              ].map(([rank, ticker, score, level]) => (
                <div key={ticker} className="motion-card rounded-xl border border-white/8 bg-white/[0.06] p-4">
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm text-faint">{rank}</span>
                        <span className="font-heading text-2xl font-bold uppercase text-white">{ticker}</span>
                      </div>
                      <div className="mt-1 text-xs uppercase tracking-[0.16em] text-faint">{level} conviction</div>
                    </div>
                    <div className="font-mono text-3xl font-bold text-[oklch(0.82_0.1_175)]">{score}</div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2">
              {stats.map((stat) => (
                <div key={stat.labelKey} className="rounded-xl border border-white/8 bg-white/[0.05] p-3">
                  <div className="text-xs font-bold uppercase tracking-[0.08em] text-faint">{t(stat.labelKey)}</div>
                  <div className="mt-2 font-heading text-xl font-bold text-white">{t(stat.valueKey)}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="app-shell py-10">
          <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="section-kicker">{t("home.features.kicker")}</div>
              <h2 className="mt-2 font-heading text-3xl font-bold uppercase text-[var(--rv-ink)] sm:text-5xl">
                {t("home.features.headline")}
              </h2>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <article key={feature.titleKey} className="motion-card metric-tile">
                  <div className="flex size-11 items-center justify-center rounded-xl bg-[rgba(15,186,157,0.12)] text-[#075e54]">
                    <Icon className="size-5" />
                  </div>
                  <h3 className="mt-4 font-heading text-xl font-bold text-[var(--rv-ink)]">{t(feature.titleKey)}</h3>
                  <p className="mt-2 text-sm leading-6 text-[var(--rv-mute)]">{t(feature.bodyKey)}</p>
                </article>
              );
            })}
          </div>
        </section>
      </main>
    </div>
  );
}
