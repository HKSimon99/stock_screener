import { SiteChrome } from "@/components/site-chrome";

const rows = [
  ["Needs Price", "The security exists in the supported universe but does not yet have usable price history."],
  ["Needs Fundamentals", "Historical pricing exists, but supported stock filing coverage is not available yet."],
  ["Needs Scoring", "The required raw data exists, but a stored score has not been generated yet."],
  ["Stale", "A price or fundamentals layer is older than the market-aware freshness policy expects."],
  ["Ranked", "A stored score snapshot exists and the symbol can appear in the leaderboard."],
] as const;

export default function FreshnessPolicyPage() {
  return (
    <div className="pb-16">
      <SiteChrome />
      <main className="app-shell pt-6 sm:pt-8">
        <section className="surface-panel rounded-[2rem] px-6 py-7 sm:px-8">
          <div className="section-kicker">Freshness Policy</div>
          <h1 className="mt-3 font-heading text-6xl uppercase tracking-[0.03em] text-white">
            Freshness labels should remove ambiguity, not decorate it.
          </h1>
          <p className="mt-5 max-w-3xl text-sm leading-7 text-quiet sm:text-base">
            The app exposes what date the price, fundamental, and ranked layers were last refreshed.
            Coverage states are intended to explain what the product can safely claim for each symbol.
          </p>
        </section>

        <section className="mt-6 overflow-hidden rounded-[1.8rem] border border-white/10">
          <table className="w-full text-left text-sm">
            <thead className="bg-black/18">
              <tr>
                <th className="px-5 py-4 tiny-label">State</th>
                <th className="px-5 py-4 tiny-label">Meaning</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([state, meaning]) => (
                <tr key={state} className="border-t border-white/8">
                  <td className="px-5 py-4 font-heading text-2xl uppercase text-white">{state}</td>
                  <td className="px-5 py-4 text-quiet">{meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}
