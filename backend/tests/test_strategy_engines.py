from app.services.strategies.dual_momentum.engine import compute_dual_momentum
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
