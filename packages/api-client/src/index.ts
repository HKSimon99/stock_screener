/**
 * Configurable base URL.
 *
 * - Next.js (web): set via `NEXT_PUBLIC_API_BASE_URL` at build time.
 * - Expo (mobile): call `configureApiClient({ baseUrl: ... })` in app/_layout.tsx
 *   using the value from expo-constants or react-native-dotenv.
 */
let _baseUrl = "http://localhost:8000/api/v1";

if (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_BASE_URL) {
  _baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
}

/** Override the API base URL at runtime (required for Expo). */
export function configureApiClient(options: { baseUrl: string }): void {
  _baseUrl = options.baseUrl;
}

/** @internal */
export function getBaseUrl(): string {
  return _baseUrl;
}

/** @deprecated — use `getBaseUrl()` for runtime access. */
export const BASE_URL = _baseUrl;

export type ConvictionLevel =
  | "DIAMOND"
  | "PLATINUM"
  | "GOLD"
  | "SILVER"
  | "BRONZE"
  | "UNRANKED";

export type RegimeState =
  | "CONFIRMED_UPTREND"
  | "UPTREND_UNDER_PRESSURE"
  | "MARKET_IN_CORRECTION";

export type AlertSeverity = "CRITICAL" | "WARNING" | "INFO";
export type CoverageState =
  | "searchable"
  | "price_ready"
  | "fundamentals_ready"
  | "ranked";

export type RankingSortField =
  | "final_score"
  | "consensus_composite"
  | "technical_composite"
  | "canslim_score"
  | "piotroski_score"
  | "minervini_score"
  | "weinstein_score";

export interface PaginationMeta {
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface FreshnessSummary {
  price_as_of?: string;
  quarterly_as_of?: string;
  annual_as_of?: string;
  ranked_as_of?: string;
}

export interface RankingEligibility {
  eligible: boolean;
  reasons: string[];
}

export interface RankingItem {
  rank: number;
  instrument_id: number;
  ticker: string;
  name?: string;
  market: "US" | "KR";
  exchange?: string;
  asset_type?: "stock" | "etf";
  coverage_state?: CoverageState;
  rank_model_version?: string;
  conviction_level: ConvictionLevel;
  final_score: number;
  consensus_composite?: number;
  technical_composite?: number;
  strategy_pass_count: number;
  regime_warning: boolean;
  score_date: string;
  canslim_score: number;
  piotroski_score: number;
  minervini_score: number;
  weinstein_score: number;
}

export interface RankingsResponse {
  score_date: string;
  market: "US" | "KR";
  regime_state?: RegimeState;
  regime_warning_count: number;
  total: number;
  pagination: PaginationMeta;
  freshness: string;
  items: RankingItem[];
}

export interface StrategyDetail {
  canslim_detail?: Record<string, unknown>;
  canslim_breakdown?: Array<{
    key: "C" | "A" | "N" | "S" | "L" | "I";
    label: string;
    score: number;
  }>;
  piotroski_detail?: {
    f1: boolean;
    f2: boolean;
    f3: boolean;
    f4: boolean;
    f5: boolean;
    f6: boolean;
    f7: boolean;
    f8: boolean;
    f9: boolean;
    f_score: number;
  };
  minervini_detail?: {
    t1: boolean;
    t2: boolean;
    t3: boolean;
    t4: boolean;
    t5: boolean;
    t6: boolean;
    t7: boolean;
    t8: boolean;
    count_passing: number;
  };
  weinstein_detail?: {
    stage: string;
    sub_stage?: string;
    ma_slope: number;
    price_vs_ma: number;
  };
  patterns?: Array<{
    pattern_name: string;
    confidence: number;
    pivot_price: number;
    status?: string;
  }>;
}

export interface ScoreHistoryPoint {
  date: string;
  final_score: number;
  consensus_composite?: number;
  technical_composite?: number;
}

export interface WeinsteinStageHistoryPoint {
  date: string;
  stage?: string;
  score?: number;
}

export interface InstrumentDetail extends RankingItem, StrategyDetail {
  name_kr?: string;
  listing_status?: string;
  exchange?: string;
  sector?: string;
  industry_group?: string;
  shares_outstanding?: number;
  float_shares?: number;
  is_test_issue?: boolean;
  ranking_eligibility?: RankingEligibility;
  freshness?: FreshnessSummary;
  delay_minutes?: number;
  score_history?: ScoreHistoryPoint[];
  weinstein_stage_history?: WeinsteinStageHistoryPoint[];
  consensus_composite?: number;
  computed_at?: string;
  factor_breakdown?: Record<string, unknown>;
  rs_rating?: number;
  ad_rating?: string;
  bb_squeeze?: boolean;
  rs_line_new_high?: boolean;
  technical_composite: number;
  stop_loss_7pct?: number;
}

export interface ChartPriceBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  avg_volume_50d?: number;
  sma_50?: number | null;
  sma_150?: number | null;
  sma_200?: number | null;
}

export interface ChartLinePoint {
  time: string;
  value: number;
}

export interface ChartPatternAnchor {
  time: string;
  value: number;
  label?: string;
}

export interface ChartPatternOverlay {
  pattern_type: string;
  status?: string;
  confidence: number;
  pivot_price?: number;
  start_date?: string;
  end_date?: string;
  anchors: ChartPatternAnchor[];
}

export interface InstrumentChart {
  ticker: string;
  market: "US" | "KR";
  score_date: string;
  interval: "1d" | "1w" | "1m";
  range_days: number;
  benchmark_ticker?: string;
  benchmark_available: boolean;
  benchmark_note?: string;
  freshness?: FreshnessSummary;
  delay_minutes?: number;
  bars: ChartPriceBar[];
  rs_line: ChartLinePoint[];
  patterns: ChartPatternOverlay[];
}

export interface MarketRegime {
  market: "US" | "KR";
  state: RegimeState;
  prior_state?: RegimeState;
  trigger_reason?: string;
  effective_date: string;
  drawdown_from_high?: number;
  distribution_day_count?: number;
  follow_through_day: boolean;
}

export interface MarketRegimeBoard {
  us: MarketRegime | null;
  kr: MarketRegime | null;
  history: MarketRegime[];
}

export interface Alert {
  id: number;
  instrument_id?: number;
  ticker?: string;
  market?: "US" | "KR";
  alert_type: string;
  severity: "CRITICAL" | "WARNING" | "INFO";
  title?: string;
  detail?: string;
  threshold_value?: number;
  actual_value?: number;
  is_read: boolean;
  created_at: string;
}

export interface AdvancedFilterQuery {
  market?: "US" | "KR";
  conviction_level?: ConvictionLevel[];
  min_final_score?: number;
  max_final_score?: number;
  min_canslim?: number;
  min_piotroski?: number;
  min_piotroski_f?: number;
  min_minervini?: number;
  minervini_criteria_min?: number;
  weinstein_stage?: string[];
  ad_rating?: string[];
  rs_line_new_high?: boolean;
  has_pattern?: string;
  limit?: number;
  offset?: number;
  sort_by?: RankingSortField;
  sort_dir?: "asc" | "desc";
}

export interface AlertsResponse {
  total: number;
  critical: number;
  warnings: number;
  items: Alert[];
}

export interface StrategyRankingItem {
  rank: number;
  instrument_id: number;
  ticker: string;
  name: string;
  market: "US" | "KR";
  score?: number;
  detail?: Record<string, unknown>;
  score_date: string;
}

export interface StrategyRankingsResponse {
  strategy: string;
  score_date: string;
  market?: "US" | "KR";
  pagination: PaginationMeta;
  items: StrategyRankingItem[];
}

export interface SearchResult {
  instrument_id: number;
  ticker: string;
  name: string;
  name_kr?: string;
  market: "US" | "KR";
  exchange: string;
  asset_type: "stock" | "etf";
  listing_status: string;
  coverage_state: CoverageState;
  ranking_eligibility: RankingEligibility;
  rank_model_version?: string;
}

export interface SearchResponse {
  query: string;
  total: number;
  items: SearchResult[];
}

export interface UniverseCoverageBucket {
  market: "US" | "KR";
  asset_type: "stock" | "etf";
  searchable: number;
  price_ready: number;
  fundamentals_ready: number;
  ranked: number;
}

export interface UniverseCoverageResponse {
  as_of: string;
  items: UniverseCoverageBucket[];
}

export class APIError extends Error {
  status: number;
  detail?: string;
  url: string;

  constructor(status: number, statusText: string, url: string, detail?: string) {
    super(detail ?? `API error ${status}: ${statusText} (${url})`);
    this.name = "APIError";
    this.status = status;
    this.detail = detail;
    this.url = url;
  }
}

interface APIRequestOptions extends RequestInit {
  bearerToken?: string;
}

interface RawStrategyScores {
  canslim?: number | null;
  piotroski?: number | null;
  minervini?: number | null;
  weinstein?: number | null;
}

interface RawRankingItem {
  rank: number;
  instrument_id: number;
  ticker: string;
  name: string;
  market: "US" | "KR";
  exchange?: string | null;
  asset_type?: "stock" | "etf" | null;
  coverage_state?: CoverageState | null;
  rank_model_version?: string | null;
  conviction_level: ConvictionLevel;
  final_score: number;
  consensus_composite?: number | null;
  technical_composite?: number | null;
  strategy_pass_count: number;
  scores: RawStrategyScores;
  regime_warning: boolean;
  score_date: string;
}

interface RawRankingsResponse {
  score_date: string;
  market: "US" | "KR";
  regime_state?: RegimeState | null;
  regime_warning_count: number;
  pagination: PaginationMeta;
  items: RawRankingItem[];
}

interface RawCANSLIMDetail {
  score?: number | null;
  c?: number | null;
  a?: number | null;
  n?: number | null;
  s?: number | null;
  l?: number | null;
  i?: number | null;
  raw?: Record<string, unknown> | null;
}

interface RawPiotroskiDetail {
  score?: number | null;
  f_raw?: number | null;
  criteria?: Record<string, unknown> | null;
}

interface RawMinerviniDetail {
  score?: number | null;
  criteria_count?: number | null;
  criteria?: Record<string, unknown> | null;
}

interface RawWeinsteinDetail {
  score?: number | null;
  stage?: string | null;
  detail?: Record<string, unknown> | null;
}

interface RawTechnicalDetail {
  composite?: number | null;
  rs_rating?: number | null;
  ad_rating?: string | null;
  bb_squeeze?: boolean | null;
  rs_line_new_high?: boolean | null;
  patterns?: Array<Record<string, unknown>>;
  detail?: Record<string, unknown> | null;
}

interface RawInstrumentDetail {
  instrument_id: number;
  ticker: string;
  name: string;
  name_kr?: string | null;
  market: "US" | "KR";
  asset_type?: "stock" | "etf" | null;
  score_date: string;
  exchange?: string | null;
  listing_status?: string | null;
  sector?: string | null;
  industry_group?: string | null;
  shares_outstanding?: number | null;
  float_shares?: number | null;
  is_test_issue?: boolean | null;
  coverage_state?: CoverageState | null;
  ranking_eligibility?: RankingEligibility | null;
  freshness?: FreshnessSummary | null;
  delay_minutes?: number | null;
  rank_model_version?: string | null;
  conviction_level: ConvictionLevel;
  final_score?: number | null;
  consensus_composite?: number | null;
  strategy_pass_count?: number | null;
  canslim: RawCANSLIMDetail;
  piotroski: RawPiotroskiDetail;
  minervini: RawMinerviniDetail;
  weinstein: RawWeinsteinDetail;
  technical: RawTechnicalDetail;
  score_breakdown?: Record<string, unknown> | null;
  factor_breakdown?: Record<string, unknown> | null;
  score_history?: ScoreHistoryPoint[] | null;
  weinstein_stage_history?: WeinsteinStageHistoryPoint[] | null;
  computed_at?: string | null;
}

interface RawChartPriceBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  avg_volume_50d?: number | null;
  sma_50?: number | null;
  sma_150?: number | null;
  sma_200?: number | null;
}

interface RawChartLinePoint {
  time: string;
  value: number;
}

interface RawChartPatternAnchor {
  time: string;
  value: number;
  label?: string | null;
}

interface RawChartPatternOverlay {
  pattern_type: string;
  status?: string | null;
  confidence: number;
  pivot_price?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  anchors: RawChartPatternAnchor[];
}

interface RawInstrumentChart {
  ticker: string;
  market: "US" | "KR";
  score_date: string;
  interval?: "1d" | "1w" | "1m";
  range_days?: number;
  benchmark_ticker?: string | null;
  benchmark_available: boolean;
  benchmark_note?: string | null;
  freshness?: FreshnessSummary | null;
  delay_minutes?: number | null;
  bars: RawChartPriceBar[];
  rs_line: RawChartLinePoint[];
  patterns: RawChartPatternOverlay[];
}

interface RawSearchResult {
  instrument_id: number;
  ticker: string;
  name: string;
  name_kr?: string | null;
  market: "US" | "KR";
  exchange: string;
  asset_type: "stock" | "etf";
  listing_status: string;
  coverage_state: CoverageState;
  ranking_eligibility: RankingEligibility;
  rank_model_version?: string | null;
}

interface RawSearchResponse {
  query: string;
  total: number;
  items: RawSearchResult[];
}

interface RawUniverseCoverageResponse {
  as_of: string;
  items: UniverseCoverageBucket[];
}

interface RawRegimeEntry {
  market: "US" | "KR";
  state: RegimeState;
  prior_state?: RegimeState | null;
  trigger_reason?: string | null;
  effective_date: string;
  drawdown_from_high?: number | null;
  distribution_day_count?: number | null;
  follow_through_day: boolean;
}

interface RawMarketRegimeResponse {
  us?: RawRegimeEntry | null;
  kr?: RawRegimeEntry | null;
  history: RawRegimeEntry[];
}

interface RawAlertsResponse {
  total: number;
  critical: number;
  warnings: number;
  items: Alert[];
}

interface RawFilterResponse {
  score_date: string;
  total_found: number;
  pagination: PaginationMeta;
  items: RawRankingItem[];
}

function toNumber(value: number | null | undefined, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function toBoolean(value: unknown): boolean {
  return value === true;
}

function extractPass(
  source: Record<string, unknown> | null | undefined,
  key: string
): boolean {
  const entry = source?.[key];
  if (entry && typeof entry === "object" && "pass" in entry) {
    return toBoolean((entry as { pass?: unknown }).pass);
  }
  return false;
}

function humanizePattern(pattern: string | undefined): string {
  if (!pattern) return "Pattern";
  return pattern
    .split("_")
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(" ");
}

export function formatSnapshotDate(value: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(new Date(`${value}T00:00:00`));
  } catch {
    return value;
  }
}

export function buildInstrumentPath(
  ticker: string,
  market: "US" | "KR"
): string {
  return `/app/instruments/${market}/${encodeURIComponent(ticker)}`;
}

function normalizeRankingItem(item: RawRankingItem): RankingItem {
  return {
    rank: item.rank,
    instrument_id: item.instrument_id,
    ticker: item.ticker,
    name: item.name,
    market: item.market,
    exchange: item.exchange ?? undefined,
    asset_type: item.asset_type ?? undefined,
    coverage_state: item.coverage_state ?? undefined,
    rank_model_version: item.rank_model_version ?? undefined,
    conviction_level: item.conviction_level,
    final_score: toNumber(item.final_score),
    consensus_composite: item.consensus_composite ?? undefined,
    technical_composite: item.technical_composite ?? undefined,
    strategy_pass_count: item.strategy_pass_count,
    regime_warning: item.regime_warning,
    score_date: item.score_date,
    canslim_score: toNumber(item.scores.canslim),
    piotroski_score: toNumber(item.scores.piotroski),
    minervini_score: toNumber(item.scores.minervini),
    weinstein_score: toNumber(item.scores.weinstein),
  };
}

function normalizeRankingsResponse(raw: RawRankingsResponse): RankingsResponse {
  return {
    score_date: raw.score_date,
    market: raw.market,
    regime_state: raw.regime_state ?? undefined,
    regime_warning_count: raw.regime_warning_count,
    total: raw.pagination.total,
    pagination: raw.pagination,
    freshness: `Snapshot ${formatSnapshotDate(raw.score_date)}`,
    items: raw.items.map(normalizeRankingItem),
  };
}

function normalizeInstrument(raw: RawInstrumentDetail): InstrumentDetail {
  const piotroskiCriteria = raw.piotroski.criteria ?? {};
  const minerviniCriteria = raw.minervini.criteria ?? {};
  const weinsteinDetail = raw.weinstein.detail ?? {};
  const technicalDetail = raw.technical.detail ?? {};
  const scoreBreakdown = raw.score_breakdown ?? {};
  const rawMaSlope =
    typeof weinsteinDetail.ma_slope === "number"
      ? weinsteinDetail.ma_slope
      : typeof weinsteinDetail.ma_slope_20d === "number"
        ? weinsteinDetail.ma_slope_20d
        : null;
  const rawPriceVsMa =
    typeof weinsteinDetail.price_vs_ma === "number"
      ? weinsteinDetail.price_vs_ma
      : null;

  return {
    rank: 0,
    instrument_id: raw.instrument_id,
    ticker: raw.ticker,
    name: raw.name,
    name_kr: raw.name_kr ?? undefined,
    market: raw.market,
    asset_type: raw.asset_type ?? undefined,
    listing_status: raw.listing_status ?? undefined,
    exchange: raw.exchange ?? undefined,
    sector: raw.sector ?? undefined,
    industry_group: raw.industry_group ?? undefined,
    shares_outstanding:
      typeof raw.shares_outstanding === "number"
        ? raw.shares_outstanding
        : undefined,
    float_shares:
      typeof raw.float_shares === "number" ? raw.float_shares : undefined,
    is_test_issue: raw.is_test_issue ?? undefined,
    coverage_state: raw.coverage_state ?? undefined,
    ranking_eligibility: raw.ranking_eligibility ?? undefined,
    freshness: raw.freshness ?? undefined,
    delay_minutes:
      typeof raw.delay_minutes === "number" ? raw.delay_minutes : undefined,
    rank_model_version: raw.rank_model_version ?? undefined,
    conviction_level: raw.conviction_level,
    final_score: toNumber(raw.final_score),
    consensus_composite: raw.consensus_composite ?? undefined,
    technical_composite: toNumber(raw.technical.composite),
    strategy_pass_count: toNumber(raw.strategy_pass_count),
    regime_warning: toBoolean(
      (scoreBreakdown as { regime_warning?: unknown }).regime_warning
    ),
    score_date: raw.score_date,
    canslim_score: toNumber(raw.canslim.score),
    piotroski_score: toNumber(raw.piotroski.score),
    minervini_score: toNumber(raw.minervini.score),
    weinstein_score: toNumber(raw.weinstein.score),
    computed_at: raw.computed_at ?? undefined,
    rs_rating: raw.technical.rs_rating ?? undefined,
    ad_rating: raw.technical.ad_rating ?? undefined,
    bb_squeeze: raw.technical.bb_squeeze ?? undefined,
    rs_line_new_high: raw.technical.rs_line_new_high ?? undefined,
    canslim_detail: raw.canslim.raw ?? undefined,
    canslim_breakdown: [
      { key: "C", label: "Current EPS", score: toNumber(raw.canslim.c) },
      { key: "A", label: "Annual EPS", score: toNumber(raw.canslim.a) },
      { key: "N", label: "New Highs", score: toNumber(raw.canslim.n) },
      { key: "S", label: "Supply / Demand", score: toNumber(raw.canslim.s) },
      { key: "L", label: "Leadership", score: toNumber(raw.canslim.l) },
      { key: "I", label: "Institutional", score: toNumber(raw.canslim.i) },
    ],
    piotroski_detail: {
      f1: extractPass(piotroskiCriteria, "F1_roa_positive"),
      f2: extractPass(piotroskiCriteria, "F2_cfo_positive"),
      f3: extractPass(piotroskiCriteria, "F3_roa_improving"),
      f4: extractPass(piotroskiCriteria, "F4_accruals"),
      f5: extractPass(piotroskiCriteria, "F5_leverage_decreasing"),
      f6: extractPass(piotroskiCriteria, "F6_current_ratio_improving"),
      f7: extractPass(piotroskiCriteria, "F7_no_dilution"),
      f8: extractPass(piotroskiCriteria, "F8_gross_margin_improving"),
      f9: extractPass(piotroskiCriteria, "F9_asset_turnover_improving"),
      f_score: toNumber(raw.piotroski.f_raw),
    },
    minervini_detail: {
      t1: extractPass(minerviniCriteria, "T1_above_150ma"),
      t2: extractPass(minerviniCriteria, "T2_above_200ma"),
      t3: extractPass(minerviniCriteria, "T3_150ma_above_200ma"),
      t4: extractPass(minerviniCriteria, "T4_200ma_trending_up"),
      t5: extractPass(minerviniCriteria, "T5_above_50ma"),
      t6: extractPass(minerviniCriteria, "T6_25pct_above_52w_low"),
      t7: extractPass(minerviniCriteria, "T7_within_25pct_52w_high"),
      t8: extractPass(minerviniCriteria, "T8_rs_rating_ge_70"),
      count_passing: toNumber(raw.minervini.criteria_count),
    },
    weinstein_detail: {
      stage: raw.weinstein.stage ?? "0",
      sub_stage:
        typeof weinsteinDetail.sub_stage === "string"
          ? weinsteinDetail.sub_stage
          : undefined,
      ma_slope: toNumber(rawMaSlope),
      price_vs_ma: toNumber(rawPriceVsMa),
    },
    patterns:
      raw.technical.patterns?.map((pattern) => ({
        pattern_name: humanizePattern(
          typeof pattern.pattern_type === "string"
            ? pattern.pattern_type
            : undefined
        ),
        confidence: toNumber(
          typeof pattern.confidence === "number" ? pattern.confidence : null
        ),
        pivot_price: toNumber(
          typeof pattern.pivot_price === "number" ? pattern.pivot_price : null
        ),
        status: typeof pattern.status === "string" ? pattern.status : undefined,
      })) ?? [],
    score_history:
      raw.score_history?.map((point) => ({
        date: point.date,
        final_score: toNumber(point.final_score),
        consensus_composite: point.consensus_composite ?? undefined,
        technical_composite: point.technical_composite ?? undefined,
      })) ?? [],
    weinstein_stage_history:
      raw.weinstein_stage_history?.map((point) => ({
        date: point.date,
        stage: point.stage ?? undefined,
        score: point.score ?? undefined,
      })) ?? [],
    stop_loss_7pct:
      typeof technicalDetail.stop_loss_7pct === "number"
        ? technicalDetail.stop_loss_7pct
        : undefined,
    factor_breakdown: raw.factor_breakdown ?? undefined,
  };
}

function normalizeInstrumentChart(raw: RawInstrumentChart): InstrumentChart {
  return {
    ticker: raw.ticker,
    market: raw.market,
    score_date: raw.score_date,
    interval: raw.interval ?? "1d",
    range_days: typeof raw.range_days === "number" ? raw.range_days : 350,
    benchmark_ticker: raw.benchmark_ticker ?? undefined,
    benchmark_available: raw.benchmark_available,
    benchmark_note: raw.benchmark_note ?? undefined,
    freshness: raw.freshness ?? undefined,
    delay_minutes:
      typeof raw.delay_minutes === "number" ? raw.delay_minutes : undefined,
    bars: raw.bars.map((bar) => ({
      time: bar.time,
      open: toNumber(bar.open),
      high: toNumber(bar.high),
      low: toNumber(bar.low),
      close: toNumber(bar.close),
      volume: toNumber(bar.volume),
      avg_volume_50d:
        typeof bar.avg_volume_50d === "number" ? bar.avg_volume_50d : undefined,
      sma_50: typeof bar.sma_50 === "number" ? bar.sma_50 : null,
      sma_150: typeof bar.sma_150 === "number" ? bar.sma_150 : null,
      sma_200: typeof bar.sma_200 === "number" ? bar.sma_200 : null,
    })),
    rs_line: raw.rs_line.map((point) => ({
      time: point.time,
      value: toNumber(point.value),
    })),
    patterns: raw.patterns.map((pattern) => ({
      pattern_type: pattern.pattern_type,
      status: pattern.status ?? undefined,
      confidence: toNumber(pattern.confidence),
      pivot_price:
        typeof pattern.pivot_price === "number" ? pattern.pivot_price : undefined,
      start_date: pattern.start_date ?? undefined,
      end_date: pattern.end_date ?? undefined,
      anchors:
        pattern.anchors?.map((anchor) => ({
          time: anchor.time,
          value: toNumber(anchor.value),
          label: anchor.label ?? undefined,
        })) ?? [],
    })),
  };
}

function normalizeRegimeEntry(
  entry: RawRegimeEntry | null | undefined
): MarketRegime | null {
  if (!entry) {
    return null;
  }

  return {
    market: entry.market,
    state: entry.state,
    prior_state: entry.prior_state ?? undefined,
    trigger_reason: entry.trigger_reason ?? undefined,
    effective_date: entry.effective_date,
    drawdown_from_high: entry.drawdown_from_high ?? undefined,
    distribution_day_count: entry.distribution_day_count ?? undefined,
    follow_through_day: entry.follow_through_day,
  };
}

function normalizeRegimeBoard(raw: RawMarketRegimeResponse): MarketRegimeBoard {
  return {
    us: normalizeRegimeEntry(raw.us),
    kr: normalizeRegimeEntry(raw.kr),
    history: raw.history
      .map((entry) => normalizeRegimeEntry(entry))
      .filter((entry): entry is MarketRegime => entry !== null),
  };
}

function normalizeFilteredRankings(
  raw: RawFilterResponse,
  market?: "US" | "KR"
): RankingsResponse {
  const items = raw.items.map(normalizeRankingItem);
  return {
    score_date: raw.score_date,
    market: market ?? items[0]?.market ?? "US",
    regime_state: undefined,
    regime_warning_count: items.filter((item) => item.regime_warning).length,
    total: raw.total_found,
    pagination: raw.pagination,
    freshness: `Snapshot ${formatSnapshotDate(raw.score_date)}`,
    items,
  };
}

function normalizeSearchResponse(raw: RawSearchResponse): SearchResponse {
  return {
    query: raw.query,
    total: raw.total,
    items: raw.items.map((item) => ({
      instrument_id: item.instrument_id,
      ticker: item.ticker,
      name: item.name,
      name_kr: item.name_kr ?? undefined,
      market: item.market,
      exchange: item.exchange,
      asset_type: item.asset_type,
      listing_status: item.listing_status,
      coverage_state: item.coverage_state,
      ranking_eligibility: item.ranking_eligibility,
      rank_model_version: item.rank_model_version ?? undefined,
    })),
  };
}

export async function apiFetch<T>(
  path: string,
  options?: APIRequestOptions
): Promise<T> {
  const url = `${getBaseUrl()}${path}`;
  const headers = new Headers(options?.headers);
  if (options?.bearerToken) {
    headers.set("Authorization", `Bearer ${options.bearerToken}`);
  }
  const res = await fetch(url, {
    cache: "no-store",
    ...options,
    headers,
  });

  if (!res.ok) {
    let detail: string | undefined;

    try {
      const payload = (await res.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      detail = undefined;
    }

    throw new APIError(res.status, res.statusText, url, detail);
  }

  return res.json() as Promise<T>;
}

export async function fetchRankings(params: {
  market: "US" | "KR";
  asset_type?: "stock" | "etf";
  conviction?: string;
  limit?: number;
  offset?: number;
}): Promise<RankingsResponse> {
  const qs = new URLSearchParams();
  qs.set("market", params.market);
  if (params.asset_type) qs.set("asset_type", params.asset_type);
  if (params.conviction) qs.set("conviction", params.conviction);
  if (params.limit != null) qs.set("limit", String(params.limit));
  if (params.offset != null) qs.set("offset", String(params.offset));

  const raw = await apiFetch<RawRankingsResponse>(`/rankings?${qs.toString()}`);
  return normalizeRankingsResponse(raw);
}

export async function fetchFilteredRankings(
  params: AdvancedFilterQuery,
  bearerToken?: string
): Promise<RankingsResponse> {
  const body = Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== "")
  );
  const raw = await apiFetch<RawFilterResponse>("/filters/query", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    bearerToken,
    body: JSON.stringify(body),
  });
  return normalizeFilteredRankings(raw, params.market);
}

export async function fetchInstrument(
  ticker: string,
  market: "US" | "KR"
): Promise<InstrumentDetail> {
  const raw = await apiFetch<RawInstrumentDetail>(
    `/instruments/${encodeURIComponent(ticker)}?market=${market}`
  );
  return normalizeInstrument(raw);
}

export async function fetchInstrumentChart(
  ticker: string,
  market: "US" | "KR",
  params?: {
    interval?: "1d" | "1w" | "1m";
    range_days?: number;
    include_indicators?: boolean;
  }
): Promise<InstrumentChart> {
  const qs = new URLSearchParams();
  qs.set("market", market);
  if (params?.interval) qs.set("interval", params.interval);
  if (params?.range_days != null) qs.set("range_days", String(params.range_days));
  if (params?.include_indicators != null) {
    qs.set("include_indicators", String(params.include_indicators));
  }
  const raw = await apiFetch<RawInstrumentChart>(
    `/instruments/${encodeURIComponent(ticker)}/chart?${qs.toString()}`
  );
  return normalizeInstrumentChart(raw);
}

export async function fetchInstrumentSearch(params: {
  q: string;
  market?: "US" | "KR";
  asset_type?: "stock" | "etf";
  limit?: number;
}): Promise<SearchResponse> {
  const qs = new URLSearchParams();
  qs.set("q", params.q);
  if (params.market) qs.set("market", params.market);
  if (params.asset_type) qs.set("asset_type", params.asset_type);
  if (params.limit != null) qs.set("limit", String(params.limit));
  const raw = await apiFetch<RawSearchResponse>(`/search?${qs.toString()}`);
  return normalizeSearchResponse(raw);
}

export async function fetchUniverseCoverage(): Promise<UniverseCoverageResponse> {
  return apiFetch<RawUniverseCoverageResponse>("/universe/coverage");
}

export async function fetchMarketRegime(
  market: "US" | "KR"
): Promise<MarketRegime | null> {
  const board = await fetchMarketRegimeBoard();
  return market === "US" ? board.us : board.kr;
}

export async function fetchMarketRegimeBoard(
  includeHistory = 0
): Promise<MarketRegimeBoard> {
  const query = includeHistory > 0 ? `?include_history=${includeHistory}` : "";
  const raw = await apiFetch<RawMarketRegimeResponse>(`/market-regime${query}`);
  return normalizeRegimeBoard(raw);
}

export async function fetchAlerts(params?: {
  market?: "US" | "KR";
  severity?: AlertSeverity;
  days?: number;
  acknowledged?: boolean;
  limit?: number;
}): Promise<AlertsResponse> {
  const qs = new URLSearchParams();
  if (params?.market) qs.set("market", params.market);
  if (params?.severity) qs.set("severity", params.severity);
  if (params?.days != null) qs.set("days", String(params.days));
  if (params?.acknowledged != null) {
    qs.set("acknowledged", String(params.acknowledged));
  }
  if (params?.limit != null) qs.set("limit", String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<RawAlertsResponse>(`/alerts${suffix}`);
}

export async function fetchStrategyRankings(
  strategy: string,
  market: "US" | "KR"
): Promise<StrategyRankingsResponse> {
  return apiFetch<StrategyRankingsResponse>(
    `/strategies/${encodeURIComponent(strategy)}/rankings?market=${market}`
  );
}
