"""
GET  /api/v1/strategies/{name}/rankings  — per-strategy ranked list
POST /api/v1/filters/query               — advanced multi-criteria filter

Strategy names: canslim | piotroski | minervini | weinstein | dual_mom | technical
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, asc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import ClerkAuthUser, get_clerk_user
from app.api.deps import get_db
from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.strategy_score import StrategyScore
from app.schemas.v1 import (
    FilterQuery, FilterResponse, PaginationMeta,
    RankingEntry, StrategyRankingEntry, StrategyRankingsResponse, StrategyScores,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Column map for strategy routing
# ---------------------------------------------------------------------------

_STRATEGY_SCORE_COL = {
    "canslim":    StrategyScore.canslim_score,
    "piotroski":  StrategyScore.piotroski_score,
    "minervini":  StrategyScore.minervini_score,
    "weinstein":  StrategyScore.weinstein_score,
    "dual_mom":   StrategyScore.dual_mom_score,
    "technical":  StrategyScore.technical_composite,
}

_STRATEGY_DETAIL_COL = {
    "canslim":   StrategyScore.canslim_detail,
    "piotroski": StrategyScore.piotroski_detail,
    "minervini": StrategyScore.minervini_detail,
    "weinstein": StrategyScore.weinstein_detail,
    "dual_mom":  StrategyScore.dual_mom_detail,
    "technical": StrategyScore.technical_detail,
}

_CONSENSUS_SORT_COL = {
    "final_score":           ConsensusScore.final_score,
    "consensus_composite":   ConsensusScore.consensus_composite,
    "technical_composite":   ConsensusScore.technical_composite,
    "canslim_score":         ConsensusScore.canslim_score,
    "piotroski_score":       ConsensusScore.piotroski_score,
    "minervini_score":       ConsensusScore.minervini_score,
    "weinstein_score":       ConsensusScore.weinstein_score,
    "dual_mom_score":        ConsensusScore.dual_mom_score,
}


async def _latest_ss_date(market: Optional[str], db: AsyncSession) -> Optional[date]:
    q = select(func.max(StrategyScore.score_date))
    if market:
        q = q.join(Instrument, StrategyScore.instrument_id == Instrument.id).where(
            Instrument.market == market
        )
    result = await db.execute(q)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# GET /strategies/{name}/rankings
# ---------------------------------------------------------------------------

@router.get("/{name}/rankings", response_model=StrategyRankingsResponse,
            summary="Rankings for a single strategy")
async def get_strategy_rankings(
    name:       str,
    market:     Optional[str]  = Query(None, pattern="^(US|KR)$"),
    score_date: Optional[date] = Query(None),
    limit:      int            = Query(default=50, ge=1, le=200),
    offset:     int            = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> StrategyRankingsResponse:
    if name not in _STRATEGY_SCORE_COL:
        raise HTTPException(
            400,
            detail=f"Unknown strategy '{name}'. "
                   f"Valid values: {list(_STRATEGY_SCORE_COL.keys())}"
        )

    if score_date is None:
        score_date = await _latest_ss_date(market, db)
    if score_date is None:
        raise HTTPException(404, detail="No strategy scores found. Run the scoring pipeline first.")

    score_col  = _STRATEGY_SCORE_COL[name]
    detail_col = _STRATEGY_DETAIL_COL[name]

    stmt = (
        select(StrategyScore, Instrument.ticker, Instrument.name, Instrument.market)
        .join(Instrument, StrategyScore.instrument_id == Instrument.id)
        .where(
            StrategyScore.score_date == score_date,
            Instrument.is_active == True,
            score_col.isnot(None),
        )
    )
    if market:
        stmt = stmt.where(Instrument.market == market)

    # Count
    count_q = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_q.scalar_one()

    # Page
    stmt = stmt.order_by(desc(score_col)).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).all()

    items = [
        StrategyRankingEntry(
            rank          = offset + idx + 1,
            instrument_id = ss.instrument_id,
            ticker        = ticker,
            name          = name_,
            market        = mkt,
            score         = float(getattr(ss, score_col.key)) if getattr(ss, score_col.key) is not None else None,
            detail        = getattr(ss, detail_col.key),
            score_date    = ss.score_date,
        )
        for idx, (ss, ticker, name_, mkt) in enumerate(rows)
    ]

    return StrategyRankingsResponse(
        strategy   = name,
        score_date = score_date,
        market     = market,
        pagination = PaginationMeta(
            total    = total,
            limit    = limit,
            offset   = offset,
            has_more = offset + limit < total,
        ),
        items = items,
    )


# ---------------------------------------------------------------------------
# POST /filters/query
# ---------------------------------------------------------------------------

filter_router = APIRouter()


@filter_router.post("/query", response_model=FilterResponse, summary="Advanced multi-criteria filter")
async def filter_instruments(
    body:       FilterQuery,
    score_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: ClerkAuthUser = Depends(get_clerk_user),
) -> FilterResponse:
    """
    Flexible filter endpoint.  All filter fields are optional — omit any
    field to skip that criterion.

    Supports filtering by:
    - conviction_level  (DIAMOND, GOLD, SILVER, …)
    - final_score range
    - individual strategy minimum scores
    - Piotroski raw F-score
    - Minervini criteria count
    - Weinstein stage list
    - dual_mom pass flag
    - A/D rating list
    - RS Line new-high flag
    - Pattern type presence (matches against pattern_type in patterns JSONB array)
    """
    _ = current_user
    if score_date is None:
        date_q = await db.execute(select(func.max(ConsensusScore.score_date)))
        score_date = date_q.scalar_one_or_none()
    if score_date is None:
        raise HTTPException(404, detail="No consensus scores found.")

    # Base join: consensus + strategy + instrument
    stmt = (
        select(
            ConsensusScore,
            StrategyScore,
            Instrument.ticker,
            Instrument.name,
            Instrument.market,
        )
        .join(Instrument, ConsensusScore.instrument_id == Instrument.id)
        .join(
            StrategyScore,
            (StrategyScore.instrument_id == ConsensusScore.instrument_id)
            & (StrategyScore.score_date == ConsensusScore.score_date),
            isouter=True,
        )
        .where(ConsensusScore.score_date == score_date, Instrument.is_active == True)
    )

    # ── Filters ──────────────────────────────────────────────────────────────
    if body.market:
        stmt = stmt.where(Instrument.market == body.market)
    if body.conviction_level:
        stmt = stmt.where(ConsensusScore.conviction_level.in_(body.conviction_level))
    if body.min_final_score is not None:
        stmt = stmt.where(ConsensusScore.final_score >= body.min_final_score)
    if body.max_final_score is not None:
        stmt = stmt.where(ConsensusScore.final_score <= body.max_final_score)
    if body.min_canslim is not None:
        stmt = stmt.where(ConsensusScore.canslim_score >= body.min_canslim)
    if body.min_piotroski is not None:
        stmt = stmt.where(ConsensusScore.piotroski_score >= body.min_piotroski)
    if body.min_piotroski_f is not None:
        stmt = stmt.where(StrategyScore.piotroski_f_raw >= body.min_piotroski_f)
    if body.min_minervini is not None:
        stmt = stmt.where(ConsensusScore.minervini_score >= body.min_minervini)
    if body.minervini_criteria_min is not None:
        stmt = stmt.where(StrategyScore.minervini_criteria_count >= body.minervini_criteria_min)
    if body.weinstein_stage:
        stmt = stmt.where(StrategyScore.weinstein_stage.in_(body.weinstein_stage))
    if body.ad_rating:
        stmt = stmt.where(StrategyScore.ad_rating.in_(body.ad_rating))
    if body.rs_line_new_high is not None:
        stmt = stmt.where(StrategyScore.rs_line_new_high == body.rs_line_new_high)
    if body.has_pattern:
        stmt = stmt.where(
            StrategyScore.patterns.contains([{"pattern_type": body.has_pattern}])
        )

    # ── Sorting ───────────────────────────────────────────────────────────────
    sort_col = _CONSENSUS_SORT_COL.get(body.sort_by, ConsensusScore.final_score)
    order = desc(sort_col) if body.sort_dir == "desc" else asc(sort_col)

    # Count
    count_q = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_q.scalar_one()

    # Page
    stmt = stmt.order_by(order).limit(body.limit).offset(body.offset)
    rows = (await db.execute(stmt)).all()

    items = []
    for rank_idx, (cs, ss, ticker, instr_name, mkt) in enumerate(rows):
        bd = cs.score_breakdown or {}
        strat = bd.get("strategy_scores", {})
        items.append(RankingEntry(
            rank              = body.offset + rank_idx + 1,
            instrument_id     = cs.instrument_id,
            ticker            = ticker,
            name              = instr_name,
            market            = mkt,
            conviction_level  = cs.conviction_level,
            final_score       = float(cs.final_score)           if cs.final_score           else 0.0,
            consensus_composite = float(cs.consensus_composite) if cs.consensus_composite   else None,
            technical_composite = float(cs.technical_composite) if cs.technical_composite   else None,
            strategy_pass_count = cs.strategy_pass_count or 0,
            scores = StrategyScores(
                canslim   = float(cs.canslim_score)   if cs.canslim_score   else None,
                piotroski = float(cs.piotroski_score) if cs.piotroski_score else None,
                minervini = float(cs.minervini_score) if cs.minervini_score else None,
                weinstein = float(cs.weinstein_score) if cs.weinstein_score else None,
                dual_mom  = float(cs.dual_mom_score)  if cs.dual_mom_score  else None,
            ),
            regime_warning = cs.regime_warning or False,
            score_date     = cs.score_date,
        ))

    return FilterResponse(
        score_date  = score_date,
        total_found = total,
        pagination  = PaginationMeta(
            total    = total,
            limit    = body.limit,
            offset   = body.offset,
            has_more = body.offset + body.limit < total,
        ),
        items = items,
    )
