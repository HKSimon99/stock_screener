from app.services.technical.advanced_indicators import compute_ad_rating


def test_compute_ad_rating_returns_none_ratio_when_no_down_volume():
    closes = [10.0, 11.0, 12.0, 13.0]
    volumes = [100.0, 120.0, 130.0, 140.0]

    grade, ud_ratio = compute_ad_rating(closes, volumes, window=3)

    assert grade == "A+"
    assert ud_ratio is None
