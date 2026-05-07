import { SiteChrome } from "@/components/site-chrome";

const sections = [
  {
    title: "Coverage before confidence",
    body: "The platform distinguishes symbols that need price data, fundamentals, scoring, or freshness repair from names that are truly ranked.",
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
        <section className="surface-panel rounded-2xl px-6 py-7 sm:px-8">
          <div className="section-kicker">Methodology</div>
          <h1 className="mt-3 max-w-5xl font-heading text-4xl font-bold uppercase text-white sm:text-5xl lg:text-6xl">
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
            <article key={section.title} className="metric-tile">
              <h2 className="font-heading text-2xl font-bold uppercase text-[var(--rv-ink)] sm:text-3xl">
                {section.title}
              </h2>
              <p className="mt-3 text-sm leading-6 text-[var(--rv-mute)]">{section.body}</p>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
