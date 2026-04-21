import { fetchStrategyRankings, type StrategyRankingsResponse } from "@/lib/api";
import { StrategiesClient } from "@/app/app/strategies/_components/strategies-client";

/**
 * Strategies page — server component.
 *
 * Pre-fetches CANSLIM/US rankings (the default tab) for instant first-paint.
 * Additional strategy/market combos are fetched client-side on tab change.
 */
export default async function StrategiesPage() {
  let initialData: Partial<Record<string, StrategyRankingsResponse>> = {};

  try {
    const canslimUS = await fetchStrategyRankings("canslim", "US");
    initialData = { "canslim-US": canslimUS };
  } catch {
    // Client-side query handles recovery; page still renders.
  }

  return <StrategiesClient initialData={initialData} />;
}
