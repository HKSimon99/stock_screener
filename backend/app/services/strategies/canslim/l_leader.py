"""
CANSLIM — L: Leader or Laggard (RS Rating)
============================================
Scores the IBD-style Relative Strength rating.

Scoring table (from PLAN-FINAL §3.1 L):
  rs < 50    → 0
  50-59      → 10
  60-69      → 25
  70-79      → 45
  80-84      → 65
  85-89      → 80
  90-94      → 90
  ≥ 95       → 98
  +5  if industry_group_rs ≥ 80 (leader in leading group)
  -10 if rs dropped 10+ pts in 4 weeks
  Clamp [0, 100]
"""

from typing import Optional


def score_l(
    rs_rating: Optional[float],
    industry_group_rs: Optional[float] = None,
    rs_rating_4w_ago: Optional[float] = None,
) -> tuple[float, dict]:
    """
    Compute the CANSLIM 'L' sub-score.

    Args:
        rs_rating:          Current IBD RS rating (1-99 scale).
        industry_group_rs:  Median RS rating for the instrument's industry group.
        rs_rating_4w_ago:   RS rating from 4 weeks ago (for momentum-drop check).

    Returns:
        (score, detail_dict)
    """
    detail: dict = {}

    if rs_rating is None:
        detail["reason"] = "rs_rating unavailable"
        return 0.0, detail

    detail["rs_rating"] = rs_rating

    # Base tier
    if rs_rating < 50:
        base = 0
    elif rs_rating < 60:
        base = 10
    elif rs_rating < 70:
        base = 25
    elif rs_rating < 80:
        base = 45
    elif rs_rating < 85:
        base = 65
    elif rs_rating < 90:
        base = 80
    elif rs_rating < 95:
        base = 90
    else:
        base = 98
    detail["base_score"] = base

    # Industry group RS bonus
    ig_bonus = 0
    if industry_group_rs is not None and industry_group_rs >= 80:
        ig_bonus = 5
    detail["industry_group_rs"] = industry_group_rs
    detail["ig_bonus"] = ig_bonus

    # RS drop penalty
    drop_penalty = 0
    if rs_rating_4w_ago is not None:
        rs_drop = rs_rating_4w_ago - rs_rating
        detail["rs_drop_4w"] = rs_drop
        if rs_drop >= 10:
            drop_penalty = -10
    detail["drop_penalty"] = drop_penalty

    score = max(0.0, min(100.0, base + ig_bonus + drop_penalty))
    return score, detail
