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
from sqlalchemy import select

from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.market_regime import MarketRegime
from app.models.strategy_score import StrategyScore
from app.services.strategies.consensus import (
    compute_consensus,
    get_latest_regime,
    run_consensus_scoring,
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
        magic_formula_score=90.0,
        weinstein_stage="2_early",
        weinstein_score=82.0,
        technical_composite=85.0,
        regime_state="CONFIRMED_UPTREND",
    )

    # US: canslim 40%, piotroski 30%, magic_formula 30% of the 80% strategy budget
    # normalized weights: canslim=0.32, piotroski=0.24, magic_formula=0.24
    # consensus = 95*0.32 + 92*0.24 + 90*0.24 = 30.4 + 22.08 + 21.6 = 74.08
    # final    = 74.08 + 85*0.20 = 74.08 + 17 = 91.08
    assert result["consensus_composite"] == pytest.approx(74.08, abs=0.01)
    assert result["final_score"] == pytest.approx(91.08, abs=0.01)
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
        magic_formula_score=80.0,
        weinstein_stage="2_mid",
        weinstein_score=75.0,
        technical_composite=75.0,
        regime_state="CONFIRMED_UPTREND",
    )

    # consensus = 85*0.32 + 82*0.24 + 80*0.24 = 27.2 + 19.68 + 19.2 = 66.08
    # final    = 66.08 + 75*0.20 = 66.08 + 15 = 81.08
    assert result["final_score"] == pytest.approx(81.08, abs=0.01)
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
        magic_formula_score=60.0,
        technical_composite=None,
        regime_state="CONFIRMED_UPTREND",
    )

    # available: canslim=80, magic_formula=60 (piotroski missing)
    # raw weights: canslim=0.40, magic_formula=0.30 → total=0.70
    # normalized (no technical, strategy_budget=1.0): canslim=0.5714, magic_formula=0.4286
    # consensus = 80*0.5714 + 60*0.4286 ≈ 71.43
    # pass_count = 1 (canslim ≥ 70; magic_formula 60 < 70)
    # GOLD requires pass_count ≥ 2 → falls to SILVER (≥ 50 and pass_count ≥ 1)
    assert result["consensus_composite"] == pytest.approx(71.43, abs=0.01)
    assert result["final_score"] == pytest.approx(71.43, abs=0.01)
    assert result["strategy_pass_count"] == 1
    assert result["conviction_level"] == "SILVER"
    assert result["score_breakdown"]["strategy_weights"] == {
        "canslim": 0.5714,
        "magic_formula": 0.4286,
    }


def test_compute_consensus_weinstein_gate_caps_non_stage2_at_silver():
    """Diamond-worthy scores in Weinstein Stage 1 are capped to SILVER."""
    result = compute_consensus(
        market="US",
        canslim_score=95.0,
        piotroski_score=92.0,
        magic_formula_score=90.0,
        weinstein_stage="1",          # Stage 1 — not a Stage 2 variant
        weinstein_score=40.0,
        technical_composite=85.0,
        regime_state="CONFIRMED_UPTREND",
    )

    # Same numeric scores as the DIAMOND test → raw conviction = DIAMOND
    assert result["final_score"] == pytest.approx(91.08, abs=0.01)
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
        magic_formula_score=90.0,
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
        magic_formula_score=90.0,
        weinstein_stage="2_early",
        weinstein_score=82.0,
        technical_composite=85.0,
        regime_state=regime_state,
    )

    assert result["final_score"] == pytest.approx(91.08, abs=0.01)
    assert result["strategy_pass_count"] == 3
    assert result["conviction_level"] == expected_conviction
    assert result["regime_warning"] is True
    assert result["score_breakdown"]["raw_conviction"] == "DIAMOND"
    assert result["score_breakdown"]["final_conviction"] == expected_conviction
    assert result["score_breakdown"]["regime_cap"] == expected_conviction


def test_compute_consensus_kr_market_uses_canslim_piotroski_magic_formula():
    """KR uses the same canslim/piotroski/magic_formula weights as US."""
    result = compute_consensus(
        market="KR",
        canslim_score=95.0,
        piotroski_score=82.0,
        magic_formula_score=80.0,
        weinstein_stage="2_early",
        technical_composite=75.0,
        regime_state="CONFIRMED_UPTREND",
    )

    # KR: canslim 40%, piotroski 30%, magic_formula 30% of the 80% strategy budget
    # normalized: canslim=0.32, piotroski=0.24, magic_formula=0.24
    # consensus = 95*0.32 + 82*0.24 + 80*0.24 = 30.4 + 19.68 + 19.2 = 69.28
    # final    = 69.28 + 75*0.20 = 69.28 + 15 = 84.28
    assert result["consensus_composite"] == pytest.approx(69.28, abs=0.01)
    assert result["final_score"] == pytest.approx(84.28, abs=0.01)
    assert result["strategy_pass_count"] == 3
    assert result["conviction_level"] == "PLATINUM"
    # All three strategies must appear in weights
    assert set(result["score_breakdown"]["strategy_weights"].keys()) == {
        "canslim", "piotroski", "magic_formula"
    }


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
            magic_formula_score=88.0,
            minervini_score=88.0,         # legacy column; not used in consensus weighting
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

    # US weights (canslim 0.40, piotroski 0.30, magic_formula 0.30) * strategy_budget 0.80:
    # consensus = 90*0.32 + 85*0.24 + 88*0.24 = 28.8 + 20.4 + 21.12 = 70.32
    # final = 70.32 + 80*0.20 = 86.32
    assert scored["final_score"] == pytest.approx(86.32, abs=0.01)
    assert scored["strategy_pass_count"] == 3

    # 86.32 < 88 → not DIAMOND; 86.32 ≥ 78 and pass_count ≥ 2 → PLATINUM (raw)
    # weinstein_stage="2_early" → gate passes → gated = PLATINUM
    # regime MARKET_IN_CORRECTION → cap SILVER → final = SILVER
    assert scored["conviction_level"] == "SILVER"
    assert scored["regime_warning"] is True
    assert scored["score_breakdown"]["raw_conviction"] == "PLATINUM"
    assert scored["score_breakdown"]["final_conviction"] == "SILVER"
    assert set(scored["score_breakdown"]["strategy_weights"]) == {
        "canslim",
        "piotroski",
        "magic_formula",
    }
    assert "dual_mom" not in scored["score_breakdown"]["strategy_weights"]


@pytest.mark.asyncio
async def test_run_consensus_scoring_persists_magic_formula_score(db_session, monkeypatch):
    class _SessionContext:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "app.services.strategies.consensus.AsyncSessionLocal",
        lambda: _SessionContext(),
    )

    instrument = Instrument(
        ticker="MFIX",
        name="Magic Fix Co",
        market="US",
        exchange="NYSE",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    score_date = date(2026, 5, 5)
    db_session.add(
        StrategyScore(
            instrument_id=instrument.id,
            score_date=score_date,
            canslim_score=82.0,
            piotroski_score=75.0,
            magic_formula_score=91.0,
            minervini_score=88.0,
            weinstein_score=80.0,
            weinstein_stage="2_mid",
            technical_composite=78.0,
        )
    )
    db_session.add(
        MarketRegime(
            market="US",
            effective_date=score_date,
            state="CONFIRMED_UPTREND",
            prior_state="UPTREND_UNDER_PRESSURE",
            trigger_reason="Test regime",
            distribution_day_count=1,
            follow_through_day=True,
        )
    )
    await db_session.commit()

    results = await run_consensus_scoring(
        score_date=score_date,
        market="US",
        instrument_ids=[instrument.id],
    )

    assert len(results) == 1
    row = (
        await db_session.execute(
            select(ConsensusScore).where(
                ConsensusScore.instrument_id == instrument.id,
                ConsensusScore.score_date == score_date,
            )
        )
    ).scalar_one()
    assert float(row.magic_formula_score) == pytest.approx(91.0)
