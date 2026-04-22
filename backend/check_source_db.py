"""Verify that the configured source database is populated and production-like."""

from __future__ import annotations

import sys
from textwrap import dedent

import psycopg2

from app.core.config import settings


def host_kind(host: str) -> str:
    lowered = (host or "").lower()
    if lowered in {"localhost", "127.0.0.1"}:
        return "local"
    if "neon" in lowered:
        return "neon"
    return "other"


def main() -> int:
    url = settings.sync_database_url.replace("+psycopg2", "")
    conn = psycopg2.connect(url)
    cur = conn.cursor()

    cur.execute(
        dedent(
            """
            select
              (select count(*) from consensus_app.instruments) as instruments,
              (select count(*) from consensus_app.prices) as prices,
              (select count(*) from consensus_app.fundamentals_annual) as annuals,
              (select count(*) from consensus_app.fundamentals_quarterly) as quarterlies,
              (select count(*) from consensus_app.strategy_scores) as strategy_scores,
              (select count(*) from consensus_app.consensus_scores) as consensus_scores
            """
        )
    )
    counts = cur.fetchone()

    cur.execute(
        dedent(
            """
            select market, count(*)
            from consensus_app.instruments
            where is_active = true
            group by market
            order by market
            """
        )
    )
    active_market_counts = cur.fetchall()

    cur.execute(
        dedent(
            """
            select i.market, count(*)
            from consensus_app.consensus_scores cs
            join consensus_app.instruments i on i.id = cs.instrument_id
            group by i.market
            order by i.market
            """
        )
    )
    ranked_market_counts = cur.fetchall()

    cur.execute(
        dedent(
            """
            select ticker, market, asset_type
            from consensus_app.instruments
            where ticker in ('NVDA', '005930', 'SPY', '069500')
            order by market, ticker
            """
        )
    )
    ticker_checks = cur.fetchall()

    cur.execute(
        dedent(
            """
            select i.ticker, count(*) as bars, min(p.trade_date), max(p.trade_date)
            from consensus_app.prices p
            join consensus_app.instruments i on i.id = p.instrument_id
            where i.ticker in ('NVDA', '005930', 'SPY', '069500')
            group by i.ticker
            order by i.ticker
            """
        )
    )
    price_checks = cur.fetchall()

    conn.close()

    print(f"Configured DB host: {settings.postgres_host} [{host_kind(settings.postgres_host)}]")
    print(f"Configured pooler: {settings.postgres_host_pooler or '<none>'}")
    print()
    print("Core row counts:")
    print(
        f"  instruments={counts[0]} prices={counts[1]} annuals={counts[2]} "
        f"quarterlies={counts[3]} strategy_scores={counts[4]} consensus_scores={counts[5]}"
    )
    print()
    print("Active instruments by market:")
    for market, total in active_market_counts:
        print(f"  {market}: {total}")
    print()
    print("Ranked instruments by market:")
    for market, total in ranked_market_counts:
        print(f"  {market}: {total}")
    print()
    print("Benchmark/sample ticker presence:")
    for ticker, market, asset_type in ticker_checks:
        print(f"  {ticker} ({market}, {asset_type})")
    print()
    print("Benchmark/sample price coverage:")
    for ticker, bars, min_date, max_date in price_checks:
        print(f"  {ticker}: bars={bars}, range={min_date} -> {max_date}")

    missing_tickers = {"NVDA", "005930", "SPY", "069500"} - {row[0] for row in ticker_checks}
    if counts[0] == 0 or counts[1] == 0 or missing_tickers:
        print()
        print("Source DB verification failed.")
        if counts[0] == 0 or counts[1] == 0:
            print("  Expected a populated database but instruments/prices are empty.")
        if missing_tickers:
            print(f"  Missing expected representative tickers: {', '.join(sorted(missing_tickers))}")
        return 1

    print()
    print("Source DB verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
