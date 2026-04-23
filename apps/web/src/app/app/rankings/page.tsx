import { fetchRankings, type RankingsResponse } from "@/lib/api";
import { RankingsClient } from "@/app/app/rankings/_components/rankings-client";

interface PageProps {
  searchParams: Promise<{
    market?: string;
    asset_type?: string;
    conviction?: string;
    limit?: string;
  }>;
}

export default async function AppRankingsPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const market = sp.market === "KR" ? "KR" : "US";
  const assetType = sp.asset_type === "etf" ? "etf" : "stock";
  const conviction = sp.conviction ?? "";
  const parsedLimit = sp.limit ? parseInt(sp.limit, 10) : 200;
  const limit = Number.isFinite(parsedLimit) ? Math.min(Math.max(parsedLimit, 1), 200) : 200;

  let initialData: RankingsResponse | null = null;
  try {
    initialData = await fetchRankings({
      market,
      asset_type: assetType,
      conviction: conviction || undefined,
      limit,
    });
  } catch {
    // Client-side query handles recovery.
  }

  return (
    <RankingsClient
      initialFilters={{
        market,
        assetType,
        conviction,
        limit,
      }}
      initialData={initialData}
    />
  );
}
