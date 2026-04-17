"""
CANSLIM — A: Annual Earnings Growth
====================================
Scores the 3-year EPS compound annual growth rate and consistency.

Scoring table (from PLAN-FINAL §3.1 A):
  any negative EPS in last 3 years → 0
  cagr < 15%   → 10
  15-19%       → 30
  20-24%       → 50
  25-34%       → 70
  35-49%       → 85
  ≥ 50%        → 95
  +5  if consecutive growth all 5 years
  -20 if NOT consecutive 3 years
  Clamp [0, 100]
"""

from typing import Optional


def _cagr(eps_start: float, eps_end: float, years: int) -> Optional[float]:
    """Compute compound annual growth rate. Returns None on invalid inputs."""
    if eps_start <= 0 or eps_end <= 0 or years <= 0:
        return None
    return (eps_end / eps_start) ** (1.0 / years) - 1.0


def score_a(
    annual_eps_series: list[Optional[float]],
) -> tuple[float, dict]:
    """
    Compute the CANSLIM 'A' sub-score.

    Args:
        annual_eps_series: Annual EPS values ordered oldest → newest.
                           Ideally 4-6 entries (need at least 4 for 3-year CAGR).

    Returns:
        (score, detail_dict)
    """
    detail: dict = {}

    # Filter out None values but keep positions for gap detection
    valid = [(i, v) for i, v in enumerate(annual_eps_series) if v is not None]
    detail["raw_series"] = annual_eps_series
    detail["valid_count"] = len(valid)

    if len(valid) < 4:
        detail["reason"] = "need at least 4 years of EPS for 3-year CAGR"
        return 0.0, detail

    # Use the last 4 entries for 3-year CAGR
    recent_4 = [v for _, v in valid[-4:]]
    eps_start = recent_4[0]
    eps_end = recent_4[-1]

    # Any negative EPS in the last 3 years (positions [-3:]) → 0
    last_3_years = [v for _, v in valid[-3:]]
    has_negative = any(e is not None and e <= 0 for e in last_3_years)
    detail["last_3_years_eps"] = last_3_years
    detail["has_negative"] = has_negative

    if has_negative:
        detail["reason"] = "negative EPS in last 3 years"
        return 0.0, detail

    cagr = _cagr(eps_start, eps_end, 3)
    detail["cagr_3yr"] = cagr

    if cagr is None:
        detail["reason"] = "cannot compute CAGR (start EPS <= 0)"
        return 0.0, detail

    # Base tier
    if cagr < 0.15:
        base = 10
    elif cagr < 0.20:
        base = 30
    elif cagr < 0.25:
        base = 50
    elif cagr < 0.35:
        base = 70
    elif cagr < 0.50:
        base = 85
    else:
        base = 95
    detail["base_score"] = base

    # Consecutive growth check (last 3 years: each > prior)
    consecutive_3yr = all(
        recent_4[i] < recent_4[i + 1] for i in range(len(recent_4) - 1)
    )
    detail["consecutive_3yr"] = consecutive_3yr

    # 5-year consecutive check (if enough data)
    consecutive_5yr = False
    if len(valid) >= 6:
        recent_6 = [v for _, v in valid[-6:]]
        consecutive_5yr = all(
            recent_6[i] < recent_6[i + 1] for i in range(len(recent_6) - 1)
        )
    detail["consecutive_5yr"] = consecutive_5yr

    # Bonuses / penalties
    bonus = 0
    penalty = 0
    if consecutive_5yr:
        bonus = 5
    if not consecutive_3yr:
        penalty = -20
    detail["bonus_5yr"] = bonus
    detail["penalty_not_consec_3yr"] = penalty

    score = max(0.0, min(100.0, base + bonus + penalty))
    return score, detail
