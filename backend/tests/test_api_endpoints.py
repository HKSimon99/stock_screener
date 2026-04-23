from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.alert import Alert
from app.models.consensus_score import ConsensusScore
from app.models.coverage_summary import InstrumentCoverageSummary
from app.models.instrument import Instrument
from app.models.market_regime import MarketRegime
from app.models.snapshot import ScoringSnapshot
from app.models.strategy_score import StrategyScore
from app.services.universe import latest_expected_price_date


@pytest.mark.asyncio
async def test_rankings_endpoint_returns_weinstein_stage_and_regime(client, db_session):
    """
    Phase 4.7: rankings endpoint is now a direct consensus_scores query (no
    snapshot path). Verifies that the endpoint attaches the Weinstein stage
    via JOIN and that the MarketRegime lookup populates ``regime_state``.
    """
    snapshot_date = date(2026, 4, 13)
    nvda = Instrument(
        ticker="NVDA",
        name="Nvidia",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    aapl = Instrument(
        ticker="AAPL",
        name="Apple",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    db_session.add_all([nvda, aapl])
    await db_session.flush()

    db_session.add_all([
        ConsensusScore(
            instrument_id=nvda.id,
            score_date=snapshot_date,
            conviction_level="GOLD",
            final_score=74.5,
            consensus_composite=63.2,
            technical_composite=77.0,
            strategy_pass_count=4,
            canslim_score=72.0,
            piotroski_score=80.0,
            minervini_score=88.0,
            weinstein_score=82.0,
            regime_warning=False,
        ),
        ConsensusScore(
            instrument_id=aapl.id,
            score_date=snapshot_date,
            conviction_level="SILVER",
            final_score=66.2,
            consensus_composite=58.1,
            technical_composite=69.0,
            strategy_pass_count=3,
            canslim_score=64.0,
            piotroski_score=78.0,
            minervini_score=70.0,
            weinstein_score=62.0,
            regime_warning=True,
        ),
        StrategyScore(
            instrument_id=nvda.id,
            score_date=snapshot_date,
            weinstein_stage="2_mid",
            weinstein_score=82.0,
        ),
        StrategyScore(
            instrument_id=aapl.id,
            score_date=snapshot_date,
            weinstein_stage="1",
            weinstein_score=62.0,
        ),
        MarketRegime(
            market="US",
            effective_date=snapshot_date,
            state="CONFIRMED_UPTREND",
        ),
    ])
    await db_session.commit()

    response = await client.get(
        f"/api/v1/rankings?market=US&asset_type=stock&score_date={snapshot_date.isoformat()}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["regime_state"] == "CONFIRMED_UPTREND"
    assert payload["pagination"]["total"] == 2
    assert payload["regime_warning_count"] == 1
    assert [item["ticker"] for item in payload["items"]] == ["NVDA", "AAPL"]
    # Weinstein stage is now exposed for gate display
    stage_by_ticker = {item["ticker"]: item["weinstein_stage"] for item in payload["items"]}
    assert stage_by_ticker["NVDA"] == "2_mid"
    assert stage_by_ticker["AAPL"] == "1"


@pytest.mark.asyncio
async def test_rankings_endpoint_defaults_to_latest_snapshot_date_over_newer_single_symbol_scores(
    client,
    db_session,
):
    stable_date = date(2026, 4, 13)
    newer_single_symbol_date = date(2026, 4, 14)
    instruments = [
        Instrument(
            ticker="AMD",
            name="AMD",
            market="US",
            exchange="NASDAQ",
            asset_type="stock",
            is_active=True,
        ),
        Instrument(
            ticker="CSCO",
            name="Cisco",
            market="US",
            exchange="NASDAQ",
            asset_type="stock",
            is_active=True,
        ),
    ]
    db_session.add_all(instruments)
    await db_session.flush()

    db_session.add_all(
        [
            ConsensusScore(
                instrument_id=instruments[0].id,
                score_date=stable_date,
                conviction_level="GOLD",
                final_score=76.5,
                consensus_composite=66.2,
                technical_composite=71.0,
                strategy_pass_count=5,
                canslim_score=74.1,
                piotroski_score=78.0,
                minervini_score=100.0,
                weinstein_score=85.0,
                dual_mom_score=70.0,
                regime_warning=False,
            ),
            ConsensusScore(
                instrument_id=instruments[1].id,
                score_date=stable_date,
                conviction_level="SILVER",
                final_score=72.0,
                consensus_composite=58.0,
                technical_composite=69.0,
                strategy_pass_count=3,
                canslim_score=45.7,
                piotroski_score=90.0,
                minervini_score=100.0,
                weinstein_score=85.0,
                dual_mom_score=70.0,
                regime_warning=True,
            ),
            ConsensusScore(
                instrument_id=instruments[0].id,
                score_date=newer_single_symbol_date,
                conviction_level="PLATINUM",
                final_score=81.0,
                consensus_composite=73.0,
                technical_composite=78.0,
                strategy_pass_count=5,
                canslim_score=80.0,
                piotroski_score=79.0,
                minervini_score=98.0,
                weinstein_score=87.0,
                dual_mom_score=74.0,
                regime_warning=False,
            ),
            ScoringSnapshot(
                snapshot_date=stable_date,
                market="US",
                asset_type="stock",
                regime_state="CONFIRMED_UPTREND",
                rankings_json=[
                    {"ticker": "AMD"},
                    {"ticker": "CSCO"},
                ],
                metadata_={"instruments_count": 2, "config_hash": "stable"},
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/rankings?market=US&asset_type=stock")

    assert response.status_code == 200
    payload = response.json()
    assert payload["score_date"] == stable_date.isoformat()
    assert [item["ticker"] for item in payload["items"]] == ["AMD", "CSCO"]
    assert payload["pagination"]["total"] == 2


@pytest.mark.asyncio
async def test_rankings_endpoint_supports_advanced_get_filters(client, db_session):
    snapshot_date = latest_expected_price_date("US")
    price_as_of = snapshot_date
    annual_as_of = snapshot_date
    quarterly_as_of = snapshot_date
    instruments = [
        Instrument(
            ticker="NVDA",
            name="Nvidia",
            market="US",
            exchange="NASDAQ",
            asset_type="stock",
            sector="Technology",
            is_active=True,
        ),
        Instrument(
            ticker="AAPL",
            name="Apple",
            market="US",
            exchange="NASDAQ",
            asset_type="stock",
            sector="Technology",
            is_active=True,
        ),
        Instrument(
            ticker="JPM",
            name="JPMorgan",
            market="US",
            exchange="NYSE",
            asset_type="stock",
            sector="Financials",
            is_active=True,
        ),
    ]
    db_session.add_all(instruments)
    await db_session.flush()

    db_session.add_all(
        [
            ConsensusScore(
                instrument_id=instruments[0].id,
                score_date=snapshot_date,
                conviction_level="GOLD",
                final_score=88.0,
                consensus_composite=86.0,
                technical_composite=84.0,
                strategy_pass_count=4,
                canslim_score=82.0,
                piotroski_score=78.0,
                minervini_score=90.0,
                weinstein_score=81.0,
                regime_warning=False,
            ),
            ConsensusScore(
                instrument_id=instruments[1].id,
                score_date=snapshot_date,
                conviction_level="SILVER",
                final_score=72.0,
                consensus_composite=70.0,
                technical_composite=65.0,
                strategy_pass_count=2,
                canslim_score=64.0,
                piotroski_score=76.0,
                minervini_score=68.0,
                weinstein_score=58.0,
                regime_warning=False,
            ),
            ConsensusScore(
                instrument_id=instruments[2].id,
                score_date=snapshot_date,
                conviction_level="GOLD",
                final_score=83.0,
                consensus_composite=81.0,
                technical_composite=79.0,
                strategy_pass_count=4,
                canslim_score=70.0,
                piotroski_score=82.0,
                minervini_score=76.0,
                weinstein_score=80.0,
                regime_warning=False,
            ),
            StrategyScore(
                instrument_id=instruments[0].id,
                score_date=snapshot_date,
                weinstein_stage="2_mid",
                rs_rating=92.0,
                ad_rating="A",
                rs_line_new_high=True,
            ),
            StrategyScore(
                instrument_id=instruments[1].id,
                score_date=snapshot_date,
                weinstein_stage="1",
                rs_rating=65.0,
                ad_rating="B",
                rs_line_new_high=False,
            ),
            StrategyScore(
                instrument_id=instruments[2].id,
                score_date=snapshot_date,
                weinstein_stage="2_early",
                rs_rating=88.0,
                ad_rating="A",
                rs_line_new_high=True,
            ),
            InstrumentCoverageSummary(
                instrument_id=instruments[0].id,
                coverage_state="ranked",
                price_bar_count=365,
                price_as_of=price_as_of,
                quarterly_as_of=quarterly_as_of,
                annual_as_of=annual_as_of,
                ranked_as_of=snapshot_date,
                ranking_eligible=True,
            ),
            InstrumentCoverageSummary(
                instrument_id=instruments[1].id,
                coverage_state="ranked",
                price_bar_count=365,
                price_as_of=price_as_of,
                quarterly_as_of=None,
                annual_as_of=None,
                ranked_as_of=snapshot_date,
                ranking_eligible=True,
            ),
            InstrumentCoverageSummary(
                instrument_id=instruments[2].id,
                coverage_state="ranked",
                price_bar_count=365,
                price_as_of=price_as_of,
                quarterly_as_of=quarterly_as_of,
                annual_as_of=annual_as_of,
                ranked_as_of=snapshot_date,
                ranking_eligible=True,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/rankings",
        params=[
            ("market", "US"),
            ("asset_type", "stock"),
            ("score_date", snapshot_date.isoformat()),
            ("conviction", "GOLD"),
            ("min_final_score", "80"),
            ("min_consensus_composite", "80"),
            ("min_technical_composite", "80"),
            ("min_strategy_pass_count", "4"),
            ("min_canslim", "80"),
            ("min_piotroski", "75"),
            ("min_minervini", "85"),
            ("min_weinstein", "80"),
            ("min_rs_rating", "90"),
            ("sector", "Technology"),
            ("exchange", "NASDAQ"),
            ("coverage_state", "ranked"),
            ("weinstein_stage", "2_mid"),
            ("ad_rating", "a"),
            ("rs_line_new_high", "true"),
            ("price_ready", "true"),
            ("fundamentals_ready", "true"),
            ("price_as_of_gte", price_as_of.isoformat()),
            ("quarterly_as_of_gte", quarterly_as_of.isoformat()),
            ("annual_as_of_gte", annual_as_of.isoformat()),
            ("ranked_as_of_gte", snapshot_date.isoformat()),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total"] == 1
    assert [item["ticker"] for item in payload["items"]] == ["NVDA"]
    assert payload["items"][0]["coverage_state"] == "ranked"


@pytest.mark.asyncio
async def test_rankings_endpoint_matches_normalized_exchange_and_sector_filters(client, db_session):
    snapshot_date = date(2026, 4, 13)
    instrument = Instrument(
        ticker="AETH",
        name="Bitwise Ethereum ETF",
        market="US",
        exchange="NYSEAMER",
        asset_type="stock",
        sector="반도체",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    db_session.add(
        ConsensusScore(
            instrument_id=instrument.id,
            score_date=snapshot_date,
            conviction_level="GOLD",
            final_score=85.0,
            consensus_composite=82.0,
            technical_composite=81.0,
            strategy_pass_count=4,
            regime_warning=False,
        )
    )
    db_session.add(
        StrategyScore(
            instrument_id=instrument.id,
            score_date=snapshot_date,
            rs_rating=91.0,
            weinstein_stage="2_mid",
            ad_rating="A",
        )
    )
    db_session.add(
        InstrumentCoverageSummary(
            instrument_id=instrument.id,
            coverage_state="ranked",
            price_bar_count=365,
            price_as_of=snapshot_date,
            quarterly_as_of=snapshot_date,
            annual_as_of=snapshot_date,
            ranked_as_of=snapshot_date,
            ranking_eligible=True,
        )
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/rankings",
        params=[
            ("market", "US"),
            ("asset_type", "stock"),
            ("score_date", snapshot_date.isoformat()),
            ("exchange", "NYSE American"),
            ("sector", "Semiconductors"),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["ticker"] for item in payload["items"]] == ["AETH"]
    assert payload["items"][0]["exchange"] == "NYSE American"


@pytest.mark.asyncio
async def test_rankings_endpoint_readiness_filters_exclude_missing_fields(client, db_session):
    snapshot_date = date(2026, 4, 13)
    ready = Instrument(
        ticker="READY",
        name="Ready Co",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        sector="Technology",
        is_active=True,
    )
    missing_fundamentals = Instrument(
        ticker="MISS",
        name="Missing Fundamentals",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        sector="Technology",
        is_active=True,
    )
    db_session.add_all([ready, missing_fundamentals])
    await db_session.flush()

    db_session.add_all(
        [
            ConsensusScore(
                instrument_id=ready.id,
                score_date=snapshot_date,
                conviction_level="GOLD",
                final_score=82.0,
                consensus_composite=80.0,
                technical_composite=81.0,
                strategy_pass_count=4,
                regime_warning=False,
            ),
            ConsensusScore(
                instrument_id=missing_fundamentals.id,
                score_date=snapshot_date,
                conviction_level="GOLD",
                final_score=81.0,
                consensus_composite=79.0,
                technical_composite=80.0,
                strategy_pass_count=4,
                regime_warning=False,
            ),
            InstrumentCoverageSummary(
                instrument_id=ready.id,
                coverage_state="ranked",
                price_bar_count=365,
                price_as_of=snapshot_date,
                annual_as_of=snapshot_date,
                ranked_as_of=snapshot_date,
                ranking_eligible=True,
            ),
            InstrumentCoverageSummary(
                instrument_id=missing_fundamentals.id,
                coverage_state="ranked",
                price_bar_count=365,
                price_as_of=snapshot_date,
                annual_as_of=None,
                quarterly_as_of=None,
                ranked_as_of=snapshot_date,
                ranking_eligible=True,
            ),
        ]
    )
    await db_session.commit()

    ready_response = await client.get(
        f"/api/v1/rankings?market=US&score_date={snapshot_date.isoformat()}&fundamentals_ready=true"
    )
    missing_response = await client.get(
        f"/api/v1/rankings?market=US&score_date={snapshot_date.isoformat()}&fundamentals_ready=false"
    )

    assert ready_response.status_code == 200
    assert missing_response.status_code == 200
    assert [item["ticker"] for item in ready_response.json()["items"]] == ["READY"]
    assert [item["ticker"] for item in missing_response.json()["items"]] == ["MISS"]


@pytest.mark.asyncio
async def test_strategy_rankings_endpoint_orders_scores_desc(client, db_session):
    snapshot_date = date(2026, 4, 13)
    instruments = [
        Instrument(
            ticker="NVDA",
            name="Nvidia",
            market="US",
            exchange="NASDAQ",
            asset_type="stock",
            is_active=True,
        ),
        Instrument(
            ticker="AMD",
            name="AMD",
            market="US",
            exchange="NASDAQ",
            asset_type="stock",
            is_active=True,
        ),
    ]
    db_session.add_all(instruments)
    await db_session.flush()

    db_session.add_all(
        [
            StrategyScore(
                instrument_id=instruments[0].id,
                score_date=snapshot_date,
                canslim_score=81.0,
                canslim_detail={"narrative": "leader"},
            ),
            StrategyScore(
                instrument_id=instruments[1].id,
                score_date=snapshot_date,
                canslim_score=72.5,
                canslim_detail={"narrative": "contender"},
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/strategies/canslim/rankings?market=US")

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy"] == "canslim"
    assert [item["ticker"] for item in payload["items"]] == ["NVDA", "AMD"]
    assert payload["items"][0]["detail"]["narrative"] == "leader"


@pytest.mark.asyncio
async def test_market_regime_endpoint_includes_current_and_history(client, db_session):
    db_session.add_all(
        [
            MarketRegime(
                market="US",
                effective_date=date(2026, 4, 10),
                state="UPTREND_UNDER_PRESSURE",
                prior_state="CONFIRMED_UPTREND",
                trigger_reason="Distribution days rising",
                distribution_day_count=5,
                follow_through_day=False,
            ),
            MarketRegime(
                market="US",
                effective_date=date(2026, 4, 13),
                state="MARKET_IN_CORRECTION",
                prior_state="UPTREND_UNDER_PRESSURE",
                trigger_reason="Death cross confirmed",
                distribution_day_count=8,
                follow_through_day=False,
            ),
            MarketRegime(
                market="KR",
                effective_date=date(2026, 4, 11),
                state="CONFIRMED_UPTREND",
                prior_state="UPTREND_UNDER_PRESSURE",
                trigger_reason="Follow-through day",
                distribution_day_count=2,
                follow_through_day=True,
            ),
            MarketRegime(
                market="KR",
                effective_date=date(2026, 4, 13),
                state="UPTREND_UNDER_PRESSURE",
                prior_state="CONFIRMED_UPTREND",
                trigger_reason="Breadth deterioration",
                distribution_day_count=4,
                follow_through_day=False,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/market-regime?include_history=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["us"]["state"] == "MARKET_IN_CORRECTION"
    assert payload["kr"]["state"] == "UPTREND_UNDER_PRESSURE"
    assert len(payload["history"]) == 2
    assert {entry["market"] for entry in payload["history"]} == {"US", "KR"}


@pytest.mark.asyncio
async def test_ingest_endpoint_runs_data_ingestion_and_defers_scoring(client, db_session, monkeypatch):
    from app.tasks import ingestion_tasks

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
    await db_session.refresh(instrument)

    captured: dict[str, object] = {"scoring_called": False}

    async def fake_us_price_ingestion(*, tickers=None, days=365):
        captured["price_tickers"] = tickers
        captured["price_days"] = days
        return {"ok": True}

    async def fake_fundamentals_ingestion(*, market=None, tickers=None, years=5):
        captured["fundamentals_market"] = market
        captured["fundamentals_tickers"] = tickers
        captured["fundamentals_years"] = years
        return {"ok": True}

    monkeypatch.setattr(ingestion_tasks, "run_us_price_ingestion", fake_us_price_ingestion)
    monkeypatch.setattr(ingestion_tasks, "run_market_fundamentals_ingestion", fake_fundamentals_ingestion)

    response = await client.post("/api/v1/instruments/MSFT/ingest?market=US")

    assert response.status_code == 200
    payload = response.json()
    assert payload["instrument_id"] == instrument.id
    assert captured["price_tickers"] == ["MSFT"]
    assert captured["fundamentals_market"] == "US"
    assert payload["scoring_deferred"] is True
    assert payload["next_step"] == "batch_scoring_required"


@pytest.mark.asyncio
async def test_alerts_endpoint_filters_by_severity_market_and_acknowledged(client, db_session):
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

    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            Alert(
                instrument_id=instrument.id,
                market="US",
                alert_type="RS_BREAKDOWN",
                severity="CRITICAL",
                title="Relative strength cracked",
                detail="RS line failed while price remained near highs.",
                threshold_value=80,
                actual_value=61,
                is_read=False,
                created_at=now,
            ),
            Alert(
                instrument_id=instrument.id,
                market="US",
                alert_type="STOP_LOSS",
                severity="WARNING",
                title="Stop tightening",
                detail="Trail stop moved higher.",
                threshold_value=170,
                actual_value=172,
                is_read=True,
                created_at=now - timedelta(hours=1),
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/alerts?market=US&severity=CRITICAL&acknowledged=false&days=7&limit=20"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["critical"] == 1
    assert payload["warnings"] == 0
    assert payload["items"][0]["ticker"] == "NVDA"
    assert payload["items"][0]["alert_type"] == "RS_BREAKDOWN"


@pytest.mark.asyncio
async def test_snapshots_endpoints_return_latest_and_specific_snapshot(client, db_session):
    older_date = date(2026, 4, 12)
    latest_date = date(2026, 4, 13)

    db_session.add_all(
        [
            ScoringSnapshot(
                snapshot_date=older_date,
                market="US",
                asset_type="stock",
                regime_state="UPTREND_UNDER_PRESSURE",
                rankings_json=[{"ticker": "AMD"}],
                metadata_={
                    "instruments_count": 1,
                    "config_hash": "older",
                    "avg_final_score": 68.0,
                    "conviction_distribution": {"SILVER": 1},
                },
            ),
            ScoringSnapshot(
                snapshot_date=latest_date,
                market="US",
                asset_type="stock",
                regime_state="CONFIRMED_UPTREND",
                rankings_json=[{"ticker": "NVDA"}, {"ticker": "AAPL"}],
                metadata_={
                    "instruments_count": 2,
                    "config_hash": "latest",
                    "avg_final_score": 72.0,
                    "conviction_distribution": {"GOLD": 1, "SILVER": 1},
                },
            ),
        ]
    )
    await db_session.commit()

    latest_response = await client.get("/api/v1/snapshots/latest?market=US&asset_type=stock")
    dated_response = await client.get(
        f"/api/v1/snapshots/{older_date.isoformat()}?market=US&asset_type=stock"
    )

    assert latest_response.status_code == 200
    assert dated_response.status_code == 200

    latest_payload = latest_response.json()
    dated_payload = dated_response.json()

    assert latest_payload["meta"]["snapshot_date"] == latest_date.isoformat()
    assert [item["ticker"] for item in latest_payload["items"]] == ["NVDA", "AAPL"]
    assert dated_payload["meta"]["snapshot_date"] == older_date.isoformat()
    assert dated_payload["items"][0]["ticker"] == "AMD"


@pytest.mark.asyncio
async def test_rankings_endpoint_live_fallback_orders_consensus_scores(client, db_session):
    snapshot_date = date(2026, 4, 13)
    instruments = [
        Instrument(
            ticker="AMD",
            name="AMD",
            market="US",
            exchange="NASDAQ",
            asset_type="stock",
            is_active=True,
        ),
        Instrument(
            ticker="CSCO",
            name="Cisco",
            market="US",
            exchange="NASDAQ",
            asset_type="stock",
            is_active=True,
        ),
    ]
    db_session.add_all(instruments)
    await db_session.flush()

    db_session.add_all(
        [
            ConsensusScore(
                instrument_id=instruments[0].id,
                score_date=snapshot_date,
                conviction_level="GOLD",
                final_score=76.5,
                consensus_composite=66.2,
                technical_composite=71.0,
                strategy_pass_count=5,
                canslim_score=74.1,
                piotroski_score=78.0,
                minervini_score=100.0,
                weinstein_score=85.0,
                dual_mom_score=70.0,
                regime_warning=False,
            ),
            ConsensusScore(
                instrument_id=instruments[1].id,
                score_date=snapshot_date,
                conviction_level="SILVER",
                final_score=72.0,
                consensus_composite=58.0,
                technical_composite=69.0,
                strategy_pass_count=3,
                canslim_score=45.7,
                piotroski_score=90.0,
                minervini_score=100.0,
                weinstein_score=85.0,
                dual_mom_score=70.0,
                regime_warning=True,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/rankings?market=US")

    assert response.status_code == 200
    payload = response.json()
    assert [item["ticker"] for item in payload["items"]] == ["AMD", "CSCO"]
    assert payload["regime_warning_count"] == 1
