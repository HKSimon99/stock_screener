from datetime import date

import pytest

from app.models.instrument import Instrument
from app.models.market_regime import MarketRegime
from app.models.strategy_score import StrategyScore
from app.services.strategies.consensus import (
    compute_consensus,
    get_latest_regime,
    score_instrument_consensus,
)


def test_compute_consensus_assigns_diamond_when_score_and_passes_clear_threshold():
    result = compute_consensus(
        canslim_score=90.0,
        piotroski_score=85.0,
        minervini_score=88.0,
        weinstein_score=82.0,
        dual_mom_score=75.0,
        technical_composite=80.0,
        regime_state="CONFIRMED_UPTREND",
    )

    assert result["consensus_composite"] == pytest.approx(68.15, abs=0.01)
    assert result["final_score"] == pytest.approx(84.15, abs=0.01)
    assert result["strategy_pass_count"] == 5
    assert result["conviction_level"] == "DIAMOND"
    assert result["regime_warning"] is False
    assert result["score_breakdown"]["raw_conviction"] == "DIAMOND"
    assert result["score_breakdown"]["final_conviction"] == "DIAMOND"


def test_compute_consensus_requires_strategy_agreement_not_just_high_average():
    result = compute_consensus(
        canslim_score=80.0,
        piotroski_score=None,
        minervini_score=60.0,
        weinstein_score=None,
        dual_mom_score=None,
        technical_composite=None,
        regime_state="CONFIRMED_UPTREND",
    )

    assert result["consensus_composite"] == pytest.approx(70.0, abs=0.01)
    assert result["final_score"] == pytest.approx(70.0, abs=0.01)
    assert result["strategy_pass_count"] == 1
    assert result["conviction_level"] == "BRONZE"
    assert result["score_breakdown"]["strategy_weights"] == {
        "canslim": 0.5,
        "minervini": 0.5,
    }


@pytest.mark.parametrize(
    ("regime_state", "expected_conviction"),
    [
        ("UPTREND_UNDER_PRESSURE", "GOLD"),
        ("MARKET_IN_CORRECTION", "SILVER"),
    ],
)
def test_compute_consensus_applies_regime_caps(regime_state: str, expected_conviction: str):
    result = compute_consensus(
        canslim_score=90.0,
        piotroski_score=85.0,
        minervini_score=88.0,
        weinstein_score=82.0,
        dual_mom_score=75.0,
        technical_composite=80.0,
        regime_state=regime_state,
    )

    assert result["final_score"] == pytest.approx(84.15, abs=0.01)
    assert result["strategy_pass_count"] == 5
    assert result["conviction_level"] == expected_conviction
    assert result["regime_warning"] is True
    assert result["score_breakdown"]["raw_conviction"] == "DIAMOND"
    assert result["score_breakdown"]["final_conviction"] == expected_conviction
    assert result["score_breakdown"]["regime_cap"] == expected_conviction


def test_compute_consensus_returns_unranked_when_no_strategy_scores_exist():
    result = compute_consensus(
        canslim_score=None,
        piotroski_score=None,
        minervini_score=None,
        weinstein_score=None,
        dual_mom_score=None,
        technical_composite=92.0,
        regime_state="CONFIRMED_UPTREND",
    )

    assert result["consensus_composite"] is None
    assert result["final_score"] == 0.0
    assert result["strategy_pass_count"] == 0
    assert result["conviction_level"] == "UNRANKED"
    assert result["regime_warning"] is False
    assert result["score_breakdown"]["error"] == "no strategy scores available"


@pytest.mark.asyncio
async def test_score_instrument_consensus_uses_latest_regime_on_or_before_score_date(
    db_session,
):
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
        StrategyScore(
            instrument_id=instrument.id,
            score_date=score_date,
            canslim_score=90.0,
            piotroski_score=85.0,
            minervini_score=88.0,
            weinstein_score=82.0,
            dual_mom_score=75.0,
            technical_composite=80.0,
        )
    )
    db_session.add_all(
        [
            MarketRegime(
                market="US",
                effective_date=date(2026, 4, 10),
                state="CONFIRMED_UPTREND",
                prior_state="UPTREND_UNDER_PRESSURE",
                trigger_reason="Follow-through day",
                distribution_day_count=2,
                follow_through_day=True,
            ),
            MarketRegime(
                market="US",
                effective_date=score_date,
                state="MARKET_IN_CORRECTION",
                prior_state="CONFIRMED_UPTREND",
                trigger_reason="Distribution and drawdown breach",
                distribution_day_count=8,
                follow_through_day=False,
            ),
            MarketRegime(
                market="US",
                effective_date=date(2026, 4, 15),
                state="CONFIRMED_UPTREND",
                prior_state="MARKET_IN_CORRECTION",
                trigger_reason="Future recovery that should be ignored",
                distribution_day_count=1,
                follow_through_day=True,
            ),
        ]
    )
    await db_session.commit()

    regime_state = await get_latest_regime("US", score_date, db_session)
    scored = await score_instrument_consensus(
        instrument_id=instrument.id,
        market="US",
        score_date=score_date,
        db=db_session,
        regime_state=regime_state,
    )

    assert regime_state == "MARKET_IN_CORRECTION"
    assert scored is not None
    assert scored["final_score"] == pytest.approx(84.15, abs=0.01)
    assert scored["strategy_pass_count"] == 5
    assert scored["conviction_level"] == "SILVER"
    assert scored["regime_warning"] is True
    assert scored["score_breakdown"]["raw_conviction"] == "DIAMOND"
    assert scored["score_breakdown"]["final_conviction"] == "SILVER"
