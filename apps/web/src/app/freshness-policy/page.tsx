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
        <section className="surface-panel rounded-2xl px-6 py-7 sm:px-8">
          <div className="section-kicker">Freshness Policy</div>
          <h1 className="mt-3 max-w-5xl font-heading text-4xl font-bold uppercase text-white sm:text-5xl lg:text-6xl">
            Freshness labels should remove ambiguity, not decorate it.
          </h1>
          <p className="mt-5 max-w-3xl text-sm leading-7 text-quiet sm:text-base">
            The app exposes what date the price, fundamental, and ranked layers were last refreshed.
            Coverage states are intended to explain what the product can safely claim for each symbol.
          </p>
        </section>

        <section className="mt-6 overflow-hidden rounded-2xl border border-[rgba(15,23,42,0.1)] bg-white shadow-[0_16px_42px_rgba(15,23,42,0.06)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-[var(--rv-surface-soft)]">
              <tr>
                <th className="px-5 py-4 tiny-label">State</th>
                <th className="px-5 py-4 tiny-label">Meaning</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([state, meaning]) => (
                <tr key={state} className="border-t border-[rgba(15,23,42,0.08)]">
                  <td className="px-5 py-4 font-heading text-2xl font-bold uppercase text-[var(--rv-ink)]">{state}</td>
                  <td className="px-5 py-4 text-[var(--rv-mute)]">{meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}
