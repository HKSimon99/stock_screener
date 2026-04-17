from app.services.strategies.canslim.engine import (
    build_market_rs_lookup_from_history,
    has_minimum_required_data,
)
from app.services.strategies.canslim.l_leader import score_l


def test_has_minimum_required_data_accepts_complete_core_data():
    assert has_minimum_required_data(quarterly_count=5, annual_count=4, price_count=50) is True


def test_has_minimum_required_data_rejects_incomplete_core_data():
    assert has_minimum_required_data(quarterly_count=4, annual_count=4, price_count=50) is False
    assert has_minimum_required_data(quarterly_count=5, annual_count=3, price_count=50) is False
    assert has_minimum_required_data(quarterly_count=5, annual_count=4, price_count=49) is False


def test_build_market_rs_lookup_from_history_ranks_returns():
    prices = {
        1: [100.0] * 251 + [110.0],  # +10%
        2: [100.0] * 251 + [125.0],  # +25%
        3: [100.0] * 251 + [95.0],   # -5%
    }

    rs_lookup = build_market_rs_lookup_from_history(prices)

    assert rs_lookup[3] < rs_lookup[1] < rs_lookup[2]
    assert rs_lookup[2] == 99.0


def test_build_market_rs_lookup_from_history_skips_short_series():
    rs_lookup = build_market_rs_lookup_from_history({
        1: [100.0] * 251,
        2: [100.0] * 252,
    })

    assert 1 not in rs_lookup
    assert 2 in rs_lookup


def test_score_l_uses_expected_rs_tiers():
    score, detail = score_l(rs_rating=86.0)

    assert score == 80.0
    assert detail["base_score"] == 80
    assert detail["drop_penalty"] == 0


def test_score_l_applies_bonus_and_penalty():
    score, detail = score_l(
        rs_rating=96.0,
        industry_group_rs=82.0,
        rs_rating_4w_ago=110.0,
    )

    assert score == 93.0
    assert detail["base_score"] == 98
    assert detail["ig_bonus"] == 5
    assert detail["drop_penalty"] == -10
    assert detail["rs_drop_4w"] == 14.0
