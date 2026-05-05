"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import {
  AlertTriangle,
  ArrowUpRight,
  Bookmark,
  ChevronDown,
  Filter,
  Loader2,
  Pin,
  RefreshCw,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import {
  APIError,
  addToWatchlist,
  buildInstrumentPath,
  fetchRankings,
  fetchWatchlist,
  formatSnapshotDate,
  removeFromWatchlist,
  type CoverageState,
  type RankingItem,
  type RankingsQueryParams,
  type RankingsResponse,
  type WatchlistItem,
} from "@/lib/api";
import { ConvictionBadge } from "@/components/conviction-badge";
import { useUIStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { useT } from "@/hooks/use-t";

type Market = "US" | "KR";
type AssetType = "stock";

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
  const assetType: AssetType = "stock";
  // Default limit bumped up — no more artificial cap selector
  const rawLimit = params.get("limit");
  const parsedLimit = rawLimit ? Number.parseInt(rawLimit, 10) : initial.limit;
  const limit = Number.isFinite(parsedLimit) ? Math.min(Math.max(parsedLimit, 1), 500) : 200;

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

/** Strip legal boilerplate suffixes from US stock names for cleaner display. */
function cleanDisplayName(name: string, market: "US" | "KR"): string {
  if (market !== "US" || !name) return name;
  return name
    .replace(/\s*[-–]\s*(common\s+stock|class\s+[a-z][\w\s]*|ordinary\s+shares?|adr|ads|units?)\s*$/i, "")
    .replace(/\s+(common\s+stock)\s*$/i, "")
    .trim();
}

function displayName(item: Pick<RankingItem, "market" | "ticker" | "name" | "name_kr">) {
  if (item.market === "KR") {
    return {
      primary: item.name_kr || item.name || item.ticker,
      secondary: item.name_kr ? `${item.ticker} / ${item.name}` : item.ticker,
    };
  }
  const clean = cleanDisplayName(item.name || item.ticker, "US");
  return {
    primary: clean,
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
  const { t } = useT();
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
      {pinned ? t("ui.pinned") : t("ui.pin")}
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
    <article className="group relative overflow-hidden rounded-[1.4rem] border border-[oklch(0.8_0.03_88)] bg-[oklch(0.985_0.012_88_/_0.92)] transition-transform duration-300 md:shadow-[0_18px_60px_oklch(0.18_0.025_250_/_0.12)] md:hover:-translate-y-0.5">
      <div className="absolute inset-y-0 left-0 w-1 bg-[linear-gradient(180deg,oklch(0.78_0.13_82),oklch(0.62_0.12_190))]" />

      {/* ── Mobile compact row (< md) ── */}
      <Link
        href={buildInstrumentPath(item.ticker, item.market)}
        className="md:hidden flex items-center gap-3 pl-5 pr-4 py-3.5 active:bg-black/5 transition-colors"
      >
        {/* Rank */}
        <div className="w-7 shrink-0 text-right">
          <span className="text-[0.6rem] font-semibold uppercase text-faint leading-none">#{item.rank}</span>
        </div>

        {/* Name + mini bars */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-semibold text-sm text-[oklch(0.18_0.018_250)] shrink-0 tabular-nums">{item.ticker}</span>
            <ConvictionBadge level={item.conviction_level} size="sm" />
          </div>
          <div className="mt-0.5 truncate text-[0.72rem] text-faint leading-snug">{names.primary}</div>
          <div className="mt-2 flex gap-2">
            {strategyScores.map(([label, value]) => (
              <div key={label} className="flex-1 min-w-0">
                <div className="text-[0.5rem] uppercase tracking-wide text-faint text-center leading-none mb-0.5">{label}</div>
                <div className="h-[3px] bg-[oklch(0.86_0.02_88)] rounded-full overflow-hidden">
                  <div
                    className={cn("h-full rounded-full", scoreBarTone(Math.min(100, value)))}
                    style={{ width: `${Math.min(100, value)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Score + arrow */}
        <div className="shrink-0 flex items-center gap-1.5">
          <span className={cn("font-mono text-lg font-bold leading-none tabular-nums", scoreTone(score))}>
            {score.toFixed(0)}
          </span>
          <ArrowUpRight className="size-3.5 text-faint" />
        </div>
      </Link>

      {/* ── Desktop full card (md+) ── */}
      <div className="hidden md:block p-5">
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
                className="font-heading text-[clamp(1.6rem,3.5vw,2.8rem)] uppercase leading-[1.05] tracking-[-0.04em] text-[oklch(0.18_0.018_250)] transition-colors hover:text-[oklch(0.5_0.12_82)] line-clamp-2"
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
                {item.strategy_pass_count} {item.strategy_pass_count === 1 ? "strategy" : "strategies"}
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

export function RankingsClient({ initialFilters, initialData }: RankingsClientProps) {
  const { t } = useT();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { getToken, isSignedIn } = useAuth();
  const [isPending, startTransition] = useTransition();
  const [showAdvanced, setShowAdvanced] = useState(false);
  const filters = readFilters(searchParams, initialFilters);
  const key = filtersKey(filters);
  const initialKey = filtersKey(initialFilters);
  const queryParams = filtersToQuery(filters);
  const activeFilters = activeFilterCount(filters);

  const rankings = useQuery({
    queryKey: ["rankings", "desk", key],
    queryFn: () => fetchRankings(queryParams),
    initialData: key === initialKey ? initialData ?? undefined : undefined,
    staleTime: 30_000,
    retry: (failureCount, queryError) =>
      queryError instanceof APIError && queryError.status >= 500 && failureCount < 2,
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
      router.replace(`/rankings?${params.toString()}`, { scroll: false });
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
    <div className="app-shell py-3 sm:py-5">

      {/* ── Compact control bar ─────────────────────────────────────────── */}
      <div className="surface-panel rounded-[1.65rem] px-4 py-3 sm:px-5">
            {/* Row 1: Market toggle + inline stats */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {/* Market toggle */}
            <div className="flex gap-1 rounded-[1rem] border border-white/8 bg-black/16 p-1">
              {(["US", "KR"] as const).map((market) => (
                <button
                  key={market}
                  type="button"
                  onClick={() => replaceParams({ market })}
                  className={cn(
                    "rounded-[0.75rem] px-4 py-1.5 text-sm font-semibold transition-colors",
                    filters.market === market
                      ? "bg-white text-[oklch(0.18_0.018_250)]"
                      : "text-faint hover:text-white"
                  )}
                >
                  {market === "US" ? t("rankings.controls.usMarket") : t("rankings.controls.krMarket")}
                </button>
              ))}
            </div>
          </div>

          {/* Right: stats + filter toggle */}
          <div className="flex items-center gap-3">
            {/* Inline stats */}
            <div className="hidden items-center gap-4 text-xs sm:flex">
              {data?.score_date && (
                <span className="text-faint">{formatSnapshotDate(data.score_date)}</span>
              )}
              {topScore > 0 && (
                <span className="font-medium text-white/70">
                  <span className={cn("font-bold", scoreTone(topScore))}>{topScore.toFixed(0)}</span>
                  <span className="mx-1 text-faint">/</span>
                  <span className="text-faint">{averageScore.toFixed(0)} avg</span>
                </span>
              )}
              <span className="text-faint">
                {rankings.isFetching || isPending ? (
                  <Loader2 className="inline size-3 animate-spin" />
                ) : (
                  `${rankedItems.length} of ${data?.total ?? 0}`
                )}
              </span>
            </div>

            {/* Filter toggle button */}
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className={cn(
                "inline-flex items-center gap-2 rounded-full border px-3 py-2 text-[0.72rem] font-semibold uppercase tracking-[0.12em] transition-colors",
                showAdvanced || activeFilters > 0
                  ? "border-[oklch(0.78_0.11_84_/_0.48)] bg-[oklch(0.8_0.11_84_/_0.14)] text-white"
                  : "border-white/10 text-faint hover:text-white"
              )}
            >
              <SlidersHorizontal className="size-3.5" />
              {activeFilters > 0 ? `${activeFilters} ${t("rankings.stat.activeFilters")}` : t("rankings.presets.advanced")}
            </button>
          </div>
        </div>

        {/* Row 2 (mobile): inline stats */}
        <div className="mt-2 flex items-center gap-3 text-xs sm:hidden">
          {data?.score_date && (
            <span className="text-faint">{formatSnapshotDate(data.score_date)}</span>
          )}
          <span className="text-faint">
            {rankings.isFetching || isPending ? (
              <Loader2 className="inline size-3 animate-spin" />
            ) : (
              `${rankedItems.length} of ${data?.total ?? 0} ranked`
            )}
          </span>
          {topScore > 0 && (
            <span>
              <span className={cn("font-bold", scoreTone(topScore))}>{topScore.toFixed(0)}</span>
              <span className="text-faint"> top</span>
            </span>
          )}
        </div>
      </div>

      {/* ── Filter panel (collapsible) ─────────────────────────────────── */}
      {showAdvanced && (
        <div className="mt-3 surface-panel rounded-[1.65rem] px-4 py-4 sm:px-5">
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="tiny-label">{t("rankings.presets.kicker")}</div>
                <h2 className="mt-1 font-heading text-xl sm:text-2xl uppercase tracking-[-0.04em] leading-tight text-white">
                  {t("rankings.presets.headline")}
                </h2>
              </div>
              <button
                type="button"
                onClick={clearFilters}
                className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-2 text-[0.72rem] font-semibold uppercase tracking-[0.12em] text-faint transition-colors hover:text-white"
              >
                <RefreshCw className="size-3" />
                {t("rankings.presets.reset")}
              </button>
            </div>

            {/* Preset pills — scrollable on mobile */}
            <div className="flex gap-2 overflow-x-auto pb-1 md:grid md:grid-cols-3 xl:grid-cols-6 md:overflow-x-visible md:pb-0">
              {PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => applyPreset(preset)}
                  className={cn(
                    "shrink-0 rounded-[1.2rem] border px-4 py-3 text-left transition-all md:shrink",
                    filters.preset === preset.id
                      ? "border-[oklch(0.78_0.11_84_/_0.48)] bg-[oklch(0.8_0.11_84_/_0.14)] text-white"
                      : "border-white/8 bg-black/10 text-faint hover:border-white/16 hover:text-white"
                  )}
                  style={{ minWidth: "9rem" }}
                >
                  <div className="text-sm font-semibold">{preset.label}</div>
                  <div className="mt-1 text-[0.7rem] leading-4 opacity-76">{preset.description}</div>
                </button>
              ))}
            </div>

            {/* Advanced filter grid */}
            <details className="group rounded-[1.4rem] border border-white/10 bg-black/12">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 text-sm font-semibold text-white">
                <span className="inline-flex items-center gap-2">
                  <Search className="size-4" />
                  {t("rankings.presets.advanced")}
                </span>
                <ChevronDown className="size-4 transition-transform group-open:rotate-180" />
              </summary>
              <div className="grid gap-3 border-t border-white/8 px-4 py-4 md:grid-cols-2 xl:grid-cols-4">
                <FilterSelect
                  label={t("rankings.filters.conviction")}
                  value={filters.conviction}
                  onChange={(value) => setFilter("conviction", value || null)}
                >
                  {CONVICTION_OPTIONS.map((option) => (
                    <option key={option || "all"} value={option}>
                      {option || t("rankings.filters.anyConviction")}
                    </option>
                  ))}
                </FilterSelect>
                <FilterSelect
                  label={t("rankings.filters.finalScore")}
                  value={filters.minFinalScore?.toString() ?? ""}
                  onChange={(value) => setFilter("min_final_score", value || null)}
                >
                  {SCORE_OPTIONS.map((option) => (
                    <option key={option || "all"} value={option}>
                      {option ? `${option}+` : t("rankings.filters.noMinimum")}
                    </option>
                  ))}
                </FilterSelect>
                <FilterSelect
                  label={t("rankings.filters.strategyCount")}
                  value={filters.minStrategyPassCount?.toString() ?? ""}
                  onChange={(value) => setFilter("min_strategy_pass_count", value || null)}
                >
                  {PASS_OPTIONS.map((option) => (
                    <option key={option || "all"} value={option}>
                      {option ? `${option}+ passing` : t("rankings.filters.noPassing")}
                    </option>
                  ))}
                </FilterSelect>
                <FilterSelect
                  label={t("rankings.filters.technical")}
                  value={filters.minTechnicalComposite?.toString() ?? ""}
                  onChange={(value) => setFilter("min_technical_composite", value || null)}
                >
                  {SCORE_OPTIONS.map((option) => (
                    <option key={option || "all"} value={option}>
                      {option ? `${option}+` : t("rankings.filters.noMinimum")}
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
                  label={t("rankings.filters.rsNewHigh")}
                  value={filters.rsLineNewHigh == null ? "" : String(filters.rsLineNewHigh)}
                  onChange={(value) => setFilter("rs_line_new_high", value || null)}
                >
                  <option value="">{t("rankings.filters.any")}</option>
                  <option value="true">{t("rankings.filters.required")}</option>
                  <option value="false">{t("rankings.filters.exclude")}</option>
                </FilterSelect>
              </div>
            </details>

            {/* Active lens summary */}
            <div className="flex items-center gap-3 rounded-[1.2rem] border border-white/8 bg-black/10 px-4 py-3">
              <Filter className="size-4 text-faint" />
              <div>
                <div className="text-sm font-semibold text-white">{currentPreset.label}</div>
                <div className="text-xs leading-5 text-faint">{currentPreset.description}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Regime warning ─────────────────────────────────────────────── */}
      {(data?.regime_warning_count ?? 0) > 0 && (
        <div className="mt-3 flex items-center gap-3 rounded-[1.4rem] border border-[oklch(0.78_0.18_55_/_0.35)] bg-[oklch(0.35_0.07_55_/_0.15)] px-5 py-3 text-sm text-[oklch(0.9_0.06_75)]">
          <AlertTriangle className="size-4 shrink-0" />
          {data!.regime_warning_count} {t("rankings.regime.warning")}
        </div>
      )}

      <div className="mt-3 grid gap-4">
        {/* ── Watchlist ──────────────────────────────────────────────── */}
        {watchlistDisplay.length > 0 && (
          <section className="rounded-[1.8rem] border border-[oklch(0.82_0.03_88)] bg-[oklch(0.94_0.018_88_/_0.82)] px-4 py-4 text-[oklch(0.2_0.018_250)] sm:px-5">
            <div className="tiny-label text-[oklch(0.48_0.02_250)]">{t("rankings.watchlist.eyebrow")}</div>
            <h2 className="mt-1 font-heading text-xl uppercase tracking-[-0.03em] text-[oklch(0.18_0.018_250)] sm:text-2xl">
              {t("rankings.watchlist.title")}
            </h2>
            <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {watchlistDisplay.map((item) => (
                <WatchlistCard
                  key={`wl-${item.market}-${item.ticker}`}
                  item={item}
                  market={filters.market}
                />
              ))}
            </div>
            {!isSignedIn && (
              <p className="mt-3 text-xs text-[oklch(0.52_0.02_250)]">
                <Bookmark className="mr-1 inline size-3" />
                {t("rankings.watchlist.signIn")}
              </p>
            )}
          </section>
        )}

        {/* ── Leaderboard ────────────────────────────────────────────── */}
        <section className="rounded-[1.8rem] border border-[oklch(0.82_0.03_88)] bg-[oklch(0.94_0.018_88_/_0.82)] px-4 py-4 text-[oklch(0.2_0.018_250)] sm:px-5">
          <div className="mb-3 flex items-end justify-between gap-3">
            <div>
              <div className="tiny-label text-[oklch(0.48_0.02_250)]">{t("rankings.leaderboard.eyebrow")}</div>
              <h2 className="mt-1 font-heading text-xl uppercase tracking-[-0.03em] text-[oklch(0.18_0.018_250)] sm:text-2xl break-words">
                {filters.market} {t("ui.stock").toLowerCase()} leaderboard
              </h2>
            </div>
          </div>

          {rankings.error && (
            <div className="rounded-[1.2rem] border border-[oklch(0.68_0.18_28_/_0.3)] bg-[oklch(0.96_0.04_28_/_0.54)] px-5 py-4 text-sm text-[oklch(0.42_0.12_28)]">
              {rankings.error instanceof APIError
                ? rankings.error.detail ?? t("rankings.leaderboard.error")
                : t("rankings.leaderboard.error")}
            </div>
          )}

          {!rankings.error && rankedItems.length === 0 && !rankings.isFetching && (
            <div className="rounded-[1.2rem] border border-[oklch(0.8_0.03_88)] bg-white/55 px-5 py-8 text-center text-sm text-[oklch(0.42_0.02_250)]">
              {t("rankings.leaderboard.empty")}
            </div>
          )}

          <div className="grid gap-1 md:gap-3">
            {rankedItems.map((item) => (
              <RankedCard key={`${item.market}-${item.ticker}-${item.rank}`} item={item} />
            ))}
          </div>

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm text-[oklch(0.42_0.02_250)]">
              {rankings.isFetching || isPending ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="size-4 animate-spin" />
                  {t("rankings.leaderboard.refreshing")}
                </span>
              ) : (
                `${t("rankings.leaderboard.showing")} ${rankedItems.length} of ${data?.total ?? 0} ranked`
              )}
            </div>
            {data?.pagination.has_more && (
              <button
                type="button"
                onClick={() => replaceParams({ limit: Math.min(filters.limit + 100, 500) })}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-[oklch(0.18_0.018_250)] px-5 py-3 text-sm font-semibold uppercase tracking-[0.16em] text-white transition-colors hover:bg-[oklch(0.28_0.03_250)]"
              >
                {t("rankings.leaderboard.loadMore")}
              </button>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
