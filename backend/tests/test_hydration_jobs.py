import pytest

from app.models.instrument import Instrument
from app.services.hydration_jobs import (
    HYDRATION_JOB_COMPLETED,
    HYDRATION_JOB_FAILED,
    HYDRATION_JOB_RUNNING,
    create_hydration_job,
    get_latest_hydration_job,
    set_hydration_job_status,
)


@pytest.mark.asyncio
async def test_create_hydration_job_resolves_instrument_and_dedupes_active_job(db_session):
    instrument = Instrument(
        ticker="TSSI",
        name="TSS",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    job, created = await create_hydration_job(
        db_session,
        ticker="tssi",
        market="us",
        requester_source="user",
        requester_user_id="user_test_123",
        source_metadata={"trigger": "detail_page"},
    )

    assert created is True
    assert job.id is not None
    assert job.ticker == "TSSI"
    assert job.market == "US"
    assert job.instrument_id == instrument.id
    assert job.status == "queued"
    assert job.requester_user_id == "user_test_123"
    assert job.source_metadata == {"trigger": "detail_page"}

    duplicate, duplicate_created = await create_hydration_job(
        db_session,
        ticker="TSSI",
        market="US",
        requester_source="user",
        requester_user_id="user_test_456",
    )

    assert duplicate_created is False
    assert duplicate.id == job.id


@pytest.mark.asyncio
async def test_terminal_hydration_job_allows_new_job_for_same_symbol(db_session):
    job, created = await create_hydration_job(
        db_session,
        ticker="031980",
        market="KR",
        requester_source="admin",
    )
    assert created is True

    completed = await set_hydration_job_status(
        db_session,
        job_id=job.id,
        status=HYDRATION_JOB_COMPLETED,
        source_metadata={"price_rows": 485},
    )
    assert completed.completed_at is not None
    assert completed.error_message is None
    assert completed.source_metadata == {"price_rows": 485}

    next_job, next_created = await create_hydration_job(
        db_session,
        ticker="031980",
        market="KR",
        requester_source="admin",
    )

    assert next_created is True
    assert next_job.id != job.id
    assert next_job.status == "queued"


@pytest.mark.asyncio
async def test_hydration_job_status_tracks_running_and_failed_timestamps(db_session):
    job, _ = await create_hydration_job(
        db_session,
        ticker="NVDA",
        market="US",
        requester_source="system",
        celery_task_id="task-initial",
    )

    running = await set_hydration_job_status(
        db_session,
        job_id=job.id,
        status=HYDRATION_JOB_RUNNING,
        celery_task_id="task-running",
    )
    assert running.started_at is not None
    assert running.celery_task_id == "task-running"

    failed = await set_hydration_job_status(
        db_session,
        job_id=job.id,
        status=HYDRATION_JOB_FAILED,
        error_message="provider timeout",
        source_metadata={"provider": "edgar"},
    )

    assert failed.failed_at is not None
    assert failed.error_message == "provider timeout"
    assert failed.source_metadata == {"provider": "edgar"}

    latest = await get_latest_hydration_job(db_session, ticker="NVDA", market="US")
    assert latest is not None
    assert latest.id == job.id
    assert latest.status == HYDRATION_JOB_FAILED
