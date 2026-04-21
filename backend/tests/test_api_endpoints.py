from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.alert import Alert
from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.market_regime import MarketRegime
from app.models.snapshot import ScoringSnapshot
from app.models.strategy_score import StrategyScore


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
