from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Optional

import sentry_sdk
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import aliased
from app.core.database import AsyncTaskSessionLocal
from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.user import UserPushToken
from app.services.alerts.push import send_push_notifications
from app.services.ingestion.freshness import run_data_integrity_monitoring
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _conviction_rank(column):
    return case(
        (column == "UNRANKED", 0),
        (column == "BRONZE", 1),
        (column == "SILVER", 2),
        (column == "GOLD", 3),
        (column == "PLATINUM", 4),
        (column == "DIAMOND", 5),
        else_=0,
    )


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_date(value: Optional[str]) -> Optional[date]:
    return date.fromisoformat(value) if value else None


async def _run_conviction_upgrade_push_alerts(limit: int = 5) -> dict:
    async with AsyncTaskSessionLocal() as db:
        latest_date = (
            await db.execute(select(func.max(ConsensusScore.score_date)))
        ).scalar_one_or_none()

        if latest_date is None:
            return {"status": "skipped", "reason": "no_consensus_scores"}

        previous_date = (
            await db.execute(
                select(func.max(ConsensusScore.score_date)).where(
                    ConsensusScore.score_date < latest_date
                )
            )
        ).scalar_one_or_none()

        if previous_date is None:
            return {"status": "skipped", "reason": "no_previous_score_date"}

        current = aliased(ConsensusScore)
        previous = aliased(ConsensusScore)
        current_rank = _conviction_rank(current.conviction_level)
        previous_rank = _conviction_rank(previous.conviction_level)

        upgrades = (
            await db.execute(
                select(
                    Instrument.ticker,
                    Instrument.market,
                    Instrument.name,
                    current.conviction_level.label("current_conviction"),
                    previous.conviction_level.label("previous_conviction"),
                    current.final_score.label("current_score"),
                    previous.final_score.label("previous_score"),
                )
                .join(Instrument, Instrument.id == current.instrument_id)
                .outerjoin(
                    previous,
                    and_(
                        previous.instrument_id == current.instrument_id,
                        previous.score_date == previous_date,
                    ),
                )
                .where(
                    current.score_date == latest_date,
                    Instrument.is_active == True,
                    current_rank >= 3,
                    current_rank > func.coalesce(previous_rank, 0),
                )
                .order_by(current_rank.desc(), current.final_score.desc())
                .limit(limit)
            )
        ).all()

        if not upgrades:
            return {
                "status": "skipped",
                "reason": "no_conviction_upgrades",
                "latest_date": latest_date.isoformat(),
            }

        tokens = list(
            dict.fromkeys(
                (
                    await db.execute(select(UserPushToken.expo_push_token))
                ).scalars().all()
            )
        )

        if not tokens:
            return {
                "status": "skipped",
                "reason": "no_registered_push_tokens",
                "latest_date": latest_date.isoformat(),
                "upgrades_found": len(upgrades),
            }

        top = upgrades[0]
        additional_count = max(len(upgrades) - 1, 0)
        title = f"{top.ticker} upgraded to {top.current_conviction}"
        body = (
            f"{top.name} moved up from {top.previous_conviction or 'UNRANKED'} "
            f"on {latest_date.isoformat()}"
        )
        if additional_count:
            body += f" + {additional_count} more conviction upgrades."

        result = await send_push_notifications(
            tokens=tokens,
            title=title,
            body=body,
            data={
                "type": "conviction_upgrade",
                "score_date": latest_date.isoformat(),
                "items": [
                    {
                        "ticker": row.ticker,
                        "market": row.market,
                        "name": row.name,
                        "current_conviction": row.current_conviction,
                        "previous_conviction": row.previous_conviction or "UNRANKED",
                    }
                    for row in upgrades
                ],
            },
        )

        return {
            "status": "sent",
            "latest_date": latest_date.isoformat(),
            "previous_date": previous_date.isoformat(),
            "upgrades_found": len(upgrades),
            "tokens_targeted": len(tokens),
            "tickets": result.get("tickets", []),
        }


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


@celery_app.task(name="app.tasks.alerts.send_conviction_upgrade_push_alerts")
def send_conviction_upgrade_push_alerts_task(limit: int = 5) -> dict:
    return asyncio.run(_run_conviction_upgrade_push_alerts(limit=limit))


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
