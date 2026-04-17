from datetime import date, timedelta

import pytest

from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.price import Price
from app.services.strategies import backtest_validation


class BoundSessionFactory:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_calculate_max_drawdown_tracks_peak_to_trough():
    drawdown = backtest_validation._calculate_max_drawdown([100.0, 110.0, 90.0, 120.0])
    assert drawdown == pytest.approx(-0.18181818, rel=1e-6)


@pytest.mark.asyncio
async def test_run_consensus_backtest_groups_returns_and_benchmark(monkeypatch, db_session):
    scoring_date = date(2026, 1, 1)

    instruments = [
        Instrument(
            ticker="AAPL",
            name="Apple",
            market="US",
            exchange="NASDAQ",
            asset_type="stock",
            is_active=True,
        ),
        Instrument(
            ticker="MSFT",
            name="Microsoft",
            market="US",
            exchange="NASDAQ",
            asset_type="stock",
            is_active=True,
        ),
        Instrument(
            ticker="SPY",
            name="SPDR S&P 500 ETF",
            market="US",
            exchange="NYSE",
            asset_type="etf",
            is_active=True,
        ),
    ]
    db_session.add_all(instruments)
    await db_session.flush()

    db_session.add_all(
        [
            ConsensusScore(
                instrument_id=instruments[0].id,
                score_date=scoring_date,
                final_score=90,
                conviction_level="GOLD",
            ),
            ConsensusScore(
                instrument_id=instruments[1].id,
                score_date=scoring_date,
                final_score=55,
                conviction_level="BRONZE",
            ),
        ]
    )

    for offset in range(22):
        trade_date = scoring_date + timedelta(days=offset)
        aapl_close = 100 + offset
        msft_close = 100 if offset == 0 else 95
        spy_close = 100 + (offset * 0.5)

        db_session.add(
            Price(
                instrument_id=instruments[0].id,
                trade_date=trade_date,
                open=aapl_close,
                high=aapl_close,
                low=aapl_close,
                close=aapl_close,
                volume=1_000_000,
                avg_volume_50d=1_000_000,
            )
        )
        db_session.add(
            Price(
                instrument_id=instruments[1].id,
                trade_date=trade_date,
                open=msft_close,
                high=msft_close,
                low=msft_close,
                close=msft_close,
                volume=1_000_000,
                avg_volume_50d=1_000_000,
            )
        )
        db_session.add(
            Price(
                instrument_id=instruments[2].id,
                trade_date=trade_date,
                open=spy_close,
                high=spy_close,
                low=spy_close,
                close=spy_close,
                volume=1_000_000,
                avg_volume_50d=1_000_000,
            )
        )

    await db_session.commit()

    async def fake_pipeline(score_date=None, market=None, instrument_ids=None):
        return {
            "score_date": score_date,
            "market": market,
            "instrument_ids": instrument_ids,
            "replayed": True,
        }

    monkeypatch.setattr(backtest_validation, "_run_full_scoring_pipeline", fake_pipeline)
    monkeypatch.setattr(backtest_validation, "AsyncSessionLocal", BoundSessionFactory(db_session))

    report = await backtest_validation.run_consensus_backtest(
        market="US",
        scoring_date=scoring_date,
        forward_windows={"1m": 21},
    )

    assert report["pipeline"]["replayed"] is True
    assert report["markets"]["US"]["benchmark_ticker"] == "SPY"
    assert report["markets"]["US"]["benchmark_returns_pct"]["1m"] == pytest.approx(10.5)
    assert report["markets"]["US"]["n_scored"] == 2

    gold = report["markets"]["US"]["conviction_groups"]["GOLD"]
    bronze = report["markets"]["US"]["conviction_groups"]["BRONZE"]

    assert gold["n"] == 1
    assert gold["avg_final_score"] == 90.0
    assert gold["tickers"] == ["AAPL"]
    assert gold["horizons"]["1m"] == {
        "n": 1,
        "avg_return_pct": 21.0,
        "avg_excess_return_pct": 10.5,
        "avg_max_drawdown_pct": 0.0,
        "hit_rate": 100.0,
        "benchmark_return_pct": 10.5,
    }

    assert bronze["n"] == 1
    assert bronze["tickers"] == ["MSFT"]
    assert bronze["horizons"]["1m"] == {
        "n": 1,
        "avg_return_pct": -5.0,
        "avg_excess_return_pct": -15.5,
        "avg_max_drawdown_pct": -5.0,
        "hit_rate": 0.0,
        "benchmark_return_pct": 10.5,
    }
