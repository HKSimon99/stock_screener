import Link from "next/link";

const SITE_LINKS = [
  { href: "/methodology", label: "Methodology" },
  { href: "/data-sources", label: "Data Sources" },
  { href: "/freshness-policy", label: "Freshness" },
  { href: "/disclosures", label: "Disclosures" },
] as const;

export function SiteChrome() {
  return (
    <header className="app-shell pt-4 sm:pt-6">
      <div className="flex flex-col gap-4 rounded-[2rem] border border-white/10 bg-black/14 px-5 py-4 backdrop-blur sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>
          <div className="tiny-label">Consensus Research Platform</div>
          <Link href="/" className="mt-1 inline-block font-heading text-3xl uppercase tracking-[0.05em] text-white">
            Consensus Signal Research
          </Link>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {SITE_LINKS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-full border border-white/10 px-4 py-2 text-[0.72rem] uppercase tracking-[0.14em] text-faint transition-colors hover:text-white"
            >
              {item.label}
            </Link>
          ))}
          <Link
            href="/app/rankings"
            className="rounded-full border border-[oklch(0.78_0.11_84_/_0.42)] bg-[oklch(0.8_0.11_84_/_0.14)] px-4 py-2 text-[0.72rem] uppercase tracking-[0.14em] text-white"
          >
            Open App
          </Link>
        </div>
      </div>
    </header>
  );
}
