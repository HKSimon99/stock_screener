from datetime import date

import pytest

from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.strategy_score import StrategyScore


@pytest.mark.asyncio
async def test_filters_endpoint_supports_pattern_filter(client, db_session):
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

    score_date = date(2026, 4, 13)
    db_session.add(
        ConsensusScore(
            instrument_id=instrument.id,
            score_date=score_date,
            conviction_level="GOLD",
            final_score=74.5,
            consensus_composite=68.0,
            technical_composite=71.0,
            strategy_pass_count=4,
            canslim_score=78.0,
            piotroski_score=70.0,
            minervini_score=88.0,
            weinstein_score=82.0,
            dual_mom_score=72.0,
            regime_warning=False,
        )
    )
    db_session.add(
        StrategyScore(
            instrument_id=instrument.id,
            score_date=score_date,
            canslim_score=78.0,
            piotroski_score=70.0,
            piotroski_f_raw=7,
            minervini_score=88.0,
            minervini_criteria_count=7,
            weinstein_score=82.0,
            weinstein_stage="2",
            dual_mom_score=72.0,
            dual_mom_abs=True,
            dual_mom_rel=True,
            technical_composite=71.0,
            ad_rating="A",
            rs_line_new_high=True,
            patterns=[
                {
                    "pattern_type": "cup_with_handle",
                    "status": "complete",
                    "confidence": 0.74,
                    "pivot_price": 190.0,
                }
            ],
        )
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/filters/query",
        json={
            "market": "US",
            "has_pattern": "cup_with_handle",
            "limit": 10,
            "sort_by": "final_score",
            "sort_dir": "desc",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_found"] == 1
    assert payload["items"][0]["ticker"] == "NVDA"


@pytest.mark.asyncio
async def test_filters_endpoint_requires_clerk_auth(unauth_client):
    response = await unauth_client.post(
        "/api/v1/filters/query",
        json={"market": "US", "limit": 10, "sort_by": "final_score", "sort_dir": "desc"},
    )

    assert response.status_code == 401
