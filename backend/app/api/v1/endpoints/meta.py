"""
GET /api/v1/market-regime          — current regime for all markets
GET /api/v1/snapshots/latest       — latest frozen rankings snapshot
GET /api/v1/snapshots/{date}       — snapshot for a specific date
GET /api/v1/alerts                 — recent alerts

Also exposes scoring trigger endpoints for admin use:
POST /api/v1/scoring/trigger       — enqueue full pipeline task
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_api_key
from app.api.deps import get_db, get_read_db
from app.models.alert import Alert
from app.models.backfill_run import AdminBackfillRun
from app.models.market_regime import MarketRegime
from app.models.snapshot import ScoringSnapshot
from app.schemas.v1 import (
    AdminBackfillPreview,
    AdminBackfillRequest,
    AdminBackfillResponse,
    AdminBackfillRunResponse,
    AlertEntry, AlertsResponse,
    MarketRegimeResponse, RegimeEntry,
    SnapshotMeta, SnapshotResponse,
    ScoringTriggerRequest, ScoringTriggerResponse,
)
from app.services.backfill_runs import (
    DEFAULT_ADMIN_BACKFILL_CHUNK_SIZE,
    create_admin_backfill_run,
    get_admin_backfill_run,
    materialize_backfill_scope,
    preview_admin_backfill_scope,
    set_admin_backfill_run_status,
)

router = APIRouter()


# =============================================================================
# Market Regime
# =============================================================================

@router.get("/market-regime", response_model=MarketRegimeResponse,
            summary="Current market regime for US and KR")
async def get_market_regime(
    include_history: int = Query(default=0, ge=0, le=30,
                                 description="Number of past regime records to include per market"),
    db: AsyncSession = Depends(get_read_db),
) -> MarketRegimeResponse:
    """
    Returns the latest market regime state for US and KR.

    Set ``include_history=N`` to also return the N most recent prior records.
    """
    def _to_entry(r: MarketRegime) -> RegimeEntry:
        return RegimeEntry(
            market                 = r.market,
            state                  = r.state,
            prior_state            = r.prior_state,
            trigger_reason         = r.trigger_reason,
            effective_date         = r.effective_date,
            drawdown_from_high     = float(r.drawdown_from_high) if r.drawdown_from_high else None,
            distribution_day_count = r.distribution_day_count,
            follow_through_day     = r.follow_through_day or False,
        )

    us_entry: Optional[RegimeEntry] = None
    kr_entry: Optional[RegimeEntry] = None
    history: list[RegimeEntry] = []

    for mkt in ("US", "KR"):
        q = await db.execute(
            select(MarketRegime)
            .where(MarketRegime.market == mkt)
            .order_by(desc(MarketRegime.effective_date))
            .limit(max(1, include_history + 1))
        )
        rows = q.scalars().all()
        if not rows:
            continue

        entry = _to_entry(rows[0])
        if mkt == "US":
            us_entry = entry
        else:
            kr_entry = entry

        if include_history > 0:
            history.extend(_to_entry(r) for r in rows[1: include_history + 1])

    return MarketRegimeResponse(us=us_entry, kr=kr_entry, history=history)


# =============================================================================
# Snapshots
# =============================================================================

def _build_snapshot_meta(snap: ScoringSnapshot) -> SnapshotMeta:
    meta = snap.metadata_ or {}
    return SnapshotMeta(
        snapshot_date          = snap.snapshot_date,
        market                 = snap.market,
        asset_type             = snap.asset_type,
        regime_state           = snap.regime_state,
        instruments_count      = meta.get("instruments_count", 0),
        config_hash            = meta.get("config_hash", ""),
        avg_final_score        = meta.get("avg_final_score", 0.0),
        conviction_distribution = meta.get("conviction_distribution", {}),
        created_at             = snap.created_at,
    )


@router.get("/snapshots/latest", response_model=SnapshotResponse,
            summary="Latest frozen consensus rankings")
async def get_latest_snapshot(
    market:     str = Query(default="US", pattern="^(US|KR)$"),
    asset_type: str = Query(default="stock", pattern="^(stock|etf)$"),
    limit:      int = Query(default=50, ge=1, le=200),
    offset:     int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_read_db),
) -> SnapshotResponse:
    """Return the most recent snapshot for a given market + asset_type."""
    q = await db.execute(
        select(ScoringSnapshot)
        .where(ScoringSnapshot.market == market, ScoringSnapshot.asset_type == asset_type)
        .order_by(desc(ScoringSnapshot.snapshot_date))
        .limit(1)
    )
    snap = q.scalars().first()
    if not snap:
        raise HTTPException(
            404,
            detail=f"No snapshot found for {market}/{asset_type}. Run the scoring pipeline first."
        )

    rankings: list[dict] = snap.rankings_json or []
    page = rankings[offset: offset + limit]

    return SnapshotResponse(meta=_build_snapshot_meta(snap), items=page)


@router.get("/snapshots/{snapshot_date}", response_model=SnapshotResponse,
            summary="Snapshot for a specific date")
async def get_snapshot_by_date(
    snapshot_date: date,
    market:     str = Query(default="US", pattern="^(US|KR)$"),
    asset_type: str = Query(default="stock", pattern="^(stock|etf)$"),
    limit:      int = Query(default=50, ge=1, le=200),
    offset:     int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_read_db),
) -> SnapshotResponse:
    q = await db.execute(
        select(ScoringSnapshot).where(
            ScoringSnapshot.snapshot_date == snapshot_date,
            ScoringSnapshot.market        == market,
            ScoringSnapshot.asset_type    == asset_type,
        )
    )
    snap = q.scalars().first()
    if not snap:
        raise HTTPException(404, detail=f"No snapshot for {snapshot_date}/{market}/{asset_type}.")

    rankings: list[dict] = snap.rankings_json or []
    page = rankings[offset: offset + limit]
    return SnapshotResponse(meta=_build_snapshot_meta(snap), items=page)


# =============================================================================
# Alerts
# =============================================================================

@router.get("/alerts", response_model=AlertsResponse, summary="Recent scoring alerts")
async def get_alerts(
    market:     Optional[str] = Query(None, pattern="^(US|KR)$"),
    severity:   Optional[str] = Query(None, pattern="^(CRITICAL|WARNING|INFO)$"),
    days:       int           = Query(default=7, ge=1, le=90),
    limit:      int           = Query(default=100, ge=1, le=500),
    acknowledged: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_read_db),
) -> AlertsResponse:
    """
    Return alerts from the last ``days`` days.

    Filterable by severity, market, and acknowledgement status.
    """
    from datetime import datetime, timezone
    from app.models.instrument import Instrument
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    stmt = select(Alert, Instrument.ticker).outerjoin(Instrument, Alert.instrument_id == Instrument.id).where(Alert.created_at >= cutoff)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if acknowledged is not None:
        stmt = stmt.where(Alert.is_read == acknowledged)
    if market:
        stmt = stmt.where(Alert.market == market)
        
    stmt = stmt.order_by(desc(Alert.created_at)).limit(limit)

    try:
        result = await db.execute(stmt)
        rows = result.all()
    except Exception:
        # alerts table might not be populated yet
        rows = []

    entries = [
        AlertEntry(
            id              = a.id,
            instrument_id   = a.instrument_id,
            market          = a.market,
            ticker          = ticker,
            alert_type      = a.alert_type,
            severity        = a.severity,
            title           = a.title,
            detail          = a.detail,
            threshold_value = float(a.threshold_value) if a.threshold_value is not None else None,
            actual_value    = float(a.actual_value) if a.actual_value is not None else None,
            is_read         = a.is_read or False,
            created_at      = a.created_at,
        )
        for a, ticker in rows
    ]

    critical = sum(1 for e in entries if e.severity == "CRITICAL")
    warnings = sum(1 for e in entries if e.severity == "WARNING")

    return AlertsResponse(
        total    = len(entries),
        critical = critical,
        warnings = warnings,
        items    = entries,
    )


# =============================================================================
# Scoring Trigger (admin)
# =============================================================================

@router.post("/scoring/trigger", response_model=ScoringTriggerResponse,
             summary="Trigger the full scoring pipeline (admin)")
async def trigger_scoring(
    body: ScoringTriggerRequest,
    api_key: str = Depends(get_api_key),
) -> ScoringTriggerResponse:
    """
    Enqueue the full scoring pipeline as a Celery task.
    The task runs asynchronously; poll ``/health`` or Flower to monitor.
    """
    _ = api_key
    try:
        from app.tasks.scoring_tasks import run_full_pipeline_task
        task = run_full_pipeline_task.delay(
            score_date      = body.score_date.isoformat() if body.score_date else None,
            market          = body.market,
            instrument_ids  = body.instrument_ids,
        )
        return ScoringTriggerResponse(
            task_id = task.id,
            status  = "queued",
            message = f"Scoring pipeline queued as task {task.id}",
        )
    except Exception as exc:
        raise HTTPException(500, detail=f"Failed to queue task: {exc}")


# =============================================================================
# Admin Backfill
# =============================================================================


def _serialize_admin_backfill_run(run: AdminBackfillRun) -> AdminBackfillRunResponse:
    return AdminBackfillRunResponse(
        id=run.id,
        market=run.market,
        requested_tickers=list(run.requested_tickers or []),
        selected_tickers=list(run.selected_tickers or []),
        limit_requested=run.limit_requested,
        chunk_size=run.chunk_size,
        price_only=bool(run.price_only),
        score_requested=bool(run.score_requested),
        status=run.status,
        requester_source=run.requester_source,
        requester_user_id=run.requester_user_id,
        celery_task_id=run.celery_task_id,
        requested_count=run.requested_count,
        selected_count=run.selected_count,
        processed_count=run.processed_count,
        failed_count=run.failed_count,
        queued_at=run.queued_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        failed_at=run.failed_at,
        updated_at=run.updated_at,
        error_message=run.error_message,
        result_metadata=dict(run.result_metadata or {}),
    )


def _serialize_admin_backfill_preview(preview) -> AdminBackfillPreview:
    return AdminBackfillPreview(
        market=preview.market,
        selection_mode=preview.selection_mode,
        requested_count=preview.requested_count,
        selected_count=preview.selected_count,
        unresolved_count=preview.unresolved_count,
        existing_count=preview.existing_count,
        resolved_from_provider_count=preview.resolved_from_provider_count,
        limit_requested=preview.limit_requested,
        chunk_size=preview.chunk_size,
        chunk_count=preview.chunk_count,
        price_only=preview.price_only,
        score_requested=preview.score_requested,
        sample_selected_tickers=preview.sample_selected_tickers(),
        sample_unresolved_tickers=preview.sample_unresolved_tickers(),
    )


@router.post(
    "/admin/backfill",
    response_model=AdminBackfillResponse,
    summary="Preview or queue an admin backfill run",
)
async def trigger_admin_backfill(
    body: AdminBackfillRequest,
    api_key: str = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminBackfillResponse:
    _ = api_key
    if body.price_only and body.score:
        raise HTTPException(
            400,
            detail="price_only=true cannot be combined with score=true",
        )

    preview = await preview_admin_backfill_scope(
        db,
        market=body.market,
        tickers=body.tickers,
        limit=body.limit,
        price_only=body.price_only,
        score_requested=body.score,
        chunk_size=DEFAULT_ADMIN_BACKFILL_CHUNK_SIZE,
    )
    preview_payload = _serialize_admin_backfill_preview(preview)

    if body.dry_run:
        return AdminBackfillResponse(
            dry_run=True,
            preview=preview_payload,
            run=None,
            message=f"Dry run ready for {preview.selected_count} selected instruments in {body.market}.",
        )

    if preview.selected_count == 0:
        raise HTTPException(
            400,
            detail="No instruments matched the requested backfill scope.",
        )

    await materialize_backfill_scope(db, preview=preview)
    run = await create_admin_backfill_run(
        db,
        preview=preview,
        requester_source="api_key",
        requester_user_id=None,
        result_metadata={
            "selection_mode": preview.selection_mode,
            "resolved_from_provider_count": preview.resolved_from_provider_count,
            "unresolved_count": preview.unresolved_count,
            "sample_unresolved_tickers": preview.sample_unresolved_tickers(),
        },
    )
    await db.commit()

    try:
        from app.tasks.backfill_tasks import run_admin_backfill_task

        task = run_admin_backfill_task.delay(run_id=run.id)
        await set_admin_backfill_run_status(
            db,
            run_id=run.id,
            status="queued",
            celery_task_id=task.id,
            result_metadata={"dispatch_channel": "celery"},
        )
        await db.commit()
        await db.refresh(run)
    except Exception as exc:
        await db.rollback()
        await set_admin_backfill_run_status(
            db,
            run_id=run.id,
            status="failed",
            error_message=f"Failed to dispatch admin backfill task: {exc}",
            result_metadata={"failure_reason": "dispatch_error"},
        )
        await db.commit()
        raise HTTPException(503, detail=f"Failed to queue admin backfill task: {exc}") from exc

    return AdminBackfillResponse(
        dry_run=False,
        preview=preview_payload,
        run=_serialize_admin_backfill_run(run),
        message=f"Admin backfill queued as run {run.id}.",
    )


@router.get(
    "/admin/backfill/{run_id}",
    response_model=AdminBackfillRunResponse,
    summary="Get admin backfill run status",
)
async def get_admin_backfill_status(
    run_id: int,
    api_key: str = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminBackfillRunResponse:
    _ = api_key
    run = await get_admin_backfill_run(db, run_id)
    if run is None:
        raise HTTPException(404, detail=f"Admin backfill run {run_id} not found.")
    return _serialize_admin_backfill_run(run)
