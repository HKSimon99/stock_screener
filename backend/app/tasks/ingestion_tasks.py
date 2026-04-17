from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.price import Price
from app.services.ingestion.kr_fundamental import run_kr_fundamentals_ingestion
from app.services.ingestion.freshness import (
    KR_FUNDAMENTALS_SOURCE,
    KR_INVESTOR_FLOWS_SOURCE,
    KR_PRICES_SOURCE,
    US_FUNDAMENTALS_SOURCE,
    US_INSTITUTIONAL_SOURCE,
    US_PRICES_SOURCE,
    record_data_freshness,
)
from app.services.ingestion.kr_price import (
    fetch_and_store_kr_prices,
    pykis,
    sync_kr_instruments,
)
from app.services.ingestion.us_fundamental import run_us_fundamentals_ingestion
from app.services.ingestion.us_institutional import ingest_us_institutional
from app.services.ingestion.kr_investor_flow import ingest_kr_investor_flows
from app.services.ingestion.us_price import fetch_and_store_prices, sync_instruments
from app.tasks.celery_app import celery_app


KR_PRICE_REQUEST_DELAY_SECONDS = 1.0
logger = logging.getLogger(__name__)


def _normalize_tickers(tickers: Optional[list[str]] = None) -> list[str]:
    if not tickers:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for ticker in tickers:
        cleaned = ticker.strip().upper()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


async def _get_active_tickers(market: str, limit: Optional[int] = None) -> list[str]:
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Instrument.ticker)
            .where(
                Instrument.market == market,
                Instrument.asset_type == "stock",
                Instrument.is_active.is_(True),
            )
            .order_by(Instrument.ticker.asc())
        )
        if limit:
            stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        return [row[0] for row in result.fetchall()]


async def _get_instrument_refs(
    session,
    market: str,
    tickers: Optional[list[str]] = None,
    limit: Optional[int] = None,
) -> list[tuple[int, str]]:
    stmt = (
        select(Instrument.id, Instrument.ticker)
        .where(
            Instrument.market == market,
            Instrument.asset_type == "stock",
            Instrument.is_active.is_(True),
        )
        .order_by(Instrument.ticker.asc())
    )

    normalized = _normalize_tickers(tickers)
    if normalized:
        stmt = stmt.where(Instrument.ticker.in_(normalized))
    elif limit:
        stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    rows = result.fetchall()
    refs = [(row[0], row[1]) for row in rows]

    if not normalized:
        return refs

    refs_by_ticker = {ticker: (instrument_id, ticker) for instrument_id, ticker in refs}
    return [refs_by_ticker[ticker] for ticker in normalized if ticker in refs_by_ticker]


async def _has_price_rows(session, instrument_id: int) -> bool:
    stmt = select(Price.instrument_id).where(Price.instrument_id == instrument_id).limit(1)
    result = await session.execute(stmt)
    return result.first() is not None


async def _record_source_freshness(
    source_name: str,
    market: str,
    requested_count: int,
    processed_count: int,
    failed_tickers: Optional[list[str]] = None,
    error: Optional[str] = None,
) -> None:
    failed_tickers = failed_tickers or []
    detail = error
    if detail is None and failed_tickers:
        sample = ", ".join(failed_tickers[:5])
        suffix = "..." if len(failed_tickers) > 5 else ""
        detail = (
            f"{len(failed_tickers)} of {requested_count} tickers failed"
            f"{': ' + sample + suffix if sample else ''}"
        )

    succeeded = processed_count > 0 or (requested_count == 0 and detail is None)

    try:
        async with AsyncSessionLocal() as session:
            await record_data_freshness(
                session,
                source_name=source_name,
                market=market,
                succeeded=succeeded,
                records_updated=processed_count,
                error=detail,
            )
            await session.commit()
    except Exception as exc:
        logger.warning(
            "Unable to persist data freshness for %s/%s: %s",
            source_name,
            market,
            exc,
        )


async def run_market_fundamentals_ingestion(
    market: str,
    tickers: Optional[list[str]] = None,
    years: int = 5,
    limit: Optional[int] = None,
) -> dict:
    market = market.upper()
    if market == "US":
        runner = run_us_fundamentals_ingestion
        source_name = US_FUNDAMENTALS_SOURCE
    elif market == "KR":
        runner = run_kr_fundamentals_ingestion
        source_name = KR_FUNDAMENTALS_SOURCE
    else:
        raise ValueError(f"Unsupported market: {market}")

    requested_count = 0
    selected_tickers = _normalize_tickers(tickers)
    processed_tickers: list[str] = []
    failed_tickers: list[str] = []

    try:
        if not selected_tickers:
            selected_tickers = await _get_active_tickers(market=market, limit=limit)
        requested_count = len(selected_tickers)

        for ticker in selected_tickers:
            try:
                await runner(ticker, years=years)
                processed_tickers.append(ticker)
            except Exception:
                failed_tickers.append(ticker)
    except Exception as exc:
        await _record_source_freshness(
            source_name=source_name,
            market=market,
            requested_count=requested_count,
            processed_count=len(processed_tickers),
            failed_tickers=failed_tickers or selected_tickers,
            error=str(exc),
        )
        raise

    await _record_source_freshness(
        source_name=source_name,
        market=market,
        requested_count=requested_count,
        processed_count=len(processed_tickers),
        failed_tickers=failed_tickers,
    )

    return {
        "market": market,
        "years": years,
        "requested_count": requested_count,
        "processed_count": len(processed_tickers),
        "failed_count": len(failed_tickers),
        "processed_tickers": processed_tickers,
        "failed_tickers": failed_tickers,
    }


async def run_us_price_ingestion(
    tickers: Optional[list[str]] = None,
    days: int = 730,
    limit: Optional[int] = None,
    sync_universe: bool = False,
) -> dict:
    normalized = _normalize_tickers(tickers)
    instrument_refs: list[tuple[int, str]] = []
    processed_tickers: list[str] = []
    failed_tickers: list[str] = []

    try:
        async with AsyncSessionLocal() as session:
            if sync_universe:
                await sync_instruments(session)

            instrument_refs = await _get_instrument_refs(
                session=session,
                market="US",
                tickers=normalized or None,
                limit=limit,
            )

            for instrument_id, ticker in instrument_refs:
                try:
                    await fetch_and_store_prices(
                        session=session,
                        instrument_id=instrument_id,
                        ticker=ticker,
                        days=days,
                    )
                    processed_tickers.append(ticker)
                except Exception:
                    failed_tickers.append(ticker)
    except Exception as exc:
        await _record_source_freshness(
            source_name=US_PRICES_SOURCE,
            market="US",
            requested_count=len(instrument_refs),
            processed_count=len(processed_tickers),
            failed_tickers=failed_tickers or normalized,
            error=str(exc),
        )
        raise

    await _record_source_freshness(
        source_name=US_PRICES_SOURCE,
        market="US",
        requested_count=len(instrument_refs),
        processed_count=len(processed_tickers),
        failed_tickers=failed_tickers,
    )

    return {
        "market": "US",
        "days": days,
        "requested_count": len(instrument_refs),
        "processed_count": len(processed_tickers),
        "failed_count": len(failed_tickers),
        "processed_tickers": processed_tickers,
        "failed_tickers": failed_tickers,
        "sync_universe": sync_universe,
    }


def _build_kis_client():
    if not pykis:
        raise RuntimeError("pykis is not installed.")

    appkey = os.environ.get("KIS_APP_KEY")
    secretkey = os.environ.get("KIS_APP_SECRET")
    hts_id = os.environ.get("KIS_HTS_ID", "")
    account = os.environ.get("KIS_ACCOUNT_NO", "")

    if not appkey or not secretkey or not hts_id or not account:
        raise RuntimeError(
            "Missing KIS env vars. Expected KIS_APP_KEY, KIS_APP_SECRET, "
            "KIS_HTS_ID, and KIS_ACCOUNT_NO."
        )

    return pykis.PyKis(
        id=hts_id,
        account=account,
        appkey=appkey,
        secretkey=secretkey,
    )


async def run_kr_price_ingestion(
    tickers: Optional[list[str]] = None,
    days: int = 730,
    limit: Optional[int] = None,
    sync_universe: bool = False,
) -> dict:
    normalized = _normalize_tickers(tickers)
    instrument_refs: list[tuple[int, str]] = []
    processed_tickers: list[str] = []
    failed_tickers: list[str] = []

    try:
        kis_client = _build_kis_client()

        async with AsyncSessionLocal() as session:
            if sync_universe:
                await sync_kr_instruments(session)

            instrument_refs = await _get_instrument_refs(
                session=session,
                market="KR",
                tickers=normalized or None,
                limit=limit,
            )

            for index, (instrument_id, ticker) in enumerate(instrument_refs):
                try:
                    await fetch_and_store_kr_prices(
                        session=session,
                        instrument_id=instrument_id,
                        ticker=ticker,
                        kis_client=kis_client,
                        days=days,
                    )
                    if await _has_price_rows(session, instrument_id):
                        processed_tickers.append(ticker)
                    else:
                        failed_tickers.append(ticker)
                except Exception:
                    failed_tickers.append(ticker)

                if index < len(instrument_refs) - 1:
                    await asyncio.sleep(KR_PRICE_REQUEST_DELAY_SECONDS)
    except Exception as exc:
        await _record_source_freshness(
            source_name=KR_PRICES_SOURCE,
            market="KR",
            requested_count=len(instrument_refs),
            processed_count=len(processed_tickers),
            failed_tickers=failed_tickers or normalized,
            error=str(exc),
        )
        raise

    await _record_source_freshness(
        source_name=KR_PRICES_SOURCE,
        market="KR",
        requested_count=len(instrument_refs),
        processed_count=len(processed_tickers),
        failed_tickers=failed_tickers,
    )

    return {
        "market": "KR",
        "days": days,
        "requested_count": len(instrument_refs),
        "processed_count": len(processed_tickers),
        "failed_count": len(failed_tickers),
        "processed_tickers": processed_tickers,
        "failed_tickers": failed_tickers,
        "sync_universe": sync_universe,
    }


@celery_app.task(name="app.tasks.ingestion.run_us_fundamentals")
def run_us_fundamentals_task(ticker: str, years: int = 5) -> dict:
    normalized = _normalize_tickers([ticker])
    if not normalized:
        raise ValueError("Ticker is required.")

    result = asyncio.run(
        run_market_fundamentals_ingestion(
            market="US",
            tickers=normalized,
            years=years,
        )
    )
    return {
        "market": "US",
        "ticker": normalized[0],
        "years": years,
        "processed": normalized[0] in result["processed_tickers"],
    }


@celery_app.task(name="app.tasks.ingestion.run_kr_fundamentals")
def run_kr_fundamentals_task(ticker: str, years: int = 5) -> dict:
    normalized = _normalize_tickers([ticker])
    if not normalized:
        raise ValueError("Ticker is required.")

    result = asyncio.run(
        run_market_fundamentals_ingestion(
            market="KR",
            tickers=normalized,
            years=years,
        )
    )
    return {
        "market": "KR",
        "ticker": normalized[0],
        "years": years,
        "processed": normalized[0] in result["processed_tickers"],
    }


@celery_app.task(name="app.tasks.ingestion.run_us_prices")
def run_us_price_task(
    ticker: str,
    days: int = 730,
    sync_universe: bool = False,
) -> dict:
    normalized = _normalize_tickers([ticker])
    if not normalized:
        raise ValueError("Ticker is required.")

    result = asyncio.run(
        run_us_price_ingestion(
            tickers=normalized,
            days=days,
            sync_universe=sync_universe,
        )
    )
    return {
        "market": "US",
        "ticker": normalized[0],
        "days": days,
        "processed": normalized[0] in result["processed_tickers"],
        "sync_universe": sync_universe,
    }


@celery_app.task(name="app.tasks.ingestion.run_kr_prices")
def run_kr_price_task(
    ticker: str,
    days: int = 730,
    sync_universe: bool = False,
) -> dict:
    normalized = _normalize_tickers([ticker])
    if not normalized:
        raise ValueError("Ticker is required.")

    result = asyncio.run(
        run_kr_price_ingestion(
            tickers=normalized,
            days=days,
            sync_universe=sync_universe,
        )
    )
    return {
        "market": "KR",
        "ticker": normalized[0],
        "days": days,
        "processed": normalized[0] in result["processed_tickers"],
        "sync_universe": sync_universe,
    }


@celery_app.task(name="app.tasks.ingestion.run_us_fundamentals_batch")
def run_us_fundamentals_batch_task(
    tickers: Optional[list[str]] = None,
    years: int = 5,
    limit: Optional[int] = None,
) -> dict:
    return asyncio.run(
        run_market_fundamentals_ingestion(
            market="US",
            tickers=tickers,
            years=years,
            limit=limit,
        )
    )


@celery_app.task(name="app.tasks.ingestion.run_kr_fundamentals_batch")
def run_kr_fundamentals_batch_task(
    tickers: Optional[list[str]] = None,
    years: int = 5,
    limit: Optional[int] = None,
) -> dict:
    return asyncio.run(
        run_market_fundamentals_ingestion(
            market="KR",
            tickers=tickers,
            years=years,
            limit=limit,
        )
    )


@celery_app.task(name="app.tasks.ingestion.run_us_prices_batch")
def run_us_price_batch_task(
    tickers: Optional[list[str]] = None,
    days: int = 730,
    limit: Optional[int] = None,
    sync_universe: bool = False,
) -> dict:
    return asyncio.run(
        run_us_price_ingestion(
            tickers=tickers,
            days=days,
            limit=limit,
            sync_universe=sync_universe,
        )
    )


@celery_app.task(name="app.tasks.ingestion.run_kr_prices_batch")
def run_kr_price_batch_task(
    tickers: Optional[list[str]] = None,
    days: int = 730,
    limit: Optional[int] = None,
    sync_universe: bool = False,
) -> dict:
    return asyncio.run(
        run_kr_price_ingestion(
            tickers=tickers,
            days=days,
            limit=limit,
            sync_universe=sync_universe,
        )
    )


@celery_app.task(name="app.tasks.ingestion.run_us_institutional")
def run_us_institutional_task(
    tickers: Optional[list[str]] = None,
    report_date: Optional[str] = None,
    max_filers: int = 200,
) -> dict:
    """
    Ingest US institutional ownership data from SEC 13F filings.
    report_date: ISO date string (YYYY-MM-DD) or None for today.
    """
    from datetime import date as _date
    parsed_date = _date.fromisoformat(report_date) if report_date else None
    result = asyncio.run(
        ingest_us_institutional(
            tickers=tickers,
            report_date=parsed_date,
            max_filers=max_filers,
        )
    )
    asyncio.run(
        _record_source_freshness(
            source_name=US_INSTITUTIONAL_SOURCE,
            market="US",
            requested_count=(result.get("processed", 0) + result.get("skipped", 0)),
            processed_count=result.get("processed", 0),
            error=result.get("error"),
        )
    )
    return result


@celery_app.task(name="app.tasks.ingestion.run_kr_investor_flows")
def run_kr_investor_flows_task(
    tickers: Optional[list[str]] = None,
    report_date: Optional[str] = None,
) -> dict:
    """
    Ingest KR investor category flows (foreign/institutional/individual) from KIS.
    report_date: ISO date string (YYYY-MM-DD) or None for today.
    """
    from datetime import date as _date
    parsed_date = _date.fromisoformat(report_date) if report_date else None
    result = asyncio.run(
        ingest_kr_investor_flows(
            tickers=tickers,
            report_date=parsed_date,
        )
    )
    asyncio.run(
        _record_source_freshness(
            source_name=KR_INVESTOR_FLOWS_SOURCE,
            market="KR",
            requested_count=(result.get("processed", 0) + result.get("skipped", 0)),
            processed_count=result.get("processed", 0),
            error=result.get("error"),
        )
    )
    return result
