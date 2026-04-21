"""
CANSLIM Orchestrator Engine
============================
Queries all required data for a single instrument, runs each sub-scorer,
applies the M (market-direction) gate, computes the weighted composite,
and upserts the result into strategy_scores.

Composite weights (from PLAN-FINAL §3.1):
    C: 0.20 | A: 0.15 | N: 0.15 | S: 0.10 | L: 0.20 | I: 0.10 | M_gate: 0.10
"""

import asyncio
import logging
import math
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, desc, func as sqlfunc

from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.price import Price
from app.models.fundamental import FundamentalQuarterly, FundamentalAnnual
from app.models.institutional import InstitutionalOwnership
from app.models.market_regime import MarketRegime
from app.models.strategy_score import StrategyScore

from app.services.strategies.canslim.c_earnings import score_c
from app.services.strategies.canslim.a_annual import score_a
from app.services.strategies.canslim.n_new_highs import score_n
from app.services.strategies.canslim.s_supply import score_s
from app.services.strategies.canslim.l_leader import score_l
from app.services.strategies.canslim.i_institutional import score_i
from app.services.korea.sector_normalizer import normalize_eps

logger = logging.getLogger(__name__)

WEIGHTS = {
    "C": 0.20,
    "A": 0.15,
    "N": 0.15,
    "S": 0.10,
    "L": 0.20,
    "I": 0.10,
    "M": 0.10,
}

M_GATE_VALUES = {
    "CONFIRMED_UPTREND": 100,
    "UPTREND_UNDER_PRESSURE": 40,
    "MARKET_IN_CORRECTION": 0,
}

MIN_QUARTERLY_REPORTS = 5
MIN_ANNUAL_REPORTS = 4
MIN_PRICE_BARS = 50
RS_LOOKBACK_BARS = 252
RS_LOOKBACK_WINDOW_DAYS = 450


def _dec(v) -> Optional[float]:
    """Convert Decimal/numeric to float, pass through None."""
    if v is None:
        return None
    return float(v)


def has_minimum_required_data(
    quarterly_count: int,
    annual_count: int,
    price_count: int,
) -> bool:
    """
    Require core fundamentals + price history before producing a CANSLIM score.

    This prevents persisting placeholder composites that are driven only by
    the market-direction gate when the instrument has not actually been loaded.
    """
    return (
        quarterly_count >= MIN_QUARTERLY_REPORTS
        and annual_count >= MIN_ANNUAL_REPORTS
        and price_count >= MIN_PRICE_BARS
    )


def build_market_rs_lookup_from_history(
    price_history_by_instrument: dict[int, list[float]],
) -> dict[int, float]:
    """
    Convert per-instrument close histories into 1-99 RS ratings.

    Uses a simple 1-year return proxy over the last 252 bars, ranked
    cross-sectionally within a market snapshot.
    """
    ranked_returns: list[tuple[int, float]] = []

    for instrument_id, closes in price_history_by_instrument.items():
        if len(closes) < RS_LOOKBACK_BARS:
            continue

        window = closes[-RS_LOOKBACK_BARS:]
        start_close = window[0]
        end_close = window[-1]
        if start_close is None or end_close is None or start_close <= 0:
            continue

        rs_raw = ((end_close - start_close) / start_close) * 100
        ranked_returns.append((instrument_id, rs_raw))

    if not ranked_returns:
        return {}

    ranked_returns.sort(key=lambda item: item[1])
    total = len(ranked_returns)

    rs_lookup: dict[int, float] = {}
    for rank, (instrument_id, _) in enumerate(ranked_returns, start=1):
        rs_lookup[instrument_id] = float(math.floor((rank / total) * 98) + 1)

    return rs_lookup


async def build_market_rs_lookup(
    db,
    market: str,
    score_date: date,
) -> dict[int, float]:
    """
    Build a market-wide RS lookup from historical prices up to score_date.
    """
    price_rows_q = await db.execute(
        select(Price.instrument_id, Price.close)
        .join(Instrument, Instrument.id == Price.instrument_id)
        .where(
            Instrument.market == market,
            Instrument.is_active == True,
            Price.trade_date <= score_date,
            Price.trade_date >= score_date - timedelta(days=RS_LOOKBACK_WINDOW_DAYS),
        )
        .order_by(Price.instrument_id.asc(), Price.trade_date.asc())
    )

    price_history: dict[int, list[float]] = {}
    for instrument_id, close in price_rows_q.all():
        close_val = _dec(close)
        if close_val is None:
            continue
        price_history.setdefault(instrument_id, []).append(close_val)

    return build_market_rs_lookup_from_history(price_history)


async def score_instrument(
    instrument_id: int,
    score_date: date,
    db,
    rs_lookup: Optional[dict[int, float]] = None,
    rs_4w_lookup: Optional[dict[int, float]] = None,
) -> Optional[dict]:
    """
    Compute full CANSLIM score for one instrument on a given date.

    Returns a dict with all sub-scores, composite, and detail,
    or None if critical data is missing.
    """
    # ── Fetch instrument ────────────────────────────────────────────────────
    inst_q = await db.execute(
        select(Instrument).where(Instrument.id == instrument_id)
    )
    inst = inst_q.scalars().first()
    if not inst:
        return None

    # ── Fetch supporting data — 4 independent queries run in parallel ───────
    # Using asyncio.gather cuts per-instrument latency from ~4 serial round-
    # trips to ~1 (asyncpg pipelines the queries on the same connection).
    async def _fetch_quarterlies():
        r = await db.execute(
            select(FundamentalQuarterly)
            .where(
                FundamentalQuarterly.instrument_id == instrument_id,
                FundamentalQuarterly.report_date <= score_date,
            )
            .order_by(desc(FundamentalQuarterly.report_date))
            .limit(8)
        )
        return list(reversed(r.scalars().all()))  # oldest first

    async def _fetch_annuals():
        r = await db.execute(
            select(FundamentalAnnual)
            .where(
                FundamentalAnnual.instrument_id == instrument_id,
                FundamentalAnnual.report_date <= score_date,
            )
            .order_by(desc(FundamentalAnnual.report_date))
            .limit(6)
        )
        return list(reversed(r.scalars().all()))  # oldest first

    async def _fetch_prices():
        r = await db.execute(
            select(Price)
            .where(
                Price.instrument_id == instrument_id,
                Price.trade_date <= score_date,
            )
            .order_by(desc(Price.trade_date))
            .limit(252)  # ~1 year for 52w high calc
        )
        return list(reversed(r.scalars().all()))  # oldest first

    async def _fetch_inst_own():
        r = await db.execute(
            select(InstitutionalOwnership)
            .where(
                InstitutionalOwnership.instrument_id == instrument_id,
                InstitutionalOwnership.report_date <= score_date,
            )
            .order_by(desc(InstitutionalOwnership.report_date))
            .limit(1)
        )
        return r.scalars().first()

    quarterlies, annuals, prices, inst_own = await asyncio.gather(
        _fetch_quarterlies(),
        _fetch_annuals(),
        _fetch_prices(),
        _fetch_inst_own(),
    )

    if not has_minimum_required_data(
        quarterly_count=len(quarterlies),
        annual_count=len(annuals),
        price_count=len(prices),
    ):
        logger.debug(
            "Skipping CANSLIM for instrument %s due to insufficient core data "
            "(quarterlies=%s, annuals=%s, prices=%s)",
            instrument_id,
            len(quarterlies),
            len(annuals),
            len(prices),
        )
        return None

    # ── Fetch market regime (sequential — needs inst.market from above) ─────
    regime_q = await db.execute(
        select(MarketRegime)
        .where(
            MarketRegime.market == inst.market,
            MarketRegime.effective_date <= score_date,
        )
        .order_by(desc(MarketRegime.effective_date))
        .limit(1)
    )
    regime = regime_q.scalars().first()

    # ════════════════════════════════════════════════════════════════════════
    # C — Current quarterly earnings
    # ════════════════════════════════════════════════════════════════════════
    c_score = 0.0
    c_detail: dict = {}
    if len(quarterlies) >= 5:  # need current + 4 prior for YoY
        q_current = quarterlies[-1]
        # Find same quarter one year ago
        q_prior = None
        for q in quarterlies:
            if (
                q.fiscal_quarter == q_current.fiscal_quarter
                and q.fiscal_year == q_current.fiscal_year - 1
            ):
                q_prior = q
                break

        eps_current_raw = _dec(q_current.eps)
        eps_prior_raw = _dec(q_prior.eps) if q_prior else None

        # Apply Korea sector normalization
        eps_series = [_dec(q.eps) for q in quarterlies]
        eps_current = normalize_eps(eps_series, inst.sector) if inst.market == "KR" else eps_current_raw

        rev_yoy = _dec(q_current.revenue_yoy_growth)
        eps_yoy_series = [_dec(q.eps_yoy_growth) for q in quarterlies]

        c_score, c_detail = score_c(
            eps_current=eps_current,
            eps_same_q_prior=eps_prior_raw,
            revenue_yoy_growth=rev_yoy,
            eps_yoy_growth_series=eps_yoy_series,
            sector=inst.sector,
        )
    else:
        c_detail["reason"] = f"insufficient quarterly data ({len(quarterlies)} < 5)"

    # ════════════════════════════════════════════════════════════════════════
    # A — Annual earnings growth
    # ════════════════════════════════════════════════════════════════════════
    a_score = 0.0
    a_detail: dict = {}
    annual_eps = [_dec(a.eps) for a in annuals]
    if len(annual_eps) >= 4:
        a_score, a_detail = score_a(annual_eps)
    else:
        a_detail["reason"] = f"insufficient annual data ({len(annual_eps)} < 4)"

    # ════════════════════════════════════════════════════════════════════════
    # N — New highs / base
    # ════════════════════════════════════════════════════════════════════════
    n_score = 0.0
    n_detail: dict = {}
    if prices:
        latest = prices[-1]
        highs = [_dec(p.high) for p in prices if p.high is not None]
        high_52w = max(highs) if highs else 0
        close = _dec(latest.close) or 0
        avg_vol = _dec(latest.avg_volume_50d)
        vol_today = latest.volume

        # Wire in pattern detection (Phase 3.4) and RS line new high (Phase 3.5)
        # Read from an existing strategy_scores row for this date if available
        _existing_ss_q = await db.execute(
            select(StrategyScore).where(
                StrategyScore.instrument_id == instrument_id,
                StrategyScore.score_date == score_date,
            )
        )
        _existing_ss = _existing_ss_q.scalars().first()

        has_base = False
        rs_new_hi = False
        if _existing_ss:
            # patterns is a JSONB list of detected pattern dicts
            if _existing_ss.patterns:
                has_base = any(
                    p.get("confidence", 0) >= 0.50
                    for p in (_existing_ss.patterns if isinstance(_existing_ss.patterns, list) else [])
                )
            rs_new_hi = bool(_existing_ss.rs_line_new_high)

        n_score, n_detail = score_n(
            close=close,
            high_52w=high_52w,
            avg_volume_50d=avg_vol,
            volume_today=vol_today,
            has_base_pattern=has_base,
            rs_line_new_high=rs_new_hi,
        )
    else:
        n_detail["reason"] = "no price data"

    # ════════════════════════════════════════════════════════════════════════
    # S — Supply / demand
    # ════════════════════════════════════════════════════════════════════════
    s_score = 0.0
    s_detail: dict = {}
    float_sh = _dec(inst.float_shares)
    shares_out = _dec(inst.shares_outstanding)

    # Compute volume surge days (last 20 trading days)
    surge_days = 0
    if len(prices) >= 20:
        recent_20 = prices[-20:]
        for p in recent_20:
            if p.avg_volume_50d and p.volume and p.avg_volume_50d > 0:
                if p.volume > 2 * float(p.avg_volume_50d):
                    surge_days += 1

    # Compute up/down volume ratio (last 50 trading days)
    ud_ratio = None
    if len(prices) >= 2:
        window = prices[-50:] if len(prices) >= 50 else prices
        up_vol = 0
        down_vol = 0
        for i in range(1, len(window)):
            c_curr = _dec(window[i].close)
            c_prev = _dec(window[i - 1].close)
            vol = window[i].volume or 0
            if c_curr is not None and c_prev is not None:
                if c_curr > c_prev:
                    up_vol += vol
                elif c_curr < c_prev:
                    down_vol += vol
        if down_vol > 0:
            ud_ratio = up_vol / down_vol

    buyback = bool(inst_own and inst_own.is_buyback_active)

    s_score, s_detail = score_s(
        float_shares=float_sh,
        shares_outstanding=shares_out,
        volume_surge_days_20d=surge_days,
        ud_volume_ratio_50d=ud_ratio,
        is_buyback_active=buyback,
        exchange=inst.exchange,
    )

    # ════════════════════════════════════════════════════════════════════════
    # L — Leader (RS rating)
    # ════════════════════════════════════════════════════════════════════════
    l_score = 0.0
    l_detail: dict = {}
    if rs_lookup is None:
        rs_lookup = await build_market_rs_lookup(db, inst.market, score_date)
    if rs_4w_lookup is None:
        rs_4w_lookup = await build_market_rs_lookup(db, inst.market, score_date - timedelta(days=28))

    rs_val = rs_lookup.get(instrument_id)
    rs_4w_ago = rs_4w_lookup.get(instrument_id)

    l_score, l_detail = score_l(
        rs_rating=rs_val,
        rs_rating_4w_ago=rs_4w_ago,
    )

    # ════════════════════════════════════════════════════════════════════════
    # I — Institutional sponsorship
    # ════════════════════════════════════════════════════════════════════════
    i_score = 0.0
    i_detail: dict = {}
    if inst.market == "US":
        i_score, i_detail = score_i(
            market="US",
            institutional_pct=_dec(inst_own.institutional_pct) if inst_own else None,
            num_institutional_owners=inst_own.num_institutional_owners if inst_own else None,
            qoq_owner_change=inst_own.qoq_owner_change if inst_own else None,
            fund_quality_score=_dec(inst_own.top_fund_quality_score) if inst_own else None,
        )
    else:
        i_score, i_detail = score_i(
            market="KR",
            foreign_ownership_pct=_dec(inst_own.foreign_ownership_pct) if inst_own else None,
            foreign_net_buy_30d=_dec(inst_own.foreign_net_buy_30d) if inst_own else None,
            institutional_net_buy_30d=_dec(inst_own.institutional_net_buy_30d) if inst_own else None,
            is_chaebol_cross=inst.is_chaebol_cross,
        )

    # ════════════════════════════════════════════════════════════════════════
    # M — Market regime gate
    # ════════════════════════════════════════════════════════════════════════
    regime_state = regime.state if regime else "CONFIRMED_UPTREND"
    m_gate = M_GATE_VALUES.get(regime_state, 0)

    # ════════════════════════════════════════════════════════════════════════
    # Composite
    # ════════════════════════════════════════════════════════════════════════
    composite = (
        WEIGHTS["C"] * c_score
        + WEIGHTS["A"] * a_score
        + WEIGHTS["N"] * n_score
        + WEIGHTS["S"] * s_score
        + WEIGHTS["L"] * l_score
        + WEIGHTS["I"] * i_score
        + WEIGHTS["M"] * m_gate
    )

    return {
        "instrument_id": instrument_id,
        "score_date": score_date,
        "canslim_score": round(composite, 2),
        "canslim_c": round(c_score, 2),
        "canslim_a": round(a_score, 2),
        "canslim_n": round(n_score, 2),
        "canslim_s": round(s_score, 2),
        "canslim_l": round(l_score, 2),
        "canslim_i": round(i_score, 2),
        "rs_rating": round(rs_val, 2) if rs_val is not None else None,
        "canslim_detail": {
            "C": c_detail,
            "A": a_detail,
            "N": n_detail,
            "S": s_detail,
            "L": l_detail,
            "I": i_detail,
            "M": {"state": regime_state, "gate_value": m_gate},
        },
        "market_regime": regime_state,
    }


async def run_canslim_scoring(
    score_date: Optional[date] = None,
    market: Optional[str] = None,
    instrument_ids: Optional[list[int]] = None,
) -> list[dict]:
    """
    Run CANSLIM scoring for a batch of instruments and upsert results
    into strategy_scores.

    Args:
        score_date:     Date to score as-of (defaults to today).
        market:         Filter to "US" or "KR" only; None = both.
        instrument_ids: Explicit list of IDs; None = all active instruments.

    Returns:
        List of result dicts from score_instrument.
    """
    if score_date is None:
        score_date = date.today()

    async with AsyncSessionLocal() as db:
        # Determine target instruments
        stmt = select(Instrument.id, Instrument.market).where(Instrument.is_active == True)
        if market:
            stmt = stmt.where(Instrument.market == market)
        if instrument_ids:
            stmt = stmt.where(Instrument.id.in_(instrument_ids))
        result = await db.execute(stmt)
        instrument_rows = result.all()
        ids = [row[0] for row in instrument_rows]
        market_by_id = {row[0]: row[1] for row in instrument_rows}

        logger.info(f"CANSLIM scoring {len(ids)} instruments for {score_date}")

        rs_lookup_by_market: dict[str, dict[int, float]] = {}
        rs_4w_lookup_by_market: dict[str, dict[int, float]] = {}
        for market_name in sorted(set(market_by_id.values())):
            rs_lookup_by_market[market_name] = await build_market_rs_lookup(db, market_name, score_date)
            rs_4w_lookup_by_market[market_name] = await build_market_rs_lookup(
                db,
                market_name,
                score_date - timedelta(days=28),
            )

        results = []
        for inst_id in ids:
            try:
                instrument_market = market_by_id[inst_id]
                scored = await score_instrument(
                    inst_id,
                    score_date,
                    db,
                    rs_lookup=rs_lookup_by_market[instrument_market],
                    rs_4w_lookup=rs_4w_lookup_by_market[instrument_market],
                )
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

                if existing:
                    existing.canslim_score = scored["canslim_score"]
                    existing.canslim_c = scored["canslim_c"]
                    existing.canslim_a = scored["canslim_a"]
                    existing.canslim_n = scored["canslim_n"]
                    existing.canslim_s = scored["canslim_s"]
                    existing.canslim_l = scored["canslim_l"]
                    existing.canslim_i = scored["canslim_i"]
                    existing.canslim_detail = scored["canslim_detail"]
                    existing.market_regime = scored["market_regime"]
                    existing.rs_rating = scored["rs_rating"]
                else:
                    new_row = StrategyScore(
                        instrument_id=inst_id,
                        score_date=score_date,
                        canslim_score=scored["canslim_score"],
                        canslim_c=scored["canslim_c"],
                        canslim_a=scored["canslim_a"],
                        canslim_n=scored["canslim_n"],
                        canslim_s=scored["canslim_s"],
                        canslim_l=scored["canslim_l"],
                        canslim_i=scored["canslim_i"],
                        canslim_detail=scored["canslim_detail"],
                        market_regime=scored["market_regime"],
                        rs_rating=scored["rs_rating"],
                    )
                    db.add(new_row)

                results.append(scored)
            except Exception as e:
                logger.error(f"CANSLIM scoring failed for instrument {inst_id}: {e}")

        await db.commit()
        logger.info(f"CANSLIM scoring complete: {len(results)}/{len(ids)} scored")

    return results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    market_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_canslim_scoring(market=market_arg))
