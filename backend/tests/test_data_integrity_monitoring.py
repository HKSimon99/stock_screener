from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.alert import Alert
from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.snapshot import DataFreshness, ScoringSnapshot
from app.models.strategy_score import StrategyScore
from app.services.ingestion.freshness import monitor_data_integrity


@pytest.mark.asyncio
async def test_monitor_data_integrity_creates_alerts_for_stale_sources_gaps_and_snapshot_mismatch(
    db_session,
):
    as_of = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)
    score_date = date(2026, 4, 13)

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

    db_session.add(
        DataFreshness(
            source_name="US_PRICES",
            market="US",
            last_success_at=as_of - timedelta(hours=72),
            next_expected=as_of - timedelta(hours=48),
            records_updated=1,
            staleness_threshold_hours=36,
        )
    )
    db_session.add(
        ConsensusScore(
            instrument_id=instrument.id,
            score_date=score_date,
            conviction_level="GOLD",
            final_score=76.5,
            consensus_composite=68.0,
            technical_composite=72.0,
            strategy_pass_count=4,
            canslim_score=82.0,
            piotroski_score=70.0,
            minervini_score=88.0,
            weinstein_score=80.0,
            dual_mom_score=75.0,
            regime_warning=False,
        )
    )
    db_session.add(
        ScoringSnapshot(
            snapshot_date=score_date,
            market="US",
            asset_type="stock",
            regime_state="CONFIRMED_UPTREND",
            rankings_json=[
                {
                    "rank": 1,
                    "instrument_id": instrument.id,
                    "ticker": "BROKEN",
                    "name": "Broken Snapshot",
                    "conviction_level": "GOLD",
                    "final_score": 10.0,
                    "consensus_composite": 10.0,
                    "technical_composite": 10.0,
                    "strategy_pass_count": 1,
                    "scores": {
                        "canslim": 10.0,
                        "piotroski": 10.0,
                        "minervini": 10.0,
                        "weinstein": 10.0,
                        "dual_mom": 10.0,
                    },
                    "regime_warning": False,
                }
            ],
            metadata_={
                "config_hash": "stale-config",
                "instruments_count": 1,
                "avg_final_score": 10.0,
                "conviction_distribution": {"GOLD": 1},
            },
        )
    )
    await db_session.commit()

    result = await monitor_data_integrity(
        db_session,
        markets=["US"],
        as_of=as_of,
        score_date=score_date,
        snapshot_date=score_date,
        include_distribution=False,
    )

    assert result["alerts_created"] == 4
    assert result["freshness"][0]["status"] == "stale"
    assert result["coverage"]["US"]["prices"]["missing_count"] == 1
    assert result["coverage"]["US"]["fundamentals"]["stale_count"] == 1
    assert result["snapshots"][0]["status"] == "failed"

    alerts = (await db_session.execute(select(Alert).order_by(Alert.title.asc()))).scalars().all()
    titles = {alert.title for alert in alerts}
    assert titles == {
        "US missing fresh price data",
        "US snapshot reproducibility mismatch",
        "US stale fundamentals detected",
        "US US_PRICES freshness stale",
    }


@pytest.mark.asyncio
async def test_monitor_data_integrity_accepts_reasonable_rs_and_piotroski_distributions(
    db_session,
):
    score_date = date(2026, 4, 13)
    rs_values = [5, 12, 18, 27, 35, 45, 55, 65, 75, 85, 92, 99]
    piotroski_values = [2, 3, 4, 5, 6, 7, 5, 4, 6, 3, 5, 7]

    instruments = [
        Instrument(
            ticker=f"T{index:02d}",
            name=f"Test {index:02d}",
            market="US",
            exchange="NASDAQ",
            asset_type="stock",
            is_active=True,
        )
        for index in range(len(rs_values))
    ]
    db_session.add_all(instruments)
    await db_session.flush()

    db_session.add_all(
        [
            StrategyScore(
                instrument_id=instrument.id,
                score_date=score_date,
                rs_rating=rs_value,
                piotroski_f_raw=piotroski_value,
            )
            for instrument, rs_value, piotroski_value in zip(instruments, rs_values, piotroski_values)
        ]
    )
    await db_session.commit()

    result = await monitor_data_integrity(
        db_session,
        markets=["US"],
        as_of=datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc),
        score_date=score_date,
        include_freshness=False,
        include_coverage=False,
        include_distribution=True,
        include_snapshot=False,
    )

    assert result["alerts_created"] == 0
    assert result["distributions"]["US"]["rs"]["status"] == "ok"
    assert result["distributions"]["US"]["piotroski"]["status"] == "ok"
