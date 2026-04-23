from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from app.api.deps import get_db
from app.api.auth import ClerkAuthUser, get_clerk_user
from app.models.watchlist_item import WatchlistItem
from app.models.instrument import Instrument
from app.schemas.v1 import WatchlistItemResponse, WatchlistResponse

router = APIRouter()


def _to_response(item: WatchlistItem, instrument: Instrument) -> WatchlistItemResponse:
    return WatchlistItemResponse(
        id=item.id,
        instrument_id=item.instrument_id,
        market=item.market,
        ticker=item.ticker,
        name=instrument.name,
        name_kr=instrument.name_kr,
        added_at=item.added_at,
    )


@router.get("", response_model=WatchlistResponse)
async def get_watchlist(
    db: AsyncSession = Depends(get_db),
    current_user: ClerkAuthUser = Depends(get_clerk_user),
):
    result = await db.execute(
        select(WatchlistItem, Instrument)
        .join(Instrument, WatchlistItem.instrument_id == Instrument.id)
        .where(WatchlistItem.user_id == current_user.user_id)
        .order_by(WatchlistItem.added_at.desc())
    )
    rows = result.all()
    items = [_to_response(row.WatchlistItem, row.Instrument) for row in rows]
    return WatchlistResponse(items=items, total=len(items))


@router.post(
    "/{market}/{ticker}",
    response_model=WatchlistItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_watchlist(
    market: str,
    ticker: str,
    db: AsyncSession = Depends(get_db),
    current_user: ClerkAuthUser = Depends(get_clerk_user),
):
    market = market.upper()
    ticker = ticker.upper()

    result = await db.execute(
        select(Instrument).where(
            Instrument.ticker == ticker, Instrument.market == market
        )
    )
    instrument = result.scalars().first()
    if not instrument:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{ticker} not found in {market}",
        )

    existing_result = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == current_user.user_id,
            WatchlistItem.instrument_id == instrument.id,
        )
    )
    existing = existing_result.scalars().first()
    if existing:
        return _to_response(existing, instrument)

    new_item = WatchlistItem(
        user_id=current_user.user_id,
        instrument_id=instrument.id,
        market=market,
        ticker=ticker,
    )
    db.add(new_item)
    await db.commit()
    await db.refresh(new_item)
    return _to_response(new_item, instrument)


@router.delete("/{market}/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(
    market: str,
    ticker: str,
    db: AsyncSession = Depends(get_db),
    current_user: ClerkAuthUser = Depends(get_clerk_user),
):
    market = market.upper()
    ticker = ticker.upper()

    result = await db.execute(
        select(Instrument).where(
            Instrument.ticker == ticker, Instrument.market == market
        )
    )
    instrument = result.scalars().first()
    if not instrument:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{ticker} not found in {market}",
        )

    await db.execute(
        delete(WatchlistItem).where(
            WatchlistItem.user_id == current_user.user_id,
            WatchlistItem.instrument_id == instrument.id,
        )
    )
    await db.commit()
