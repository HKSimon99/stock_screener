"""
Tests for the consensus scoring engine (consensus.py).

Covers:
  - Market-specific strategy weights (US vs KR)
  - PLATINUM conviction assignment
  - Weinstein Stage 2 gate (non-Stage-2 capped at SILVER)
  - Regime caps (UPTREND_UNDER_PRESSURE → PLATINUM, MARKET_IN_CORRECTION → SILVER)
  - Unranked / no-data path
  - DB-backed score_instrument_consensus with regime lookup
"""

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

# ---------------------------------------------------------------------------
# Pure-function tests (no DB)
# ---------------------------------------------------------------------------

def test_compute_consensus_assigns_diamond_for_top_us_scores():
    """All three US strategies strong + Stage 2 + no regime headwind → DIAMOND."""
    result = compute_consensus(
        market="US",
        canslim_score=95.0,
        piotroski_score=92.0,
        minervini_score=90.0,
        weinstein_stage="2_early",
        weinstein_score=82.0,
        technical_composite=85.0,
        regime_state="CONFIRMED_UPTREND",
    )

    # US: canslim 50%, piotroski 25%, minervini 25% of the 80% strategy budget
    # normalized weights: canslim=0.40, piotroski=0.20, minervini=0.20
    # consensus = 95*0.40 + 92*0.20 + 90*0.20 = 38 + 18.4 + 18 = 74.4
    # final    = 74.4 + 85*0.20 = 74.4 + 17 = 91.4
    assert result["consensus_composite"] == pytest.approx(74.4, abs=0.01)
    assert result["final_score"] == pytest.approx(91.4, abs=0.01)
    assert result["strategy_pass_count"] == 3
    assert result["conviction_level"] == "DIAMOND"
    assert result["regime_warning"] is False
    assert result["weinstein_gate_pass"] is True
    assert result["score_breakdown"]["raw_conviction"] == "DIAMOND"
    assert result["score_breakdown"]["final_conviction"] == "DIAMOND"


def test_compute_consensus_assigns_platinum_for_mid_range_us_scores():
    """Scores above PLATINUM threshold but below DIAMOND with Stage 2 → PLATINUM."""
    result = compute_consensus(
        market="US",
        canslim_score=85.0,
        piotroski_score=82.0,
        minervini_score=80.0,
        weinstein_stage="2_mid",
        weinstein_score=75.0,
        technical_composite=75.0,
        regime_state="CONFIRMED_UPTREND",
    )

    # consensus = 85*0.40 + 82*0.20 + 80*0.20 = 34 + 16.4 + 16 = 66.4
    # final    = 66.4 + 75*0.20 = 66.4 + 15 = 81.4
    assert result["final_score"] == pytest.approx(81.4, abs=0.01)
    assert result["strategy_pass_count"] == 3
    assert result["conviction_level"] == "PLATINUM"
    assert result["regime_warning"] is False
    assert result["weinstein_gate_pass"] is True
    assert result["score_breakdown"]["raw_conviction"] == "PLATINUM"


def test_compute_consensus_requires_strategy_agreement_not_just_high_average():
    """High CANSLIM but only one strategy available → conviction capped by pass count."""
    result = compute_consensus(
        market="US",
        canslim_score=80.0,
        piotroski_score=None,
        minervini_score=60.0,
        technical_composite=None,
        regime_state="CONFIRMED_UPTREND",
    )

    # available: canslim=80, minervini=60 (piotroski missing)
    # raw weights: canslim=0.5, minervini=0.25 → total=0.75
    # normalized (no technical): canslim=0.6667, minervini=0.3333
    # consensus = 80*0.6667 + 60*0.3333 ≈ 73.33
    # pass_count = 1 (canslim ≥ 70; minervini 60 < 70)
    # GOLD requires pass_count ≥ 2 → falls to SILVER (≥ 50 and pass_count ≥ 1)
    assert result["consensus_composite"] == pytest.approx(73.33, abs=0.01)
    assert result["final_score"] == pytest.approx(73.33, abs=0.01)
    assert result["strategy_pass_count"] == 1
    assert result["conviction_level"] == "SILVER"
    assert result["score_breakdown"]["strategy_weights"] == {
        "canslim": 0.6667,
        "minervini": 0.3333,
    }


def test_compute_consensus_weinstein_gate_caps_non_stage2_at_silver():
    """Diamond-worthy scores in Weinstein Stage 1 are capped to SILVER."""
    result = compute_consensus(
        market="US",
        canslim_score=95.0,
        piotroski_score=92.0,
        minervini_score=90.0,
        weinstein_stage="1",          # Stage 1 — not a Stage 2 variant
        weinstein_score=40.0,
        technical_composite=85.0,
        regime_state="CONFIRMED_UPTREND",
    )

    # Same numeric scores as the DIAMOND test → raw conviction = DIAMOND
    assert result["final_score"] == pytest.approx(91.4, abs=0.01)
    assert result["score_breakdown"]["raw_conviction"] == "DIAMOND"

    # Weinstein gate applies: non-Stage-2 → cap at SILVER
    assert result["weinstein_gate_pass"] is False
    assert result["score_breakdown"]["gated_conviction"] == "SILVER"
    assert result["conviction_level"] == "SILVER"

    # Regime didn't add a warning (regime is CONFIRMED_UPTREND; Weinstein gate did the capping)
    assert result["regime_warning"] is False


def test_compute_consensus_weinstein_gate_allows_stage2_late():
    """Stage 2 late is a valid Stage 2 variant — gate should pass."""
    result = compute_consensus(
        market="US",
        canslim_score=95.0,
        piotroski_score=92.0,
        minervini_score=90.0,
        weinstein_stage="2_late",
        technical_composite=85.0,
        regime_state="CONFIRMED_UPTREND",
    )

    assert result["weinstein_gate_pass"] is True
    assert result["conviction_level"] == "DIAMOND"


@pytest.mark.parametrize(
    ("regime_state", "expected_conviction"),
    [
        ("UPTREND_UNDER_PRESSURE", "PLATINUM"),
        ("MARKET_IN_CORRECTION",   "SILVER"),
    ],
)
def test_compute_consensus_applies_regime_caps(regime_state: str, expected_conviction: str):
    """Regime caps are enforced on top of raw conviction."""
    result = compute_consensus(
        market="US",
        canslim_score=95.0,
        piotroski_score=92.0,
        minervini_score=90.0,
        weinstein_stage="2_early",
        weinstein_score=82.0,
        technical_composite=85.0,
        regime_state=regime_state,
    )

    assert result["final_score"] == pytest.approx(91.4, abs=0.01)
    assert result["strategy_pass_count"] == 3
    assert result["conviction_level"] == expected_conviction
    assert result["regime_warning"] is True
    assert result["score_breakdown"]["raw_conviction"] == "DIAMOND"
    assert result["score_breakdown"]["final_conviction"] == expected_conviction
    assert result["score_breakdown"]["regime_cap"] == expected_conviction


def test_compute_consensus_kr_market_ignores_canslim():
    """KR market uses Piotroski 50% + Minervini 50% only — CANSLIM is excluded."""
    result = compute_consensus(
        market="KR",
        canslim_score=95.0,   # Should be ignored for KR
        piotroski_score=82.0,
        minervini_score=80.0,
        weinstein_stage="2_early",
        technical_composite=75.0,
        regime_state="CONFIRMED_UPTREND",
    )

    # KR: piotroski 50%, minervini 50% of the 80% strategy budget
    # normalized: piotroski=0.40, minervini=0.40
    # consensus = 82*0.40 + 80*0.40 = 32.8 + 32 = 64.8
    # final    = 64.8 + 75*0.20 = 64.8 + 15 = 79.8
    assert result["consensus_composite"] == pytest.approx(64.8, abs=0.01)
    assert result["final_score"] == pytest.approx(79.8, abs=0.01)
    assert result["strategy_pass_count"] == 2
    assert result["conviction_level"] == "PLATINUM"
    # CANSLIM must not appear in weights
    assert "canslim" not in result["score_breakdown"]["strategy_weights"]


def test_compute_consensus_returns_unranked_when_no_strategy_scores_exist():
    result = compute_consensus(
        market="US",
        canslim_score=None,
        piotroski_score=None,
        minervini_score=None,
        technical_composite=92.0,
        regime_state="CONFIRMED_UPTREND",
    )

    assert result["consensus_composite"] is None
    assert result["final_score"] == 0.0
    assert result["strategy_pass_count"] == 0
    assert result["conviction_level"] == "UNRANKED"
    assert result["regime_warning"] is False
    assert result["score_breakdown"]["error"] == "no strategy scores available"


def test_compute_consensus_raises_for_unknown_market():
    with pytest.raises(ValueError, match="Unknown market"):
        compute_consensus(
            market="JP",
            canslim_score=80.0,
        )


# ---------------------------------------------------------------------------
# DB-backed tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_instrument_consensus_uses_latest_regime_on_or_before_score_date(
    db_session,
):
    """score_instrument_consensus picks the regime effective on score_date (not a future one)."""
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
            weinstein_stage="2_early",   # Gate passes → conviction capped by regime only
            dual_mom_score=75.0,          # Stored for history; not used in consensus
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

    # US weights: canslim=90*0.4 + piotroski=85*0.2 + minervini=88*0.2 = 70.6
    # final = 70.6 + 80*0.20 = 86.6
    assert scored["final_score"] == pytest.approx(86.6, abs=0.01)
    assert scored["strategy_pass_count"] == 3

    # 86.6 < 88 → not DIAMOND; 86.6 ≥ 78 and pass_count ≥ 2 → PLATINUM (raw)
    # weinstein_stage="2_early" → gate passes → gated = PLATINUM
    # regime MARKET_IN_CORRECTION → cap SILVER → final = SILVER
    assert scored["conviction_level"] == "SILVER"
    assert scored["regime_warning"] is True
    assert scored["score_breakdown"]["raw_conviction"] == "PLATINUM"
    assert scored["score_breakdown"]["final_conviction"] == "SILVER"
