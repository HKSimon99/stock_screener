"""
Snapshot Generation — Phase 4.4
=================================
Freezes the consensus rankings for a given (date, market, asset_type) into
an immutable ``scoring_snapshots`` record.

The ``rankings_json`` JSONB column contains the full ranked list so the
API can serve it without re-computing scores at request time.

A ``config_hash`` is embedded in ``metadata_`` to detect when the scoring
configuration changes (weights, thresholds, model version).

Usage:
    python -m app.services.strategies.snapshot_generator [--market US|KR]
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import date
from typing import Optional

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.snapshot import ScoringSnapshot
from app.services.universe import RANK_MODEL_VERSION

logger = logging.getLogger(__name__)

# Increment when scoring logic/weights change to invalidate stale snapshots
SCORE_VERSION = 1


def _build_config_hash() -> str:
    """Stable hash of the current scoring configuration."""
    from app.services.strategies.consensus import (
        STRATEGY_WEIGHTS, TECHNICAL_WEIGHT, STRATEGY_PASS_THRESHOLD,
        CONVICTION_THRESHOLDS,
    )
    config = {
        "strategy_weights":     STRATEGY_WEIGHTS,
        "technical_weight":     TECHNICAL_WEIGHT,
        "pass_threshold":       STRATEGY_PASS_THRESHOLD,
        "conviction_thresholds": [(t, p, l) for t, p, l in CONVICTION_THRESHOLDS],
        "score_version":        SCORE_VERSION,
    }
    payload = json.dumps(config, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _build_ranking_entry(
    cs: ConsensusScore,
    ticker: str,
    name: str,
    exchange: str,
    asset_type: str,
) -> dict:
    """Build the per-instrument dict stored inside ``rankings_json``."""
    bd = cs.score_breakdown or {}
    strat = bd.get("strategy_scores", {})
    return {
        "rank":               None,          # Filled in after sort
        "instrument_id":      cs.instrument_id,
        "ticker":             ticker,
        "name":               name,
        "exchange":           exchange,
        "asset_type":         asset_type,
        "conviction_level":   cs.conviction_level,
        "final_score":        float(cs.final_score) if cs.final_score else 0.0,
        "consensus_composite": float(cs.consensus_composite) if cs.consensus_composite else 0.0,
        "technical_composite": float(cs.technical_composite) if cs.technical_composite else 0.0,
        "strategy_pass_count": cs.strategy_pass_count or 0,
        "scores": {
            "canslim":   float(cs.canslim_score)   if cs.canslim_score   else None,
            "piotroski": float(cs.piotroski_score) if cs.piotroski_score else None,
            "minervini": float(cs.minervini_score) if cs.minervini_score else None,
            "weinstein": float(cs.weinstein_score) if cs.weinstein_score else None,
            "dual_mom":  float(cs.dual_mom_score)  if cs.dual_mom_score  else None,
        },
        "regime_warning":  cs.regime_warning,
        "coverage_state":  "ranked",
        "rank_model_version": RANK_MODEL_VERSION,
        "score_date":      cs.score_date.isoformat(),
    }


async def generate_snapshot(
    snapshot_date: Optional[date] = None,
    market: str = "US",
    asset_type: str = "stock",
) -> Optional[dict]:
    """
    Build and upsert a ScoringSnapshot for the given parameters.

    Returns the full snapshot dict (including ``rankings_json``), or None
    if no consensus scores exist for this date/market.
    """
    if snapshot_date is None:
        snapshot_date = date.today()

    async with AsyncSessionLocal() as db:
        payload = await build_snapshot_payload(
            db,
            snapshot_date=snapshot_date,
            market=market,
            asset_type=asset_type,
        )
        if payload is None:
            return None

        rankings = payload["rankings_json"]
        metadata = payload["metadata"]
        regime_state = payload["regime_state"]

        # Upsert (update if same date+market+asset_type already exists)
        existing_q = await db.execute(
            select(ScoringSnapshot).where(
                ScoringSnapshot.snapshot_date == snapshot_date,
                ScoringSnapshot.market == market,
                ScoringSnapshot.asset_type == asset_type,
            )
        )
        existing = existing_q.scalars().first()

        if existing:
            existing.rankings_json = rankings
            existing.metadata_ = metadata
            existing.regime_state = regime_state
            logger.info(
                "Updated snapshot %s/%s/%s: %d instruments, config_hash=%s",
                snapshot_date, market, asset_type, len(rankings), metadata["config_hash"],
            )
        else:
            db.add(ScoringSnapshot(
                snapshot_date = snapshot_date,
                market        = market,
                asset_type    = asset_type,
                regime_state  = regime_state,
                rankings_json = rankings,
                metadata_     = metadata,
            ))
            logger.info(
                "Created snapshot %s/%s/%s: %d instruments, config_hash=%s",
                snapshot_date, market, asset_type, len(rankings), metadata["config_hash"],
            )

        await db.commit()

        return {
            "snapshot_date":  snapshot_date.isoformat(),
            "market":         market,
            "asset_type":     asset_type,
            "instruments":    len(rankings),
            "config_hash":    metadata["config_hash"],
            "conviction_distribution": metadata["conviction_distribution"],
            "top_5":          rankings[:5],
        }


async def build_snapshot_payload(
    db,
    snapshot_date: Optional[date] = None,
    market: str = "US",
    asset_type: str = "stock",
) -> Optional[dict]:
    """Build the deterministic snapshot payload without persisting it."""
    if snapshot_date is None:
        snapshot_date = date.today()

    q = await db.execute(
        select(
            ConsensusScore,
            Instrument.ticker,
            Instrument.name,
            Instrument.exchange,
            Instrument.asset_type,
        )
        .join(Instrument, ConsensusScore.instrument_id == Instrument.id)
        .where(
            ConsensusScore.score_date == snapshot_date,
            Instrument.market == market,
            Instrument.is_active == True,
            Instrument.asset_type == asset_type,
        )
        .order_by(ConsensusScore.final_score.desc())
    )
    rows = q.all()

    if not rows:
        logger.warning(
            "No consensus scores found for %s %s on %s — snapshot skipped.",
            market, asset_type, snapshot_date,
        )
        return None

    rankings: list[dict] = []
    for rank, (cs, ticker, name, exchange, instrument_asset_type) in enumerate(rows, start=1):
        entry = _build_ranking_entry(cs, ticker, name, exchange, instrument_asset_type)
        entry["rank"] = rank
        rankings.append(entry)

    final_scores = [entry["final_score"] for entry in rankings]
    conviction_dist: dict[str, int] = {}
    for entry in rankings:
        conviction_level = entry["conviction_level"]
        conviction_dist[conviction_level] = conviction_dist.get(conviction_level, 0) + 1

    metadata = {
        "config_hash": _build_config_hash(),
        "score_version": SCORE_VERSION,
        "instruments_count": len(rankings),
        "avg_final_score": round(sum(final_scores) / len(final_scores), 2),
        "min_final_score": round(min(final_scores), 2),
        "max_final_score": round(max(final_scores), 2),
        "conviction_distribution": conviction_dist,
        "regime_warnings": sum(1 for entry in rankings if entry["regime_warning"]),
    }

    return {
        "snapshot_date": snapshot_date,
        "market": market,
        "asset_type": asset_type,
        "rankings_json": rankings,
        "metadata": metadata,
        "regime_state": rows[0][0].regime_state if rows else None,
    }


async def run_snapshot_generation(
    snapshot_date: Optional[date] = None,
    markets: Optional[list[str]] = None,
) -> list[dict]:
    """
    Generate snapshots for all markets (default: US + KR) for a single date.
    """
    if markets is None:
        markets = ["US", "KR"]

    results = []
    for mkt in markets:
        snap = await generate_snapshot(
            snapshot_date=snapshot_date,
            market=mkt,
            asset_type="stock",
        )
        if snap:
            results.append(snap)
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

    markets = [market_arg] if market_arg else ["US", "KR"]

    async def _main():
        results = await run_snapshot_generation(markets=markets)
        for snap in results:
            dist = snap["conviction_distribution"]
            print(
                f"\nSnapshot {snap['snapshot_date']} / {snap['market']} / {snap['asset_type']}"
            )
            print(f"  Instruments : {snap['instruments']}")
            print(f"  Config hash : {snap['config_hash']}")
            print(f"  Conviction  : {dist}")
            print(f"  Top 5:")
            for entry in snap["top_5"]:
                print(
                    f"    #{entry['rank']} [{entry['conviction_level']:<8}]"
                    f"  {entry['ticker']:<8}  final={entry['final_score']:.1f}"
                    f"  passes={entry['strategy_pass_count']}"
                )

    asyncio.run(_main())
