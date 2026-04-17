"""
Piotroski F-Score Engine
=========================
9 binary criteria examining financial health from annual reports.
Each criterion = 0 or 1. Raw F-score (0-9) is normalized to 0-100.

Criteria (from PLAN-FINAL §3.2):

PROFITABILITY (4 points):
  F1: ROA > 0                   (net_income / total_assets > 0)
  F2: Operating cash flow > 0   (cfo > 0)
  F3: ΔROA > 0                  (roa_this_year > roa_last_year)
  F4: Accruals: CFO > net_income (cash earnings exceed accounting earnings)

LEVERAGE / LIQUIDITY (3 points):
  F5: ΔLeverage < 0             (lt_debt/total_assets decreased YoY)
  F6: ΔCurrent Ratio > 0        (current_ratio increased YoY)
  F7: No dilution                (shares_outstanding ≤ last year)

OPERATING EFFICIENCY (2 points):
  F8: ΔGross Margin > 0         (gross_margin increased YoY)
  F9: ΔAsset Turnover > 0       (asset_turnover increased YoY)

Normalized 0-100 mapping:
  0-1→0, 2→15, 3→25, 4→35, 5→50, 6→65, 7→78, 8→90, 9→100
"""

import asyncio
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, desc

from app.core.database import AsyncSessionLocal
from app.models.fundamental import FundamentalAnnual
from app.models.instrument import Instrument
from app.models.strategy_score import StrategyScore

logger = logging.getLogger(__name__)

F_SCORE_NORM = {0: 0, 1: 0, 2: 15, 3: 25, 4: 35, 5: 50, 6: 65, 7: 78, 8: 90, 9: 100}


def _dec(v) -> Optional[float]:
    if v is None:
        return None
    return float(v)


def _safe_div(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or den is None or den == 0:
        return None
    return num / den


def compute_f_score(
    current: dict,
    prior: dict,
) -> tuple[int, float, dict]:
    """
    Compute the 9-point Piotroski F-Score from two years of annual data.

    Args:
        current: Dict with keys matching FundamentalAnnual columns (current year).
        prior:   Dict with same keys (prior year).

    Returns:
        (f_raw, normalized_score, detail_dict)
        f_raw: 0-9 integer
        normalized_score: 0-100 float
        detail_dict: F1-F9 individual results for audit
    """
    detail: dict = {}

    # ── Helper ratios for current year ──────────────────────────────────────
    roa_curr = _safe_div(current.get("net_income"), current.get("total_assets"))
    cfo_curr = current.get("operating_cash_flow")
    leverage_curr = _safe_div(current.get("long_term_debt"), current.get("total_assets"))
    cr_curr = _safe_div(current.get("current_assets"), current.get("current_liabilities"))
    gm_curr = _safe_div(current.get("gross_profit"), current.get("revenue"))
    at_curr = _safe_div(current.get("revenue"), current.get("total_assets"))

    # ── Helper ratios for prior year ────────────────────────────────────────
    roa_prior = _safe_div(prior.get("net_income"), prior.get("total_assets"))
    leverage_prior = _safe_div(prior.get("long_term_debt"), prior.get("total_assets"))
    cr_prior = _safe_div(prior.get("current_assets"), prior.get("current_liabilities"))
    gm_prior = _safe_div(prior.get("gross_profit"), prior.get("revenue"))
    at_prior = _safe_div(prior.get("revenue"), prior.get("total_assets"))

    shares_curr = current.get("shares_outstanding_annual")
    shares_prior = prior.get("shares_outstanding_annual")

    # ── PROFITABILITY ───────────────────────────────────────────────────────
    f1 = int(roa_curr is not None and roa_curr > 0)
    detail["F1_roa_positive"] = {"pass": bool(f1), "roa": roa_curr}

    f2 = int(cfo_curr is not None and cfo_curr > 0)
    detail["F2_cfo_positive"] = {"pass": bool(f2), "cfo": cfo_curr}

    f3 = 0
    if roa_curr is not None and roa_prior is not None:
        f3 = int(roa_curr > roa_prior)
    detail["F3_roa_improving"] = {"pass": bool(f3), "roa_curr": roa_curr, "roa_prior": roa_prior}

    f4 = 0
    ni_curr = current.get("net_income")
    if cfo_curr is not None and ni_curr is not None:
        f4 = int(cfo_curr > ni_curr)
    detail["F4_accruals"] = {"pass": bool(f4), "cfo": cfo_curr, "net_income": ni_curr}

    # ── LEVERAGE / LIQUIDITY ────────────────────────────────────────────────
    f5 = 0
    if leverage_curr is not None and leverage_prior is not None:
        f5 = int(leverage_curr < leverage_prior)
    detail["F5_leverage_decreasing"] = {
        "pass": bool(f5), "lev_curr": leverage_curr, "lev_prior": leverage_prior,
    }

    f6 = 0
    if cr_curr is not None and cr_prior is not None:
        f6 = int(cr_curr > cr_prior)
    detail["F6_current_ratio_improving"] = {
        "pass": bool(f6), "cr_curr": cr_curr, "cr_prior": cr_prior,
    }

    f7 = 0
    if shares_curr is not None and shares_prior is not None:
        f7 = int(shares_curr <= shares_prior)
    detail["F7_no_dilution"] = {
        "pass": bool(f7), "shares_curr": shares_curr, "shares_prior": shares_prior,
    }

    # ── OPERATING EFFICIENCY ────────────────────────────────────────────────
    f8 = 0
    if gm_curr is not None and gm_prior is not None:
        f8 = int(gm_curr > gm_prior)
    detail["F8_gross_margin_improving"] = {
        "pass": bool(f8), "gm_curr": gm_curr, "gm_prior": gm_prior,
    }

    f9 = 0
    if at_curr is not None and at_prior is not None:
        f9 = int(at_curr > at_prior)
    detail["F9_asset_turnover_improving"] = {
        "pass": bool(f9), "at_curr": at_curr, "at_prior": at_prior,
    }

    f_raw = f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9
    normalized = F_SCORE_NORM.get(f_raw, 0)
    detail["f_raw"] = f_raw

    return f_raw, float(normalized), detail


def _annual_to_dict(row: FundamentalAnnual) -> dict:
    """Convert an ORM row to a plain dict with float values."""
    return {
        "net_income": _dec(row.net_income),
        "total_assets": _dec(row.total_assets),
        "operating_cash_flow": _dec(row.operating_cash_flow),
        "long_term_debt": _dec(row.long_term_debt),
        "current_assets": _dec(row.current_assets),
        "current_liabilities": _dec(row.current_liabilities),
        "shares_outstanding_annual": _dec(row.shares_outstanding_annual),
        "gross_profit": _dec(row.gross_profit),
        "revenue": _dec(row.revenue),
    }


async def score_instrument(
    instrument_id: int,
    score_date: date,
    db,
) -> Optional[dict]:
    """
    Compute Piotroski F-Score for one instrument.

    Needs at least 2 annual reports (current + prior year).
    Returns None if insufficient data.
    """
    af_q = await db.execute(
        select(FundamentalAnnual)
        .where(
            FundamentalAnnual.instrument_id == instrument_id,
            FundamentalAnnual.report_date <= score_date,
        )
        .order_by(desc(FundamentalAnnual.report_date))
        .limit(2)
    )
    rows = af_q.scalars().all()

    if len(rows) < 2:
        return None

    current_row, prior_row = rows[0], rows[1]  # descending order
    current = _annual_to_dict(current_row)
    prior = _annual_to_dict(prior_row)

    f_raw, normalized, detail = compute_f_score(current, prior)

    return {
        "instrument_id": instrument_id,
        "score_date": score_date,
        "piotroski_score": normalized,
        "piotroski_f_raw": f_raw,
        "piotroski_detail": detail,
    }


async def run_piotroski_scoring(
    score_date: Optional[date] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> list[dict]:
    """
    Run Piotroski F-Score for a batch of instruments and upsert into strategy_scores.
    """
    if score_date is None:
        score_date = date.today()

    async with AsyncSessionLocal() as db:
        stmt = select(Instrument.id).where(Instrument.is_active == True)
        if market:
            stmt = stmt.where(Instrument.market == market)
        if instrument_ids:
            stmt = stmt.where(Instrument.id.in_(instrument_ids))
        result = await db.execute(stmt)
        ids = [row[0] for row in result.all()]

        logger.info(f"Piotroski scoring {len(ids)} instruments for {score_date}")

        results = []
        for inst_id in ids:
            try:
                scored = await score_instrument(inst_id, score_date, db)
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
                    existing.piotroski_score = scored["piotroski_score"]
                    existing.piotroski_f_raw = scored["piotroski_f_raw"]
                    existing.piotroski_detail = scored["piotroski_detail"]
                else:
                    new_row = StrategyScore(
                        instrument_id=inst_id,
                        score_date=score_date,
                        piotroski_score=scored["piotroski_score"],
                        piotroski_f_raw=scored["piotroski_f_raw"],
                        piotroski_detail=scored["piotroski_detail"],
                    )
                    db.add(new_row)

                results.append(scored)
            except Exception as e:
                logger.error(f"Piotroski scoring failed for instrument {inst_id}: {e}")

        await db.commit()
        logger.info(f"Piotroski scoring complete: {len(results)}/{len(ids)} scored")

    return results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    market_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_piotroski_scoring(market=market_arg))
