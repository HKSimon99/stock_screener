from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.hydration_job import HydrationJob
from app.models.instrument import Instrument
from app.tasks import hydration_tasks
from tests.conftest import TEST_ASYNCPG_CONNECT_ARGS, TEST_ASYNC_DATABASE_URL


@pytest.fixture
async def hydration_task_test_session_factory(monkeypatch):
    test_engine = create_async_engine(
        TEST_ASYNC_DATABASE_URL,
        echo=False,
        connect_args=TEST_ASYNCPG_CONNECT_ARGS,
    )
    test_session_local = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    monkeypatch.setattr(hydration_tasks, "AsyncTaskSessionLocal", test_session_local)
    yield test_session_local
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_run_hydration_job_updates_completed_status_and_defers_scoring(
    db_session,
    monkeypatch,
    hydration_task_test_session_factory,
):
    instrument = Instrument(
        ticker="MSFT",
        name="Microsoft",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    job = HydrationJob(
        ticker="MSFT",
        market="US",
        instrument_id=instrument.id,
        status="queued",
        requester_source="user",
        source_metadata={"trigger": "explicit_hydration_api"},
    )
    db_session.add(job)
    await db_session.commit()

    async def fake_us_price_ingestion(*, tickers=None, days=365, sync_universe=False):
        assert tickers == ["MSFT"]
        assert days == 365
        assert sync_universe is False
        return {"processed_count": 1, "processed_tickers": ["MSFT"]}

    async def fake_fundamentals_ingestion(*, market=None, tickers=None, years=5, limit=None):
        assert market == "US"
        assert tickers == ["MSFT"]
        assert years == 5
        assert limit is None
        return {"processed_count": 1, "processed_tickers": ["MSFT"]}

    monkeypatch.setattr(hydration_tasks, "run_us_price_ingestion", fake_us_price_ingestion)
    monkeypatch.setattr(hydration_tasks, "run_market_fundamentals_ingestion", fake_fundamentals_ingestion)

    result = await hydration_tasks.run_hydration_job(job_id=job.id, celery_task_id="celery-123")
    assert result["job_id"] == job.id
    assert result["scoring_deferred"] is True
    assert result["next_step"] == "batch_scoring_required"

    async with hydration_task_test_session_factory() as verification_session:
        refreshed = await verification_session.get(HydrationJob, job.id)
    assert refreshed is not None
    assert refreshed.status == "completed"
    assert refreshed.started_at is not None
    assert refreshed.completed_at is not None
    assert refreshed.celery_task_id == "celery-123"
    assert refreshed.source_metadata["price_processed"] == 1
    assert refreshed.source_metadata["fundamentals_processed"] == 1
    assert refreshed.source_metadata["scoring_deferred"] is True


@pytest.mark.asyncio
async def test_run_hydration_job_marks_failure_when_provider_raises(
    db_session,
    monkeypatch,
    hydration_task_test_session_factory,
):
    instrument = Instrument(
        ticker="005930",
        name="Samsung Electronics",
        market="KR",
        exchange="KOSPI",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    job = HydrationJob(
        ticker="005930",
        market="KR",
        instrument_id=instrument.id,
        status="queued",
        requester_source="user",
        source_metadata={},
    )
    db_session.add(job)
    await db_session.commit()

    async def broken_kr_price_ingestion(*, tickers=None, days=365, sync_universe=False):
        _ = (tickers, days, sync_universe)
        raise RuntimeError("kr price failure")

    monkeypatch.setattr(hydration_tasks, "run_kr_price_ingestion", broken_kr_price_ingestion)

    with pytest.raises(RuntimeError, match="kr price failure"):
        await hydration_tasks.run_hydration_job(job_id=job.id, celery_task_id="celery-kr")

    async with hydration_task_test_session_factory() as verification_session:
        refreshed = await verification_session.get(HydrationJob, job.id)
    assert refreshed is not None
    assert refreshed.status == "failed"
    assert refreshed.started_at is not None
    assert refreshed.failed_at is not None
    assert refreshed.error_message == "kr price failure"
    assert refreshed.celery_task_id == "celery-kr"
