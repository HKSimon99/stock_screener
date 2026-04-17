"""
Korea Sector Normalizer
=======================
Korean corporate earnings are highly seasonal for certain industries.
This module adjusts EPS/revenue for sector-specific seasonality before
passing values to the CANSLIM C/A scorers.

Key adjustments:
  - Semiconductor (반도체): peak Q3/Q4 → use 2-quarter trailing average
  - Shipbuilding (조선): long-cycle revenue recognition → use 3-quarter average
  - All others: pass-through (use raw quarterly value)
"""

from typing import Optional

# GICS sector strings as stored in instruments.sector
SEMICONDUCTOR_KEYWORDS = [
    "semiconductor", "반도체", "electronic components",
    "electronic equipment", "technology hardware",
]

SHIPBUILDING_KEYWORDS = [
    "shipbuilding", "조선", "marine", "ship",
]


def _matches(sector: Optional[str], keywords: list[str]) -> bool:
    if not sector:
        return False
    s = sector.lower()
    return any(kw in s for kw in keywords)


def get_avg_window(sector: Optional[str]) -> int:
    """
    Return the number of trailing quarters to average for EPS/revenue
    normalization for a given sector string.

    Returns:
        2  — semiconductor (2-quarter average to smooth extreme cyclicality)
        3  — shipbuilding (3-quarter average for long revenue-recognition cycles)
        1  — all other sectors (raw single-quarter value, no averaging)
    """
    if _matches(sector, SEMICONDUCTOR_KEYWORDS):
        return 2
    if _matches(sector, SHIPBUILDING_KEYWORDS):
        return 3
    return 1


def normalize_eps(
    eps_series: list[Optional[float]],
    sector: Optional[str],
) -> Optional[float]:
    """
    Return the sector-adjusted EPS for the most recent quarter.

    Args:
        eps_series: EPS values ordered oldest → newest.
                    Must contain at least `window` entries.
        sector:     Value from instruments.sector (may be None).

    Returns:
        Average EPS over the trailing `window` quarters,
        or None if there is insufficient data.
    """
    window = get_avg_window(sector)
    valid = [v for v in eps_series[-window:] if v is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def normalize_revenue(
    revenue_series: list[Optional[float]],
    sector: Optional[str],
) -> Optional[float]:
    """
    Return the sector-adjusted revenue for the most recent quarter.
    Same averaging logic as normalize_eps.
    """
    window = get_avg_window(sector)
    valid = [v for v in revenue_series[-window:] if v is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)
