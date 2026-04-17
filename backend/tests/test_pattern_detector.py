from datetime import date, timedelta

import pytest

from app.models.instrument import Instrument
from app.models.price import Price
from app.services.technical.pattern_detector import (
    detect_ascending_base,
    detect_double_bottom,
    find_zigzag_pivots,
    score_instrument_patterns,
)


def _build_series(points: list[tuple[int, float]]) -> list[float]:
    values: list[float] = []
    for (start_idx, start_value), (end_idx, end_value) in zip(points, points[1:]):
        steps = end_idx - start_idx
        for step in range(steps):
            values.append(start_value + (end_value - start_value) * step / steps)
    values.append(points[-1][1])
    return values


def _build_double_bottom_fixture() -> tuple[list[float], list[float], list[float], list[int]]:
    closes = _build_series(
        [(0, 130), (10, 120), (20, 100), (30, 112), (40, 101), (50, 118), (59, 121)]
    )
    highs = [close + 1.5 for close in closes]
    lows = [close - 1.5 for close in closes]
    volumes = []
    for idx in range(len(closes)):
        if 17 <= idx <= 23:
            volumes.append(2_000_000)
        elif 37 <= idx <= 43:
            volumes.append(1_400_000)
        else:
            volumes.append(1_700_000)
    return closes, highs, lows, volumes


def _build_ascending_base_fixture() -> tuple[list[float], list[float], list[float], list[int]]:
    closes = _build_series(
        [
            (0, 120),
            (5, 130),
            (10, 120),
            (15, 100),
            (25, 120),
            (35, 108),
            (45, 124),
            (55, 114),
            (64, 123),
            (66, 121),
            (69, 128),
        ]
    )
    highs = [close + 1.5 for close in closes]
    lows = [close - 1.5 for close in closes]
    volumes = []
    for idx in range(len(closes)):
        if 32 <= idx <= 38:
            volumes.append(1_600_000)
        elif 52 <= idx <= 58:
            volumes.append(1_300_000)
        else:
            volumes.append(1_800_000)
    return closes, highs, lows, volumes


def test_find_zigzag_pivots_tracks_threshold_reversals():
    closes = [100, 105, 110, 115, 110, 105, 100, 104, 108, 112, 107, 102]
    highs = [close + 1 for close in closes]
    lows = [close - 1 for close in closes]

    pivots = find_zigzag_pivots(closes, highs, lows, threshold_pct=5.0)

    assert [pivot.kind for pivot in pivots] == ["low", "high", "low", "high", "low"]
    assert [pivot.index for pivot in pivots] == [0, 3, 6, 9, 11]


def test_detect_double_bottom_identifies_breakout_and_volume_exhaustion():
    closes, highs, lows, volumes = _build_double_bottom_fixture()

    pattern = detect_double_bottom(closes, highs, lows, volumes)

    assert pattern is not None
    assert pattern["pattern_type"] == "double_bottom"
    assert pattern["status"] == "breakout"
    assert pattern["pivot_price"] == 113.5
    assert pattern["detail"]["volume_exhaustion"] is True
    assert pattern["detail"]["low1_bar"] == 20
    assert pattern["detail"]["low2_bar"] == 40


def test_detect_ascending_base_identifies_higher_lows_and_breakout():
    closes, highs, lows, volumes = _build_ascending_base_fixture()

    pattern = detect_ascending_base(closes, highs, lows, volumes)

    assert pattern is not None
    assert pattern["pattern_type"] == "ascending_base"
    assert pattern["status"] == "breakout"
    assert pattern["pivot_price"] == 125.5
    assert pattern["detail"]["volume_contracting"] is True
    assert pattern["detail"]["low1"]["bar"] == 15
    assert pattern["detail"]["low3"]["bar"] == 55


@pytest.mark.asyncio
async def test_score_instrument_patterns_skips_short_history(db_session):
    instrument = Instrument(
        ticker="SHORT",
        name="Short History",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    start = date(2026, 1, 1)
    for idx in range(59):
        trade_date = start + timedelta(days=idx)
        close = 100 + idx
        db_session.add(
            Price(
                instrument_id=instrument.id,
                trade_date=trade_date,
                open=close - 1,
                high=close + 1,
                low=close - 2,
                close=close,
                volume=1_000_000,
                avg_volume_50d=950_000,
            )
        )

    await db_session.commit()

    result = await score_instrument_patterns(instrument.id, start + timedelta(days=58), db_session)

    assert result is None


@pytest.mark.asyncio
async def test_score_instrument_patterns_returns_detected_patterns_for_seeded_history(db_session):
    instrument = Instrument(
        ticker="WBASE",
        name="W Base",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    closes, highs, lows, volumes = _build_double_bottom_fixture()
    start = date(2026, 1, 1)
    for idx, (close, high, low, volume) in enumerate(zip(closes, highs, lows, volumes)):
        trade_date = start + timedelta(days=idx)
        db_session.add(
            Price(
                instrument_id=instrument.id,
                trade_date=trade_date,
                open=close - 1,
                high=high,
                low=low,
                close=close,
                volume=volume,
                avg_volume_50d=1_500_000,
            )
        )

    await db_session.commit()

    result = await score_instrument_patterns(instrument.id, start + timedelta(days=len(closes) - 1), db_session)

    assert result is not None
    assert result["instrument_id"] == instrument.id
    assert result["pattern_count"] >= 1
    assert "double_bottom" in [pattern["pattern_type"] for pattern in result["patterns"]]
