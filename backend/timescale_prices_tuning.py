"""Audit and selectively tune the `consensus_app.prices` table for TimescaleDB."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import text

from app.core.database import AsyncTaskSessionLocal


DEFAULT_SCHEMA = "consensus_app"
DEFAULT_TABLE = "prices"
DEFAULT_CHUNK_INTERVAL_DAYS = 30
DEFAULT_COMPRESS_AFTER_DAYS = 540
DEFAULT_MIN_ROWS_FOR_COMPRESSION = 1_000_000
DEFAULT_MIN_SIZE_BYTES_FOR_COMPRESSION = 256 * 1024 * 1024


@dataclass(slots=True)
class PricesAudit:
    schema: str
    table: str
    timescaledb_enabled: bool
    is_hypertable: bool
    compression_enabled: bool
    compression_orderby: str | None
    compression_segmentby: str | None
    chunk_interval: str | None
    jobs: list[dict[str, Any]]
    row_count: int
    instrument_count: int
    min_trade_date: str | None
    max_trade_date: str | None
    total_size_bytes: int
    total_size_pretty: str
    recommended_for_compression: bool
    recommendation_reasons: list[str]


async def _scalar(session, sql: str, params: dict[str, Any]) -> Any:
    return (await session.execute(text(sql), params)).scalar_one_or_none()


async def collect_prices_audit(
    *,
    schema: str = DEFAULT_SCHEMA,
    table: str = DEFAULT_TABLE,
    compress_after_days: int = DEFAULT_COMPRESS_AFTER_DAYS,
    min_rows_for_compression: int = DEFAULT_MIN_ROWS_FOR_COMPRESSION,
    min_size_bytes_for_compression: int = DEFAULT_MIN_SIZE_BYTES_FOR_COMPRESSION,
) -> PricesAudit:
    params = {"schema": schema, "table": table}

    async with AsyncTaskSessionLocal() as session:
        timescaledb_enabled = bool(
            await _scalar(
                session,
                "select exists(select 1 from pg_extension where extname = 'timescaledb')",
                {},
            )
        )

        row = (
            await session.execute(
                text(
                    f"""
                    select
                      count(*)::bigint as row_count,
                      count(distinct instrument_id)::bigint as instrument_count,
                      min(trade_date)::text as min_trade_date,
                      max(trade_date)::text as max_trade_date,
                      pg_total_relation_size('{schema}.{table}')::bigint as total_size_bytes,
                      pg_size_pretty(pg_total_relation_size('{schema}.{table}')) as total_size_pretty
                    from {schema}.{table}
                    """
                )
            )
        ).one()

        is_hypertable = False
        compression_enabled = False
        compression_orderby = None
        compression_segmentby = None
        chunk_interval = None
        jobs: list[dict[str, Any]] = []

        if timescaledb_enabled:
            hypertable_row = (
                await session.execute(
                    text(
                        """
                        select compression_enabled
                        from timescaledb_information.hypertables
                        where hypertable_schema = :schema and hypertable_name = :table
                        """
                    ),
                    params,
                )
            ).first()
            is_hypertable = hypertable_row is not None
            compression_enabled = bool(hypertable_row[0]) if hypertable_row else False

            chunk_interval = await _scalar(
                session,
                """
                select interval_length::text
                from timescaledb_information.dimensions
                where hypertable_schema = :schema and hypertable_name = :table
                  and column_name = 'trade_date'
                """,
                params,
            )

            settings_rows = (
                await session.execute(
                    text(
                        """
                        select attname, segmentby_column_index, orderby_column_index
                        from timescaledb_information.compression_settings
                        where hypertable_schema = :schema and hypertable_name = :table
                        order by coalesce(segmentby_column_index, 999), coalesce(orderby_column_index, 999), attname
                        """
                    ),
                    params,
                )
            ).all()

            segmentby = [attname for attname, seg_idx, _ord_idx in settings_rows if seg_idx is not None]
            orderby = [attname for attname, _seg_idx, ord_idx in settings_rows if ord_idx is not None]
            compression_segmentby = ", ".join(segmentby) if segmentby else None
            compression_orderby = ", ".join(orderby) if orderby else None

            jobs_rows = (
                await session.execute(
                    text(
                        """
                        select application_name, schedule_interval::text, proc_name
                        from timescaledb_information.jobs
                        where hypertable_schema = :schema and hypertable_name = :table
                        order by application_name
                        """
                    ),
                    params,
                )
            ).all()
            jobs = [
                {
                    "application_name": application_name,
                    "schedule_interval": schedule_interval,
                    "proc_name": proc_name,
                }
                for application_name, schedule_interval, proc_name in jobs_rows
            ]

        reasons: list[str] = []
        if row.row_count < min_rows_for_compression:
            reasons.append(
                f"row_count {row.row_count} is below the compression threshold {min_rows_for_compression}"
            )
        if row.total_size_bytes < min_size_bytes_for_compression:
            reasons.append(
                "table size "
                f"{row.total_size_pretty} is below the compression threshold "
                f"{min_size_bytes_for_compression // (1024 * 1024)} MB"
            )
        if not timescaledb_enabled:
            reasons.append("timescaledb extension is not enabled in this database")
        elif not is_hypertable:
            reasons.append("prices exists as a plain table, not a hypertable")
        if compress_after_days < 365:
            reasons.append("compress_after_days is under 365, which is too aggressive for chart reads")

        return PricesAudit(
            schema=schema,
            table=table,
            timescaledb_enabled=timescaledb_enabled,
            is_hypertable=is_hypertable,
            compression_enabled=compression_enabled,
            compression_orderby=compression_orderby,
            compression_segmentby=compression_segmentby,
            chunk_interval=chunk_interval,
            jobs=jobs,
            row_count=int(row.row_count or 0),
            instrument_count=int(row.instrument_count or 0),
            min_trade_date=row.min_trade_date,
            max_trade_date=row.max_trade_date,
            total_size_bytes=int(row.total_size_bytes or 0),
            total_size_pretty=str(row.total_size_pretty),
            recommended_for_compression=not reasons,
            recommendation_reasons=reasons,
        )


async def apply_prices_tuning(
    *,
    schema: str = DEFAULT_SCHEMA,
    table: str = DEFAULT_TABLE,
    chunk_interval_days: int = DEFAULT_CHUNK_INTERVAL_DAYS,
    compress_after_days: int = DEFAULT_COMPRESS_AFTER_DAYS,
    min_rows_for_compression: int = DEFAULT_MIN_ROWS_FOR_COMPRESSION,
    min_size_bytes_for_compression: int = DEFAULT_MIN_SIZE_BYTES_FOR_COMPRESSION,
) -> PricesAudit:
    audit = await collect_prices_audit(
        schema=schema,
        table=table,
        compress_after_days=compress_after_days,
        min_rows_for_compression=min_rows_for_compression,
        min_size_bytes_for_compression=min_size_bytes_for_compression,
    )

    if not audit.timescaledb_enabled:
        raise RuntimeError("timescaledb is not enabled in this database")
    if not audit.is_hypertable:
        raise RuntimeError("prices is not a Timescale hypertable")
    if not audit.recommended_for_compression:
        raise RuntimeError(
            "Refusing to apply compression policy because readiness checks failed: "
            + "; ".join(audit.recommendation_reasons)
        )

    full_name = f"{schema}.{table}"
    async with AsyncTaskSessionLocal() as session:
        await session.execute(
            text(
                f"""
                SELECT set_chunk_time_interval('{full_name}', INTERVAL '{chunk_interval_days} days')
                """
            )
        )
        await session.execute(
            text(
                f"""
                ALTER TABLE {full_name}
                SET (
                    timescaledb.compress,
                    timescaledb.compress_segmentby = 'instrument_id',
                    timescaledb.compress_orderby = 'trade_date DESC'
                )
                """
            )
        )
        await session.execute(
            text(
                f"""
                SELECT remove_compression_policy('{full_name}', if_exists => TRUE)
                """
            )
        )
        await session.execute(
            text(
                f"""
                SELECT add_compression_policy('{full_name}', compress_after => INTERVAL '{compress_after_days} days')
                """
            )
        )
        await session.commit()

    return await collect_prices_audit(
        schema=schema,
        table=table,
        compress_after_days=compress_after_days,
        min_rows_for_compression=min_rows_for_compression,
        min_size_bytes_for_compression=min_size_bytes_for_compression,
    )


async def async_main(args: argparse.Namespace) -> int:
    if args.apply:
        audit = await apply_prices_tuning(
            schema=args.schema,
            table=args.table,
            chunk_interval_days=args.chunk_interval_days,
            compress_after_days=args.compress_after_days,
            min_rows_for_compression=args.min_rows_for_compression,
            min_size_bytes_for_compression=args.min_size_bytes_for_compression,
        )
    else:
        audit = await collect_prices_audit(
            schema=args.schema,
            table=args.table,
            compress_after_days=args.compress_after_days,
            min_rows_for_compression=args.min_rows_for_compression,
            min_size_bytes_for_compression=args.min_size_bytes_for_compression,
        )

    if args.json:
        print(json.dumps(asdict(audit), indent=2, sort_keys=True))
    else:
        print(f"Timescale enabled: {audit.timescaledb_enabled}")
        print(f"Hypertable: {audit.is_hypertable}")
        print(f"Compression enabled: {audit.compression_enabled}")
        print(f"Chunk interval: {audit.chunk_interval}")
        print(f"Compression orderby: {audit.compression_orderby}")
        print(f"Compression segmentby: {audit.compression_segmentby}")
        print(f"Jobs: {audit.jobs or '<none>'}")
        print(
            f"Rows={audit.row_count} Instruments={audit.instrument_count} "
            f"Range={audit.min_trade_date}..{audit.max_trade_date} Size={audit.total_size_pretty}"
        )
        if audit.recommended_for_compression:
            print("Compression recommendation: ready")
        else:
            print("Compression recommendation: not ready")
            for reason in audit.recommendation_reasons:
                print(f"  - {reason}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--chunk-interval-days", type=int, default=DEFAULT_CHUNK_INTERVAL_DAYS)
    parser.add_argument("--compress-after-days", type=int, default=DEFAULT_COMPRESS_AFTER_DAYS)
    parser.add_argument("--min-rows-for-compression", type=int, default=DEFAULT_MIN_ROWS_FOR_COMPRESSION)
    parser.add_argument(
        "--min-size-bytes-for-compression",
        type=int,
        default=DEFAULT_MIN_SIZE_BYTES_FOR_COMPRESSION,
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(async_main(build_parser().parse_args())))
