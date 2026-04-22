from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from datetime import date, timedelta
from time import perf_counter
from typing import Optional

from sqlalchemy import event, select

from app.core.config import settings
from app.core.database import AsyncTaskSessionLocal, engine as db_engine
from app.models.instrument import Instrument
from app.models.price import Price
from app.services.scoring_compute import (
    compute_canslim_from_context,
    compute_dual_momentum_from_context,
    compute_minervini_from_context,
    compute_patterns_from_context,
    compute_piotroski_from_context,
    compute_technical_composite_from_context,
    compute_technical_indicators_from_context,
    compute_weinstein_from_context,
)
from app.services.scoring_context import load_batch_scoring_context
from app.services.strategy_score_bulk import bulk_upsert_strategy_scores, merge_strategy_score_rows
from app.tasks.celery_app import celery_app
from app.services.strategies.canslim.engine import run_canslim_scoring
from app.services.strategies.canslim.engine import build_market_rs_lookup
from app.services.strategies.dual_momentum.engine import (
    BENCHMARK_TICKER,
    fetch_kr_risk_free_rate,
    fetch_us_risk_free_rate,
)
from app.services.strategies.piotroski.engine import run_piotroski_scoring
from app.services.strategies.backtest_validation import run_backtest, run_consensus_backtest

logger = logging.getLogger(__name__)

# Keep the historical module-level session name available for tests and older
# helpers while routing task work through the direct-host task session factory.
AsyncSessionLocal = AsyncTaskSessionLocal


def _parse_score_date(score_date: Optional[str]) -> Optional[date]:
    if not score_date:
        return None
    return date.fromisoformat(score_date)


@contextmanager
def _count_sql_queries():
    """
    Count SQL statements executed through the primary async engine while the
    scoring pipeline is running. This gives us a stable baseline before any
    shared-context refactor changes behavior.
    """
    counts = {"total": 0}

    def before_cursor_execute(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        counts["total"] += 1

    sync_engine = db_engine.sync_engine
    event.listen(sync_engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield counts
    finally:
        event.remove(sync_engine, "before_cursor_execute", before_cursor_execute)


async def _run_profiled_stage(name: str, coro, stage_metrics: dict[str, dict]) -> object:
    started_at = perf_counter()
    result = await coro
    duration_ms = round((perf_counter() - started_at) * 1000, 2)
    metric: dict[str, object] = {"duration_ms": duration_ms}
    if isinstance(result, list):
        metric["result_count"] = len(result)
    stage_metrics[name] = metric
    return result


def _build_profile_summary(
    *,
    started_at: float,
    query_counter: dict[str, int],
    stage_metrics: dict[str, dict],
) -> dict:
    total_duration_ms = round((perf_counter() - started_at) * 1000, 2)
    slowest_stage = max(
        stage_metrics.items(),
        key=lambda item: item[1]["duration_ms"],
        default=(None, None),
    )
    summary = {
        "total_duration_ms": total_duration_ms,
        "sql_query_count": query_counter["total"],
        "stages": stage_metrics,
    }
    if slowest_stage[0]:
        summary["slowest_stage"] = {
            "name": slowest_stage[0],
            "duration_ms": slowest_stage[1]["duration_ms"],
        }
    return summary


def _log_profile_summary(
    *,
    pipeline_name: str,
    market: Optional[str],
    instrument_ids: Optional[list[int]],
    profile: dict,
) -> None:
    logger.info(
        "%s profile: market=%s instruments=%s total_ms=%s queries=%s slowest=%s",
        pipeline_name,
        market or "ALL",
        len(instrument_ids) if instrument_ids else "ALL",
        profile["total_duration_ms"],
        profile["sql_query_count"],
        profile.get("slowest_stage", {}).get("name"),
    )


def _accumulate_stage_metric(
    stage_metrics: dict[str, dict],
    *,
    name: str,
    duration_ms: float,
    result_count: int = 0,
    extra: Optional[dict] = None,
) -> None:
    metric = stage_metrics.setdefault(name, {"duration_ms": 0.0})
    metric["duration_ms"] = round(metric["duration_ms"] + duration_ms, 2)
    if result_count:
        metric["result_count"] = metric.get("result_count", 0) + result_count
    if extra:
        for key, value in extra.items():
            if isinstance(value, (int, float)) and isinstance(metric.get(key), (int, float)):
                metric[key] += value
            elif key not in metric:
                metric[key] = value
            else:
                metric[key] = value


def _chunked(values: list[int], chunk_size: int) -> list[list[int]]:
    return [values[idx: idx + chunk_size] for idx in range(0, len(values), chunk_size)]


async def _resolve_target_instruments(
    *,
    market: Optional[str],
    instrument_ids: Optional[list[int]],
) -> list[tuple[int, str]]:
    async with AsyncTaskSessionLocal() as db:
        stmt = select(Instrument.id, Instrument.market).where(Instrument.is_active == True)
        if market:
            stmt = stmt.where(Instrument.market == market)
        if instrument_ids:
            stmt = stmt.where(Instrument.id.in_(instrument_ids))
        rows = await db.execute(stmt)
        return rows.all()


async def _load_market_inputs(
    *,
    markets: list[str],
    score_date: date,
) -> tuple[dict[str, list[float]], dict[str, float], dict[str, dict[int, float]], dict[str, dict[int, float]]]:
    risk_free_by_market: dict[str, float] = {}
    if "US" in markets and "KR" in markets:
        us_rf, kr_rf = await asyncio.gather(fetch_us_risk_free_rate(), fetch_kr_risk_free_rate())
        risk_free_by_market["US"] = us_rf or 0.05
        risk_free_by_market["KR"] = kr_rf or 0.035
    elif "US" in markets:
        risk_free_by_market["US"] = (await fetch_us_risk_free_rate()) or 0.05
    elif "KR" in markets:
        risk_free_by_market["KR"] = (await fetch_kr_risk_free_rate()) or 0.035

    benchmark_closes_by_market: dict[str, list[float]] = {}
    rs_lookup_by_market: dict[str, dict[int, float]] = {}
    rs_4w_lookup_by_market: dict[str, dict[int, float]] = {}
    async with AsyncTaskSessionLocal() as db:
        for market_name in markets:
            ticker = BENCHMARK_TICKER.get(market_name)
            if ticker is None:
                continue
            rows = await db.execute(
                select(Price.close)
                .join(Instrument, Instrument.id == Price.instrument_id)
                .where(
                    Instrument.ticker == ticker,
                    Price.trade_date <= score_date,
                )
                .order_by(Price.trade_date.asc())
            )
            closes = [float(row[0]) for row in rows.all() if row[0] is not None]
            benchmark_closes_by_market[market_name] = closes[-260:]
            rs_lookup_by_market[market_name] = await build_market_rs_lookup(db, market_name, score_date)
            rs_4w_lookup_by_market[market_name] = await build_market_rs_lookup(
                db,
                market_name,
                score_date - timedelta(days=28),
            )
    return benchmark_closes_by_market, risk_free_by_market, rs_lookup_by_market, rs_4w_lookup_by_market


def _resolve_pipeline_mode(pipeline_mode: Optional[str]) -> str:
    resolved = (pipeline_mode or settings.scoring_pipeline_mode or "context").strip().lower()
    return resolved if resolved in {"context", "legacy", "auto"} else "context"


def _build_full_pipeline_result(
    *,
    parsed_date: date,
    market: Optional[str],
    canslim_count: int,
    piotroski_count: int,
    minervini_count: int,
    weinstein_count: int,
    dual_momentum_count: int,
    technical_count: int,
    pattern_count: int,
    pattern_hits: int,
    composite_results: list[dict],
    consensus_results: list[dict],
    snapshots: list[dict],
    unique_ids: set[int],
    profile: dict,
) -> dict:
    all_ids = sorted(unique_ids | {row["instrument_id"] for row in consensus_results})
    composite_values = [
        row["technical_composite"]
        for row in composite_results
        if row.get("technical_composite") is not None
    ]
    avg_composite = (
        sum(composite_values) / len(composite_values) if composite_values else 0.0
    )
    conviction_dist: dict[str, int] = {}
    for row in consensus_results:
        conviction_level = row["conviction_level"]
        conviction_dist[conviction_level] = conviction_dist.get(conviction_level, 0) + 1

    return {
        "score_date": parsed_date.isoformat(),
        "market": market,
        "canslim_scored": canslim_count,
        "piotroski_scored": piotroski_count,
        "minervini_scored": minervini_count,
        "weinstein_scored": weinstein_count,
        "dual_momentum_scored": dual_momentum_count,
        "technical_scored": technical_count,
        "patterns_scanned": pattern_count,
        "patterns_with_detections": pattern_hits,
        "composite_scored": len(composite_results),
        "avg_technical_composite": round(avg_composite, 1),
        "consensus_scored": len(consensus_results),
        "conviction_distribution": conviction_dist,
        "snapshots_generated": len(snapshots),
        "unique_instruments_scored": len(all_ids),
        "scored_instrument_ids": all_ids,
        "profile": profile,
    }


async def _run_context_full_scoring_pipeline(
    *,
    parsed_date: date,
    market: Optional[str],
    instrument_ids: Optional[list[int]],
    generate_snapshots: bool,
) -> dict:
    from app.services.strategies.consensus import run_consensus_scoring
    from app.services.strategies.snapshot_generator import run_snapshot_generation

    stage_metrics: dict[str, dict] = {}

    with _count_sql_queries() as query_counter:
        started_at = perf_counter()
        resolve_started_at = perf_counter()
        instrument_rows = await _resolve_target_instruments(market=market, instrument_ids=instrument_ids)
        _accumulate_stage_metric(
            stage_metrics,
            name="resolve_targets",
            duration_ms=(perf_counter() - resolve_started_at) * 1000,
            result_count=len(instrument_rows),
        )

        target_ids = [row[0] for row in instrument_rows]
        target_markets = sorted({row[1] for row in instrument_rows})
        unique_ids: set[int] = set()

        canslim_count = 0
        piotroski_count = 0
        minervini_count = 0
        weinstein_count = 0
        dual_momentum_count = 0
        technical_count = 0
        pattern_count = 0
        pattern_hits = 0
        composite_results: list[dict] = []

        market_inputs_started_at = perf_counter()
        (
            benchmark_closes_by_market,
            risk_free_by_market,
            rs_lookup_by_market,
            rs_4w_lookup_by_market,
        ) = await _load_market_inputs(
            markets=target_markets,
            score_date=parsed_date,
        )
        _accumulate_stage_metric(
            stage_metrics,
            name="market_inputs",
            duration_ms=(perf_counter() - market_inputs_started_at) * 1000,
            extra={"markets_loaded": len(target_markets)},
        )

        chunk_size = 100
        for chunk_ids in _chunked(target_ids, chunk_size):
            async with AsyncSessionLocal() as db:
                context_started_at = perf_counter()
                batch_context = await load_batch_scoring_context(
                    db,
                    instrument_ids=chunk_ids,
                    score_date=parsed_date,
                )
                _accumulate_stage_metric(
                    stage_metrics,
                    name="context_load",
                    duration_ms=(perf_counter() - context_started_at) * 1000,
                    result_count=len(batch_context.instruments),
                )

                pattern_results: list[dict] = []
                technical_results: list[dict] = []
                piotroski_results: list[dict] = []
                minervini_results: list[dict] = []
                weinstein_results: list[dict] = []
                dual_mom_results: list[dict] = []
                canslim_results: list[dict] = []
                chunk_composite_results: list[dict] = []

                patterns_by_id: dict[int, dict] = {}
                technical_by_id: dict[int, dict] = {}
                minervini_by_id: dict[int, dict] = {}

                stage_started_at = perf_counter()
                for inst_id in chunk_ids:
                    ctx = batch_context.instruments.get(inst_id)
                    if ctx is None:
                        continue
                    result = compute_patterns_from_context(
                        instrument=ctx.instrument,
                        score_date=parsed_date,
                        prices=ctx.prices,
                    )
                    if result is not None:
                        pattern_results.append(result)
                        patterns_by_id[inst_id] = result
                _accumulate_stage_metric(
                    stage_metrics,
                    name="pattern_detection",
                    duration_ms=(perf_counter() - stage_started_at) * 1000,
                    result_count=len(pattern_results),
                )

                stage_started_at = perf_counter()
                for inst_id in chunk_ids:
                    ctx = batch_context.instruments.get(inst_id)
                    if ctx is None:
                        continue
                    result = compute_technical_indicators_from_context(
                        instrument_id=inst_id,
                        score_date=parsed_date,
                        prices=ctx.prices,
                        benchmark_closes=benchmark_closes_by_market.get(ctx.instrument.market, []),
                    )
                    if result is not None:
                        technical_results.append(result)
                        technical_by_id[inst_id] = result
                _accumulate_stage_metric(
                    stage_metrics,
                    name="technical_indicators",
                    duration_ms=(perf_counter() - stage_started_at) * 1000,
                    result_count=len(technical_results),
                )

                stage_started_at = perf_counter()
                for inst_id in chunk_ids:
                    ctx = batch_context.instruments.get(inst_id)
                    if ctx is None:
                        continue
                    result = compute_piotroski_from_context(
                        instrument_id=inst_id,
                        score_date=parsed_date,
                        annuals=ctx.annuals,
                    )
                    if result is not None:
                        piotroski_results.append(result)
                _accumulate_stage_metric(
                    stage_metrics,
                    name="piotroski",
                    duration_ms=(perf_counter() - stage_started_at) * 1000,
                    result_count=len(piotroski_results),
                )

                stage_started_at = perf_counter()
                for inst_id in chunk_ids:
                    ctx = batch_context.instruments.get(inst_id)
                    if ctx is None:
                        continue
                    result = compute_minervini_from_context(
                        instrument_id=inst_id,
                        score_date=parsed_date,
                        prices=ctx.prices,
                        rs_rating=rs_lookup_by_market.get(ctx.instrument.market, {}).get(inst_id),
                    )
                    if result is not None:
                        minervini_results.append(result)
                        minervini_by_id[inst_id] = result
                _accumulate_stage_metric(
                    stage_metrics,
                    name="minervini",
                    duration_ms=(perf_counter() - stage_started_at) * 1000,
                    result_count=len(minervini_results),
                )

                stage_started_at = perf_counter()
                for inst_id in chunk_ids:
                    ctx = batch_context.instruments.get(inst_id)
                    if ctx is None:
                        continue
                    result = compute_weinstein_from_context(
                        instrument_id=inst_id,
                        score_date=parsed_date,
                        prices=ctx.prices,
                    )
                    if result is not None:
                        weinstein_results.append(result)
                _accumulate_stage_metric(
                    stage_metrics,
                    name="weinstein",
                    duration_ms=(perf_counter() - stage_started_at) * 1000,
                    result_count=len(weinstein_results),
                )

                stage_started_at = perf_counter()
                for inst_id in chunk_ids:
                    ctx = batch_context.instruments.get(inst_id)
                    if ctx is None:
                        continue
                    result = compute_dual_momentum_from_context(
                        instrument_id=inst_id,
                        score_date=parsed_date,
                        prices=ctx.prices,
                        benchmark_closes=benchmark_closes_by_market.get(ctx.instrument.market, []),
                        risk_free=risk_free_by_market.get(ctx.instrument.market, 0.05),
                    )
                    if result is not None:
                        dual_mom_results.append(result)
                _accumulate_stage_metric(
                    stage_metrics,
                    name="dual_momentum",
                    duration_ms=(perf_counter() - stage_started_at) * 1000,
                    result_count=len(dual_mom_results),
                )

                stage_started_at = perf_counter()
                for inst_id in chunk_ids:
                    ctx = batch_context.instruments.get(inst_id)
                    if ctx is None:
                        continue
                    pattern_result = patterns_by_id.get(inst_id)
                    technical_result = technical_by_id.get(inst_id)
                    result = compute_canslim_from_context(
                        instrument=ctx.instrument,
                        quarterlies=ctx.quarterlies,
                        annuals=ctx.annuals,
                        prices=ctx.prices,
                        institutional=ctx.institutional,
                        regime=batch_context.regimes_by_market.get(ctx.instrument.market),
                        score_date=parsed_date,
                        rs_lookup=rs_lookup_by_market.get(ctx.instrument.market, {}),
                        rs_4w_lookup=rs_4w_lookup_by_market.get(ctx.instrument.market, {}),
                        patterns=pattern_result["patterns"] if pattern_result else None,
                        rs_line_new_high=bool(
                            technical_result["rs_line_new_high"] if technical_result else False
                        ),
                    )
                    if result is not None:
                        canslim_results.append(result)
                _accumulate_stage_metric(
                    stage_metrics,
                    name="canslim",
                    duration_ms=(perf_counter() - stage_started_at) * 1000,
                    result_count=len(canslim_results),
                )

                stage_started_at = perf_counter()
                for inst_id in chunk_ids:
                    ctx = batch_context.instruments.get(inst_id)
                    if ctx is None:
                        continue
                    result = compute_technical_composite_from_context(
                        instrument_id=inst_id,
                        score_date=parsed_date,
                        prices=ctx.prices,
                        patterns=patterns_by_id.get(inst_id, {}).get("patterns"),
                        technical_detail=technical_by_id.get(inst_id, {}).get("technical_detail"),
                        minervini_criteria_count=minervini_by_id.get(inst_id, {}).get(
                            "minervini_criteria_count"
                        ),
                    )
                    if result is not None:
                        chunk_composite_results.append(result)
                _accumulate_stage_metric(
                    stage_metrics,
                    name="technical_composite_compute",
                    duration_ms=(perf_counter() - stage_started_at) * 1000,
                    result_count=len(chunk_composite_results),
                )

                bulk_rows = merge_strategy_score_rows(
                    [
                        pattern_results,
                        technical_results,
                        piotroski_results,
                        minervini_results,
                        weinstein_results,
                        dual_mom_results,
                        canslim_results,
                        chunk_composite_results,
                    ]
                )
                upsert_started_at = perf_counter()
                await bulk_upsert_strategy_scores(db, bulk_rows)
                await db.commit()
                _accumulate_stage_metric(
                    stage_metrics,
                    name="strategy_score_upsert",
                    duration_ms=(perf_counter() - upsert_started_at) * 1000,
                    result_count=len(bulk_rows),
                )

                canslim_count += len(canslim_results)
                piotroski_count += len(piotroski_results)
                minervini_count += len(minervini_results)
                weinstein_count += len(weinstein_results)
                dual_momentum_count += len(dual_mom_results)
                technical_count += len(technical_results)
                pattern_count += len(pattern_results)
                pattern_hits += sum(1 for row in pattern_results if row["pattern_count"] > 0)
                composite_results.extend(chunk_composite_results)
                unique_ids.update(row["instrument_id"] for row in bulk_rows)

        consensus_results = await _run_profiled_stage(
            "consensus",
            run_consensus_scoring(
                score_date=parsed_date, market=market, instrument_ids=instrument_ids
            ),
            stage_metrics,
        )

        snapshots: list[dict] = []
        if generate_snapshots:
            markets_to_snap = [market] if market else ["US", "KR"]
            snapshots = await _run_profiled_stage(
                "snapshot_generation",
                run_snapshot_generation(snapshot_date=parsed_date, markets=markets_to_snap),
                stage_metrics,
            )
        else:
            stage_metrics["snapshot_generation"] = {
                "duration_ms": 0.0,
                "result_count": 0,
                "skipped": True,
            }

        profile = _build_profile_summary(
            started_at=started_at,
            query_counter=query_counter,
            stage_metrics=stage_metrics,
        )

    return _build_full_pipeline_result(
        parsed_date=parsed_date,
        market=market,
        canslim_count=canslim_count,
        piotroski_count=piotroski_count,
        minervini_count=minervini_count,
        weinstein_count=weinstein_count,
        dual_momentum_count=dual_momentum_count,
        technical_count=technical_count,
        pattern_count=pattern_count,
        pattern_hits=pattern_hits,
        composite_results=composite_results,
        consensus_results=consensus_results,
        snapshots=snapshots,
        unique_ids=unique_ids,
        profile=profile,
    )


async def _run_legacy_full_scoring_pipeline(
    *,
    parsed_date: date,
    market: Optional[str],
    instrument_ids: Optional[list[int]],
    generate_snapshots: bool,
) -> dict:
    from app.services.strategies.consensus import run_consensus_scoring
    from app.services.strategies.minervini.engine import run_minervini_scoring
    from app.services.strategies.snapshot_generator import run_snapshot_generation
    from app.services.strategies.weinstein.engine import run_weinstein_scoring
    from app.services.strategies.dual_momentum.engine import run_dual_momentum_scoring
    from app.services.technical.advanced_indicators import run_technical_indicator_scoring
    from app.services.technical.multi_timeframe import run_technical_composite_scoring
    from app.services.technical.pattern_detector import run_pattern_detection

    stage_metrics: dict[str, dict] = {}

    with _count_sql_queries() as query_counter:
        started_at = perf_counter()
        canslim_results = await _run_profiled_stage(
            "canslim",
            run_canslim_scoring(
                score_date=parsed_date,
                market=market,
                instrument_ids=instrument_ids,
            ),
            stage_metrics,
        )
        piotroski_results = await _run_profiled_stage(
            "piotroski",
            run_piotroski_scoring(
                score_date=parsed_date,
                market=market,
                instrument_ids=instrument_ids,
            ),
            stage_metrics,
        )
        minervini_results = await _run_profiled_stage(
            "minervini",
            run_minervini_scoring(
                score_date=parsed_date,
                market=market,
                instrument_ids=instrument_ids,
            ),
            stage_metrics,
        )
        weinstein_results = await _run_profiled_stage(
            "weinstein",
            run_weinstein_scoring(
                score_date=parsed_date,
                market=market,
                instrument_ids=instrument_ids,
            ),
            stage_metrics,
        )
        dual_momentum_results = await _run_profiled_stage(
            "dual_momentum",
            run_dual_momentum_scoring(
                score_date=parsed_date,
                market=market,
                instrument_ids=instrument_ids,
            ),
            stage_metrics,
        )
        technical_results = await _run_profiled_stage(
            "technical_indicators",
            run_technical_indicator_scoring(
                score_date=parsed_date,
                market=market,
                instrument_ids=instrument_ids,
            ),
            stage_metrics,
        )
        pattern_results = await _run_profiled_stage(
            "pattern_detection",
            run_pattern_detection(
                score_date=parsed_date,
                market=market,
                instrument_ids=instrument_ids,
            ),
            stage_metrics,
        )
        composite_results = await _run_profiled_stage(
            "technical_composite_compute",
            run_technical_composite_scoring(
                score_date=parsed_date,
                market=market,
                instrument_ids=instrument_ids,
            ),
            stage_metrics,
        )
        consensus_results = await _run_profiled_stage(
            "consensus",
            run_consensus_scoring(
                score_date=parsed_date,
                market=market,
                instrument_ids=instrument_ids,
            ),
            stage_metrics,
        )

        snapshots: list[dict] = []
        if generate_snapshots:
            markets_to_snap = [market] if market else ["US", "KR"]
            snapshots = await _run_profiled_stage(
                "snapshot_generation",
                run_snapshot_generation(snapshot_date=parsed_date, markets=markets_to_snap),
                stage_metrics,
            )
        else:
            stage_metrics["snapshot_generation"] = {
                "duration_ms": 0.0,
                "result_count": 0,
                "skipped": True,
            }

        profile = _build_profile_summary(
            started_at=started_at,
            query_counter=query_counter,
            stage_metrics=stage_metrics,
        )

    unique_ids = {
        *(row["instrument_id"] for row in canslim_results),
        *(row["instrument_id"] for row in piotroski_results),
        *(row["instrument_id"] for row in minervini_results),
        *(row["instrument_id"] for row in weinstein_results),
        *(row["instrument_id"] for row in dual_momentum_results),
        *(row["instrument_id"] for row in technical_results),
        *(row["instrument_id"] for row in pattern_results),
        *(row["instrument_id"] for row in composite_results),
    }

    return _build_full_pipeline_result(
        parsed_date=parsed_date,
        market=market,
        canslim_count=len(canslim_results),
        piotroski_count=len(piotroski_results),
        minervini_count=len(minervini_results),
        weinstein_count=len(weinstein_results),
        dual_momentum_count=len(dual_momentum_results),
        technical_count=len(technical_results),
        pattern_count=len(pattern_results),
        pattern_hits=sum(1 for row in pattern_results if row.get("pattern_count", 0) > 0),
        composite_results=composite_results,
        consensus_results=consensus_results,
        snapshots=snapshots,
        unique_ids=unique_ids,
        profile=profile,
    )


async def run_phase2_scoring_pipeline(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    parsed_date = _parse_score_date(score_date)
    stage_metrics: dict[str, dict] = {}

    with _count_sql_queries() as query_counter:
        started_at = perf_counter()
        canslim_results = await _run_profiled_stage(
            "canslim",
            run_canslim_scoring(
                score_date=parsed_date,
                market=market,
                instrument_ids=instrument_ids,
            ),
            stage_metrics,
        )
        piotroski_results = await _run_profiled_stage(
            "piotroski",
            run_piotroski_scoring(
                score_date=parsed_date,
                market=market,
                instrument_ids=instrument_ids,
            ),
            stage_metrics,
        )
        profile = _build_profile_summary(
            started_at=started_at,
            query_counter=query_counter,
            stage_metrics=stage_metrics,
        )

    scored_ids = sorted(
        {
            *(row["instrument_id"] for row in canslim_results),
            *(row["instrument_id"] for row in piotroski_results),
        }
    )

    result = {
        "score_date": (parsed_date or date.today()).isoformat(),
        "market": market,
        "instrument_ids": instrument_ids,
        "canslim_scored": len(canslim_results),
        "piotroski_scored": len(piotroski_results),
        "unique_instruments_scored": len(scored_ids),
        "scored_instrument_ids": scored_ids,
        "profile": profile,
    }
    _log_profile_summary(
        pipeline_name="phase2_scoring_pipeline",
        market=market,
        instrument_ids=instrument_ids,
        profile=profile,
    )
    return result


async def run_full_scoring_pipeline(
    score_date: Optional[str] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
    *,
    pipeline_mode: Optional[str] = None,
    generate_snapshots: bool = True,
) -> dict:
    """
    Full scoring pipeline: Phase 2 strategies → Phase 3 technical →
    Phase 4 consensus + snapshot generation.
    """
    parsed_date = _parse_score_date(score_date) or date.today()
    resolved_pipeline_mode = _resolve_pipeline_mode(pipeline_mode)
    if resolved_pipeline_mode == "legacy":
        result = await _run_legacy_full_scoring_pipeline(
            parsed_date=parsed_date,
            market=market,
            instrument_ids=instrument_ids,
            generate_snapshots=generate_snapshots,
        )
    else:
        result = await _run_context_full_scoring_pipeline(
            parsed_date=parsed_date,
            market=market,
            instrument_ids=instrument_ids,
            generate_snapshots=generate_snapshots,
        )

    result["pipeline_mode"] = "legacy" if resolved_pipeline_mode == "legacy" else "context"
    _log_profile_summary(
        pipeline_name="full_scoring_pipeline",
        market=market,
        instrument_ids=instrument_ids,
        profile=result["profile"],
    )
    return result


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
        sum(r["technical_composite"] for r in results) / len(results) if results else 0.0
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
    """
    Freeze consensus rankings into scoring_snapshots, then upload to R2.

    R2 upload is env-gated — a no-op when R2_ACCOUNT_ID is absent.
    """
    from app.services.strategies.snapshot_generator import run_snapshot_generation

    parsed_date = _parse_score_date(snapshot_date)
    snapshots = asyncio.run(
        run_snapshot_generation(
            snapshot_date=parsed_date,
            markets=markets,
        )
    )

    result = {
        "snapshot_date": (parsed_date or date.today()).isoformat(),
        "snapshots_generated": len(snapshots),
        "markets": [s["market"] for s in snapshots],
        "totals": {s["market"]: s["instruments"] for s in snapshots},
        "r2_urls": [],
    }

    # ── R2 CDN upload (no-op when not configured) ─────────────────────────────
    if snapshots:
        r2_urls = asyncio.run(_upload_all_snapshots_to_r2(snapshots))
        result["r2_urls"] = r2_urls

    return result


async def _upload_all_snapshots_to_r2(snapshots: list[dict]) -> list[str]:
    """
    For each generated snapshot, fetch the full rankings_json from the DB and
    upload to R2.  Returns a list of public CDN URLs (empty strings for failed
    or unconfigured uploads).
    """
    from app.core.config import settings  # noqa: PLC0415
    from app.core.database import AsyncTaskSessionLocal  # noqa: PLC0415
    from app.models.snapshot import ScoringSnapshot  # noqa: PLC0415
    from app.services.storage.r2 import upload_snapshot  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415

    if not settings.r2_enabled:
        return []

    urls: list[str] = []
    async with AsyncTaskSessionLocal() as db:
        for snap in snapshots:
            market = snap["market"]
            asset_type = snap.get("asset_type", "stock")
            snap_date = date.fromisoformat(snap["snapshot_date"])

            result = await db.execute(
                select(ScoringSnapshot).where(
                    ScoringSnapshot.snapshot_date == snap_date,
                    ScoringSnapshot.market == market,
                    ScoringSnapshot.asset_type == asset_type,
                )
            )
            row = result.scalars().first()
            if row is None:
                urls.append("")
                continue

            payload = {
                "snapshot_date": snap_date.isoformat(),
                "market": market,
                "asset_type": asset_type,
                "rankings": row.rankings_json or [],
                "metadata": row.metadata_ or {},
            }
            url = upload_snapshot(
                market=market,
                asset_type=asset_type,
                snapshot_date=snap_date,
                payload=payload,
            )
            urls.append(url or "")
    return urls


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
    pipeline_mode: Optional[str] = None,
    generate_snapshots: bool = True,
) -> dict:
    """Full Phase 2 + Phase 3 scoring pipeline (all 6 strategy engines)."""
    return asyncio.run(
        run_full_scoring_pipeline(
            score_date=score_date,
            market=market,
            instrument_ids=instrument_ids,
            pipeline_mode=pipeline_mode,
            generate_snapshots=generate_snapshots,
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
