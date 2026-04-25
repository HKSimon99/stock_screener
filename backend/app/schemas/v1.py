"""
Response schemas for the Consensus Stock Research Platform API v1.

All schemas are Pydantic v2 models.  They are intentionally kept separate
from the ORM models so the API contract can evolve independently of the DB.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Shared / Building Blocks
# =============================================================================

class StrategyScores(BaseModel):
    canslim:   Optional[float] = None
    piotroski: Optional[float] = None
    minervini: Optional[float] = None
    weinstein: Optional[float] = None


class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool


class FreshnessSummary(BaseModel):
    price_as_of: Optional[date] = None
    quarterly_as_of: Optional[date] = None
    annual_as_of: Optional[date] = None
    ranked_as_of: Optional[date] = None


class RankingEligibility(BaseModel):
    eligible: bool = False
    reasons: list[str] = Field(default_factory=list)


# =============================================================================
# Rankings (5.1)
# =============================================================================

class RankingEntry(BaseModel):
    rank:                int
    instrument_id:       int
    ticker:              str
    name:                str
    name_kr:             Optional[str] = None
    market:              str
    exchange:            Optional[str] = None
    asset_type:          Optional[str] = None
    conviction_level:    str                       # DIAMOND | PLATINUM | GOLD | SILVER | BRONZE | UNRANKED
    final_score:         float
    consensus_composite: Optional[float] = None
    technical_composite: Optional[float] = None
    strategy_pass_count: int
    scores:              StrategyScores
    weinstein_stage:     Optional[str] = None      # '1' | '2_early' | '2_mid' | '2_late' | '3' | '4' — used for gate display
    regime_warning:      bool = False
    score_date:          date
    coverage_state:      Optional[str] = None
    rank_model_version:  Optional[str] = None


class RankingsResponse(BaseModel):
    score_date:           Optional[date] = None   # None when no scores exist yet for this market
    market:               str
    regime_state:         Optional[str] = None
    regime_warning_count: int = 0
    pagination:           PaginationMeta
    items:                list[RankingEntry]


# =============================================================================
# Instrument Detail (5.2)
# =============================================================================

class CANSLIMDetail(BaseModel):
    score:    Optional[float] = None
    c:        Optional[float] = None   # Current earnings
    a:        Optional[float] = None   # Annual earnings
    n:        Optional[float] = None   # New products / highs
    s:        Optional[float] = None   # Supply / demand
    l:        Optional[float] = None   # Leader RS
    i:        Optional[float] = None   # Institutional sponsorship
    raw:      Optional[dict]  = None   # Full detail JSON


class PiotroskiDetail(BaseModel):
    score:    Optional[float] = None
    f_raw:    Optional[int]   = None   # 0-9 raw F-score
    criteria: Optional[dict]  = None   # F1-F9 pass/fail


class MinerviniDetail(BaseModel):
    score:          Optional[float] = None
    criteria_count: Optional[int]   = None   # Of 8 criteria
    criteria:       Optional[dict]  = None   # T1-T8 pass/fail


class WeinsteinDetail(BaseModel):
    score:  Optional[float] = None
    stage:  Optional[str]   = None   # '1'|'2_early'|'2_mid'|'2_late'|'3'|'4'
    detail: Optional[dict]  = None


class TechnicalDetail(BaseModel):
    composite:       Optional[float] = None
    rs_rating:       Optional[float] = None
    ad_rating:       Optional[str]   = None
    bb_squeeze:      Optional[bool]  = None
    rs_line_new_high: Optional[bool] = None
    patterns:        list[dict]      = Field(default_factory=list)
    detail:          Optional[dict]  = None


class PriceMetrics(BaseModel):
    trade_date: Optional[date] = None
    close: Optional[float] = None
    previous_close: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None
    avg_volume_50d: Optional[int] = None


class QuarterlyMetrics(BaseModel):
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    report_date: Optional[date] = None
    revenue: Optional[int] = None
    net_income: Optional[int] = None
    eps: Optional[float] = None
    eps_diluted: Optional[float] = None
    revenue_yoy_growth: Optional[float] = None
    eps_yoy_growth: Optional[float] = None
    data_source: Optional[str] = None


class AnnualMetrics(BaseModel):
    fiscal_year: Optional[int] = None
    report_date: Optional[date] = None
    revenue: Optional[int] = None
    gross_profit: Optional[int] = None
    net_income: Optional[int] = None
    eps: Optional[float] = None
    eps_diluted: Optional[float] = None
    eps_yoy_growth: Optional[float] = None
    total_assets: Optional[int] = None
    current_assets: Optional[int] = None
    current_liabilities: Optional[int] = None
    long_term_debt: Optional[int] = None
    shares_outstanding_annual: Optional[int] = None
    operating_cash_flow: Optional[int] = None
    roa: Optional[float] = None
    current_ratio: Optional[float] = None
    gross_margin: Optional[float] = None
    asset_turnover: Optional[float] = None
    leverage_ratio: Optional[float] = None
    data_source: Optional[str] = None


class MarketMetrics(BaseModel):
    price_as_of: Optional[date] = None
    share_count_source: Optional[str] = None
    trailing_eps_source: Optional[str] = None
    market_cap: Optional[float] = None
    float_market_cap: Optional[float] = None
    trailing_pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None


class OwnershipMetrics(BaseModel):
    report_date: Optional[date] = None
    data_source: Optional[str] = None
    num_institutional_owners: Optional[int] = None
    institutional_pct: Optional[float] = None
    top_fund_quality_score: Optional[float] = None
    qoq_owner_change: Optional[int] = None
    foreign_ownership_pct: Optional[float] = None
    foreign_net_buy_30d: Optional[float] = None
    institutional_net_buy_30d: Optional[float] = None
    individual_net_buy_30d: Optional[float] = None
    is_buyback_active: bool = False


class ScoreHistoryPoint(BaseModel):
    date:                 date
    final_score:          Optional[float] = None
    consensus_composite:  Optional[float] = None
    technical_composite:  Optional[float] = None


class WeinsteinStageHistoryPoint(BaseModel):
    date:   date
    stage:  Optional[str] = None
    score:  Optional[float] = None


class ChartPriceBar(BaseModel):
    time: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    avg_volume_50d: Optional[int] = None
    sma_50: Optional[float] = None
    sma_150: Optional[float] = None
    sma_200: Optional[float] = None


class ChartLinePoint(BaseModel):
    time: date
    value: float


class ChartPatternAnchor(BaseModel):
    time: date
    value: float
    label: Optional[str] = None


class ChartPatternOverlay(BaseModel):
    pattern_type: str
    status: Optional[str] = None
    confidence: float
    pivot_price: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    anchors: list[ChartPatternAnchor] = Field(default_factory=list)


class InstrumentChartResponse(BaseModel):
    ticker: str
    market: str
    score_date: date
    interval: str = "1d"
    range_days: int = 350
    benchmark_ticker: Optional[str] = None
    benchmark_available: bool = False
    benchmark_note: Optional[str] = None
    freshness: FreshnessSummary = Field(default_factory=FreshnessSummary)
    delay_minutes: Optional[int] = None
    bars: list[ChartPriceBar] = Field(default_factory=list)
    rs_line: list[ChartLinePoint] = Field(default_factory=list)
    patterns: list[ChartPatternOverlay] = Field(default_factory=list)


class InstrumentDetailResponse(BaseModel):
    instrument_id: int
    ticker:        str
    name:          str
    name_kr:       Optional[str] = None
    market:        str
    asset_type:    Optional[str] = None
    score_date:    date
    exchange:      Optional[str] = None
    listing_status: Optional[str] = None
    sector:        Optional[str] = None
    industry_group: Optional[str] = None
    shares_outstanding: Optional[int] = None
    float_shares: Optional[int] = None
    is_test_issue: bool = False
    coverage_state: Optional[str] = None
    ranking_eligibility: RankingEligibility = Field(default_factory=RankingEligibility)
    freshness: FreshnessSummary = Field(default_factory=FreshnessSummary)
    delay_minutes: Optional[int] = None
    rank_model_version: Optional[str] = None
    needs_refresh: bool = False

    conviction_level:    str
    final_score:         Optional[float] = None
    consensus_composite: Optional[float] = None
    strategy_pass_count: Optional[int]   = None
    weinstein_stage:     Optional[str]   = None   # For UI gate visibility

    canslim:    CANSLIMDetail     = Field(default_factory=CANSLIMDetail)
    piotroski:  PiotroskiDetail   = Field(default_factory=PiotroskiDetail)
    minervini:  MinerviniDetail   = Field(default_factory=MinerviniDetail)
    weinstein:  WeinsteinDetail   = Field(default_factory=WeinsteinDetail)
    technical:  TechnicalDetail   = Field(default_factory=TechnicalDetail)
    price_metrics: PriceMetrics = Field(default_factory=PriceMetrics)
    quarterly_metrics: Optional[QuarterlyMetrics] = None
    annual_metrics: Optional[AnnualMetrics] = None
    market_metrics: Optional[MarketMetrics] = None
    ownership_metrics: Optional[OwnershipMetrics] = None

    score_breakdown: Optional[dict] = None
    factor_breakdown: Optional[dict] = None
    score_history: list[ScoreHistoryPoint] = Field(default_factory=list)
    weinstein_stage_history: list[WeinsteinStageHistoryPoint] = Field(default_factory=list)
    computed_at:     Optional[datetime] = None


# =============================================================================
# Strategy Rankings (5.3)
# =============================================================================

class StrategyRankingEntry(BaseModel):
    rank:          int
    instrument_id: int
    ticker:        str
    name:          str
    market:        str
    score:         Optional[float] = None
    detail:        Optional[dict]  = None
    score_date:    date


class StrategyRankingsResponse(BaseModel):
    strategy:   str
    score_date: date
    market:     Optional[str] = None
    pagination: PaginationMeta
    items:      list[StrategyRankingEntry]


# =============================================================================
# Filter Query (5.3)
# =============================================================================

class FilterQuery(BaseModel):
    market:           Optional[str]   = None
    conviction_level: Optional[list[str]] = None     # ["DIAMOND", "GOLD"]
    min_final_score:  Optional[float] = None
    max_final_score:  Optional[float] = None
    min_canslim:      Optional[float] = None
    min_piotroski:    Optional[float] = None
    min_piotroski_f:  Optional[int]   = None         # Raw F-score (0-9)
    min_minervini:    Optional[float] = None
    minervini_criteria_min: Optional[int] = None     # Of 8 criteria
    weinstein_stage:  Optional[list[str]] = None     # ["2_early", "2_mid"]
    ad_rating:        Optional[list[str]] = None     # ["A+", "A", "B"]
    rs_line_new_high: Optional[bool]  = None
    has_pattern:      Optional[str]   = None         # pattern_type filter
    limit:            int = Field(default=50, ge=1, le=200)
    offset:           int = Field(default=0, ge=0)
    sort_by:          str = Field(
        default="final_score",
        pattern="^(final_score|consensus_composite|technical_composite|canslim_score|piotroski_score|minervini_score|weinstein_score)$"
    )
    sort_dir:         str = Field(default="desc", pattern="^(asc|desc)$")


class FilterResponse(BaseModel):
    score_date:  date
    total_found: int
    pagination:  PaginationMeta
    items:       list[RankingEntry]


# =============================================================================
# Market Regime (5.4)
# =============================================================================

class RegimeEntry(BaseModel):
    market:                str
    state:                 str
    prior_state:           Optional[str]  = None
    trigger_reason:        Optional[str]  = None
    effective_date:        date
    drawdown_from_high:    Optional[float] = None
    distribution_day_count: Optional[int] = None
    follow_through_day:    bool = False


class MarketRegimeResponse(BaseModel):
    us: Optional[RegimeEntry] = None
    kr: Optional[RegimeEntry] = None
    history: list[RegimeEntry] = Field(default_factory=list)


# =============================================================================
# Snapshots (5.4)
# =============================================================================

class SnapshotMeta(BaseModel):
    snapshot_date:        date
    market:               str
    asset_type:           str
    regime_state:         Optional[str]   = None
    instruments_count:    int
    config_hash:          str
    avg_final_score:      float
    conviction_distribution: dict[str, int]
    created_at:           datetime


class SnapshotResponse(BaseModel):
    meta:    SnapshotMeta
    items:   list[dict]  # Full rankings_json entries


# =============================================================================
# Search / Coverage
# =============================================================================


class SearchResultEntry(BaseModel):
    instrument_id: int
    ticker: str
    name: str
    name_kr: Optional[str] = None
    market: str
    exchange: str
    asset_type: str
    listing_status: str
    coverage_state: str
    ranking_eligibility: RankingEligibility = Field(default_factory=RankingEligibility)
    rank_model_version: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    total: int
    items: list[SearchResultEntry]


class BrowseResultEntry(BaseModel):
    instrument_id: int
    ticker: str
    name: str
    name_kr: Optional[str] = None
    market: str
    exchange: str
    asset_type: str
    listing_status: str
    sector: Optional[str] = None
    industry_group: Optional[str] = None
    coverage_state: str
    ranking_eligibility: RankingEligibility = Field(default_factory=RankingEligibility)
    freshness: FreshnessSummary = Field(default_factory=FreshnessSummary)
    delay_minutes: Optional[int] = None
    rank_model_version: Optional[str] = None


class BrowseResponse(BaseModel):
    pagination: PaginationMeta
    items: list[BrowseResultEntry]


class CoverageBucket(BaseModel):
    market: str
    asset_type: str
    searchable: int
    price_ready: int
    fundamentals_ready: int
    ranked: int


class UniverseCoverageResponse(BaseModel):
    as_of: datetime
    items: list[CoverageBucket]


# =============================================================================
# Alerts (5.4)
# =============================================================================

class AlertEntry(BaseModel):
    id:            int
    instrument_id: Optional[int] = None
    market:        Optional[str] = None
    ticker:        Optional[str] = None
    alert_type:    str
    severity:      str   # CRITICAL | WARNING | INFO
    title:         Optional[str] = None
    detail:        Optional[str] = None
    threshold_value: Optional[float] = None
    actual_value:  Optional[float] = None
    is_read:       bool = False
    created_at:    datetime


class AlertsResponse(BaseModel):
    total:      int
    critical:   int
    warnings:   int
    items:      list[AlertEntry]


# =============================================================================
# Scoring Task Trigger (used by admin / scheduling)
# =============================================================================

class ScoringTriggerRequest(BaseModel):
    market:         Optional[str]       = None
    instrument_ids: Optional[list[int]] = None
    score_date:     Optional[date]      = None


class ScoringTriggerResponse(BaseModel):
    task_id:    str
    status:     str   # "queued" | "started"
    message:    str


# =============================================================================
# Hydration Jobs
# =============================================================================

class HydrationJobResponse(BaseModel):
    id: int
    ticker: str
    market: str
    instrument_id: Optional[int] = None
    status: str
    requester_source: str
    requester_user_id: Optional[str] = None
    celery_task_id: Optional[str] = None
    queued_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    updated_at: datetime
    error_message: Optional[str] = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class HydrationJobCreateResponse(BaseModel):
    job: HydrationJobResponse
    created: bool
    message: str


# =============================================================================
# Admin Backfill
# =============================================================================


class AdminBackfillRequest(BaseModel):
    market: str = Field(pattern="^(US|KR)$")
    tickers: Optional[list[str]] = None
    limit: Optional[int] = Field(default=None, ge=1, le=10000)
    dry_run: bool = True
    price_only: bool = False
    score: bool = False


class AdminBackfillPreview(BaseModel):
    market: str
    selection_mode: str
    requested_count: int
    selected_count: int
    unresolved_count: int
    existing_count: int
    resolved_from_provider_count: int
    limit_requested: Optional[int] = None
    chunk_size: int
    chunk_count: int
    price_only: bool = False
    score_requested: bool = False
    sample_selected_tickers: list[str] = Field(default_factory=list)
    sample_unresolved_tickers: list[str] = Field(default_factory=list)


class AdminBackfillRunResponse(BaseModel):
    id: int
    market: str
    requested_tickers: list[str] = Field(default_factory=list)
    selected_tickers: list[str] = Field(default_factory=list)
    limit_requested: Optional[int] = None
    chunk_size: int
    price_only: bool = False
    score_requested: bool = False
    status: str
    requester_source: str
    requester_user_id: Optional[str] = None
    celery_task_id: Optional[str] = None
    requested_count: int
    selected_count: int
    processed_count: int
    failed_count: int
    queued_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    updated_at: datetime
    error_message: Optional[str] = None
    result_metadata: dict[str, Any] = Field(default_factory=dict)


class AdminBackfillResponse(BaseModel):
    dry_run: bool
    preview: AdminBackfillPreview
    run: Optional[AdminBackfillRunResponse] = None
    message: str


# =============================================================================
# Watchlist
# =============================================================================


class WatchlistItemResponse(BaseModel):
    id: int
    instrument_id: int
    market: str
    ticker: str
    name: Optional[str] = None
    name_kr: Optional[str] = None
    added_at: datetime


class WatchlistResponse(BaseModel):
    items: list[WatchlistItemResponse]
    total: int
