from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Optional

from app.services.ingestion.freshness import run_data_integrity_monitoring
from app.tasks.celery_app import celery_app


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_date(value: Optional[str]) -> Optional[date]:
    return date.fromisoformat(value) if value else None


@celery_app.task(name="app.tasks.alerts.run_data_integrity_monitoring")
def run_data_integrity_monitoring_task(
    as_of: Optional[str] = None,
    score_date: Optional[str] = None,
    snapshot_date: Optional[str] = None,
    markets: Optional[list[str]] = None,
) -> dict:
    return asyncio.run(
        run_data_integrity_monitoring(
            as_of=_parse_datetime(as_of),
            score_date=_parse_date(score_date),
            snapshot_date=_parse_date(snapshot_date),
            markets=markets,
        )
    )
