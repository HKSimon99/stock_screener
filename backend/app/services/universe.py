from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional
import zoneinfo

from sqlalchemy import and_, case, desc, func, literal, not_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consensus_score import ConsensusScore
from app.models.coverage_summary import InstrumentCoverageSummary
from app.models.fundamental import FundamentalAnnual, FundamentalQuarterly
from app.models.instrument import Instrument
from app.models.price import Price

RANK_MODEL_VERSION = "consensus-v1-foundation"
DEFAULT_DELAY_MINUTES = {
    "US": 15,
    "KR": 0,
}
UPSERT_BATCH_SIZE = 500
PRICE_STALE_TRADING_DAYS = 3
QUARTERLY_FUNDAMENTAL_STALE_DAYS = 200
ANNUAL_FUNDAMENTAL_STALE_DAYS = 500
PUBLIC_COVERAGE_STATES = {
    "ranked",
    "needs_price",
    "needs_fundamentals",
    "needs_scoring",
    "stale",
}
LEGACY_COVERAGE_TO_PUBLIC = {
    "searchable": "needs_price",
    "price_ready": "needs_fundamentals",
    "fundamentals_ready": "needs_scoring",
    "ranked": "ranked",
}


@dataclass(slots=True)
class InstrumentCoverage:
    instrument_id: int
    coverage_state: str
    internal_coverage_state: str
    ranking_eligibility: dict
    freshness: dict
    delay_minutes: Optional[int]
    rank_model_version: str
    price_bar_count: int


def _to_freshness(
    *,
    price_as_of: Optional[date],
    quarterly_as_of: Optional[date],
    annual_as_of: Optional[date],
    ranked_as_of: Optional[date],
) -> dict:
    return {
        "price_as_of": price_as_of,
        "quarterly_as_of": quarterly_as_of,
        "annual_as_of": annual_as_of,
        "ranked_as_of": ranked_as_of,
    }


def _to_instrument_coverage(
    *,
    instrument_id: int,
    coverage_state: str,
    ranking_eligible: bool,
    ranking_reasons: list[str],
    market: str,
    asset_type: str,
    price_as_of: Optional[date],
    quarterly_as_of: Optional[date],
    annual_as_of: Optional[date],
    ranked_as_of: Optional[date],
    delay_minutes: Optional[int],
    rank_model_version: str,
    price_bar_count: int,
) -> InstrumentCoverage:
    public_coverage_state, public_reasons = public_coverage_state_for(
        market=market,
        asset_type=asset_type,
        internal_coverage_state=coverage_state,
        price_as_of=price_as_of,
        quarterly_as_of=quarterly_as_of,
        annual_as_of=annual_as_of,
        ranked_as_of=ranked_as_of,
    )
    merged_reasons = list(dict.fromkeys([*ranking_reasons, *public_reasons]))
    return InstrumentCoverage(
        instrument_id=instrument_id,
        coverage_state=public_coverage_state,
        internal_coverage_state=coverage_state,
        ranking_eligibility={
            "eligible": ranking_eligible,
            "reasons": merged_reasons,
        },
        freshness=_to_freshness(
            price_as_of=price_as_of,
            quarterly_as_of=quarterly_as_of,
            annual_as_of=annual_as_of,
            ranked_as_of=ranked_as_of,
        ),
        delay_minutes=delay_minutes,
        rank_model_version=rank_model_version,
        price_bar_count=price_bar_count,
    )


def _market_today(market: str, now: Optional[datetime] = None) -> date:
    timezone_name = "Asia/Seoul" if market == "KR" else "America/New_York"
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    try:
        return current.astimezone(zoneinfo.ZoneInfo(timezone_name)).date()
    except zoneinfo.ZoneInfoNotFoundError:
        return current.date()


def _previous_trading_day(value: date) -> date:
    candidate = value - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _subtract_trading_days(value: date, days: int) -> date:
    candidate = value
    for _ in range(days):
        candidate = _previous_trading_day(candidate)
    return candidate


def latest_expected_price_date(market: str, now: Optional[datetime] = None) -> date:
    today = _market_today(market, now=now)
    while today.weekday() >= 5:
        today -= timedelta(days=1)
    return today


def _price_stale_cutoff(market: str, now: Optional[datetime] = None) -> date:
    return _subtract_trading_days(
        latest_expected_price_date(market, now=now),
        PRICE_STALE_TRADING_DAYS,
    )


def public_coverage_state_for(
    *,
    market: str,
    asset_type: str,
    internal_coverage_state: Optional[str],
    price_as_of: Optional[date],
    quarterly_as_of: Optional[date],
    annual_as_of: Optional[date],
    ranked_as_of: Optional[date],
    now: Optional[datetime] = None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if price_as_of is None:
        return "needs_price", ["no_price_history"]

    if asset_type == "stock" and annual_as_of is None and quarterly_as_of is None:
        return "needs_fundamentals", ["no_fundamentals"]

    price_cutoff = _price_stale_cutoff(market, now=now)
    price_is_stale = price_as_of < price_cutoff
    quarterly_is_stale = (
        quarterly_as_of is not None
        and quarterly_as_of < _market_today(market, now=now) - timedelta(days=QUARTERLY_FUNDAMENTAL_STALE_DAYS)
    )
    annual_is_stale = (
        annual_as_of is not None
        and annual_as_of < _market_today(market, now=now) - timedelta(days=ANNUAL_FUNDAMENTAL_STALE_DAYS)
    )
    if price_is_stale:
        reasons.append("stale_price_data")
    if quarterly_is_stale or annual_is_stale:
        reasons.append("stale_fundamentals")
    if reasons:
        return "stale", reasons

    if ranked_as_of is None:
        return "needs_scoring", ["score_not_generated"]

    if internal_coverage_state in PUBLIC_COVERAGE_STATES:
        return internal_coverage_state, []
    return LEGACY_COVERAGE_TO_PUBLIC.get(internal_coverage_state or "", "ranked"), []


def public_coverage_state_sql_expressions() -> dict[str, object]:
    us_price_cutoff = _price_stale_cutoff("US")
    kr_price_cutoff = _price_stale_cutoff("KR")
    today = datetime.now(timezone.utc).date()
    quarterly_cutoff = today - timedelta(days=QUARTERLY_FUNDAMENTAL_STALE_DAYS)
    annual_cutoff = today - timedelta(days=ANNUAL_FUNDAMENTAL_STALE_DAYS)

    price_missing_expr = InstrumentCoverageSummary.price_as_of.is_(None)
    fundamentals_missing_expr = and_(
        Instrument.asset_type == "stock",
        InstrumentCoverageSummary.price_as_of.is_not(None),
        InstrumentCoverageSummary.quarterly_as_of.is_(None),
        InstrumentCoverageSummary.annual_as_of.is_(None),
    )
    price_stale_expr = or_(
        and_(
            Instrument.market == "US",
            InstrumentCoverageSummary.price_as_of < us_price_cutoff,
        ),
        and_(
            Instrument.market == "KR",
            InstrumentCoverageSummary.price_as_of < kr_price_cutoff,
        ),
    )
    fundamentals_stale_expr = or_(
        and_(
            InstrumentCoverageSummary.quarterly_as_of.is_not(None),
            InstrumentCoverageSummary.quarterly_as_of < quarterly_cutoff,
        ),
        and_(
            InstrumentCoverageSummary.annual_as_of.is_not(None),
            InstrumentCoverageSummary.annual_as_of < annual_cutoff,
        ),
    )
    stale_expr = and_(
        not_(price_missing_expr),
        not_(fundamentals_missing_expr),
        or_(price_stale_expr, fundamentals_stale_expr),
    )
    needs_scoring_expr = and_(
        InstrumentCoverageSummary.ranked_as_of.is_(None),
        not_(price_missing_expr),
        not_(fundamentals_missing_expr),
        not_(stale_expr),
    )
    ranked_expr = and_(
        InstrumentCoverageSummary.ranked_as_of.is_not(None),
        not_(price_missing_expr),
        not_(fundamentals_missing_expr),
        not_(stale_expr),
    )
    return {
        "needs_price": price_missing_expr,
        "needs_fundamentals": fundamentals_missing_expr,
        "needs_scoring": needs_scoring_expr,
        "stale": stale_expr,
        "ranked": ranked_expr,
    }


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


async def _fetch_live_coverage_inputs(
    db: AsyncSession,
    instrument_ids: list[int],
    *,
    score_date: Optional[date] = None,
) -> tuple[dict[int, dict], dict[int, Optional[date]], dict[int, Optional[date]], dict[int, Optional[date]]]:
    if not instrument_ids:
        return {}, {}, {}, {}

    # Use window functions (PARTITION BY) + DISTINCT instead of GROUP BY.
    # PostgreSQL 16 on Neon + asyncpg raises "ORDER/GROUP BY expression not found in
    # targetlist" for ANY prepared statement containing GROUP BY over schema-qualified
    # tables. Window functions with PARTITION BY produce identical results and are not
    # affected by this bug.
    _part_price = Price.instrument_id
    price_rows = (
        await db.execute(
            select(
                Price.instrument_id.label("instrument_id"),
                func.count(Price.trade_date).over(partition_by=_part_price).label("price_count"),
                func.max(Price.trade_date).over(partition_by=_part_price).label("latest_trade_date"),
            )
            .where(Price.instrument_id.in_(instrument_ids))
            .distinct()
        )
    ).all()
    annual_rows = (
        await db.execute(
            select(
                FundamentalAnnual.instrument_id.label("instrument_id"),
                func.max(FundamentalAnnual.report_date).over(
                    partition_by=FundamentalAnnual.instrument_id
                ).label("latest_report_date"),
            )
            .where(FundamentalAnnual.instrument_id.in_(instrument_ids))
            .distinct()
        )
    ).all()
    quarterly_rows = (
        await db.execute(
            select(
                FundamentalQuarterly.instrument_id.label("instrument_id"),
                func.max(FundamentalQuarterly.report_date).over(
                    partition_by=FundamentalQuarterly.instrument_id
                ).label("latest_report_date"),
            )
            .where(FundamentalQuarterly.instrument_id.in_(instrument_ids))
            .distinct()
        )
    ).all()

    consensus_stmt = (
        select(
            ConsensusScore.instrument_id.label("instrument_id"),
            func.max(ConsensusScore.score_date).over(
                partition_by=ConsensusScore.instrument_id
            ).label("latest_score_date"),
        )
        .where(ConsensusScore.instrument_id.in_(instrument_ids))
        .distinct()
    )
    if score_date is not None:
        consensus_stmt = consensus_stmt.where(ConsensusScore.score_date <= score_date)

    consensus_rows = (await db.execute(consensus_stmt)).all()

    price_by_id: dict[int, dict] = {
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
    return price_by_id, annual_by_id, quarterly_by_id, consensus_by_id


def _build_live_coverage(
    *,
    instrument: Instrument,
    price_by_id: dict[int, dict],
    annual_by_id: dict[int, Optional[date]],
    quarterly_by_id: dict[int, Optional[date]],
    consensus_by_id: dict[int, Optional[date]],
) -> InstrumentCoverage:
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
    return _to_instrument_coverage(
        instrument_id=instrument.id,
        coverage_state=_coverage_state(
            ranked_as_of=ranked_as_of,
            annual_as_of=annual_as_of,
            quarterly_as_of=quarterly_as_of,
            price_as_of=price_as_of,
        ),
        ranking_eligible=len(reasons) == 0,
        ranking_reasons=reasons,
        market=instrument.market,
        asset_type=instrument.asset_type,
        price_as_of=price_as_of,
        quarterly_as_of=quarterly_as_of,
        annual_as_of=annual_as_of,
        ranked_as_of=ranked_as_of,
        delay_minutes=DEFAULT_DELAY_MINUTES.get(instrument.market),
        rank_model_version=RANK_MODEL_VERSION,
        price_bar_count=price_bar_count,
    )


async def refresh_instrument_coverage_summary(
    db: AsyncSession,
    *,
    instrument_ids: Optional[list[int]] = None,
    market: Optional[str] = None,
) -> int:
    stmt = select(Instrument).where(Instrument.is_active == True)
    if instrument_ids:
        stmt = stmt.where(Instrument.id.in_(instrument_ids))
    if market:
        stmt = stmt.where(Instrument.market == market)

    result = await db.execute(stmt.order_by(Instrument.id.asc()))
    instruments = list(result.scalars().all())
    if not instruments:
        return 0

    selected_ids = [instrument.id for instrument in instruments]
    price_by_id, annual_by_id, quarterly_by_id, consensus_by_id = await _fetch_live_coverage_inputs(
        db,
        selected_ids,
    )

    rows = []
    for instrument in instruments:
        coverage = _build_live_coverage(
            instrument=instrument,
            price_by_id=price_by_id,
            annual_by_id=annual_by_id,
            quarterly_by_id=quarterly_by_id,
            consensus_by_id=consensus_by_id,
        )
        rows.append(
            {
                "instrument_id": coverage.instrument_id,
                "coverage_state": coverage.internal_coverage_state,
                "price_bar_count": coverage.price_bar_count,
                "price_as_of": coverage.freshness["price_as_of"],
                "quarterly_as_of": coverage.freshness["quarterly_as_of"],
                "annual_as_of": coverage.freshness["annual_as_of"],
                "ranked_as_of": coverage.freshness["ranked_as_of"],
                "ranking_eligible": coverage.ranking_eligibility["eligible"],
                "ranking_reasons": coverage.ranking_eligibility["reasons"],
                "delay_minutes": coverage.delay_minutes,
                "rank_model_version": coverage.rank_model_version,
                "refreshed_at": datetime.now(timezone.utc),
            }
        )

    for start_idx in range(0, len(rows), UPSERT_BATCH_SIZE):
        chunk = rows[start_idx : start_idx + UPSERT_BATCH_SIZE]
        stmt = insert(InstrumentCoverageSummary).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=[InstrumentCoverageSummary.instrument_id],
            set_={
                "coverage_state": stmt.excluded.coverage_state,
                "price_bar_count": stmt.excluded.price_bar_count,
                "price_as_of": stmt.excluded.price_as_of,
                "quarterly_as_of": stmt.excluded.quarterly_as_of,
                "annual_as_of": stmt.excluded.annual_as_of,
                "ranked_as_of": stmt.excluded.ranked_as_of,
                "ranking_eligible": stmt.excluded.ranking_eligible,
                "ranking_reasons": stmt.excluded.ranking_reasons,
                "delay_minutes": stmt.excluded.delay_minutes,
                "rank_model_version": stmt.excluded.rank_model_version,
                "refreshed_at": stmt.excluded.refreshed_at,
            },
        )
        await db.execute(stmt)
    return len(rows)


async def refresh_coverage_summary_for_market_tickers(
    db: AsyncSession,
    *,
    market: str,
    tickers: list[str],
) -> int:
    normalized = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
    if not normalized:
        return 0
    result = await db.execute(
        select(Instrument.id)
        .where(
            Instrument.market == market,
            func.upper(Instrument.ticker).in_(normalized),
        )
        .order_by(Instrument.id.asc())
    )
    instrument_ids = [row[0] for row in result.all()]
    if not instrument_ids:
        return 0
    return await refresh_instrument_coverage_summary(db, instrument_ids=instrument_ids)


async def _load_summary_coverage_map(
    db: AsyncSession,
    instruments: list[Instrument],
) -> dict[int, InstrumentCoverage]:
    instrument_ids = [instrument.id for instrument in instruments]
    rows = (
        await db.execute(
            select(InstrumentCoverageSummary).where(
                InstrumentCoverageSummary.instrument_id.in_(instrument_ids)
            )
        )
    ).scalars().all()
    rows_by_id = {row.instrument_id: row for row in rows}

    coverage_map: dict[int, InstrumentCoverage] = {}
    for instrument in instruments:
        row = rows_by_id.get(instrument.id)
        if row is None:
            continue
        coverage_map[instrument.id] = _to_instrument_coverage(
            instrument_id=instrument.id,
            coverage_state=row.coverage_state,
            ranking_eligible=bool(row.ranking_eligible),
            ranking_reasons=list(row.ranking_reasons or []),
            market=instrument.market,
            asset_type=instrument.asset_type,
            price_as_of=row.price_as_of,
            quarterly_as_of=row.quarterly_as_of,
            annual_as_of=row.annual_as_of,
            ranked_as_of=row.ranked_as_of,
            delay_minutes=row.delay_minutes,
            rank_model_version=row.rank_model_version,
            price_bar_count=int(row.price_bar_count or 0),
        )
    return coverage_map


async def build_coverage_map(
    db: AsyncSession,
    instruments: list[Instrument],
    *,
    score_date: Optional[date] = None,
) -> dict[int, InstrumentCoverage]:
    instrument_ids = [instrument.id for instrument in instruments]
    if not instrument_ids:
        return {}

    if score_date is not None:
        price_by_id, annual_by_id, quarterly_by_id, consensus_by_id = await _fetch_live_coverage_inputs(
            db,
            instrument_ids,
            score_date=score_date,
        )
        return {
            instrument.id: _build_live_coverage(
                instrument=instrument,
                price_by_id=price_by_id,
                annual_by_id=annual_by_id,
                quarterly_by_id=quarterly_by_id,
                consensus_by_id=consensus_by_id,
            )
            for instrument in instruments
        }

    coverage_map = await _load_summary_coverage_map(db, instruments)
    missing_instruments = [instrument for instrument in instruments if instrument.id not in coverage_map]
    if not missing_instruments:
        return coverage_map

    price_by_id, annual_by_id, quarterly_by_id, consensus_by_id = await _fetch_live_coverage_inputs(
        db,
        [instrument.id for instrument in missing_instruments],
    )
    for instrument in missing_instruments:
        coverage_map[instrument.id] = _build_live_coverage(
            instrument=instrument,
            price_by_id=price_by_id,
            annual_by_id=annual_by_id,
            quarterly_by_id=quarterly_by_id,
            consensus_by_id=consensus_by_id,
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
    results: list[Instrument] = []
    seen_ids: set[int] = set()

    def _base_stmt():
        stmt = select(Instrument).where(Instrument.is_active == True)
        if market:
            stmt = stmt.where(Instrument.market == market)
        if asset_type:
            stmt = stmt.where(Instrument.asset_type == asset_type)
        if seen_ids:
            stmt = stmt.where(Instrument.id.not_in(seen_ids))
        return stmt

    # Tier 1: exact ticker match
    exact_stmt = (
        _base_stmt()
        .where(func.upper(Instrument.ticker) == upper_cleaned)
        .order_by(Instrument.market.asc(), Instrument.asset_type.asc(), Instrument.ticker.asc())
        .limit(limit)
    )
    exact_rows = list((await db.execute(exact_stmt)).scalars().all())
    results.extend(exact_rows)
    seen_ids.update(instrument.id for instrument in exact_rows)

    if len(results) >= limit:
        return results[:limit]

    # Tier 2: prefix matches
    prefix_conditions = [
        Instrument.ticker.ilike(prefix_pattern),
        Instrument.name.ilike(prefix_pattern),
        Instrument.name_kr.ilike(prefix_pattern),
    ]
    prefix_stmt = (
        _base_stmt()
        .where(or_(*prefix_conditions))
        .order_by(
            case((Instrument.ticker.ilike(prefix_pattern), 0), else_=1),
            case((Instrument.name.ilike(prefix_pattern), 0), else_=1),
            case((Instrument.name_kr.ilike(prefix_pattern), 0), else_=1),
            Instrument.market.asc(),
            Instrument.asset_type.asc(),
            Instrument.ticker.asc(),
        )
        .limit(limit - len(results))
    )
    prefix_rows = list((await db.execute(prefix_stmt)).scalars().all())
    results.extend(prefix_rows)
    seen_ids.update(instrument.id for instrument in prefix_rows)

    if len(results) >= limit or len(cleaned) < 2:
        return results[:limit]

    # Tier 3: broader contains fallback
    contains_stmt = (
        _base_stmt()
        .where(
            or_(
                Instrument.ticker.ilike(pattern),
                Instrument.name.ilike(pattern),
                Instrument.name_kr.ilike(pattern),
                Instrument.exchange.ilike(pattern),
            )
        )
        .order_by(
            Instrument.market.asc(),
            Instrument.asset_type.asc(),
            Instrument.ticker.asc(),
        )
        .limit(limit - len(results))
    )
    contains_rows = list((await db.execute(contains_stmt)).scalars().all())
    results.extend(contains_rows)
    return results[:limit]


async def browse_instruments(
    db: AsyncSession,
    *,
    market: Optional[str] = None,
    asset_type: Optional[str] = None,
    coverage_state: Optional[str] = None,
    exclude_ranked: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Instrument, Optional[InstrumentCoverageSummary], int]], int]:
    """
    Read-only universe browser used by the frontend's Explore More section.

    This intentionally reads only persisted instrument and coverage-summary rows.
    It does not refresh coverage, call providers, enqueue Celery, or create
    instruments, so a browse failure cannot mutate production state.
    """
    total_col = func.count().over().label("total_count")
    coverage_expressions = public_coverage_state_sql_expressions()
    price_missing_expr = coverage_expressions["needs_price"]
    fundamentals_missing_expr = coverage_expressions["needs_fundamentals"]
    stale_expr = coverage_expressions["stale"]
    needs_scoring_expr = coverage_expressions["needs_scoring"]
    ranked_expr = coverage_expressions["ranked"]
    coverage_order = case(
        (needs_scoring_expr, 0),
        (stale_expr, 1),
        (fundamentals_missing_expr, 2),
        (price_missing_expr, 3),
        else_=4,
    )

    stmt = (
        select(Instrument, InstrumentCoverageSummary, total_col)
        .select_from(Instrument)
        .outerjoin(
            InstrumentCoverageSummary,
            InstrumentCoverageSummary.instrument_id == Instrument.id,
        )
        .where(Instrument.is_active == True)
    )
    if market:
        stmt = stmt.where(Instrument.market == market)
    if asset_type:
        stmt = stmt.where(Instrument.asset_type == asset_type)
    if coverage_state:
        public_state = LEGACY_COVERAGE_TO_PUBLIC.get(coverage_state, coverage_state)
        if public_state == "ranked":
            stmt = stmt.where(ranked_expr)
        elif public_state == "needs_price":
            stmt = stmt.where(price_missing_expr)
        elif public_state == "needs_fundamentals":
            stmt = stmt.where(fundamentals_missing_expr)
        elif public_state == "needs_scoring":
            stmt = stmt.where(needs_scoring_expr)
        elif public_state == "stale":
            stmt = stmt.where(stale_expr)
        else:
            stmt = stmt.where(literal(False))
    if exclude_ranked:
        stmt = stmt.where(not_(ranked_expr))

    stmt = (
        stmt.order_by(
            coverage_order,
            desc(InstrumentCoverageSummary.price_bar_count),
            desc(InstrumentCoverageSummary.ranked_as_of),
            Instrument.market.asc(),
            Instrument.asset_type.asc(),
            Instrument.ticker.asc(),
        )
        .limit(limit)
        .offset(offset)
    )
    rows = list((await db.execute(stmt)).all())
    total = int(rows[0][2] or 0) if rows else 0
    return rows, total


async def summarize_universe_coverage(db: AsyncSession) -> dict:
    active_total = int(
        (
            await db.execute(
                select(func.count()).select_from(Instrument).where(Instrument.is_active == True)
            )
        ).scalar_one()
        or 0
    )
    summary_total = int(
        (
            await db.execute(
                select(func.count())
                .select_from(InstrumentCoverageSummary)
            )
        ).scalar_one()
        or 0
    )

    if active_total != summary_total:
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
            internal_state = coverage.internal_coverage_state
            if internal_state in {"price_ready", "fundamentals_ready", "ranked"}:
                bucket["price_ready"] += 1
            if internal_state in {"fundamentals_ready", "ranked"}:
                bucket["fundamentals_ready"] += 1
            if internal_state == "ranked":
                bucket["ranked"] += 1

        return {
            "as_of": datetime.now(timezone.utc),
            "items": list(buckets.values()),
        }

    result = await db.execute(
        select(
            Instrument.market,
            Instrument.asset_type,
            func.count().label("searchable"),
            func.count().filter(
                InstrumentCoverageSummary.coverage_state.in_(
                    ("price_ready", "fundamentals_ready", "ranked")
                )
            ).label("price_ready"),
            func.count().filter(
                InstrumentCoverageSummary.coverage_state.in_(("fundamentals_ready", "ranked"))
            ).label("fundamentals_ready"),
            func.count().filter(
                InstrumentCoverageSummary.coverage_state == "ranked"
            ).label("ranked"),
        )
        .select_from(Instrument)
        .outerjoin(
            InstrumentCoverageSummary,
            InstrumentCoverageSummary.instrument_id == Instrument.id,
        )
        .where(Instrument.is_active == True)
        .group_by(Instrument.market, Instrument.asset_type)
        .order_by(Instrument.market, Instrument.asset_type)
    )
    buckets = [
        {
            "market": market,
            "asset_type": asset_type,
            "searchable": int(searchable or 0),
            "price_ready": int(price_ready or 0),
            "fundamentals_ready": int(fundamentals_ready or 0),
            "ranked": int(ranked or 0),
        }
        for market, asset_type, searchable, price_ready, fundamentals_ready, ranked in result.all()
    ]

    return {
        "as_of": datetime.now(timezone.utc),
        "items": buckets,
    }
