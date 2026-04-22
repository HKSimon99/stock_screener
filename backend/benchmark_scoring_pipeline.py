"""
Benchmark the scoring pipeline on a representative instrument sample.

Examples:
  cd backend && uv run python benchmark_scoring_pipeline.py --market US --limit 10
  cd backend && uv run python benchmark_scoring_pipeline.py --market KR --limit 10 --modes context legacy
"""

from __future__ import annotations

import argparse
import asyncio
import json
from statistics import mean
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base
from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.price import Price
from app.tasks.scoring_tasks import run_full_scoring_pipeline


async def _select_price_ready_instrument_ids(*, market: str | None, limit: int) -> list[int]:
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Instrument.id)
            .join(Price, Price.instrument_id == Instrument.id)
            .where(Instrument.is_active == True)
            .group_by(Instrument.id)
            .order_by(func.max(Price.trade_date).desc(), Instrument.id.asc())
            .limit(limit)
        )
        if market:
            stmt = stmt.where(Instrument.market == market)
        rows = await db.execute(stmt)
        return [row[0] for row in rows.all()]


def _truncate_all_tables_sql() -> str:
    table_names = [
        f'"{table.schema}"."{table.name}"' if table.schema else f'"{table.name}"'
        for table in reversed(Base.metadata.sorted_tables)
    ]
    return f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE"


async def _seed_synthetic_fixture() -> tuple[list[int], str | None]:
    from app.tasks import scoring_tasks
    from app.services.strategies.dual_momentum import engine as dual_momentum_engine
    from tests.test_strategy_runners import _seed_full_strategy_fixture

    async def fake_us_rate():
        return 0.05

    async def fake_kr_rate():
        return 0.0325

    scoring_tasks.fetch_us_risk_free_rate = fake_us_rate
    scoring_tasks.fetch_kr_risk_free_rate = fake_kr_rate
    dual_momentum_engine.fetch_us_risk_free_rate = fake_us_rate
    dual_momentum_engine.fetch_kr_risk_free_rate = fake_kr_rate

    engine = create_async_engine(settings.database_url, echo=False, connect_args=settings.asyncpg_connect_args)
    session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_local() as session:
        await session.execute(text(_truncate_all_tables_sql()))
        await session.commit()
        fixture = await _seed_full_strategy_fixture(session)
        instrument_ids = [fixture["us_stock"].id, fixture["kr_stock"].id]
        await session.commit()
    await engine.dispose()
    return instrument_ids, None


async def _cleanup_synthetic_fixture() -> None:
    engine = create_async_engine(settings.database_url, echo=False, connect_args=settings.asyncpg_connect_args)
    session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_local() as session:
        await session.execute(text(_truncate_all_tables_sql()))
        await session.commit()
    await engine.dispose()


def _summarize_stage_means(results: list[dict[str, Any]]) -> dict[str, float]:
    stage_names = sorted(
        {
            stage_name
            for result in results
            for stage_name in result.get("profile", {}).get("stages", {}).keys()
        }
    )
    summary: dict[str, float] = {}
    for stage_name in stage_names:
        durations = [
            result["profile"]["stages"][stage_name]["duration_ms"]
            for result in results
            if stage_name in result.get("profile", {}).get("stages", {})
        ]
        if durations:
            summary[stage_name] = round(mean(durations), 2)
    return summary


async def _benchmark_mode(
    *,
    market: str | None,
    instrument_ids: list[int],
    repeats: int,
    mode: str,
    generate_snapshots: bool,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for _ in range(repeats):
        result = await run_full_scoring_pipeline(
            market=market,
            instrument_ids=instrument_ids,
            pipeline_mode=mode,
            generate_snapshots=generate_snapshots,
        )
        runs.append(result)

    avg_total_ms = round(mean(result["profile"]["total_duration_ms"] for result in runs), 2)
    avg_queries = round(mean(result["profile"]["sql_query_count"] for result in runs), 2)
    return {
        "mode": mode,
        "repeats": repeats,
        "market": market,
        "instrument_ids": instrument_ids,
        "generate_snapshots": generate_snapshots,
        "avg_total_duration_ms": avg_total_ms,
        "avg_sql_query_count": avg_queries,
        "avg_stage_duration_ms": _summarize_stage_means(runs),
        "runs": [
            {
                "total_duration_ms": result["profile"]["total_duration_ms"],
                "sql_query_count": result["profile"]["sql_query_count"],
                "slowest_stage": result["profile"].get("slowest_stage"),
            }
            for result in runs
        ],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the scoring pipeline.")
    parser.add_argument("--market", choices=["US", "KR"], default=None)
    parser.add_argument("--limit", type=int, default=10, help="Number of price-ready instruments to sample.")
    parser.add_argument("--repeats", type=int, default=1, help="How many times to run each mode.")
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=["context", "legacy"],
        default=["context", "legacy"],
        help="Pipeline modes to benchmark.",
    )
    parser.add_argument(
        "--include-snapshots",
        action="store_true",
        help="Include snapshot generation in the benchmark.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a text summary.",
    )
    parser.add_argument(
        "--synthetic-fixture",
        action="store_true",
        help="Seed the benchmark with the small strategy-runner fixture instead of using live DB data.",
    )
    return parser


async def _main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    cleanup_synthetic = False
    if args.synthetic_fixture:
        instrument_ids, seeded_market = await _seed_synthetic_fixture()
        cleanup_synthetic = True
        benchmark_market = seeded_market
    else:
        instrument_ids = await _select_price_ready_instrument_ids(
            market=args.market,
            limit=args.limit,
        )
        if not instrument_ids:
            raise SystemExit("No price-ready instruments found for the requested sample.")
        benchmark_market = args.market

    try:
        reports = []
        for mode in args.modes:
            report = await _benchmark_mode(
                market=benchmark_market,
                instrument_ids=instrument_ids,
                repeats=args.repeats,
                mode=mode,
                generate_snapshots=args.include_snapshots,
            )
            reports.append(report)
    finally:
        if cleanup_synthetic:
            await _cleanup_synthetic_fixture()

    if args.json:
        print(json.dumps(reports, indent=2))
        return

    print(
        f"Sampled {len(instrument_ids)} instrument(s)"
        f"{f' in {benchmark_market}' if benchmark_market else ''}: {instrument_ids}"
    )
    for report in reports:
        print(f"\nMode: {report['mode']}")
        print(f"  Avg total duration: {report['avg_total_duration_ms']} ms")
        print(f"  Avg SQL queries:    {report['avg_sql_query_count']}")
        print("  Avg stage times:")
        for stage_name, duration_ms in sorted(
            report["avg_stage_duration_ms"].items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            print(f"    - {stage_name}: {duration_ms} ms")


if __name__ == "__main__":
    asyncio.run(_main())
