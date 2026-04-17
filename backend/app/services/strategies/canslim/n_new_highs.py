"""
CANSLIM — N: New Highs / Base Breakouts
========================================
Scores proximity to 52-week high, base pattern quality,
and volume confirmation on breakout.

Scoring table (from PLAN-FINAL §3.1 N):
  proximity < 70%  → 0
  70-79%           → 15
  80-84%           → 30
  85-89%           → 50
  90-94%           → 65
  ≥ 95%            → 80
  +10 if valid base pattern detected
  +5  if breakout volume confirmed (close ≥ 98% of high and vol > 1.5× avg50)
  +5  if RS line making new high before price
  Clamp [0, 100]
"""

from typing import Optional


def score_n(
    close: float,
    high_52w: float,
    avg_volume_50d: Optional[float],
    volume_today: Optional[float],
    has_base_pattern: bool = False,
    rs_line_new_high: bool = False,
) -> tuple[float, dict]:
    """
    Compute the CANSLIM 'N' sub-score.

    Args:
        close:           Latest closing price.
        high_52w:        52-week high.
        avg_volume_50d:  50-day average volume.
        volume_today:    Today's volume.
        has_base_pattern: True if a valid chart pattern was detected
                          (cup-with-handle, VCP, flat base, etc.).
        rs_line_new_high: True if the RS line is at a new high before price.

    Returns:
        (score, detail_dict)
    """
    detail: dict = {}

    if high_52w is None or high_52w <= 0:
        detail["reason"] = "invalid 52w high"
        return 0.0, detail

    proximity = close / high_52w
    detail["close"] = close
    detail["high_52w"] = high_52w
    detail["proximity"] = proximity

    # Base tier from proximity
    if proximity < 0.70:
        base = 0
    elif proximity < 0.80:
        base = 15
    elif proximity < 0.85:
        base = 30
    elif proximity < 0.90:
        base = 50
    elif proximity < 0.95:
        base = 65
    else:
        base = 80
    detail["base_score"] = base

    # Pattern bonus
    pattern_bonus = 10 if has_base_pattern else 0
    detail["has_base_pattern"] = has_base_pattern
    detail["pattern_bonus"] = pattern_bonus

    # Breakout volume confirmation
    vol_bonus = 0
    if (
        proximity >= 0.98
        and avg_volume_50d is not None
        and volume_today is not None
        and avg_volume_50d > 0
        and volume_today > 1.5 * avg_volume_50d
    ):
        vol_bonus = 5
    detail["breakout_volume_confirmed"] = vol_bonus > 0
    detail["vol_bonus"] = vol_bonus

    # RS line bonus
    rs_bonus = 5 if rs_line_new_high else 0
    detail["rs_line_new_high"] = rs_line_new_high
    detail["rs_bonus"] = rs_bonus

    score = max(0.0, min(100.0, base + pattern_bonus + vol_bonus + rs_bonus))
    return score, detail
