"""
CANSLIM — C: Current Quarterly Earnings
========================================
Scores the most recent quarter's EPS growth YoY, revenue growth,
and earnings acceleration / deceleration.

Scoring table (from PLAN-FINAL §3.1 C):
  eps_q0 ≤ 0      → 0
  eps_yoy < 18%   → 0
  18-24%           → 40
  25-39%           → 60
  40-59%           → 75
  ≥ 60%            → 90
  +10 if revenue_yoy ≥ 25%
  +5  if accelerating (3 consecutive quarters of increasing YoY growth)
  -15 if deceleration ≥ 2 quarters
  Clamp [0, 100]

Korea adaptation:
  Semiconductors/Display: thresholds × 0.8
  Shipbuilding/Heavy:     thresholds × 0.6
"""

from typing import Optional


def _tier_score(eps_yoy: float, threshold_mult: float) -> int:
    """Map eps_yoy percentage to a tier score, with sector-adjusted thresholds."""
    t = threshold_mult
    if eps_yoy < 0.18 * t:
        return 0
    if eps_yoy < 0.25 * t:
        return 40
    if eps_yoy < 0.40 * t:
        return 60
    if eps_yoy < 0.60 * t:
        return 75
    return 90


def score_c(
    eps_current: Optional[float],
    eps_same_q_prior: Optional[float],
    revenue_yoy_growth: Optional[float],
    eps_yoy_growth_series: list[Optional[float]],
    sector: Optional[str] = None,
) -> tuple[float, dict]:
    """
    Compute the CANSLIM 'C' sub-score.

    Args:
        eps_current:          EPS for the most recent quarter (after sector normalization).
        eps_same_q_prior:     EPS for the same quarter one year ago.
        revenue_yoy_growth:   Revenue YoY growth ratio for the most recent quarter.
        eps_yoy_growth_series: Last 3+ quarters of EPS YoY growth ratios,
                               ordered oldest → newest. Used for acceleration check.
        sector:               Instrument sector string for Korea threshold adjustment.

    Returns:
        (score, detail_dict)  where score is 0-100 and detail_dict is audit data.
    """
    detail: dict = {}

    # Determine Korea sector threshold multiplier
    threshold_mult = 1.0
    if sector:
        s = sector.lower()
        if any(kw in s for kw in ("semiconductor", "반도체", "display")):
            threshold_mult = 0.8
        elif any(kw in s for kw in ("shipbuilding", "조선", "heavy industry")):
            threshold_mult = 0.6
    detail["threshold_mult"] = threshold_mult

    # Guard: current EPS must be positive
    if eps_current is None or eps_current <= 0:
        detail["reason"] = "eps_current <= 0 or missing"
        return 0.0, detail

    # Compute YoY growth if not already provided in the series
    if eps_same_q_prior is not None and eps_same_q_prior != 0:
        eps_yoy = (eps_current - eps_same_q_prior) / abs(eps_same_q_prior)
    else:
        eps_yoy = None

    detail["eps_current"] = eps_current
    detail["eps_same_q_prior"] = eps_same_q_prior
    detail["eps_yoy"] = eps_yoy

    if eps_yoy is None:
        detail["reason"] = "cannot compute eps_yoy (missing prior)"
        return 0.0, detail

    # Base tier score
    base = _tier_score(eps_yoy, threshold_mult)
    detail["base_score"] = base

    # Revenue bonus
    rev_bonus = 0
    if revenue_yoy_growth is not None and revenue_yoy_growth >= 0.25:
        rev_bonus = 10
    detail["revenue_yoy_growth"] = revenue_yoy_growth
    detail["rev_bonus"] = rev_bonus

    # Acceleration / deceleration
    accel_bonus = 0
    decel_penalty = 0
    valid_growth = [g for g in eps_yoy_growth_series if g is not None]
    detail["eps_yoy_growth_series"] = valid_growth

    if len(valid_growth) >= 3:
        last3 = valid_growth[-3:]
        # Accelerating: each quarter's growth > the one before
        if last3[0] < last3[1] < last3[2]:
            accel_bonus = 5
            detail["accelerating"] = True
        else:
            detail["accelerating"] = False

        # Deceleration: 2+ consecutive declining growth rates
        decel_count = sum(
            1 for i in range(1, len(last3)) if last3[i] < last3[i - 1]
        )
        if decel_count >= 2:
            decel_penalty = -15
            detail["decelerating"] = True
            detail["decel_count"] = decel_count
        else:
            detail["decelerating"] = False
    else:
        detail["accelerating"] = None
        detail["decelerating"] = None

    detail["accel_bonus"] = accel_bonus
    detail["decel_penalty"] = decel_penalty

    score = max(0.0, min(100.0, base + rev_bonus + accel_bonus + decel_penalty))
    return score, detail
