"""
Magic Formula Engine (Joel Greenblatt)
=======================================
Two metrics, both ranked within the universe. Lower combined rank = better stock.

  ROIC = EBIT / (Net Working Capital + Net Fixed Assets)
    Net Working Capital = max(current_assets - current_liabilities, 0)  [excess cash excluded via floor]
    Net Fixed Assets    = net_fixed_assets  (total_assets - current_assets)

  EY   = EBIT / Enterprise Value
    EV  = Market Cap + Total Debt - Cash & Equivalents

Scoring:
  1. Compute raw ROIC and EY per instrument.
  2. Rank all instruments by ROIC (desc) and EY (desc) within the universe.
  3. combined_rank = roic_rank + ey_rank  (lower = better)
  4. Normalize: score = (1 - combined_rank / max_combined_rank) * 100  [0-100]
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Optional

from sqlalchemy import select

logger = logging.getLogger(__name__)


def _safe_div(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or den is None or den == 0:
        return None
    return num / den


def compute_magic_formula_raw(
    *,
    ebit: Optional[float],
    current_assets: Optional[float],
    current_liabilities: Optional[float],
    net_fixed_assets: Optional[float],
    market_cap: Optional[float],
    total_debt: Optional[float],
    cash_and_equivalents: Optional[float],
) -> dict:
    """
    Compute raw ROIC and EY for a single instrument.

    Returns a dict with keys:
      roic, ey, ev, nwc, detail, data_sufficient
    """
    detail: dict = {}
    data_sufficient = False

    # ── Net Working Capital ──────────────────────────────────────────────────
    nwc: Optional[float] = None
    if current_assets is not None and current_liabilities is not None:
        nwc = max(current_assets - current_liabilities, 0)
    detail["nwc"] = nwc
    detail["current_assets"] = current_assets
    detail["current_liabilities"] = current_liabilities

    # ── Invested Capital (NWC + Net Fixed Assets) ────────────────────────────
    invested_capital: Optional[float] = None
    if nwc is not None and net_fixed_assets is not None:
        invested_capital = nwc + net_fixed_assets
    detail["net_fixed_assets"] = net_fixed_assets
    detail["invested_capital"] = invested_capital

    # ── ROIC ─────────────────────────────────────────────────────────────────
    roic = _safe_div(ebit, invested_capital)
    detail["ebit"] = ebit
    detail["roic"] = roic

    # ── Enterprise Value ─────────────────────────────────────────────────────
    ev: Optional[float] = None
    net_debt: Optional[float] = None
    if total_debt is not None and cash_and_equivalents is not None:
        net_debt = total_debt - cash_and_equivalents
    elif total_debt is not None:
        net_debt = total_debt
    detail["market_cap"] = market_cap
    detail["total_debt"] = total_debt
    detail["cash_and_equivalents"] = cash_and_equivalents
    detail["net_debt"] = net_debt

    if market_cap is not None and net_debt is not None:
        ev = market_cap + net_debt
    elif market_cap is not None:
        ev = market_cap
    detail["ev"] = ev

    # ── Earnings Yield ───────────────────────────────────────────────────────
    ey = _safe_div(ebit, ev)
    detail["ey"] = ey

    data_sufficient = roic is not None and ey is not None
    detail["data_sufficient"] = data_sufficient

    return {
        "roic": roic,
        "ey": ey,
        "ev": ev,
        "nwc": nwc,
        "detail": detail,
        "data_sufficient": data_sufficient,
    }


def rank_magic_formula_universe(
    instrument_raws: list[dict],
) -> list[dict]:
    """
    Given a list of raw results from compute_magic_formula_raw (each with 'instrument_id',
    'roic', 'ey'), assign universe ranks and return normalized 0-100 scores.

    Args:
        instrument_raws: list of dicts with keys:
          instrument_id, roic, ey, ev, nwc, detail, data_sufficient

    Returns:
        Same list, each dict augmented with:
          roic_rank, ey_rank, combined_rank, score (0-100)
    """
    eligible = [r for r in instrument_raws if r.get("data_sufficient")]
    ineligible = [r for r in instrument_raws if not r.get("data_sufficient")]

    if not eligible:
        for r in instrument_raws:
            r.update({"roic_rank": None, "ey_rank": None, "combined_rank": None, "score": None})
        return instrument_raws

    # Rank by ROIC descending (highest ROIC = rank 1)
    sorted_by_roic = sorted(eligible, key=lambda r: r["roic"], reverse=True)
    for rank, item in enumerate(sorted_by_roic, start=1):
        item["roic_rank"] = rank

    # Rank by EY descending (highest earnings yield = rank 1)
    sorted_by_ey = sorted(eligible, key=lambda r: r["ey"], reverse=True)
    for rank, item in enumerate(sorted_by_ey, start=1):
        item["ey_rank"] = rank

    # Combined rank (lower = better Greenblatt stock)
    for item in eligible:
        item["combined_rank"] = item["roic_rank"] + item["ey_rank"]

    max_combined = 2 * len(eligible)
    for item in eligible:
        item["score"] = round((1 - item["combined_rank"] / max_combined) * 100, 2)

    for r in ineligible:
        r.update({"roic_rank": None, "ey_rank": None, "combined_rank": None, "score": None})

    return eligible + ineligible


async def run_magic_formula_scoring(
    score_date: Optional[date] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> list[dict]:
    """
    Run Magic Formula scoring for a universe of instruments and upsert into strategy_scores.

    Two-pass:
      1. Fetch EBIT, NWC, net_fixed_assets, total_debt, cash from latest annual fundamentals
         + current market_cap (last price * shares_outstanding).
      2. Rank within the universe and normalize to 0-100.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.fundamental import FundamentalAnnual
    from app.models.instrument import Instrument
    from app.models.price import Price
    from app.models.strategy_score import StrategyScore

    if score_date is None:
        score_date = date.today()

    async with AsyncSessionLocal() as db:
        inst_stmt = select(Instrument).where(Instrument.is_active == True)
        if market:
            inst_stmt = inst_stmt.where(Instrument.market == market)
        if instrument_ids:
            inst_stmt = inst_stmt.where(Instrument.id.in_(instrument_ids))
        instruments = (await db.execute(inst_stmt)).scalars().all()

        logger.info("Magic Formula: %d instruments for %s", len(instruments), score_date)

        # ── Pass 1: gather raw ROIC + EY ─────────────────────────────────────
        raws: list[dict] = []
        for inst in instruments:
            try:
                # Latest annual fundamentals
                fa_stmt = (
                    select(FundamentalAnnual)
                    .where(FundamentalAnnual.instrument_id == inst.id)
                    .order_by(FundamentalAnnual.fiscal_year.desc())
                    .limit(1)
                )
                fa = (await db.execute(fa_stmt)).scalars().first()
                if fa is None:
                    raws.append({"instrument_id": inst.id, "data_sufficient": False})
                    continue

                # Latest price for market cap
                price_stmt = (
                    select(Price)
                    .where(Price.instrument_id == inst.id)
                    .order_by(Price.date.desc())
                    .limit(1)
                )
                latest_price = (await db.execute(price_stmt)).scalars().first()
                market_cap = None
                if latest_price and latest_price.close and inst.shares_outstanding:
                    market_cap = float(latest_price.close) * float(inst.shares_outstanding)

                raw = compute_magic_formula_raw(
                    ebit=float(fa.ebit) if fa.ebit is not None else None,
                    current_assets=float(fa.current_assets) if fa.current_assets is not None else None,
                    current_liabilities=float(fa.current_liabilities) if fa.current_liabilities is not None else None,
                    net_fixed_assets=float(fa.net_fixed_assets) if fa.net_fixed_assets is not None else None,
                    market_cap=market_cap,
                    total_debt=float(fa.total_debt) if fa.total_debt is not None else None,
                    cash_and_equivalents=float(fa.cash_and_equivalents) if fa.cash_and_equivalents is not None else None,
                )
                raw["instrument_id"] = inst.id
                raws.append(raw)
            except Exception:
                logger.exception("Magic Formula raw compute failed for %s", inst.id)
                raws.append({"instrument_id": inst.id, "data_sufficient": False})

        # ── Pass 2: rank universe ─────────────────────────────────────────────
        ranked = rank_magic_formula_universe(raws)

        # ── Upsert strategy_scores ────────────────────────────────────────────
        results: list[dict] = []
        for item in ranked:
            inst_id = item["instrument_id"]
            score = item.get("score")
            if score is None:
                continue
            try:
                ss_stmt = select(StrategyScore).where(
                    StrategyScore.instrument_id == inst_id,
                    StrategyScore.score_date == score_date,
                )
                existing = (await db.execute(ss_stmt)).scalars().first()
                mf_data = {
                    "magic_formula_score": round(score, 2),
                    "magic_formula_roic": round(item["roic"], 6) if item.get("roic") is not None else None,
                    "magic_formula_ey": round(item["ey"], 6) if item.get("ey") is not None else None,
                    "magic_formula_detail": {
                        k: v for k, v in item.get("detail", {}).items()
                        if isinstance(v, (int, float, bool, str, type(None)))
                    } | {"roic_rank": item.get("roic_rank"), "ey_rank": item.get("ey_rank"), "combined_rank": item.get("combined_rank")},
                }
                if existing:
                    for k, v in mf_data.items():
                        setattr(existing, k, v)
                else:
                    db.add(StrategyScore(instrument_id=inst_id, score_date=score_date, **mf_data))
                results.append({"instrument_id": inst_id, **mf_data})
            except Exception:
                logger.exception("Magic Formula upsert failed for %s", inst_id)

        await db.commit()
        logger.info("Magic Formula complete: %d/%d scored", len(results), len(instruments))

    return results
