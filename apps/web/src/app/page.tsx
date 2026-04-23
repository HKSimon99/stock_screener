import Link from "next/link";
import { ArrowRight, CandlestickChart, Search, ShieldCheck, Waves } from "lucide-react";
import { SiteChrome } from "@/components/site-chrome";

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

export default function Home() {
  return (
    <div className="pb-20">
      <SiteChrome />

      <main className="app-shell pt-6 sm:pt-8">
        <section className="relative overflow-hidden rounded-[2.4rem] border border-white/10 bg-[linear-gradient(135deg,oklch(0.2_0.02_248),oklch(0.12_0.01_252))] px-6 py-8 shadow-[0_28px_120px_oklch(0.05_0.01_248_/_0.54)] sm:px-8 sm:py-10">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_16%_18%,oklch(0.82_0.15_78_/_0.18),transparent_30%),radial-gradient(circle_at_86%_14%,oklch(0.78_0.08_184_/_0.18),transparent_24%),linear-gradient(180deg,transparent,oklch(0.05_0.01_248_/_0.24))]" />
          <div className="relative grid gap-10 xl:grid-cols-[minmax(0,1.2fr)_minmax(20rem,0.8fr)] xl:items-end">
            <div className="max-w-4xl">
              <div className="section-kicker">Production research for US + Korea</div>
              <h1 className="mt-4 font-heading text-[clamp(4rem,10vw,8rem)] uppercase leading-[0.86] tracking-[-0.05em] text-white">
                Search Everything. Rank What You Can Defend.
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-7 text-[oklch(0.84_0.02_88)] sm:text-lg">
                Consensus Signal Research is being rebuilt as a full-market search,
                ranking, and chart workspace. It separates incomplete or stale coverage
                from truly ranked names, keeps live-vs-delayed context visible, and
                treats market regime as part of the product instead of a footnote.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  href="/app/rankings"
                  className="inline-flex items-center gap-2 rounded-full border border-[oklch(0.78_0.11_84_/_0.42)] bg-[oklch(0.8_0.11_84_/_0.14)] px-5 py-3 text-sm font-medium uppercase tracking-[0.16em] text-white"
                >
                  Open Research App
                  <ArrowRight className="size-4" />
                </Link>
                <Link
                  href="/methodology"
                  className="inline-flex items-center gap-2 rounded-full border border-white/10 px-5 py-3 text-sm font-medium uppercase tracking-[0.16em] text-faint transition-colors hover:text-white"
                >
                  Read methodology
                </Link>
              </div>
            </div>

            <div className="rounded-[2rem] border border-white/10 bg-black/18 p-5 backdrop-blur">
              <div className="tiny-label">Launch stance</div>
              <div className="mt-3 grid gap-3">
                <div className="rounded-[1.4rem] border border-white/10 bg-white/6 p-4">
                  <div className="tiny-label">Universe</div>
                  <div className="mt-2 text-xl font-semibold text-white">
                    Major listed equities + ETFs
                  </div>
                  <div className="mt-2 text-sm leading-6 text-quiet">
                    US and KR can be discovered from day one. Rankings stay honest about eligibility.
                  </div>
                </div>
                <div className="rounded-[1.4rem] border border-white/10 bg-white/6 p-4">
                  <div className="tiny-label">Launch posture</div>
                  <div className="mt-2 text-xl font-semibold text-white">Research tool first</div>
                  <div className="mt-2 text-sm leading-6 text-quiet">
                    The product is framed as a research and charting system, not an advisory product.
                  </div>
                </div>
                <div className="rounded-[1.4rem] border border-white/10 bg-white/6 p-4">
                  <div className="tiny-label">Live delivery</div>
                  <div className="mt-2 text-xl font-semibold text-white">KR live path, US delayed</div>
                  <div className="mt-2 text-sm leading-6 text-quiet">
                    Live KR display is technically supported and clearly gated by licensing.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-8 grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
          {FEATURE_GRID.map((feature) => {
            const Icon = feature.icon;
            return (
              <article
                key={feature.title}
                className="surface-panel rounded-[1.8rem] px-5 py-5"
              >
                <div className="flex size-11 items-center justify-center rounded-2xl border border-white/10 bg-black/14">
                  <Icon className="size-5 text-white" />
                </div>
                <h2 className="mt-4 font-heading text-3xl uppercase tracking-[0.03em] text-white">
                  {feature.title}
                </h2>
                <p className="mt-3 text-sm leading-6 text-quiet">{feature.body}</p>
              </article>
            );
          })}
        </section>

        <section className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.85fr)]">
          <article className="surface-panel rounded-[2rem] px-6 py-6 sm:px-7">
            <div className="section-kicker">Fresh build direction</div>
            <h2 className="mt-3 font-heading text-5xl uppercase tracking-[0.03em] text-white">
              Public site outside, working desk inside.
            </h2>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-quiet sm:text-base">
              The public surface explains methodology, data contracts, freshness,
              and disclosures. The `/app` surface is where rankings, symbol search,
              and instrument workspaces live. That split keeps the product sharper
              for launch and much easier to trust.
            </p>
          </article>

          <article className="rounded-[2rem] border border-white/10 bg-black/18 px-6 py-6">
            <div className="section-kicker">Next action</div>
            <h2 className="mt-3 font-heading text-4xl uppercase tracking-[0.03em] text-white">
              Try the production shell
            </h2>
            <p className="mt-4 text-sm leading-6 text-quiet">
              The new app shell exposes canonical `/app` routes, a search-first entry,
              and coverage-aware instrument pages.
            </p>
            <Link
              href="/app/search"
              className="mt-6 inline-flex items-center gap-2 rounded-full border border-white/10 px-5 py-3 text-sm uppercase tracking-[0.16em] text-faint transition-colors hover:text-white"
            >
              Open search
              <ArrowRight className="size-4" />
            </Link>
          </article>
        </section>
      </main>
    </div>
  );
}
