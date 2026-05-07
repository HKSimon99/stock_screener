"use client";

import Link from "next/link";
import { ArrowRight, BarChart3, Bell, Database, Search, ShieldCheck, Sparkles, TrendingUp, Zap } from "lucide-react";
import { SiteChrome } from "@/components/site-chrome";
import { useT } from "@/hooks/use-t";

/* ── mock leaderboard data ─────────────────────────────────────── */
const MOCK_RANKED = [
  { rank: 1, ticker: "NVDA", name: "NVIDIA Corp", conviction: "Diamond", score: 92, can: 91, pio: 88, min: 95, wei: 90 },
  { rank: 2, ticker: "MSFT", name: "Microsoft Corp", conviction: "Platinum", score: 88, can: 85, pio: 90, min: 84, wei: 88 },
  { rank: 3, ticker: "AAPL", name: "Apple Inc", conviction: "Gold", score: 81, can: 78, pio: 82, min: 80, wei: 83 },
] as const;

const STRATEGY_LABELS = ["CAN", "PIO", "MIN", "WEI"] as const;

const CONVICTION_COLORS: Record<string, { bg: string; text: string }> = {
  Diamond: { bg: "bg-[oklch(0.55_0.14_245_/_0.22)]", text: "text-[oklch(0.78_0.12_245)]" },
  Platinum: { bg: "bg-[oklch(0.6_0.06_200_/_0.2)]", text: "text-[oklch(0.82_0.05_200)]" },
  Gold:     { bg: "bg-[oklch(0.72_0.12_84_/_0.2)]",  text: "text-[oklch(0.82_0.11_84)]" },
};

function ScoreBar({ value }: { value: number }) {
  return (
    <div className="h-1 w-12 overflow-hidden rounded-full bg-white/10">
      <div
        className="h-full rounded-full bg-[oklch(0.72_0.12_175)]"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

const FEATURE_ICONS = [Search, ShieldCheck, BarChart3, Bell] as const;

const STEPS = [
  {
    icon: Database,
    title: "Ingest",
    body: "We pull price, volume, fundamentals and filings for 6,500+ US and Korean equities every trading day.",
  },
  {
    icon: Zap,
    title: "Score",
    body: "Five independent models — CANSLIM, Piotroski, Minervini, Weinstein and Dual Momentum — grade each name 0–100.",
  },
  {
    icon: TrendingUp,
    title: "Rank",
    body: "A conviction-weighted consensus score surfaces the names where multiple strategies agree. No single-model noise.",
  },
] as const;

export default function Home() {
  const { t } = useT();

  const features = [
    { icon: FEATURE_ICONS[0], titleKey: "home.features.search.title", bodyKey: "home.features.search.body" },
    { icon: FEATURE_ICONS[1], titleKey: "home.features.coverage.title", bodyKey: "home.features.coverage.body" },
    { icon: FEATURE_ICONS[2], titleKey: "home.features.chart.title", bodyKey: "home.features.chart.body" },
    { icon: FEATURE_ICONS[3], titleKey: "home.features.regime.title", bodyKey: "home.features.regime.body" },
  ] as const;

  const stats = [
    { labelKey: "home.stats.universe.label", valueKey: "home.stats.universe.value" },
    { labelKey: "home.stats.strategies.label", valueKey: "home.stats.strategies.value" },
    { labelKey: "home.stats.data.label", valueKey: "home.stats.data.value" },
  ] as const;

  return (
    <div className="min-h-screen">
      <SiteChrome />

      <main>
        {/* ── Hero ─────────────────────────────────────────────── */}
        <section className="app-shell grid min-h-[calc(100svh-4rem)] items-center gap-8 py-10 lg:grid-cols-[minmax(0,0.9fr)_minmax(24rem,0.78fr)] lg:gap-14 lg:py-14">
          {/* left copy */}
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

            {/* inline stats strip */}
            <div className="mt-10 flex flex-wrap gap-6 border-t border-[rgba(15,23,42,0.08)] pt-8">
              {stats.map((s) => (
                <div key={s.labelKey}>
                  <div className="font-heading text-2xl font-bold text-[var(--rv-ink)]">{t(s.valueKey)}</div>
                  <div className="mt-0.5 text-xs font-semibold uppercase tracking-[0.1em] text-[var(--rv-mute)]">{t(s.labelKey)}</div>
                </div>
              ))}
            </div>
          </div>

          {/* right — mock leaderboard panel */}
          <div className="animate-rise surface-panel rounded-2xl p-4 sm:p-5" style={{ animationDelay: "120ms" }}>
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <div className="tiny-label">Live research desk</div>
                <div className="mt-1 font-heading text-2xl font-bold uppercase text-white">US Leaderboard</div>
              </div>
              {/* live pulse */}
              <span className="flex items-center gap-2 rounded-full bg-[rgba(15,186,157,0.14)] px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-[oklch(0.84_0.1_175)]">
                <span className="relative flex size-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[oklch(0.72_0.12_175)] opacity-60" />
                  <span className="relative inline-flex size-2 rounded-full bg-[oklch(0.72_0.12_175)]" />
                </span>
                ranked
              </span>
            </div>

            <div className="space-y-2">
              {MOCK_RANKED.map((item, i) => {
                const cc = CONVICTION_COLORS[item.conviction];
                return (
                  <div
                    key={item.ticker}
                    className="motion-card animate-rise rounded-xl border border-white/8 bg-white/[0.06] p-4"
                    style={{ animationDelay: `${200 + i * 60}ms` }}
                  >
                    <div className="flex items-center gap-4">
                      {/* rank + name */}
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-sm text-faint">#{item.rank}</span>
                          <span className="font-heading text-2xl font-bold uppercase text-white">{item.ticker}</span>
                          <span className={`rounded-full px-2.5 py-0.5 text-[0.67rem] font-bold uppercase tracking-[0.12em] ${cc.bg} ${cc.text}`}>
                            {item.conviction}
                          </span>
                        </div>
                        <div className="mt-2 flex items-center gap-3">
                          {(["can", "pio", "min", "wei"] as const).map((key, ki) => (
                            <div key={key} className="flex flex-col items-center gap-1">
                              <ScoreBar value={item[key]} />
                              <span className="text-[0.6rem] font-bold uppercase tracking-[0.1em] text-faint">
                                {STRATEGY_LABELS[ki]}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                      {/* consensus score */}
                      <div className="shrink-0 font-mono text-3xl font-bold text-[oklch(0.82_0.1_175)]">
                        {item.score}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <Link
              href="/rankings"
              transitionTypes={["nav-forward"]}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 py-3 text-xs font-bold uppercase tracking-[0.12em] text-faint transition-colors hover:border-white/20 hover:text-white"
            >
              View full rankings
              <ArrowRight className="size-3.5" />
            </Link>
          </div>
        </section>

        {/* ── How it works ────────────────────────────────────── */}
        <section className="bg-white py-16 sm:py-20">
          <div className="app-shell">
            <div className="mb-10 text-center">
              <div className="section-kicker">{t("home.features.kicker")}</div>
              <h2 className="mt-3 font-heading text-3xl font-bold uppercase text-[var(--rv-ink)] sm:text-5xl">
                How it works
              </h2>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              {STEPS.map((step, i) => {
                const Icon = step.icon;
                return (
                  <article
                    key={step.title}
                    className="group relative overflow-hidden rounded-2xl border border-[rgba(15,23,42,0.08)] bg-[var(--rv-canvas-light)] p-7 transition-shadow hover:shadow-[0_12px_28px_rgba(15,23,42,0.08)]"
                  >
                    <div className="mb-1 font-mono text-[2.4rem] font-bold leading-none text-[rgba(15,23,42,0.06)]">
                      0{i + 1}
                    </div>
                    <div className="mt-2 flex size-12 items-center justify-center rounded-xl bg-[rgba(37,99,235,0.1)] text-[var(--rv-primary)]">
                      <Icon className="size-5" />
                    </div>
                    <h3 className="mt-5 font-heading text-xl font-bold uppercase text-[var(--rv-ink)]">{step.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-[var(--rv-mute)]">{step.body}</p>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── Features ────────────────────────────────────────── */}
        <section className="app-shell py-16 sm:py-20">
          <div className="mb-10">
            <h2 className="font-heading text-3xl font-bold uppercase text-[var(--rv-ink)] sm:text-5xl">
              {t("home.features.headline")}
            </h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <article
                  key={feature.titleKey}
                  className="rounded-2xl border border-[rgba(15,23,42,0.08)] bg-white p-6 transition-shadow hover:shadow-[0_12px_28px_rgba(15,23,42,0.08)]"
                >
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

        {/* ── Bottom CTA ──────────────────────────────────────── */}
        <section className="app-shell pb-20">
          <div className="surface-panel rounded-2xl px-6 py-10 sm:px-12 sm:py-14">
            <div className="flex flex-col items-start gap-8 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="tiny-label">{t("home.next.kicker")}</div>
                <h2 className="mt-3 max-w-[18ch] font-heading text-3xl font-bold uppercase text-white sm:text-4xl">
                  {t("home.next.headline")}
                </h2>
                <p className="mt-3 max-w-xl text-sm leading-6 text-quiet">
                  {t("home.next.body")}
                </p>
              </div>
              <Link
                href="/rankings"
                transitionTypes={["nav-forward"]}
                className="btn-primary shrink-0 px-6 py-3 text-sm"
              >
                {t("home.cta.app")}
                <ArrowRight className="size-4" />
              </Link>
            </div>
            <p className="mt-8 border-t border-white/8 pt-6 text-[0.7rem] leading-5 text-faint">
              {t("home.footer.disclaimer")}
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
