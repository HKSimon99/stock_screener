from datetime import date, timedelta

import pytest

from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.price import Price
from app.models.strategy_score import StrategyScore


@pytest.mark.asyncio
async def test_instrument_endpoint_returns_history_and_metadata(client, db_session):
    instrument = Instrument(
        ticker="NVDA",
        name="Nvidia",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        sector="Technology",
        industry_group="Semiconductors",
        shares_outstanding=1000,
        float_shares=900,
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    history_dates = [date(2026, 4, 11), date(2026, 4, 12), date(2026, 4, 13)]
    final_scores = [48.5, 53.25, 58.85]
    stages = ["2", "2", "3"]

    for score_date, final_score, stage in zip(history_dates, final_scores, stages):
        db_session.add(
            ConsensusScore(
                instrument_id=instrument.id,
                score_date=score_date,
                conviction_level="SILVER",
                final_score=final_score,
                consensus_composite=45.0,
                technical_composite=57.25,
                strategy_pass_count=2,
                regime_warning=False,
            )
        )
        db_session.add(
            StrategyScore(
                instrument_id=instrument.id,
                score_date=score_date,
                canslim_score=68.25,
                piotroski_score=35.0,
                minervini_score=100.0,
                weinstein_score=10.0,
                weinstein_stage=stage,
                dual_mom_score=70.0,
                technical_composite=57.25,
                rs_rating=86.0,
            )
        )

    await db_session.commit()

    response = await client.get("/api/v1/instruments/NVDA?market=US")
    assert response.status_code == 200

    payload = response.json()
    assert payload["exchange"] == "NASDAQ"
    assert payload["sector"] == "Technology"
    assert payload["industry_group"] == "Semiconductors"
    assert payload["shares_outstanding"] == 1000
    assert payload["float_shares"] == 900
    assert [point["date"] for point in payload["score_history"]] == [
        "2026-04-11",
        "2026-04-12",
        "2026-04-13",
    ]
    assert [point["final_score"] for point in payload["score_history"]] == final_scores
    assert [point["stage"] for point in payload["weinstein_stage_history"]] == stages


@pytest.mark.asyncio
async def test_instrument_chart_endpoint_returns_bars_rs_line_and_patterns(client, db_session):
    instrument = Instrument(
        ticker="NVDA",
        name="Nvidia",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    benchmark = Instrument(
        ticker="SPY",
        name="SPDR S&P 500 ETF",
        market="US",
        exchange="NYSE",
        asset_type="etf",
        is_active=True,
    )
    db_session.add_all([instrument, benchmark])
    await db_session.flush()

    start = date(2025, 1, 1)
    for idx in range(230):
        trade_date = start + timedelta(days=idx)
        close = 100 + idx * 0.8
        benchmark_close = 300 + idx * 0.4
        db_session.add(
            Price(
                instrument_id=instrument.id,
                trade_date=trade_date,
                open=close - 1,
                high=close + 2,
                low=close - 2,
                close=close,
                volume=1_000_000 + idx * 1000,
                avg_volume_50d=950_000 + idx * 500,
            )
        )
        db_session.add(
            Price(
                instrument_id=benchmark.id,
                trade_date=trade_date,
                open=benchmark_close - 1,
                high=benchmark_close + 2,
                low=benchmark_close - 2,
                close=benchmark_close,
                volume=5_000_000 + idx * 2000,
                avg_volume_50d=4_900_000 + idx * 1000,
            )
        )

    score_date = start + timedelta(days=229)
    db_session.add(
        ConsensusScore(
            instrument_id=instrument.id,
            score_date=score_date,
            conviction_level="GOLD",
            final_score=74.5,
            consensus_composite=63.2,
            technical_composite=77.0,
            strategy_pass_count=4,
            regime_warning=False,
        )
    )
    db_session.add(
        StrategyScore(
            instrument_id=instrument.id,
            score_date=score_date,
            canslim_score=72.0,
            piotroski_score=80.0,
            minervini_score=88.0,
            weinstein_score=82.0,
            dual_mom_score=75.0,
            technical_composite=77.0,
            patterns=[
                {
                    "pattern_type": "ascending_base",
                    "status": "breakout",
                    "confidence": 0.82,
                    "pivot_price": 210.5,
                    "start_bar": 180,
                    "end_bar": 229,
                    "detail": {
                        "low1": {"bar": 185, "price": 195.0},
                        "low2": {"bar": 198, "price": 201.5},
                        "peaks": [{"bar": 190, "price": 208.0}],
                    },
                }
            ],
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/instruments/NVDA/chart?market=US")
    assert response.status_code == 200

    payload = response.json()
    assert payload["benchmark_ticker"] == "SPY"
    assert payload["benchmark_available"] is True
    assert len(payload["bars"]) == 230
    assert payload["bars"][-1]["sma_50"] is not None
    assert payload["bars"][-1]["sma_150"] is not None
    assert payload["bars"][-1]["sma_200"] is not None
    assert len(payload["rs_line"]) == 230
    assert payload["patterns"][0]["pattern_type"] == "ascending_base"
    assert payload["patterns"][0]["pivot_price"] == 210.5
    assert len(payload["patterns"][0]["anchors"]) >= 3
