from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.v1 import (
    CoverageBucket,
    SearchResponse,
    SearchResultEntry,
    UniverseCoverageResponse,
)
from app.services.universe import build_coverage_map, search_instruments, summarize_universe_coverage

router = APIRouter()


@router.get("/search", response_model=SearchResponse, summary="Search covered instruments")
async def search_symbols(
    q: str = Query(..., min_length=1, max_length=100),
    market: str | None = Query(None, pattern="^(US|KR)$"),
    asset_type: str | None = Query(None, pattern="^(stock|etf)$"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
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
                exchange=instrument.exchange,
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
async def get_universe_coverage(db: AsyncSession = Depends(get_db)) -> UniverseCoverageResponse:
    summary = await summarize_universe_coverage(db)
    return UniverseCoverageResponse(
        as_of=summary["as_of"],
        items=[CoverageBucket(**item) for item in summary["items"]],
    )
