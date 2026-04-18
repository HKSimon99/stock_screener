from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Optional

import sentry_sdk
from app.services.ingestion.freshness import run_data_integrity_monitoring
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


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
    result = asyncio.run(
        run_data_integrity_monitoring(
            as_of=_parse_datetime(as_of),
            score_date=_parse_date(score_date),
            snapshot_date=_parse_date(snapshot_date),
            markets=markets,
        )
    )

    # -----------------------------------------------------------------------
    # Sentry alert — fire a Sentry message for any new CRITICAL findings so
    # that the on-call engineer gets notified even before looking at the DB.
    # Sentry de-duplicates identical messages within a short window so this
    # won't spam on every daily run if the same issue persists.
    # -----------------------------------------------------------------------
    alerts_created: int = result.get("alerts_created", 0)
    if alerts_created and sentry_sdk.is_initialized():
        _fire_sentry_alerts(result)

    return result


def _fire_sentry_alerts(result: dict) -> None:
    """Send a Sentry message for each critical finding in the monitoring report."""
    as_of = result.get("as_of", "unknown")

    # Freshness staleness
    for freshness in result.get("freshness", []):
        if freshness.get("status") == "stale":
            sentry_sdk.capture_message(
                f"[DataIntegrity] {freshness['market']} {freshness['source_name']} is STALE "
                f"(age={freshness.get('age_hours')}h, threshold={freshness.get('threshold_hours')}h) as of {as_of}",
                level="warning",
            )

    # Coverage gaps and stale fundamentals
    for market, coverage in result.get("coverage", {}).items():
        prices = coverage.get("prices", {})
        if prices.get("status") == "failed":
            sentry_sdk.capture_message(
                f"[DataIntegrity] {market} missing price data: "
                f"{prices.get('missing_count')} of {prices.get('checked_count')} instruments "
                f"lack prices newer than {prices.get('cutoff_date')} as of {as_of}",
                level="error",
            )
        fundamentals = coverage.get("fundamentals", {})
        if fundamentals.get("status") == "failed":
            sentry_sdk.capture_message(
                f"[DataIntegrity] {market} stale fundamentals: "
                f"{fundamentals.get('stale_count')} of {fundamentals.get('checked_count')} instruments "
                f"have stale data as of {as_of}",
                level="warning",
            )

    # Score distribution anomalies
    for market, dist in result.get("distributions", {}).items():
        rs = dist.get("rs", {})
        if rs.get("status") == "failed":
            sentry_sdk.capture_message(
                f"[DataIntegrity] {market} RS distribution anomaly on {rs.get('score_date')}: "
                f"bucket_shares={rs.get('bucket_shares')} as of {as_of}",
                level="warning",
            )
        piotroski = dist.get("piotroski", {})
        if piotroski.get("status") == "failed":
            sentry_sdk.capture_message(
                f"[DataIntegrity] {market} Piotroski distribution anomaly on "
                f"{piotroski.get('score_date')}: "
                f"mean={piotroski.get('mean')} stddev={piotroski.get('stddev')} as of {as_of}",
                level="warning",
            )

    # Snapshot reproducibility failures (most severe — data is inconsistent)
    for snapshot in result.get("snapshots", []):
        if snapshot.get("status") == "failed":
            sentry_sdk.capture_message(
                f"[DataIntegrity] CRITICAL: {snapshot['market']} snapshot mismatch on "
                f"{snapshot.get('snapshot_date')} — stored≠rebuilt as of {as_of}",
                level="error",
            )

    logger.info(
        "Sentry alerts fired for data integrity report (as_of=%s, alerts_created=%s)",
        as_of,
        result.get("alerts_created"),
    )
