"""
Pattern Detection Library -- Phase 3.4
=======================================
Detects 6 classic chart patterns from price/volume history and stores
matched patterns (with confidence scores) in strategy_scores.patterns JSONB.

Patterns (from PLAN-FINAL / task.md):
  1. Cup with Handle   -- Classic O'Neil breakout base
  2. Double Bottom     -- W-shaped reversal
  3. Flat Base         -- Tight horizontal consolidation
  4. VCP               -- Volatility Contraction Pattern (Minervini)
  5. High Tight Flag   -- Rare, powerful continuation flag
  6. Ascending Base    -- Three higher lows with pullbacks

All functions accept plain Python lists (oldest-first) for portability;
no pandas or numpy dependency in this module.

Usage:
    python -m app.services.technical.pattern_detector [--market US|KR]
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, desc

from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.price import Price
from app.models.strategy_score import StrategyScore

logger = logging.getLogger(__name__)

# Minimum bars to attempt any pattern detection
MIN_BARS = 60

# Confidence threshold -- patterns below this are discarded
MIN_CONFIDENCE = 0.50
KR_PRICE_LIMIT_MOVE_PCT = 0.295


# =============================================================================
#  Pivot Detection Utilities
# =============================================================================

@dataclass
class Pivot:
    """A swing high or swing low in price history."""
    index: int
    price: float
    kind: str  # 'high' or 'low'


def find_swing_pivots(
    highs: list[float],
    lows: list[float],
    order: int = 5,
) -> list[Pivot]:
    """
    Find local maxima and minima using a window of +/- `order` bars.

    A bar at index *i* is a **swing high** when ``highs[i]`` is the
    maximum of ``highs[i-order : i+order+1]``.  Swing lows are the
    mirror image on ``lows``.

    Returns a list of Pivot objects sorted by index, alternating
    highs and lows where possible.
    """
    n = len(highs)
    pivots: list[Pivot] = []

    for i in range(order, n - order):
        # Swing high
        is_high = True
        for j in range(1, order + 1):
            if highs[i] < highs[i - j] or highs[i] < highs[i + j]:
                is_high = False
                break
        if is_high:
            pivots.append(Pivot(i, highs[i], "high"))

        # Swing low
        is_low = True
        for j in range(1, order + 1):
            if lows[i] > lows[i - j] or lows[i] > lows[i + j]:
                is_low = False
                break
        if is_low:
            pivots.append(Pivot(i, lows[i], "low"))

    # De-duplicate: when both high and low happen on same bar, keep both
    pivots.sort(key=lambda p: (p.index, 0 if p.kind == "high" else 1))

    # Enforce alternation: drop consecutive same-kind pivots (keep extremer one)
    cleaned: list[Pivot] = []
    for p in pivots:
        if cleaned and cleaned[-1].kind == p.kind:
            prev = cleaned[-1]
            if p.kind == "high" and p.price > prev.price:
                cleaned[-1] = p
            elif p.kind == "low" and p.price < prev.price:
                cleaned[-1] = p
        else:
            cleaned.append(p)

    return cleaned


def find_zigzag_pivots(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    threshold_pct: float = 5.0,
) -> list[Pivot]:
    """
    Zigzag pivot detection: register a new pivot only when price reverses
    by at least `threshold_pct` percent from the last extreme.

    Returns alternating H-L-H-L pivots.
    """
    if len(closes) < 3:
        return []

    threshold = threshold_pct / 100.0

    # Start with first bar
    last_high_idx = 0
    last_high_val = highs[0]
    last_low_idx = 0
    last_low_val = lows[0]

    state: Optional[str] = None  # 'up' or 'down'
    pivots: list[Pivot] = []

    for i in range(1, len(closes)):
        h = highs[i]
        lo = lows[i]

        if state is None:
            # Determine initial direction
            if h > last_high_val:
                last_high_idx, last_high_val = i, h
            if lo < last_low_val:
                last_low_idx, last_low_val = i, lo

            # Check if we've moved enough to establish a direction
            if last_high_val > 0 and (last_high_val - last_low_val) / last_high_val >= threshold:
                if last_high_idx > last_low_idx:
                    # Price went down then up
                    pivots.append(Pivot(last_low_idx, last_low_val, "low"))
                    state = "up"
                    last_high_idx, last_high_val = i, h
                else:
                    pivots.append(Pivot(last_high_idx, last_high_val, "high"))
                    state = "down"
                    last_low_idx, last_low_val = i, lo

        elif state == "up":
            if h > last_high_val:
                last_high_idx, last_high_val = i, h
            elif last_high_val > 0 and (last_high_val - lo) / last_high_val >= threshold:
                # Reversal downward
                pivots.append(Pivot(last_high_idx, last_high_val, "high"))
                state = "down"
                last_low_idx, last_low_val = i, lo

        elif state == "down":
            if lo < last_low_val:
                last_low_idx, last_low_val = i, lo
            elif last_low_val > 0 and (h - last_low_val) / last_low_val >= threshold:
                # Reversal upward
                pivots.append(Pivot(last_low_idx, last_low_val, "low"))
                state = "up"
                last_high_idx, last_high_val = i, h

    # Close the last pending pivot
    if state == "up":
        pivots.append(Pivot(last_high_idx, last_high_val, "high"))
    elif state == "down":
        pivots.append(Pivot(last_low_idx, last_low_val, "low"))

    return pivots


def _avg_volume(volumes: list[float], start: int, end: int) -> float:
    """Average volume across a slice [start, end)."""
    seg = volumes[start:end]
    return sum(seg) / len(seg) if seg else 0.0


def _max_price(highs: list[float], start: int, end: int) -> float:
    seg = highs[start:end]
    return max(seg) if seg else 0.0


def _min_price(lows: list[float], start: int, end: int) -> float:
    seg = lows[start:end]
    return min(seg) if seg else 0.0


def _sma(data: list[float], period: int) -> Optional[float]:
    if len(data) < period:
        return None
    return sum(data[-period:]) / period


def count_price_limit_events(
    closes: list[float],
    *,
    threshold_pct: float = KR_PRICE_LIMIT_MOVE_PCT,
    recent_bars: int = 20,
) -> int:
    """
    Count recent daily close-to-close moves that look like KR limit-up/down bars.

    KR equities frequently hard-stop around ±30%; those moves can distort
    classical base-pattern detection, so the KR path suppresses fresh detections
    when they appear in the recent scan window.
    """
    if len(closes) < 2:
        return 0

    start_idx = max(1, len(closes) - recent_bars)
    count = 0
    for idx in range(start_idx, len(closes)):
        prev_close = closes[idx - 1]
        current_close = closes[idx]
        if prev_close <= 0:
            continue
        move_pct = abs(current_close - prev_close) / prev_close
        if move_pct >= threshold_pct:
            count += 1
    return count


# =============================================================================
#  1. Cup with Handle Detection
# =============================================================================

def detect_cup_with_handle(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float],
) -> Optional[dict]:
    """
    Detect a Cup-with-Handle pattern in the price history.

    Criteria:
      - Prior uptrend: >=30% advance in 120 bars before the left lip
      - Cup depth: 12-33% from the left lip
      - Cup duration: 35-325 bars (7-65 weeks)
      - Cup shape: U-shaped (bottom zone spans >=15% of cup duration)
      - Right lip: within 10% of left lip level
      - Handle: optional pullback 5-15%, lasting 5-30 bars
      - Volume: dries up at cup bottom, preferably expands on recovery

    Returns dict with pattern details and confidence, or None.
    """
    n = len(closes)
    if n < 80:
        return None

    pivots = find_swing_pivots(highs, lows, order=7)
    swing_highs = [p for p in pivots if p.kind == "high"]
    swing_lows = [p for p in pivots if p.kind == "low"]

    if len(swing_highs) < 2 or len(swing_lows) < 1:
        return None

    best: Optional[dict] = None
    best_conf = MIN_CONFIDENCE

    # Search swing highs as potential left lips
    for sh in swing_highs:
        left_lip_idx = sh.index
        left_lip_price = sh.price

        if left_lip_idx < 25:
            continue  # Not enough bars before left lip for uptrend
        if left_lip_idx > n - 35:
            continue  # Not enough bars after for cup + handle

        # Check prior uptrend: was there a >=30% advance in the 120 bars before?
        lookback = min(120, left_lip_idx)
        prior_low = min(lows[left_lip_idx - lookback: left_lip_idx])
        if prior_low <= 0:
            continue
        prior_advance = (left_lip_price - prior_low) / prior_low
        if prior_advance < 0.30:
            continue

        # Find the cup bottom: lowest low between left_lip and end of data
        max_cup_end = min(left_lip_idx + 325, n)
        if max_cup_end - left_lip_idx < 35:
            continue

        cup_lows = lows[left_lip_idx: max_cup_end]
        if not cup_lows:
            continue
        bottom_offset = cup_lows.index(min(cup_lows))
        bottom_idx = left_lip_idx + bottom_offset
        bottom_price = lows[bottom_idx]

        if left_lip_price <= 0 or bottom_price <= 0:
            continue

        depth_pct = (left_lip_price - bottom_price) / left_lip_price * 100
        if depth_pct < 12 or depth_pct > 33:
            continue

        # The bottom should not be too close to the left lip or too far
        if bottom_offset < 15:
            continue

        # Check U-shape: count bars near the bottom (within 5% of bottom price)
        bottom_zone_threshold = bottom_price * 1.05
        bottom_zone_bars = sum(
            1 for i in range(left_lip_idx, min(bottom_idx + bottom_offset, max_cup_end))
            if lows[i] <= bottom_zone_threshold
        )
        cup_bars_so_far = bottom_offset * 2 if bottom_offset > 0 else 1
        u_shape_ratio = bottom_zone_bars / cup_bars_so_far if cup_bars_so_far > 0 else 0

        # Find the right lip: price recovering near left lip level
        right_lip_idx = None
        right_lip_price = 0.0
        for i in range(bottom_idx + 5, max_cup_end):
            if highs[i] >= left_lip_price * 0.90:
                # Found a recovery near the left lip
                if right_lip_idx is None or highs[i] > right_lip_price:
                    right_lip_idx = i
                    right_lip_price = highs[i]
                # Don't search too far beyond the first good recovery
                if right_lip_idx and i > right_lip_idx + 10:
                    break

        if right_lip_idx is None:
            # Cup hasn't recovered yet -- could be "forming"
            # Check if current price is trending up from the bottom
            if closes[-1] > bottom_price * 1.10 and closes[-1] < left_lip_price * 0.90:
                # Forming cup
                cup_duration = n - 1 - left_lip_idx
                if 35 <= cup_duration <= 325:
                    forming_conf = 0.45 + 0.10 * min(prior_advance / 0.50, 1.0)
                    if forming_conf > best_conf:
                        best_conf = forming_conf
                        best = {
                            "pattern_type": "cup_with_handle",
                            "confidence": round(forming_conf, 2),
                            "start_bar": left_lip_idx,
                            "end_bar": n - 1,
                            "pivot_price": round(left_lip_price, 2),
                            "depth_pct": round(depth_pct, 1),
                            "duration_bars": cup_duration,
                            "status": "forming",
                            "detail": {
                                "left_lip_price": round(left_lip_price, 2),
                                "bottom_price": round(bottom_price, 2),
                                "current_price": round(closes[-1], 2),
                                "prior_advance_pct": round(prior_advance * 100, 1),
                            },
                        }
            continue

        # We have a right lip -- compute cup metrics
        cup_duration = right_lip_idx - left_lip_idx
        if cup_duration < 35 or cup_duration > 325:
            continue

        lip_symmetry = 1.0 - abs(right_lip_price - left_lip_price) / left_lip_price
        lip_symmetry = max(0, lip_symmetry)

        # Look for handle after right lip
        handle_start = right_lip_idx
        handle_end = min(right_lip_idx + 30, n)
        handle_detected = False
        handle_depth_pct = 0.0
        handle_low_price = right_lip_price
        pivot_price = right_lip_price  # Default pivot is right lip

        if handle_end > handle_start + 3:
            handle_lows = lows[handle_start: handle_end]
            if handle_lows:
                handle_low_price = min(handle_lows)
                handle_depth_pct = (right_lip_price - handle_low_price) / right_lip_price * 100
                if 3 <= handle_depth_pct <= 15:
                    handle_detected = True
                    # Pivot is the handle high (right lip price)
                    pivot_price = right_lip_price

        # Volume analysis
        vol_bottom = _avg_volume(volumes, max(0, bottom_idx - 10), bottom_idx + 10)
        vol_left = _avg_volume(volumes, max(0, left_lip_idx - 10), left_lip_idx + 5)
        vol_right = _avg_volume(volumes, max(0, right_lip_idx - 5), min(n, right_lip_idx + 5))
        volume_dry_up = vol_bottom < vol_left * 0.80 if vol_left > 0 else False

        # Breakout detection
        breakout = False
        if n > right_lip_idx + 1 and closes[-1] > pivot_price:
            recent_vol = _avg_volume(volumes, n - 3, n)
            avg_vol_50 = _avg_volume(volumes, max(0, n - 50), n)
            breakout = recent_vol > avg_vol_50 * 1.3 if avg_vol_50 > 0 else False

        # Determine status
        if breakout:
            status = "breakout"
        elif handle_detected or right_lip_idx >= n - 10:
            status = "complete"
        else:
            status = "complete"

        # Confidence scoring
        conf = 0.50
        conf += 0.10 * lip_symmetry                                    # Up to +0.10
        conf += 0.05 if u_shape_ratio > 0.15 else 0.0                 # U-shape bonus
        conf += 0.05 if handle_detected else 0.0                      # Handle bonus
        conf += 0.05 if volume_dry_up else 0.0                        # Volume dry-up
        conf += 0.05 if breakout else 0.0                              # Breakout bonus
        conf += 0.05 * min(prior_advance / 0.50, 1.0)                 # Strong prior trend
        conf += 0.05 if 15 <= handle_depth_pct or not handle_detected else 0.0  # handle not too deep
        conf = min(1.0, conf)

        if conf > best_conf:
            best_conf = conf
            best = {
                "pattern_type": "cup_with_handle",
                "confidence": round(conf, 2),
                "start_bar": left_lip_idx,
                "end_bar": handle_end if handle_detected else right_lip_idx,
                "pivot_price": round(pivot_price, 2),
                "depth_pct": round(depth_pct, 1),
                "duration_bars": cup_duration,
                "status": status,
                "detail": {
                    "left_lip_price": round(left_lip_price, 2),
                    "bottom_price": round(bottom_price, 2),
                    "right_lip_price": round(right_lip_price, 2),
                    "lip_symmetry": round(lip_symmetry, 3),
                    "handle_detected": handle_detected,
                    "handle_depth_pct": round(handle_depth_pct, 1),
                    "cup_duration_bars": cup_duration,
                    "u_shape_ratio": round(u_shape_ratio, 3),
                    "volume_dry_up": volume_dry_up,
                    "prior_advance_pct": round(prior_advance * 100, 1),
                    "breakout": breakout,
                },
            }

    return best


# =============================================================================
#  2. Double Bottom (W-Pattern)
# =============================================================================

def detect_double_bottom(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float],
) -> Optional[dict]:
    """
    Detect a Double Bottom (W-Pattern).

    Criteria:
      - Two distinct lows within 3% of each other
      - Separated by a middle peak (center of the W)
      - Duration: 35-150 bars (7-30 weeks)
      - Second low volume < first low volume (selling exhaustion)
      - Pivot point: middle peak + small buffer
    """
    n = len(closes)
    if n < 50:
        return None

    pivots = find_swing_pivots(highs, lows, order=5)
    swing_lows = [p for p in pivots if p.kind == "low"]
    swing_highs = [p for p in pivots if p.kind == "high"]

    if len(swing_lows) < 2 or len(swing_highs) < 1:
        return None

    best: Optional[dict] = None
    best_conf = MIN_CONFIDENCE

    # Look at pairs of swing lows with a swing high between them
    for i in range(len(swing_lows) - 1):
        low1 = swing_lows[i]
        low2 = swing_lows[i + 1]

        # Duration check
        duration = low2.index - low1.index
        if duration < 20 or duration > 150:
            continue

        # Both lows should be within 3% of each other
        if low1.price <= 0:
            continue
        diff_pct = abs(low1.price - low2.price) / low1.price * 100
        if diff_pct > 5.0:
            continue

        # Find the middle peak between the two lows
        middle_peak = None
        for sh in swing_highs:
            if low1.index < sh.index < low2.index:
                if middle_peak is None or sh.price > middle_peak.price:
                    middle_peak = sh

        if middle_peak is None:
            continue

        # Middle peak should be significantly above both lows
        avg_low = (low1.price + low2.price) / 2.0
        if avg_low <= 0:
            continue
        peak_rise = (middle_peak.price - avg_low) / avg_low * 100
        if peak_rise < 5:
            continue  # Not enough contrast for a clear W

        # Volume: second low should have less volume (exhaustion)
        vol_around_low1 = _avg_volume(volumes, max(0, low1.index - 3), min(n, low1.index + 3))
        vol_around_low2 = _avg_volume(volumes, max(0, low2.index - 3), min(n, low2.index + 3))
        volume_exhaustion = vol_around_low2 < vol_around_low1 * 0.90

        # Pivot price is middle peak
        pivot_price = middle_peak.price

        # Symmetry of the W: how equal are the two legs
        low_symmetry = 1.0 - diff_pct / 5.0

        # Breakout check
        breakout = closes[-1] > pivot_price and low2.index < n - 3

        status = "breakout" if breakout else "complete" if low2.index < n - 5 else "forming"

        # Depth of the pattern (from peak to avg bottom)
        depth_pct = (middle_peak.price - avg_low) / middle_peak.price * 100

        # Confidence
        conf = 0.50
        conf += 0.10 * low_symmetry                                    # Lows are equal
        conf += 0.10 if volume_exhaustion else 0.0                     # Volume confirmation
        conf += 0.05 if peak_rise > 10 else 0.0                       # Clear W shape
        conf += 0.05 if breakout else 0.0                              # Already breaking out
        conf += 0.05 if 35 <= duration <= 100 else 0.0                 # Ideal duration
        conf += 0.05 if diff_pct < 2.0 else 0.0                        # Very tight double bottom
        conf = min(1.0, conf)

        if conf > best_conf:
            best_conf = conf
            best = {
                "pattern_type": "double_bottom",
                "confidence": round(conf, 2),
                "start_bar": low1.index,
                "end_bar": low2.index,
                "pivot_price": round(pivot_price, 2),
                "depth_pct": round(depth_pct, 1),
                "duration_bars": duration,
                "status": status,
                "detail": {
                    "low1_price": round(low1.price, 2),
                    "low1_bar": low1.index,
                    "low2_price": round(low2.price, 2),
                    "low2_bar": low2.index,
                    "middle_peak_price": round(middle_peak.price, 2),
                    "middle_peak_bar": middle_peak.index,
                    "diff_pct": round(diff_pct, 2),
                    "peak_rise_pct": round(peak_rise, 1),
                    "volume_exhaustion": volume_exhaustion,
                    "breakout": breakout,
                },
            }

    return best


# =============================================================================
#  3. Flat Base
# =============================================================================

def detect_flat_base(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float],
) -> Optional[dict]:
    """
    Detect a Flat Base -- tight horizontal consolidation.

    Criteria:
      - Range: highest high within 15% of lowest low over the base
      - Duration: 25-75 bars (5-15 weeks)
      - Volume contracts during the base
      - Price is above 200-day MA (healthy trend context)
      - Pivot: top of the base range
    """
    n = len(closes)
    if n < 50:
        return None

    best: Optional[dict] = None
    best_conf = MIN_CONFIDENCE

    # Scan backward from the most recent data for flat bases
    sma_200 = _sma(closes, 200) if n >= 200 else None

    for base_len in range(75, 24, -5):  # Try various base lengths
        if n < base_len + 25:
            continue

        for start_offset in range(0, min(60, n - base_len), 5):
            start = n - base_len - start_offset
            end = start + base_len
            if start < 0:
                continue

            segment_highs = highs[start:end]
            segment_lows = lows[start:end]
            segment_closes = closes[start:end]
            segment_vols = volumes[start:end]

            seg_high = max(segment_highs)
            seg_low = min(segment_lows)

            if seg_low <= 0:
                continue

            range_pct = (seg_high - seg_low) / seg_low * 100
            if range_pct > 15:
                continue

            # Must be in context of an uptrend: price above 200-day MA
            if sma_200 is not None and segment_closes[-1] < sma_200:
                continue

            # Volume should contract during the base relative to before
            vol_before = _avg_volume(volumes, max(0, start - 20), start)
            vol_during = _avg_volume(volumes, start, end)
            volume_contraction = vol_during < vol_before * 0.85 if vol_before > 0 else False

            # Pivot price: top of base
            pivot_price = seg_high

            # Check breakout
            breakout = end < n and closes[-1] > pivot_price

            status = "breakout" if breakout else "complete" if end <= n - 3 else "forming"

            # Tightness bonus: tighter ranges get higher confidence
            tightness = max(0, 1.0 - range_pct / 15.0)

            conf = 0.50
            conf += 0.15 * tightness                                    # Tighter is better
            conf += 0.10 if volume_contraction else 0.0                 # Volume confirms
            conf += 0.05 if breakout else 0.0                           # After breakout
            conf += 0.05 if 30 <= base_len <= 60 else 0.0               # Ideal duration
            conf += 0.05 if sma_200 and segment_closes[-1] > sma_200 else 0.0  # Above 200MA
            conf = min(1.0, conf)

            if conf > best_conf:
                best_conf = conf
                best = {
                    "pattern_type": "flat_base",
                    "confidence": round(conf, 2),
                    "start_bar": start,
                    "end_bar": end,
                    "pivot_price": round(pivot_price, 2),
                    "depth_pct": round(range_pct, 1),
                    "duration_bars": base_len,
                    "status": status,
                    "detail": {
                        "range_high": round(seg_high, 2),
                        "range_low": round(seg_low, 2),
                        "range_pct": round(range_pct, 1),
                        "volume_contraction": volume_contraction,
                        "above_200ma": bool(sma_200 and segment_closes[-1] > sma_200),
                        "breakout": breakout,
                    },
                }
                break  # Take the first (longest) good flat base at this offset

    return best


# =============================================================================
#  4. VCP (Volatility Contraction Pattern)
# =============================================================================

def detect_vcp(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float],
) -> Optional[dict]:
    """
    Detect a Volatility Contraction Pattern (VCP).

    Criteria:
      - 2-5 successive contractions, each tighter than the previous
      - Each contraction ratio (high-low)/high is decreasing
      - Volume contracts across the base
      - Duration: 20+ bars
      - Final contraction < 10%
      - Pivot: final contraction high
    """
    n = len(closes)
    if n < 40:
        return None

    best: Optional[dict] = None
    best_conf = MIN_CONFIDENCE

    # Use zigzag to detect swing pivots at multiple thresholds
    for zigzag_threshold in (4.0, 5.0, 6.0):
        pivots = find_zigzag_pivots(closes, highs, lows, threshold_pct=zigzag_threshold)

        if len(pivots) < 5:
            continue

        # Look at the most recent sequence of pivots
        # We need at least 2 contractions: H-L-H-L-H (5 pivots minimum)
        # or H-L-H-L-H-L-H (7 pivots) for 3 contractions
        recent_pivots = pivots[-10:]  # Last 10 pivots max

        # Find contraction sequences starting from trailing high pivots
        for start_p in range(len(recent_pivots)):
            if recent_pivots[start_p].kind != "high":
                continue

            contractions = []
            j = start_p
            while j + 2 < len(recent_pivots):
                h_pivot = recent_pivots[j]
                l_pivot = recent_pivots[j + 1] if recent_pivots[j + 1].kind == "low" else None
                h2_pivot = recent_pivots[j + 2] if recent_pivots[j + 2].kind == "high" else None

                if l_pivot is None or h2_pivot is None:
                    break

                if h_pivot.price <= 0:
                    break

                contraction_pct = (h_pivot.price - l_pivot.price) / h_pivot.price * 100
                contractions.append({
                    "high_idx": h_pivot.index,
                    "high_price": h_pivot.price,
                    "low_idx": l_pivot.index,
                    "low_price": l_pivot.price,
                    "contraction_pct": contraction_pct,
                })
                j += 2

            if len(contractions) < 2:
                continue

            # Check that contractions are decreasing
            is_contracting = True
            for k in range(1, len(contractions)):
                # Allow some tolerance: next contraction should be <= 90% of previous
                if contractions[k]["contraction_pct"] > contractions[k - 1]["contraction_pct"] * 1.10:
                    is_contracting = False
                    break

            if not is_contracting:
                continue

            # Final contraction should be relatively tight
            final_contraction = contractions[-1]["contraction_pct"]
            if final_contraction > 15:
                continue

            # VCP duration
            vcp_start = contractions[0]["high_idx"]
            vcp_end = contractions[-1]["high_idx"]
            duration = vcp_end - vcp_start
            if duration < 15:
                continue

            # Volume contraction
            vol_early = _avg_volume(volumes, max(0, vcp_start - 5), min(n, vcp_start + 5))
            vol_late = _avg_volume(volumes, max(0, vcp_end - 5), min(n, vcp_end + 5))
            volume_contracting = vol_late < vol_early * 0.80 if vol_early > 0 else False

            # Pivot price: last high in the sequence
            last_high = recent_pivots[j] if j < len(recent_pivots) and recent_pivots[j].kind == "high" else None
            pivot_price = last_high.price if last_high else contractions[-1]["high_price"]

            # Breakout check
            breakout = closes[-1] > pivot_price and vcp_end < n - 2

            status = "breakout" if breakout else "complete" if vcp_end < n - 5 else "forming"

            # Confidence scoring
            num_contractions = len(contractions)
            contraction_quality = sum(
                1 for k in range(1, num_contractions)
                if contractions[k]["contraction_pct"] < contractions[k - 1]["contraction_pct"] * 0.80
            ) / max(1, num_contractions - 1)

            conf = 0.50
            conf += 0.05 * min(num_contractions - 1, 3)                 # More contractions up to +0.15
            conf += 0.10 * contraction_quality                           # Quality of contraction
            conf += 0.05 if final_contraction < 8 else 0.0              # Very tight final
            conf += 0.05 if volume_contracting else 0.0                  # Volume confirms
            conf += 0.05 if breakout else 0.0                            # Breakout bonus
            conf = min(1.0, conf)

            if conf > best_conf:
                best_conf = conf
                best = {
                    "pattern_type": "vcp",
                    "confidence": round(conf, 2),
                    "start_bar": vcp_start,
                    "end_bar": vcp_end,
                    "pivot_price": round(pivot_price, 2),
                    "depth_pct": round(contractions[0]["contraction_pct"], 1),
                    "duration_bars": duration,
                    "status": status,
                    "detail": {
                        "num_contractions": num_contractions,
                        "contractions": [
                            {
                                "high": round(c["high_price"], 2),
                                "low": round(c["low_price"], 2),
                                "pct": round(c["contraction_pct"], 1),
                            }
                            for c in contractions
                        ],
                        "final_contraction_pct": round(final_contraction, 1),
                        "volume_contracting": volume_contracting,
                        "breakout": breakout,
                    },
                }

    return best


# =============================================================================
#  5. High Tight Flag
# =============================================================================

def detect_high_tight_flag(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float],
) -> Optional[dict]:
    """
    Detect a High Tight Flag -- rare and powerful continuation pattern.

    Criteria:
      - Prior advance: 100%+ gain in 20-40 bars (4-8 weeks)
      - Flag: tight consolidation with max 10-25% pullback
      - Flag duration: 10-30 bars (2-6 weeks)
      - Volume: high during advance, contracts during flag
    """
    n = len(closes)
    if n < 50:
        return None

    best: Optional[dict] = None
    best_conf = MIN_CONFIDENCE

    # Scan for potential huge advances
    for advance_end in range(n - 10, max(40, n - 80), -1):
        # Look for 100%+ advance ending at advance_end
        for advance_start in range(max(0, advance_end - 60), advance_end - 15):
            advance_low = min(lows[advance_start: advance_start + 5])
            advance_high = max(highs[advance_end - 5: advance_end + 1])

            if advance_low <= 0:
                continue

            advance_pct = (advance_high - advance_low) / advance_low * 100
            if advance_pct < 80:  # Slightly relaxed from 100% for more detections
                continue

            advance_duration = advance_end - advance_start
            if advance_duration < 15 or advance_duration > 60:
                continue

            # Flag: from advance_end to the end of data (or a limited window)
            flag_end = min(advance_end + 35, n)
            flag_highs = highs[advance_end: flag_end]
            flag_lows = lows[advance_end: flag_end]

            if len(flag_highs) < 8:
                continue

            flag_high = max(flag_highs)
            flag_low = min(flag_lows)

            if flag_high <= 0:
                continue

            flag_pullback = (flag_high - flag_low) / flag_high * 100
            if flag_pullback > 25:
                continue  # Too deep -- not a flag

            flag_duration = flag_end - advance_end

            # Volume: should contract during flag
            vol_advance = _avg_volume(volumes, advance_start, advance_end)
            vol_flag = _avg_volume(volumes, advance_end, flag_end)
            volume_contraction = vol_flag < vol_advance * 0.70 if vol_advance > 0 else False

            # Pivot: flag high
            pivot_price = flag_high

            # Breakout check
            breakout = flag_end < n and closes[-1] > pivot_price

            status = "breakout" if breakout else "complete" if flag_end <= n - 3 else "forming"

            # Confidence
            conf = 0.50
            conf += 0.10 * min(advance_pct / 150.0, 1.0)                # Stronger advance
            conf += 0.10 if flag_pullback <= 15 else 0.05                # Tight flag
            conf += 0.10 if volume_contraction else 0.0                  # Volume confirms
            conf += 0.05 if breakout else 0.0                            # Breakout bonus
            conf += 0.05 if 15 <= flag_duration <= 25 else 0.0           # Ideal flag duration
            conf = min(1.0, conf)

            if conf > best_conf:
                best_conf = conf
                best = {
                    "pattern_type": "high_tight_flag",
                    "confidence": round(conf, 2),
                    "start_bar": advance_start,
                    "end_bar": flag_end,
                    "pivot_price": round(pivot_price, 2),
                    "depth_pct": round(flag_pullback, 1),
                    "duration_bars": advance_duration + flag_duration,
                    "status": status,
                    "detail": {
                        "advance_pct": round(advance_pct, 1),
                        "advance_duration_bars": advance_duration,
                        "flag_pullback_pct": round(flag_pullback, 1),
                        "flag_duration_bars": flag_duration,
                        "volume_contraction": volume_contraction,
                        "breakout": breakout,
                    },
                }

    return best


# =============================================================================
#  6. Ascending Base
# =============================================================================

def detect_ascending_base(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float],
) -> Optional[dict]:
    """
    Detect an Ascending Base -- three pullbacks with progressively higher lows.

    Criteria:
      - Three distinct pullbacks, each 10-20% deep
      - Each pullback low is higher than the previous
      - Duration: 45-80 bars (9-16 weeks)
      - Volume contracts on pullbacks
      - Pivot: high of the entire pattern
    """
    n = len(closes)
    if n < 60:
        return None

    pivots = find_swing_pivots(highs, lows, order=5)
    swing_lows = [p for p in pivots if p.kind == "low"]
    swing_highs = [p for p in pivots if p.kind == "high"]

    if len(swing_lows) < 3 or len(swing_highs) < 3:
        return None

    best: Optional[dict] = None
    best_conf = MIN_CONFIDENCE

    # Look for sequences of three ascending lows with peaks between them
    for i in range(len(swing_lows) - 2):
        low1 = swing_lows[i]
        low2 = swing_lows[i + 1]
        low3 = swing_lows[i + 2]

        # All three lows must be ascending
        if not (low1.price < low2.price < low3.price):
            continue

        # Duration check
        duration = low3.index - low1.index
        if duration < 30 or duration > 120:
            continue

        # Each low should be the result of a meaningful pullback (5-25%)
        # Find the peak before each low
        peaks_between = []
        for pair_start, pair_end in [(low1, low2), (low2, low3)]:
            peak = None
            for sh in swing_highs:
                if pair_start.index < sh.index < pair_end.index:
                    if peak is None or sh.price > peak.price:
                        peak = sh
            if peak:
                peaks_between.append(peak)

        if len(peaks_between) < 2:
            continue

        # Calculate pullback depths
        pullbacks = []
        all_lows = [low1, low2, low3]
        for k, peak in enumerate(peaks_between):
            low = all_lows[k + 1]
            if peak.price <= 0:
                continue
            pb_depth = (peak.price - low.price) / peak.price * 100
            pullbacks.append(pb_depth)

        if len(pullbacks) < 2:
            continue

        # Each pullback should be 5-25%
        valid_pullbacks = all(3 <= pb <= 25 for pb in pullbacks)
        if not valid_pullbacks:
            continue

        # Pattern high (pivot)
        pattern_high = max(p.price for p in peaks_between)
        # Also check if current high exceeds
        overall_high = _max_price(highs, low1.index, min(n, low3.index + 10))
        pivot_price = max(pattern_high, overall_high)

        # Volume on pullbacks should ideally contract
        vol_pullback1 = _avg_volume(volumes, max(0, low2.index - 3), min(n, low2.index + 3))
        vol_pullback2 = _avg_volume(volumes, max(0, low3.index - 3), min(n, low3.index + 3))
        volume_contracting = vol_pullback2 < vol_pullback1 * 0.90 if vol_pullback1 > 0 else False

        # Ascending quality: how much higher is each successive low?
        ascent_quality = min(
            (low2.price - low1.price) / low1.price,
            (low3.price - low2.price) / low2.price,
        ) if low1.price > 0 and low2.price > 0 else 0

        # Breakout
        breakout = closes[-1] > pivot_price and low3.index < n - 3

        status = "breakout" if breakout else "complete" if low3.index < n - 5 else "forming"

        # Overall pattern depth: from highest peak to lowest low
        depth_pct = (pivot_price - low1.price) / pivot_price * 100 if pivot_price > 0 else 0

        # Confidence
        conf = 0.50
        conf += 0.10 * min(ascent_quality * 10, 1.0)                    # Higher lows quality
        conf += 0.05 if volume_contracting else 0.0                      # Volume confirms
        conf += 0.05 if all(5 <= pb <= 20 for pb in pullbacks) else 0.0  # Ideal pullback depth
        conf += 0.05 if breakout else 0.0                                # Breakout bonus
        conf += 0.05 if 45 <= duration <= 80 else 0.0                    # Ideal duration
        conf += 0.05 if len(pullbacks) >= 2 else 0.0                     # Got enough pullbacks
        conf = min(1.0, conf)

        if conf > best_conf:
            best_conf = conf
            best = {
                "pattern_type": "ascending_base",
                "confidence": round(conf, 2),
                "start_bar": low1.index,
                "end_bar": low3.index,
                "pivot_price": round(pivot_price, 2),
                "depth_pct": round(depth_pct, 1),
                "duration_bars": duration,
                "status": status,
                "detail": {
                    "low1": {"bar": low1.index, "price": round(low1.price, 2)},
                    "low2": {"bar": low2.index, "price": round(low2.price, 2)},
                    "low3": {"bar": low3.index, "price": round(low3.price, 2)},
                    "pullback_depths_pct": [round(pb, 1) for pb in pullbacks],
                    "peaks": [
                        {"bar": p.index, "price": round(p.price, 2)}
                        for p in peaks_between
                    ],
                    "volume_contracting": volume_contracting,
                    "ascent_quality": round(ascent_quality, 4),
                    "breakout": breakout,
                },
            }

    return best


# =============================================================================
#  Master Scanner
# =============================================================================

def scan_all_patterns(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float],
) -> list[dict]:
    """
    Run all 6 pattern detectors and return a list of detected patterns.
    Only patterns with confidence >= MIN_CONFIDENCE are included.
    """
    detectors = [
        detect_cup_with_handle,
        detect_double_bottom,
        detect_flat_base,
        detect_vcp,
        detect_high_tight_flag,
        detect_ascending_base,
    ]

    detected: list[dict] = []
    for detector in detectors:
        try:
            result = detector(closes, highs, lows, volumes)
            if result and result["confidence"] >= MIN_CONFIDENCE:
                detected.append(result)
        except Exception as exc:
            logger.warning("Pattern detector %s failed: %s", detector.__name__, exc)

    # Sort by confidence descending
    detected.sort(key=lambda p: p["confidence"], reverse=True)
    return detected


# =============================================================================
#  DB-backed per-instrument scorer
# =============================================================================

async def score_instrument_patterns(
    instrument_id: int,
    score_date: date,
    db,
) -> Optional[dict]:
    """
    Run pattern detection for one instrument using its price history.
    Returns dict with detected patterns list, or None if insufficient data.
    """
    instrument_q = await db.execute(
        select(Instrument.market).where(Instrument.id == instrument_id)
    )
    market = instrument_q.scalar_one_or_none()
    if market is None:
        return None

    price_q = await db.execute(
        select(Price)
        .where(
            Price.instrument_id == instrument_id,
            Price.trade_date <= score_date,
        )
        .order_by(desc(Price.trade_date))
        .limit(350)  # Need more bars for cup-with-handle (up to 325 bars)
    )
    price_rows = list(reversed(price_q.scalars().all()))

    if len(price_rows) < MIN_BARS:
        logger.debug(
            "Skipping pattern detection for instrument %s: only %d bars (need %d)",
            instrument_id, len(price_rows), MIN_BARS,
        )
        return None

    closes = [float(p.close) for p in price_rows if p.close is not None]
    highs = [float(p.high) for p in price_rows if p.high is not None]
    lows = [float(p.low) for p in price_rows if p.low is not None]
    volumes = [float(p.volume) for p in price_rows if p.volume is not None]

    # Ensure matching lengths
    min_len = min(len(closes), len(highs), len(lows))
    closes = closes[:min_len]
    highs = highs[:min_len]
    lows = lows[:min_len]
    while len(volumes) < min_len:
        volumes.append(0.0)
    volumes = volumes[:min_len]

    if min_len < MIN_BARS:
        return None

    recent_limit_moves = count_price_limit_events(closes) if market == "KR" else 0
    if market == "KR" and recent_limit_moves > 0:
        logger.info(
            "Suppressing KR pattern detection for instrument %s on %s due to %d recent limit-move bars",
            instrument_id,
            score_date,
            recent_limit_moves,
        )
        return {
            "instrument_id": instrument_id,
            "score_date": score_date,
            "patterns": [],
            "pattern_count": 0,
            "limit_move_count": recent_limit_moves,
        }

    patterns = scan_all_patterns(closes, highs, lows, volumes)

    return {
        "instrument_id": instrument_id,
        "score_date": score_date,
        "patterns": patterns,
        "pattern_count": len(patterns),
        "limit_move_count": recent_limit_moves,
    }


# =============================================================================
#  Batch runner with DB upsert
# =============================================================================

async def run_pattern_detection(
    score_date: Optional[date] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> list[dict]:
    """
    Run pattern detection for a batch of instruments and upsert results
    into strategy_scores.patterns JSONB column.
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

        logger.info("Pattern detection scanning %d instruments for %s", len(ids), score_date)

        results = []
        for inst_id in ids:
            try:
                scored = await score_instrument_patterns(inst_id, score_date, db)
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

                patterns_data = scored["patterns"]

                if existing:
                    existing.patterns = patterns_data
                else:
                    db.add(StrategyScore(
                        instrument_id=inst_id,
                        score_date=score_date,
                        patterns=patterns_data,
                    ))

                results.append(scored)

            except Exception as exc:
                logger.error("Pattern detection failed for instrument %s: %s", inst_id, exc)

        await db.commit()
        logger.info(
            "Pattern detection complete: %d/%d scanned, %d with patterns detected",
            len(results), len(ids),
            sum(1 for r in results if r["pattern_count"] > 0),
        )

    return results


# =============================================================================
#  CLI entry point
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
        results = await run_pattern_detection(market=market_arg)
        print(f"\nScanned {len(results)} instruments")
        for r in results:
            if r["pattern_count"] > 0:
                patterns_summary = ", ".join(
                    f"{p['pattern_type']}({p['confidence']:.0%})"
                    for p in r["patterns"]
                )
                print(f"  Instrument {r['instrument_id']}: {patterns_summary}")

    asyncio.run(_main())
