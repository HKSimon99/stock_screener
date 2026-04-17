"""
Weinstein Stage Analysis Engine
=================================
Classifies each instrument into one of 4 stage categories based on the
150-day (30-week) moving average, its slope, volume patterns, and
price/MA relationship.

Stages (from PLAN-FINAL §3.4):
  Stage 1 — Basing    : flat MA, price oscillating above/below
  Stage 2 — Advancing : price > rising MA (ideal buy zone)
  Stage 3 — Topping   : flat MA, heavier volume on declines
  Stage 4 — Declining : price < declining MA

Sub-stages for Stage 2:
  Early  (slope just turned positive in last 40 days) → score 100
  Mid    (sustained, price 5-25% above MA)             → score 85
  Late   (price >30% above MA — extended, caution)     → score 55

Scoring (0-100):
  Stage 2 early → 100  |  Stage 2 mid → 85  |  Stage 2 late → 55
  Stage 1 late  → 60   |  Stage 1 early → 25
  Stage 3       → 10   |  Stage 4       → 0
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

logger = logging.getLogger(__name__)

MIN_PRICE_BARS = 155  # 150 for sma + 5 extra for slope calc
STAGE_SCORE = {
    "2_early": 100,
    "2_mid":    85,
    "2_late":   55,
    "1_late":   60,
    "1_early":  25,
    "3":        10,
    "4":         0,
}


def _sma(closes: list[float], period: int) -> Optional[float]:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def compute_weinstein_stage(
    closes: list[float],
    volumes: list[float],
) -> tuple[float, str, dict]:
    """
    Classify the Weinstein stage from price/volume history.

    Args:
        closes:  Daily close prices (oldest first, ≥155 bars).
        volumes: Parallel daily volumes.

    Returns:
        (score_0_100, stage_label, detail_dict)
        stage_label: '1_early' | '1_late' | '2_early' | '2_mid' | '2_late' | '3' | '4'
    """
    n = len(closes)
    if n < MIN_PRICE_BARS:
        return 0.0, "4", {"error": "insufficient price data"}

    close = closes[-1]
    ma_150 = _sma(closes, 150)
    if ma_150 is None:
        return 0.0, "4", {"error": "cannot compute 150-day MA"}

    # ── MA slope: (ma_today - ma_20d_ago) / ma_20d_ago ────────────────────
    ma_150_20d: Optional[float] = None
    if n >= 170:
        ma_150_20d = _sma(closes[:-20], 150)

    ma_slope_20d: Optional[float] = None
    if ma_150_20d is not None and ma_150_20d > 0:
        ma_slope_20d = (ma_150 - ma_150_20d) / ma_150_20d

    price_vs_ma = (close / ma_150 - 1) if ma_150 > 0 else 0.0

    # ── Cross count: how many times price crossed the 150-MA in last 60 days
    cross_count_60d = 0
    window_60 = min(n - 1, 60)
    if n > 1:
        for i in range(max(1, n - window_60), n):
            prev_side = closes[i - 1] >= ma_150
            curr_side = closes[i]     >= ma_150
            if prev_side != curr_side:
                cross_count_60d += 1

    # ── Volume: avg on up vs down days (last 50 bars) ───────────────────────
    vol_on_up_days = 0.0
    vol_on_down_days = 0.0
    up_count = down_count = 0
    window_50 = min(n - 1, 50)
    for i in range(max(1, n - window_50), n):
        vol = volumes[i] if i < len(volumes) else 0
        if closes[i] > closes[i - 1]:
            vol_on_up_days += vol
            up_count += 1
        elif closes[i] < closes[i - 1]:
            vol_on_down_days += vol
            down_count += 1
    avg_vol_up   = vol_on_up_days   / up_count   if up_count   > 0 else 0.0
    avg_vol_down = vol_on_down_days / down_count if down_count > 0 else 0.0

    # ── MA slope history for early Stage 2 detection (last 40 days) ─────────
    slope_turned_positive_recently = False
    if n >= 192:  # 150 + 2*20 + 2 buffer
        # Check if slope was negative/flat 40 days ago but positive now
        ma_40d_ago = _sma(closes[:-40], 150)
        ma_60d_ago = _sma(closes[:-60], 150) if n >= 212 else None
        if ma_40d_ago is not None and ma_60d_ago is not None and ma_40d_ago > 0 and ma_60d_ago > 0:
            slope_before = (ma_40d_ago - ma_60d_ago) / ma_60d_ago
            if slope_before <= 0.001 and (ma_slope_20d is not None and ma_slope_20d > 0.005):
                slope_turned_positive_recently = True

    slope_flat = abs(ma_slope_20d) < 0.005 if ma_slope_20d is not None else True
    slope_up   = (ma_slope_20d is not None and ma_slope_20d > 0.005)
    slope_down = (ma_slope_20d is not None and ma_slope_20d < -0.005)

    # ── Stage Classification ─────────────────────────────────────────────────
    stage: str

    if slope_down and price_vs_ma < 0:
        # Stage 4: price below declining MA
        stage = "4"

    elif slope_up and price_vs_ma > 0:
        # Stage 2: price above rising MA
        if slope_turned_positive_recently:
            stage = "2_early"
        elif price_vs_ma > 0.30:
            stage = "2_late"
        else:
            stage = "2_mid"

    elif slope_flat and cross_count_60d >= 3:
        # Stage 1 or 3
        if avg_vol_down > avg_vol_up:
            # Heavier volume on down days → distribution → Stage 3
            stage = "3"
        else:
            # Accumulation or base building
            # Late Stage 1 if looking like about to break out (price_vs_ma near 0)
            if abs(price_vs_ma) < 0.05:
                stage = "1_late"
            else:
                stage = "1_early"

    elif slope_flat and price_vs_ma > 0:
        # Topping (flat MA, price still above)
        if avg_vol_down > avg_vol_up:
            stage = "3"
        else:
            stage = "1_late"

    else:
        # Default based on price/MA relationship
        if price_vs_ma < 0:
            stage = "4" if slope_down else "1_early"
        else:
            stage = "2_mid" if slope_up else "1_late"

    score = float(STAGE_SCORE.get(stage, 0))

    detail = {
        "stage":                   stage,
        "ma_150":                  ma_150,
        "ma_slope_20d":            ma_slope_20d,
        "price_vs_ma":             round(price_vs_ma, 4),
        "cross_count_60d":         cross_count_60d,
        "avg_vol_up_days":         round(avg_vol_up,   0),
        "avg_vol_down_days":       round(avg_vol_down, 0),
        "slope_turned_positive_recently": slope_turned_positive_recently,
    }

    return score, stage, detail


async def score_instrument(
    instrument_id: int,
    score_date: date,
    db,
) -> Optional[dict]:
    """Compute Weinstein stage score for one instrument."""
    price_q = await db.execute(
        select(Price)
        .where(
            Price.instrument_id == instrument_id,
            Price.trade_date <= score_date,
        )
        .order_by(desc(Price.trade_date))
        .limit(220)
    )
    price_rows = list(reversed(price_q.scalars().all()))

    if len(price_rows) < MIN_PRICE_BARS:
        logger.debug(
            "Skipping Weinstein for instrument %s: only %d bars",
            instrument_id, len(price_rows),
        )
        return None

    closes  = [float(p.close)  for p in price_rows if p.close  is not None]
    volumes = [float(p.volume) for p in price_rows if p.volume is not None]

    # Pad volumes if needed (shouldn't happen in practice)
    while len(volumes) < len(closes):
        volumes.append(0.0)

    score, stage, detail = compute_weinstein_stage(closes, volumes)

    return {
        "instrument_id":   instrument_id,
        "score_date":      score_date,
        "weinstein_score": round(score, 2),
        "weinstein_stage": stage,
        "weinstein_detail": detail,
    }


async def run_weinstein_scoring(
    score_date: Optional[date] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> list[dict]:
    """Run Weinstein scoring for a batch of instruments and upsert into strategy_scores."""
    if score_date is None:
        score_date = date.today()

    async with AsyncSessionLocal() as db:
        stmt = select(Instrument.id).where(Instrument.is_active == True)
        if market:
            stmt = stmt.where(Instrument.market == market)
        if instrument_ids:
            stmt = stmt.where(Instrument.id.in_(instrument_ids))
        result = await db.execute(stmt)
        ids = [row[0] for row in result.all()]

        logger.info("Weinstein scoring %d instruments for %s", len(ids), score_date)

        results = []
        for inst_id in ids:
            try:
                scored = await score_instrument(inst_id, score_date, db)
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
                    existing.weinstein_score  = scored["weinstein_score"]
                    existing.weinstein_stage  = scored["weinstein_stage"]
                    existing.weinstein_detail = scored["weinstein_detail"]
                else:
                    db.add(StrategyScore(
                        instrument_id   = inst_id,
                        score_date      = score_date,
                        weinstein_score = scored["weinstein_score"],
                        weinstein_stage = scored["weinstein_stage"],
                        weinstein_detail = scored["weinstein_detail"],
                    ))

                results.append(scored)

            except Exception as exc:
                logger.error("Weinstein scoring failed for instrument %s: %s", inst_id, exc)

        await db.commit()
        logger.info("Weinstein scoring complete: %d/%d scored", len(results), len(ids))

    return results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    market_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_weinstein_scoring(market=market_arg))
