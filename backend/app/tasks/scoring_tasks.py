from __future__ import annotations

import asyncio
from datetime import date
from typing import Optional

from app.tasks.celery_app import celery_app
from app.services.strategies.canslim.engine import run_canslim_scoring
from app.services.strategies.piotroski.engine import run_piotroski_scoring
from app.services.strategies.backtest_validation import run_backtest, run_consensus_backtest


def _parse_score_date(score_date: Optional[str]) -> Optional[date]:
    if not score_date:
        return None
    return date.fromisoformat(score_date)


async def run_phase2_scoring_pipeline(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    parsed_date = _parse_score_date(score_date)

    canslim_results = await run_canslim_scoring(
        score_date=parsed_date,
        market=market,
        instrument_ids=instrument_ids,
    )
    piotroski_results = await run_piotroski_scoring(
        score_date=parsed_date,
        market=market,
        instrument_ids=instrument_ids,
    )

    scored_ids = sorted(
        {
            *(row["instrument_id"] for row in canslim_results),
            *(row["instrument_id"] for row in piotroski_results),
        }
    )

    return {
        "score_date": (parsed_date or date.today()).isoformat(),
        "market": market,
        "instrument_ids": instrument_ids,
        "canslim_scored": len(canslim_results),
        "piotroski_scored": len(piotroski_results),
        "unique_instruments_scored": len(scored_ids),
        "scored_instrument_ids": scored_ids,
    }


async def run_full_scoring_pipeline(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    """
    Full scoring pipeline: Phase 2 strategies → Phase 3 technical →
    Phase 4 consensus + snapshot generation.
    """
    from app.services.strategies.minervini.engine import run_minervini_scoring
    from app.services.strategies.weinstein.engine import run_weinstein_scoring
    from app.services.strategies.dual_momentum.engine import run_dual_momentum_scoring
    from app.services.technical.advanced_indicators import run_technical_indicator_scoring
    from app.services.technical.pattern_detector import run_pattern_detection
    from app.services.technical.multi_timeframe import run_technical_composite_scoring
    from app.services.strategies.consensus import run_consensus_scoring
    from app.services.strategies.snapshot_generator import run_snapshot_generation

    parsed_date = _parse_score_date(score_date)

    canslim_results = await run_canslim_scoring(
        score_date=parsed_date, market=market, instrument_ids=instrument_ids
    )
    piotroski_results = await run_piotroski_scoring(
        score_date=parsed_date, market=market, instrument_ids=instrument_ids
    )
    minervini_results = await run_minervini_scoring(
        score_date=parsed_date, market=market, instrument_ids=instrument_ids
    )
    weinstein_results = await run_weinstein_scoring(
        score_date=parsed_date, market=market, instrument_ids=instrument_ids
    )
    dual_mom_results = await run_dual_momentum_scoring(
        score_date=parsed_date, market=market, instrument_ids=instrument_ids
    )
    tech_results = await run_technical_indicator_scoring(
        score_date=parsed_date, market=market, instrument_ids=instrument_ids
    )
    pattern_results = await run_pattern_detection(
        score_date=parsed_date, market=market, instrument_ids=instrument_ids
    )
    # Composite must run after all other strategy_scores writes
    composite_results = await run_technical_composite_scoring(
        score_date=parsed_date, market=market, instrument_ids=instrument_ids
    )
    # Consensus reads strategy_scores + technical_composite
    consensus_results = await run_consensus_scoring(
        score_date=parsed_date, market=market, instrument_ids=instrument_ids
    )
    # Snapshot freezes consensus into an immutable rankings record
    markets_to_snap = [market] if market else ["US", "KR"]
    snapshots = await run_snapshot_generation(
        snapshot_date=parsed_date, markets=markets_to_snap
    )

    all_ids = sorted({
        *(r["instrument_id"] for r in canslim_results),
        *(r["instrument_id"] for r in piotroski_results),
        *(r["instrument_id"] for r in minervini_results),
        *(r["instrument_id"] for r in weinstein_results),
        *(r["instrument_id"] for r in dual_mom_results),
        *(r["instrument_id"] for r in tech_results),
        *(r["instrument_id"] for r in pattern_results),
        *(r["instrument_id"] for r in composite_results),
        *(r["instrument_id"] for r in consensus_results),
    })

    patterns_with_hits = sum(1 for r in pattern_results if r["pattern_count"] > 0)
    avg_composite = (
        sum(r["technical_composite"] for r in composite_results) / len(composite_results)
        if composite_results else 0.0
    )
    conviction_dist = {}
    for r in consensus_results:
        lv = r["conviction_level"]
        conviction_dist[lv] = conviction_dist.get(lv, 0) + 1

    return {
        "score_date":               (parsed_date or date.today()).isoformat(),
        "market":                   market,
        "canslim_scored":           len(canslim_results),
        "piotroski_scored":         len(piotroski_results),
        "minervini_scored":         len(minervini_results),
        "weinstein_scored":         len(weinstein_results),
        "dual_momentum_scored":     len(dual_mom_results),
        "technical_scored":         len(tech_results),
        "patterns_scanned":         len(pattern_results),
        "patterns_with_detections": patterns_with_hits,
        "composite_scored":         len(composite_results),
        "avg_technical_composite":  round(avg_composite, 1),
        "consensus_scored":         len(consensus_results),
        "conviction_distribution":  conviction_dist,
        "snapshots_generated":      len(snapshots),
        "unique_instruments_scored": len(all_ids),
        "scored_instrument_ids":    all_ids,
    }


# ── Individual Celery tasks ───────────────────────────────────────────────────

@celery_app.task(name="app.tasks.scoring.run_canslim")
def run_canslim_task(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    parsed_date = _parse_score_date(score_date)
    results = asyncio.run(
        run_canslim_scoring(
            score_date=parsed_date,
            market=market,
            instrument_ids=instrument_ids,
        )
    )
    return {
        "score_date": (parsed_date or date.today()).isoformat(),
        "market": market,
        "scored_count": len(results),
        "scored_instrument_ids": [r["instrument_id"] for r in results],
    }


@celery_app.task(name="app.tasks.scoring.run_piotroski")
def run_piotroski_task(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    parsed_date = _parse_score_date(score_date)
    results = asyncio.run(
        run_piotroski_scoring(
            score_date=parsed_date,
            market=market,
            instrument_ids=instrument_ids,
        )
    )
    return {
        "score_date": (parsed_date or date.today()).isoformat(),
        "market": market,
        "scored_count": len(results),
        "scored_instrument_ids": [r["instrument_id"] for r in results],
    }


@celery_app.task(name="app.tasks.scoring.run_minervini")
def run_minervini_task(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    from app.services.strategies.minervini.engine import run_minervini_scoring
    parsed_date = _parse_score_date(score_date)
    results = asyncio.run(
        run_minervini_scoring(
            score_date=parsed_date,
            market=market,
            instrument_ids=instrument_ids,
        )
    )
    return {
        "score_date": (parsed_date or date.today()).isoformat(),
        "market": market,
        "scored_count": len(results),
        "scored_instrument_ids": [r["instrument_id"] for r in results],
    }


@celery_app.task(name="app.tasks.scoring.run_weinstein")
def run_weinstein_task(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    from app.services.strategies.weinstein.engine import run_weinstein_scoring
    parsed_date = _parse_score_date(score_date)
    results = asyncio.run(
        run_weinstein_scoring(
            score_date=parsed_date,
            market=market,
            instrument_ids=instrument_ids,
        )
    )
    return {
        "score_date": (parsed_date or date.today()).isoformat(),
        "market": market,
        "scored_count": len(results),
        "scored_instrument_ids": [r["instrument_id"] for r in results],
    }


@celery_app.task(name="app.tasks.scoring.run_dual_momentum")
def run_dual_momentum_task(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    from app.services.strategies.dual_momentum.engine import run_dual_momentum_scoring
    parsed_date = _parse_score_date(score_date)
    results = asyncio.run(
        run_dual_momentum_scoring(
            score_date=parsed_date,
            market=market,
            instrument_ids=instrument_ids,
        )
    )
    return {
        "score_date": (parsed_date or date.today()).isoformat(),
        "market": market,
        "scored_count": len(results),
        "scored_instrument_ids": [r["instrument_id"] for r in results],
    }


@celery_app.task(name="app.tasks.scoring.run_technical_indicators")
def run_technical_indicators_task(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    from app.services.technical.advanced_indicators import run_technical_indicator_scoring
    parsed_date = _parse_score_date(score_date)
    results = asyncio.run(
        run_technical_indicator_scoring(
            score_date=parsed_date,
            market=market,
            instrument_ids=instrument_ids,
        )
    )
    return {
        "score_date": (parsed_date or date.today()).isoformat(),
        "market": market,
        "scored_count": len(results),
        "scored_instrument_ids": [r["instrument_id"] for r in results],
    }


@celery_app.task(name="app.tasks.scoring.run_pattern_detection")
def run_pattern_detection_task(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    from app.services.technical.pattern_detector import run_pattern_detection
    parsed_date = _parse_score_date(score_date)
    results = asyncio.run(
        run_pattern_detection(
            score_date=parsed_date,
            market=market,
            instrument_ids=instrument_ids,
        )
    )
    patterns_with_hits = sum(1 for r in results if r["pattern_count"] > 0)
    return {
        "score_date": (parsed_date or date.today()).isoformat(),
        "market": market,
        "scanned_count": len(results),
        "patterns_detected_count": patterns_with_hits,
        "scanned_instrument_ids": [r["instrument_id"] for r in results],
    }


@celery_app.task(name="app.tasks.scoring.run_technical_composite")
def run_technical_composite_task(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    """Standalone task: run technical composite AFTER indicators + patterns."""
    from app.services.technical.multi_timeframe import run_technical_composite_scoring
    parsed_date = _parse_score_date(score_date)
    results = asyncio.run(
        run_technical_composite_scoring(
            score_date=parsed_date,
            market=market,
            instrument_ids=instrument_ids,
        )
    )
    avg_composite = (
        sum(r["technical_composite"] for r in results) / len(results)
        if results else 0.0
    )
    return {
        "score_date": (parsed_date or date.today()).isoformat(),
        "market": market,
        "scored_count": len(results),
        "avg_technical_composite": round(avg_composite, 1),
        "scored_instrument_ids": [r["instrument_id"] for r in results],
    }


@celery_app.task(name="app.tasks.scoring.run_consensus")
def run_consensus_task(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    """Standalone task: compute consensus scores AFTER composite is ready."""
    from app.services.strategies.consensus import run_consensus_scoring
    parsed_date = _parse_score_date(score_date)
    results = asyncio.run(
        run_consensus_scoring(
            score_date=parsed_date,
            market=market,
            instrument_ids=instrument_ids,
        )
    )
    conviction_dist: dict[str, int] = {}
    for r in results:
        lv = r["conviction_level"]
        conviction_dist[lv] = conviction_dist.get(lv, 0) + 1
    return {
        "score_date": (parsed_date or date.today()).isoformat(),
        "market": market,
        "scored_count": len(results),
        "conviction_distribution": conviction_dist,
        "scored_instrument_ids": [r["instrument_id"] for r in results],
    }


@celery_app.task(name="app.tasks.scoring.run_snapshot")
def run_snapshot_task(
    snapshot_date: Optional[str] = None,
    markets: Optional[list[str]] = None,
) -> dict:
    """Standalone task: freeze consensus rankings into scoring_snapshots."""
    from app.services.strategies.snapshot_generator import run_snapshot_generation
    parsed_date = _parse_score_date(snapshot_date)
    snapshots = asyncio.run(
        run_snapshot_generation(
            snapshot_date=parsed_date,
            markets=markets,
        )
    )
    return {
        "snapshot_date": (parsed_date or date.today()).isoformat(),
        "snapshots_generated": len(snapshots),
        "markets": [s["market"] for s in snapshots],
        "totals": {s["market"]: s["instruments"] for s in snapshots},
    }


# ── Pipeline tasks ────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.scoring.run_phase2_pipeline")
def run_phase2_pipeline_task(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    return asyncio.run(
        run_phase2_scoring_pipeline(
            score_date=score_date,
            market=market,
            instrument_ids=instrument_ids,
        )
    )


@celery_app.task(name="app.tasks.scoring.run_full_pipeline")
def run_full_pipeline_task(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    """Full Phase 2 + Phase 3 scoring pipeline (all 6 strategy engines)."""
    return asyncio.run(
        run_full_scoring_pipeline(
            score_date=score_date,
            market=market,
            instrument_ids=instrument_ids,
        )
    )


@celery_app.task(name="app.tasks.scoring.run_phase2_backtest")
def run_phase2_backtest_task(
    market: Optional[str] = None,
    scoring_date: Optional[str] = None,
    forward_days: int = 63,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    parsed_date = _parse_score_date(scoring_date)
    report = asyncio.run(
        run_backtest(
            market=market,
            scoring_date=parsed_date,
            forward_days=forward_days,
            instrument_ids=instrument_ids,
        )
    )
    return report


@celery_app.task(name="app.tasks.scoring.run_consensus_backtest")
def run_consensus_backtest_task(
    market: Optional[str] = None,
    scoring_date: Optional[str] = None,
    forward_windows: Optional[dict[str, int]] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    parsed_date = _parse_score_date(scoring_date)
    report = asyncio.run(
        run_consensus_backtest(
            market=market,
            scoring_date=parsed_date,
            forward_windows=forward_windows,
            instrument_ids=instrument_ids,
        )
    )
    return report
