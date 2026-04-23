import {
  fetchRankings,
  type CoverageState,
  type RankingsQueryParams,
  type RankingsResponse,
} from "@/lib/api";
import { RankingsClient } from "@/app/app/rankings/_components/rankings-client";

interface PageProps {
  searchParams: Promise<{
    market?: string;
    asset_type?: string;
    conviction?: string;
    coverage_state?: string;
    limit?: string;
    min_final_score?: string;
    min_consensus_composite?: string;
    min_technical_composite?: string;
    min_strategy_pass_count?: string;
    min_canslim?: string;
    min_piotroski?: string;
    min_minervini?: string;
    min_weinstein?: string;
    min_rs_rating?: string;
    rs_line_new_high?: string;
    preset?: string;
  }>;
}

type Market = "US" | "KR";
type AssetType = "stock" | "etf";

const COVERAGE_STATES = new Set<CoverageState>([
  "ranked",
  "needs_price",
  "needs_fundamentals",
  "needs_scoring",
  "stale",
]);

function optionalNumber(value: string | undefined): number | undefined {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function optionalCoverageState(value: string | undefined): CoverageState | undefined {
  return COVERAGE_STATES.has(value as CoverageState) ? (value as CoverageState) : undefined;
}

function optionalBoolean(value: string | undefined): boolean | undefined {
  if (value === "true") return true;
  if (value === "false") return false;
  return undefined;
}

export default async function AppRankingsPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const market: Market = sp.market === "KR" ? "KR" : "US";
  const assetType: AssetType = sp.asset_type === "etf" ? "etf" : "stock";
  const conviction = sp.conviction ?? "";
  const coverageState = optionalCoverageState(sp.coverage_state);
  const parsedLimit = sp.limit ? parseInt(sp.limit, 10) : 200;
  const limit = Number.isFinite(parsedLimit) ? Math.min(Math.max(parsedLimit, 1), 200) : 200;
  const initialFilters = {
    market,
    assetType,
    conviction,
    coverageState,
    limit,
    minFinalScore: optionalNumber(sp.min_final_score),
    minConsensusComposite: optionalNumber(sp.min_consensus_composite),
    minTechnicalComposite: optionalNumber(sp.min_technical_composite),
    minStrategyPassCount: optionalNumber(sp.min_strategy_pass_count),
    minCanslim: optionalNumber(sp.min_canslim),
    minPiotroski: optionalNumber(sp.min_piotroski),
    minMinervini: optionalNumber(sp.min_minervini),
    minWeinstein: optionalNumber(sp.min_weinstein),
    minRsRating: optionalNumber(sp.min_rs_rating),
    rsLineNewHigh: optionalBoolean(sp.rs_line_new_high),
    preset: sp.preset ?? "all",
  };
  const rankingParams: RankingsQueryParams = {
    market,
    asset_type: assetType,
    conviction: conviction || undefined,
    coverage_state: coverageState,
    limit,
    min_final_score: initialFilters.minFinalScore,
    min_consensus_composite: initialFilters.minConsensusComposite,
    min_technical_composite: initialFilters.minTechnicalComposite,
    min_strategy_pass_count: initialFilters.minStrategyPassCount,
    min_canslim: initialFilters.minCanslim,
    min_piotroski: initialFilters.minPiotroski,
    min_minervini: initialFilters.minMinervini,
    min_weinstein: initialFilters.minWeinstein,
    min_rs_rating: initialFilters.minRsRating,
    rs_line_new_high: initialFilters.rsLineNewHigh,
  };

  let initialData: RankingsResponse | null = null;
  try {
    initialData = await fetchRankings(rankingParams);
  } catch {
    // Client-side query handles recovery.
  }

  return (
    <RankingsClient
      initialFilters={initialFilters}
      initialData={initialData}
    />
  );
}
