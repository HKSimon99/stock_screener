from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hydration_job import HydrationJob
from app.models.instrument import Instrument


HYDRATION_JOB_QUEUED = "queued"
HYDRATION_JOB_RUNNING = "running"
HYDRATION_JOB_COMPLETED = "completed"
HYDRATION_JOB_FAILED = "failed"
HYDRATION_JOB_CANCELLED = "cancelled"

ACTIVE_HYDRATION_JOB_STATUSES = (HYDRATION_JOB_QUEUED, HYDRATION_JOB_RUNNING)
TERMINAL_HYDRATION_JOB_STATUSES = (
    HYDRATION_JOB_COMPLETED,
    HYDRATION_JOB_FAILED,
    HYDRATION_JOB_CANCELLED,
)
VALID_HYDRATION_JOB_STATUSES = ACTIVE_HYDRATION_JOB_STATUSES + TERMINAL_HYDRATION_JOB_STATUSES
HYDRATION_QUEUE_TIMEOUT = timedelta(minutes=10)
HYDRATION_RUNNING_TIMEOUT = timedelta(minutes=70)


def normalize_hydration_symbol(ticker: str, market: str) -> tuple[str, str]:
    normalized_ticker = ticker.strip().upper()
    normalized_market = market.strip().upper()
    if not normalized_ticker:
        raise ValueError("ticker is required")
    if normalized_market not in {"US", "KR"}:
        raise ValueError("market must be US or KR")
    return normalized_ticker, normalized_market


async def get_active_hydration_job(
    session: AsyncSession,
    *,
    ticker: str,
    market: str,
) -> HydrationJob | None:
    normalized_ticker, normalized_market = normalize_hydration_symbol(ticker, market)
    return (
        await session.execute(
            select(HydrationJob)
            .where(
                HydrationJob.ticker == normalized_ticker,
                HydrationJob.market == normalized_market,
                HydrationJob.status.in_(ACTIVE_HYDRATION_JOB_STATUSES),
            )
            .order_by(HydrationJob.queued_at.desc(), HydrationJob.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def get_latest_hydration_job(
    session: AsyncSession,
    *,
    ticker: str,
    market: str,
) -> HydrationJob | None:
    normalized_ticker, normalized_market = normalize_hydration_symbol(ticker, market)
    return (
        await session.execute(
            select(HydrationJob)
            .where(HydrationJob.ticker == normalized_ticker, HydrationJob.market == normalized_market)
            .order_by(HydrationJob.queued_at.desc(), HydrationJob.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def resolve_hydration_instrument_id(
    session: AsyncSession,
    *,
    ticker: str,
    market: str,
) -> int | None:
    normalized_ticker, normalized_market = normalize_hydration_symbol(ticker, market)
    return (
        await session.execute(
            select(Instrument.id)
            .where(
                Instrument.market == normalized_market,
                Instrument.ticker == normalized_ticker,
            )
            .limit(1)
        )
    ).scalar_one_or_none()


async def create_hydration_job(
    session: AsyncSession,
    *,
    ticker: str,
    market: str,
    requester_source: str = "user",
    requester_user_id: str | None = None,
    instrument_id: int | None = None,
    celery_task_id: str | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> tuple[HydrationJob, bool]:
    """
    Create a durable refresh job, returning an active duplicate when one exists.

    The database partial unique index is the final concurrency guard for queued
    or running jobs. This helper keeps normal API paths idempotent before the
    Celery wiring lands in the next action plans.
    """
    normalized_ticker, normalized_market = normalize_hydration_symbol(ticker, market)
    existing = await get_active_hydration_job(
        session,
        ticker=normalized_ticker,
        market=normalized_market,
    )
    if existing is not None:
        return existing, False

    resolved_instrument_id = instrument_id
    if resolved_instrument_id is None:
        resolved_instrument_id = await resolve_hydration_instrument_id(
            session,
            ticker=normalized_ticker,
            market=normalized_market,
        )

    job = HydrationJob(
        ticker=normalized_ticker,
        market=normalized_market,
        instrument_id=resolved_instrument_id,
        status=HYDRATION_JOB_QUEUED,
        requester_source=requester_source,
        requester_user_id=requester_user_id,
        celery_task_id=celery_task_id,
        source_metadata=source_metadata or {},
    )
    session.add(job)
    await session.flush()
    return job, True


async def set_hydration_job_status(
    session: AsyncSession,
    *,
    job_id: int,
    status: str,
    celery_task_id: str | None = None,
    error_message: str | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> HydrationJob:
    normalized_status = status.strip().lower()
    if normalized_status not in VALID_HYDRATION_JOB_STATUSES:
        raise ValueError(f"unsupported hydration job status: {status}")

    job = await session.get(HydrationJob, job_id)
    if job is None:
        raise ValueError(f"hydration job not found: {job_id}")

    now = datetime.now(timezone.utc)
    job.status = normalized_status
    job.updated_at = now
    if celery_task_id is not None:
        job.celery_task_id = celery_task_id
    if source_metadata:
        merged_metadata = dict(job.source_metadata or {})
        merged_metadata.update(source_metadata)
        job.source_metadata = merged_metadata

    if normalized_status == HYDRATION_JOB_RUNNING:
        job.started_at = job.started_at or now
    elif normalized_status == HYDRATION_JOB_COMPLETED:
        job.completed_at = job.completed_at or now
        job.error_message = None
    elif normalized_status == HYDRATION_JOB_FAILED:
        job.failed_at = job.failed_at or now
        job.error_message = error_message
    elif normalized_status == HYDRATION_JOB_CANCELLED:
        job.failed_at = job.failed_at or now
        job.error_message = error_message or "cancelled"

    await session.flush()
    return job


async def reconcile_hydration_job_health(
    session: AsyncSession,
    *,
    job: HydrationJob,
    now: datetime | None = None,
) -> HydrationJob:
    if job.status not in ACTIVE_HYDRATION_JOB_STATUSES:
        return job

    current_time = now or datetime.now(timezone.utc)

    if job.status == HYDRATION_JOB_QUEUED and job.queued_at <= current_time - HYDRATION_QUEUE_TIMEOUT:
        return await set_hydration_job_status(
            session,
            job_id=job.id,
            status=HYDRATION_JOB_FAILED,
            error_message="Hydration worker did not start before the queue timeout elapsed.",
            source_metadata={"failure_reason": "queue_timeout"},
        )

    started_reference = job.started_at or job.updated_at or job.queued_at
    if job.status == HYDRATION_JOB_RUNNING and started_reference <= current_time - HYDRATION_RUNNING_TIMEOUT:
        return await set_hydration_job_status(
            session,
            job_id=job.id,
            status=HYDRATION_JOB_FAILED,
            error_message="Hydration worker exceeded the expected runtime window.",
            source_metadata={"failure_reason": "runtime_timeout"},
        )

    return job
