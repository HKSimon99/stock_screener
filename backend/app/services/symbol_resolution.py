from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.services.ingestion.kr_price import fetch_kr_tickers
from app.services.ingestion.us_price import fetch_us_tickers
from app.services.request_cache import TtlCache

logger = logging.getLogger(__name__)

_SYMBOL_DIRECTORY_CACHE = TtlCache[dict[str, dict]](ttl_seconds=900)


@dataclass(slots=True)
class SymbolResolutionResult:
    instrument: Instrument
    resolved_from_provider: bool
    resolution_source: Optional[str] = None


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace("$", "").replace(".", "-")


async def _load_symbol_directory(market: str) -> dict[str, dict]:
    cached = _SYMBOL_DIRECTORY_CACHE.get(market)
    if cached is not None:
        return cached

    if market == "US":
        rows = await fetch_us_tickers()
    elif market == "KR":
        rows = await fetch_kr_tickers()
    else:
        raise ValueError(f"Unsupported market for symbol resolution: {market}")

    directory = {
        _normalize_symbol(str(row.get("ticker", ""))): row
        for row in rows
        if row.get("ticker")
    }
    return _SYMBOL_DIRECTORY_CACHE.set(market, directory)


async def resolve_symbol_payload(ticker: str, market: str) -> Optional[dict]:
    normalized_ticker = _normalize_symbol(ticker)
    directory = await _load_symbol_directory(market)
    payload = directory.get(normalized_ticker)
    if payload is None:
        return None
    return {
        **payload,
        "ticker": normalized_ticker,
    }


async def upsert_resolved_instrument(db: AsyncSession, payload: dict) -> Instrument:
    stmt = insert(Instrument).values(payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker", "market"],
        set_={
            "name": stmt.excluded.name,
            "name_kr": stmt.excluded.name_kr,
            "exchange": stmt.excluded.exchange,
            "asset_type": stmt.excluded.asset_type,
            "listing_status": stmt.excluded.listing_status,
            "sector": stmt.excluded.sector,
            "industry_group": stmt.excluded.industry_group,
            "is_active": stmt.excluded.is_active,
            "is_test_issue": stmt.excluded.is_test_issue,
            "source_provenance": stmt.excluded.source_provenance,
            "source_symbol": stmt.excluded.source_symbol,
            "is_chaebol_cross": stmt.excluded.is_chaebol_cross,
            "is_leveraged": stmt.excluded.is_leveraged,
            "is_inverse": stmt.excluded.is_inverse,
            "updated_at": text("CURRENT_TIMESTAMP"),
        },
    ).returning(Instrument.id)
    instrument_id = (await db.execute(stmt)).scalar_one()
    await db.flush()
    instrument = await db.get(Instrument, instrument_id)
    if instrument is None:
        raise RuntimeError(f"Failed to load upserted instrument id={instrument_id}")
    return instrument


async def resolve_instrument_for_explicit_request(
    db: AsyncSession,
    *,
    ticker: str,
    market: str,
) -> Optional[SymbolResolutionResult]:
    normalized_ticker = _normalize_symbol(ticker)
    existing = await db.scalar(
        select(Instrument).where(
            func.upper(Instrument.ticker) == normalized_ticker,
            Instrument.market == market,
            Instrument.is_active.is_(True),
        )
    )
    if existing is not None:
        return SymbolResolutionResult(
            instrument=existing,
            resolved_from_provider=False,
        )

    payload = await resolve_symbol_payload(normalized_ticker, market)
    if payload is None:
        return None

    instrument = await upsert_resolved_instrument(db, payload)
    return SymbolResolutionResult(
        instrument=instrument,
        resolved_from_provider=True,
        resolution_source=str(payload.get("source_provenance") or f"{market}_provider_directory"),
    )


async def resolve_instrument_for_hydration(
    db: AsyncSession,
    *,
    ticker: str,
    market: str,
) -> Optional[SymbolResolutionResult]:
    return await resolve_instrument_for_explicit_request(
        db,
        ticker=ticker,
        market=market,
    )
