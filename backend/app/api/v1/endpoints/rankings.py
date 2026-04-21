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
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_read_db
from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.market_regime import MarketRegime
from app.models.strategy_score import StrategyScore
from app.schemas.v1 import (
    PaginationMeta,
    RankingEntry,
    RankingsResponse,
    StrategyScores,
)
from app.services.universe import RANK_MODEL_VERSION

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
        f"{limit}:{offset}:{total}"
    )
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return f'W/"{digest}"'


router = APIRouter()


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
        3  market
        4  exchange
        5  asset_type
        6  conviction_level
        7  final_score
        8  consensus_composite
        9  technical_composite
        10 strategy_pass_count
        11 canslim_score
        12 piotroski_score
        13 minervini_score
        14 weinstein_score
        15 regime_warning
        16 score_date
        17 weinstein_stage
        18 total_count  (from COUNT(*) OVER ())
    """
    return RankingEntry(
        rank=rank,
        instrument_id=row[0],
        ticker=row[1],
        name=row[2] or "",
        market=row[3],
        exchange=row[4],
        asset_type=row[5],
        conviction_level=row[6] or "UNRANKED",
        final_score=_f(row[7]) or 0.0,
        consensus_composite=_f(row[8]),
        technical_composite=_f(row[9]),
        strategy_pass_count=row[10] or 0,
        scores=StrategyScores(
            canslim=_f(row[11]),
            piotroski=_f(row[12]),
            minervini=_f(row[13]),
            weinstein=_f(row[14]),
        ),
        weinstein_stage=row[17],
        regime_warning=bool(row[15]) if row[15] is not None else False,
        score_date=row[16],
        coverage_state="ranked",
        rank_model_version=RANK_MODEL_VERSION,
    )


async def _latest_consensus_date(market: Optional[str], db: AsyncSession) -> Optional[date]:
    q = select(func.max(ConsensusScore.score_date))
    if market:
        q = q.join(Instrument, ConsensusScore.instrument_id == Instrument.id).where(
            Instrument.market == market
        )
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def _get_regime(market: str, score_date: date, db: AsyncSession) -> Optional[str]:
    q = await db.execute(
        select(MarketRegime.state)
        .where(MarketRegime.market == market, MarketRegime.effective_date <= score_date)
        .order_by(desc(MarketRegime.effective_date))
        .limit(1)
    )
    return q.scalar_one_or_none()


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
            Instrument.market,                           # 3
            Instrument.exchange,                         # 4
            Instrument.asset_type,                       # 5
            ConsensusScore.conviction_level,             # 6
            ConsensusScore.final_score,                  # 7
            ConsensusScore.consensus_composite,          # 8
            ConsensusScore.technical_composite,          # 9
            ConsensusScore.strategy_pass_count,          # 10
            ConsensusScore.canslim_score,                # 11
            ConsensusScore.piotroski_score,              # 12
            ConsensusScore.minervini_score,              # 13
            ConsensusScore.weinstein_score,              # 14
            ConsensusScore.regime_warning,               # 15
            ConsensusScore.score_date,                   # 16
            StrategyScore.weinstein_stage,               # 17
            total_col,                                   # 18
        )
        .join(Instrument, ConsensusScore.instrument_id == Instrument.id)
        .outerjoin(
            StrategyScore,
            (StrategyScore.instrument_id == ConsensusScore.instrument_id)
            & (StrategyScore.score_date == ConsensusScore.score_date),
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
            ConsensusScore.conviction_level.in_([c.upper() for c in conviction])
        )

    # Order & paginate — indexed by (score_date DESC, instrument_id) after 0006
    stmt = (
        stmt.order_by(desc(ConsensusScore.final_score), Instrument.ticker)
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(stmt)
    rows_live = result.all()

    total = rows_live[0][18] if rows_live else 0
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
