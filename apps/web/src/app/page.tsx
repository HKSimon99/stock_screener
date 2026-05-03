"use client";

import Link from "next/link";
import { ArrowRight, CandlestickChart, Search, ShieldCheck, Waves } from "lucide-react";
import { SiteChrome } from "@/components/site-chrome";
import { useT } from "@/hooks/use-t";

/**
 * Landing page — Revolut three-band layout.
 * Strings pulled from useT() so EN/KO toggle works immediately.
 *
 * Band 1: Black storytelling canvas — hero headline + CTAs + launch stats
 * Band 2: White catalogue canvas — feature grid (light card, dark ink)
 * Band 3: Black direction canvas — direction card + next action card
 * Footer: Black hairline bottom
 */

const FEATURE_ICONS = [Search, ShieldCheck, CandlestickChart, Waves] as const;

export default function Home() {
  const { t } = useT();

  const FEATURES = [
    { icon: FEATURE_ICONS[0], titleKey: "home.features.search.title",   bodyKey: "home.features.search.body"   },
    { icon: FEATURE_ICONS[1], titleKey: "home.features.coverage.title", bodyKey: "home.features.coverage.body" },
    { icon: FEATURE_ICONS[2], titleKey: "home.features.chart.title",    bodyKey: "home.features.chart.body"    },
    { icon: FEATURE_ICONS[3], titleKey: "home.features.regime.title",   bodyKey: "home.features.regime.body"   },
  ] as const;

  const STATS = [
    {
      labelKey: "home.stats.universe.label",
      valueKey: "home.stats.universe.value",
      subKey:   "home.stats.universe.sub",
    },
    {
      labelKey: "home.stats.strategies.label",
      valueKey: "home.stats.strategies.value",
      subKey:   "home.stats.strategies.sub",
    },
    {
      labelKey: "home.stats.data.label",
      valueKey: "home.stats.data.value",
      subKey:   "home.stats.data.sub",
    },
  ] as const;

  return (
    <div className="min-h-screen" style={{ background: "#000000" }}>
      <SiteChrome />

      {/* ── Band 1: Black storytelling canvas ─────────────────────── */}
      <section style={{ background: "#000000", paddingBottom: "var(--sp-band)" }}>
        <div className="app-shell" style={{ paddingTop: "var(--sp-band)" }}>

          <div className="section-kicker" style={{ color: "rgba(255,255,255,0.45)" }}>
            {t("home.kicker")}
          </div>

          <h1
            className="display-hero text-white text-balance"
            style={{ marginTop: "var(--sp-xl)", maxWidth: "16ch" }}
          >
            {t("home.headline1")}{" "}
            <span style={{ color: "rgba(255,255,255,0.42)" }}>
              {t("home.headline2")}
            </span>
          </h1>

          <p
            className="text-quiet"
            style={{
              marginTop: "var(--sp-xl)",
              maxWidth: "44ch",
              fontSize: "1.125rem",
              lineHeight: 1.7,
            }}
          >
            {t("home.sub")}
          </p>

          <div
            style={{
              marginTop: "var(--sp-xxl)",
              display: "flex",
              flexWrap: "wrap",
              gap: "var(--sp-md)",
            }}
          >
            <Link href="/rankings" className="btn-primary">
              {t("home.cta.app")}
              <ArrowRight style={{ width: 16, height: 16 }} />
            </Link>
            <Link href="/methodology" className="btn-outline">
              {t("home.cta.methodology")}
            </Link>
          </div>

          {/* Launch stats row */}
          <div
            style={{
              marginTop: "var(--sp-3xl)",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(11rem, 1fr))",
              gap: "var(--sp-md)",
            }}
          >
            {STATS.map((stat) => (
              <div
                key={stat.labelKey}
                style={{
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  background: "#16181a",
                  padding: "var(--sp-xl)",
                }}
              >
                <div className="tiny-label">{t(stat.labelKey)}</div>
                <div
                  className="font-heading text-white"
                  style={{
                    marginTop: "var(--sp-sm)",
                    fontSize: "2rem",
                    fontWeight: 500,
                    letterSpacing: "-0.03em",
                  }}
                >
                  {t(stat.valueKey)}
                </div>
                <div
                  style={{
                    marginTop: "var(--sp-xs)",
                    fontSize: "0.8125rem",
                    color: "rgba(255,255,255,0.42)",
                  }}
                >
                  {t(stat.subKey)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Band 2: White catalogue canvas ────────────────────────── */}
      <section style={{ background: "#ffffff", paddingBlock: "var(--sp-band)" }}>
        <div className="app-shell">

          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 600,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "#505a63",
            }}
          >
            {t("home.features.kicker")}
          </div>

          <h2
            className="font-heading"
            style={{
              marginTop: "var(--sp-lg)",
              fontSize: "clamp(2rem, 4vw, 3rem)",
              fontWeight: 500,
              letterSpacing: "-0.02em",
              textTransform: "uppercase",
              color: "#191c1f",
              maxWidth: "20ch",
            }}
          >
            {t("home.features.headline")}
          </h2>

          <div
            style={{
              marginTop: "var(--sp-3xl)",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(16rem, 1fr))",
              gap: "var(--sp-lg)",
            }}
          >
            {FEATURES.map((feature) => {
              const Icon = feature.icon;
              return (
                <article
                  key={feature.titleKey}
                  style={{
                    borderRadius: "var(--radius-lg)",
                    border: "1px solid #e2e2e7",
                    background: "#ffffff",
                    padding: "var(--sp-xl)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: 44,
                      height: 44,
                      borderRadius: "var(--radius-md)",
                      border: "1px solid #e2e2e7",
                      background: "#f4f4f4",
                    }}
                  >
                    <Icon style={{ width: 20, height: 20, color: "#3a40c4" }} />
                  </div>

                  <h3
                    className="font-heading"
                    style={{
                      marginTop: "var(--sp-lg)",
                      fontSize: "1.25rem",
                      fontWeight: 600,
                      letterSpacing: "-0.01em",
                      color: "#191c1f",
                    }}
                  >
                    {t(feature.titleKey)}
                  </h3>
                  <p
                    style={{
                      marginTop: "var(--sp-sm)",
                      fontSize: "0.875rem",
                      lineHeight: 1.7,
                      color: "#505a63",
                    }}
                  >
                    {t(feature.bodyKey)}
                  </p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── Band 3: Black direction canvas ────────────────────────── */}
      <section style={{ background: "#000000", paddingBlock: "var(--sp-band)" }}>
        <div
          className="app-shell"
          style={{
            display: "grid",
            gap: "var(--sp-lg)",
            gridTemplateColumns: "repeat(auto-fit, minmax(20rem, 1fr))",
          }}
        >
          {/* Direction card */}
          <article
            style={{
              borderRadius: "var(--radius-lg)",
              border: "1px solid rgba(255,255,255,0.08)",
              background: "#16181a",
              padding: "var(--sp-xxl)",
            }}
          >
            <div className="section-kicker" style={{ color: "rgba(255,255,255,0.42)" }}>
              {t("home.direction.kicker")}
            </div>
            <h2
              className="font-heading text-white"
              style={{
                marginTop: "var(--sp-lg)",
                fontSize: "clamp(1.75rem, 3vw, 2.5rem)",
                fontWeight: 500,
                letterSpacing: "-0.025em",
                textTransform: "uppercase",
              }}
            >
              {t("home.direction.headline1")}{" "}
              <span style={{ color: "rgba(255,255,255,0.42)" }}>
                {t("home.direction.headline2")}
              </span>
            </h2>
            <p
              style={{
                marginTop: "var(--sp-xl)",
                fontSize: "0.9375rem",
                lineHeight: 1.7,
                color: "rgba(255,255,255,0.55)",
                maxWidth: "44ch",
              }}
            >
              {t("home.direction.body")}
            </p>
          </article>

          {/* Next action card */}
          <article
            style={{
              borderRadius: "var(--radius-lg)",
              border: "1px solid rgba(73,79,223,0.30)",
              background: "rgba(73,79,223,0.06)",
              padding: "var(--sp-xxl)",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div className="section-kicker" style={{ color: "rgba(255,255,255,0.42)" }}>
              {t("home.next.kicker")}
            </div>
            <h2
              className="font-heading text-white"
              style={{
                marginTop: "var(--sp-lg)",
                fontSize: "clamp(1.75rem, 3vw, 2.5rem)",
                fontWeight: 500,
                letterSpacing: "-0.025em",
                textTransform: "uppercase",
              }}
            >
              {t("home.next.headline")}
            </h2>
            <p
              style={{
                marginTop: "var(--sp-xl)",
                fontSize: "0.9375rem",
                lineHeight: 1.7,
                color: "rgba(255,255,255,0.55)",
              }}
            >
              {t("home.next.body")}
            </p>
            <div style={{ marginTop: "auto", paddingTop: "var(--sp-xxl)" }}>
              <Link href="/rankings" className="btn-primary">
                {t("home.next.cta")}
                <ArrowRight style={{ width: 16, height: 16 }} />
              </Link>
            </div>
          </article>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────────── */}
      <footer
        style={{
          background: "#000000",
          borderTop: "1px solid rgba(255,255,255,0.06)",
          paddingBlock: "var(--sp-3xl)",
        }}
      >
        <div
          className="app-shell"
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--sp-xl)",
          }}
        >
          <span
            className="font-heading text-white"
            style={{
              fontSize: "1rem",
              fontWeight: 600,
              letterSpacing: "-0.01em",
              textTransform: "uppercase",
            }}
          >
            Consensus
          </span>
          <nav style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-xl)" }}>
            {(
              [
                { href: "/methodology",      labelKey: "nav.methodology" },
                { href: "/data-sources",     labelKey: "nav.dataSources" },
                { href: "/freshness-policy", labelKey: "nav.freshness"   },
                { href: "/disclosures",      labelKey: "nav.disclosures" },
              ] as const
            ).map((item) => (
              <Link
                key={item.href}
                href={item.href}
                style={{
                  fontSize: "0.8125rem",
                  color: "rgba(255,255,255,0.42)",
                  transition: "color 180ms ease",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "#ffffff")}
                onMouseLeave={(e) =>
                  (e.currentTarget.style.color = "rgba(255,255,255,0.42)")
                }
              >
                {t(item.labelKey)}
              </Link>
            ))}
          </nav>
          <span style={{ fontSize: "0.8125rem", color: "rgba(255,255,255,0.28)" }}>
            {t("home.footer.disclaimer")}
          </span>
        </div>
      </footer>
    </div>
  );
}
