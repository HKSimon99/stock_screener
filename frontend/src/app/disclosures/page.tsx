import { SiteChrome } from "@/components/site-chrome";

const items = [
  "The product is a research and charting tool, not individualized investment advice.",
  "Displayed market data may be live, delayed, or end-of-day depending on market, entitlement, and source availability.",
  "Coverage states explain what data is available; they are not endorsements of quality, safety, or expected return.",
  "Korea live redistribution for public web and mobile experiences remains subject to market-data licensing and exchange policy.",
] as const;

export default function DisclosuresPage() {
  return (
    <div className="pb-16">
      <SiteChrome />
      <main className="app-shell pt-6 sm:pt-8">
        <section className="surface-panel rounded-[2rem] px-6 py-7 sm:px-8">
          <div className="section-kicker">Disclosures</div>
          <h1 className="mt-3 font-heading text-6xl uppercase tracking-[0.03em] text-white">
            Trust is built with limits stated clearly.
          </h1>
          <div className="mt-6 grid gap-4">
            {items.map((item) => (
              <div key={item} className="rounded-[1.4rem] border border-white/10 bg-black/14 px-5 py-4 text-sm leading-6 text-quiet">
                {item}
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
