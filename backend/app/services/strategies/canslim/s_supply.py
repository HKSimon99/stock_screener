"""
CANSLIM — S: Supply and Demand
===============================
Scores float tightness, volume surge days, and up/down volume ratio.

Scoring table (from PLAN-FINAL §3.1 S):
  float_ratio > 0.90   → 20
  0.70-0.90            → 35
  0.50-0.70            → 50
  0.30-0.50            → 70
  < 0.30               → 85
  +10 if volume_surge_days ≥ 2 (accumulation)
  +10 if ud_ratio > 1.5 (buying > selling)
  +5  if buyback active
  -10 if ud_ratio < 0.7 (distribution)
  Korea KOSDAQ: +5 if avg_vol_50d > 1.5× sector median
  Clamp [0, 100]
"""

from typing import Optional


def score_s(
    float_shares: Optional[float],
    shares_outstanding: Optional[float],
    volume_surge_days_20d: int = 0,
    ud_volume_ratio_50d: Optional[float] = None,
    is_buyback_active: bool = False,
    exchange: Optional[str] = None,
    avg_volume_50d: Optional[float] = None,
    sector_median_volume: Optional[float] = None,
) -> tuple[float, dict]:
    """
    Compute the CANSLIM 'S' sub-score.

    Args:
        float_shares:           Number of freely traded shares.
        shares_outstanding:     Total shares outstanding.
        volume_surge_days_20d:  Days in last 20 where volume > 2× avg_vol_50d.
        ud_volume_ratio_50d:    50-day up-volume / down-volume ratio.
        is_buyback_active:      True if company has active buyback program.
        exchange:               Exchange code (for KOSDAQ bonus).
        avg_volume_50d:         50-day average volume.
        sector_median_volume:   Median 50-day avg volume for the instrument's sector.

    Returns:
        (score, detail_dict)
    """
    detail: dict = {}

    # Float ratio
    if (
        float_shares is not None
        and shares_outstanding is not None
        and shares_outstanding > 0
    ):
        float_ratio = float_shares / shares_outstanding
    else:
        float_ratio = None
    detail["float_ratio"] = float_ratio

    # Base from float ratio
    if float_ratio is None:
        base = 50  # neutral default when data unavailable
    elif float_ratio > 0.90:
        base = 20
    elif float_ratio > 0.70:
        base = 35
    elif float_ratio > 0.50:
        base = 50
    elif float_ratio > 0.30:
        base = 70
    else:
        base = 85
    detail["base_score"] = base

    # Volume surge bonus (accumulation signal)
    surge_bonus = 10 if volume_surge_days_20d >= 2 else 0
    detail["volume_surge_days_20d"] = volume_surge_days_20d
    detail["surge_bonus"] = surge_bonus

    # Up/Down volume ratio
    ud_adj = 0
    if ud_volume_ratio_50d is not None:
        if ud_volume_ratio_50d > 1.5:
            ud_adj = 10
        elif ud_volume_ratio_50d < 0.7:
            ud_adj = -10
    detail["ud_volume_ratio_50d"] = ud_volume_ratio_50d
    detail["ud_adj"] = ud_adj

    # Buyback bonus
    buyback_bonus = 5 if is_buyback_active else 0
    detail["is_buyback_active"] = is_buyback_active
    detail["buyback_bonus"] = buyback_bonus

    # KOSDAQ liquidity bonus
    kosdaq_bonus = 0
    if (
        exchange is not None
        and exchange.upper() == "KOSDAQ"
        and avg_volume_50d is not None
        and sector_median_volume is not None
        and sector_median_volume > 0
        and avg_volume_50d > 1.5 * sector_median_volume
    ):
        kosdaq_bonus = 5
    detail["kosdaq_bonus"] = kosdaq_bonus

    score = max(
        0.0,
        min(100.0, base + surge_bonus + ud_adj + buyback_bonus + kosdaq_bonus),
    )
    return score, detail
