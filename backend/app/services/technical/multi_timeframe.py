"""
Technical Composite + Multi-Timeframe — Phase 3.6
===================================================
Aggregates all technical sub-scores into a single 0-100
``technical_composite`` score and persists it back to strategy_scores.

Sub-components (weights):
  30% — Multi-Timeframe Alignment  (daily / weekly / monthly trend)
  25% — Chart Pattern Quality      (best pattern confidence + breakout bonus)
  25% — Volume / Accumulation      (A/D rating, OBV, UD ratio, dry-up)
  20% — Momentum / Breakout        (RS new-high, BB squeeze, MFI, SMA position)

Multi-timeframe resampling uses a stride approach on daily price lists
(no pandas dependency): weekly ≈ every 5 bars, monthly ≈ every 21 bars.

Usage:
    python -m app.services.technical.multi_timeframe [--market US|KR]
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import select, desc

from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.price import Price
from app.models.strategy_score import StrategyScore

logger = logging.getLogger(__name__)

# AD rating → volume score points (out of 25)
_AD_VOLUME_POINTS: dict[str, float] = {
    "A+": 25.0,
    "A":  20.0,
    "B":  15.0,
    "C":  10.0,
    "D":   5.0,
    "E":   0.0,
}

# Minervini criteria count → multi-TF alignment bonus (max 15 extra points)
_MINERVINI_BONUS: dict[int, float] = {
    8: 15.0,
    7: 12.0,
    6:  9.0,
    5:  6.0,
    4:  3.0,
}


# =============================================================================
# Multi-Timeframe Utilities
# =============================================================================

def _sma(data: list[float], period: int) -> Optional[float]:
    if len(data) < period:
        return None
    return sum(data[-period:]) / period


def resample_to_period(closes: list[float], stride: int) -> list[float]:
    """
    Stride-subsample a daily close list to approximate a coarser timeframe.
    Takes one bar every ``stride`` bars (the last bar of each period).

    stride=5  → weekly  (≈ every 5 trading days)
    stride=21 → monthly (≈ every 21 trading days)
    """
    if not closes or stride < 1:
        return []
    return [closes[i] for i in range(stride - 1, len(closes), stride)]


def compute_multi_timeframe_score(closes: list[float]) -> tuple[float, dict]:
    """
    Assess trend alignment across daily / weekly / monthly timeframes.

    Scoring (per timeframe, max 100 total across all three):
      Each timeframe can contribute up to ~33 points.
      A timeframe is "bullish" when:
        - Current close > SMA of that timeframe
        - SMA is rising (current SMA > SMA 4 periods ago)

    Returns:
        (score_0_100, detail_dict)
    """
    n = len(closes)
    if n < 30:
        return 0.0, {"error": "insufficient data"}

    # ── Daily alignment ───────────────────────────────────────────────────────
    sma50d  = _sma(closes, 50)
    sma200d = _sma(closes, 200)
    close_d = closes[-1]

    daily_above_50  = sma50d  is not None and close_d > sma50d
    daily_above_200 = sma200d is not None and close_d > sma200d

    # SMA50 trending up (compare to 10 bars ago)
    sma50d_lag: Optional[float] = None
    if n >= 60:
        sma50d_lag = _sma(closes[:-10], 50)
    daily_sma50_rising = sma50d is not None and sma50d_lag is not None and sma50d > sma50d_lag

    # ── Weekly alignment ──────────────────────────────────────────────────────
    weekly = resample_to_period(closes, 5)
    sma10w  = _sma(weekly, 10)   # ≈ 50 trading days
    sma40w  = _sma(weekly, 40)   # ≈ 200 trading days
    close_w = weekly[-1] if weekly else 0.0

    weekly_above_10w  = sma10w is not None and close_w > sma10w
    weekly_above_40w  = sma40w is not None and close_w > sma40w

    sma10w_lag: Optional[float] = None
    if len(weekly) >= 14:
        sma10w_lag = _sma(weekly[:-4], 10)
    weekly_sma_rising = sma10w is not None and sma10w_lag is not None and sma10w > sma10w_lag

    # ── Monthly alignment ─────────────────────────────────────────────────────
    monthly = resample_to_period(closes, 21)
    sma10m  = _sma(monthly, 10)  # ≈ 200 trading days
    close_m = monthly[-1] if monthly else 0.0

    monthly_above_10m = sma10m is not None and close_m > sma10m

    sma10m_lag: Optional[float] = None
    if len(monthly) >= 14:
        sma10m_lag = _sma(monthly[:-2], 10)
    monthly_sma_rising = sma10m is not None and sma10m_lag is not None and sma10m > sma10m_lag

    # ── Score ─────────────────────────────────────────────────────────────────
    # Daily component (up to 40 points)
    daily_score = 0.0
    if daily_above_50:   daily_score += 20.0
    if daily_above_200:  daily_score += 10.0
    if daily_sma50_rising: daily_score += 10.0

    # Weekly component (up to 35 points)
    weekly_score = 0.0
    if weekly_above_10w:  weekly_score += 15.0
    if weekly_above_40w:  weekly_score += 10.0
    if weekly_sma_rising: weekly_score += 10.0

    # Monthly component (up to 25 points)
    monthly_score = 0.0
    if monthly_above_10m:  monthly_score += 15.0
    if monthly_sma_rising: monthly_score += 10.0

    total = min(100.0, daily_score + weekly_score + monthly_score)

    detail = {
        "daily": {
            "close": round(close_d, 2),
            "sma50": round(sma50d, 2) if sma50d else None,
            "sma200": round(sma200d, 2) if sma200d else None,
            "above_50": daily_above_50,
            "above_200": daily_above_200,
            "sma50_rising": daily_sma50_rising,
            "score": daily_score,
        },
        "weekly": {
            "close": round(close_w, 2),
            "sma10w": round(sma10w, 2) if sma10w else None,
            "sma40w": round(sma40w, 2) if sma40w else None,
            "above_10w": weekly_above_10w,
            "above_40w": weekly_above_40w,
            "sma_rising": weekly_sma_rising,
            "score": weekly_score,
        },
        "monthly": {
            "close": round(close_m, 2),
            "sma10m": round(sma10m, 2) if sma10m else None,
            "above_10m": monthly_above_10m,
            "sma_rising": monthly_sma_rising,
            "score": monthly_score,
        },
    }

    return round(total, 2), detail


# =============================================================================
# Pattern Score Sub-Component
# =============================================================================

def compute_pattern_score(patterns: Optional[list[dict]]) -> tuple[float, dict]:
    """
    Convert detected patterns list into a 0-100 sub-score.

    Logic:
      - Best single pattern confidence × 100 → base score
      - +10 bonus if that pattern status is "breakout"
      - +5 bonus if ≥3 patterns detected above 60% confidence
    Returns:
        (score_0_100, detail_dict)
    """
    if not patterns:
        return 0.0, {"pattern_count": 0, "best_pattern": None}

    # Sort by confidence
    sorted_pats = sorted(patterns, key=lambda p: p.get("confidence", 0), reverse=True)
    best = sorted_pats[0]
    best_conf = best.get("confidence", 0)
    best_type = best.get("pattern_type", "unknown")
    best_status = best.get("status", "")

    base = best_conf * 100.0

    # Breakout bonus
    breakout_bonus = 10.0 if best_status == "breakout" else 0.0

    # Breadth bonus: multiple strong patterns
    strong_count = sum(1 for p in patterns if p.get("confidence", 0) >= 0.60)
    breadth_bonus = 5.0 if strong_count >= 3 else 0.0

    score = min(100.0, base + breakout_bonus + breadth_bonus)

    return round(score, 2), {
        "pattern_count": len(patterns),
        "best_pattern": best_type,
        "best_confidence": round(best_conf, 3),
        "best_status": best_status,
        "strong_patterns": strong_count,
        "breakout_bonus": breakout_bonus,
        "breadth_bonus": breadth_bonus,
    }


# =============================================================================
# Volume / Accumulation Sub-Component
# =============================================================================

def compute_volume_score(technical_detail: Optional[dict]) -> tuple[float, dict]:
    """
    Convert volume/accumulation indicators into a 0-100 sub-score.

    Components (total 100):
      AD Rating (0-25): A+=25, A=20, B=15, C=10, D=5, E=0
      OBV Trend (0-20): rising=20, flat=10, falling=0
      UD Ratio 50d (0-20): >2.0=20, >1.5=15, >1.0=10, >0.5=5, else=0
      Volume Dry-Up (0-15): ratio<0.60=15, <0.70=10, <0.80=5, else=0
      UD Ratio 65d (0-10): >2.5=10, >1.8=7, >1.3=4, else=0
      MFI health (0-10): 40-70=10, 30-80=5, else=0
    """
    if not technical_detail:
        return 0.0, {"error": "no technical_detail"}

    # AD Rating
    ad_rating = technical_detail.get("ad_rating", "E")
    ad_pts = _AD_VOLUME_POINTS.get(ad_rating, 0.0)

    # OBV Trend
    obv_trend = technical_detail.get("obv_trend", "flat")
    obv_pts = {"rising": 20.0, "flat": 10.0, "falling": 0.0}.get(obv_trend, 5.0)

    # UD Ratio 50d
    ud_50 = technical_detail.get("ud_ratio_50d")
    if ud_50 is None:
        ud50_pts = 5.0
    elif ud_50 >= 2.0:
        ud50_pts = 20.0
    elif ud_50 >= 1.5:
        ud50_pts = 15.0
    elif ud_50 >= 1.0:
        ud50_pts = 10.0
    elif ud_50 >= 0.5:
        ud50_pts = 5.0
    else:
        ud50_pts = 0.0

    # Volume Dry-Up (contraction is bullish)
    dry_up = technical_detail.get("volume_dry_up")
    if dry_up is None:
        dry_pts = 5.0
    elif dry_up < 0.60:
        dry_pts = 15.0
    elif dry_up < 0.70:
        dry_pts = 10.0
    elif dry_up < 0.80:
        dry_pts = 5.0
    else:
        dry_pts = 0.0

    # UD Ratio 65d (A/D base)
    ud_65 = technical_detail.get("ud_ratio_65d", 0)
    if ud_65 >= 2.5:
        ud65_pts = 10.0
    elif ud_65 >= 1.8:
        ud65_pts = 7.0
    elif ud_65 >= 1.3:
        ud65_pts = 4.0
    else:
        ud65_pts = 0.0

    # MFI health zone
    mfi = technical_detail.get("mfi_14d")
    if mfi is None:
        mfi_pts = 5.0
    elif 40 <= mfi <= 70:
        mfi_pts = 10.0
    elif 30 <= mfi <= 80:
        mfi_pts = 5.0
    else:
        mfi_pts = 0.0

    total = min(100.0, ad_pts + obv_pts + ud50_pts + dry_pts + ud65_pts + mfi_pts)

    return round(total, 2), {
        "ad_rating": ad_rating,
        "ad_pts": ad_pts,
        "obv_trend": obv_trend,
        "obv_pts": obv_pts,
        "ud_ratio_50d": ud_50,
        "ud50_pts": ud50_pts,
        "volume_dry_up": dry_up,
        "dry_pts": dry_pts,
        "ud_ratio_65d": ud_65,
        "ud65_pts": ud65_pts,
        "mfi_14d": mfi,
        "mfi_pts": mfi_pts,
    }


# =============================================================================
# Momentum / Breakout Sub-Component
# =============================================================================

def compute_momentum_score(
    technical_detail: Optional[dict],
    minervini_criteria_count: Optional[int],
) -> tuple[float, dict]:
    """
    Convert momentum and breakout signals into a 0-100 sub-score.

    Components:
      RS Line New High (0-30): Yes=30, No=0
      Minervini count bonus (0-30): 8→30, 7→25, 6→20, 5→15, 4→10, <4→0
      BB Squeeze (0-15): active squeeze=15 (coiled spring)
      RS Line value trend (0-15): rs_line_value above recent range → 15
      OBV rising (0-10): captured from technical_detail
    """
    if not technical_detail:
        return 0.0, {"error": "no technical_detail"}

    # RS Line New High (strongest momentum signal)
    rs_new_high = technical_detail.get("rs_line_new_high", False)
    rs_pts = 30.0 if rs_new_high else 0.0

    # Minervini criteria (already captures most momentum factors)
    mc = minervini_criteria_count or 0
    minervini_pts = {8: 30.0, 7: 25.0, 6: 20.0, 5: 15.0, 4: 10.0}.get(mc, 0.0)

    # BB Squeeze (volatility compression before expansion)
    bb_squeeze = technical_detail.get("bb_squeeze", False)
    bb_pts = 15.0 if bb_squeeze else 0.0

    # OBV rising as a momentum bonus (already in volume score, mild bonus here)
    obv_trend = technical_detail.get("obv_trend", "flat")
    obv_mom_pts = 10.0 if obv_trend == "rising" else 5.0 if obv_trend == "flat" else 0.0

    # RS Line value vs threshold (bonus for extremely high RS line)
    rs_line_val = technical_detail.get("rs_line_value")
    rs_line_pts = 15.0 if rs_new_high and rs_line_val else 0.0

    # Normalize: cap at 100
    raw = rs_pts + minervini_pts + bb_pts + obv_mom_pts + rs_line_pts
    # Maximum raw = 30 + 30 + 15 + 10 + 15 = 100
    total = min(100.0, raw)

    return round(total, 2), {
        "rs_line_new_high": rs_new_high,
        "rs_pts": rs_pts,
        "minervini_criteria_count": mc,
        "minervini_pts": minervini_pts,
        "bb_squeeze": bb_squeeze,
        "bb_pts": bb_pts,
        "obv_trend": obv_trend,
        "obv_mom_pts": obv_mom_pts,
        "rs_line_pts": rs_line_pts,
    }


# =============================================================================
# Master Composite Aggregator (pure function — no DB)
# =============================================================================

def compute_technical_composite(
    closes: list[float],
    patterns: Optional[list[dict]],
    technical_detail: Optional[dict],
    minervini_criteria_count: Optional[int],
) -> tuple[float, dict]:
    """
    Aggregate all technical sub-scores into a single 0-100 composite.

    Weights:
      30% multi-timeframe alignment
      25% chart pattern quality
      25% volume / accumulation
      20% momentum / breakout signals

    Returns:
        (technical_composite, detail_dict)
    """
    # Sub-component scores
    mtf_score, mtf_detail = compute_multi_timeframe_score(closes)
    pattern_score, pattern_detail = compute_pattern_score(patterns)
    volume_score, volume_detail = compute_volume_score(technical_detail)
    momentum_score, momentum_detail = compute_momentum_score(
        technical_detail, minervini_criteria_count
    )

    composite = (
        0.30 * mtf_score
        + 0.25 * pattern_score
        + 0.25 * volume_score
        + 0.20 * momentum_score
    )
    composite = round(min(100.0, max(0.0, composite)), 2)

    detail = {
        "multi_timeframe_score": mtf_score,
        "pattern_score": pattern_score,
        "volume_score": volume_score,
        "momentum_score": momentum_score,
        "weights": {"multi_tf": 0.30, "pattern": 0.25, "volume": 0.25, "momentum": 0.20},
        "multi_timeframe": mtf_detail,
        "pattern_breakdown": pattern_detail,
        "volume_breakdown": volume_detail,
        "momentum_breakdown": momentum_detail,
    }

    return composite, detail


# =============================================================================
# DB-Backed Per-Instrument Scorer
# =============================================================================

async def score_instrument_composite(
    instrument_id: int,
    score_date: date,
    db,
) -> Optional[dict]:
    """
    Read price history + existing strategy_scores row, compute composite.
    Returns dict ready for upsert, or None if insufficient data.
    """
    # Fetch price history
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

    if len(price_rows) < 50:
        return None

    closes = [float(p.close) for p in price_rows if p.close is not None]
    if len(closes) < 50:
        return None

    # Fetch existing strategy_scores row for this date (may have patterns + tech detail)
    ss_q = await db.execute(
        select(StrategyScore).where(
            StrategyScore.instrument_id == instrument_id,
            StrategyScore.score_date == score_date,
        )
    )
    ss = ss_q.scalars().first()

    patterns: Optional[list[dict]] = None
    technical_detail: Optional[dict] = None
    minervini_count: Optional[int] = None

    if ss:
        patterns = ss.patterns
        technical_detail = ss.technical_detail
        minervini_count = ss.minervini_criteria_count

    composite, detail = compute_technical_composite(
        closes, patterns, technical_detail, minervini_count
    )

    return {
        "instrument_id": instrument_id,
        "score_date": score_date,
        "technical_composite": composite,
        "technical_composite_detail": detail,
    }


# =============================================================================
# Batch Runner with DB Upsert
# =============================================================================

async def run_technical_composite_scoring(
    score_date: Optional[date] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> list[dict]:
    """
    Compute ``technical_composite`` for a batch of instruments and
    upsert back into ``strategy_scores``.

    Run AFTER pattern_detector and advanced_indicators have persisted
    their results for the same ``score_date``.
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

        logger.info(
            "Technical composite scoring %d instruments for %s", len(ids), score_date
        )

        results = []
        for inst_id in ids:
            try:
                scored = await score_instrument_composite(inst_id, score_date, db)
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

                composite = scored["technical_composite"]
                composite_detail = scored["technical_composite_detail"]

                if existing:
                    existing.technical_composite = composite
                    # Merge composite detail into existing technical_detail JSONB
                    merged_detail = dict(existing.technical_detail or {})
                    merged_detail["composite"] = composite_detail
                    existing.technical_detail = merged_detail
                else:
                    db.add(StrategyScore(
                        instrument_id=inst_id,
                        score_date=score_date,
                        technical_composite=composite,
                        technical_detail={"composite": composite_detail},
                    ))

                results.append(scored)

            except Exception as exc:
                logger.error(
                    "Technical composite scoring failed for instrument %s: %s",
                    inst_id, exc,
                )

        await db.commit()
        logger.info(
            "Technical composite complete: %d/%d scored. "
            "Avg composite=%.1f",
            len(results), len(ids),
            sum(r["technical_composite"] for r in results) / len(results) if results else 0,
        )

    return results


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    market_arg = None
    for arg in sys.argv[1:]:
        if arg.startswith("--market="):
            market_arg = arg.split("=")[1]
        elif arg in ("US", "KR"):
            market_arg = arg

    async def _main():
        results = await run_technical_composite_scoring(market=market_arg)
        print(f"\nScored {len(results)} instruments")
        if results:
            scores = [r["technical_composite"] for r in results]
            print(f"  Min:    {min(scores):.1f}")
            print(f"  Max:    {max(scores):.1f}")
            print(f"  Avg:    {sum(scores)/len(scores):.1f}")
            # Show top 10
            top = sorted(results, key=lambda r: r["technical_composite"], reverse=True)[:10]
            print("\nTop 10 by technical_composite:")
            for r in top:
                detail = r["technical_composite_detail"]
                print(
                    f"  Instrument {r['instrument_id']:>5}: "
                    f"composite={r['technical_composite']:.1f}  "
                    f"mtf={detail['multi_timeframe_score']:.0f}  "
                    f"pat={detail['pattern_score']:.0f}  "
                    f"vol={detail['volume_score']:.0f}  "
                    f"mom={detail['momentum_score']:.0f}"
                )

    asyncio.run(_main())
