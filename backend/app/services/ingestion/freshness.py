from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from statistics import fmean, pstdev
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.alert import Alert
from app.models.fundamental import FundamentalAnnual, FundamentalQuarterly
from app.models.instrument import Instrument
from app.models.price import Price
from app.models.snapshot import DataFreshness, ScoringSnapshot
from app.models.strategy_score import StrategyScore
from app.services.strategies.snapshot_generator import build_snapshot_payload

US_PRICES_SOURCE = "US_PRICES"
KR_PRICES_SOURCE = "KR_PRICES"
US_FUNDAMENTALS_SOURCE = "US_FUNDAMENTALS"
KR_FUNDAMENTALS_SOURCE = "KR_FUNDAMENTALS"
US_INSTITUTIONAL_SOURCE = "US_INSTITUTIONAL"
KR_INVESTOR_FLOWS_SOURCE = "KR_INVESTOR_FLOWS"

PRICE_STALE_DAYS = 7
QUARTERLY_FUNDAMENTAL_STALE_DAYS = 200
ANNUAL_FUNDAMENTAL_STALE_DAYS = 500

RS_BUCKETS = (
    ("1-20", 1, 20),
    ("21-40", 21, 40),
    ("41-60", 41, 60),
    ("61-80", 61, 80),
    ("81-99", 81, 99),
)


@dataclass(frozen=True)
class FreshnessPolicy:
    threshold_hours: int
    expected_interval_hours: int


FRESHNESS_POLICIES: dict[tuple[str, str], FreshnessPolicy] = {
    (US_PRICES_SOURCE, "US"): FreshnessPolicy(threshold_hours=36, expected_interval_hours=24),
    (KR_PRICES_SOURCE, "KR"): FreshnessPolicy(threshold_hours=36, expected_interval_hours=24),
    (US_FUNDAMENTALS_SOURCE, "US"): FreshnessPolicy(threshold_hours=168, expected_interval_hours=168),
    (KR_FUNDAMENTALS_SOURCE, "KR"): FreshnessPolicy(threshold_hours=168, expected_interval_hours=168),
    (US_INSTITUTIONAL_SOURCE, "US"): FreshnessPolicy(threshold_hours=336, expected_interval_hours=168),
    (KR_INVESTOR_FLOWS_SOURCE, "KR"): FreshnessPolicy(threshold_hours=168, expected_interval_hours=168),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _policy_for(source_name: str, market: str) -> FreshnessPolicy:
    return FRESHNESS_POLICIES.get((source_name, market), FreshnessPolicy(48, 24))


def _start_of_day(ts: datetime) -> datetime:
    return datetime.combine(ts.date(), time.min, tzinfo=timezone.utc)


def _to_iso_date(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


async def record_data_freshness(
    db: AsyncSession,
    *,
    source_name: str,
    market: str,
    succeeded: bool,
    records_updated: int = 0,
    error: Optional[str] = None,
    observed_at: Optional[datetime] = None,
) -> DataFreshness:
    observed_at = observed_at or _utc_now()
    market = market.upper()
    policy = _policy_for(source_name, market)

    result = await db.execute(
        select(DataFreshness).where(
            DataFreshness.source_name == source_name,
            DataFreshness.market == market,
        )
    )
    row = result.scalars().first()
    if row is None:
        row = DataFreshness(source_name=source_name, market=market)
        db.add(row)

    row.staleness_threshold_hours = policy.threshold_hours
    row.next_expected = observed_at + timedelta(hours=policy.expected_interval_hours)

    if succeeded:
        row.last_success_at = observed_at
        row.records_updated = records_updated
        row.last_error = error
    else:
        row.last_failure_at = observed_at
        row.records_updated = records_updated
        row.last_error = error

    await db.flush()
    return row


async def evaluate_source_freshness(
    db: AsyncSession,
    *,
    as_of: Optional[datetime] = None,
) -> list[dict]:
    as_of = as_of or _utc_now()
    result = await db.execute(select(DataFreshness).order_by(DataFreshness.market, DataFreshness.source_name))
    rows = result.scalars().all()

    evaluations: list[dict] = []
    for row in rows:
        threshold_hours = row.staleness_threshold_hours or _policy_for(row.source_name, row.market).threshold_hours
        age_hours = None
        status = "ok"
        reason = None

        if row.last_success_at:
            age_hours = round((as_of - row.last_success_at).total_seconds() / 3600, 2)
            if age_hours > threshold_hours:
                status = "stale"
                reason = f"Last successful run was {age_hours:.1f}h ago."
        else:
            status = "stale"
            reason = "No successful ingestion recorded yet."

        evaluations.append(
            {
                "source_name": row.source_name,
                "market": row.market,
                "status": status,
                "reason": reason,
                "records_updated": row.records_updated or 0,
                "last_success_at": row.last_success_at.isoformat() if row.last_success_at else None,
                "last_failure_at": row.last_failure_at.isoformat() if row.last_failure_at else None,
                "next_expected": row.next_expected.isoformat() if row.next_expected else None,
                "threshold_hours": threshold_hours,
                "age_hours": age_hours,
                "last_error": row.last_error,
            }
        )

    return evaluations


async def evaluate_missing_prices(
    db: AsyncSession,
    *,
    market: str,
    as_of_date: Optional[date] = None,
) -> dict:
    as_of_date = as_of_date or _utc_now().date()
    cutoff = as_of_date - timedelta(days=PRICE_STALE_DAYS)

    latest_price_sq = (
        select(
            Price.instrument_id.label("instrument_id"),
            func.max(Price.trade_date).label("latest_trade_date"),
        )
        .group_by(Price.instrument_id)
        .subquery()
    )

    result = await db.execute(
        select(Instrument.ticker, latest_price_sq.c.latest_trade_date)
        .outerjoin(latest_price_sq, latest_price_sq.c.instrument_id == Instrument.id)
        .where(
            Instrument.market == market,
            Instrument.asset_type == "stock",
            Instrument.is_active.is_(True),
        )
        .order_by(Instrument.ticker.asc())
    )
    rows = result.all()

    if not rows:
        return {
            "market": market,
            "status": "skipped",
            "checked_count": 0,
            "missing_count": 0,
            "cutoff_date": cutoff.isoformat(),
            "sample_tickers": [],
        }

    missing = [ticker for ticker, latest_date in rows if latest_date is None or latest_date < cutoff]
    return {
        "market": market,
        "status": "failed" if missing else "ok",
        "checked_count": len(rows),
        "missing_count": len(missing),
        "cutoff_date": cutoff.isoformat(),
        "sample_tickers": missing[:10],
    }


async def evaluate_stale_fundamentals(
    db: AsyncSession,
    *,
    market: str,
    as_of_date: Optional[date] = None,
) -> dict:
    as_of_date = as_of_date or _utc_now().date()
    quarterly_cutoff = as_of_date - timedelta(days=QUARTERLY_FUNDAMENTAL_STALE_DAYS)
    annual_cutoff = as_of_date - timedelta(days=ANNUAL_FUNDAMENTAL_STALE_DAYS)

    latest_quarterly_sq = (
        select(
            FundamentalQuarterly.instrument_id.label("instrument_id"),
            func.max(FundamentalQuarterly.report_date).label("latest_quarterly_date"),
        )
        .group_by(FundamentalQuarterly.instrument_id)
        .subquery()
    )
    latest_annual_sq = (
        select(
            FundamentalAnnual.instrument_id.label("instrument_id"),
            func.max(FundamentalAnnual.report_date).label("latest_annual_date"),
        )
        .group_by(FundamentalAnnual.instrument_id)
        .subquery()
    )

    result = await db.execute(
        select(
            Instrument.ticker,
            latest_quarterly_sq.c.latest_quarterly_date,
            latest_annual_sq.c.latest_annual_date,
        )
        .outerjoin(latest_quarterly_sq, latest_quarterly_sq.c.instrument_id == Instrument.id)
        .outerjoin(latest_annual_sq, latest_annual_sq.c.instrument_id == Instrument.id)
        .where(
            Instrument.market == market,
            Instrument.asset_type == "stock",
            Instrument.is_active.is_(True),
        )
        .order_by(Instrument.ticker.asc())
    )
    rows = result.all()

    if not rows:
        return {
            "market": market,
            "status": "skipped",
            "checked_count": 0,
            "stale_count": 0,
            "quarterly_cutoff": quarterly_cutoff.isoformat(),
            "annual_cutoff": annual_cutoff.isoformat(),
            "sample_tickers": [],
        }

    stale = []
    for ticker, latest_quarterly_date, latest_annual_date in rows:
        quarterly_stale = latest_quarterly_date is None or latest_quarterly_date < quarterly_cutoff
        annual_stale = latest_annual_date is None or latest_annual_date < annual_cutoff
        if quarterly_stale or annual_stale:
            stale.append(ticker)

    return {
        "market": market,
        "status": "failed" if stale else "ok",
        "checked_count": len(rows),
        "stale_count": len(stale),
        "quarterly_cutoff": quarterly_cutoff.isoformat(),
        "annual_cutoff": annual_cutoff.isoformat(),
        "sample_tickers": stale[:10],
    }


async def _resolve_latest_score_date(
    db: AsyncSession,
    *,
    market: str,
    score_date: Optional[date],
) -> Optional[date]:
    if score_date is not None:
        return score_date

    result = await db.execute(
        select(func.max(StrategyScore.score_date))
        .select_from(StrategyScore)
        .join(Instrument, Instrument.id == StrategyScore.instrument_id)
        .where(Instrument.market == market)
    )
    return result.scalar_one_or_none()


async def evaluate_rs_distribution(
    db: AsyncSession,
    *,
    market: str,
    score_date: Optional[date] = None,
) -> dict:
    resolved_score_date = await _resolve_latest_score_date(db, market=market, score_date=score_date)
    if resolved_score_date is None:
        return {"market": market, "status": "skipped", "reason": "No strategy scores available.", "score_date": None}

    result = await db.execute(
        select(StrategyScore.rs_rating)
        .join(Instrument, Instrument.id == StrategyScore.instrument_id)
        .where(
            Instrument.market == market,
            StrategyScore.score_date == resolved_score_date,
            StrategyScore.rs_rating.is_not(None),
        )
    )
    values = [float(row[0]) for row in result.all() if row[0] is not None]
    if len(values) < 10:
        return {
            "market": market,
            "status": "skipped",
            "reason": "Not enough RS observations for a stable distribution check.",
            "score_date": resolved_score_date.isoformat(),
            "count": len(values),
        }

    buckets = {label: 0 for label, _, _ in RS_BUCKETS}
    for value in values:
        rounded = int(round(value))
        for label, lower, upper in RS_BUCKETS:
            if lower <= rounded <= upper:
                buckets[label] += 1
                break

    shares = {label: round(count / len(values), 3) for label, count in buckets.items()}
    passes = (
        min(values) <= 20
        and max(values) >= 80
        and min(shares.values()) >= 0.02
        and max(shares.values()) <= 0.55
    )

    return {
        "market": market,
        "status": "ok" if passes else "failed",
        "score_date": resolved_score_date.isoformat(),
        "count": len(values),
        "mean": round(fmean(values), 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "bucket_shares": shares,
    }


async def evaluate_piotroski_distribution(
    db: AsyncSession,
    *,
    market: str,
    score_date: Optional[date] = None,
) -> dict:
    resolved_score_date = await _resolve_latest_score_date(db, market=market, score_date=score_date)
    if resolved_score_date is None:
        return {"market": market, "status": "skipped", "reason": "No strategy scores available.", "score_date": None}

    result = await db.execute(
        select(StrategyScore.piotroski_f_raw)
        .join(Instrument, Instrument.id == StrategyScore.instrument_id)
        .where(
            Instrument.market == market,
            StrategyScore.score_date == resolved_score_date,
            StrategyScore.piotroski_f_raw.is_not(None),
        )
    )
    values = [int(row[0]) for row in result.all() if row[0] is not None]
    if len(values) < 5:
        return {
            "market": market,
            "status": "skipped",
            "reason": "Not enough Piotroski observations for a stable distribution check.",
            "score_date": resolved_score_date.isoformat(),
            "count": len(values),
        }

    mean_value = fmean(values)
    std_dev = pstdev(values) if len(values) > 1 else 0.0
    unique_values = len(set(values))
    passes = 2.0 <= mean_value <= 7.0 and unique_values >= 3 and 0.5 <= std_dev <= 3.5

    return {
        "market": market,
        "status": "ok" if passes else "failed",
        "score_date": resolved_score_date.isoformat(),
        "count": len(values),
        "mean": round(mean_value, 2),
        "stddev": round(std_dev, 2),
        "min": min(values),
        "max": max(values),
        "unique_values": unique_values,
    }


async def evaluate_snapshot_reproducibility(
    db: AsyncSession,
    *,
    market: str,
    asset_type: str = "stock",
    snapshot_date: Optional[date] = None,
) -> dict:
    stmt = select(ScoringSnapshot).where(
        ScoringSnapshot.market == market,
        ScoringSnapshot.asset_type == asset_type,
    )
    if snapshot_date is not None:
        stmt = stmt.where(ScoringSnapshot.snapshot_date == snapshot_date)
    else:
        stmt = stmt.order_by(ScoringSnapshot.snapshot_date.desc()).limit(1)

    result = await db.execute(stmt)
    snapshot = result.scalars().first()
    if snapshot is None:
        return {
            "market": market,
            "asset_type": asset_type,
            "status": "skipped",
            "reason": "No snapshot available for reproducibility verification.",
            "snapshot_date": _to_iso_date(snapshot_date),
        }

    rebuilt = await build_snapshot_payload(
        db,
        snapshot_date=snapshot.snapshot_date,
        market=market,
        asset_type=asset_type,
    )
    if rebuilt is None:
        return {
            "market": market,
            "asset_type": asset_type,
            "status": "failed",
            "reason": "Stored snapshot exists but no fresh consensus payload could be rebuilt.",
            "snapshot_date": snapshot.snapshot_date.isoformat(),
        }

    stored_meta = snapshot.metadata_ or {}
    rebuilt_meta = rebuilt["metadata"]
    matches = (
        snapshot.rankings_json == rebuilt["rankings_json"]
        and stored_meta.get("config_hash") == rebuilt_meta.get("config_hash")
        and stored_meta.get("instruments_count") == rebuilt_meta.get("instruments_count")
    )

    return {
        "market": market,
        "asset_type": asset_type,
        "status": "ok" if matches else "failed",
        "snapshot_date": snapshot.snapshot_date.isoformat(),
        "stored_config_hash": stored_meta.get("config_hash"),
        "rebuilt_config_hash": rebuilt_meta.get("config_hash"),
        "stored_instruments_count": stored_meta.get("instruments_count"),
        "rebuilt_instruments_count": rebuilt_meta.get("instruments_count"),
        "matches": matches,
    }


async def _create_daily_alert(
    db: AsyncSession,
    *,
    alert_type: str,
    severity: str,
    title: str,
    detail: str,
    market: Optional[str] = None,
    instrument_id: Optional[int] = None,
    threshold_value: Optional[float] = None,
    actual_value: Optional[float] = None,
    as_of: Optional[datetime] = None,
) -> bool:
    as_of = as_of or _utc_now()
    day_start = _start_of_day(as_of)

    stmt = select(Alert.id).where(
        Alert.alert_type == alert_type,
        Alert.title == title,
        Alert.created_at >= day_start,
    )
    if market is None:
        stmt = stmt.where(Alert.market.is_(None))
    else:
        stmt = stmt.where(Alert.market == market)
    if instrument_id is None:
        stmt = stmt.where(Alert.instrument_id.is_(None))
    else:
        stmt = stmt.where(Alert.instrument_id == instrument_id)

    existing = await db.execute(stmt.limit(1))
    if existing.scalar_one_or_none() is not None:
        return False

    db.add(
        Alert(
            instrument_id=instrument_id,
            market=market,
            alert_type=alert_type,
            severity=severity,
            title=title,
            detail=detail,
            threshold_value=threshold_value,
            actual_value=actual_value,
            created_at=as_of,
        )
    )
    await db.flush()
    return True


async def monitor_data_integrity(
    db: AsyncSession,
    *,
    markets: Optional[list[str]] = None,
    as_of: Optional[datetime] = None,
    score_date: Optional[date] = None,
    snapshot_date: Optional[date] = None,
    include_freshness: bool = True,
    include_coverage: bool = True,
    include_distribution: bool = True,
    include_snapshot: bool = True,
) -> dict:
    as_of = as_of or _utc_now()
    markets = [market.upper() for market in (markets or ["US", "KR"])]
    alerts_created = 0

    freshness_results: list[dict] = []
    coverage_results: dict[str, dict] = {}
    distribution_results: dict[str, dict] = {}
    snapshot_results: list[dict] = []

    if include_freshness:
        freshness_results = await evaluate_source_freshness(db, as_of=as_of)
        for result in freshness_results:
            if result["status"] != "stale":
                continue
            created = await _create_daily_alert(
                db,
                alert_type="DATA_STALE",
                severity="WARNING",
                title=f"{result['market']} {result['source_name']} freshness stale",
                detail=result["reason"] or (result["last_error"] or "Freshness threshold exceeded."),
                market=result["market"],
                threshold_value=float(result["threshold_hours"]),
                actual_value=float(result["age_hours"]) if result["age_hours"] is not None else None,
                as_of=as_of,
            )
            alerts_created += int(created)

    for market in markets:
        if include_coverage:
            price_result = await evaluate_missing_prices(db, market=market, as_of_date=as_of.date())
            fundamental_result = await evaluate_stale_fundamentals(db, market=market, as_of_date=as_of.date())
            coverage_results[market] = {
                "prices": price_result,
                "fundamentals": fundamental_result,
            }

            if price_result["status"] == "failed":
                created = await _create_daily_alert(
                    db,
                    alert_type="DATA_GAP",
                    severity="CRITICAL",
                    title=f"{market} missing fresh price data",
                    detail=(
                        f"{price_result['missing_count']} of {price_result['checked_count']} active instruments "
                        f"lack prices newer than {price_result['cutoff_date']}. "
                        f"Examples: {', '.join(price_result['sample_tickers']) or 'n/a'}."
                    ),
                    market=market,
                    threshold_value=0.0,
                    actual_value=float(price_result["missing_count"]),
                    as_of=as_of,
                )
                alerts_created += int(created)

            if fundamental_result["status"] == "failed":
                created = await _create_daily_alert(
                    db,
                    alert_type="DATA_GAP",
                    severity="WARNING",
                    title=f"{market} stale fundamentals detected",
                    detail=(
                        f"{fundamental_result['stale_count']} of {fundamental_result['checked_count']} active instruments "
                        f"have quarterly fundamentals older than {fundamental_result['quarterly_cutoff']} "
                        f"or annual fundamentals older than {fundamental_result['annual_cutoff']}. "
                        f"Examples: {', '.join(fundamental_result['sample_tickers']) or 'n/a'}."
                    ),
                    market=market,
                    threshold_value=0.0,
                    actual_value=float(fundamental_result["stale_count"]),
                    as_of=as_of,
                )
                alerts_created += int(created)

        if include_distribution:
            rs_result = await evaluate_rs_distribution(db, market=market, score_date=score_date)
            piotroski_result = await evaluate_piotroski_distribution(db, market=market, score_date=score_date)
            distribution_results[market] = {
                "rs": rs_result,
                "piotroski": piotroski_result,
            }

            if rs_result["status"] == "failed":
                created = await _create_daily_alert(
                    db,
                    alert_type="DATA_DISTRIBUTION",
                    severity="WARNING",
                    title=f"{market} RS distribution anomaly",
                    detail=(
                        f"RS ratings on {rs_result['score_date']} look overly concentrated. "
                        f"Bucket shares: {rs_result['bucket_shares']}."
                    ),
                    market=market,
                    threshold_value=0.55,
                    actual_value=max(rs_result["bucket_shares"].values()),
                    as_of=as_of,
                )
                alerts_created += int(created)

            if piotroski_result["status"] == "failed":
                created = await _create_daily_alert(
                    db,
                    alert_type="DATA_DISTRIBUTION",
                    severity="WARNING",
                    title=f"{market} Piotroski distribution anomaly",
                    detail=(
                        f"Piotroski F-score distribution on {piotroski_result['score_date']} "
                        f"looks off (mean={piotroski_result['mean']}, stddev={piotroski_result['stddev']}, "
                        f"unique_values={piotroski_result['unique_values']})."
                    ),
                    market=market,
                    threshold_value=3.0,
                    actual_value=float(piotroski_result["mean"]),
                    as_of=as_of,
                )
                alerts_created += int(created)

        if include_snapshot:
            snapshot_result = await evaluate_snapshot_reproducibility(
                db,
                market=market,
                asset_type="stock",
                snapshot_date=snapshot_date,
            )
            snapshot_results.append(snapshot_result)

            if snapshot_result["status"] == "failed":
                created = await _create_daily_alert(
                    db,
                    alert_type="SNAPSHOT_MISMATCH",
                    severity="CRITICAL",
                    title=f"{market} snapshot reproducibility mismatch",
                    detail=(
                        f"Stored snapshot {snapshot_result['snapshot_date']} does not match a fresh rebuild. "
                        f"Stored config={snapshot_result.get('stored_config_hash')} rebuilt config={snapshot_result.get('rebuilt_config_hash')}."
                    ),
                    market=market,
                    threshold_value=0.0,
                    actual_value=1.0,
                    as_of=as_of,
                )
                alerts_created += int(created)

    await db.commit()

    return {
        "as_of": as_of.isoformat(),
        "markets": markets,
        "freshness": freshness_results,
        "coverage": coverage_results,
        "distributions": distribution_results,
        "snapshots": snapshot_results,
        "alerts_created": alerts_created,
    }


async def run_data_integrity_monitoring(
    *,
    markets: Optional[list[str]] = None,
    as_of: Optional[datetime] = None,
    score_date: Optional[date] = None,
    snapshot_date: Optional[date] = None,
    include_freshness: bool = True,
    include_coverage: bool = True,
    include_distribution: bool = True,
    include_snapshot: bool = True,
) -> dict:
    async with AsyncSessionLocal() as db:
        return await monitor_data_integrity(
            db,
            markets=markets,
            as_of=as_of,
            score_date=score_date,
            snapshot_date=snapshot_date,
            include_freshness=include_freshness,
            include_coverage=include_coverage,
            include_distribution=include_distribution,
            include_snapshot=include_snapshot,
        )
