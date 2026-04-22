from app.services.technical.multi_timeframe import compute_volume_score


def test_compute_volume_score_handles_missing_ud_ratio_65d():
    score, detail = compute_volume_score(
        {
            "ad_rating": "A+",
            "obv_trend": "rising",
            "ud_ratio_50d": None,
            "volume_dry_up": 0.55,
            "ud_ratio_65d": None,
            "mfi_14d": 55.0,
        }
    )

    assert score >= 0
    assert detail["ud_ratio_65d"] is None
    assert detail["ud65_pts"] == 0.0
