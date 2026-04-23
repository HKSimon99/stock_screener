from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.backfill_run import AdminBackfillRun
from app.models.instrument import Instrument
from app.tasks import backfill_tasks
from tests.conftest import TEST_ASYNCPG_CONNECT_ARGS, TEST_ASYNC_DATABASE_URL


@pytest.fixture
async def backfill_task_test_session_factory(monkeypatch):
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
    monkeypatch.setattr(backfill_tasks, "AsyncTaskSessionLocal", test_session_local)
    yield test_session_local
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_run_admin_backfill_processes_chunks_and_scores_without_snapshots(
    db_session,
    monkeypatch,
    backfill_task_test_session_factory,
):
    instruments = [
        Instrument(
            ticker=ticker,
            name=ticker,
            market="US",
            exchange="NASDAQ",
            asset_type="stock",
            is_active=True,
        )
        for ticker in ["AAPL", "MSFT", "NVDA"]
    ]
    db_session.add_all(instruments)
    await db_session.flush()

    run = AdminBackfillRun(
        market="US",
        requested_tickers=["AAPL", "MSFT", "NVDA"],
        selected_tickers=["AAPL", "MSFT", "NVDA"],
        chunk_size=2,
        price_only=False,
        score_requested=True,
        status="queued",
        requester_source="api_key",
        requested_count=3,
        selected_count=3,
    )
    db_session.add(run)
    await db_session.commit()

    captured: dict[str, object] = {
        "price_chunks": [],
        "fundamentals_chunks": [],
    }

    async def fake_us_price_ingestion(*, tickers=None, days=365, limit=None, sync_universe=False):
        _ = (limit, sync_universe)
        captured["price_chunks"].append(list(tickers or []))
        return {"processed_tickers": list(tickers or [])}

    async def fake_fundamentals_ingestion(*, market=None, tickers=None, years=5, limit=None):
        _ = (market, years, limit)
        captured["fundamentals_chunks"].append(list(tickers or []))
        return {"processed_tickers": list(tickers or [])}

    async def fake_full_scoring_pipeline(*, market=None, instrument_ids=None, generate_snapshots=True, **kwargs):
        _ = kwargs
        captured["scoring_market"] = market
        captured["scoring_instrument_ids"] = sorted(instrument_ids or [])
        captured["generate_snapshots"] = generate_snapshots
        return {"consensus_scored": len(instrument_ids or [])}

    monkeypatch.setattr(backfill_tasks, "run_us_price_ingestion", fake_us_price_ingestion)
    monkeypatch.setattr(backfill_tasks, "run_market_fundamentals_ingestion", fake_fundamentals_ingestion)
    monkeypatch.setattr(backfill_tasks, "run_full_scoring_pipeline", fake_full_scoring_pipeline)

    result = await backfill_tasks.run_admin_backfill(run.id)

    assert result["run_id"] == run.id
    assert result["processed_count"] == 3
    assert result["failed_count"] == 0
    assert captured["price_chunks"] == [["AAPL", "MSFT"], ["NVDA"]]
    assert captured["fundamentals_chunks"] == [["AAPL", "MSFT"], ["NVDA"]]
    assert captured["scoring_market"] == "US"
    assert captured["scoring_instrument_ids"] == sorted([instrument.id for instrument in instruments])
    assert captured["generate_snapshots"] is False

    async with backfill_task_test_session_factory() as verification_session:
        refreshed = await verification_session.get(AdminBackfillRun, run.id)
    assert refreshed is not None
    assert refreshed.status == "completed"
    assert refreshed.processed_count == 3
    assert refreshed.failed_count == 0
    assert refreshed.result_metadata["scoring_result"]["consensus_scored"] == 3
