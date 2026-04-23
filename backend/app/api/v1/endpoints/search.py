from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_read_db
from app.schemas.v1 import (
    BrowseResponse,
    BrowseResultEntry,
    CoverageBucket,
    FreshnessSummary,
    PaginationMeta,
    RankingEligibility,
    SearchResponse,
    SearchResultEntry,
    UniverseCoverageResponse,
)
from app.services.taxonomy import normalize_exchange, normalize_sector
from app.services.universe import (
    browse_instruments,
    build_coverage_map,
    public_coverage_state_for,
    search_instruments,
    summarize_universe_coverage,
)

router = APIRouter()


@router.get("/search", response_model=SearchResponse, summary="Search covered instruments")
async def search_symbols(
    q: str = Query(..., min_length=1, max_length=100),
    market: str | None = Query(None, pattern="^(US|KR)$"),
    asset_type: str | None = Query(None, pattern="^(stock|etf)$"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_read_db),
) -> SearchResponse:
    instruments = await search_instruments(
        db,
        query=q,
        market=market,
        asset_type=asset_type,
        limit=limit,
    )
    coverage_map = await build_coverage_map(db, instruments)

    return SearchResponse(
        query=q,
        total=len(instruments),
        items=[
            SearchResultEntry(
                instrument_id=instrument.id,
                ticker=instrument.ticker,
                name=instrument.name,
                name_kr=instrument.name_kr,
                market=instrument.market,
                exchange=normalize_exchange(instrument.exchange) or "",
                asset_type=instrument.asset_type,
                listing_status=instrument.listing_status,
                coverage_state=coverage_map[instrument.id].coverage_state,
                ranking_eligibility=coverage_map[instrument.id].ranking_eligibility,
                rank_model_version=coverage_map[instrument.id].rank_model_version,
            )
            for instrument in instruments
        ],
    )


@router.get(
    "/universe/coverage",
    response_model=UniverseCoverageResponse,
    summary="Coverage summary for the searchable universe",
)
async def get_universe_coverage(db: AsyncSession = Depends(get_read_db)) -> UniverseCoverageResponse:
    summary = await summarize_universe_coverage(db)
    return UniverseCoverageResponse(
        as_of=summary["as_of"],
        items=[CoverageBucket(**item) for item in summary["items"]],
    )


@router.get(
    "/universe/browse",
    response_model=BrowseResponse,
    summary="Browse active instruments beyond the ranked list",
)
async def browse_universe(
    market: str | None = Query(None, pattern="^(US|KR)$"),
    asset_type: str | None = Query(None, pattern="^(stock|etf)$"),
    coverage_state: str | None = Query(None, max_length=30),
    exclude_ranked: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_read_db),
) -> BrowseResponse:
    rows, total = await browse_instruments(
        db,
        market=market,
        asset_type=asset_type,
        coverage_state=coverage_state,
        exclude_ranked=exclude_ranked,
        limit=limit,
        offset=offset,
    )

    items: list[BrowseResultEntry] = []
    for instrument, coverage, _total in rows:
        coverage_state_value, coverage_reasons = public_coverage_state_for(
            market=instrument.market,
            asset_type=instrument.asset_type,
            internal_coverage_state=coverage.coverage_state if coverage else None,
            price_as_of=coverage.price_as_of if coverage else None,
            quarterly_as_of=coverage.quarterly_as_of if coverage else None,
            annual_as_of=coverage.annual_as_of if coverage else None,
            ranked_as_of=coverage.ranked_as_of if coverage else None,
        )
        items.append(
            BrowseResultEntry(
                instrument_id=instrument.id,
                ticker=instrument.ticker,
                name=instrument.name,
                name_kr=instrument.name_kr,
                market=instrument.market,
                exchange=normalize_exchange(instrument.exchange) or "",
                asset_type=instrument.asset_type,
                listing_status=instrument.listing_status,
                sector=normalize_sector(instrument.sector),
                industry_group=instrument.industry_group,
                coverage_state=coverage_state_value,
                ranking_eligibility=RankingEligibility(
                    eligible=bool(coverage.ranking_eligible) if coverage else False,
                    reasons=list(
                        dict.fromkeys(
                            [
                                *(list(coverage.ranking_reasons or []) if coverage else ["coverage_not_summarized"]),
                                *coverage_reasons,
                            ]
                        )
                    ),
                ),
                freshness=FreshnessSummary(
                    price_as_of=coverage.price_as_of if coverage else None,
                    quarterly_as_of=coverage.quarterly_as_of if coverage else None,
                    annual_as_of=coverage.annual_as_of if coverage else None,
                    ranked_as_of=coverage.ranked_as_of if coverage else None,
                ),
                delay_minutes=coverage.delay_minutes if coverage else None,
                rank_model_version=coverage.rank_model_version if coverage else None,
            )
        )

    return BrowseResponse(
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + limit < total,
        ),
        items=items,
    )
