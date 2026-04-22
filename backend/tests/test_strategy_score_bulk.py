from datetime import date

from app.services.strategy_score_bulk import merge_strategy_score_rows, _sanitize_json_value


def test_merge_strategy_score_rows_ignores_transient_metrics():
    rows = merge_strategy_score_rows(
        [
            [
                {
                    "instrument_id": 1,
                    "score_date": date(2026, 4, 13),
                    "patterns": [{"pattern_type": "cup_handle"}],
                    "pattern_count": 1,
                    "limit_move_count": 2,
                }
            ],
            [
                {
                    "instrument_id": 1,
                    "score_date": date(2026, 4, 13),
                    "technical_detail": {"obv_trend": "rising"},
                    "ad_rating": "A",
                }
            ],
        ]
    )

    assert rows == [
        {
            "instrument_id": 1,
            "score_date": date(2026, 4, 13),
            "patterns": [{"pattern_type": "cup_handle"}],
            "technical_detail": {"obv_trend": "rising"},
            "ad_rating": "A",
        }
    ]


def test_sanitize_json_value_replaces_non_finite_numbers():
    value = {
        "ad_rating": "A+",
        "ud_ratio_65d": float("inf"),
        "nested": [1.0, float("-inf"), {"x": float("nan")}],
    }

    assert _sanitize_json_value(value) == {
        "ad_rating": "A+",
        "ud_ratio_65d": None,
        "nested": [1.0, None, {"x": None}],
    }
