"""
GET /api/v1/rankings
GET /api/v1/rankings/{ticker}  (convenience redirect to instruments)

Returns the consensus-ranked list of instruments, optionally filtered by
market, conviction level, asset_type, and date.  Results are served from
the latest ``scoring_snapshots`` record when available (fast path), falling
back to a live ``consensus_scores`` query.

Query parameters
----------------
market          US | KR (default: all)
conviction      DIAMOND | GOLD | SILVER | BRONZE | UNRANKED (repeatable)
asset_type      stock | etf (default: stock)
score_date      ISO date (default: latest available)
limit           1-200 (default 50)
offset          int (default 0)
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, asc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.market_regime import MarketRegime
from app.models.snapshot import ScoringSnapshot
from app.schemas.v1 import (
    PaginationMeta, RankingEntry, RankingsResponse, StrategyScores,
)
from app.services.universe import RANK_MODEL_VERSION

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry_from_snapshot_row(row: dict, market: str, asset_type: str) -> RankingEntry:
    return RankingEntry(
        rank              = row.get("rank", 0),
        instrument_id     = row["instrument_id"],
        ticker            = row.get("ticker", ""),
        name              = row.get("name", ""),
        market            = market,
        exchange          = row.get("exchange"),
        asset_type        = row.get("asset_type", asset_type),
        conviction_level  = row.get("conviction_level", "UNRANKED"),
        final_score       = row.get("final_score", 0.0),
        consensus_composite = row.get("consensus_composite"),
        technical_composite = row.get("technical_composite"),
        strategy_pass_count = row.get("strategy_pass_count", 0),
        scores = StrategyScores(
            canslim   = row.get("scores", {}).get("canslim"),
            piotroski = row.get("scores", {}).get("piotroski"),
            minervini = row.get("scores", {}).get("minervini"),
            weinstein = row.get("scores", {}).get("weinstein"),
            dual_mom  = row.get("scores", {}).get("dual_mom"),
        ),
        regime_warning = row.get("regime_warning", False),
        score_date     = date.fromisoformat(str(row.get("score_date", date.today()))),
        coverage_state = row.get("coverage_state", "ranked"),
        rank_model_version = row.get("rank_model_version", RANK_MODEL_VERSION),
    )


def _entry_from_consensus(
    cs: ConsensusScore,
    ticker: str,
    name: str,
    market: str,
    exchange: str,
    asset_type: str,
    rank: int,
) -> RankingEntry:
    bd = cs.score_breakdown or {}
    strat = bd.get("strategy_scores", {})
    return RankingEntry(
        rank              = rank,
        instrument_id     = cs.instrument_id,
        ticker            = ticker,
        name              = name,
        market            = market,
        exchange          = exchange,
        asset_type        = asset_type,
        conviction_level  = cs.conviction_level,
        final_score       = float(cs.final_score)         if cs.final_score         else 0.0,
        consensus_composite = float(cs.consensus_composite) if cs.consensus_composite else None,
        technical_composite = float(cs.technical_composite) if cs.technical_composite else None,
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
        coverage_state = "ranked",
        rank_model_version = RANK_MODEL_VERSION,
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
    market:      Optional[str]  = Query(None, pattern="^(US|KR)$"),
    conviction:  list[str]      = Query(default=[]),
    asset_type:  str            = Query(default="stock", pattern="^(stock|etf)$"),
    score_date:  Optional[date] = Query(None),
    limit:       int            = Query(default=50, ge=1, le=200),
    offset:      int            = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> RankingsResponse:
    """
    Returns the consensus-ranked list.

    Tries the snapshot table first (fast), falls back to live consensus_scores.
    """
    # ── Resolve score_date ──────────────────────────────────────────────────
    if score_date is None:
        score_date = await _latest_consensus_date(market, db)
    if score_date is None:
        raise HTTPException(404, detail="No consensus scores found. Run the scoring pipeline first.")

    # ── Try snapshot fast path ──────────────────────────────────────────────
    snap_market = market or "US"
    snap_q = await db.execute(
        select(ScoringSnapshot).where(
            ScoringSnapshot.snapshot_date == score_date,
            ScoringSnapshot.market        == snap_market,
            ScoringSnapshot.asset_type    == asset_type,
        )
    )
    snapshot = snap_q.scalars().first()

    if snapshot:
        rows: list[dict] = snapshot.rankings_json or []
        # Filter by conviction
        if conviction:
            rows = [r for r in rows if r.get("conviction_level") in conviction]
        total = len(rows)
        page  = rows[offset: offset + limit]
        items = [_entry_from_snapshot_row(r, snap_market, asset_type) for r in page]
        regime = snapshot.regime_state
        regime_warning_count = sum(1 for r in rows if r.get("regime_warning"))
    else:
        # ── Live fallback ───────────────────────────────────────────────────
        stmt = (
            select(
                ConsensusScore,
                Instrument.ticker,
                Instrument.name,
                Instrument.market,
                Instrument.exchange,
                Instrument.asset_type,
            )
            .join(Instrument, ConsensusScore.instrument_id == Instrument.id)
            .where(
                ConsensusScore.score_date == score_date,
                Instrument.is_active == True,
                Instrument.asset_type == asset_type,
            )
        )
        if market:
            stmt = stmt.where(Instrument.market == market)
        if conviction:
            stmt = stmt.where(ConsensusScore.conviction_level.in_(conviction))

        # Count
        count_q = await db.execute(select(func.count()).select_from(stmt.subquery()))
        total = count_q.scalar_one()

        # Page
        stmt = stmt.order_by(desc(ConsensusScore.final_score)).limit(limit).offset(offset)
        result = await db.execute(stmt)
        rows_live = result.all()

        items = [
            _entry_from_consensus(cs, ticker, name, mkt, exchange, asset_type_value, offset + idx + 1)
            for idx, (cs, ticker, name, mkt, exchange, asset_type_value) in enumerate(rows_live)
        ]
        regime = await _get_regime(market or "US", score_date, db) if items else None
        regime_warning_count = sum(1 for it in items if it.regime_warning)

    return RankingsResponse(
        score_date            = score_date,
        market                = market or snap_market,
        regime_state          = regime,
        regime_warning_count  = regime_warning_count,
        pagination            = PaginationMeta(
            total    = total,
            limit    = limit,
            offset   = offset,
            has_more = offset + limit < total,
        ),
        items = items,
    )
