"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import {
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  Bookmark,
  ChevronDown,
  Filter,
  LineChart,
  Loader2,
  Pin,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  APIError,
  addToWatchlist,
  buildInstrumentPath,
  fetchRankings,
  fetchUniverseBrowse,
  fetchWatchlist,
  formatSnapshotDate,
  removeFromWatchlist,
  type BrowseResult,
  type CoverageState,
  type RankingItem,
  type RankingsQueryParams,
  type RankingsResponse,
  type WatchlistItem,
} from "@/lib/api";
import { ConvictionBadge } from "@/components/conviction-badge";
import { useUIStore } from "@/lib/store";
import { cn } from "@/lib/utils";

type Market = "US" | "KR";
type AssetType = "stock" | "etf";

interface RankingsFilters {
  market: Market;
  assetType: AssetType;
  conviction: string;
  coverageState?: CoverageState;
  limit: number;
  minFinalScore?: number;
  minConsensusComposite?: number;
  minTechnicalComposite?: number;
  minStrategyPassCount?: number;
  minCanslim?: number;
  minPiotroski?: number;
  minMinervini?: number;
  minWeinstein?: number;
  minRsRating?: number;
  rsLineNewHigh?: boolean;
  preset: string;
}

interface RankingsClientProps {
  initialFilters: RankingsFilters;
  initialData: RankingsResponse | null;
}

type ParamReader = {
  get(name: string): string | null;
};

const COVERAGE_STATES = new Set<CoverageState>([
  "ranked",
  "needs_price",
  "needs_fundamentals",
  "needs_scoring",
  "stale",
]);

const THRESHOLD_KEYS = [
  "conviction",
  "coverage_state",
  "min_final_score",
  "min_consensus_composite",
  "min_technical_composite",
  "min_strategy_pass_count",
  "min_canslim",
  "min_piotroski",
  "min_minervini",
  "min_weinstein",
  "min_rs_rating",
  "rs_line_new_high",
  "preset",
] as const;

const PRESETS = [
  {
    id: "all",
    label: "All Signals",
    description: "No thresholds. See the board as scored.",
    params: {},
  },
  {
    id: "growth",
    label: "Growth",
    description: "CANSLIM plus Minervini leaning, but still gentle.",
    params: {
      min_canslim: "65",
      min_minervini: "60",
      min_strategy_pass_count: "2",
    },
  },
  {
    id: "quality",
    label: "Value Quality",
    description: "Piotroski strength with enough consensus support.",
    params: {
      min_piotroski: "65",
      min_final_score: "55",
      min_strategy_pass_count: "2",
    },
  },
  {
    id: "momentum",
    label: "Momentum",
    description: "Technical composite and RS bias for leadership scans.",
    params: {
      min_technical_composite: "60",
      min_rs_rating: "65",
      min_strategy_pass_count: "2",
    },
  },
  {
    id: "turnaround",
    label: "Turnaround",
    description: "Weinstein posture without demanding perfect scores.",
    params: {
      min_weinstein: "55",
      min_final_score: "50",
    },
  },
  {
    id: "conservative",
    label: "Conservative",
    description: "Higher final score and broader strategy agreement.",
    params: {
      min_final_score: "70",
      min_strategy_pass_count: "3",
    },
  },
] as const;

const SCORE_OPTIONS = ["", "50", "60", "70", "80"] as const;
const PASS_OPTIONS = ["", "1", "2", "3", "4", "5"] as const;
const CONVICTION_OPTIONS = ["", "DIAMOND", "PLATINUM", "GOLD", "SILVER", "BRONZE"] as const;
const LIMIT_OPTIONS = [50, 100, 200] as const;

function parseOptionalNumber(value: string | null, fallback?: number): number | undefined {
  if (value == null || value === "") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseCoverageState(value: string | null, fallback?: CoverageState): CoverageState | undefined {
  if (value == null || value === "") return fallback;
  return COVERAGE_STATES.has(value as CoverageState) ? (value as CoverageState) : fallback;
}

function parseBoolean(value: string | null, fallback?: boolean): boolean | undefined {
  if (value == null || value === "") return fallback;
  if (value === "true") return true;
  if (value === "false") return false;
  return fallback;
}

function readFilters(params: ParamReader, initial: RankingsFilters): RankingsFilters {
  const market = params.get("market") === "KR" ? "KR" : initial.market;
  const assetType = params.get("asset_type") === "etf" ? "etf" : initial.assetType;
  const rawLimit = params.get("limit");
  const parsedLimit = rawLimit ? Number.parseInt(rawLimit, 10) : initial.limit;
  const limit = Number.isFinite(parsedLimit) ? Math.min(Math.max(parsedLimit, 1), 200) : 200;

  return {
    market,
    assetType,
    conviction: params.get("conviction") ?? initial.conviction,
    coverageState: parseCoverageState(params.get("coverage_state"), initial.coverageState),
    limit,
    minFinalScore: parseOptionalNumber(params.get("min_final_score"), initial.minFinalScore),
    minConsensusComposite: parseOptionalNumber(
      params.get("min_consensus_composite"),
      initial.minConsensusComposite
    ),
    minTechnicalComposite: parseOptionalNumber(
      params.get("min_technical_composite"),
      initial.minTechnicalComposite
    ),
    minStrategyPassCount: parseOptionalNumber(
      params.get("min_strategy_pass_count"),
      initial.minStrategyPassCount
    ),
    minCanslim: parseOptionalNumber(params.get("min_canslim"), initial.minCanslim),
    minPiotroski: parseOptionalNumber(params.get("min_piotroski"), initial.minPiotroski),
    minMinervini: parseOptionalNumber(params.get("min_minervini"), initial.minMinervini),
    minWeinstein: parseOptionalNumber(params.get("min_weinstein"), initial.minWeinstein),
    minRsRating: parseOptionalNumber(params.get("min_rs_rating"), initial.minRsRating),
    rsLineNewHigh: parseBoolean(params.get("rs_line_new_high"), initial.rsLineNewHigh),
    preset: params.get("preset") ?? initial.preset,
  };
}

function filtersToQuery(filters: RankingsFilters): RankingsQueryParams {
  return {
    market: filters.market,
    asset_type: filters.assetType,
    conviction: filters.conviction || undefined,
    coverage_state: filters.coverageState,
    limit: filters.limit,
    min_final_score: filters.minFinalScore,
    min_consensus_composite: filters.minConsensusComposite,
    min_technical_composite: filters.minTechnicalComposite,
    min_strategy_pass_count: filters.minStrategyPassCount,
    min_canslim: filters.minCanslim,
    min_piotroski: filters.minPiotroski,
    min_minervini: filters.minMinervini,
    min_weinstein: filters.minWeinstein,
    min_rs_rating: filters.minRsRating,
    rs_line_new_high: filters.rsLineNewHigh,
  };
}

function filtersKey(filters: RankingsFilters): string {
  return JSON.stringify(filtersToQuery(filters));
}

function hasScoreFilters(filters: RankingsFilters): boolean {
  return Boolean(
    filters.conviction ||
      filters.minFinalScore != null ||
      filters.minConsensusComposite != null ||
      filters.minTechnicalComposite != null ||
      filters.minStrategyPassCount != null ||
      filters.minCanslim != null ||
      filters.minPiotroski != null ||
      filters.minMinervini != null ||
      filters.minWeinstein != null ||
      filters.minRsRating != null ||
      filters.rsLineNewHigh != null
  );
}

function activeFilterCount(filters: RankingsFilters): number {
  return [
    filters.conviction,
    filters.coverageState,
    filters.minFinalScore,
    filters.minConsensusComposite,
    filters.minTechnicalComposite,
    filters.minStrategyPassCount,
    filters.minCanslim,
    filters.minPiotroski,
    filters.minMinervini,
    filters.minWeinstein,
    filters.minRsRating,
    filters.rsLineNewHigh,
  ].filter((value) => value != null && value !== "").length;
}

function coverageLabel(state?: CoverageState): string {
  if (!state) return "All coverage";
  return state
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function coverageTone(state?: CoverageState): string {
  if (state === "ranked") {
    return "border-[oklch(0.56_0.11_150_/_0.34)] bg-[oklch(0.84_0.08_150_/_0.18)] text-[oklch(0.33_0.08_150)]";
  }
  if (state === "needs_scoring") {
    return "border-[oklch(0.74_0.12_84_/_0.38)] bg-[oklch(0.88_0.09_84_/_0.24)] text-[oklch(0.42_0.08_78)]";
  }
  if (state === "needs_fundamentals") {
    return "border-[oklch(0.67_0.08_192_/_0.34)] bg-[oklch(0.84_0.07_192_/_0.22)] text-[oklch(0.34_0.07_205)]";
  }
  if (state === "stale") {
    return "border-[oklch(0.72_0.12_55_/_0.34)] bg-[oklch(0.88_0.08_55_/_0.24)] text-[oklch(0.43_0.08_52)]";
  }
  return "border-[oklch(0.55_0.02_248_/_0.28)] bg-white/45 text-[oklch(0.38_0.02_248)]";
}

function displayName(item: Pick<RankingItem | BrowseResult, "market" | "ticker" | "name" | "name_kr">) {
  if (item.market === "KR") {
    return {
      primary: item.name_kr || item.name || item.ticker,
      secondary: item.name_kr ? `${item.ticker} / ${item.name}` : item.ticker,
    };
  }
  return {
    primary: item.name || item.ticker,
    secondary: item.ticker,
  };
}

function scoreTone(score: number): string {
  if (score >= 80) return "text-[oklch(0.43_0.12_150)]";
  if (score >= 65) return "text-[oklch(0.48_0.1_78)]";
  if (score >= 50) return "text-[oklch(0.42_0.08_235)]";
  return "text-[oklch(0.5_0.11_32)]";
}

function scoreBarTone(score: number): string {
  if (score >= 80) return "bg-[oklch(0.61_0.14_150)]";
  if (score >= 65) return "bg-[oklch(0.72_0.14_78)]";
  if (score >= 50) return "bg-[oklch(0.58_0.1_235)]";
  return "bg-[oklch(0.65_0.16_32)]";
}

function formatCompact(value: number): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: value >= 10 ? 0 : 1,
  }).format(value);
}

function FilterSelect({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="grid gap-2">
      <span className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-[oklch(0.46_0.02_250)]">
        {label}
      </span>
      <span className="relative">
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="h-11 w-full appearance-none rounded-2xl border border-[oklch(0.78_0.03_88)] bg-white/75 px-3 pr-9 text-sm font-medium text-[oklch(0.22_0.02_250)] outline-none transition-colors focus:border-[oklch(0.65_0.13_82)]"
        >
          {children}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-[oklch(0.46_0.02_250)]" />
      </span>
    </label>
  );
}

function ScoreMeter({ label, value }: { label: string; value: number }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className="min-w-0">
      <div className="mb-1 flex items-center justify-between gap-2 text-[0.62rem] uppercase tracking-[0.14em] text-[oklch(0.48_0.02_250)]">
        <span>{label}</span>
        <span>{formatCompact(clamped)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[oklch(0.86_0.02_88)]">
        <div
          className={cn("h-full rounded-full", scoreBarTone(clamped))}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}

function CoverageBadge({ state }: { state?: CoverageState }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-[0.62rem] font-semibold uppercase tracking-[0.14em]",
        coverageTone(state)
      )}
    >
      {coverageLabel(state)}
    </span>
  );
}

function PinnedButton({
  ticker,
  market,
  name,
  exchange,
  light = false,
}: {
  ticker: string;
  market: Market;
  name: string;
  exchange?: string;
  light?: boolean;
}) {
  const { getToken } = useAuth();
  const togglePinned = useUIStore((state) => state.togglePinnedInstrument);
  const isPinned = useUIStore((state) => state.isPinned);
  const pinned = isPinned(ticker, market);

  async function handleToggle() {
    togglePinned({ ticker, market, name, exchange: exchange ?? "" });
    try {
      const token = await getToken();
      if (token) {
        if (!pinned) {
          await addToWatchlist(ticker, market, token);
        } else {
          await removeFromWatchlist(ticker, market, token);
        }
      }
    } catch {
      // backend sync is best-effort; local state already updated
    }
  }

  return (
    <button
      type="button"
      onClick={handleToggle}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-2 text-[0.65rem] font-semibold uppercase tracking-[0.14em] transition-colors",
        pinned
          ? "border-[oklch(0.64_0.12_82_/_0.5)] bg-[oklch(0.88_0.1_84_/_0.32)] text-[oklch(0.32_0.06_72)]"
          : light
            ? "border-[oklch(0.78_0.03_88)] bg-white/55 text-[oklch(0.42_0.02_250)] hover:border-[oklch(0.64_0.12_82_/_0.5)]"
            : "border-white/10 text-faint hover:text-white"
      )}
    >
      <Pin className="size-3.5" />
      {pinned ? "Pinned" : "Pin"}
    </button>
  );
}

function RankedCard({ item }: { item: RankingItem }) {
  const names = displayName(item);
  const score = Math.max(0, Math.min(100, item.final_score));
  const strategyScores = [
    ["CAN", item.canslim_score],
    ["PIO", item.piotroski_score],
    ["MIN", item.minervini_score],
    ["WEI", item.weinstein_score],
  ] as const;

  return (
    <article className="group relative overflow-hidden rounded-[1.6rem] border border-[oklch(0.8_0.03_88)] bg-[oklch(0.985_0.012_88_/_0.92)] p-4 shadow-[0_18px_60px_oklch(0.18_0.025_250_/_0.12)] transition-transform duration-300 hover:-translate-y-0.5 sm:p-5">
      <div className="absolute inset-y-0 left-0 w-1 bg-[linear-gradient(180deg,oklch(0.78_0.13_82),oklch(0.62_0.12_190))]" />
      <div className="grid gap-4 xl:grid-cols-[auto_minmax(0,1fr)_minmax(15rem,0.65fr)_auto] xl:items-center">
        <div className="flex items-start justify-between gap-3 xl:block">
          <div className="font-heading text-4xl uppercase leading-none tracking-[-0.06em] text-[oklch(0.28_0.02_250)]">
            #{item.rank}
          </div>
          <div className={cn("font-heading text-5xl leading-none tracking-[-0.06em] xl:mt-4", scoreTone(score))}>
            {score.toFixed(0)}
          </div>
        </div>

        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={buildInstrumentPath(item.ticker, item.market)}
              className="font-heading text-[clamp(1.9rem,5vw,3.1rem)] uppercase leading-[0.9] tracking-[-0.04em] text-[oklch(0.18_0.018_250)] transition-colors hover:text-[oklch(0.5_0.12_82)]"
            >
              {names.primary}
            </Link>
            <ConvictionBadge level={item.conviction_level} size="sm" />
            {item.regime_warning && (
              <span className="inline-flex items-center gap-1 rounded-full border border-[oklch(0.74_0.14_55_/_0.34)] bg-[oklch(0.92_0.08_55_/_0.28)] px-2.5 py-1 text-[0.62rem] font-semibold uppercase tracking-[0.14em] text-[oklch(0.44_0.08_52)]">
                <AlertTriangle className="size-3" />
                Regime
              </span>
            )}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-[oklch(0.46_0.02_250)]">
            <span className="font-semibold">{names.secondary}</span>
            <span>{item.market}</span>
            {item.exchange && <span>{item.exchange}</span>}
            {item.asset_type && <span>{item.asset_type.toUpperCase()}</span>}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <CoverageBadge state={item.coverage_state ?? "ranked"} />
            <span className="rounded-full border border-[oklch(0.78_0.03_88)] bg-white/55 px-2.5 py-1 text-[0.62rem] font-semibold uppercase tracking-[0.14em] text-[oklch(0.42_0.02_250)]">
              {item.strategy_pass_count} strategies
            </span>
            {item.technical_composite != null && (
              <span className="rounded-full border border-[oklch(0.78_0.03_88)] bg-white/55 px-2.5 py-1 text-[0.62rem] font-semibold uppercase tracking-[0.14em] text-[oklch(0.42_0.02_250)]">
                Tech {item.technical_composite.toFixed(0)}
              </span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-2">
          {strategyScores.map(([label, value]) => (
            <ScoreMeter key={label} label={label} value={value} />
          ))}
        </div>

        <div className="flex items-center justify-between gap-3 xl:flex-col xl:items-end">
          <PinnedButton
            ticker={item.ticker}
            market={item.market}
            name={names.primary}
            exchange={item.exchange}
            light
          />
          <Link
            href={buildInstrumentPath(item.ticker, item.market)}
            className="inline-flex items-center gap-2 rounded-full bg-[oklch(0.18_0.018_250)] px-4 py-2 text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-white transition-colors hover:bg-[oklch(0.28_0.03_250)]"
          >
            Open
            <ArrowUpRight className="size-3.5" />
          </Link>
        </div>
      </div>
    </article>
  );
}

function WatchlistCard({
  item,
  market,
}: {
  item: WatchlistItem;
  market: Market;
  }) {
  if (item.market !== market) return null;
  const primaryName =
    item.market === "KR"
      ? item.name_kr || item.name || item.ticker
      : item.name || item.ticker;
  const secondaryName =
    item.market === "KR" && item.name_kr
      ? `${item.ticker} / ${item.name}`
      : item.ticker;

  return (
    <div className="flex items-center justify-between gap-3 rounded-[1.35rem] border border-[oklch(0.64_0.12_82_/_0.28)] bg-[oklch(0.88_0.08_84_/_0.18)] px-4 py-3">
      <div className="min-w-0">
        <Link
          href={buildInstrumentPath(item.ticker, item.market as "US" | "KR")}
          className="block truncate font-heading text-2xl uppercase leading-none text-[oklch(0.22_0.018_250)] transition-colors hover:text-[oklch(0.5_0.12_82)]"
        >
          {primaryName}
        </Link>
        <div className="mt-1 text-xs text-[oklch(0.46_0.02_250)]">{secondaryName}</div>
      </div>
      <PinnedButton
        ticker={item.ticker}
        market={item.market as Market}
        name={primaryName}
        light
      />
    </div>
  );
}

function BrowseCard({ item, label }: { item: BrowseResult; label: string }) {
  const names = displayName(item);
  const reasons = item.ranking_eligibility.reasons.slice(0, 3);

  return (
    <article className="rounded-[1.45rem] border border-white/10 bg-white/[0.06] p-4 backdrop-blur">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="tiny-label text-white/45">{label}</div>
          <Link
            href={buildInstrumentPath(item.ticker, item.market)}
            className="mt-2 block truncate font-heading text-3xl uppercase leading-none text-white transition-colors hover:text-[oklch(0.85_0.12_84)]"
          >
            {names.primary}
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-white/58">
            <span>{names.secondary}</span>
            <span>{item.market}</span>
            <span>{item.exchange}</span>
          </div>
        </div>
        <PinnedButton
          ticker={item.ticker}
          market={item.market}
          name={names.primary}
          exchange={item.exchange}
        />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <CoverageBadge state={item.coverage_state} />
        {item.sector && (
          <span className="rounded-full border border-white/10 px-2.5 py-1 text-[0.62rem] font-semibold uppercase tracking-[0.14em] text-white/60">
            {item.sector}
          </span>
        )}
      </div>
      {reasons.length > 0 && (
        <p className="mt-3 text-xs leading-5 text-white/46">
          {reasons.map((reason) => reason.replaceAll("_", " ")).join(" / ")}
        </p>
      )}
    </article>
  );
}

function SectionShell({
  eyebrow,
  title,
  subtitle,
  children,
  tone = "dark",
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  tone?: "dark" | "light";
}) {
  return (
    <section
      className={cn(
        "rounded-[2rem] border p-4 sm:p-5",
        tone === "light"
          ? "border-[oklch(0.82_0.03_88)] bg-[oklch(0.94_0.018_88_/_0.82)] text-[oklch(0.2_0.018_250)]"
          : "border-white/10 bg-[oklch(0.18_0.018_250_/_0.72)]"
      )}
    >
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className={cn("tiny-label", tone === "light" && "text-[oklch(0.48_0.02_250)]")}>
            {eyebrow}
          </div>
          <h2
            className={cn(
              "mt-2 font-heading text-4xl uppercase leading-none tracking-[-0.04em]",
              tone === "light" ? "text-[oklch(0.18_0.018_250)]" : "text-white"
            )}
          >
            {title}
          </h2>
        </div>
        {subtitle && (
          <p className={cn("max-w-xl text-sm leading-6", tone === "light" ? "text-[oklch(0.42_0.02_250)]" : "text-white/54")}>
            {subtitle}
          </p>
        )}
      </div>
      {children}
    </section>
  );
}

export function RankingsClient({ initialFilters, initialData }: RankingsClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { getToken, isSignedIn } = useAuth();
  const [isPending, startTransition] = useTransition();
  const [partialLimit, setPartialLimit] = useState(8);
  const [exploreLimit, setExploreLimit] = useState(8);
  const filters = readFilters(searchParams, initialFilters);
  const key = filtersKey(filters);
  const initialKey = filtersKey(initialFilters);
  const queryParams = filtersToQuery(filters);
  const scoreFiltersActive = hasScoreFilters(filters);
  const activeFilters = activeFilterCount(filters);
  const showPartial = !scoreFiltersActive && (!filters.coverageState || filters.coverageState === "needs_scoring");
  const showExplore =
    !scoreFiltersActive &&
    filters.coverageState !== "ranked" &&
    filters.coverageState !== "needs_scoring";
  const exploreCoverage =
    filters.coverageState && filters.coverageState !== "ranked" ? filters.coverageState : undefined;

  const rankings = useQuery({
    queryKey: ["rankings", "desk", key],
    queryFn: () => fetchRankings(queryParams),
    initialData: key === initialKey ? initialData ?? undefined : undefined,
    staleTime: 30_000,
    retry: (failureCount, queryError) =>
      queryError instanceof APIError && queryError.status >= 500 && failureCount < 2,
  });

  const partial = useQuery({
    queryKey: ["universe-browse", "partial", filters.market, filters.assetType, partialLimit],
    queryFn: () =>
      fetchUniverseBrowse({
        market: filters.market,
        asset_type: filters.assetType,
        coverage_state: "needs_scoring",
        exclude_ranked: true,
        limit: partialLimit,
      }),
    enabled: showPartial,
    staleTime: 60_000,
  });

  const explore = useQuery({
    queryKey: [
      "universe-browse",
      "explore",
      filters.market,
      filters.assetType,
      exploreCoverage ?? "all",
      exploreLimit,
    ],
    queryFn: () =>
      fetchUniverseBrowse({
        market: filters.market,
        asset_type: filters.assetType,
        coverage_state: exploreCoverage,
        exclude_ranked: true,
        limit: exploreLimit,
      }),
    enabled: showExplore,
    staleTime: 60_000,
  });

  const watchlist = useQuery({
    queryKey: ["watchlist", isSignedIn],
    queryFn: async () => {
      const token = await getToken();
      if (!token) return null;
      return fetchWatchlist(token);
    },
    enabled: !!isSignedIn,
    staleTime: 60_000,
  });

  const pinnedInstruments = useUIStore((state) => state.pinnedInstruments);
  const watchlistItems: WatchlistItem[] = watchlist.data?.items ?? [];
  // Merge: prefer backend items when signed in, else show local pins as stub items
  const watchlistDisplay: WatchlistItem[] =
    isSignedIn && watchlistItems.length > 0
      ? watchlistItems.filter((item) => item.market === filters.market)
      : pinnedInstruments
          .filter((pin) => pin.market === filters.market)
          .map((pin, idx) => ({
            id: -idx,
            instrument_id: -1,
            market: pin.market,
            ticker: pin.ticker,
            name: pin.name,
            added_at: new Date().toISOString(),
          }));

  const data = rankings.data;
  const rankedItems = data?.items ?? [];
  const averageScore =
    rankedItems.length > 0
      ? rankedItems.reduce((sum, item) => sum + item.final_score, 0) / rankedItems.length
      : 0;
  const topScore = rankedItems[0]?.final_score ?? 0;
  const partialItems = partial.data?.items ?? [];
  const exploreItems = (explore.data?.items ?? []).filter(
    (item) => exploreCoverage || item.coverage_state !== "needs_scoring"
  );
  const currentPreset = PRESETS.find((preset) => preset.id === filters.preset) ?? PRESETS[0];

  function replaceParams(updates: Record<string, string | number | boolean | null | undefined>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [field, value] of Object.entries(updates)) {
      if (value == null || value === "") {
        params.delete(field);
      } else {
        params.set(field, String(value));
      }
    }
    startTransition(() => {
      router.replace(`/app/rankings?${params.toString()}`, { scroll: false });
    });
  }

  function setFilter(keyName: string, value: string | number | boolean | null | undefined) {
    replaceParams({ [keyName]: value, preset: keyName === "preset" ? value : "custom" });
  }

  function clearFilters() {
    const clears = Object.fromEntries(THRESHOLD_KEYS.map((name) => [name, null]));
    replaceParams({ ...clears, preset: "all" });
  }

  function applyPreset(preset: (typeof PRESETS)[number]) {
    const clears = Object.fromEntries(THRESHOLD_KEYS.map((name) => [name, null]));
    replaceParams({
      ...clears,
      ...preset.params,
      preset: preset.id,
    });
  }

  return (
    <div className="app-shell py-4 sm:py-6">
      <section className="relative isolate overflow-hidden rounded-[2.4rem] border border-[oklch(0.76_0.04_88)] bg-[oklch(0.94_0.018_88)] px-4 py-5 text-[oklch(0.2_0.018_250)] shadow-[0_30px_120px_oklch(0.08_0.015_250_/_0.34)] sm:px-6 sm:py-7">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_12%_12%,oklch(0.82_0.13_82_/_0.22),transparent_28%),radial-gradient(circle_at_82%_8%,oklch(0.7_0.08_195_/_0.18),transparent_25%),linear-gradient(135deg,transparent,oklch(0.99_0.012_88_/_0.72))]" />
        <div className="absolute inset-x-0 top-0 -z-10 h-24 bg-[repeating-linear-gradient(90deg,oklch(0.25_0.02_250_/_0.08)_0_1px,transparent_1px_54px)] opacity-60" />

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(22rem,0.7fr)] xl:items-end">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-[oklch(0.78_0.04_88)] bg-white/55 px-3 py-1.5 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[oklch(0.42_0.02_250)]">
              <Sparkles className="size-3.5" />
              Production rankings desk
            </div>
            <h1 className="mt-4 max-w-5xl font-heading text-[clamp(4rem,10vw,8rem)] uppercase leading-[0.82] tracking-[-0.07em] text-[oklch(0.16_0.018_250)]">
              Signal Board
            </h1>
            <p className="mt-5 max-w-3xl text-sm leading-7 text-[oklch(0.38_0.02_250)] sm:text-base">
              Ranked names stay score-backed. Partial and explore rows sit underneath so we can
              surface more of the US/KR universe without pretending incomplete data is ranked.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
            <div className="rounded-[1.5rem] border border-[oklch(0.8_0.03_88)] bg-white/58 p-4">
              <div className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-[oklch(0.48_0.02_250)]">
                Loaded
              </div>
              <div className="mt-2 font-heading text-4xl uppercase tracking-[-0.04em]">
                {rankedItems.length}/{data?.total ?? 0}
              </div>
              <div className="mt-1 text-xs text-[oklch(0.46_0.02_250)]">
                Top {filters.limit} requested
              </div>
            </div>
            <div className="rounded-[1.5rem] border border-[oklch(0.8_0.03_88)] bg-white/58 p-4">
              <div className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-[oklch(0.48_0.02_250)]">
                Top score
              </div>
              <div className={cn("mt-2 font-heading text-4xl uppercase tracking-[-0.04em]", scoreTone(topScore))}>
                {topScore ? topScore.toFixed(1) : "--"}
              </div>
              <div className="mt-1 text-xs text-[oklch(0.46_0.02_250)]">
                Average {averageScore ? averageScore.toFixed(1) : "--"}
              </div>
            </div>
            <div className="rounded-[1.5rem] border border-[oklch(0.8_0.03_88)] bg-white/58 p-4">
              <div className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-[oklch(0.48_0.02_250)]">
                Freshness
              </div>
              <div className="mt-2 text-lg font-semibold">
                {data?.score_date ? formatSnapshotDate(data.score_date) : "Waiting"}
              </div>
              <div className="mt-1 text-xs text-[oklch(0.46_0.02_250)]">
                {rankings.isFetching || isPending ? "Refreshing view" : `${activeFilters} active filters`}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.42fr)]">
        <div className="surface-panel rounded-[2rem] px-4 py-4 sm:px-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="tiny-label">Market and result controls</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(["US", "KR"] as const).map((market) => (
                  <button
                    key={market}
                    type="button"
                    onClick={() => replaceParams({ market })}
                    className="filter-chip px-4 py-2 text-sm font-semibold"
                    data-active={filters.market === market}
                  >
                    {market === "US" ? "US Market" : "Korea Market"}
                  </button>
                ))}
                {(["stock", "etf"] as const).map((assetType) => (
                  <button
                    key={assetType}
                    type="button"
                    onClick={() => replaceParams({ asset_type: assetType })}
                    className="filter-chip px-4 py-2 text-sm font-semibold"
                    data-active={filters.assetType === assetType}
                  >
                    {assetType.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="tiny-label lg:text-right">Result count</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {LIMIT_OPTIONS.map((limit) => (
                  <button
                    key={limit}
                    type="button"
                    onClick={() => replaceParams({ limit })}
                    className="filter-chip px-4 py-2 text-sm font-semibold"
                    data-active={filters.limit === limit}
                  >
                    Top {limit}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="surface-panel rounded-[2rem] px-4 py-4 sm:px-5">
          <div className="tiny-label">Current lens</div>
          <div className="mt-3 flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-2xl border border-white/10 bg-black/14">
              <Filter className="size-5 text-white" />
            </div>
            <div>
              <div className="text-sm font-semibold text-white">{currentPreset.label}</div>
              <div className="text-xs leading-5 text-faint">{currentPreset.description}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-5 surface-panel rounded-[2rem] px-4 py-4 sm:px-5">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="tiny-label">Strategy presets</div>
              <h2 className="mt-2 font-heading text-4xl uppercase tracking-[-0.04em] text-white">
                Gentle filters, not a black box.
              </h2>
            </div>
            <button
              type="button"
              onClick={clearFilters}
              className="inline-flex items-center gap-2 self-start rounded-full border border-white/10 px-4 py-2 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-faint transition-colors hover:text-white sm:self-auto"
            >
              <RefreshCw className="size-3.5" />
              Reset filters
            </button>
          </div>

          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-6">
            {PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => applyPreset(preset)}
                className={cn(
                  "rounded-[1.35rem] border px-4 py-4 text-left transition-all",
                  filters.preset === preset.id
                    ? "border-[oklch(0.78_0.11_84_/_0.48)] bg-[oklch(0.8_0.11_84_/_0.14)] text-white"
                    : "border-white/8 bg-black/10 text-faint hover:border-white/16 hover:text-white"
                )}
              >
                <div className="text-sm font-semibold">{preset.label}</div>
                <div className="mt-2 text-xs leading-5 opacity-76">{preset.description}</div>
              </button>
            ))}
          </div>

          <details className="group rounded-[1.6rem] border border-white/10 bg-black/12">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-4 text-sm font-semibold text-white">
              <span className="inline-flex items-center gap-2">
                <Search className="size-4" />
                Advanced filter panel
              </span>
              <ChevronDown className="size-4 transition-transform group-open:rotate-180" />
            </summary>
            <div className="grid gap-3 border-t border-white/8 px-4 py-4 md:grid-cols-2 xl:grid-cols-4">
              <FilterSelect
                label="Conviction"
                value={filters.conviction}
                onChange={(value) => setFilter("conviction", value || null)}
              >
                {CONVICTION_OPTIONS.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option || "Any conviction"}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="Coverage"
                value={filters.coverageState ?? ""}
                onChange={(value) => setFilter("coverage_state", value || null)}
              >
                <option value="">Any coverage</option>
                {[...COVERAGE_STATES].map((state) => (
                  <option key={state} value={state}>
                    {coverageLabel(state)}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="Final score"
                value={filters.minFinalScore?.toString() ?? ""}
                onChange={(value) => setFilter("min_final_score", value || null)}
              >
                {SCORE_OPTIONS.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option ? `${option}+` : "No minimum"}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="Strategy count"
                value={filters.minStrategyPassCount?.toString() ?? ""}
                onChange={(value) => setFilter("min_strategy_pass_count", value || null)}
              >
                {PASS_OPTIONS.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option ? `${option}+ passing` : "No minimum"}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="Technical"
                value={filters.minTechnicalComposite?.toString() ?? ""}
                onChange={(value) => setFilter("min_technical_composite", value || null)}
              >
                {SCORE_OPTIONS.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option ? `${option}+` : "No minimum"}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="CANSLIM"
                value={filters.minCanslim?.toString() ?? ""}
                onChange={(value) => setFilter("min_canslim", value || null)}
              >
                {SCORE_OPTIONS.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option ? `${option}+` : "No minimum"}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="Piotroski"
                value={filters.minPiotroski?.toString() ?? ""}
                onChange={(value) => setFilter("min_piotroski", value || null)}
              >
                {SCORE_OPTIONS.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option ? `${option}+` : "No minimum"}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="Minervini"
                value={filters.minMinervini?.toString() ?? ""}
                onChange={(value) => setFilter("min_minervini", value || null)}
              >
                {SCORE_OPTIONS.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option ? `${option}+` : "No minimum"}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="Weinstein"
                value={filters.minWeinstein?.toString() ?? ""}
                onChange={(value) => setFilter("min_weinstein", value || null)}
              >
                {SCORE_OPTIONS.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option ? `${option}+` : "No minimum"}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="RS Rating"
                value={filters.minRsRating?.toString() ?? ""}
                onChange={(value) => setFilter("min_rs_rating", value || null)}
              >
                {SCORE_OPTIONS.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option ? `${option}+` : "No minimum"}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="RS New High"
                value={filters.rsLineNewHigh == null ? "" : String(filters.rsLineNewHigh)}
                onChange={(value) => setFilter("rs_line_new_high", value || null)}
              >
                <option value="">Any</option>
                <option value="true">Required</option>
                <option value="false">Exclude</option>
              </FilterSelect>
            </div>
          </details>
        </div>
      </section>

      {(data?.regime_warning_count ?? 0) > 0 && (
        <div className="mt-5 flex items-center gap-3 rounded-[1.65rem] border border-[oklch(0.78_0.18_55_/_0.35)] bg-[oklch(0.35_0.07_55_/_0.15)] px-5 py-3 text-sm text-[oklch(0.9_0.06_75)]">
          <AlertTriangle className="size-4 shrink-0" />
          {data!.regime_warning_count} ranked instruments have an active regime warning.
        </div>
      )}

      <div className="mt-5 grid gap-5">
        {watchlistDisplay.length > 0 && (
          <SectionShell eyebrow="Your watchlist" title="Pinned instruments" tone="light">
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {watchlistDisplay.map((item) => (
                <WatchlistCard
                  key={`wl-${item.market}-${item.ticker}`}
                  item={item}
                  market={filters.market}
                />
              ))}
            </div>
            {watchlistDisplay.length === 0 && (
              <p className="text-sm text-[oklch(0.46_0.02_250)]">
                No pinned instruments for this market yet. Pin a row from the board below.
              </p>
            )}
            {!isSignedIn && (
              <p className="mt-3 text-xs text-[oklch(0.52_0.02_250)]">
                <Bookmark className="mr-1 inline size-3" />
                Sign in to sync your watchlist across devices.
              </p>
            )}
          </SectionShell>
        )}

        <SectionShell
          eyebrow="Ranked results"
          title={`${filters.market} ${filters.assetType === "etf" ? "ETF" : "stock"} leaderboard`}
          subtitle="These rows are backed by stored consensus scores. Use filters to narrow the ranked board without changing the underlying order."
          tone="light"
        >
          {rankings.error && (
            <div className="rounded-[1.4rem] border border-[oklch(0.68_0.18_28_/_0.3)] bg-[oklch(0.96_0.04_28_/_0.54)] px-5 py-4 text-sm text-[oklch(0.42_0.12_28)]">
              {rankings.error instanceof APIError
                ? rankings.error.detail ?? "Rankings are temporarily unavailable."
                : "Rankings are temporarily unavailable."}
            </div>
          )}

          {!rankings.error && rankedItems.length === 0 && !rankings.isFetching && (
            <div className="rounded-[1.4rem] border border-[oklch(0.8_0.03_88)] bg-white/55 px-5 py-8 text-center text-sm text-[oklch(0.42_0.02_250)]">
              No ranked instruments match this lens yet. Try removing thresholds or browse the
              incomplete universe below.
            </div>
          )}

          <div className="grid gap-3">
            {rankedItems.map((item) => (
              <RankedCard key={`${item.market}-${item.ticker}-${item.rank}`} item={item} />
            ))}
          </div>

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm text-[oklch(0.42_0.02_250)]">
              {rankings.isFetching || isPending ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="size-4 animate-spin" />
                  Refreshing the desk
                </span>
              ) : (
                `Showing ${rankedItems.length} of ${data?.total ?? 0} ranked rows`
              )}
            </div>
            {data?.pagination.has_more && filters.limit < 200 && (
              <button
                type="button"
                onClick={() => replaceParams({ limit: Math.min(filters.limit + 50, 200) })}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-[oklch(0.18_0.018_250)] px-5 py-3 text-sm font-semibold uppercase tracking-[0.16em] text-white transition-colors hover:bg-[oklch(0.28_0.03_250)]"
              >
                Load more ranked names
                <BarChart3 className="size-4" />
              </button>
            )}
          </div>
        </SectionShell>

        {showPartial && (
          <SectionShell
            eyebrow="Partial rows"
            title="Ready for scoring"
            subtitle="These symbols have enough persisted coverage to be interesting, but they are not part of the ranked board until scoring runs."
          >
            {partial.error ? (
              <div className="rounded-[1.35rem] border border-white/10 bg-black/12 px-4 py-4 text-sm text-faint">
                Partial rows are unavailable, but ranked results are unaffected.
              </div>
            ) : partialItems.length === 0 && !partial.isFetching ? (
              <div className="rounded-[1.35rem] border border-white/10 bg-black/12 px-4 py-5 text-sm text-faint">
                No needs-scoring symbols are available for this market yet.
              </div>
            ) : (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {partialItems.map((item) => (
                  <BrowseCard key={`partial-${item.market}-${item.ticker}`} item={item} label="Needs scoring" />
                ))}
              </div>
            )}
            {partial.data?.pagination.has_more && (
              <button
                type="button"
                onClick={() => setPartialLimit((value) => Math.min(value + 8, 200))}
                className="mt-4 inline-flex items-center gap-2 rounded-full border border-white/10 px-5 py-3 text-sm font-semibold uppercase tracking-[0.16em] text-faint transition-colors hover:text-white"
              >
                Load more partial rows
                <LineChart className="size-4" />
              </button>
            )}
          </SectionShell>
        )}

        {showExplore && (
          <SectionShell
            eyebrow="Explore more"
            title="Known but incomplete"
            subtitle="Discovery-only rows from the covered universe. They do not affect ranking totals and never claim a score they do not have."
          >
            {explore.error ? (
              <div className="rounded-[1.35rem] border border-white/10 bg-black/12 px-4 py-4 text-sm text-faint">
                Explore More is unavailable, but ranked results are unaffected.
              </div>
            ) : exploreItems.length === 0 && !explore.isFetching ? (
              <div className="rounded-[1.35rem] border border-white/10 bg-black/12 px-4 py-5 text-sm text-faint">
                No additional discoverable rows match this market and asset type.
              </div>
            ) : (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {exploreItems.map((item) => (
                  <BrowseCard key={`explore-${item.market}-${item.ticker}`} item={item} label="Explore" />
                ))}
              </div>
            )}
            {explore.data?.pagination.has_more && (
              <button
                type="button"
                onClick={() => setExploreLimit((value) => Math.min(value + 8, 200))}
                className="mt-4 inline-flex items-center gap-2 rounded-full border border-white/10 px-5 py-3 text-sm font-semibold uppercase tracking-[0.16em] text-faint transition-colors hover:text-white"
              >
                Load more explore rows
                <ShieldCheck className="size-4" />
              </button>
            )}
          </SectionShell>
        )}
      </div>
    </div>
  );
}
