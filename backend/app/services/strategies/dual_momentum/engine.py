"""
Dual Momentum Engine
=====================
Based on Gary Antonacci's Dual Momentum strategy.
Tests two independent momentum conditions:

  Absolute Momentum: stock's 12-month return > risk-free rate
  Relative Momentum: stock's 12-month return > benchmark index return

Additional signal — all-positive momentum:
  ret_12m > 0  AND  ret_6m > 0  AND  ret_3m > 0

Scoring (0-100):
  abs + rel + all_positive → 100
  abs + rel                → 85
  abs + all_positive       → 70
  abs only                 → 50
  rel only                 → 30
  neither                  → 0
  +10 if ret_3m > ret_6m > ret_12m (accelerating momentum)
  Clamp [0, 100]

Risk-free rates:
  US:  FRED DGS3MO (3-month T-bill) — fetched live or from cache
  KR:  Bank of Korea base rate       — fetched live or from cache

Benchmark:
  US:  S&P 500 (SPY proxy from prices table, ticker='SPY')
  KR:  KOSPI index (ticker='069500' — KODEX 200 ETF or '^KS11')
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

import httpx
from sqlalchemy import select, desc

from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.price import Price
from app.models.strategy_score import StrategyScore

logger = logging.getLogger(__name__)

# Minimum bars for reliable momentum computation
MIN_BARS_12M = 240   # ~12 months
MIN_BARS_6M  = 120   # ~6 months
MIN_BARS_3M  = 60    # ~3 months

# Benchmark tickers (must exist in the prices table)
BENCHMARK_TICKER = {
    "US": "SPY",
    "KR": "069500",  # KODEX 200 (KOSPI large-cap ETF)
}

# ── Risk-free rate fetchers ──────────────────────────────────────────────────

async def fetch_us_risk_free_rate() -> Optional[float]:
    """
    Fetch the latest 3-month US T-bill yield from FRED (DGS3MO).
    Returns the annualised yield as a decimal (e.g. 0.053 for 5.3%).
    Falls back to a conservative default if the request fails.
    """
    try:
        url = (
            "https://fred.stlouisfed.org/graph/fredgraph.csv"
            "?id=DGS3MO&vintage_date=&realtime_start=&realtime_end="
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            lines = resp.text.strip().splitlines()
            # CSV header: DATE,DGS3MO
            for line in reversed(lines[1:]):
                parts = line.split(",")
                if len(parts) == 2 and parts[1].strip() not in ("", "."):
                    return float(parts[1].strip()) / 100.0
    except Exception as exc:
        logger.warning("FRED DGS3MO fetch failed: %s — using default 5%%", exc)
    return 0.05  # conservative default


async def fetch_kr_risk_free_rate() -> Optional[float]:
    """
    Fetch the Bank of Korea base rate.
    BOK provides a JSON API; falls back to 3.5% if unavailable.
    """
    try:
        url = (
            "https://ecos.bok.or.kr/api/StatisticSearch/"
            "sample/json/kr/1/1/722Y001/D/20230101/20251231/?/?//?//?//?/"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            data = resp.json()
            rows = data.get("StatisticSearch", {}).get("row", [])
            if rows:
                return float(rows[-1]["DATA_VALUE"]) / 100.0
    except Exception as exc:
        logger.warning("BOK rate fetch failed: %s — using default 3.5%%", exc)
    return 0.035


# ── Core computation ─────────────────────────────────────────────────────────

def compute_dual_momentum(
    closes: list[float],
    benchmark_closes: list[float],
    risk_free_12m: float,
) -> tuple[float, bool, bool, dict]:
    """
    Compute Dual Momentum score from price history.

    Args:
        closes:           Instrument close prices (oldest first, ≥240 bars preferred).
        benchmark_closes: Benchmark close prices over same window.
        risk_free_12m:    12-month equivalent risk-free rate as decimal.

    Returns:
        (score_0_100, abs_mom_pass, rel_mom_pass, detail_dict)
    """
    n = len(closes)
    nb = len(benchmark_closes)

    # ── Compute returns ───────────────────────────────────────────────────────
    ret_12m: Optional[float] = None
    if n >= MIN_BARS_12M and closes[-MIN_BARS_12M] > 0:
        ret_12m = (closes[-1] / closes[-MIN_BARS_12M]) - 1.0

    ret_6m: Optional[float] = None
    if n >= MIN_BARS_6M and closes[-MIN_BARS_6M] > 0:
        ret_6m = (closes[-1] / closes[-MIN_BARS_6M]) - 1.0

    ret_3m: Optional[float] = None
    if n >= MIN_BARS_3M and closes[-MIN_BARS_3M] > 0:
        ret_3m = (closes[-1] / closes[-MIN_BARS_3M]) - 1.0

    # ── Benchmark 12-month return ─────────────────────────────────────────────
    benchmark_ret_12m: Optional[float] = None
    if nb >= MIN_BARS_12M and benchmark_closes[-MIN_BARS_12M] > 0:
        benchmark_ret_12m = (benchmark_closes[-1] / benchmark_closes[-MIN_BARS_12M]) - 1.0

    if ret_12m is None:
        return 0.0, False, False, {"error": "insufficient price history for 12-month return"}

    # ── Momentum tests ────────────────────────────────────────────────────────
    abs_mom = ret_12m > risk_free_12m
    rel_mom = (benchmark_ret_12m is not None and ret_12m > benchmark_ret_12m)
    all_positive = (
        ret_12m is not None and ret_12m > 0
        and ret_6m  is not None and ret_6m  > 0
        and ret_3m  is not None and ret_3m  > 0
    )

    # ── Score lookup ──────────────────────────────────────────────────────────
    if abs_mom and rel_mom and all_positive:
        base = 100
    elif abs_mom and rel_mom:
        base = 85
    elif abs_mom and all_positive:
        base = 70
    elif abs_mom:
        base = 50
    elif rel_mom:
        base = 30
    else:
        base = 0

    # Accelerating momentum bonus
    bonus = 0
    if (ret_3m is not None and ret_6m is not None and ret_12m is not None
            and ret_3m > ret_6m > ret_12m):
        bonus = 10

    score = float(min(100, base + bonus))

    detail = {
        "ret_12m":           round(ret_12m, 4) if ret_12m is not None else None,
        "ret_6m":            round(ret_6m,  4) if ret_6m  is not None else None,
        "ret_3m":            round(ret_3m,  4) if ret_3m  is not None else None,
        "benchmark_ret_12m": round(benchmark_ret_12m, 4) if benchmark_ret_12m is not None else None,
        "risk_free_12m":     round(risk_free_12m, 4),
        "abs_momentum":      abs_mom,
        "rel_momentum":      rel_mom,
        "all_positive":      all_positive,
        "bonus":             bonus,
    }

    return score, abs_mom, rel_mom, detail


# ── Per-instrument scorer ────────────────────────────────────────────────────

async def score_instrument(
    instrument_id: int,
    score_date: date,
    db,
    benchmark_closes_by_market: dict[str, list[float]],
    risk_free_by_market: dict[str, float],
    instrument_market: str,
) -> Optional[dict]:
    """Compute Dual Momentum score for one instrument."""
    price_q = await db.execute(
        select(Price)
        .where(
            Price.instrument_id == instrument_id,
            Price.trade_date <= score_date,
        )
        .order_by(desc(Price.trade_date))
        .limit(260)
    )
    price_rows = list(reversed(price_q.scalars().all()))

    if len(price_rows) < MIN_BARS_3M:
        return None

    closes = [float(p.close) for p in price_rows if p.close is not None]
    benchmark_closes = benchmark_closes_by_market.get(instrument_market, [])
    risk_free = risk_free_by_market.get(instrument_market, 0.05)

    score, abs_mom, rel_mom, detail = compute_dual_momentum(
        closes, benchmark_closes, risk_free
    )

    return {
        "instrument_id": instrument_id,
        "score_date":    score_date,
        "dual_mom_score": round(score, 2),
        "dual_mom_abs":   abs_mom,
        "dual_mom_rel":   rel_mom,
        "dual_mom_detail": detail,
    }


# ── Batch runner ─────────────────────────────────────────────────────────────

async def run_dual_momentum_scoring(
    score_date: Optional[date] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> list[dict]:
    """Run Dual Momentum scoring for a batch of instruments."""
    if score_date is None:
        score_date = date.today()

    # Fetch risk-free rates concurrently
    us_rf, kr_rf = await asyncio.gather(
        fetch_us_risk_free_rate(),
        fetch_kr_risk_free_rate(),
    )
    risk_free_by_market = {"US": us_rf or 0.05, "KR": kr_rf or 0.035}
    logger.info("Risk-free rates — US: %.2f%% | KR: %.2f%%",
                risk_free_by_market["US"] * 100, risk_free_by_market["KR"] * 100)

    async with AsyncSessionLocal() as db:
        # ── Load benchmark closes ─────────────────────────────────────────────
        benchmark_closes_by_market: dict[str, list[float]] = {}
        for mkt, ticker in BENCHMARK_TICKER.items():
            if market and mkt != market:
                continue
            bm_q = await db.execute(
                select(Price.close)
                .join(Instrument, Instrument.id == Price.instrument_id)
                .where(
                    Instrument.ticker == ticker,
                    Price.trade_date <= score_date,
                )
                .order_by(desc(Price.trade_date))
                .limit(260)
            )
            bm_closes = list(reversed([float(r[0]) for r in bm_q.all() if r[0] is not None]))
            benchmark_closes_by_market[mkt] = bm_closes
            logger.info("Benchmark %s (%s): %d bars loaded", ticker, mkt, len(bm_closes))

        # ── Fetch target instruments ──────────────────────────────────────────
        stmt = select(Instrument.id, Instrument.market).where(Instrument.is_active == True)
        if market:
            stmt = stmt.where(Instrument.market == market)
        if instrument_ids:
            stmt = stmt.where(Instrument.id.in_(instrument_ids))
        result = await db.execute(stmt)
        rows = result.all()
        ids = [r[0] for r in rows]
        market_by_id = {r[0]: r[1] for r in rows}

        logger.info("Dual Momentum scoring %d instruments for %s", len(ids), score_date)

        results = []
        for inst_id in ids:
            try:
                inst_market = market_by_id[inst_id]
                scored = await score_instrument(
                    inst_id, score_date, db,
                    benchmark_closes_by_market=benchmark_closes_by_market,
                    risk_free_by_market=risk_free_by_market,
                    instrument_market=inst_market,
                )
                if scored is None:
                    continue

                existing_q = await db.execute(
                    select(StrategyScore).where(
                        StrategyScore.instrument_id == inst_id,
                        StrategyScore.score_date == score_date,
                    )
                )
                existing = existing_q.scalars().first()

                if existing:
                    existing.dual_mom_score  = scored["dual_mom_score"]
                    existing.dual_mom_abs    = scored["dual_mom_abs"]
                    existing.dual_mom_rel    = scored["dual_mom_rel"]
                    existing.dual_mom_detail = scored["dual_mom_detail"]
                else:
                    db.add(StrategyScore(
                        instrument_id  = inst_id,
                        score_date     = score_date,
                        dual_mom_score = scored["dual_mom_score"],
                        dual_mom_abs   = scored["dual_mom_abs"],
                        dual_mom_rel   = scored["dual_mom_rel"],
                        dual_mom_detail = scored["dual_mom_detail"],
                    ))

                results.append(scored)

            except Exception as exc:
                logger.error("Dual Momentum failed for instrument %s: %s", inst_id, exc)

        await db.commit()
        logger.info("Dual Momentum scoring complete: %d/%d scored", len(results), len(ids))

    return results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    market_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_dual_momentum_scoring(market=market_arg))
