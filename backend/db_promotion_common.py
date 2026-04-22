from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import psycopg2
from sqlalchemy.engine import make_url


CORE_TABLES = (
    "instruments",
    "prices",
    "fundamentals_annual",
    "fundamentals_quarterly",
    "strategy_scores",
    "consensus_scores",
    "instrument_coverage_summary",
)
DEFAULT_SAMPLE_TICKERS = ("NVDA", "005930", "SPY", "069500")


@dataclass(slots=True)
class DbSummary:
    host: str
    database: str
    schema: str
    counts: dict[str, int | None]
    active_by_market: dict[str, int]
    latest_strategy_score_date: str | None
    latest_consensus_score_date: str | None
    latest_strategy_score_by_market: dict[str, str]
    latest_consensus_score_by_market: dict[str, str]
    sample_tickers: dict[str, dict[str, Any]]
    sample_price_coverage: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_postgres_url(raw_url: str) -> str:
    url = make_url(raw_url)
    if "+" in url.drivername:
        url = url.set(drivername=url.drivername.split("+", 1)[0])
    return url.render_as_string(hide_password=False)


def connect(url: str):
    return psycopg2.connect(normalize_postgres_url(url))


def parsed_url(url: str):
    normalized = normalize_postgres_url(url)
    return make_url(normalized)


def host_label(url: str) -> str:
    host = (parsed_url(url).host or "").lower()
    if host in {"localhost", "127.0.0.1"}:
        return "local"
    if "neon" in host:
        return "neon"
    return "other"


def is_pooled_neon_url(url: str) -> bool:
    host = (parsed_url(url).host or "").lower()
    return "neon" in host and "pooler" in host


def _fetch_one_value(cur, sql: str, params: tuple[Any, ...] = ()) -> Any:
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def _table_exists(cur, schema: str, table_name: str) -> bool:
    return bool(
        _fetch_one_value(
            cur,
            "select to_regclass(%s)",
            (f"{schema}.{table_name}",),
        )
    )


def collect_db_summary(
    url: str,
    *,
    schema: str = "consensus_app",
    sample_tickers: tuple[str, ...] = DEFAULT_SAMPLE_TICKERS,
) -> DbSummary:
    parsed = parsed_url(url)
    conn = connect(url)
    cur = conn.cursor()

    counts: dict[str, int | None] = {}
    for table_name in CORE_TABLES:
        if _table_exists(cur, schema, table_name):
            counts[table_name] = int(
                _fetch_one_value(cur, f"select count(*) from {schema}.{table_name}") or 0
            )
        else:
            counts[table_name] = None

    cur.execute(
        f"""
        select market, count(*)
        from {schema}.instruments
        where is_active = true
        group by market
        order by market
        """
    )
    active_by_market = {market: int(total) for market, total in cur.fetchall()}

    latest_strategy_score_date = _fetch_one_value(
        cur,
        f"select max(score_date)::text from {schema}.strategy_scores",
    )
    latest_consensus_score_date = _fetch_one_value(
        cur,
        f"select max(score_date)::text from {schema}.consensus_scores",
    )

    cur.execute(
        f"""
        select i.market, max(ss.score_date)::text
        from {schema}.strategy_scores ss
        join {schema}.instruments i on i.id = ss.instrument_id
        group by i.market
        order by i.market
        """
    )
    latest_strategy_score_by_market = {
        market: latest_date for market, latest_date in cur.fetchall() if latest_date is not None
    }

    cur.execute(
        f"""
        select i.market, max(cs.score_date)::text
        from {schema}.consensus_scores cs
        join {schema}.instruments i on i.id = cs.instrument_id
        group by i.market
        order by i.market
        """
    )
    latest_consensus_score_by_market = {
        market: latest_date for market, latest_date in cur.fetchall() if latest_date is not None
    }

    cur.execute(
        f"""
        select ticker, market, asset_type, is_active
        from {schema}.instruments
        where ticker = any(%s)
        order by market, ticker
        """,
        (list(sample_tickers),),
    )
    sample_tickers_map = {
        ticker: {
            "market": market,
            "asset_type": asset_type,
            "is_active": bool(is_active),
        }
        for ticker, market, asset_type, is_active in cur.fetchall()
    }

    cur.execute(
        f"""
        select i.ticker, count(*)::int, min(p.trade_date)::text, max(p.trade_date)::text
        from {schema}.prices p
        join {schema}.instruments i on i.id = p.instrument_id
        where i.ticker = any(%s)
        group by i.ticker
        order by i.ticker
        """,
        (list(sample_tickers),),
    )
    sample_price_coverage = {
        ticker: {
            "bars": bars,
            "min_trade_date": min_trade_date,
            "max_trade_date": max_trade_date,
        }
        for ticker, bars, min_trade_date, max_trade_date in cur.fetchall()
    }

    conn.close()
    return DbSummary(
        host=parsed.host or "",
        database=parsed.database or "",
        schema=schema,
        counts=counts,
        active_by_market=active_by_market,
        latest_strategy_score_date=latest_strategy_score_date,
        latest_consensus_score_date=latest_consensus_score_date,
        latest_strategy_score_by_market=latest_strategy_score_by_market,
        latest_consensus_score_by_market=latest_consensus_score_by_market,
        sample_tickers=sample_tickers_map,
        sample_price_coverage=sample_price_coverage,
    )


def compare_db_summaries(source: DbSummary, target: DbSummary) -> list[str]:
    mismatches: list[str] = []

    for table_name, source_count in source.counts.items():
        target_count = target.counts.get(table_name)
        if source_count != target_count:
            mismatches.append(
                f"table count mismatch for {table_name}: source={source_count} target={target_count}"
            )

    if source.active_by_market != target.active_by_market:
        mismatches.append(
            f"active instrument markets differ: source={source.active_by_market} target={target.active_by_market}"
        )

    if source.latest_strategy_score_date != target.latest_strategy_score_date:
        mismatches.append(
            "latest strategy score date mismatch: "
            f"source={source.latest_strategy_score_date} target={target.latest_strategy_score_date}"
        )
    if source.latest_consensus_score_date != target.latest_consensus_score_date:
        mismatches.append(
            "latest consensus score date mismatch: "
            f"source={source.latest_consensus_score_date} target={target.latest_consensus_score_date}"
        )

    if source.latest_strategy_score_by_market != target.latest_strategy_score_by_market:
        mismatches.append(
            "latest strategy score dates by market differ: "
            f"source={source.latest_strategy_score_by_market} "
            f"target={target.latest_strategy_score_by_market}"
        )
    if source.latest_consensus_score_by_market != target.latest_consensus_score_by_market:
        mismatches.append(
            "latest consensus score dates by market differ: "
            f"source={source.latest_consensus_score_by_market} "
            f"target={target.latest_consensus_score_by_market}"
        )

    all_tickers = sorted(set(source.sample_tickers) | set(target.sample_tickers))
    for ticker in all_tickers:
        if source.sample_tickers.get(ticker) != target.sample_tickers.get(ticker):
            mismatches.append(
                f"sample ticker mismatch for {ticker}: "
                f"source={source.sample_tickers.get(ticker)} target={target.sample_tickers.get(ticker)}"
            )
        if source.sample_price_coverage.get(ticker) != target.sample_price_coverage.get(ticker):
            mismatches.append(
                f"sample price coverage mismatch for {ticker}: "
                f"source={source.sample_price_coverage.get(ticker)} "
                f"target={target.sample_price_coverage.get(ticker)}"
            )

    return mismatches


def promotion_readiness_issues(summary: DbSummary) -> list[str]:
    issues: list[str] = []

    if not summary.counts.get("instruments"):
        issues.append("instruments table is empty")
    if not summary.counts.get("prices"):
        issues.append("prices table is empty")

    coverage_rows = summary.counts.get("instrument_coverage_summary")
    active_total = sum(summary.active_by_market.values())
    if coverage_rows is not None and coverage_rows != active_total:
        issues.append(
            "instrument_coverage_summary is out of sync: "
            f"coverage_rows={coverage_rows} active_instruments={active_total}"
        )

    missing_samples = sorted(set(DEFAULT_SAMPLE_TICKERS) - set(summary.sample_tickers))
    if missing_samples:
        issues.append(f"missing representative tickers: {', '.join(missing_samples)}")

    return issues


def print_db_summary(summary: DbSummary, *, label: str) -> None:
    print(f"[{label}] host={summary.host} database={summary.database} schema={summary.schema}")
    print("  Counts:")
    for table_name, count in summary.counts.items():
        print(f"    {table_name}: {count}")
    print(f"  Active by market: {summary.active_by_market}")
    print(
        "  Latest scores:"
        f" strategy={summary.latest_strategy_score_date}"
        f" consensus={summary.latest_consensus_score_date}"
    )
    print(f"  Latest strategy by market: {summary.latest_strategy_score_by_market}")
    print(f"  Latest consensus by market: {summary.latest_consensus_score_by_market}")
    print(f"  Sample tickers: {summary.sample_tickers}")
    print(f"  Sample price coverage: {summary.sample_price_coverage}")
