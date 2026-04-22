from __future__ import annotations

import math
from collections.abc import Iterable

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.postgresql import JSONB

from app.models.strategy_score import StrategyScore

_PERSISTED_STRATEGY_SCORE_FIELDS = {
    column.name
    for column in StrategyScore.__table__.columns
    if column.name not in {"id", "instrument_id", "score_date", "computed_at"}
}
_JSON_STRATEGY_SCORE_FIELDS = {
    column.name
    for column in StrategyScore.__table__.columns
    if isinstance(column.type, JSONB)
}


def _sanitize_json_value(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_json_value(item) for item in value]
    return value


def merge_strategy_score_rows(result_sets: Iterable[list[dict]]) -> list[dict]:
    merged: dict[tuple[int, object], dict] = {}

    for results in result_sets:
        for row in results:
            key = (row["instrument_id"], row["score_date"])
            target = merged.setdefault(
                key,
                {
                    "instrument_id": row["instrument_id"],
                    "score_date": row["score_date"],
                },
            )
            for field, value in row.items():
                if field in {"instrument_id", "score_date"}:
                    continue
                if field not in _PERSISTED_STRATEGY_SCORE_FIELDS:
                    continue
                if field == "technical_detail" and value is not None:
                    merged_detail = dict(target.get("technical_detail") or {})
                    merged_detail.update(value)
                    target["technical_detail"] = merged_detail
                    continue
                target[field] = value

    return list(merged.values())


async def bulk_upsert_strategy_scores(db, rows: list[dict]) -> None:
    if not rows:
        return

    field_names = sorted(
        {
            key
            for row in rows
            for key in row.keys()
            if key in _PERSISTED_STRATEGY_SCORE_FIELDS
        }
    )
    normalized_rows = []
    for row in rows:
        normalized = {
            "instrument_id": row["instrument_id"],
            "score_date": row["score_date"],
        }
        for field_name in field_names:
            value = row.get(field_name)
            if field_name in _JSON_STRATEGY_SCORE_FIELDS:
                value = _sanitize_json_value(value)
            normalized[field_name] = value
        normalized_rows.append(normalized)

    stmt = insert(StrategyScore).values(normalized_rows)
    update_map = {
        field_name: getattr(stmt.excluded, field_name)
        for field_name in field_names
    }
    update_map["computed_at"] = func.now()

    await db.execute(
        stmt.on_conflict_do_update(
            constraint="uq_strategy_score_instrument_date",
            set_=update_map,
        )
    )
