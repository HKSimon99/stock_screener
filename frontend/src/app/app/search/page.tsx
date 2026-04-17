import { SearchClient } from "./search-client";

interface PageProps {
  searchParams: Promise<{
    q?: string;
    market?: string;
    asset_type?: string;
  }>;
}

export default async function SearchPage({ searchParams }: PageProps) {
  const sp = await searchParams;

  return (
    <SearchClient
      initialQuery={sp.q ?? ""}
      initialMarket={sp.market === "KR" ? "KR" : sp.market === "US" ? "US" : undefined}
      initialAssetType={sp.asset_type === "etf" ? "etf" : sp.asset_type === "stock" ? "stock" : undefined}
    />
  );
}
