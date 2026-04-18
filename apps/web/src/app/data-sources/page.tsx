import { SiteChrome } from "@/components/site-chrome";

const sources = [
  ["US listings", "Nasdaq Trader symbol directories for major listed US securities."],
  ["KR listings", "KRX universe ingestion via FinanceDataReader-backed KRX listings."],
  ["US fundamentals", "SEC EDGAR / XBRL ingestion through edgartools."],
  ["KR fundamentals", "OpenDART filings and corp-code mapping."],
  ["US prices", "Yahoo Finance historical prices for delayed/snapshot research views."],
  ["KR prices", "KIS-backed historical pricing pipeline with live-stream delivery path gated by licensing."],
] as const;

export default function DataSourcesPage() {
  return (
    <div className="pb-16">
      <SiteChrome />
      <main className="app-shell pt-6 sm:pt-8">
        <section className="surface-panel rounded-[2rem] px-6 py-7 sm:px-8">
          <div className="section-kicker">Data Sources</div>
          <h1 className="mt-3 font-heading text-6xl uppercase tracking-[0.03em] text-white">
            Source provenance is part of the product.
          </h1>
          <p className="mt-5 max-w-3xl text-sm leading-7 text-quiet sm:text-base">
            Every coverage state in the app should eventually be traceable to one or more
            upstream market, price, or filing sources. This page describes the current launch stack.
          </p>
        </section>

        <section className="mt-6 grid gap-4 lg:grid-cols-2">
          {sources.map(([title, body]) => (
            <article key={title} className="surface-panel rounded-[1.8rem] px-5 py-5">
              <div className="tiny-label">{title}</div>
              <p className="mt-3 text-sm leading-6 text-quiet">{body}</p>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
