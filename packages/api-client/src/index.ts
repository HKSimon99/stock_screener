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
  | "ranked"
  | "needs_price"
  | "needs_fundamentals"
  | "needs_scoring"
  | "stale";

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
  name_kr?: string;
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
  score_date?: string | null;   // null/undefined when market has no scores yet
  market: "US" | "KR";
  regime_state?: RegimeState;
  regime_warning_count: number;
  total: number;
  pagination: PaginationMeta;
  freshness: string;
  items: RankingItem[];
}

export interface RankingsQueryParams {
  market: "US" | "KR";
  asset_type?: "stock" | "etf";
  conviction?: string | string[];
  score_date?: string;
  limit?: number;
  offset?: number;
  min_final_score?: number;
  max_final_score?: number;
  min_consensus_composite?: number;
  min_technical_composite?: number;
  min_strategy_pass_count?: number;
  min_canslim?: number;
  min_piotroski?: number;
  min_minervini?: number;
  min_weinstein?: number;
  min_rs_rating?: number;
  sector?: string | string[];
  exchange?: string | string[];
  coverage_state?: CoverageState | CoverageState[];
  weinstein_stage?: string | string[];
  ad_rating?: string | string[];
  rs_line_new_high?: boolean;
  price_ready?: boolean;
  fundamentals_ready?: boolean;
  price_as_of_gte?: string;
  price_as_of_lte?: string;
  quarterly_as_of_gte?: string;
  annual_as_of_gte?: string;
  ranked_as_of_gte?: string;
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

export interface PriceMetrics {
  trade_date?: string;
  close?: number;
  previous_close?: number;
  change?: number;
  change_percent?: number;
  volume?: number;
  avg_volume_50d?: number;
}

export interface QuarterlyMetrics {
  fiscal_year?: number;
  fiscal_quarter?: number;
  report_date?: string;
  revenue?: number;
  net_income?: number;
  eps?: number;
  eps_diluted?: number;
  revenue_yoy_growth?: number;
  eps_yoy_growth?: number;
  data_source?: string;
}

export interface AnnualMetrics {
  fiscal_year?: number;
  report_date?: string;
  revenue?: number;
  gross_profit?: number;
  net_income?: number;
  eps?: number;
  eps_diluted?: number;
  eps_yoy_growth?: number;
  total_assets?: number;
  current_assets?: number;
  current_liabilities?: number;
  long_term_debt?: number;
  shares_outstanding_annual?: number;
  operating_cash_flow?: number;
  roa?: number;
  current_ratio?: number;
  gross_margin?: number;
  asset_turnover?: number;
  leverage_ratio?: number;
  data_source?: string;
}

export interface MarketMetrics {
  price_as_of?: string;
  share_count_source?: string;
  trailing_eps_source?: string;
  market_cap?: number;
  float_market_cap?: number;
  trailing_pe_ratio?: number;
  dividend_yield?: number;
}

export interface OwnershipMetrics {
  report_date?: string;
  data_source?: string;
  num_institutional_owners?: number;
  institutional_pct?: number;
  top_fund_quality_score?: number;
  qoq_owner_change?: number;
  foreign_ownership_pct?: number;
  foreign_net_buy_30d?: number;
  institutional_net_buy_30d?: number;
  individual_net_buy_30d?: number;
  is_buyback_active?: boolean;
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
  needs_refresh?: boolean;
  score_history?: ScoreHistoryPoint[];
  weinstein_stage_history?: WeinsteinStageHistoryPoint[];
  consensus_composite?: number;
  computed_at?: string;
  factor_breakdown?: Record<string, unknown>;
  rs_rating?: number;
  ad_rating?: string;
  bb_squeeze?: boolean;
  rs_line_new_high?: boolean;
  price_metrics?: PriceMetrics;
  quarterly_metrics?: QuarterlyMetrics;
  annual_metrics?: AnnualMetrics;
  market_metrics?: MarketMetrics;
  ownership_metrics?: OwnershipMetrics;
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
  name_kr?: string | null;
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

export interface BrowseResult {
  instrument_id: number;
  ticker: string;
  name: string;
  name_kr?: string;
  market: "US" | "KR";
  exchange: string;
  asset_type: "stock" | "etf";
  listing_status: string;
  sector?: string;
  industry_group?: string;
  coverage_state: CoverageState;
  ranking_eligibility: RankingEligibility;
  freshness: FreshnessSummary;
  delay_minutes?: number;
  rank_model_version?: string;
}

export interface BrowseResponse {
  pagination: PaginationMeta;
  total: number;
  items: BrowseResult[];
}

export interface BrowseQueryParams {
  market?: "US" | "KR";
  asset_type?: "stock" | "etf";
  coverage_state?: CoverageState;
  exclude_ranked?: boolean;
  limit?: number;
  offset?: number;
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

export interface HydrationJob {
  id: number;
  ticker: string;
  market: "US" | "KR";
  instrument_id?: number;
  status: string;
  requester_source: string;
  requester_user_id?: string;
  celery_task_id?: string;
  queued_at: string;
  started_at?: string;
  completed_at?: string;
  failed_at?: string;
  updated_at: string;
  error_message?: string;
  source_metadata: Record<string, unknown>;
}

export interface HydrationJobCreateResponse {
  job: HydrationJob;
  created: boolean;
  message: string;
}

export interface InstrumentIngestResponse {
  message: string;
  instrument_id: number;
  scoring_deferred?: boolean;
  next_step?: string;
}

// =============================================================================
// Watchlist
// =============================================================================

export interface WatchlistItem {
  id: number;
  instrument_id: number;
  market: string;
  ticker: string;
  name?: string;
  name_kr?: string;
  added_at: string;
}

export interface WatchlistResponse {
  items: WatchlistItem[];
  total: number;
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
  name_kr?: string | null;
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
  score_date?: string | null;   // null when market has no scores yet
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

interface RawPriceMetrics {
  trade_date?: string | null;
  close?: number | null;
  previous_close?: number | null;
  change?: number | null;
  change_percent?: number | null;
  volume?: number | null;
  avg_volume_50d?: number | null;
}

interface RawQuarterlyMetrics {
  fiscal_year?: number | null;
  fiscal_quarter?: number | null;
  report_date?: string | null;
  revenue?: number | null;
  net_income?: number | null;
  eps?: number | null;
  eps_diluted?: number | null;
  revenue_yoy_growth?: number | null;
  eps_yoy_growth?: number | null;
  data_source?: string | null;
}

interface RawAnnualMetrics {
  fiscal_year?: number | null;
  report_date?: string | null;
  revenue?: number | null;
  gross_profit?: number | null;
  net_income?: number | null;
  eps?: number | null;
  eps_diluted?: number | null;
  eps_yoy_growth?: number | null;
  total_assets?: number | null;
  current_assets?: number | null;
  current_liabilities?: number | null;
  long_term_debt?: number | null;
  shares_outstanding_annual?: number | null;
  operating_cash_flow?: number | null;
  roa?: number | null;
  current_ratio?: number | null;
  gross_margin?: number | null;
  asset_turnover?: number | null;
  leverage_ratio?: number | null;
  data_source?: string | null;
}

interface RawMarketMetrics {
  price_as_of?: string | null;
  share_count_source?: string | null;
  trailing_eps_source?: string | null;
  market_cap?: number | null;
  float_market_cap?: number | null;
  trailing_pe_ratio?: number | null;
  dividend_yield?: number | null;
}

interface RawOwnershipMetrics {
  report_date?: string | null;
  data_source?: string | null;
  num_institutional_owners?: number | null;
  institutional_pct?: number | null;
  top_fund_quality_score?: number | null;
  qoq_owner_change?: number | null;
  foreign_ownership_pct?: number | null;
  foreign_net_buy_30d?: number | null;
  institutional_net_buy_30d?: number | null;
  individual_net_buy_30d?: number | null;
  is_buyback_active?: boolean | null;
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
  needs_refresh?: boolean | null;
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
  price_metrics?: RawPriceMetrics | null;
  quarterly_metrics?: RawQuarterlyMetrics | null;
  annual_metrics?: RawAnnualMetrics | null;
  market_metrics?: RawMarketMetrics | null;
  ownership_metrics?: RawOwnershipMetrics | null;
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

interface RawBrowseResult {
  instrument_id: number;
  ticker: string;
  name: string;
  name_kr?: string | null;
  market: "US" | "KR";
  exchange: string;
  asset_type: "stock" | "etf";
  listing_status: string;
  sector?: string | null;
  industry_group?: string | null;
  coverage_state: CoverageState;
  ranking_eligibility: RankingEligibility;
  freshness?: FreshnessSummary | null;
  delay_minutes?: number | null;
  rank_model_version?: string | null;
}

interface RawBrowseResponse {
  pagination: PaginationMeta;
  items: RawBrowseResult[];
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

function optionalNumber(value: number | null | undefined): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
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

function normalizePriceMetrics(raw: RawPriceMetrics | null | undefined): PriceMetrics {
  if (!raw) return {};
  return {
    trade_date: raw.trade_date ?? undefined,
    close: optionalNumber(raw.close),
    previous_close: optionalNumber(raw.previous_close),
    change: optionalNumber(raw.change),
    change_percent: optionalNumber(raw.change_percent),
    volume: optionalNumber(raw.volume),
    avg_volume_50d: optionalNumber(raw.avg_volume_50d),
  };
}

function normalizeQuarterlyMetrics(
  raw: RawQuarterlyMetrics | null | undefined
): QuarterlyMetrics | undefined {
  if (!raw) return undefined;
  return {
    fiscal_year: optionalNumber(raw.fiscal_year),
    fiscal_quarter: optionalNumber(raw.fiscal_quarter),
    report_date: raw.report_date ?? undefined,
    revenue: optionalNumber(raw.revenue),
    net_income: optionalNumber(raw.net_income),
    eps: optionalNumber(raw.eps),
    eps_diluted: optionalNumber(raw.eps_diluted),
    revenue_yoy_growth: optionalNumber(raw.revenue_yoy_growth),
    eps_yoy_growth: optionalNumber(raw.eps_yoy_growth),
    data_source: raw.data_source ?? undefined,
  };
}

function normalizeAnnualMetrics(
  raw: RawAnnualMetrics | null | undefined
): AnnualMetrics | undefined {
  if (!raw) return undefined;
  return {
    fiscal_year: optionalNumber(raw.fiscal_year),
    report_date: raw.report_date ?? undefined,
    revenue: optionalNumber(raw.revenue),
    gross_profit: optionalNumber(raw.gross_profit),
    net_income: optionalNumber(raw.net_income),
    eps: optionalNumber(raw.eps),
    eps_diluted: optionalNumber(raw.eps_diluted),
    eps_yoy_growth: optionalNumber(raw.eps_yoy_growth),
    total_assets: optionalNumber(raw.total_assets),
    current_assets: optionalNumber(raw.current_assets),
    current_liabilities: optionalNumber(raw.current_liabilities),
    long_term_debt: optionalNumber(raw.long_term_debt),
    shares_outstanding_annual: optionalNumber(raw.shares_outstanding_annual),
    operating_cash_flow: optionalNumber(raw.operating_cash_flow),
    roa: optionalNumber(raw.roa),
    current_ratio: optionalNumber(raw.current_ratio),
    gross_margin: optionalNumber(raw.gross_margin),
    asset_turnover: optionalNumber(raw.asset_turnover),
    leverage_ratio: optionalNumber(raw.leverage_ratio),
    data_source: raw.data_source ?? undefined,
  };
}

function normalizeMarketMetrics(
  raw: RawMarketMetrics | null | undefined
): MarketMetrics | undefined {
  if (!raw) return undefined;
  return {
    price_as_of: raw.price_as_of ?? undefined,
    share_count_source: raw.share_count_source ?? undefined,
    trailing_eps_source: raw.trailing_eps_source ?? undefined,
    market_cap: optionalNumber(raw.market_cap),
    float_market_cap: optionalNumber(raw.float_market_cap),
    trailing_pe_ratio: optionalNumber(raw.trailing_pe_ratio),
    dividend_yield: optionalNumber(raw.dividend_yield),
  };
}

function normalizeOwnershipMetrics(
  raw: RawOwnershipMetrics | null | undefined
): OwnershipMetrics | undefined {
  if (!raw) return undefined;
  return {
    report_date: raw.report_date ?? undefined,
    data_source: raw.data_source ?? undefined,
    num_institutional_owners: optionalNumber(raw.num_institutional_owners),
    institutional_pct: optionalNumber(raw.institutional_pct),
    top_fund_quality_score: optionalNumber(raw.top_fund_quality_score),
    qoq_owner_change: optionalNumber(raw.qoq_owner_change),
    foreign_ownership_pct: optionalNumber(raw.foreign_ownership_pct),
    foreign_net_buy_30d: optionalNumber(raw.foreign_net_buy_30d),
    institutional_net_buy_30d: optionalNumber(raw.institutional_net_buy_30d),
    individual_net_buy_30d: optionalNumber(raw.individual_net_buy_30d),
    is_buyback_active:
      typeof raw.is_buyback_active === "boolean" ? raw.is_buyback_active : undefined,
  };
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
    name_kr: item.name_kr ?? undefined,
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
    score_date: raw.score_date ?? null,
    market: raw.market,
    regime_state: raw.regime_state ?? undefined,
    regime_warning_count: raw.regime_warning_count,
    total: raw.pagination.total,
    pagination: raw.pagination,
    freshness: raw.score_date ? `Snapshot ${formatSnapshotDate(raw.score_date)}` : "No data yet",
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
    needs_refresh: raw.needs_refresh ?? false,
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
    price_metrics: normalizePriceMetrics(raw.price_metrics),
    quarterly_metrics: normalizeQuarterlyMetrics(raw.quarterly_metrics),
    annual_metrics: normalizeAnnualMetrics(raw.annual_metrics),
    market_metrics: normalizeMarketMetrics(raw.market_metrics),
    ownership_metrics: normalizeOwnershipMetrics(raw.ownership_metrics),
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

function normalizeBrowseResponse(raw: RawBrowseResponse): BrowseResponse {
  return {
    pagination: raw.pagination,
    total: raw.pagination.total,
    items: raw.items.map((item) => ({
      instrument_id: item.instrument_id,
      ticker: item.ticker,
      name: item.name,
      name_kr: item.name_kr ?? undefined,
      market: item.market,
      exchange: item.exchange,
      asset_type: item.asset_type,
      listing_status: item.listing_status,
      sector: item.sector ?? undefined,
      industry_group: item.industry_group ?? undefined,
      coverage_state: item.coverage_state,
      ranking_eligibility: item.ranking_eligibility,
      freshness: item.freshness ?? {},
      delay_minutes:
        typeof item.delay_minutes === "number" ? item.delay_minutes : undefined,
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

export async function fetchRankings(
  params: RankingsQueryParams
): Promise<RankingsResponse> {
  const qs = new URLSearchParams();
  const appendList = (key: string, value?: string | string[]) => {
    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item) qs.append(key, item);
      });
    } else if (value) {
      qs.set(key, value);
    }
  };
  const setNumber = (key: string, value?: number) => {
    if (value != null) qs.set(key, String(value));
  };
  const setBoolean = (key: string, value?: boolean) => {
    if (value != null) qs.set(key, String(value));
  };
  const setString = (key: string, value?: string) => {
    if (value) qs.set(key, value);
  };

  qs.set("market", params.market);
  if (params.asset_type) qs.set("asset_type", params.asset_type);
  appendList("conviction", params.conviction);
  setString("score_date", params.score_date);
  setNumber("limit", params.limit);
  setNumber("offset", params.offset);
  setNumber("min_final_score", params.min_final_score);
  setNumber("max_final_score", params.max_final_score);
  setNumber("min_consensus_composite", params.min_consensus_composite);
  setNumber("min_technical_composite", params.min_technical_composite);
  setNumber("min_strategy_pass_count", params.min_strategy_pass_count);
  setNumber("min_canslim", params.min_canslim);
  setNumber("min_piotroski", params.min_piotroski);
  setNumber("min_minervini", params.min_minervini);
  setNumber("min_weinstein", params.min_weinstein);
  setNumber("min_rs_rating", params.min_rs_rating);
  appendList("sector", params.sector);
  appendList("exchange", params.exchange);
  appendList("coverage_state", params.coverage_state);
  appendList("weinstein_stage", params.weinstein_stage);
  appendList("ad_rating", params.ad_rating);
  setBoolean("rs_line_new_high", params.rs_line_new_high);
  setBoolean("price_ready", params.price_ready);
  setBoolean("fundamentals_ready", params.fundamentals_ready);
  setString("price_as_of_gte", params.price_as_of_gte);
  setString("price_as_of_lte", params.price_as_of_lte);
  setString("quarterly_as_of_gte", params.quarterly_as_of_gte);
  setString("annual_as_of_gte", params.annual_as_of_gte);
  setString("ranked_as_of_gte", params.ranked_as_of_gte);

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

export async function ingestInstrument(
  ticker: string,
  market: "US" | "KR"
): Promise<InstrumentIngestResponse> {
  return apiFetch<InstrumentIngestResponse>(
    `/instruments/${encodeURIComponent(ticker)}/ingest?market=${market}`,
    { method: "POST" }
  );
}

export async function queueInstrumentHydration(
  ticker: string,
  market: "US" | "KR",
  bearerToken?: string
): Promise<HydrationJobCreateResponse> {
  return apiFetch<HydrationJobCreateResponse>(
    `/instruments/${encodeURIComponent(ticker)}/hydrate?market=${market}`,
    {
      method: "POST",
      bearerToken,
    }
  );
}

export async function fetchInstrumentHydrationStatus(
  ticker: string,
  market: "US" | "KR",
  bearerToken?: string
): Promise<HydrationJob> {
  return apiFetch<HydrationJob>(
    `/instruments/${encodeURIComponent(ticker)}/hydrate-status?market=${market}`,
    {
      bearerToken,
    }
  );
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

export async function fetchUniverseBrowse(
  params: BrowseQueryParams = {}
): Promise<BrowseResponse> {
  const qs = new URLSearchParams();
  if (params.market) qs.set("market", params.market);
  if (params.asset_type) qs.set("asset_type", params.asset_type);
  if (params.coverage_state) qs.set("coverage_state", params.coverage_state);
  if (params.exclude_ranked != null) {
    qs.set("exclude_ranked", String(params.exclude_ranked));
  }
  if (params.limit != null) qs.set("limit", String(params.limit));
  if (params.offset != null) qs.set("offset", String(params.offset));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const raw = await apiFetch<RawBrowseResponse>(`/universe/browse${suffix}`);
  return normalizeBrowseResponse(raw);
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

export async function fetchWatchlist(bearerToken: string): Promise<WatchlistResponse> {
  return apiFetch<WatchlistResponse>("/watchlist", { bearerToken });
}

export async function addToWatchlist(
  ticker: string,
  market: "US" | "KR",
  bearerToken: string
): Promise<WatchlistItem> {
  return apiFetch<WatchlistItem>(
    `/watchlist/${encodeURIComponent(market)}/${encodeURIComponent(ticker)}`,
    { method: "POST", bearerToken }
  );
}

export async function removeFromWatchlist(
  ticker: string,
  market: "US" | "KR",
  bearerToken: string
): Promise<void> {
  await apiFetch<void>(
    `/watchlist/${encodeURIComponent(market)}/${encodeURIComponent(ticker)}`,
    { method: "DELETE", bearerToken }
  );
}
