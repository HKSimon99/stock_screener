from datetime import date

import pytest
from sqlalchemy import select

from app.models.instrument import Instrument
from app.models.strategy_score import StrategyScore
from app.services.strategy_score_bulk import (
    _normalize_strategy_score_rows,
    _sanitize_json_value,
    bulk_upsert_strategy_scores,
    merge_strategy_score_rows,
)


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


def test_normalize_strategy_score_rows_marks_missing_union_fields_as_none():
    fields, rows = _normalize_strategy_score_rows(
        [
            {
                "instrument_id": 1,
                "score_date": date(2026, 5, 5),
                "canslim_score": 80.0,
            },
            {
                "instrument_id": 2,
                "score_date": date(2026, 5, 5),
                "magic_formula_score": 90.0,
            },
        ]
    )

    assert "canslim_score" in fields
    assert "magic_formula_score" in fields
    assert rows[0]["magic_formula_score"] is None
    assert rows[1]["canslim_score"] is None


@pytest.mark.asyncio
async def test_bulk_upsert_preserves_existing_scores_when_batch_field_is_missing(db_session):
    instrument = Instrument(
        ticker="AAPL",
        name="Apple",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    score_date = date(2026, 5, 5)
    db_session.add(
        StrategyScore(
            instrument_id=instrument.id,
            score_date=score_date,
            magic_formula_score=88.0,
            piotroski_score=77.0,
        )
    )
    await db_session.commit()

    await bulk_upsert_strategy_scores(
        db_session,
        [
            {
                "instrument_id": instrument.id,
                "score_date": score_date,
                "canslim_score": 82.0,
            }
        ],
    )
    await db_session.commit()

    row = (
        await db_session.execute(
            select(StrategyScore).where(
                StrategyScore.instrument_id == instrument.id,
                StrategyScore.score_date == score_date,
            )
        )
    ).scalars().one()
    assert float(row.canslim_score) == 82.0
    assert float(row.magic_formula_score) == 88.0
    assert float(row.piotroski_score) == 77.0
