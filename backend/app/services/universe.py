from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consensus_score import ConsensusScore
from app.models.fundamental import FundamentalAnnual, FundamentalQuarterly
from app.models.instrument import Instrument
from app.models.price import Price

RANK_MODEL_VERSION = "consensus-v1-foundation"
DEFAULT_DELAY_MINUTES = {
    "US": 15,
    "KR": 0,
}


@dataclass(slots=True)
class InstrumentCoverage:
    instrument_id: int
    coverage_state: str
    ranking_eligibility: dict
    freshness: dict
    delay_minutes: Optional[int]
    rank_model_version: str
    price_bar_count: int


def _coverage_state(
    ranked_as_of: Optional[date],
    annual_as_of: Optional[date],
    quarterly_as_of: Optional[date],
    price_as_of: Optional[date],
) -> str:
    if ranked_as_of:
        return "ranked"
    if annual_as_of or quarterly_as_of:
        return "fundamentals_ready"
    if price_as_of:
        return "price_ready"
    return "searchable"


def _eligibility_reasons(
    instrument: Instrument,
    price_bar_count: int,
    price_as_of: Optional[date],
    annual_as_of: Optional[date],
    quarterly_as_of: Optional[date],
    ranked_as_of: Optional[date],
) -> list[str]:
    reasons: list[str] = []
    if not instrument.is_active or instrument.listing_status != "LISTED":
        reasons.append("inactive_listing")
    if instrument.is_test_issue:
        reasons.append("test_issue")
    if instrument.asset_type not in {"stock", "etf"}:
        reasons.append("unsupported_asset_type")
    if price_as_of is None:
        reasons.append("no_price_history")
    elif price_bar_count < 126:
        reasons.append("insufficient_price_history")
    if instrument.asset_type == "stock" and annual_as_of is None and quarterly_as_of is None:
        reasons.append("no_fundamentals")
    if ranked_as_of is None:
        reasons.append("score_not_generated")
    return reasons


async def build_coverage_map(
    db: AsyncSession,
    instruments: list[Instrument],
    *,
    score_date: Optional[date] = None,
) -> dict[int, InstrumentCoverage]:
    instrument_ids = [instrument.id for instrument in instruments]
    if not instrument_ids:
        return {}

    price_rows = (
        await db.execute(
            select(
                Price.instrument_id,
                func.count(Price.trade_date),
                func.max(Price.trade_date),
            )
            .where(Price.instrument_id.in_(instrument_ids))
            .group_by(Price.instrument_id)
        )
    ).all()
    annual_rows = (
        await db.execute(
            select(
                FundamentalAnnual.instrument_id,
                func.max(FundamentalAnnual.report_date),
            )
            .where(FundamentalAnnual.instrument_id.in_(instrument_ids))
            .group_by(FundamentalAnnual.instrument_id)
        )
    ).all()
    quarterly_rows = (
        await db.execute(
            select(
                FundamentalQuarterly.instrument_id,
                func.max(FundamentalQuarterly.report_date),
            )
            .where(FundamentalQuarterly.instrument_id.in_(instrument_ids))
            .group_by(FundamentalQuarterly.instrument_id)
        )
    ).all()

    consensus_stmt = (
        select(
            ConsensusScore.instrument_id,
            func.max(ConsensusScore.score_date),
        )
        .where(ConsensusScore.instrument_id.in_(instrument_ids))
        .group_by(ConsensusScore.instrument_id)
    )
    if score_date is not None:
        consensus_stmt = consensus_stmt.where(ConsensusScore.score_date <= score_date)

    consensus_rows = (await db.execute(consensus_stmt)).all()

    price_by_id = {
        instrument_id: {
            "price_bar_count": int(price_bar_count or 0),
            "price_as_of": price_as_of,
        }
        for instrument_id, price_bar_count, price_as_of in price_rows
    }
    annual_by_id = {instrument_id: annual_as_of for instrument_id, annual_as_of in annual_rows}
    quarterly_by_id = {
        instrument_id: quarterly_as_of for instrument_id, quarterly_as_of in quarterly_rows
    }
    consensus_by_id = {
        instrument_id: ranked_as_of for instrument_id, ranked_as_of in consensus_rows
    }

    coverage_map: dict[int, InstrumentCoverage] = {}
    for instrument in instruments:
        price = price_by_id.get(instrument.id, {})
        price_bar_count = int(price.get("price_bar_count", 0))
        price_as_of = price.get("price_as_of")
        annual_as_of = annual_by_id.get(instrument.id)
        quarterly_as_of = quarterly_by_id.get(instrument.id)
        ranked_as_of = consensus_by_id.get(instrument.id)

        reasons = _eligibility_reasons(
            instrument=instrument,
            price_bar_count=price_bar_count,
            price_as_of=price_as_of,
            annual_as_of=annual_as_of,
            quarterly_as_of=quarterly_as_of,
            ranked_as_of=ranked_as_of,
        )
        coverage_map[instrument.id] = InstrumentCoverage(
            instrument_id=instrument.id,
            coverage_state=_coverage_state(
                ranked_as_of=ranked_as_of,
                annual_as_of=annual_as_of,
                quarterly_as_of=quarterly_as_of,
                price_as_of=price_as_of,
            ),
            ranking_eligibility={
                "eligible": len(reasons) == 0,
                "reasons": reasons,
            },
            freshness={
                "price_as_of": price_as_of,
                "quarterly_as_of": quarterly_as_of,
                "annual_as_of": annual_as_of,
                "ranked_as_of": ranked_as_of,
            },
            delay_minutes=DEFAULT_DELAY_MINUTES.get(instrument.market),
            rank_model_version=RANK_MODEL_VERSION,
            price_bar_count=price_bar_count,
        )

    return coverage_map


async def search_instruments(
    db: AsyncSession,
    *,
    query: str,
    market: Optional[str] = None,
    asset_type: Optional[str] = None,
    limit: int = 20,
) -> list[Instrument]:
    cleaned = query.strip()
    if not cleaned:
        return []

    pattern = f"%{cleaned}%"
    prefix_pattern = f"{cleaned}%"
    upper_cleaned = cleaned.upper()

    stmt = select(Instrument).where(
        Instrument.is_active == True,
        or_(
            Instrument.ticker.ilike(pattern),
            Instrument.name.ilike(pattern),
            Instrument.name_kr.ilike(pattern),
            Instrument.exchange.ilike(pattern),
        )
    )
    if market:
        stmt = stmt.where(Instrument.market == market)
    if asset_type:
        stmt = stmt.where(Instrument.asset_type == asset_type)

    stmt = stmt.order_by(
        case((func.upper(Instrument.ticker) == upper_cleaned, 0), else_=1),
        case((Instrument.ticker.ilike(prefix_pattern), 0), else_=1),
        case((Instrument.name.ilike(prefix_pattern), 0), else_=1),
        Instrument.market.asc(),
        Instrument.asset_type.asc(),
        Instrument.ticker.asc(),
    ).limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def summarize_universe_coverage(db: AsyncSession) -> dict:
    result = await db.execute(
        select(Instrument).where(Instrument.is_active == True).order_by(Instrument.market, Instrument.ticker)
    )
    instruments = list(result.scalars().all())
    coverage_map = await build_coverage_map(db, instruments)

    buckets: dict[tuple[str, str], dict[str, int | str]] = {}
    for instrument in instruments:
        key = (instrument.market, instrument.asset_type)
        bucket = buckets.setdefault(
            key,
            {
                "market": instrument.market,
                "asset_type": instrument.asset_type,
                "searchable": 0,
                "price_ready": 0,
                "fundamentals_ready": 0,
                "ranked": 0,
            },
        )
        bucket["searchable"] += 1
        coverage = coverage_map[instrument.id]
        if coverage.coverage_state in {"price_ready", "fundamentals_ready", "ranked"}:
            bucket["price_ready"] += 1
        if coverage.coverage_state in {"fundamentals_ready", "ranked"}:
            bucket["fundamentals_ready"] += 1
        if coverage.coverage_state == "ranked":
            bucket["ranked"] += 1

    return {
        "as_of": datetime.now(timezone.utc),
        "items": list(buckets.values()),
    }
