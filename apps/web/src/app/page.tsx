import Link from "next/link";
import { ArrowRight, CandlestickChart, Search, ShieldCheck, Waves } from "lucide-react";
import { SiteChrome } from "@/components/site-chrome";

/**
 * Landing page — Revolut three-band layout
 *
 * Band 1: Black storytelling canvas — hero headline + CTAs + launch stats
 * Band 2: White catalogue canvas — feature grid (light card, dark ink)
 * Band 3: Black direction canvas — direction card + next action card
 * Footer: Black hairline bottom
 */

const FEATURE_GRID = [
  {
    title: "Full-market search",
    body: "Search every covered US and KR symbol, then open a chart workspace even when a stock is not yet fully ranked.",
    icon: Search,
  },
  {
    title: "Coverage-aware ranking",
    body: "The product separates symbols that need more data, scoring, or freshness repair from ranked names so the board stays honest about what it knows.",
    icon: ShieldCheck,
  },
  {
    title: "Research chart workspace",
    body: "Move from rankings into a single-stock desk with price structure, relative strength, patterns, and freshness context in one place.",
    icon: CandlestickChart,
  },
  {
    title: "Market-state discipline",
    body: "US and KR regime boards stay visible so rank interpretation is grounded in actual market posture instead of blind score chasing.",
    icon: Waves,
  },
] as const;

const LAUNCH_STATS = [
  { label: "Universe", value: "6,500+", sub: "US + KR equities & ETFs" },
  { label: "Strategies", value: "3", sub: "CANSLIM · Piotroski · Magic Formula" },
  { label: "Market data", value: "Nightly", sub: "KR live path, US delayed" },
] as const;

export default function Home() {
  return (
    <div className="min-h-screen" style={{ background: "#000000" }}>
      <SiteChrome />

      {/* ── Band 1: Black storytelling canvas ─────────────────────── */}
      <section style={{ background: "#000000", paddingBottom: "var(--sp-band)" }}>
        <div className="app-shell" style={{ paddingTop: "var(--sp-band)" }}>

          {/* Kicker */}
          <div className="section-kicker" style={{ color: "rgba(255,255,255,0.45)" }}>
            Production research for US + Korea
          </div>

          {/* Hero headline */}
          <h1
            className="display-hero text-white text-balance"
            style={{ marginTop: "var(--sp-xl)", maxWidth: "16ch" }}
          >
            Search Everything.{" "}
            <span style={{ color: "rgba(255,255,255,0.42)" }}>
              Rank What You Can Defend.
            </span>
          </h1>

          {/* Sub-copy */}
          <p
            className="text-quiet"
            style={{
              marginTop: "var(--sp-xl)",
              maxWidth: "44ch",
              fontSize: "1.125rem",
              lineHeight: 1.7,
            }}
          >
            Consensus Signal Research is a full-market search, ranking, and chart
            workspace for US and Korean equities. Honest coverage, regime-aware
            conviction levels, nightly data.
          </p>

          {/* CTAs */}
          <div
            style={{
              marginTop: "var(--sp-xxl)",
              display: "flex",
              flexWrap: "wrap",
              gap: "var(--sp-md)",
            }}
          >
            <Link href="/rankings" className="btn-primary">
              Open Research App
              <ArrowRight style={{ width: 16, height: 16 }} />
            </Link>
            <Link href="/methodology" className="btn-outline">
              Read methodology
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
            {LAUNCH_STATS.map((stat) => (
              <div
                key={stat.label}
                style={{
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  background: "#16181a",
                  padding: "var(--sp-xl)",
                }}
              >
                <div className="tiny-label">{stat.label}</div>
                <div
                  className="font-heading text-white"
                  style={{
                    marginTop: "var(--sp-sm)",
                    fontSize: "2rem",
                    fontWeight: 500,
                    letterSpacing: "-0.03em",
                  }}
                >
                  {stat.value}
                </div>
                <div
                  style={{
                    marginTop: "var(--sp-xs)",
                    fontSize: "0.8125rem",
                    color: "rgba(255,255,255,0.42)",
                  }}
                >
                  {stat.sub}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Band 2: White catalogue canvas ────────────────────────── */}
      <section style={{ background: "#ffffff", paddingBlock: "var(--sp-band)" }}>
        <div className="app-shell">

          {/* Section kicker */}
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 600,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "#505a63",
            }}
          >
            What's inside
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
            Built for how research actually works.
          </h2>

          {/* Feature grid — light cards on white canvas */}
          <div
            style={{
              marginTop: "var(--sp-3xl)",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(16rem, 1fr))",
              gap: "var(--sp-lg)",
            }}
          >
            {FEATURE_GRID.map((feature) => {
              const Icon = feature.icon;
              return (
                <article
                  key={feature.title}
                  style={{
                    borderRadius: "var(--radius-lg)",
                    border: "1px solid #e2e2e7",
                    background: "#ffffff",
                    padding: "var(--sp-xl)",
                  }}
                >
                  {/* Icon */}
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
                    {feature.title}
                  </h3>
                  <p
                    style={{
                      marginTop: "var(--sp-sm)",
                      fontSize: "0.875rem",
                      lineHeight: 1.7,
                      color: "#505a63",
                    }}
                  >
                    {feature.body}
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
              Fresh build direction
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
              Public site outside,{" "}
              <span style={{ color: "rgba(255,255,255,0.42)" }}>
                working desk inside.
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
              The public surface explains methodology, data contracts, freshness,
              and disclosures. The app is where rankings, symbol search, and
              instrument workspaces live — kept separate to stay sharp and easy
              to trust at launch.
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
              Next action
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
              Try the production shell
            </h2>
            <p
              style={{
                marginTop: "var(--sp-xl)",
                fontSize: "0.9375rem",
                lineHeight: 1.7,
                color: "rgba(255,255,255,0.55)",
              }}
            >
              The app shell exposes canonical routes, a search-first entry, and
              coverage-aware instrument pages. Rankings update nightly.
            </p>
            <div style={{ marginTop: "auto", paddingTop: "var(--sp-xxl)" }}>
              <Link href="/app/search" className="btn-primary">
                Open search
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
          <nav
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "var(--sp-xl)",
            }}
          >
            {[
              { href: "/methodology", label: "Methodology" },
              { href: "/data-sources", label: "Data Sources" },
              { href: "/freshness-policy", label: "Freshness" },
              { href: "/disclosures", label: "Disclosures" },
            ].map((item) => (
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
                {item.label}
              </Link>
            ))}
          </nav>
          <span style={{ fontSize: "0.8125rem", color: "rgba(255,255,255,0.28)" }}>
            Not investment advice.
          </span>
        </div>
      </footer>
    </div>
  );
}
