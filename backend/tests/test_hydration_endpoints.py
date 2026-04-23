from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.api import auth as auth_module
from app.api.v1.endpoints import instruments as instruments_endpoint
from app.models.hydration_job import HydrationJob
from app.models.instrument import Instrument
from app.services import symbol_resolution as symbol_resolution_module


@pytest.fixture(autouse=True)
def stub_hydration_dispatch(monkeypatch):
    class DummyTaskResult:
        id = "celery-task-123"

    def fake_delay(*, job_id):
        _ = job_id
        return DummyTaskResult()

    monkeypatch.setattr(
        "app.tasks.hydration_tasks.run_instrument_hydration_task.delay",
        fake_delay,
    )


@pytest.mark.asyncio
async def test_hydrate_endpoint_creates_job_and_dedupes(client, db_session):
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

    response = await client.post("/api/v1/instruments/MSFT/hydrate?market=US")
    assert response.status_code == 202
    payload = response.json()
    assert payload["created"] is True
    assert payload["job"]["ticker"] == "MSFT"
    assert payload["job"]["market"] == "US"
    assert payload["job"]["instrument_id"] == instrument.id
    assert payload["job"]["status"] == "queued"
    assert payload["job"]["requester_source"] == "user"
    assert payload["job"]["source_metadata"]["dispatch_channel"] == "celery"

    duplicate = await client.post("/api/v1/instruments/MSFT/hydrate?market=US")
    assert duplicate.status_code == 202
    duplicate_payload = duplicate.json()
    assert duplicate_payload["created"] is False
    assert duplicate_payload["job"]["id"] == payload["job"]["id"]

    total_jobs = await db_session.scalar(select(func.count(HydrationJob.id)))
    assert total_jobs == 1


@pytest.mark.asyncio
async def test_hydrate_status_endpoint_returns_latest_job(client, db_session):
    instrument = Instrument(
        ticker="NVDA",
        name="Nvidia",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    queued = await client.post("/api/v1/instruments/NVDA/hydrate?market=US")
    assert queued.status_code == 202

    response = await client.get("/api/v1/instruments/NVDA/hydrate-status?market=US")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "NVDA"
    assert payload["status"] == "queued"


@pytest.mark.asyncio
async def test_hydrate_status_endpoint_returns_404_when_missing(client, db_session):
    instrument = Instrument(
        ticker="AAPL",
        name="Apple",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    response = await client.get("/api/v1/instruments/AAPL/hydrate-status?market=US")
    assert response.status_code == 404
    assert "No hydration job found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_hydrate_endpoint_requires_auth(unauth_client, db_session):
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

    response = await unauth_client.post("/api/v1/instruments/005930/hydrate?market=KR")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token or X-API-Key header"


@pytest.mark.asyncio
async def test_hydrate_endpoint_accepts_api_key(unauth_client, db_session, monkeypatch):
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

    monkeypatch.setattr(auth_module.settings, "api_keys", "test-key")
    auth_module._RATE_LIMIT_STORE.clear()

    response = await unauth_client.post(
        "/api/v1/instruments/TSSI/hydrate?market=US",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["created"] is True
    assert payload["job"]["requester_source"] == "api_key"


@pytest.mark.asyncio
async def test_hydrate_endpoint_resolves_unknown_us_symbol_from_provider_directory(
    client,
    db_session,
    monkeypatch,
):
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

    response = await client.post("/api/v1/instruments/TSSI/hydrate?market=US")

    assert response.status_code == 202
    payload = response.json()
    assert payload["created"] is True
    assert payload["job"]["ticker"] == "TSSI"
    assert payload["job"]["market"] == "US"
    assert payload["job"]["source_metadata"]["resolved_from_provider"] is True
    assert payload["job"]["source_metadata"]["resolution_source"] == "NASDAQ_TRADER:nasdaqlisted"
    assert "Resolved TSSI" in payload["message"]

    instrument = await db_session.scalar(
        select(Instrument).where(Instrument.ticker == "TSSI", Instrument.market == "US")
    )
    assert instrument is not None
    assert instrument.exchange == "NASDAQ"
    assert instrument.source_provenance == "NASDAQ_TRADER:nasdaqlisted"


@pytest.mark.asyncio
async def test_hydrate_endpoint_returns_clear_404_when_symbol_cannot_be_resolved(
    client,
    db_session,
    monkeypatch,
):
    _ = db_session
    symbol_resolution_module._SYMBOL_DIRECTORY_CACHE._entries.clear()

    async def fake_fetch_us_tickers():
        return []

    monkeypatch.setattr(symbol_resolution_module, "fetch_us_tickers", fake_fetch_us_tickers)

    response = await client.post("/api/v1/instruments/ZZZZ/hydrate?market=US")

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "Instrument 'ZZZZ' is not in the database and could not be resolved from the US provider symbol directory."
    )

    instrument = await db_session.scalar(
        select(Instrument).where(Instrument.ticker == "ZZZZ", Instrument.market == "US")
    )
    assert instrument is None


@pytest.mark.asyncio
async def test_hydrate_endpoint_rate_limits_actor_requests(client, db_session, monkeypatch):
    first = Instrument(
        ticker="ORCL",
        name="Oracle",
        market="US",
        exchange="NYSE",
        asset_type="stock",
        is_active=True,
    )
    second = Instrument(
        ticker="IBM",
        name="IBM",
        market="US",
        exchange="NYSE",
        asset_type="stock",
        is_active=True,
    )
    db_session.add_all([first, second])
    await db_session.flush()

    monkeypatch.setattr(auth_module, "HYDRATION_RATE_LIMIT_REQUESTS", 1)
    monkeypatch.setattr(auth_module, "HYDRATION_RATE_LIMIT_WINDOW_SEC", 3600)
    monkeypatch.setattr(instruments_endpoint, "HYDRATION_RATE_LIMIT_REQUESTS", 1)
    monkeypatch.setattr(instruments_endpoint, "HYDRATION_RATE_LIMIT_WINDOW_SEC", 3600)
    auth_module._RATE_LIMIT_STORE.clear()

    first_response = await client.post("/api/v1/instruments/ORCL/hydrate?market=US")
    assert first_response.status_code == 202

    second_response = await client.post("/api/v1/instruments/IBM/hydrate?market=US")
    assert second_response.status_code == 429
    assert second_response.json()["detail"] == "Rate limit exceeded"


@pytest.mark.asyncio
async def test_hydrate_endpoint_marks_job_failed_when_dispatch_fails(client, db_session, monkeypatch):
    instrument = Instrument(
        ticker="AMD",
        name="AMD",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    def broken_delay(*, job_id):
        _ = job_id
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(
        "app.tasks.hydration_tasks.run_instrument_hydration_task.delay",
        broken_delay,
    )

    response = await client.post("/api/v1/instruments/AMD/hydrate?market=US")
    assert response.status_code == 503
    assert "Failed to queue hydration task" in response.json()["detail"]

    job = await db_session.scalar(select(HydrationJob).where(HydrationJob.ticker == "AMD"))
    assert job is not None
    assert job.status == "failed"
    assert job.error_message is not None
    assert "broker unavailable" in job.error_message


@pytest.mark.asyncio
async def test_hydrate_status_endpoint_reconciles_stale_queued_jobs(client, db_session):
    instrument = Instrument(
        ticker="INTC",
        name="Intel",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    stale_job = HydrationJob(
        ticker="INTC",
        market="US",
        instrument_id=instrument.id,
        status="queued",
        requester_source="user",
        celery_task_id="celery-task-stale",
        queued_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        source_metadata={"dispatch_channel": "celery"},
    )
    db_session.add(stale_job)
    await db_session.commit()

    response = await client.get("/api/v1/instruments/INTC/hydrate-status?market=US")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_message"] == "Hydration worker did not start before the queue timeout elapsed."
    assert payload["source_metadata"]["failure_reason"] == "queue_timeout"
