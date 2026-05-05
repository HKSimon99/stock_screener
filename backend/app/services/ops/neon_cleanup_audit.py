from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy import text

from app.core.database import AsyncSessionLocal


AUDIT_SQL: dict[str, str] = {
    "instrument_asset_counts": """
        select asset_type, count(*)::int
        from consensus_app.instruments
        group by asset_type
        order by count(*) desc
    """,
    "legacy_etf_instruments": """
        select count(*)::int
        from consensus_app.instruments
        where asset_type = 'etf'
    """,
    "etf_dependent_prices": """
        select count(*)::int
        from consensus_app.prices p
        join consensus_app.instruments i on i.id = p.instrument_id
        where i.asset_type = 'etf'
    """,
    "etf_dependent_strategy_scores": """
        select count(*)::int
        from consensus_app.strategy_scores ss
        join consensus_app.instruments i on i.id = ss.instrument_id
        where i.asset_type = 'etf'
    """,
    "etf_dependent_consensus_scores": """
        select count(*)::int
        from consensus_app.consensus_scores cs
        join consensus_app.instruments i on i.id = cs.instrument_id
        where i.asset_type = 'etf'
    """,
    "etf_dependent_fundamentals_annual": """
        select count(*)::int
        from consensus_app.fundamentals_annual fa
        join consensus_app.instruments i on i.id = fa.instrument_id
        where i.asset_type = 'etf'
    """,
    "etf_dependent_fundamentals_quarterly": """
        select count(*)::int
        from consensus_app.fundamentals_quarterly fq
        join consensus_app.instruments i on i.id = fq.instrument_id
        where i.asset_type = 'etf'
    """,
    "stock_magic_formula_latest_coverage": """
        with latest as (
            select i.market, max(ss.score_date) as score_date
            from consensus_app.strategy_scores ss
            join consensus_app.instruments i on i.id = ss.instrument_id
            where i.asset_type = 'stock'
            group by i.market
        )
        select l.market,
               l.score_date,
               count(*)::int as rows,
               count(*) filter (where ss.magic_formula_score is not null)::int as magic_formula_rows,
               count(*) filter (where ss.piotroski_score is not null)::int as piotroski_rows
        from latest l
        join consensus_app.strategy_scores ss on ss.score_date = l.score_date
        join consensus_app.instruments i
          on i.id = ss.instrument_id
         and i.market = l.market
         and i.asset_type = 'stock'
        group by l.market, l.score_date
        order by l.market
    """,
}


async def run_neon_cleanup_audit() -> dict[str, Any]:
    """
    Read-only preflight for phased Neon cleanup.

    This intentionally does not delete rows or issue DDL. Use the counts to
    build a separate migration/deletion runbook after confirming dependencies.
    """
    report: dict[str, Any] = {}
    async with AsyncSessionLocal() as db:
        await db.execute(text("set statement_timeout = '10000ms'"))
        for name, sql in AUDIT_SQL.items():
            result = await db.execute(text(sql))
            rows = [dict(row._mapping) for row in result.fetchall()]
            report[name] = rows
    return report


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_neon_cleanup_audit()), indent=2, default=str))

