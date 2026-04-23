"""
GET /api/v1/rankings
GET /api/v1/rankings/{ticker}  (convenience redirect to instruments)

Returns the consensus-ranked list of instruments, optionally filtered by
market, conviction level, asset_type, and date.

Implementation (Phase 4.7 refactor)
-----------------------------------
Queries ``consensus_scores`` directly (no more snapshot-JSON filtering in
Python). The snapshot fallback was removed because it required Python-side
pagination and filtering that couldn't leverage DB indexes; the direct
query uses the ``idx_cs_score_date`` composite index (see migration 0006)
and returns the total in the same round-trip via a
``COUNT(*) OVER ()`` window function — eliminating the separate count query.

Query parameters
----------------
market          US | KR (default: all)
conviction      DIAMOND | PLATINUM | GOLD | SILVER | BRONZE | UNRANKED (repeatable)
asset_type      stock | etf (default: stock)
score_date      ISO date (default: latest available)
limit           1-200 (default 50)
offset          int (default 0)
thresholds      min/max final score, min consensus/technical composite,
                min strategy pass count, and per-strategy minimums
metadata        sector, exchange, coverage_state
technicals      weinstein_stage, ad_rating, rs_line_new_high, min_rs_rating
readiness       price_ready, fundamentals_ready, *_as_of_gte/lte freshness dates
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import false, select, desc, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_read_db
from app.models.consensus_score import ConsensusScore
from app.models.coverage_summary import InstrumentCoverageSummary
from app.models.instrument import Instrument
from app.models.market_regime import MarketRegime
from app.models.strategy_score import StrategyScore
from app.schemas.v1 import (
    PaginationMeta,
    RankingEntry,
    RankingsResponse,
    StrategyScores,
)
from app.services.request_cache import TtlCache
from app.services.universe import (
    LEGACY_COVERAGE_TO_PUBLIC,
    RANK_MODEL_VERSION,
    public_coverage_state_for,
    public_coverage_state_sql_expressions,
)

# Rankings data changes at most once per day (after the scoring pipeline runs).
# Tell downstream caches — browsers, CDN, reverse proxies — to keep the
# response for 5 minutes and serve stale while revalidating for another minute.
_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=60"


def _make_etag(
    score_date,
    market: str,
    asset_type: str,
    conviction: list[str],
    limit: int,
    offset: int,
    total: int,
    filters_key: str = "",
) -> str:
    """
    Deterministic weak ETag that fingerprints every dimension a client can
    vary. Previously the ETag ignored ``conviction``, ``limit`` and
    ``offset``, which caused different filter combinations to collide on
    the same cache entry.
    """
    # Normalise conviction (order-insensitive, case-insensitive)
    conviction_key = ",".join(sorted(c.upper() for c in conviction)) or "*"
    key = (
        f"{score_date}:{market}:{asset_type}:{conviction_key}:"
        f"{limit}:{offset}:{total}:{filters_key}"
    )
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return f'W/"{digest}"'


router = APIRouter()
_LATEST_CONSENSUS_DATE_CACHE = TtlCache[Optional[date]](ttl_seconds=60)
_REGIME_CACHE = TtlCache[Optional[str]](ttl_seconds=60)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _f(val) -> Optional[float]:
    return float(val) if val is not None else None


def _entry_from_row(
    row: tuple,
    rank: int,
) -> RankingEntry:
    """Convert a joined query row into a RankingEntry.

    ``row`` tuple layout (must match the SELECT order in ``get_rankings``):
        0  instrument_id
        1  ticker
        2  name
        3  name_kr
        4  market
        5  exchange
        6  asset_type
        7  conviction_level
        8  final_score
        9  consensus_composite
        10 technical_composite
        11 strategy_pass_count
        12 canslim_score
        13 piotroski_score
        14 minervini_score
        15 weinstein_score
        16 regime_warning
        17 score_date
        18 weinstein_stage
        19 coverage_state
        20 price_as_of
        21 quarterly_as_of
        22 annual_as_of
        23 ranked_as_of
        24 total_count  (from COUNT(*) OVER ())
    """
    if row[19] is None:
        coverage_state = "ranked"
    else:
        coverage_state = public_coverage_state_for(
            market=row[4],
            asset_type=row[6] or "stock",
            internal_coverage_state=row[19] or "ranked",
            price_as_of=row[20],
            quarterly_as_of=row[21],
            annual_as_of=row[22],
            ranked_as_of=row[23],
        )[0]

    return RankingEntry(
        rank=rank,
        instrument_id=row[0],
        ticker=row[1],
        name=row[2] or "",
        name_kr=row[3],
        market=row[4],
        exchange=row[5],
        asset_type=row[6],
        conviction_level=row[7] or "UNRANKED",
        final_score=_f(row[8]) or 0.0,
        consensus_composite=_f(row[9]),
        technical_composite=_f(row[10]),
        strategy_pass_count=row[11] or 0,
        scores=StrategyScores(
            canslim=_f(row[12]),
            piotroski=_f(row[13]),
            minervini=_f(row[14]),
            weinstein=_f(row[15]),
        ),
        weinstein_stage=row[18],
        regime_warning=bool(row[16]) if row[16] is not None else False,
        score_date=row[17],
        coverage_state=coverage_state,
        rank_model_version=RANK_MODEL_VERSION,
    )


def _normalise_list(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value and value.strip()]


def _normalise_upper_list(values: list[str]) -> list[str]:
    return [value.upper() for value in _normalise_list(values)]


def _make_filters_key(filters: dict[str, object]) -> str:
    parts: list[str] = []
    for key in sorted(filters):
        value = filters[key]
        if value is None or value == []:
            continue
        if isinstance(value, list):
            value = ",".join(str(item) for item in sorted(value))
        parts.append(f"{key}={value}")
    return "&".join(parts)


async def _latest_consensus_date(market: Optional[str], db: AsyncSession) -> Optional[date]:
    cache_key = market or "*"
    cached = _LATEST_CONSENSUS_DATE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    q = select(func.max(ConsensusScore.score_date))
    if market:
        q = q.join(Instrument, ConsensusScore.instrument_id == Instrument.id).where(
            Instrument.market == market
        )
    result = await db.execute(q)
    return _LATEST_CONSENSUS_DATE_CACHE.set(cache_key, result.scalar_one_or_none())


async def _get_regime(market: str, score_date: date, db: AsyncSession) -> Optional[str]:
    cache_key = f"{market}:{score_date.isoformat()}"
    cached = _REGIME_CACHE.get(cache_key)
    if cached is not None:
        return cached
    q = await db.execute(
        select(MarketRegime.state)
        .where(MarketRegime.market == market, MarketRegime.effective_date <= score_date)
        .order_by(desc(MarketRegime.effective_date))
        .limit(1)
    )
    return _REGIME_CACHE.set(cache_key, q.scalar_one_or_none())


# ---------------------------------------------------------------------------
# GET /rankings
# ---------------------------------------------------------------------------


@router.get("", response_model=RankingsResponse, summary="Get ranked instrument list")
async def get_rankings(
    request: Request,
    response: Response,
    market: Optional[str] = Query(None, pattern="^(US|KR)$"),
    conviction: list[str] = Query(default=[]),
    asset_type: str = Query(default="stock", pattern="^(stock|etf)$"),
    score_date: Optional[date] = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    min_final_score: Optional[float] = Query(None, ge=0, le=100),
    max_final_score: Optional[float] = Query(None, ge=0, le=100),
    min_consensus_composite: Optional[float] = Query(None, ge=0, le=100),
    min_technical_composite: Optional[float] = Query(None, ge=0, le=100),
    min_strategy_pass_count: Optional[int] = Query(None, ge=0, le=10),
    min_canslim: Optional[float] = Query(None, ge=0, le=100),
    min_piotroski: Optional[float] = Query(None, ge=0, le=100),
    min_minervini: Optional[float] = Query(None, ge=0, le=100),
    min_weinstein: Optional[float] = Query(None, ge=0, le=100),
    min_rs_rating: Optional[float] = Query(None, ge=0, le=100),
    sector: list[str] = Query(default=[]),
    exchange: list[str] = Query(default=[]),
    coverage_state: list[str] = Query(default=[]),
    weinstein_stage: list[str] = Query(default=[]),
    ad_rating: list[str] = Query(default=[]),
    rs_line_new_high: Optional[bool] = Query(None),
    price_ready: Optional[bool] = Query(None),
    fundamentals_ready: Optional[bool] = Query(None),
    price_as_of_gte: Optional[date] = Query(None),
    price_as_of_lte: Optional[date] = Query(None),
    quarterly_as_of_gte: Optional[date] = Query(None),
    annual_as_of_gte: Optional[date] = Query(None),
    ranked_as_of_gte: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_read_db),
) -> RankingsResponse:
    """
    Returns the consensus-ranked list using a direct indexed query.

    Uses ``COUNT(*) OVER ()`` so the total row count is returned in the
    same query as the page, avoiding a second round-trip. The LEFT JOIN
    to ``strategy_scores`` attaches the Weinstein stage so the UI can
    show the gate reason ("capped at SILVER because Stage 1") without
    hitting the instrument-detail endpoint.
    """
    # ── Resolve score_date ──────────────────────────────────────────────────
    if score_date is None:
        score_date = await _latest_consensus_date(market, db)
    if score_date is None:
        raise HTTPException(
            404, detail="No consensus scores found. Run the scoring pipeline first."
        )

    # ── Build direct query with window-function count ───────────────────────
    # Window function gives total matching rows (pre-limit/offset) in the
    # same round-trip — no separate COUNT query needed.
    total_col = func.count().over().label("total_count")

    stmt = (
        select(
            ConsensusScore.instrument_id,                # 0
            Instrument.ticker,                           # 1
            Instrument.name,                             # 2
            Instrument.name_kr,                          # 3
            Instrument.market,                           # 4
            Instrument.exchange,                         # 5
            Instrument.asset_type,                       # 6
            ConsensusScore.conviction_level,             # 7
            ConsensusScore.final_score,                  # 8
            ConsensusScore.consensus_composite,          # 9
            ConsensusScore.technical_composite,          # 10
            ConsensusScore.strategy_pass_count,          # 11
            ConsensusScore.canslim_score,                # 12
            ConsensusScore.piotroski_score,              # 13
            ConsensusScore.minervini_score,              # 14
            ConsensusScore.weinstein_score,              # 15
            ConsensusScore.regime_warning,               # 16
            ConsensusScore.score_date,                   # 17
            StrategyScore.weinstein_stage,               # 18
            InstrumentCoverageSummary.coverage_state,     # 19
            InstrumentCoverageSummary.price_as_of,        # 20
            InstrumentCoverageSummary.quarterly_as_of,    # 21
            InstrumentCoverageSummary.annual_as_of,       # 22
            InstrumentCoverageSummary.ranked_as_of,       # 23
            total_col,                                   # 24
        )
        .join(Instrument, ConsensusScore.instrument_id == Instrument.id)
        .outerjoin(
            StrategyScore,
            (StrategyScore.instrument_id == ConsensusScore.instrument_id)
            & (StrategyScore.score_date == ConsensusScore.score_date),
        )
        .outerjoin(
            InstrumentCoverageSummary,
            InstrumentCoverageSummary.instrument_id == ConsensusScore.instrument_id,
        )
        .where(
            ConsensusScore.score_date == score_date,
            Instrument.is_active.is_(True),
            Instrument.asset_type == asset_type,
        )
    )
    if market:
        stmt = stmt.where(Instrument.market == market)
    if conviction:
        # Normalise to upper-case to match the DB convention
        stmt = stmt.where(
            ConsensusScore.conviction_level.in_(_normalise_upper_list(conviction))
        )
    sector_values = _normalise_list(sector)
    if sector_values:
        stmt = stmt.where(Instrument.sector.in_(sector_values))
    exchange_values = _normalise_list(exchange)
    if exchange_values:
        stmt = stmt.where(Instrument.exchange.in_(exchange_values))
    coverage_values = _normalise_list(coverage_state)
    if coverage_values:
        public_values = {
            LEGACY_COVERAGE_TO_PUBLIC.get(value, value)
            for value in coverage_values
        }
        coverage_expressions = public_coverage_state_sql_expressions()
        summary_exists = InstrumentCoverageSummary.instrument_id.is_not(None)
        selected_expressions = []
        for value in public_values:
            if value == "ranked":
                selected_expressions.append(or_(
                    InstrumentCoverageSummary.instrument_id.is_(None),
                    coverage_expressions["ranked"],
                ))
            elif value in coverage_expressions:
                selected_expressions.append(and_(summary_exists, coverage_expressions[value]))
        stmt = stmt.where(or_(*selected_expressions) if selected_expressions else false())
    weinstein_stage_values = _normalise_list(weinstein_stage)
    if weinstein_stage_values:
        stmt = stmt.where(StrategyScore.weinstein_stage.in_(weinstein_stage_values))
    ad_rating_values = _normalise_upper_list(ad_rating)
    if ad_rating_values:
        stmt = stmt.where(StrategyScore.ad_rating.in_(ad_rating_values))

    if min_final_score is not None:
        stmt = stmt.where(ConsensusScore.final_score >= min_final_score)
    if max_final_score is not None:
        stmt = stmt.where(ConsensusScore.final_score <= max_final_score)
    if min_consensus_composite is not None:
        stmt = stmt.where(ConsensusScore.consensus_composite >= min_consensus_composite)
    if min_technical_composite is not None:
        stmt = stmt.where(ConsensusScore.technical_composite >= min_technical_composite)
    if min_strategy_pass_count is not None:
        stmt = stmt.where(ConsensusScore.strategy_pass_count >= min_strategy_pass_count)
    if min_canslim is not None:
        stmt = stmt.where(ConsensusScore.canslim_score >= min_canslim)
    if min_piotroski is not None:
        stmt = stmt.where(ConsensusScore.piotroski_score >= min_piotroski)
    if min_minervini is not None:
        stmt = stmt.where(ConsensusScore.minervini_score >= min_minervini)
    if min_weinstein is not None:
        stmt = stmt.where(ConsensusScore.weinstein_score >= min_weinstein)
    if min_rs_rating is not None:
        stmt = stmt.where(StrategyScore.rs_rating >= min_rs_rating)
    if rs_line_new_high is not None:
        stmt = stmt.where(StrategyScore.rs_line_new_high.is_(rs_line_new_high))
    if price_ready is not None:
        price_ready_expr = InstrumentCoverageSummary.price_as_of.is_not(None)
        stmt = stmt.where(price_ready_expr if price_ready else or_(
            InstrumentCoverageSummary.instrument_id.is_(None),
            InstrumentCoverageSummary.price_as_of.is_(None),
        ))
    if fundamentals_ready is not None:
        fundamentals_ready_expr = or_(
            InstrumentCoverageSummary.quarterly_as_of.is_not(None),
            InstrumentCoverageSummary.annual_as_of.is_not(None),
        )
        stmt = stmt.where(fundamentals_ready_expr if fundamentals_ready else or_(
            InstrumentCoverageSummary.instrument_id.is_(None),
            and_(
                InstrumentCoverageSummary.quarterly_as_of.is_(None),
                InstrumentCoverageSummary.annual_as_of.is_(None),
            ),
        ))
    if price_as_of_gte is not None:
        stmt = stmt.where(InstrumentCoverageSummary.price_as_of >= price_as_of_gte)
    if price_as_of_lte is not None:
        stmt = stmt.where(InstrumentCoverageSummary.price_as_of <= price_as_of_lte)
    if quarterly_as_of_gte is not None:
        stmt = stmt.where(InstrumentCoverageSummary.quarterly_as_of >= quarterly_as_of_gte)
    if annual_as_of_gte is not None:
        stmt = stmt.where(InstrumentCoverageSummary.annual_as_of >= annual_as_of_gte)
    if ranked_as_of_gte is not None:
        stmt = stmt.where(InstrumentCoverageSummary.ranked_as_of >= ranked_as_of_gte)

    # Order & paginate — indexed by (score_date DESC, instrument_id) after 0006
    stmt = (
        stmt.order_by(desc(ConsensusScore.final_score), Instrument.ticker)
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(stmt)
    rows_live = result.all()

    total = rows_live[0][24] if rows_live else 0
    items = [_entry_from_row(row, offset + idx + 1) for idx, row in enumerate(rows_live)]
    regime = await _get_regime(market or "US", score_date, db) if items else None
    regime_warning_count = sum(1 for it in items if it.regime_warning)

    # ── Caching headers ────────────────────────────────────────────────────
    resolved_market = market or "US"
    etag = _make_etag(
        score_date=score_date,
        market=resolved_market,
        asset_type=asset_type,
        conviction=conviction,
        limit=limit,
        offset=offset,
        total=total,
        filters_key=_make_filters_key({
            "min_final_score": min_final_score,
            "max_final_score": max_final_score,
            "min_consensus_composite": min_consensus_composite,
            "min_technical_composite": min_technical_composite,
            "min_strategy_pass_count": min_strategy_pass_count,
            "min_canslim": min_canslim,
            "min_piotroski": min_piotroski,
            "min_minervini": min_minervini,
            "min_weinstein": min_weinstein,
            "min_rs_rating": min_rs_rating,
            "sector": sector_values,
            "exchange": exchange_values,
            "coverage_state": coverage_values,
            "weinstein_stage": weinstein_stage_values,
            "ad_rating": ad_rating_values,
            "rs_line_new_high": rs_line_new_high,
            "price_ready": price_ready,
            "fundamentals_ready": fundamentals_ready,
            "price_as_of_gte": price_as_of_gte,
            "price_as_of_lte": price_as_of_lte,
            "quarterly_as_of_gte": quarterly_as_of_gte,
            "annual_as_of_gte": annual_as_of_gte,
            "ranked_as_of_gte": ranked_as_of_gte,
        }),
    )
    response.headers["Cache-Control"] = _CACHE_CONTROL
    response.headers["ETag"] = etag

    # Short-circuit with 304 Not Modified if the client already has this ETag
    if request.headers.get("If-None-Match") == etag:
        raise HTTPException(status_code=304)

    return RankingsResponse(
        score_date=score_date,
        market=resolved_market,
        regime_state=regime,
        regime_warning_count=regime_warning_count,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + limit < total,
        ),
        items=items,
    )
