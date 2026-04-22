from datetime import date, timedelta

import pytest

from app.models.consensus_score import ConsensusScore
from app.models.coverage_summary import InstrumentCoverageSummary
from app.models.fundamental import FundamentalAnnual
from app.models.instrument import Instrument
from app.models.price import Price
from app.services.universe import build_coverage_map, refresh_instrument_coverage_summary
from app.services.strategies.snapshot_generator import build_snapshot_payload


@pytest.mark.asyncio
async def test_search_endpoint_returns_coverage_state_and_reasons(client, db_session):
    ranked = Instrument(
        ticker="AAPL",
        name="Apple Inc.",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        listing_status="LISTED",
        is_active=True,
    )
    db_session.add(ranked)
    await db_session.flush()

    for idx in range(130):
        trade_date = date(2025, 12, 1) + timedelta(days=idx)
        db_session.add(
            Price(
                instrument_id=ranked.id,
                trade_date=trade_date,
                open=190 + idx,
                high=192 + idx,
                low=188 + idx,
                close=191 + idx,
                volume=10_000_000,
                avg_volume_50d=9_500_000,
            )
        )
    db_session.add(
        FundamentalAnnual(
            instrument_id=ranked.id,
            fiscal_year=2025,
            report_date=date(2026, 2, 1),
            revenue=1_000,
            net_income=200,
            total_assets=800,
            current_assets=300,
            current_liabilities=100,
            operating_cash_flow=240,
            data_source="EDGAR",
        )
    )
    db_session.add(
        ConsensusScore(
            instrument_id=ranked.id,
            score_date=date(2026, 4, 13),
            conviction_level="GOLD",
            final_score=78.0,
            consensus_composite=70.0,
            technical_composite=82.0,
            strategy_pass_count=4,
            regime_warning=False,
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/search?q=AAPL")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["ticker"] == "AAPL"
    assert payload["items"][0]["coverage_state"] == "ranked"
    assert payload["items"][0]["ranking_eligibility"]["eligible"] is True


@pytest.mark.asyncio
async def test_instrument_endpoint_returns_partial_detail_when_not_yet_scored(client, db_session):
    """
    Unranked but price-ready instruments should still return a usable partial
    detail payload so the frontend can show coverage and refresh state instead
    of hanging on a missing-score 404.
    """
    instrument = Instrument(
        ticker="MSFT",
        name="Microsoft",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        listing_status="LISTED",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    db_session.add(
        Price(
            instrument_id=instrument.id,
            trade_date=date(2026, 4, 13),
            open=400,
            high=403,
            low=398,
            close=402,
            volume=8_000_000,
            avg_volume_50d=7_000_000,
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/instruments/MSFT?market=US")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "MSFT"
    assert payload["coverage_state"] == "price_ready"
    assert payload["conviction_level"] == "UNRANKED"
    assert payload["final_score"] is None


@pytest.mark.asyncio
async def test_chart_endpoint_supports_interval_and_price_fallback(client, db_session):
    instrument = Instrument(
        ticker="QQQ",
        name="Invesco QQQ",
        market="US",
        exchange="NASDAQ",
        asset_type="etf",
        listing_status="LISTED",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    start = date(2025, 1, 1)
    for idx in range(220):
        trade_date = start + timedelta(days=idx)
        close = 300 + idx
        db_session.add(
            Price(
                instrument_id=instrument.id,
                trade_date=trade_date,
                open=close - 1,
                high=close + 2,
                low=close - 2,
                close=close,
                volume=5_000_000 + idx * 100,
                avg_volume_50d=4_800_000 + idx * 50,
            )
        )
    await db_session.commit()

    response = await client.get("/api/v1/instruments/QQQ/chart?market=US&interval=1w&range_days=180")

    assert response.status_code == 200
    payload = response.json()
    assert payload["interval"] == "1w"
    assert payload["range_days"] == 180
    assert payload["delay_minutes"] == 15
    assert len(payload["bars"]) < 180
    assert payload["score_date"] == (start + timedelta(days=219)).isoformat()


@pytest.mark.asyncio
async def test_universe_coverage_endpoint_groups_states(client, db_session):
    ranked = Instrument(
        ticker="NVDA",
        name="Nvidia",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        listing_status="LISTED",
        is_active=True,
    )
    price_ready = Instrument(
        ticker="SPY",
        name="SPDR S&P 500 ETF",
        market="US",
        exchange="NYSE",
        asset_type="etf",
        listing_status="LISTED",
        is_active=True,
    )
    searchable = Instrument(
        ticker="005930",
        name="Samsung Electronics",
        name_kr="삼성전자",
        market="KR",
        exchange="KOSPI",
        asset_type="stock",
        listing_status="LISTED",
        is_active=True,
    )
    db_session.add_all([ranked, price_ready, searchable])
    await db_session.flush()

    db_session.add(
        Price(
            instrument_id=ranked.id,
            trade_date=date(2026, 4, 13),
            open=100,
            high=102,
            low=98,
            close=101,
            volume=1_000_000,
            avg_volume_50d=900_000,
        )
    )
    db_session.add(
        Price(
            instrument_id=price_ready.id,
            trade_date=date(2026, 4, 13),
            open=500,
            high=502,
            low=498,
            close=501,
            volume=2_000_000,
            avg_volume_50d=1_900_000,
        )
    )
    db_session.add(
        FundamentalAnnual(
            instrument_id=ranked.id,
            fiscal_year=2025,
            report_date=date(2026, 2, 1),
            revenue=1000,
            net_income=220,
            total_assets=800,
            current_assets=320,
            current_liabilities=120,
            operating_cash_flow=260,
            data_source="EDGAR",
        )
    )
    db_session.add(
        ConsensusScore(
            instrument_id=ranked.id,
            score_date=date(2026, 4, 13),
            conviction_level="GOLD",
            final_score=76,
            consensus_composite=70,
            technical_composite=79,
            strategy_pass_count=4,
            regime_warning=False,
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/universe/coverage")

    assert response.status_code == 200
    payload = response.json()
    us_stock = next(
        item for item in payload["items"] if item["market"] == "US" and item["asset_type"] == "stock"
    )
    us_etf = next(
        item for item in payload["items"] if item["market"] == "US" and item["asset_type"] == "etf"
    )
    kr_stock = next(
        item for item in payload["items"] if item["market"] == "KR" and item["asset_type"] == "stock"
    )

    assert us_stock["searchable"] == 1
    assert us_stock["ranked"] == 1
    assert us_etf["price_ready"] == 1
    assert us_etf["ranked"] == 0
    assert kr_stock["searchable"] == 1
    assert kr_stock["price_ready"] == 0


@pytest.mark.asyncio
async def test_refresh_coverage_summary_persists_and_build_coverage_map_reuses_it(db_session):
    instrument = Instrument(
        ticker="META",
        name="Meta Platforms",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        listing_status="LISTED",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    for idx in range(126):
        trade_date = date(2025, 12, 1) + timedelta(days=idx)
        db_session.add(
            Price(
                instrument_id=instrument.id,
                trade_date=trade_date,
                open=500 + idx,
                high=503 + idx,
                low=498 + idx,
                close=501 + idx,
                volume=3_000_000,
                avg_volume_50d=2_500_000,
            )
        )
    db_session.add(
        FundamentalAnnual(
            instrument_id=instrument.id,
            fiscal_year=2025,
            report_date=date(2026, 2, 1),
            revenue=2_000,
            net_income=400,
            total_assets=1_200,
            current_assets=450,
            current_liabilities=180,
            operating_cash_flow=420,
            data_source="EDGAR",
        )
    )
    db_session.add(
        ConsensusScore(
            instrument_id=instrument.id,
            score_date=date(2026, 4, 13),
            conviction_level="GOLD",
            final_score=80.0,
            consensus_composite=74.0,
            technical_composite=84.0,
            strategy_pass_count=4,
            regime_warning=False,
        )
    )
    await db_session.commit()

    refreshed = await refresh_instrument_coverage_summary(db_session, instrument_ids=[instrument.id])
    await db_session.commit()

    assert refreshed == 1
    stored = await db_session.get(InstrumentCoverageSummary, instrument.id)
    assert stored is not None
    assert stored.coverage_state == "ranked"
    assert stored.ranking_eligible is True
    assert stored.price_bar_count == 126

    coverage_map = await build_coverage_map(db_session, [instrument])
    assert coverage_map[instrument.id].coverage_state == "ranked"
    assert coverage_map[instrument.id].ranking_eligibility["eligible"] is True


@pytest.mark.asyncio
async def test_search_endpoint_prioritizes_exact_and_prefix_matches(client, db_session):
    exact = Instrument(
        ticker="NV",
        name="Exact Match",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        listing_status="LISTED",
        is_active=True,
    )
    prefix = Instrument(
        ticker="NVDA",
        name="NVIDIA",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        listing_status="LISTED",
        is_active=True,
    )
    contains = Instrument(
        ticker="ABNV",
        name="Contains Only",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        listing_status="LISTED",
        is_active=True,
    )
    db_session.add_all([exact, prefix, contains])
    await db_session.commit()

    response = await client.get("/api/v1/search?q=NV")

    assert response.status_code == 200
    payload = response.json()
    assert [item["ticker"] for item in payload["items"][:3]] == ["NV", "NVDA", "ABNV"]


@pytest.mark.asyncio
async def test_snapshot_payload_filters_asset_type(db_session):
    snapshot_date = date(2026, 4, 13)
    stock = Instrument(
        ticker="AMD",
        name="AMD",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        listing_status="LISTED",
        is_active=True,
    )
    etf = Instrument(
        ticker="XLK",
        name="Technology Select Sector SPDR",
        market="US",
        exchange="NYSE Arca",
        asset_type="etf",
        listing_status="LISTED",
        is_active=True,
    )
    db_session.add_all([stock, etf])
    await db_session.flush()

    db_session.add_all(
        [
            ConsensusScore(
                instrument_id=stock.id,
                score_date=snapshot_date,
                conviction_level="GOLD",
                final_score=70,
                consensus_composite=65,
                technical_composite=75,
                strategy_pass_count=4,
                regime_warning=False,
            ),
            ConsensusScore(
                instrument_id=etf.id,
                score_date=snapshot_date,
                conviction_level="SILVER",
                final_score=60,
                consensus_composite=55,
                technical_composite=64,
                strategy_pass_count=2,
                regime_warning=False,
            ),
        ]
    )
    await db_session.commit()

    payload = await build_snapshot_payload(
        db_session,
        snapshot_date=snapshot_date,
        market="US",
        asset_type="stock",
    )

    assert payload is not None
    assert [row["ticker"] for row in payload["rankings_json"]] == ["AMD"]
