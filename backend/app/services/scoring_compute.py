from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from app.services.korea.sector_normalizer import normalize_eps
from app.services.scoring_context import (
    AnnualReport,
    InstrumentMeta,
    InstitutionalSnapshot,
    PriceBar,
    QuarterlyReport,
    RegimeSnapshot,
)
from app.services.strategies.canslim.a_annual import score_a
from app.services.strategies.canslim.c_earnings import score_c
from app.services.strategies.canslim.engine import (
    M_GATE_VALUES,
    WEIGHTS,
    build_market_rs_lookup_from_history,
    has_minimum_required_data,
)
from app.services.strategies.canslim.i_institutional import score_i
from app.services.strategies.canslim.l_leader import score_l
from app.services.strategies.canslim.n_new_highs import score_n
from app.services.strategies.canslim.s_supply import score_s
from app.services.strategies.dual_momentum.engine import compute_dual_momentum
from app.services.strategies.minervini.engine import MIN_PRICE_BARS as MIN_MINERVINI_BARS
from app.services.strategies.minervini.engine import compute_minervini_score
from app.services.strategies.piotroski.engine import compute_f_score
from app.services.strategies.weinstein.engine import (
    MIN_PRICE_BARS as MIN_WEINSTEIN_BARS,
    compute_weinstein_stage,
)
from app.services.technical.advanced_indicators import (
    compute_ad_rating,
    compute_bollinger_band_squeeze,
    compute_mfi,
    compute_obv,
    compute_rs_line_new_high,
    compute_ud_volume_ratio,
    compute_volume_dry_up,
)
from app.services.technical.multi_timeframe import compute_technical_composite
from app.services.technical.pattern_detector import MIN_BARS as MIN_PATTERN_BARS
from app.services.technical.pattern_detector import count_price_limit_events, scan_all_patterns


def build_market_rs_lookup_from_bars(
    price_bars_by_instrument: dict[int, tuple[PriceBar, ...]],
) -> dict[int, float]:
    histories = {
        instrument_id: [bar.close for bar in bars if bar.close is not None]
        for instrument_id, bars in price_bars_by_instrument.items()
    }
    return build_market_rs_lookup_from_history(histories)


def _annual_to_dict(row: AnnualReport) -> dict:
    return {
        "net_income": row.net_income,
        "total_assets": row.total_assets,
        "operating_cash_flow": row.operating_cash_flow,
        "long_term_debt": row.long_term_debt,
        "current_assets": row.current_assets,
        "current_liabilities": row.current_liabilities,
        "shares_outstanding_annual": row.shares_outstanding_annual,
        "gross_profit": row.gross_profit,
        "revenue": row.revenue,
    }


def compute_piotroski_from_context(
    *,
    instrument_id: int,
    score_date: date,
    annuals: tuple[AnnualReport, ...],
) -> Optional[dict]:
    if len(annuals) < 2:
        return None
    current = _annual_to_dict(annuals[-1])
    prior = _annual_to_dict(annuals[-2])
    f_raw, normalized, detail = compute_f_score(current, prior)
    return {
        "instrument_id": instrument_id,
        "score_date": score_date,
        "piotroski_score": normalized,
        "piotroski_f_raw": f_raw,
        "piotroski_detail": detail,
    }


def compute_minervini_from_context(
    *,
    instrument_id: int,
    score_date: date,
    prices: tuple[PriceBar, ...],
    rs_rating: Optional[float],
) -> Optional[dict]:
    if len(prices) < MIN_MINERVINI_BARS:
        return None
    closes = [bar.close for bar in prices if bar.close is not None]
    highs = [bar.high if bar.high is not None else bar.close for bar in prices if bar.close is not None]
    lows = [bar.low if bar.low is not None else bar.close for bar in prices if bar.close is not None]
    score, count, detail = compute_minervini_score(closes, highs, lows, rs_rating)
    return {
        "instrument_id": instrument_id,
        "score_date": score_date,
        "minervini_score": round(score, 2),
        "minervini_criteria_count": count,
        "minervini_detail": detail,
    }


def compute_weinstein_from_context(
    *,
    instrument_id: int,
    score_date: date,
    prices: tuple[PriceBar, ...],
) -> Optional[dict]:
    if len(prices) < MIN_WEINSTEIN_BARS:
        return None
    closes = [bar.close for bar in prices if bar.close is not None]
    volumes = [bar.volume or 0.0 for bar in prices if bar.close is not None]
    while len(volumes) < len(closes):
        volumes.append(0.0)
    score, stage, detail = compute_weinstein_stage(closes, volumes)
    return {
        "instrument_id": instrument_id,
        "score_date": score_date,
        "weinstein_score": round(score, 2),
        "weinstein_stage": stage,
        "weinstein_detail": detail,
    }


def compute_dual_momentum_from_context(
    *,
    instrument_id: int,
    score_date: date,
    prices: tuple[PriceBar, ...],
    benchmark_closes: list[float],
    risk_free: float,
) -> Optional[dict]:
    closes = [bar.close for bar in prices if bar.close is not None]
    if len(closes) < 60:
        return None
    score, abs_mom, rel_mom, detail = compute_dual_momentum(closes, benchmark_closes, risk_free)
    return {
        "instrument_id": instrument_id,
        "score_date": score_date,
        "dual_mom_score": round(score, 2),
        "dual_mom_abs": abs_mom,
        "dual_mom_rel": rel_mom,
        "dual_mom_detail": detail,
    }


def compute_technical_indicators_from_context(
    *,
    instrument_id: int,
    score_date: date,
    prices: tuple[PriceBar, ...],
    benchmark_closes: list[float],
) -> Optional[dict]:
    if len(prices) < 22:
        return None
    closes = [bar.close for bar in prices if bar.close is not None]
    highs = [
        bar.high if bar.high is not None else bar.close
        for bar in prices
        if bar.close is not None
    ]
    lows = [
        bar.low if bar.low is not None else bar.close
        for bar in prices
        if bar.close is not None
    ]
    volumes = [bar.volume or 0.0 for bar in prices if bar.close is not None]
    while len(highs) < len(closes):
        highs.append(closes[-1])
    while len(lows) < len(closes):
        lows.append(closes[-1])
    while len(volumes) < len(closes):
        volumes.append(0.0)

    ad_grade, ud_65 = compute_ad_rating(closes, volumes)
    ud_50 = compute_ud_volume_ratio(closes, volumes)
    dry_up = compute_volume_dry_up(volumes)
    rs_new_high, rs_line_val = compute_rs_line_new_high(closes, benchmark_closes)
    bb_squeeze, bb_bw = compute_bollinger_band_squeeze(closes)
    mfi_val = compute_mfi(highs, lows, closes, volumes)
    obv_val, obv_trend = compute_obv(closes, volumes)

    technical_detail = {
        "ad_rating": ad_grade,
        "ud_ratio_65d": ud_65,
        "ud_ratio_50d": ud_50,
        "volume_dry_up": dry_up,
        "rs_line_value": rs_line_val,
        "rs_line_new_high": rs_new_high,
        "bb_squeeze": bb_squeeze,
        "bb_bandwidth": bb_bw,
        "mfi_14d": mfi_val,
        "obv": obv_val,
        "obv_trend": obv_trend,
    }

    return {
        "instrument_id": instrument_id,
        "score_date": score_date,
        "ad_rating": ad_grade,
        "bb_squeeze": bb_squeeze,
        "rs_line_new_high": rs_new_high,
        "technical_detail": technical_detail,
    }


def compute_patterns_from_context(
    *,
    instrument: InstrumentMeta,
    score_date: date,
    prices: tuple[PriceBar, ...],
) -> Optional[dict]:
    if len(prices) < MIN_PATTERN_BARS:
        return None
    closes = [bar.close for bar in prices if bar.close is not None]
    highs = [
        bar.high if bar.high is not None else bar.close
        for bar in prices
        if bar.close is not None
    ]
    lows = [
        bar.low if bar.low is not None else bar.close
        for bar in prices
        if bar.close is not None
    ]
    volumes = [bar.volume or 0.0 for bar in prices if bar.close is not None]
    min_len = min(len(closes), len(highs), len(lows))
    closes = closes[:min_len]
    highs = highs[:min_len]
    lows = lows[:min_len]
    while len(volumes) < min_len:
        volumes.append(0.0)
    volumes = volumes[:min_len]
    if min_len < MIN_PATTERN_BARS:
        return None

    recent_limit_moves = count_price_limit_events(closes) if instrument.market == "KR" else 0
    if instrument.market == "KR" and recent_limit_moves > 0:
        return {
            "instrument_id": instrument.id,
            "score_date": score_date,
            "patterns": [],
            "pattern_count": 0,
            "limit_move_count": recent_limit_moves,
        }

    patterns = scan_all_patterns(closes, highs, lows, volumes)
    return {
        "instrument_id": instrument.id,
        "score_date": score_date,
        "patterns": patterns,
        "pattern_count": len(patterns),
        "limit_move_count": recent_limit_moves,
    }


def compute_technical_composite_from_context(
    *,
    instrument_id: int,
    score_date: date,
    prices: tuple[PriceBar, ...],
    patterns: Optional[list[dict]],
    technical_detail: Optional[dict],
    minervini_criteria_count: Optional[int],
) -> Optional[dict]:
    closes = [bar.close for bar in prices if bar.close is not None]
    if len(closes) < 50:
        return None
    composite, detail = compute_technical_composite(
        closes,
        patterns,
        technical_detail,
        minervini_criteria_count,
    )
    merged_technical_detail = dict(technical_detail or {})
    merged_technical_detail["composite"] = detail
    return {
        "instrument_id": instrument_id,
        "score_date": score_date,
        "technical_composite": composite,
        "technical_detail": merged_technical_detail,
    }


def compute_canslim_from_context(
    *,
    instrument: InstrumentMeta,
    quarterlies: tuple[QuarterlyReport, ...],
    annuals: tuple[AnnualReport, ...],
    prices: tuple[PriceBar, ...],
    institutional: Optional[InstitutionalSnapshot],
    regime: Optional[RegimeSnapshot],
    score_date: date,
    rs_lookup: dict[int, float],
    rs_4w_lookup: dict[int, float],
    patterns: Optional[list[dict]],
    rs_line_new_high: bool,
) -> Optional[dict]:
    if not has_minimum_required_data(
        quarterly_count=len(quarterlies),
        annual_count=len(annuals),
        price_count=len(prices),
    ):
        return None

    c_score = 0.0
    c_detail: dict = {}
    if len(quarterlies) >= 5:
        q_current = quarterlies[-1]
        q_prior = next(
            (
                row for row in quarterlies
                if row.fiscal_quarter == q_current.fiscal_quarter
                and row.fiscal_year == q_current.fiscal_year - 1
            ),
            None,
        )
        eps_series = [row.eps for row in quarterlies]
        eps_current = (
            normalize_eps(eps_series, instrument.sector)
            if instrument.market == "KR"
            else q_current.eps
        )
        c_score, c_detail = score_c(
            eps_current=eps_current,
            eps_same_q_prior=q_prior.eps if q_prior else None,
            revenue_yoy_growth=q_current.revenue_yoy_growth,
            eps_yoy_growth_series=[row.eps_yoy_growth for row in quarterlies],
            sector=instrument.sector,
        )
    else:
        c_detail["reason"] = f"insufficient quarterly data ({len(quarterlies)} < 5)"

    annual_eps = [row.eps for row in annuals]
    if len(annual_eps) >= 4:
        a_score, a_detail = score_a(annual_eps)
    else:
        a_score, a_detail = 0.0, {"reason": f"insufficient annual data ({len(annual_eps)} < 4)"}

    highs = [bar.high for bar in prices if bar.high is not None]
    latest_price = prices[-1]
    close = latest_price.close or 0.0
    high_52w = max(highs) if highs else 0.0
    has_base = any(pattern.get("confidence", 0) >= 0.50 for pattern in (patterns or []))
    n_score, n_detail = score_n(
        close=close,
        high_52w=high_52w,
        avg_volume_50d=latest_price.avg_volume_50d,
        volume_today=latest_price.volume,
        has_base_pattern=has_base,
        rs_line_new_high=rs_line_new_high,
    )

    surge_days = 0
    recent_20 = prices[-20:] if len(prices) >= 20 else prices
    for bar in recent_20:
        if bar.avg_volume_50d and bar.volume and bar.avg_volume_50d > 0:
            if bar.volume > 2 * bar.avg_volume_50d:
                surge_days += 1

    ud_ratio = None
    if len(prices) >= 2:
        up_vol = 0.0
        down_vol = 0.0
        window = prices[-50:] if len(prices) >= 50 else prices
        for idx in range(1, len(window)):
            curr_close = window[idx].close
            prev_close = window[idx - 1].close
            vol = window[idx].volume or 0.0
            if curr_close is None or prev_close is None:
                continue
            if curr_close > prev_close:
                up_vol += vol
            elif curr_close < prev_close:
                down_vol += vol
        if down_vol > 0:
            ud_ratio = up_vol / down_vol

    s_score, s_detail = score_s(
        float_shares=instrument.float_shares,
        shares_outstanding=instrument.shares_outstanding,
        volume_surge_days_20d=surge_days,
        ud_volume_ratio_50d=ud_ratio,
        is_buyback_active=bool(institutional and institutional.is_buyback_active),
        exchange=instrument.exchange,
    )

    rs_val = rs_lookup.get(instrument.id)
    rs_4w_ago = rs_4w_lookup.get(instrument.id)
    l_score, l_detail = score_l(
        rs_rating=rs_val,
        rs_rating_4w_ago=rs_4w_ago,
    )

    if instrument.market == "US":
        i_score, i_detail = score_i(
            market="US",
            institutional_pct=institutional.institutional_pct if institutional else None,
            num_institutional_owners=(
                institutional.num_institutional_owners if institutional else None
            ),
            qoq_owner_change=institutional.qoq_owner_change if institutional else None,
            fund_quality_score=(
                institutional.top_fund_quality_score if institutional else None
            ),
        )
    else:
        i_score, i_detail = score_i(
            market="KR",
            foreign_ownership_pct=(
                institutional.foreign_ownership_pct if institutional else None
            ),
            foreign_net_buy_30d=(
                institutional.foreign_net_buy_30d if institutional else None
            ),
            institutional_net_buy_30d=(
                institutional.institutional_net_buy_30d if institutional else None
            ),
            is_chaebol_cross=instrument.is_chaebol_cross,
        )

    regime_state = regime.state if regime else "CONFIRMED_UPTREND"
    m_gate = M_GATE_VALUES.get(regime_state, 0)
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
        "instrument_id": instrument.id,
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
