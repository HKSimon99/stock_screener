from __future__ import annotations

import asyncio
import logging

from app.core.database import AsyncTaskSessionLocal
from app.models.hydration_job import HydrationJob
from app.services.hydration_jobs import (
    HYDRATION_JOB_COMPLETED,
    HYDRATION_JOB_FAILED,
    HYDRATION_JOB_RUNNING,
    set_hydration_job_status,
)
from app.tasks.celery_app import celery_app
from app.tasks.ingestion_tasks import (
    run_kr_price_ingestion,
    run_market_fundamentals_ingestion,
    run_us_price_ingestion,
)


logger = logging.getLogger(__name__)


async def run_hydration_job(*, job_id: int, celery_task_id: str | None = None) -> dict:
    async with AsyncTaskSessionLocal() as session:
        job = await session.get(HydrationJob, job_id)
        if job is None:
            raise ValueError(f"hydration job not found: {job_id}")

        await set_hydration_job_status(
            session,
            job_id=job_id,
            status=HYDRATION_JOB_RUNNING,
            celery_task_id=celery_task_id,
        )
        await session.commit()
        ticker = job.ticker
        market = job.market

    try:
        if market == "US":
            price_result = await run_us_price_ingestion(tickers=[ticker], days=365, sync_universe=False)
        elif market == "KR":
            price_result = await run_kr_price_ingestion(tickers=[ticker], days=365, sync_universe=False)
        else:
            raise ValueError(f"Unsupported market: {market}")

        fundamentals_result = await run_market_fundamentals_ingestion(
            market=market,
            tickers=[ticker],
            years=5,
        )

        result = {
            "job_id": job_id,
            "ticker": ticker,
            "market": market,
            "price_result": price_result,
            "fundamentals_result": fundamentals_result,
            "scoring_deferred": True,
            "next_step": "batch_scoring_required",
        }

        async with AsyncTaskSessionLocal() as session:
            await set_hydration_job_status(
                session,
                job_id=job_id,
                status=HYDRATION_JOB_COMPLETED,
                celery_task_id=celery_task_id,
                source_metadata={
                    "price_processed": price_result.get("processed_count", 0),
                    "fundamentals_processed": fundamentals_result.get("processed_count", 0),
                    "scoring_deferred": True,
                    "next_step": "batch_scoring_required",
                },
            )
            await session.commit()
        return result
    except Exception as exc:
        logger.exception("Hydration job %s failed", job_id)
        async with AsyncTaskSessionLocal() as session:
            await set_hydration_job_status(
                session,
                job_id=job_id,
                status=HYDRATION_JOB_FAILED,
                celery_task_id=celery_task_id,
                error_message=str(exc),
            )
            await session.commit()
        raise


@celery_app.task(name="app.tasks.hydration.run_instrument_hydration", bind=True)
def run_instrument_hydration_task(self, job_id: int) -> dict:
    task_id = getattr(self.request, "id", None)
    return asyncio.run(run_hydration_job(job_id=job_id, celery_task_id=task_id))
