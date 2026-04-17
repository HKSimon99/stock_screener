import { SiteChrome } from "@/components/site-chrome";

const sections = [
  {
    title: "Coverage before confidence",
    body: "The platform distinguishes searchable symbols from price-ready, fundamentals-ready, and ranked names. A stock can be searchable even when it is not yet eligible for ranking.",
  },
  {
    title: "Named strategies are overlays",
    body: "CANSLIM, Piotroski, Minervini, Weinstein, and Dual Momentum remain visible because they explain profile and posture well, but they should not be confused with full-universe coverage by themselves.",
  },
  {
    title: "Point-in-time data matters",
    body: "US fundamentals come from EDGAR/XBRL and Korea fundamentals come from OpenDART. Rankings and explanations are only as trustworthy as their filing availability, price history, and freshness labels.",
  },
] as const;

export default function MethodologyPage() {
  return (
    <div className="pb-16">
      <SiteChrome />
      <main className="app-shell pt-6 sm:pt-8">
        <section className="surface-panel rounded-[2rem] px-6 py-7 sm:px-8">
          <div className="section-kicker">Methodology</div>
          <h1 className="mt-3 font-heading text-6xl uppercase tracking-[0.03em] text-white">
            Ranking logic should be explainable before it is persuasive.
          </h1>
          <p className="mt-5 max-w-3xl text-sm leading-7 text-quiet sm:text-base">
            This release keeps the existing multi-strategy scoring engine visible while
            rebuilding the product around broader universe coverage, clearer freshness,
            and coverage-aware ranking eligibility.
          </p>
        </section>

        <section className="mt-6 grid gap-4 lg:grid-cols-3">
          {sections.map((section) => (
            <article key={section.title} className="surface-panel rounded-[1.8rem] px-5 py-5">
              <h2 className="font-heading text-3xl uppercase tracking-[0.03em] text-white">
                {section.title}
              </h2>
              <p className="mt-3 text-sm leading-6 text-quiet">{section.body}</p>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
