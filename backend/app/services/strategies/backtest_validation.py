"""
Early Backtesting Validation (Phase 2.6)
=========================================
Run CANSLIM + Piotroski scoring over 6 months of historical data,
then measure forward 3-month returns for top-scoring vs bottom-scoring
instruments to verify meaningful signal.

Usage:
    python -m app.services.strategies.backtest_validation [--market US|KR]
"""

import logging
from datetime import date, timedelta
from typing import Optional
import statistics

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.price import Price

from app.services.strategies.canslim.engine import (
    build_market_rs_lookup,
    score_instrument as canslim_score_instrument,
)
from app.services.strategies.piotroski.engine import score_instrument as piotroski_score_instrument

logger = logging.getLogger(__name__)

DEFAULT_FORWARD_WINDOWS = {
    "1m": 21,
    "3m": 63,
    "6m": 126,
    "12m": 252,
}

BENCHMARK_TICKERS = {
    "US": "SPY",
    "KR": "069500",
}


async def _run_full_scoring_pipeline(
    score_date: str,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    """Lazy import wrapper to avoid a module import cycle with scoring_tasks."""
    from app.tasks.scoring_tasks import run_full_scoring_pipeline

    return await run_full_scoring_pipeline(
        score_date=score_date,
        market=market,
        instrument_ids=instrument_ids,
    )


async def _get_forward_return(
    instrument_id: int,
    start_date: date,
    days_forward: int,
    db,
) -> Optional[float]:
    """
    Compute the return from start_date over the next `days_forward` trading days.
    Returns the percentage return, or None if data is insufficient.
    """
    prices_q = await db.execute(
        select(Price)
        .where(
            Price.instrument_id == instrument_id,
            Price.trade_date >= start_date,
        )
        .order_by(Price.trade_date)
        .limit(days_forward + 1)
    )
    prices = prices_q.scalars().all()

    if len(prices) < 2:
        return None

    start_price = float(prices[0].close) if prices[0].close else None
    end_price = float(prices[-1].close) if prices[-1].close else None

    if start_price is None or end_price is None or start_price <= 0:
        return None

    return (end_price - start_price) / start_price


def _calculate_max_drawdown(closes: list[float]) -> float:
    """Return the worst drawdown over the supplied close series."""
    if not closes:
        return 0.0

    peak = closes[0]
    max_drawdown = 0.0
    for close in closes:
        peak = max(peak, close)
        if peak <= 0:
            continue
        drawdown = close / peak - 1.0
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown


async def _get_forward_path_metrics(
    instrument_id: int,
    start_date: date,
    days_forward: int,
    db,
) -> Optional[dict]:
    """
    Compute total return and max drawdown over the next `days_forward` trading bars.
    """
    prices_q = await db.execute(
        select(Price)
        .where(
            Price.instrument_id == instrument_id,
            Price.trade_date >= start_date,
        )
        .order_by(Price.trade_date)
        .limit(days_forward + 1)
    )
    prices = prices_q.scalars().all()

    if len(prices) < 2:
        return None

    closes = [float(price.close) for price in prices if price.close is not None]
    if len(closes) < 2 or closes[0] <= 0:
        return None

    total_return = (closes[-1] - closes[0]) / closes[0]
    return {
        "return": total_return,
        "max_drawdown": _calculate_max_drawdown(closes),
        "bars": len(closes),
    }


async def _get_benchmark_returns(
    market: str,
    start_date: date,
    forward_windows: dict[str, int],
    db,
) -> dict[str, Optional[float]]:
    """Fetch benchmark forward returns for a market, keyed by window label."""
    benchmark_ticker = BENCHMARK_TICKERS.get(market)
    if not benchmark_ticker:
        return {label: None for label in forward_windows}

    benchmark_q = await db.execute(
        select(Instrument.id)
        .where(
            Instrument.market == market,
            Instrument.ticker == benchmark_ticker,
            Instrument.is_active.is_(True),
        )
        .limit(1)
    )
    benchmark_id = benchmark_q.scalar_one_or_none()
    if benchmark_id is None:
        return {label: None for label in forward_windows}

    benchmark_returns: dict[str, Optional[float]] = {}
    for label, days_forward in forward_windows.items():
        metrics = await _get_forward_path_metrics(benchmark_id, start_date, days_forward, db)
        benchmark_returns[label] = None if metrics is None else metrics["return"]
    return benchmark_returns


def _summarize_consensus_groups(
    rows: list[dict],
    forward_windows: dict[str, int],
    benchmark_returns: dict[str, Optional[float]],
) -> dict:
    """Aggregate consensus backtest outcomes by conviction level."""
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["conviction_level"], []).append(row)

    summary: dict[str, dict] = {}
    conviction_order = ["DIAMOND", "GOLD", "SILVER", "BRONZE", "UNRANKED"]
    for conviction_level in conviction_order:
        group_rows = grouped.get(conviction_level, [])
        if not group_rows:
            continue

        horizons: dict[str, dict] = {}
        for label in forward_windows:
            valid_rows = [row for row in group_rows if row["forward_metrics"].get(label) is not None]
            if not valid_rows:
                horizons[label] = {
                    "n": 0,
                    "avg_return_pct": None,
                    "avg_excess_return_pct": None,
                    "avg_max_drawdown_pct": None,
                    "hit_rate": None,
                    "benchmark_return_pct": None if benchmark_returns.get(label) is None else round(float(benchmark_returns[label]) * 100, 2),
                }
                continue

            returns = [row["forward_metrics"][label]["return"] for row in valid_rows]
            drawdowns = [row["forward_metrics"][label]["max_drawdown"] for row in valid_rows]
            benchmark_return = benchmark_returns.get(label)
            excess_returns = [
                ret - benchmark_return
                for ret in returns
                if benchmark_return is not None
            ]

            horizons[label] = {
                "n": len(valid_rows),
                "avg_return_pct": round(float(statistics.mean(returns)) * 100, 2),
                "avg_excess_return_pct": None if not excess_returns else round(float(statistics.mean(excess_returns)) * 100, 2),
                "avg_max_drawdown_pct": round(float(statistics.mean(drawdowns)) * 100, 2),
                "hit_rate": round(sum(1 for value in returns if value > 0) / len(returns) * 100, 1),
                "benchmark_return_pct": None if benchmark_return is None else round(float(benchmark_return) * 100, 2),
            }

        summary[conviction_level] = {
            "n": len(group_rows),
            "avg_final_score": round(float(statistics.mean(row["final_score"] for row in group_rows)), 2),
            "tickers": [row["ticker"] for row in sorted(group_rows, key=lambda item: item["final_score"], reverse=True)],
            "horizons": horizons,
        }

    return summary


async def run_backtest(
    market: Optional[str] = None,
    scoring_date: Optional[date] = None,
    forward_days: int = 63,  # ~3 months
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    """
    Score all instruments as-of scoring_date, then measure forward returns.
    Split into quintiles by score and compare returns.

    Args:
        market:       "US" or "KR"; None = both.
        scoring_date: Date to score as-of (default: 6 months ago).
        forward_days: Trading days to measure forward return (default: 63 ~3mo).

    Returns:
        Dict with quintile returns, hit rates, and summary stats.
    """
    if scoring_date is None:
        scoring_date = date.today() - timedelta(days=180)

    report: dict = {
        "scoring_date": str(scoring_date),
        "forward_days": forward_days,
        "market": market,
        "instrument_ids": instrument_ids,
        "canslim": {},
        "piotroski": {},
    }

    async with AsyncSessionLocal() as db:
        # Get active instruments
        stmt = select(Instrument).where(Instrument.is_active == True)
        if market:
            stmt = stmt.where(Instrument.market == market)
        if instrument_ids:
            stmt = stmt.where(Instrument.id.in_(instrument_ids))
        result = await db.execute(stmt)
        instruments = result.scalars().all()

        logger.info(
            f"Backtesting {len(instruments)} instruments, "
            f"scoring_date={scoring_date}, forward={forward_days}d"
        )

        rs_lookup_by_market: dict[str, dict[int, float]] = {}
        rs_4w_lookup_by_market: dict[str, dict[int, float]] = {}
        for market_name in sorted({inst.market for inst in instruments}):
            rs_lookup_by_market[market_name] = await build_market_rs_lookup(db, market_name, scoring_date)
            rs_4w_lookup_by_market[market_name] = await build_market_rs_lookup(
                db,
                market_name,
                scoring_date - timedelta(days=28),
            )

        # Score each instrument
        canslim_results: list[dict] = []
        piotroski_results: list[dict] = []

        for inst in instruments:
            try:
                cs = await canslim_score_instrument(
                    inst.id,
                    scoring_date,
                    db,
                    rs_lookup=rs_lookup_by_market.get(inst.market, {}),
                    rs_4w_lookup=rs_4w_lookup_by_market.get(inst.market, {}),
                )
                if cs:
                    fwd = await _get_forward_return(inst.id, scoring_date, forward_days, db)
                    if fwd is not None:
                        canslim_results.append({
                            "ticker": inst.ticker,
                            "score": cs["canslim_score"],
                            "forward_return": fwd,
                        })
            except Exception as e:
                logger.debug(f"CANSLIM backtest skip {inst.ticker}: {e}")

            try:
                ps = await piotroski_score_instrument(inst.id, scoring_date, db)
                if ps:
                    fwd = await _get_forward_return(inst.id, scoring_date, forward_days, db)
                    if fwd is not None:
                        piotroski_results.append({
                            "ticker": inst.ticker,
                            "score": ps["piotroski_score"],
                            "f_raw": ps["piotroski_f_raw"],
                            "forward_return": fwd,
                        })
            except Exception as e:
                logger.debug(f"Piotroski backtest skip {inst.ticker}: {e}")

        # Analyze quintiles
        report["canslim"] = _analyze_quintiles(canslim_results, "canslim")
        report["piotroski"] = _analyze_quintiles(piotroski_results, "piotroski")

    return report


def _summarize_single_strategy_quintiles(
    rows: list[dict],
    strategy_key: str,
    forward_windows: dict[str, int],
    benchmark_returns: dict[str, Optional[float]],
) -> dict:
    """Split instruments into quintiles by a single strategy score and summarise."""
    scored = [r for r in rows if r.get(strategy_key) is not None]
    if len(scored) < 5:
        return {"error": f"insufficient data ({len(scored)} instruments)", "n": len(scored)}

    sorted_rows = sorted(scored, key=lambda r: r[strategy_key])
    n = len(sorted_rows)
    q_size = n // 5

    quintiles: dict[str, dict] = {}
    for qi in range(5):
        start = qi * q_size
        end = (qi + 1) * q_size if qi < 4 else n
        group = sorted_rows[start:end]

        horizons: dict[str, dict] = {}
        for label in forward_windows:
            valid = [r for r in group if r["forward_metrics"].get(label) is not None]
            if not valid:
                horizons[label] = {"n": 0, "avg_return_pct": None, "hit_rate": None}
                continue
            returns = [r["forward_metrics"][label]["return"] for r in valid]
            benchmark_ret = benchmark_returns.get(label)
            excess = [ret - benchmark_ret for ret in returns] if benchmark_ret is not None else []
            horizons[label] = {
                "n": len(valid),
                "avg_return_pct": round(float(statistics.mean(returns)) * 100, 2),
                "avg_excess_return_pct": round(float(statistics.mean(excess)) * 100, 2) if excess else None,
                "hit_rate": round(sum(1 for v in returns if v > 0) / len(returns) * 100, 1),
            }

        scores = [r[strategy_key] for r in group]
        quintiles[f"Q{qi + 1}"] = {
            "n": len(group),
            "avg_score": round(float(statistics.mean(scores)), 2),
            "tickers": [r["ticker"] for r in group],
            "horizons": horizons,
        }

    # Spread: top quintile minus bottom quintile average return
    spread_by_horizon: dict[str, Optional[float]] = {}
    for label in forward_windows:
        top_ret = quintiles["Q5"]["horizons"].get(label, {}).get("avg_return_pct")
        bot_ret = quintiles["Q1"]["horizons"].get(label, {}).get("avg_return_pct")
        if top_ret is not None and bot_ret is not None:
            spread_by_horizon[label] = round(top_ret - bot_ret, 2)
        else:
            spread_by_horizon[label] = None

    return {
        "n_total": n,
        "quintiles": quintiles,
        "top_vs_bottom_spread_pct": spread_by_horizon,
    }


async def run_consensus_backtest(
    market: Optional[str] = None,
    scoring_date: Optional[date] = None,
    forward_windows: Optional[dict[str, int]] = None,
    instrument_ids: Optional[list[int]] = None,
) -> dict:
    """
    Replay the full consensus pipeline as-of `scoring_date`, then measure
    forward returns and drawdowns by conviction tier versus the market benchmark.

    Also includes single-strategy quintile comparisons (CANSLIM, Piotroski,
    Minervini, Weinstein, Dual Momentum) so the consensus advantage can be
    measured directly.
    """
    from app.models.strategy_score import StrategyScore

    if scoring_date is None:
        scoring_date = date.today() - timedelta(days=180)

    if forward_windows is None:
        forward_windows = DEFAULT_FORWARD_WINDOWS

    pipeline_result = await _run_full_scoring_pipeline(
        score_date=scoring_date.isoformat(),
        market=market,
        instrument_ids=instrument_ids,
    )

    report = {
        "scoring_date": scoring_date.isoformat(),
        "market": market,
        "instrument_ids": instrument_ids,
        "forward_windows": forward_windows,
        "pipeline": pipeline_result,
        "markets": {},
    }

    async with AsyncSessionLocal() as db:
        markets = [market] if market else ["US", "KR"]
        for market_name in markets:
            benchmark_returns = await _get_benchmark_returns(
                market_name,
                scoring_date,
                forward_windows,
                db,
            )

            scores_q = await db.execute(
                select(ConsensusScore, Instrument)
                .join(Instrument, Instrument.id == ConsensusScore.instrument_id)
                .where(
                    ConsensusScore.score_date == scoring_date,
                    Instrument.market == market_name,
                    Instrument.asset_type == "stock",
                    Instrument.is_active.is_(True),
                )
                .order_by(ConsensusScore.final_score.desc())
            )
            score_rows = scores_q.all()
            if instrument_ids:
                score_rows = [
                    row for row in score_rows
                    if row[1].id in instrument_ids
                ]

            # Fetch per-strategy scores for single-strategy comparison
            strategy_scores_map: dict[int, dict] = {}
            for consensus_score, instrument in score_rows:
                ss_q = await db.execute(
                    select(StrategyScore).where(
                        StrategyScore.instrument_id == instrument.id,
                        StrategyScore.score_date == scoring_date,
                    )
                )
                ss = ss_q.scalars().first()
                if ss:
                    strategy_scores_map[instrument.id] = {
                        "canslim_score": float(ss.canslim_score) if ss.canslim_score is not None else None,
                        "piotroski_score": float(ss.piotroski_score) if ss.piotroski_score is not None else None,
                        "minervini_score": float(ss.minervini_score) if ss.minervini_score is not None else None,
                        "weinstein_score": float(ss.weinstein_score) if ss.weinstein_score is not None else None,
                        "dual_mom_score": float(ss.dual_mom_score) if ss.dual_mom_score is not None else None,
                    }

            rows: list[dict] = []
            for consensus_score, instrument in score_rows:
                metrics_by_window: dict[str, Optional[dict]] = {}
                for label, days_forward in forward_windows.items():
                    metrics_by_window[label] = await _get_forward_path_metrics(
                        instrument.id,
                        scoring_date,
                        days_forward,
                        db,
                    )

                row_data = {
                    "instrument_id": instrument.id,
                    "ticker": instrument.ticker,
                    "conviction_level": consensus_score.conviction_level,
                    "final_score": float(consensus_score.final_score),
                    "forward_metrics": metrics_by_window,
                }
                # Merge per-strategy scores for single-strategy quintile analysis
                row_data.update(strategy_scores_map.get(instrument.id, {}))
                rows.append(row_data)

            # Single-strategy quintile comparisons
            strategy_comparisons: dict[str, dict] = {}
            for strategy_key in ["canslim_score", "piotroski_score", "minervini_score", "weinstein_score", "dual_mom_score"]:
                strategy_comparisons[strategy_key.replace("_score", "")] = _summarize_single_strategy_quintiles(
                    rows, strategy_key, forward_windows, benchmark_returns,
                )

            report["markets"][market_name] = {
                "benchmark_ticker": BENCHMARK_TICKERS.get(market_name),
                "benchmark_returns_pct": {
                    label: None if value is None else round(float(value) * 100, 2)
                    for label, value in benchmark_returns.items()
                },
                "n_scored": len(rows),
                "conviction_groups": _summarize_consensus_groups(
                    rows,
                    forward_windows,
                    benchmark_returns,
                ),
                "single_strategy_quintiles": strategy_comparisons,
            }

    return report


def _analyze_quintiles(results: list[dict], strategy_name: str) -> dict:
    """Split results into quintiles by score and compute return statistics."""
    if len(results) < 5:
        return {"error": f"insufficient data ({len(results)} instruments)", "n": len(results)}

    sorted_results = sorted(results, key=lambda x: x["score"])
    n = len(sorted_results)
    q_size = n // 5

    quintiles = {}
    for qi in range(5):
        start = qi * q_size
        end = (qi + 1) * q_size if qi < 4 else n
        group = sorted_results[start:end]

        returns = [r["forward_return"] for r in group]
        scores = [r["score"] for r in group]

        quintiles[f"Q{qi + 1}"] = {
            "n": len(group),
            "avg_score": round(float(statistics.mean(scores)), 2),
            "avg_return": round(float(statistics.mean(returns)) * 100, 2),
            "median_return": round(float(statistics.median(returns)) * 100, 2),
            "hit_rate": round(sum(1 for r in returns if r > 0) / len(returns) * 100, 1),
            "max_return": round(float(max(returns)) * 100, 2),
            "min_return": round(float(min(returns)) * 100, 2),
        }

    # Top quintile vs bottom quintile spread
    top = quintiles["Q5"]
    bot = quintiles["Q1"]
    spread = top["avg_return"] - bot["avg_return"]

    return {
        "n_total": n,
        "quintiles": quintiles,
        "top_vs_bottom_spread_pct": round(spread, 2),
        "signal_positive": spread > 0,
        "top_quintile_tickers": [r["ticker"] for r in sorted_results[-q_size:]],
        "bottom_quintile_tickers": [r["ticker"] for r in sorted_results[:q_size]],
    }


def print_report(report: dict):
    """Pretty-print the backtest report."""
    print(f"\n{'='*70}")
    print(f"BACKTEST REPORT - Scoring Date: {report['scoring_date']}")
    print(f"Forward Period: {report['forward_days']} trading days")
    print(f"Market: {report['market'] or 'ALL'}")
    if report.get("instrument_ids"):
        print(f"Instrument IDs: {', '.join(str(inst_id) for inst_id in report['instrument_ids'])}")
    print(f"{'='*70}")

    for strategy in ("canslim", "piotroski"):
        data = report[strategy]
        print(f"\n--- {strategy.upper()} ---")

        if "error" in data:
            print(f"  {data['error']}")
            continue

        print(f"  Total instruments scored: {data['n_total']}")
        print(f"  Top vs Bottom quintile spread: {data['top_vs_bottom_spread_pct']:+.2f}%")
        print(f"  Signal positive: {'YES' if data['signal_positive'] else 'NO'}")
        print()
        print(f"  {'Quintile':<10} {'N':>4} {'Avg Score':>10} {'Avg Ret%':>10} {'Med Ret%':>10} {'Hit Rate':>10}")
        print(f"  {'-'*54}")
        for qname, qdata in data["quintiles"].items():
            print(
                f"  {qname:<10} {qdata['n']:>4} "
                f"{qdata['avg_score']:>10.1f} "
                f"{qdata['avg_return']:>+10.2f} "
                f"{qdata['median_return']:>+10.2f} "
                f"{qdata['hit_rate']:>9.1f}%"
            )

        print(f"\n  Top quintile tickers: {', '.join(data['top_quintile_tickers'][:10])}")
        print(f"  Bottom quintile tickers: {', '.join(data['bottom_quintile_tickers'][:10])}")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    market_arg = None
    instrument_ids_arg = None
    for arg in sys.argv[1:]:
        if arg.startswith("--market="):
            market_arg = arg.split("=")[1]
        elif arg.startswith("--instrument-ids="):
            raw_ids = arg.split("=", 1)[1]
            instrument_ids_arg = [int(item) for item in raw_ids.split(",") if item]
        elif arg in ("US", "KR"):
            market_arg = arg

    import asyncio

    report = asyncio.run(run_backtest(market=market_arg, instrument_ids=instrument_ids_arg))
    print_report(report)
