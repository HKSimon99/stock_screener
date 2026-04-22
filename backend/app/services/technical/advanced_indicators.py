"""
Advanced Technical Indicators — Phase 3.5
==========================================
Computes 7 advanced technical indicators from price/volume history
and stores results in strategy_scores (technical_detail, ad_rating,
bb_squeeze, rs_line_new_high) and returns a structured dict.

Indicators (from PLAN-FINAL §4, Phase 3.5):
  1. Accumulation/Distribution (A/D) Rating — 13-week graded A+ to E
  2. Up/Down Volume Ratio — 50-day
  3. Volume Dry-Up score — base quality proxy
  4. RS Line new-high detection — leading indicator vs benchmark
  5. Bollinger Band Squeeze — volatility compression before expansion
  6. Money Flow Index (MFI) — 14-day volume-weighted RSI
  7. On-Balance Volume (OBV) + slope trend

All functions accept plain Python lists (oldest-first) for portability;
no pandas dependency in this module.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, desc

from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.price import Price
from app.models.strategy_score import StrategyScore

logger = logging.getLogger(__name__)

# ── AD Rating Thresholds ─────────────────────────────────────────────────────
# Compute 13-week (65-bar) UD-volume ratio, then bucket A+/A/B/C/D/E
_AD_THRESHOLDS = [
    (2.5,  "A+"),
    (1.8,  "A"),
    (1.3,  "B"),
    (0.9,  "C"),
    (0.6,  "D"),
    (0.0,  "E"),
]


# ── Individual indicator functions ───────────────────────────────────────────

def compute_ad_rating(
    closes: list[float],
    volumes: list[float],
    window: int = 65,
) -> tuple[str, Optional[float]]:
    """
    Accumulation/Distribution Rating based on 13-week (65-bar) Up/Down volume.

    Returns:
        (grade, ud_ratio)  where grade is 'A+' | 'A' | 'B' | 'C' | 'D' | 'E'
    """
    n = len(closes)
    if n < 2:
        return "E", 0.0

    slice_len = min(window, n - 1)
    up_vol = down_vol = 0.0
    for i in range(n - slice_len, n):
        vol = volumes[i] if i < len(volumes) else 0
        if closes[i] > closes[i - 1]:
            up_vol += vol
        elif closes[i] < closes[i - 1]:
            down_vol += vol

    ud_ratio = up_vol / down_vol if down_vol > 0 else None
    grade = "E"
    comparison_ratio = ud_ratio if ud_ratio is not None else float("inf")
    for threshold, g in _AD_THRESHOLDS:
        if comparison_ratio >= threshold:
            grade = g
            break

    return grade, round(ud_ratio, 3) if ud_ratio is not None else None


def compute_ud_volume_ratio(
    closes: list[float],
    volumes: list[float],
    window: int = 50,
) -> Optional[float]:
    """Up/Down volume ratio over last `window` bars."""
    n = len(closes)
    if n < 2:
        return None

    slice_len = min(window, n - 1)
    up_vol = down_vol = 0.0
    for i in range(n - slice_len, n):
        vol = volumes[i] if i < len(volumes) else 0
        if closes[i] > closes[i - 1]:
            up_vol += vol
        elif closes[i] < closes[i - 1]:
            down_vol += vol

    if down_vol == 0:
        return None
    return round(up_vol / down_vol, 3)


def compute_volume_dry_up(
    volumes: list[float],
    window_base: int = 20,
    window_prior: int = 50,
) -> Optional[float]:
    """
    Volume Dry-Up score: ratio of recent base volume to prior average.
    Lower = drier = better base quality.

    Returns:
        dry_up_ratio (recent_avg_vol / prior_avg_vol)
        Values < 0.7 indicate significant volume contraction (tight base).
    """
    n = len(volumes)
    if n < window_prior:
        return None

    recent_avg = sum(volumes[-window_base:]) / window_base
    prior_avg  = sum(volumes[-window_prior:-window_base]) / (window_prior - window_base)

    if prior_avg == 0:
        return None
    return round(recent_avg / prior_avg, 3)


def compute_rs_line_new_high(
    instrument_closes: list[float],
    benchmark_closes: list[float],
    window: int = 52,
) -> tuple[bool, Optional[float]]:
    """
    Detect whether the RS Line (instrument/benchmark ratio) is making a new high
    relative to its own `window`-week (≈252-bar) history.

    Returns:
        (is_new_high, current_rs_line_value)
    """
    n_i = len(instrument_closes)
    n_b = len(benchmark_closes)
    min_n = min(n_i, n_b)

    if min_n < 2:
        return False, None

    window_days = min(window * 5, min_n)  # approx trading days
    rs_line = [
        instrument_closes[i] / benchmark_closes[i]
        for i in range(min_n - window_days, min_n)
        if benchmark_closes[i] > 0
    ]

    if not rs_line:
        return False, None

    current = rs_line[-1]
    prior_high = max(rs_line[:-1]) if len(rs_line) > 1 else current

    return current >= prior_high, round(current, 6)


def compute_bollinger_band_squeeze(
    closes: list[float],
    window: int = 20,
    num_std: float = 2.0,
    squeeze_threshold: float = 0.06,
) -> tuple[bool, Optional[float]]:
    """
    Bollinger Band Squeeze: bandwidth < `squeeze_threshold` fraction of middle band.

    Returns:
        (is_squeezed, bandwidth_pct)
        bandwidth_pct = (upper - lower) / middle_band
    """
    n = len(closes)
    if n < window:
        return False, None

    window_slice = closes[-window:]
    mean = sum(window_slice) / window
    variance = sum((x - mean) ** 2 for x in window_slice) / window
    std = math.sqrt(variance)

    upper = mean + num_std * std
    lower = mean - num_std * std
    bandwidth = (upper - lower) / mean if mean > 0 else None

    if bandwidth is None:
        return False, None
    return bandwidth < squeeze_threshold, round(bandwidth, 4)


def compute_mfi(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
    period: int = 14,
) -> Optional[float]:
    """
    Money Flow Index (MFI) — volume-weighted RSI.
    Returns current MFI value (0-100); >80 = overbought, <20 = oversold.
    """
    n = len(closes)
    if n < period + 1 or not volumes:
        return None

    # Typical price
    typical = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(n)]

    pos_flow = neg_flow = 0.0
    for i in range(n - period, n):
        mf = typical[i] * (volumes[i] if i < len(volumes) else 0)
        if typical[i] > typical[i - 1]:
            pos_flow += mf
        elif typical[i] < typical[i - 1]:
            neg_flow += mf

    if neg_flow == 0:
        return 100.0
    mfr = pos_flow / neg_flow
    return round(100 - (100 / (1 + mfr)), 2)


def compute_obv(
    closes: list[float],
    volumes: list[float],
) -> tuple[Optional[float], Optional[str]]:
    """
    On-Balance Volume + trend classification.

    Returns:
        (obv_current, trend)  where trend is 'rising' | 'falling' | 'flat'
    """
    n = len(closes)
    if n < 2 or not volumes:
        return None, None

    obv = [0.0]
    for i in range(1, n):
        vol = volumes[i] if i < len(volumes) else 0
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + vol)
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - vol)
        else:
            obv.append(obv[-1])

    current = obv[-1]

    # Trend: compare last 20-bar OBV avg vs 50-bar OBV avg
    obv_20 = sum(obv[-20:]) / min(20, len(obv))
    obv_50 = sum(obv[-50:]) / min(50, len(obv))

    if obv_20 > obv_50 * 1.01:
        trend = "rising"
    elif obv_20 < obv_50 * 0.99:
        trend = "falling"
    else:
        trend = "flat"

    return round(current, 0), trend


# ── DB-backed per-instrument scorer ─────────────────────────────────────────

async def score_instrument_technical(
    instrument_id: int,
    score_date: date,
    db,
    benchmark_closes_by_market: dict[str, list[float]],
    instrument_market: str,
) -> Optional[dict]:
    """Compute all 7 advanced technical indicators for one instrument."""
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

    if len(price_rows) < 22:
        return None

    closes  = [float(p.close)  for p in price_rows if p.close  is not None]
    highs   = [float(p.high)   for p in price_rows if p.high   is not None]
    lows    = [float(p.low)    for p in price_rows if p.low    is not None]
    volumes = [float(p.volume) for p in price_rows if p.volume is not None]

    # Pad shorter arrays to match closes length
    while len(highs)   < len(closes): highs.append(closes[-1])
    while len(lows)    < len(closes): lows.append(closes[-1])
    while len(volumes) < len(closes): volumes.append(0.0)

    # 1. AD Rating
    ad_grade, ud_65 = compute_ad_rating(closes, volumes)

    # 2. UD Volume Ratio (50-day)
    ud_50 = compute_ud_volume_ratio(closes, volumes)

    # 3. Volume Dry-Up
    dry_up = compute_volume_dry_up(volumes)

    # 4. RS Line New High
    benchmark_closes = benchmark_closes_by_market.get(instrument_market, [])
    rs_new_high, rs_line_val = compute_rs_line_new_high(closes, benchmark_closes)

    # 5. Bollinger Band Squeeze
    bb_squeeze, bb_bw = compute_bollinger_band_squeeze(closes)

    # 6. Money Flow Index
    mfi_val = compute_mfi(highs, lows, closes, volumes)

    # 7. OBV + trend
    obv_val, obv_trend = compute_obv(closes, volumes)

    technical_detail = {
        "ad_rating":      ad_grade,
        "ud_ratio_65d":   ud_65,
        "ud_ratio_50d":   ud_50,
        "volume_dry_up":  dry_up,
        "rs_line_value":  rs_line_val,
        "rs_line_new_high": rs_new_high,
        "bb_squeeze":     bb_squeeze,
        "bb_bandwidth":   bb_bw,
        "mfi_14d":        mfi_val,
        "obv":            obv_val,
        "obv_trend":      obv_trend,
    }

    return {
        "instrument_id":    instrument_id,
        "score_date":       score_date,
        "ad_rating":        ad_grade,
        "bb_squeeze":       bb_squeeze,
        "rs_line_new_high": rs_new_high,
        "technical_detail": technical_detail,
    }


async def run_technical_indicator_scoring(
    score_date: Optional[date] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
    benchmark_closes_by_market: Optional[dict[str, list[float]]] = None,
) -> list[dict]:
    """
    Compute advanced technical indicators for a batch of instruments
    and upsert results into strategy_scores.

    `benchmark_closes_by_market` can be pre-built by the caller for efficiency;
    if None, it will be fetched from the DB internally.
    """
    if score_date is None:
        score_date = date.today()

    async with AsyncSessionLocal() as db:
        # ── Load benchmarks if not provided ──────────────────────────────────
        if benchmark_closes_by_market is None:
            from app.services.strategies.dual_momentum.engine import BENCHMARK_TICKER
            benchmark_closes_by_market = {}
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
                bm_closes = list(reversed([
                    float(r[0]) for r in bm_q.all() if r[0] is not None
                ]))
                benchmark_closes_by_market[mkt] = bm_closes

        # ── Target instruments ────────────────────────────────────────────────
        stmt = select(Instrument.id, Instrument.market).where(Instrument.is_active == True)
        if market:
            stmt = stmt.where(Instrument.market == market)
        if instrument_ids:
            stmt = stmt.where(Instrument.id.in_(instrument_ids))
        result = await db.execute(stmt)
        rows = result.all()
        ids = [r[0] for r in rows]
        market_by_id = {r[0]: r[1] for r in rows}

        logger.info("Technical indicators scoring %d instruments for %s", len(ids), score_date)

        results = []
        for inst_id in ids:
            try:
                inst_market = market_by_id[inst_id]
                scored = await score_instrument_technical(
                    inst_id, score_date, db,
                    benchmark_closes_by_market=benchmark_closes_by_market,
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
                    existing.ad_rating        = scored["ad_rating"]
                    existing.bb_squeeze       = scored["bb_squeeze"]
                    existing.rs_line_new_high = scored["rs_line_new_high"]
                    existing.technical_detail = scored["technical_detail"]
                else:
                    db.add(StrategyScore(
                        instrument_id   = inst_id,
                        score_date      = score_date,
                        ad_rating       = scored["ad_rating"],
                        bb_squeeze      = scored["bb_squeeze"],
                        rs_line_new_high = scored["rs_line_new_high"],
                        technical_detail = scored["technical_detail"],
                    ))

                results.append(scored)

            except Exception as exc:
                logger.error("Technical indicator scoring failed for instrument %s: %s", inst_id, exc)

        await db.commit()
        logger.info("Technical indicator scoring complete: %d/%d scored", len(results), len(ids))

    return results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    market_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_technical_indicator_scoring(market=market_arg))
