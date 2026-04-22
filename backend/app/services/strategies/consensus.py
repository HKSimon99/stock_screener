"""
Consensus Scoring Engine
========================
Aggregates strategy scores into a single ``final_score`` and assigns a
conviction level (DIAMOND / PLATINUM / GOLD / SILVER / BRONZE / UNRANKED)
with regime gating and a Weinstein Stage 2 gate.

Weighting scheme (market-specific)
----------------------------------
US strategy consensus (80% of final_score):
  CANSLIM       50%
  Piotroski     25%
  Minervini     25%

KR strategy consensus (80% of final_score):
  Piotroski     50%
  Minervini     50%

Technical composite contributes the remaining 20% when available.
Weights are renormalized over strategies that actually have data.

Weinstein is **gate-only**: if the instrument is not in Stage 2
(2_early / 2_mid / 2_late) the final conviction is capped at SILVER.
Dual Momentum has been removed.

Conviction thresholds (applied to ``final_score``)
---------------------------------------------------
  DIAMOND  ≥ 88   AND strategy_pass_count ≥ 3
  PLATINUM ≥ 78   AND strategy_pass_count ≥ 2
  GOLD     ≥ 65   AND strategy_pass_count ≥ 2
  SILVER   ≥ 50   AND strategy_pass_count ≥ 1
  BRONZE   ≥ 35
  UNRANKED < 35

Regime cap
----------
  CONFIRMED_UPTREND       → DIAMOND (no cap)
  UPTREND_UNDER_PRESSURE  → PLATINUM
  MARKET_IN_CORRECTION    → SILVER

Usage:
    python -m app.services.strategies.consensus [--market US|KR]
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Optional

from sqlalchemy import select, desc

from app.core.database import AsyncSessionLocal
from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.market_regime import MarketRegime
from app.models.strategy_score import StrategyScore
from app.services.universe import refresh_instrument_coverage_summary

logger = logging.getLogger(__name__)

# Market-specific strategy weights (each market's dict sums to 1.0)
STRATEGY_WEIGHTS: dict[str, dict[str, float]] = {
    "US": {"canslim": 0.50, "piotroski": 0.25, "minervini": 0.25},
    "KR": {"piotroski": 0.50, "minervini": 0.50},
}

# Strategy consensus gets 80%, technical composite 20% (if both present).
TECHNICAL_WEIGHT = 0.20

# Score at which a strategy is considered "passing" for pass-count counting.
STRATEGY_PASS_THRESHOLD = 70.0

# Conviction tiers: (min_final_score, min_pass_count, label). Ordered high→low.
CONVICTION_THRESHOLDS: list[tuple[float, int, str]] = [
    (88.0, 3, "DIAMOND"),
    (78.0, 2, "PLATINUM"),
    (65.0, 2, "GOLD"),
    (50.0, 1, "SILVER"),
    (35.0, 0, "BRONZE"),
]

# Regime → max allowed conviction.
REGIME_CAPS: dict[str, str] = {
    "CONFIRMED_UPTREND":      "DIAMOND",
    "UPTREND_UNDER_PRESSURE": "PLATINUM",
    "MARKET_IN_CORRECTION":   "SILVER",
}

# Ordered low→high; used by _cap_conviction to compute the minimum of two levels.
_CONVICTION_ORDER = ["UNRANKED", "BRONZE", "SILVER", "GOLD", "PLATINUM", "DIAMOND"]

# Weinstein stages that satisfy the Stage 2 gate.
WEINSTEIN_STAGE_2 = {"2_early", "2_mid", "2_late"}

# Non-Stage-2 instruments cannot exceed this conviction level.
WEINSTEIN_GATE_CAP = "SILVER"


def _cap_conviction(level: str, cap: str) -> str:
    """Return the lower of two conviction levels (by _CONVICTION_ORDER)."""
    idx_level = _CONVICTION_ORDER.index(level) if level in _CONVICTION_ORDER else 0
    idx_cap   = _CONVICTION_ORDER.index(cap)   if cap   in _CONVICTION_ORDER else len(_CONVICTION_ORDER) - 1
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
    *,
    market: str,
    canslim_score:       Optional[float] = None,
    piotroski_score:     Optional[float] = None,
    minervini_score:     Optional[float] = None,
    technical_composite: Optional[float] = None,
    weinstein_stage:     Optional[str]   = None,
    weinstein_score:     Optional[float] = None,   # stored for history, not weighted
    regime_state:        Optional[str]   = "CONFIRMED_UPTREND",
) -> dict:
    """
    Compute consensus composite, conviction level, and full score breakdown.

    Weights are market-specific (``STRATEGY_WEIGHTS[market]``). Missing strategy
    scores are excluded and remaining weights are renormalized. Weinstein does
    not contribute to the weighted score — it is used as a Stage 2 gate.
    """
    if market not in STRATEGY_WEIGHTS:
        raise ValueError(f"Unknown market {market!r}; expected one of {list(STRATEGY_WEIGHTS)}")

    weights_for_market = STRATEGY_WEIGHTS[market]
    raw_scores: dict[str, Optional[float]] = {
        "canslim":   canslim_score,
        "piotroski": piotroski_score,
        "minervini": minervini_score,
    }
    # Restrict to strategies valid for this market AND present.
    available = {
        k: v for k, v in raw_scores.items()
        if k in weights_for_market and v is not None
    }

    if not available:
        return {
            "consensus_composite":  None,
            "final_score":          0.0,
            "strategy_pass_count":  0,
            "conviction_level":     "UNRANKED",
            "regime_state":         regime_state,
            "regime_warning":       False,
            "weinstein_stage":      weinstein_stage,
            "weinstein_gate_pass":  False,
            "score_breakdown":      {"error": "no strategy scores available", "market": market},
        }

    # Renormalize strategy weights over available strategies.
    total_raw_weight = sum(weights_for_market[k] for k in available)
    strat_budget = 1.0 - TECHNICAL_WEIGHT if technical_composite is not None else 1.0

    normalized_weights: dict[str, float] = {
        k: (weights_for_market[k] / total_raw_weight) * strat_budget
        for k in available
    }

    consensus_composite = sum(available[k] * normalized_weights[k] for k in available)

    if technical_composite is not None:
        final_score = consensus_composite + technical_composite * TECHNICAL_WEIGHT
    else:
        final_score = consensus_composite

    final_score = min(100.0, max(0.0, final_score))
    consensus_composite = min(100.0, max(0.0, consensus_composite))

    pass_count = sum(1 for v in available.values() if v >= STRATEGY_PASS_THRESHOLD)

    raw_conviction = _assign_conviction(final_score, pass_count)

    # Weinstein Stage 2 gate: cap non-Stage-2 at SILVER.
    weinstein_gate_pass = weinstein_stage in WEINSTEIN_STAGE_2
    gated_conviction = (
        raw_conviction if weinstein_gate_pass
        else _cap_conviction(raw_conviction, WEINSTEIN_GATE_CAP)
    )

    # Regime cap.
    regime = regime_state or "CONFIRMED_UPTREND"
    regime_cap = REGIME_CAPS.get(regime, "DIAMOND")
    capped_conviction = _cap_conviction(gated_conviction, regime_cap)

    regime_warning = capped_conviction != gated_conviction
    weinstein_warning = gated_conviction != raw_conviction

    breakdown: dict = {
        "market":              market,
        "strategy_scores":     {k: round(v, 2) for k, v in available.items()},
        "strategy_weights":    {k: round(w, 4) for k, w in normalized_weights.items()},
        "consensus_composite": round(consensus_composite, 2),
        "technical_composite": round(technical_composite, 2) if technical_composite is not None else None,
        "technical_weight":    TECHNICAL_WEIGHT if technical_composite is not None else 0,
        "final_score":         round(final_score, 2),
        "pass_count":          pass_count,
        "pass_threshold":      STRATEGY_PASS_THRESHOLD,
        "raw_conviction":      raw_conviction,
        "weinstein_stage":     weinstein_stage,
        "weinstein_score":     round(weinstein_score, 2) if weinstein_score is not None else None,
        "weinstein_gate_pass": weinstein_gate_pass,
        "weinstein_warning":   weinstein_warning,
        "gated_conviction":    gated_conviction,
        "regime_state":        regime,
        "regime_cap":          regime_cap,
        "regime_warning":      regime_warning,
        "final_conviction":    capped_conviction,
    }

    return {
        "consensus_composite": round(consensus_composite, 2),
        "final_score":         round(final_score, 2),
        "strategy_pass_count": pass_count,
        "conviction_level":    capped_conviction,
        "regime_state":        regime,
        "regime_warning":      regime_warning,
        "weinstein_stage":     weinstein_stage,
        "weinstein_gate_pass": weinstein_gate_pass,
        "score_breakdown":     breakdown,
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
    return q.scalar_one_or_none()


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
    consensus. Returns a dict of ConsensusScore fields, or None if no data.
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
        market              = market,
        canslim_score       = _f(ss.canslim_score),
        piotroski_score     = _f(ss.piotroski_score),
        minervini_score     = _f(ss.minervini_score),
        technical_composite = _f(ss.technical_composite),
        weinstein_stage     = ss.weinstein_stage,
        weinstein_score     = _f(ss.weinstein_score),
        regime_state        = regime_state,
    )

    return {
        "instrument_id":       instrument_id,
        "score_date":          score_date,
        "canslim_score":       _f(ss.canslim_score),
        "piotroski_score":     _f(ss.piotroski_score),
        "minervini_score":     _f(ss.minervini_score),
        "weinstein_score":     _f(ss.weinstein_score),
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
    """
    if score_date is None:
        score_date = date.today()

    async with AsyncSessionLocal() as db:
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

        markets_needed: set[str] = {r[1] for r in instrument_rows}
        regime_by_market: dict[str, Optional[str]] = {
            mkt: await get_latest_regime(mkt, score_date, db) for mkt in markets_needed
        }

        logger.info(
            "Consensus scoring %d instruments for %s. Regimes: %s",
            len(instrument_rows), score_date, regime_by_market,
        )

        results: list[dict] = []
        conviction_counts: dict[str, int] = {
            "DIAMOND": 0, "PLATINUM": 0, "GOLD": 0, "SILVER": 0, "BRONZE": 0, "UNRANKED": 0,
        }

        for inst_id, inst_market in instrument_rows:
            try:
                regime = regime_by_market.get(inst_market, "CONFIRMED_UPTREND")
                scored = await score_instrument_consensus(
                    inst_id, inst_market, score_date, db, regime_state=regime
                )
                if scored is None:
                    continue

                existing_q = await db.execute(
                    select(ConsensusScore).where(
                        ConsensusScore.instrument_id == inst_id,
                        ConsensusScore.score_date == score_date,
                    )
                )
                existing = existing_q.scalars().first()

                if existing:
                    existing.canslim_score       = scored["canslim_score"]
                    existing.piotroski_score     = scored["piotroski_score"]
                    existing.minervini_score     = scored["minervini_score"]
                    existing.weinstein_score     = scored["weinstein_score"]
                    existing.technical_composite = scored["technical_composite"]
                    existing.strategy_pass_count = scored["strategy_pass_count"]
                    existing.consensus_composite = scored["consensus_composite"]
                    existing.final_score         = scored["final_score"]
                    existing.conviction_level    = scored["conviction_level"]
                    existing.regime_state        = scored["regime_state"]
                    existing.regime_warning      = scored["regime_warning"]
                    existing.score_breakdown     = scored["score_breakdown"]
                else:
                    db.add(ConsensusScore(
                        instrument_id       = inst_id,
                        score_date          = score_date,
                        canslim_score       = scored["canslim_score"],
                        piotroski_score     = scored["piotroski_score"],
                        minervini_score     = scored["minervini_score"],
                        weinstein_score     = scored["weinstein_score"],
                        technical_composite = scored["technical_composite"],
                        strategy_pass_count = scored["strategy_pass_count"],
                        consensus_composite = scored["consensus_composite"],
                        final_score         = scored["final_score"],
                        conviction_level    = scored["conviction_level"],
                        regime_state        = scored["regime_state"],
                        regime_warning      = scored["regime_warning"],
                        score_breakdown     = scored["score_breakdown"],
                    ))

                results.append(scored)
                conviction_counts[scored["conviction_level"]] += 1

            except Exception as exc:
                logger.error(
                    "Consensus scoring failed for instrument %s: %s", inst_id, exc
                )

        await db.commit()
        if results:
            await refresh_instrument_coverage_summary(
                db,
                instrument_ids=[row["instrument_id"] for row in results],
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

        counts: dict[str, int] = {
            "DIAMOND": 0, "PLATINUM": 0, "GOLD": 0, "SILVER": 0, "BRONZE": 0, "UNRANKED": 0,
        }
        for r in results:
            counts[r["conviction_level"]] += 1

        scores = [r["final_score"] for r in results]
        print(f"\nScored {len(results)} instruments")
        print(f"  Min final_score: {min(scores):.1f}")
        print(f"  Max final_score: {max(scores):.1f}")
        print(f"  Avg final_score: {sum(scores)/len(scores):.1f}")
        print("\nConviction distribution:")
        for level in ["DIAMOND", "PLATINUM", "GOLD", "SILVER", "BRONZE", "UNRANKED"]:
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
                f"M={cs.get('minervini',0):.0f}  "
                f"W-stage={bd.get('weinstein_stage')}  "
                f"tech={r['technical_composite'] or 0:.0f}"
            )

    asyncio.run(_main())
