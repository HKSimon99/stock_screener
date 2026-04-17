"""
CANSLIM — I: Institutional Sponsorship
========================================
Scores institutional ownership using a bell-curve sweet spot
and directional change.

Scoring table (from PLAN-FINAL §3.1 I):
  < 5%        → 10
  5-14%       → 30
  15-29%      → 55
  30-59%      → 80  (sweet spot)
  60-79%      → 55
  80-89%      → 30
  ≥ 90%       → 10  (too crowded)

  US:  +10 if qoq_change > 0, +5 if fund_quality ≥ 70, cap at 15 if owners < 3
  KR:  +10 if foreign net buying, +10 if institutional net buying, -5 if chaebol cross
  Clamp [0, 100]
"""

from typing import Optional


def _ownership_tier(pct: float) -> int:
    """Map institutional ownership % (0-1 scale) to base score."""
    if pct < 0.05:
        return 10
    if pct < 0.15:
        return 30
    if pct < 0.30:
        return 55
    if pct < 0.60:
        return 80
    if pct < 0.80:
        return 55
    if pct < 0.90:
        return 30
    return 10


def score_i(
    market: str,
    # US fields
    institutional_pct: Optional[float] = None,
    num_institutional_owners: Optional[int] = None,
    qoq_owner_change: Optional[int] = None,
    fund_quality_score: Optional[float] = None,
    # KR fields
    foreign_ownership_pct: Optional[float] = None,
    foreign_net_buy_30d: Optional[float] = None,
    institutional_net_buy_30d: Optional[float] = None,
    is_chaebol_cross: bool = False,
) -> tuple[float, dict]:
    """
    Compute the CANSLIM 'I' sub-score.

    Args:
        market:                 "US" or "KR".
        institutional_pct:      US: institutional ownership ratio (0-1).
        num_institutional_owners: US: count of institutional 13F filers.
        qoq_owner_change:      US: net new institutions vs prior quarter.
        fund_quality_score:     US: avg performance rank of top-10 holders.
        foreign_ownership_pct:  KR: foreign ownership ratio (0-1).
        foreign_net_buy_30d:    KR: net foreign shares bought in 30 days.
        institutional_net_buy_30d: KR: net institutional shares bought in 30 days.
        is_chaebol_cross:       KR: True if ticker flagged as chaebol cross-holding.

    Returns:
        (score, detail_dict)
    """
    detail: dict = {"market": market}

    if market == "US":
        return _score_us(
            institutional_pct, num_institutional_owners,
            qoq_owner_change, fund_quality_score, detail,
        )
    else:
        return _score_kr(
            foreign_ownership_pct, foreign_net_buy_30d,
            institutional_net_buy_30d, is_chaebol_cross, detail,
        )


def _score_us(
    institutional_pct: Optional[float],
    num_owners: Optional[int],
    qoq_change: Optional[int],
    fund_quality: Optional[float],
    detail: dict,
) -> tuple[float, dict]:
    if institutional_pct is None:
        detail["reason"] = "institutional_pct unavailable"
        return 0.0, detail

    base = _ownership_tier(institutional_pct)
    detail["institutional_pct"] = institutional_pct
    detail["base_score"] = base

    # QoQ change bonus
    qoq_bonus = 10 if (qoq_change is not None and qoq_change > 0) else 0
    detail["qoq_owner_change"] = qoq_change
    detail["qoq_bonus"] = qoq_bonus

    # Fund quality bonus
    fq_bonus = 5 if (fund_quality is not None and fund_quality >= 70) else 0
    detail["fund_quality_score"] = fund_quality
    detail["fq_bonus"] = fq_bonus

    score = base + qoq_bonus + fq_bonus

    # Cap if too few owners
    if num_owners is not None and num_owners < 3:
        score = min(score, 15)
        detail["capped_low_owners"] = True
    else:
        detail["capped_low_owners"] = False

    detail["num_institutional_owners"] = num_owners

    score = max(0.0, min(100.0, float(score)))
    return score, detail


def _score_kr(
    foreign_pct: Optional[float],
    foreign_net_buy: Optional[float],
    institutional_net_buy: Optional[float],
    is_chaebol_cross: bool,
    detail: dict,
) -> tuple[float, dict]:
    if foreign_pct is None:
        detail["reason"] = "foreign_ownership_pct unavailable"
        return 0.0, detail

    # Apply chaebol haircut before scoring
    effective_pct = foreign_pct
    if is_chaebol_cross:
        effective_pct = foreign_pct * 0.6  # 40% haircut
    detail["foreign_ownership_pct"] = foreign_pct
    detail["effective_pct"] = effective_pct
    detail["is_chaebol_cross"] = is_chaebol_cross

    base = _ownership_tier(effective_pct)
    detail["base_score"] = base

    # Foreign net buying bonus
    foreign_bonus = 10 if (foreign_net_buy is not None and foreign_net_buy > 0) else 0
    detail["foreign_net_buy_30d"] = foreign_net_buy
    detail["foreign_bonus"] = foreign_bonus

    # Institutional net buying bonus
    inst_bonus = 10 if (institutional_net_buy is not None and institutional_net_buy > 0) else 0
    detail["institutional_net_buy_30d"] = institutional_net_buy
    detail["inst_bonus"] = inst_bonus

    # Chaebol penalty
    chaebol_penalty = -5 if is_chaebol_cross else 0
    detail["chaebol_penalty"] = chaebol_penalty

    score = max(0.0, min(100.0, base + foreign_bonus + inst_bonus + chaebol_penalty))
    return score, detail
