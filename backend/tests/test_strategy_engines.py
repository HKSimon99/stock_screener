from datetime import date

from app.services.scoring_context import AnnualReport, PriceBar
from app.services.scoring_compute import (
    compute_magic_formula_raw_from_context,
    diagnose_magic_formula_ineligibility_from_context,
)
from app.services.strategies.dual_momentum.engine import compute_dual_momentum
from app.services.strategies.magic_formula.engine import (
    compute_magic_formula_raw,
    rank_magic_formula_universe,
)
from app.services.strategies.minervini.engine import compute_minervini_score
from app.services.strategies.piotroski.engine import compute_f_score
from app.services.strategies.weinstein.engine import compute_weinstein_stage


def _build_series(points: list[tuple[int, float]]) -> list[float]:
    values: list[float] = []
    for (start_idx, start_value), (end_idx, end_value) in zip(points, points[1:]):
        steps = end_idx - start_idx
        for step in range(steps):
            values.append(start_value + (end_value - start_value) * step / steps)
    values.append(points[-1][1])
    return values


def test_minervini_scores_perfect_trend_at_100():
    closes = [100 + idx for idx in range(222)]
    highs = [close + 2 for close in closes]
    lows = [close - 2 for close in closes]

    score, count, detail = compute_minervini_score(closes, highs, lows, rs_rating=95)

    assert score == 100.0
    assert count == 8
    assert detail["bonus"] == 15
    assert detail["T8_rs_rating_ge_70"]["pass"] is True


def test_minervini_scores_declining_stock_at_zero():
    closes = [321 - idx for idx in range(222)]
    highs = [close + 2 for close in closes]
    lows = [close - 2 for close in closes]

    score, count, detail = compute_minervini_score(closes, highs, lows, rs_rating=40)

    assert score == 0.0
    assert count == 0
    assert detail["T1_above_150ma"]["pass"] is False
    assert detail["T8_rs_rating_ge_70"]["pass"] is False


def test_piotroski_maps_all_nine_criteria_to_full_score():
    current = {
        "net_income": 120,
        "total_assets": 850,
        "operating_cash_flow": 150,
        "long_term_debt": 150,
        "current_assets": 320,
        "current_liabilities": 100,
        "shares_outstanding_annual": 90,
        "gross_profit": 500,
        "revenue": 1000,
    }
    prior = {
        "net_income": 80,
        "total_assets": 900,
        "operating_cash_flow": 70,
        "long_term_debt": 250,
        "current_assets": 250,
        "current_liabilities": 110,
        "shares_outstanding_annual": 100,
        "gross_profit": 400,
        "revenue": 950,
    }

    f_raw, normalized, detail = compute_f_score(current, prior)

    assert f_raw == 9
    assert normalized == 100.0
    assert all(item["pass"] for key, item in detail.items() if key.startswith("F"))


def test_piotroski_weak_financials_collapse_to_zero_band():
    current = {
        "net_income": -20,
        "total_assets": 1000,
        "operating_cash_flow": -10,
        "long_term_debt": 300,
        "current_assets": 100,
        "current_liabilities": 200,
        "shares_outstanding_annual": 120,
        "gross_profit": 100,
        "revenue": 700,
    }
    prior = {
        "net_income": 10,
        "total_assets": 900,
        "operating_cash_flow": 30,
        "long_term_debt": 200,
        "current_assets": 120,
        "current_liabilities": 180,
        "shares_outstanding_annual": 100,
        "gross_profit": 120,
        "revenue": 650,
    }

    f_raw, normalized, detail = compute_f_score(current, prior)

    assert f_raw == 1
    assert normalized == 0.0
    assert detail["F4_accruals"]["pass"] is True
    assert detail["F7_no_dilution"]["pass"] is False


def test_weinstein_identifies_stage_two_mid_for_rising_trend():
    closes = [100 + idx * 0.4 for idx in range(220)]
    volumes = [1_000_000] * len(closes)

    score, stage, detail = compute_weinstein_stage(closes, volumes)

    assert stage == "2_mid"
    assert score == 85.0
    assert detail["price_vs_ma"] > 0


def test_weinstein_identifies_stage_three_distribution():
    closes = []
    value = 100.0
    for idx in range(220):
        cycle = idx % 10
        if cycle in (0, 1, 2):
            value += 0.35
        elif cycle in (3, 4):
            value += 0.05
        elif cycle in (5, 6, 7):
            value -= 0.4
        else:
            value -= 0.05
        closes.append(value)

    volumes = [1_000_000]
    for idx in range(1, len(closes)):
        if closes[idx] > closes[idx - 1]:
            volumes.append(850_000)
        elif closes[idx] < closes[idx - 1]:
            volumes.append(1_700_000)
        else:
            volumes.append(1_000_000)

    score, stage, detail = compute_weinstein_stage(closes, volumes)

    assert stage == "3"
    assert score == 10.0
    assert detail["cross_count_60d"] >= 3
    assert detail["avg_vol_down_days"] > detail["avg_vol_up_days"]


def test_weinstein_identifies_stage_four_for_decline_below_ma():
    closes = [220 - idx * 0.5 for idx in range(220)]
    volumes = [1_000_000] * len(closes)

    score, stage, detail = compute_weinstein_stage(closes, volumes)

    assert stage == "4"
    assert score == 0.0
    assert detail["price_vs_ma"] < 0


def test_dual_momentum_adds_acceleration_bonus_when_relative_fails():
    closes = _build_series([(0, 130), (20, 120), (140, 110), (200, 100), (259, 150)])
    benchmark = _build_series([(0, 140), (20, 115), (259, 150)])

    score, abs_mom, rel_mom, detail = compute_dual_momentum(closes, benchmark, risk_free_12m=0.03)

    assert score == 80.0
    assert abs_mom is True
    assert rel_mom is False
    assert detail["all_positive"] is True
    assert detail["bonus"] == 10


def test_dual_momentum_rel_only_scores_30():
    closes = [100.0] * 259 + [104.0]
    benchmark = [100.0] * 259 + [90.0]

    score, abs_mom, rel_mom, detail = compute_dual_momentum(closes, benchmark, risk_free_12m=0.05)

    assert score == 30.0
    assert abs_mom is False
    assert rel_mom is True
    assert detail["benchmark_ret_12m"] == -0.1


def test_dual_momentum_returns_error_when_12m_history_is_missing():
    score, abs_mom, rel_mom, detail = compute_dual_momentum(
        closes=[100.0] * 100,
        benchmark_closes=[100.0] * 100,
        risk_free_12m=0.03,
    )

    assert score == 0.0
    assert abs_mom is False
    assert rel_mom is False
    assert detail["error"] == "insufficient price history for 12-month return"


# =============================================================================
# Magic Formula
# =============================================================================

def _mf_inputs(**overrides):
    """Healthy baseline so individual tests can mutate one factor at a time."""
    base = dict(
        ebit=200.0,
        current_assets=300.0,
        current_liabilities=100.0,
        net_fixed_assets=400.0,
        market_cap=1500.0,
        total_debt=500.0,
        cash_and_equivalents=200.0,
    )
    base.update(overrides)
    return base


def test_magic_formula_computes_roic_and_ey_for_healthy_inputs():
    raw = compute_magic_formula_raw(**_mf_inputs())

    # NWC = max(300 - 100, 0) = 200; invested = 200 + 400 = 600; ROIC = 200/600 ≈ 0.3333
    assert raw["data_sufficient"] is True
    assert abs(raw["roic"] - (200 / 600)) < 1e-9
    # EV = 1500 + 500 - 200 = 1800; EY = 200/1800 ≈ 0.1111
    assert raw["ev"] == 1800
    assert abs(raw["ey"] - (200 / 1800)) < 1e-9
    assert raw["nwc"] == 200


def test_magic_formula_excludes_negative_ebit():
    raw = compute_magic_formula_raw(**_mf_inputs(ebit=-50.0))

    assert raw["data_sufficient"] is False
    # ROIC and EY are still computed (negative), but the exclusion gate trips
    assert raw["roic"] is not None and raw["roic"] < 0
    assert raw["ey"] is not None and raw["ey"] < 0


def test_magic_formula_excludes_non_positive_ev():
    # EV = market_cap + total_debt - cash; force net_debt to dominate so EV ≤ 0
    raw = compute_magic_formula_raw(**_mf_inputs(market_cap=100.0, total_debt=50.0, cash_and_equivalents=200.0))

    # EV = 100 + 50 - 200 = -50  → non-positive
    assert raw["ev"] == -50
    assert raw["data_sufficient"] is False


def test_magic_formula_handles_missing_balance_sheet():
    raw = compute_magic_formula_raw(**_mf_inputs(current_assets=None, current_liabilities=None))

    assert raw["nwc"] is None
    assert raw["roic"] is None
    assert raw["data_sufficient"] is False


def test_magic_formula_ranking_assigns_top_score_to_best_combined_rank():
    # Construct three eligible stocks. Stock A has best ROIC + best EY; should score 100.
    rows = [
        {"instrument_id": 1, **compute_magic_formula_raw(
            ebit=300, current_assets=200, current_liabilities=50,
            net_fixed_assets=200, market_cap=1000, total_debt=100, cash_and_equivalents=50,
        )},
        {"instrument_id": 2, **compute_magic_formula_raw(
            ebit=100, current_assets=200, current_liabilities=50,
            net_fixed_assets=200, market_cap=1500, total_debt=200, cash_and_equivalents=50,
        )},
        {"instrument_id": 3, **compute_magic_formula_raw(
            ebit=50, current_assets=200, current_liabilities=50,
            net_fixed_assets=200, market_cap=2000, total_debt=300, cash_and_equivalents=50,
        )},
    ]

    ranked = rank_magic_formula_universe(rows)
    by_id = {r["instrument_id"]: r for r in ranked}

    # Stock 1 has the highest ROIC AND highest EY → roic_rank=1, ey_rank=1, combined=2 → score top
    assert by_id[1]["roic_rank"] == 1
    assert by_id[1]["ey_rank"] == 1
    assert by_id[1]["combined_rank"] == 2
    # combined_rank ranges 2..6 for 3 stocks; max_combined = 2*3 = 6
    # score = (1 - 2/6) * 100 ≈ 66.67
    assert by_id[1]["score"] is not None
    assert by_id[1]["score"] > by_id[2]["score"] > by_id[3]["score"]


def test_magic_formula_ranking_skips_ineligible_rows():
    rows = [
        {"instrument_id": 1, **compute_magic_formula_raw(**_mf_inputs())},
        {"instrument_id": 2, **compute_magic_formula_raw(**_mf_inputs(ebit=-100))},   # negative EBIT
    ]

    ranked = rank_magic_formula_universe(rows)
    by_id = {r["instrument_id"]: r for r in ranked}

    assert by_id[1]["score"] is not None
    assert by_id[2]["score"] is None
    assert by_id[2]["roic_rank"] is None


def _annual_report(**overrides):
    base = dict(
        fiscal_year=2025,
        report_date=date(2026, 2, 15),
        revenue=1000.0,
        gross_profit=600.0,
        net_income=120.0,
        eps=1.2,
        total_assets=900.0,
        current_assets=300.0,
        current_liabilities=100.0,
        long_term_debt=200.0,
        shares_outstanding_annual=50.0,
        operating_cash_flow=160.0,
        ebit=200.0,
        total_debt=250.0,
        cash_and_equivalents=50.0,
        net_fixed_assets=400.0,
    )
    base.update(overrides)
    return AnnualReport(**base)


def _price_bar(close=30.0):
    return PriceBar(
        trade_date=date(2026, 5, 5),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1_000_000,
        avg_volume_50d=900_000,
    )


def test_context_magic_formula_uses_annual_shares_when_instrument_shares_missing():
    raw = compute_magic_formula_raw_from_context(
        instrument_id=1,
        annuals=(_annual_report(shares_outstanding_annual=50.0),),
        prices=(_price_bar(close=30.0),),
        shares_outstanding=None,
    )

    assert raw is not None
    assert raw["market_cap"] == 1500.0
    assert raw["shares_outstanding"] == 50.0
    assert raw["shares_source"] == "fundamentals_annual"


def test_context_magic_formula_diagnosis_reports_missing_core_inputs():
    diagnosis = diagnose_magic_formula_ineligibility_from_context(
        annuals=(_annual_report(ebit=None, shares_outstanding_annual=None),),
        prices=(_price_bar(close=30.0),),
        shares_outstanding=None,
    )

    assert diagnosis["eligible"] is False
    assert "missing_ebit" in diagnosis["reasons"]
    assert "missing_shares_outstanding" in diagnosis["reasons"]
