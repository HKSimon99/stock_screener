from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy import select

from app.core.database import AsyncTaskSessionLocal
from app.models.instrument import Instrument
from app.tasks.celery_app import celery_app
from app.tasks.ingestion_tasks import run_kr_price_ingestion, run_market_fundamentals_ingestion, run_us_price_ingestion
from app.tasks.scoring_tasks import run_full_scoring_pipeline
from app.services.backfill_runs import (
    DEFAULT_BACKFILL_FUNDAMENTAL_YEARS,
    DEFAULT_BACKFILL_PRICE_DAYS,
    get_admin_backfill_run,
    set_admin_backfill_run_status,
)

logger = logging.getLogger(__name__)


def _chunked(values: list[str], chunk_size: int) -> list[list[str]]:
    return [values[idx: idx + chunk_size] for idx in range(0, len(values), chunk_size)]


async def _resolve_instrument_ids(market: str, tickers: list[str]) -> list[int]:
    if not tickers:
        return []

    async with AsyncTaskSessionLocal() as db:
        rows = await db.execute(
            select(Instrument.id)
            .where(
                Instrument.market == market,
                Instrument.ticker.in_(tickers),
            )
            .order_by(Instrument.ticker.asc())
        )
        return [row[0] for row in rows.all()]


def _ticker_successes(
    chunk_tickers: list[str],
    *,
    price_result: dict,
    fundamentals_result: Optional[dict],
    price_only: bool,
) -> tuple[list[str], list[str]]:
    price_success = set(price_result.get("processed_tickers", []))
    fundamentals_success = (
        set(fundamentals_result.get("processed_tickers", []))
        if fundamentals_result is not None
        else set(chunk_tickers)
    )
    succeeded: list[str] = []
    failed: list[str] = []
    for ticker in chunk_tickers:
        if ticker in price_success and (price_only or ticker in fundamentals_success):
            succeeded.append(ticker)
        else:
            failed.append(ticker)
    return succeeded, failed


async def run_admin_backfill(run_id: int) -> dict:
    async with AsyncTaskSessionLocal() as db:
        run = await get_admin_backfill_run(db, run_id)
        if run is None:
            raise ValueError(f"AdminBackfillRun {run_id} does not exist")

        selected_tickers = [str(ticker) for ticker in (run.selected_tickers or [])]
        chunk_size = int(run.chunk_size or 25)
        await set_admin_backfill_run_status(
            db,
            run_id=run.id,
            status="running",
            result_metadata={
                "chunk_size": chunk_size,
                "chunk_count": len(_chunked(selected_tickers, chunk_size)) if selected_tickers else 0,
                "price_days": DEFAULT_BACKFILL_PRICE_DAYS,
                "fundamental_years": DEFAULT_BACKFILL_FUNDAMENTAL_YEARS,
                "score_runs_without_snapshots": bool(run.score_requested),
            },
        )
        await db.commit()

    if not selected_tickers:
        async with AsyncTaskSessionLocal() as db:
            await set_admin_backfill_run_status(
                db,
                run_id=run_id,
                status="completed",
                result_metadata={"message": "No instruments were selected for this backfill run."},
            )
            await db.commit()
        return {
            "run_id": run_id,
            "market": run.market,
            "selected_count": 0,
            "processed_count": 0,
            "failed_count": 0,
            "score_requested": bool(run.score_requested),
        }

    succeeded_tickers: list[str] = []
    failed_tickers: list[str] = []
    chunk_total = len(_chunked(selected_tickers, chunk_size))

    try:
        for chunk_index, chunk_tickers in enumerate(_chunked(selected_tickers, chunk_size), start=1):
            logger.info(
                "Admin backfill run %s chunk %s/%s market=%s tickers=%s",
                run_id,
                chunk_index,
                chunk_total,
                run.market,
                chunk_tickers,
            )

            if run.market == "US":
                price_task = run_us_price_ingestion(tickers=chunk_tickers, days=DEFAULT_BACKFILL_PRICE_DAYS)
            else:
                price_task = run_kr_price_ingestion(tickers=chunk_tickers, days=DEFAULT_BACKFILL_PRICE_DAYS)

            fundamentals_result: Optional[dict]
            if run.price_only:
                price_result = await price_task
                fundamentals_result = None
            else:
                price_result, fundamentals_result = await asyncio.gather(
                    price_task,
                    run_market_fundamentals_ingestion(
                        market=run.market,
                        tickers=chunk_tickers,
                        years=DEFAULT_BACKFILL_FUNDAMENTAL_YEARS,
                    ),
                )

            chunk_succeeded, chunk_failed = _ticker_successes(
                chunk_tickers,
                price_result=price_result,
                fundamentals_result=fundamentals_result,
                price_only=bool(run.price_only),
            )
            succeeded_tickers.extend(chunk_succeeded)
            failed_tickers.extend(chunk_failed)

            async with AsyncTaskSessionLocal() as db:
                await set_admin_backfill_run_status(
                    db,
                    run_id=run_id,
                    status="running",
                    processed_count=len(succeeded_tickers),
                    failed_count=len(failed_tickers),
                    result_metadata={
                        "current_chunk": chunk_index,
                        "chunk_count": chunk_total,
                        "sample_succeeded_tickers": succeeded_tickers[:20],
                        "sample_failed_tickers": failed_tickers[:20],
                    },
                )
                await db.commit()

        scoring_result: Optional[dict] = None
        if run.score_requested and succeeded_tickers:
            instrument_ids = await _resolve_instrument_ids(run.market, succeeded_tickers)
            if instrument_ids:
                scoring_result = await run_full_scoring_pipeline(
                    market=run.market,
                    instrument_ids=instrument_ids,
                    generate_snapshots=False,
                )

        async with AsyncTaskSessionLocal() as db:
            await set_admin_backfill_run_status(
                db,
                run_id=run_id,
                status="completed",
                processed_count=len(succeeded_tickers),
                failed_count=len(failed_tickers),
                result_metadata={
                    "sample_succeeded_tickers": succeeded_tickers[:20],
                    "sample_failed_tickers": failed_tickers[:20],
                    "scoring_result": scoring_result,
                },
            )
            await db.commit()

        return {
            "run_id": run_id,
            "market": run.market,
            "selected_count": len(selected_tickers),
            "processed_count": len(succeeded_tickers),
            "failed_count": len(failed_tickers),
            "score_requested": bool(run.score_requested),
            "scoring_result": scoring_result,
        }
    except Exception as exc:
        logger.exception("Admin backfill run %s failed: %s", run_id, exc)
        async with AsyncTaskSessionLocal() as db:
            await set_admin_backfill_run_status(
                db,
                run_id=run_id,
                status="failed",
                processed_count=len(succeeded_tickers),
                failed_count=len(failed_tickers),
                error_message=str(exc),
                result_metadata={
                    "sample_succeeded_tickers": succeeded_tickers[:20],
                    "sample_failed_tickers": failed_tickers[:20],
                },
            )
            await db.commit()
        raise


@celery_app.task(name="app.tasks.backfill.run_admin_backfill")
def run_admin_backfill_task(run_id: int) -> dict:
    return asyncio.run(run_admin_backfill(run_id))
