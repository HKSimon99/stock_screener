"""
Minervini Trend Template Engine
================================
8 binary criteria (T1-T8) that define a confirmed Stage 2 uptrend.
All criteria must pass for full score. Partial credit given below 8.

Criteria (from PLAN-FINAL §3.3):
  T1: close > sma_150
  T2: close > sma_200
  T3: sma_150 > sma_200          (bullish MA stack)
  T4: sma_200 today > sma_200_22d_ago  (200-day MA trending up ≥1 month)
  T5: close > sma_50
  T6: close >= low_52w * 1.25   (≥25% above 52-week low)
  T7: close >= high_52w * 0.75  (within 25% of 52-week high)
  T8: rs_rating >= 70           (relative strength)

Scoring:
  8/8 → 100 | 7/8 → 80 | 6/8 → 60 | 5/8 → 40 | 4/8 → 20 | <4 → 0
  Bonuses:
    +5 if rs_rating >= 90
    +5 if sma_50 > sma_150 > sma_200  (perfectly stacked)
    +5 if close > sma_21              (above short-term MA)
  Clamp [0, 100]
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, desc

from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.price import Price
from app.models.strategy_score import StrategyScore
from app.services.strategies.canslim.engine import build_market_rs_lookup

logger = logging.getLogger(__name__)

# Minimum bars needed: 200 for sma_200 + 22 extra for T4 + buffer
MIN_PRICE_BARS = 222

SCORE_TABLE = {8: 100, 7: 80, 6: 60, 5: 40, 4: 20}


def _sma(closes: list[float], period: int) -> Optional[float]:
    """Simple moving average of last `period` values."""
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def compute_minervini_score(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    rs_rating: Optional[float],
) -> tuple[float, int, dict]:
    """
    Evaluate 8 Minervini Trend Template criteria from price history.

    Args:
        closes: List of daily close prices (oldest first, ≥222 bars preferred).
        highs:  Parallel list of daily high prices (same length).
        lows:   Parallel list of daily low prices (same length).
        rs_rating: IBD-style RS rating for this instrument (1-99), or None.

    Returns:
        (score_0_100, criteria_passing_count, detail_dict)
    """
    n = len(closes)
    if n < 50:
        return 0.0, 0, {"error": "insufficient price data"}

    close = closes[-1]

    # ── Compute SMAs ────────────────────────────────────────────────────────
    sma_21  = _sma(closes, 21)
    sma_50  = _sma(closes, 50)
    sma_150 = _sma(closes, 150)
    sma_200 = _sma(closes, 200)

    # sma_200 from 22 trading days ago (for T4)
    sma_200_22d: Optional[float] = None
    if n >= 222:
        sma_200_22d = _sma(closes[:-22], 200)

    # ── 52-week high / low (last 252 bars) ───────────────────────────────────
    window_252 = min(n, 252)
    high_52w = max(highs[-window_252:]) if highs else None
    low_52w  = min(lows[-window_252:])  if lows  else None

    # ── Evaluate criteria ────────────────────────────────────────────────────
    t1 = bool(sma_150 is not None and close > sma_150)
    t2 = bool(sma_200 is not None and close > sma_200)
    t3 = bool(sma_150 is not None and sma_200 is not None and sma_150 > sma_200)
    t4 = bool(sma_200 is not None and sma_200_22d is not None and sma_200 > sma_200_22d)
    t5 = bool(sma_50 is not None and close > sma_50)
    t6 = bool(low_52w is not None and low_52w > 0 and close >= low_52w * 1.25)
    t7 = bool(high_52w is not None and high_52w > 0 and close >= high_52w * 0.75)
    t8 = bool(rs_rating is not None and rs_rating >= 70)

    criteria = [t1, t2, t3, t4, t5, t6, t7, t8]
    count = sum(criteria)

    # ── Base score ───────────────────────────────────────────────────────────
    base = SCORE_TABLE.get(count, 0)

    # ── Bonuses ──────────────────────────────────────────────────────────────
    bonus = 0
    if rs_rating is not None and rs_rating >= 90:
        bonus += 5
    if (sma_50 is not None and sma_150 is not None and sma_200 is not None
            and sma_50 > sma_150 > sma_200):
        bonus += 5
    if sma_21 is not None and close > sma_21:
        bonus += 5

    score = min(100.0, float(base + bonus))

    detail = {
        "T1_above_150ma":       {"pass": t1, "close": close, "sma_150": sma_150},
        "T2_above_200ma":       {"pass": t2, "close": close, "sma_200": sma_200},
        "T3_150ma_above_200ma": {"pass": t3, "sma_150": sma_150, "sma_200": sma_200},
        "T4_200ma_trending_up": {"pass": t4, "sma_200_now": sma_200, "sma_200_22d": sma_200_22d},
        "T5_above_50ma":        {"pass": t5, "close": close, "sma_50": sma_50},
        "T6_25pct_above_52w_low": {"pass": t6, "close": close, "low_52w": low_52w},
        "T7_within_25pct_52w_high": {"pass": t7, "close": close, "high_52w": high_52w},
        "T8_rs_rating_ge_70":   {"pass": t8, "rs_rating": rs_rating},
        "criteria_count":       count,
        "bonus":                bonus,
    }

    return score, count, detail


async def score_instrument(
    instrument_id: int,
    score_date: date,
    db,
    rs_lookup: Optional[dict[int, float]] = None,
) -> Optional[dict]:
    """
    Compute Minervini Trend Template score for one instrument.
    Returns None if price data is insufficient.
    """
    # Fetch price history (252+ bars for 52w range + sma_200 + 22d lookback)
    price_q = await db.execute(
        select(Price)
        .where(
            Price.instrument_id == instrument_id,
            Price.trade_date <= score_date,
        )
        .order_by(desc(Price.trade_date))
        .limit(260)
    )
    price_rows = list(reversed(price_q.scalars().all()))  # oldest first

    if len(price_rows) < MIN_PRICE_BARS:
        logger.debug(
            "Skipping Minervini for instrument %s: only %d bars (need %d)",
            instrument_id, len(price_rows), MIN_PRICE_BARS,
        )
        return None

    closes = [float(p.close) for p in price_rows if p.close is not None]
    highs  = [float(p.high)  for p in price_rows if p.high  is not None]
    lows   = [float(p.low)   for p in price_rows if p.low   is not None]

    # Use pre-built RS lookup if provided, otherwise look it up from strategy_scores
    rs_val: Optional[float] = None
    if rs_lookup is not None:
        rs_val = rs_lookup.get(instrument_id)
    else:
        # Fallback: read from latest strategy_scores row
        ss_q = await db.execute(
            select(StrategyScore.rs_rating)
            .where(
                StrategyScore.instrument_id == instrument_id,
                StrategyScore.score_date <= score_date,
                StrategyScore.rs_rating.is_not(None),
            )
            .order_by(desc(StrategyScore.score_date))
            .limit(1)
        )
        rs_row = ss_q.scalars().first()
        rs_val = float(rs_row) if rs_row is not None else None

    score, count, detail = compute_minervini_score(closes, highs, lows, rs_val)

    return {
        "instrument_id":        instrument_id,
        "score_date":           score_date,
        "minervini_score":      round(score, 2),
        "minervini_criteria_count": count,
        "minervini_detail":     detail,
    }


async def run_minervini_scoring(
    score_date: Optional[date] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> list[dict]:
    """
    Run Minervini scoring for a batch of instruments and upsert into strategy_scores.

    Shares the market-wide RS lookup with CANSLIM for efficiency when called
    from the same session.
    """
    if score_date is None:
        score_date = date.today()

    async with AsyncSessionLocal() as db:
        stmt = select(Instrument.id, Instrument.market).where(Instrument.is_active == True)
        if market:
            stmt = stmt.where(Instrument.market == market)
        if instrument_ids:
            stmt = stmt.where(Instrument.id.in_(instrument_ids))
        result = await db.execute(stmt)
        rows = result.all()
        ids = [r[0] for r in rows]
        market_by_id = {r[0]: r[1] for r in rows}

        logger.info("Minervini scoring %d instruments for %s", len(ids), score_date)

        # Build RS lookup per market (reuse the same helper as CANSLIM)
        rs_lookup_by_market: dict[str, dict[int, float]] = {}
        for mkt in sorted(set(market_by_id.values())):
            rs_lookup_by_market[mkt] = await build_market_rs_lookup(db, mkt, score_date)

        results = []
        for inst_id in ids:
            try:
                mkt = market_by_id[inst_id]
                scored = await score_instrument(
                    inst_id, score_date, db,
                    rs_lookup=rs_lookup_by_market[mkt],
                )
                if scored is None:
                    continue

                # Upsert into strategy_scores
                existing_q = await db.execute(
                    select(StrategyScore).where(
                        StrategyScore.instrument_id == inst_id,
                        StrategyScore.score_date == score_date,
                    )
                )
                existing = existing_q.scalars().first()

                if existing:
                    existing.minervini_score          = scored["minervini_score"]
                    existing.minervini_criteria_count = scored["minervini_criteria_count"]
                    existing.minervini_detail         = scored["minervini_detail"]
                else:
                    db.add(StrategyScore(
                        instrument_id          = inst_id,
                        score_date             = score_date,
                        minervini_score        = scored["minervini_score"],
                        minervini_criteria_count = scored["minervini_criteria_count"],
                        minervini_detail       = scored["minervini_detail"],
                    ))

                results.append(scored)

            except Exception as exc:
                logger.error("Minervini scoring failed for instrument %s: %s", inst_id, exc)

        await db.commit()
        logger.info("Minervini scoring complete: %d/%d scored", len(results), len(ids))

    return results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    market_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_minervini_scoring(market=market_arg))
