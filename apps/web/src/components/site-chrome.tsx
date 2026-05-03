import Link from "next/link";

/**
 * SiteChrome — public marketing nav.
 *
 * Revolut nav-bar pattern:
 *  - True black (#000000) background, 1px hairline-dark border below.
 *  - Wordmark left, secondary nav links centre, primary CTA right.
 *  - CTA = white pill on black (btn-primary) — the brand's loudest action.
 *  - Secondary links = text-white/60, hover to text-white. No pill borders.
 *  - Height 64px desktop, sticky.
 */

const SITE_LINKS = [
  { href: "/methodology",      label: "Methodology" },
  { href: "/data-sources",     label: "Data Sources" },
  { href: "/freshness-policy", label: "Freshness" },
  { href: "/disclosures",      label: "Disclosures" },
] as const;

export function SiteChrome() {
  return (
    <header
      className="sticky top-0 z-50 w-full"
      style={{
        background: "#000000",
        borderBottom: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      <div className="app-shell flex h-16 items-center justify-between gap-6">

        {/* Wordmark */}
        <Link
          href="/"
          className="shrink-0 font-heading text-xl font-semibold uppercase text-white"
          style={{ letterSpacing: "-0.02em" }}
        >
          Consensus
        </Link>

        {/* Secondary nav links — hidden on small screens */}
        <nav className="hidden items-center gap-7 md:flex">
          {SITE_LINKS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-sm font-medium transition-colors"
              style={{ color: "rgba(255,255,255,0.60)" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#ffffff")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(255,255,255,0.60)")}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        {/* Primary CTA — white pill on black */}
        <Link
          href="/rankings"
          className="btn-primary shrink-0"
          style={{ fontSize: "0.875rem", padding: "10px 22px", height: "40px" }}
        >
          Open App
        </Link>
      </div>
    </header>
  );
}
