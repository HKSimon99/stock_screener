from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.backfill_run import AdminBackfillRun
from app.models.instrument import Instrument
from app.services import symbol_resolution as symbol_resolution_module


@pytest.fixture(autouse=True)
def stub_backfill_dispatch(monkeypatch):
    class DummyTaskResult:
        id = "celery-backfill-123"

    def fake_delay(*, run_id):
        _ = run_id
        return DummyTaskResult()

    monkeypatch.setattr(
        "app.tasks.backfill_tasks.run_admin_backfill_task.delay",
        fake_delay,
    )


@pytest.mark.asyncio
async def test_admin_backfill_dry_run_previews_scope_without_writing(client, db_session, monkeypatch):
    instrument = Instrument(
        ticker="AAPL",
        name="Apple",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.commit()

    symbol_resolution_module._SYMBOL_DIRECTORY_CACHE._entries.clear()

    async def fake_fetch_us_tickers():
        return [
            {
                "ticker": "TSSI",
                "name": "TSS, Inc. Common Stock",
                "market": "US",
                "exchange": "NASDAQ",
                "asset_type": "stock",
                "listing_status": "LISTED",
                "sector": None,
                "industry_group": None,
                "is_active": True,
                "is_test_issue": False,
                "source_provenance": "NASDAQ_TRADER:nasdaqlisted",
                "source_symbol": "TSSI",
                "is_chaebol_cross": False,
                "is_leveraged": False,
                "is_inverse": False,
            }
        ]

    monkeypatch.setattr(symbol_resolution_module, "fetch_us_tickers", fake_fetch_us_tickers)

    before_instrument_count = await db_session.scalar(select(func.count(Instrument.id)))

    response = await client.post(
        "/api/v1/admin/backfill",
        json={
            "market": "US",
            "tickers": ["AAPL", "TSSI", "ZZZZ"],
            "dry_run": True,
            "score": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is True
    assert payload["run"] is None
    assert payload["preview"]["requested_count"] == 3
    assert payload["preview"]["selected_count"] == 2
    assert payload["preview"]["existing_count"] == 1
    assert payload["preview"]["resolved_from_provider_count"] == 1
    assert payload["preview"]["unresolved_count"] == 1
    assert payload["preview"]["sample_selected_tickers"] == ["AAPL", "TSSI"]
    assert payload["preview"]["sample_unresolved_tickers"] == ["ZZZZ"]

    after_instrument_count = await db_session.scalar(select(func.count(Instrument.id)))
    assert after_instrument_count == before_instrument_count
    assert await db_session.scalar(select(func.count(AdminBackfillRun.id))) == 0
    assert await db_session.scalar(
        select(Instrument).where(Instrument.ticker == "TSSI", Instrument.market == "US")
    ) is None


@pytest.mark.asyncio
async def test_admin_backfill_queue_creates_durable_run_and_dispatches_task(client, db_session):
    instrument = Instrument(
        ticker="MSFT",
        name="Microsoft",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.commit()

    response = await client.post(
        "/api/v1/admin/backfill",
        json={
            "market": "US",
            "tickers": ["MSFT"],
            "dry_run": False,
            "score": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is False
    assert payload["preview"]["selected_count"] == 1
    assert payload["run"]["status"] == "queued"
    assert payload["run"]["market"] == "US"
    assert payload["run"]["selected_tickers"] == ["MSFT"]
    assert payload["run"]["score_requested"] is True
    assert payload["run"]["result_metadata"]["dispatch_channel"] == "celery"

    run = await db_session.get(AdminBackfillRun, payload["run"]["id"])
    assert run is not None
    assert run.status == "queued"
    assert run.selected_count == 1
    assert run.celery_task_id == "celery-backfill-123"

    status_response = await client.get(f"/api/v1/admin/backfill/{run.id}")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["id"] == run.id
    assert status_payload["status"] == "queued"


@pytest.mark.asyncio
async def test_admin_backfill_rejects_price_only_with_scoring(client):
    response = await client.post(
        "/api/v1/admin/backfill",
        json={
            "market": "US",
            "dry_run": False,
            "price_only": True,
            "score": True,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "price_only=true cannot be combined with score=true"
