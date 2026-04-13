"""
Consensus Scoring Engine — Phase 4.3
======================================
Aggregates all 5 strategy scores + technical composite into a single
``final_score`` and assigns a conviction level (DIAMOND / GOLD / SILVER /
BRONZE / UNRANKED) with optional regime gating.

Weighting scheme
----------------
Strategy consensus (80% of final_score):
  CANSLIM        20%
  Piotroski      15%
  Minervini      20%
  Weinstein      15%
  Dual Momentum  10%
  ← only strategies with data contribute; weights are renormalized
    when data is missing for some strategies.

Technical composite (20% of final_score):
  technical_composite score from Phase 3.6

Conviction thresholds (applied to ``final_score``)
---------------------------------------------------
  DIAMOND  ≥ 80   AND strategy_pass_count ≥ 4   (0-5 per market, ultra-selective)
  GOLD     ≥ 65   AND strategy_pass_count ≥ 3
  SILVER   ≥ 50   AND strategy_pass_count ≥ 2
  BRONZE   ≥ 35
  UNRANKED < 35

Regime gate
-----------
During MARKET_IN_CORRECTION the max conviction is capped at SILVER.
During UPTREND_UNDER_PRESSURE the max conviction is capped at GOLD.

Usage:
    python -m app.services.strategies.consensus [--market US|KR]
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import date
from typing import Optional

from sqlalchemy import select, desc

from app.core.database import AsyncSessionLocal
from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.market_regime import MarketRegime
from app.models.strategy_score import StrategyScore

logger = logging.getLogger(__name__)

# Strategy weights (must sum to 1.0)
STRATEGY_WEIGHTS: dict[str, float] = {
    "canslim":      0.20,
    "piotroski":    0.15,
    "minervini":    0.20,
    "weinstein":    0.15,
    "dual_mom":     0.10,
}
TECHNICAL_WEIGHT = 0.20  # Of the remaining 20%

# Score threshold to count a strategy as "passing"
STRATEGY_PASS_THRESHOLD = 70.0

# Conviction thresholds: (min_final_score, min_pass_count, label)
CONVICTION_THRESHOLDS = [
    (80.0, 4, "DIAMOND"),
    (65.0, 3, "GOLD"),
    (50.0, 2, "SILVER"),
    (35.0, 0, "BRONZE"),
]

# Regime → max conviction cap
REGIME_CAPS: dict[str, str] = {
    "CONFIRMED_UPTREND":         "DIAMOND",   # No cap
    "UPTREND_UNDER_PRESSURE":    "GOLD",
    "MARKET_IN_CORRECTION":      "SILVER",
}

_CONVICTION_ORDER = ["UNRANKED", "BRONZE", "SILVER", "GOLD", "DIAMOND"]


def _cap_conviction(level: str, cap: str) -> str:
    """Return the lower of two conviction levels."""
    idx_level = _CONVICTION_ORDER.index(level) if level in _CONVICTION_ORDER else 0
    idx_cap   = _CONVICTION_ORDER.index(cap)   if cap   in _CONVICTION_ORDER else 4
    return _CONVICTION_ORDER[min(idx_level, idx_cap)]


def _assign_conviction(final_score: float, pass_count: int) -> str:
    for min_score, min_passes, label in CONVICTION_THRESHOLDS:
        if final_score >= min_score and pass_count >= min_passes:
            return label
    return "UNRANKED"


# =============================================================================
# Pure Aggregation (no DB)
# =============================================================================

def compute_consensus(
    canslim_score:      Optional[float],
    piotroski_score:    Optional[float],
    minervini_score:    Optional[float],
    weinstein_score:    Optional[float],
    dual_mom_score:     Optional[float],
    technical_composite: Optional[float],
    regime_state:       Optional[str] = "CONFIRMED_UPTREND",
) -> dict:
    """
    Compute consensus composite, conviction level, and full score breakdown.

    All score inputs are 0-100.  Missing (None) strategy scores are excluded
    and the remaining weights are renormalized so they still sum to 1.

    Returns a dict matching ConsensusScore columns plus a ``score_breakdown``
    sub-dict for audit purposes.
    """
    raw_scores: dict[str, Optional[float]] = {
        "canslim":   canslim_score,
        "piotroski": piotroski_score,
        "minervini": minervini_score,
        "weinstein": weinstein_score,
        "dual_mom":  dual_mom_score,
    }

    # Filter to strategies with data
    available = {k: v for k, v in raw_scores.items() if v is not None}

    if not available:
        return {
            "consensus_composite":  None,
            "final_score":          0.0,
            "strategy_pass_count":  0,
            "conviction_level":     "UNRANKED",
            "regime_state":         regime_state,
            "regime_warning":       False,
            "score_breakdown":      {"error": "no strategy scores available"},
        }

    # Renormalize weights for available strategies
    total_raw_weight = sum(STRATEGY_WEIGHTS[k] for k in available)
    # Split total weight budget: 80% strat + 20% tech; but tech is optional too
    strat_budget = 1.0 - TECHNICAL_WEIGHT if technical_composite is not None else 1.0

    normalized_weights: dict[str, float] = {}
    for k in available:
        normalized_weights[k] = (STRATEGY_WEIGHTS[k] / total_raw_weight) * strat_budget

    # Weighted consensus composite (strategy component only)
    consensus_composite = sum(
        available[k] * normalized_weights[k] for k in available
    )

    # Add technical composite (if available)
    if technical_composite is not None:
        final_score = consensus_composite + technical_composite * TECHNICAL_WEIGHT
    else:
        final_score = consensus_composite

    final_score = min(100.0, max(0.0, final_score))
    consensus_composite = min(100.0, max(0.0, consensus_composite))

    # Count strategies scoring ≥ pass threshold
    pass_count = sum(
        1 for v in available.values() if v >= STRATEGY_PASS_THRESHOLD
    )

    # Assign raw conviction
    conviction = _assign_conviction(final_score, pass_count)

    # Apply regime cap
    regime = regime_state or "CONFIRMED_UPTREND"
    cap = REGIME_CAPS.get(regime, "DIAMOND")
    capped_conviction = _cap_conviction(conviction, cap)
    regime_warning = capped_conviction != conviction

    breakdown: dict = {
        "strategy_scores":    {k: round(v, 2) for k, v in available.items()},
        "strategy_weights":   {k: round(w, 4) for k, w in normalized_weights.items()},
        "consensus_composite": round(consensus_composite, 2),
        "technical_composite": round(technical_composite, 2) if technical_composite else None,
        "technical_weight":   TECHNICAL_WEIGHT if technical_composite is not None else 0,
        "final_score":        round(final_score, 2),
        "pass_count":         pass_count,
        "pass_threshold":     STRATEGY_PASS_THRESHOLD,
        "raw_conviction":     conviction,
        "regime_state":       regime,
        "regime_cap":         cap,
        "final_conviction":   capped_conviction,
        "regime_warning":     regime_warning,
    }

    return {
        "consensus_composite":  round(consensus_composite, 2),
        "final_score":          round(final_score, 2),
        "strategy_pass_count":  pass_count,
        "conviction_level":     capped_conviction,
        "regime_state":         regime,
        "regime_warning":       regime_warning,
        "score_breakdown":      breakdown,
    }


# =============================================================================
# Regime Helper
# =============================================================================

async def get_latest_regime(market: str, score_date: date, db) -> Optional[str]:
    """Return the most recent market regime state for ``market`` on or before ``score_date``."""
    q = await db.execute(
        select(MarketRegime.state)
        .where(
            MarketRegime.market == market,
            MarketRegime.effective_date <= score_date,
        )
        .order_by(desc(MarketRegime.effective_date))
        .limit(1)
    )
    row = q.scalar_one_or_none()
    return row  # May be None if no regime row exists yet


# =============================================================================
# DB-Backed Per-Instrument Scorer
# =============================================================================

async def score_instrument_consensus(
    instrument_id: int,
    market: str,
    score_date: date,
    db,
    regime_state: Optional[str] = None,
) -> Optional[dict]:
    """
    Read strategy_scores for ``instrument_id`` on ``score_date`` and compute
    consensus.  Returns a dict of ConsensusScore fields, or None if no data.
    """
    q = await db.execute(
        select(StrategyScore).where(
            StrategyScore.instrument_id == instrument_id,
            StrategyScore.score_date == score_date,
        )
    )
    ss = q.scalars().first()
    if ss is None:
        return None

    def _f(val) -> Optional[float]:
        return float(val) if val is not None else None

    result = compute_consensus(
        canslim_score      = _f(ss.canslim_score),
        piotroski_score    = _f(ss.piotroski_score),
        minervini_score    = _f(ss.minervini_score),
        weinstein_score    = _f(ss.weinstein_score),
        dual_mom_score     = _f(ss.dual_mom_score),
        technical_composite= _f(ss.technical_composite),
        regime_state       = regime_state,
    )

    return {
        "instrument_id":     instrument_id,
        "score_date":        score_date,
        # Pull through individual strategy scores for the consensus row
        "canslim_score":     _f(ss.canslim_score),
        "piotroski_score":   _f(ss.piotroski_score),
        "minervini_score":   _f(ss.minervini_score),
        "weinstein_score":   _f(ss.weinstein_score),
        "dual_mom_score":    _f(ss.dual_mom_score),
        "technical_composite": _f(ss.technical_composite),
        **result,
    }


# =============================================================================
# Batch Runner
# =============================================================================

async def run_consensus_scoring(
    score_date: Optional[date] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> list[dict]:
    """
    Compute and upsert ConsensusScore rows for a batch of instruments.

    Reads from strategy_scores (which must already be populated for score_date).
    Fetches the current market regime once per market and applies it to all
    instruments in that market.
    """
    if score_date is None:
        score_date = date.today()

    async with AsyncSessionLocal() as db:
        # Fetch instruments
        stmt = (
            select(Instrument.id, Instrument.market)
            .where(Instrument.is_active == True)
        )
        if market:
            stmt = stmt.where(Instrument.market == market)
        if instrument_ids:
            stmt = stmt.where(Instrument.id.in_(instrument_ids))
        result = await db.execute(stmt)
        instrument_rows = result.all()

        # Group by market for regime lookup
        markets_needed: set[str] = {r[1] for r in instrument_rows}
        regime_by_market: dict[str, Optional[str]] = {}
        for mkt in markets_needed:
            regime_by_market[mkt] = await get_latest_regime(mkt, score_date, db)

        logger.info(
            "Consensus scoring %d instruments for %s. Regimes: %s",
            len(instrument_rows), score_date, regime_by_market,
        )

        results: list[dict] = []
        conviction_counts: dict[str, int] = {
            "DIAMOND": 0, "GOLD": 0, "SILVER": 0, "BRONZE": 0, "UNRANKED": 0
        }

        for inst_id, inst_market in instrument_rows:
            try:
                regime = regime_by_market.get(inst_market, "CONFIRMED_UPTREND")
                scored = await score_instrument_consensus(
                    inst_id, inst_market, score_date, db, regime_state=regime
                )
                if scored is None:
                    continue

                # Upsert into consensus_scores
                existing_q = await db.execute(
                    select(ConsensusScore).where(
                        ConsensusScore.instrument_id == inst_id,
                        ConsensusScore.score_date == score_date,
                    )
                )
                existing = existing_q.scalars().first()

                if existing:
                    existing.canslim_score        = scored["canslim_score"]
                    existing.piotroski_score       = scored["piotroski_score"]
                    existing.minervini_score       = scored["minervini_score"]
                    existing.weinstein_score       = scored["weinstein_score"]
                    existing.dual_mom_score        = scored["dual_mom_score"]
                    existing.technical_composite   = scored["technical_composite"]
                    existing.strategy_pass_count   = scored["strategy_pass_count"]
                    existing.consensus_composite   = scored["consensus_composite"]
                    existing.final_score           = scored["final_score"]
                    existing.conviction_level      = scored["conviction_level"]
                    existing.regime_state          = scored["regime_state"]
                    existing.regime_warning        = scored["regime_warning"]
                    existing.score_breakdown       = scored["score_breakdown"]
                else:
                    db.add(ConsensusScore(
                        instrument_id    = inst_id,
                        score_date       = score_date,
                        canslim_score    = scored["canslim_score"],
                        piotroski_score  = scored["piotroski_score"],
                        minervini_score  = scored["minervini_score"],
                        weinstein_score  = scored["weinstein_score"],
                        dual_mom_score   = scored["dual_mom_score"],
                        technical_composite = scored["technical_composite"],
                        strategy_pass_count = scored["strategy_pass_count"],
                        consensus_composite = scored["consensus_composite"],
                        final_score      = scored["final_score"],
                        conviction_level = scored["conviction_level"],
                        regime_state     = scored["regime_state"],
                        regime_warning   = scored["regime_warning"],
                        score_breakdown  = scored["score_breakdown"],
                    ))

                results.append(scored)
                conviction_counts[scored["conviction_level"]] += 1

            except Exception as exc:
                logger.error(
                    "Consensus scoring failed for instrument %s: %s", inst_id, exc
                )

        await db.commit()
        logger.info(
            "Consensus complete: %d scored. Distribution: %s",
            len(results), conviction_counts,
        )

    return results


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    market_arg = None
    for arg in sys.argv[1:]:
        if arg.startswith("--market="):
            market_arg = arg.split("=")[1]
        elif arg in ("US", "KR"):
            market_arg = arg

    async def _main():
        results = await run_consensus_scoring(market=market_arg)
        if not results:
            print("No results scored.")
            return

        # Conviction breakdown
        counts: dict[str, int] = {
            "DIAMOND": 0, "GOLD": 0, "SILVER": 0, "BRONZE": 0, "UNRANKED": 0
        }
        for r in results:
            counts[r["conviction_level"]] += 1

        scores = [r["final_score"] for r in results]
        print(f"\nScored {len(results)} instruments")
        print(f"  Min final_score: {min(scores):.1f}")
        print(f"  Max final_score: {max(scores):.1f}")
        print(f"  Avg final_score: {sum(scores)/len(scores):.1f}")
        print("\nConviction distribution:")
        for level in ["DIAMOND", "GOLD", "SILVER", "BRONZE", "UNRANKED"]:
            n = counts[level]
            bar = "#" * n
            print(f"  {level:<8}  {n:>3}  {bar}")

        print("\nTop 10 by final_score:")
        top = sorted(results, key=lambda r: r["final_score"], reverse=True)[:10]
        for r in top:
            bd = r["score_breakdown"]
            cs = bd["strategy_scores"]
            print(
                f"  [{r['conviction_level']:<8}] instr={r['instrument_id']:>5}  "
                f"final={r['final_score']:.1f}  "
                f"C={cs.get('canslim',0):.0f} P={cs.get('piotroski',0):.0f} "
                f"M={cs.get('minervini',0):.0f} W={cs.get('weinstein',0):.0f} "
                f"D={cs.get('dual_mom',0):.0f}  "
                f"tech={r['technical_composite'] or 0:.0f}"
            )

    asyncio.run(_main())
