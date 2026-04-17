import { fetchMarketRegimeBoard, type MarketRegimeBoard } from "@/lib/api";
import { MarketRegimeClient } from "@/app/app/market-regime/_components/market-regime-client";

export default async function AppMarketRegimePage() {
  let initialData: MarketRegimeBoard | null = null;

  try {
    initialData = await fetchMarketRegimeBoard(8);
  } catch {
    // Client-side query handles recovery.
  }

  return <MarketRegimeClient initialData={initialData} />;
}
