from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backfill_run import AdminBackfillRun
from app.models.instrument import Instrument
from app.services.symbol_resolution import resolve_symbol_payload, upsert_resolved_instrument

DEFAULT_ADMIN_BACKFILL_CHUNK_SIZE = 25
DEFAULT_BACKFILL_PRICE_DAYS = 365
DEFAULT_BACKFILL_FUNDAMENTAL_YEARS = 5
BACKFILL_PROGRESS_SAMPLE_LIMIT = 20


def normalize_backfill_tickers(tickers: Optional[list[str]]) -> list[str]:
    if not tickers:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for ticker in tickers:
        cleaned = ticker.strip().upper().replace("$", "").replace(".", "-")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


@dataclass(slots=True)
class BackfillScopePreview:
    market: str
    selection_mode: str
    requested_tickers: list[str]
    selected_tickers: list[str]
    unresolved_tickers: list[str]
    resolved_from_provider_tickers: list[str]
    existing_tickers: list[str]
    limit_requested: Optional[int]
    chunk_size: int
    price_only: bool
    score_requested: bool

    @property
    def requested_count(self) -> int:
        return len(self.requested_tickers)

    @property
    def selected_count(self) -> int:
        return len(self.selected_tickers)

    @property
    def unresolved_count(self) -> int:
        return len(self.unresolved_tickers)

    @property
    def resolved_from_provider_count(self) -> int:
        return len(self.resolved_from_provider_tickers)

    @property
    def existing_count(self) -> int:
        return len(self.existing_tickers)

    @property
    def chunk_count(self) -> int:
        if not self.selected_tickers:
            return 0
        return ceil(len(self.selected_tickers) / self.chunk_size)

    def sample_selected_tickers(self) -> list[str]:
        return self.selected_tickers[:BACKFILL_PROGRESS_SAMPLE_LIMIT]

    def sample_unresolved_tickers(self) -> list[str]:
        return self.unresolved_tickers[:BACKFILL_PROGRESS_SAMPLE_LIMIT]


async def _load_existing_market_tickers(
    db: AsyncSession,
    *,
    market: str,
    requested_tickers: list[str],
) -> dict[str, Instrument]:
    if not requested_tickers:
        return {}
    rows = (
        await db.execute(
            select(Instrument).where(
                Instrument.market == market,
                Instrument.is_active.is_(True),
                func.upper(Instrument.ticker).in_(requested_tickers),
            )
        )
    ).scalars().all()
    return {instrument.ticker.upper(): instrument for instrument in rows}


async def preview_admin_backfill_scope(
    db: AsyncSession,
    *,
    market: str,
    tickers: Optional[list[str]],
    limit: Optional[int],
    price_only: bool,
    score_requested: bool,
    chunk_size: int = DEFAULT_ADMIN_BACKFILL_CHUNK_SIZE,
) -> BackfillScopePreview:
    normalized_tickers = normalize_backfill_tickers(tickers)
    if limit is not None and limit > 0:
        normalized_tickers = normalized_tickers[:limit]

    if normalized_tickers:
        existing_by_ticker = await _load_existing_market_tickers(
            db,
            market=market,
            requested_tickers=normalized_tickers,
        )
        selected_tickers: list[str] = []
        unresolved_tickers: list[str] = []
        resolved_from_provider_tickers: list[str] = []
        existing_tickers: list[str] = []

        for ticker in normalized_tickers:
            if ticker in existing_by_ticker:
                selected_tickers.append(ticker)
                existing_tickers.append(ticker)
                continue

            payload = await resolve_symbol_payload(ticker, market)
            if payload is None:
                unresolved_tickers.append(ticker)
                continue

            selected_tickers.append(ticker)
            resolved_from_provider_tickers.append(ticker)

        return BackfillScopePreview(
            market=market,
            selection_mode="explicit_tickers",
            requested_tickers=normalized_tickers,
            selected_tickers=selected_tickers,
            unresolved_tickers=unresolved_tickers,
            resolved_from_provider_tickers=resolved_from_provider_tickers,
            existing_tickers=existing_tickers,
            limit_requested=limit,
            chunk_size=chunk_size,
            price_only=price_only,
            score_requested=score_requested,
        )

    stmt = (
        select(Instrument.ticker)
        .where(
            Instrument.market == market,
            Instrument.asset_type == "stock",
            Instrument.is_active.is_(True),
        )
        .order_by(Instrument.ticker.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    selected_tickers = [row[0] for row in (await db.execute(stmt)).all()]

    return BackfillScopePreview(
        market=market,
        selection_mode="market_scan",
        requested_tickers=[],
        selected_tickers=selected_tickers,
        unresolved_tickers=[],
        resolved_from_provider_tickers=[],
        existing_tickers=list(selected_tickers),
        limit_requested=limit,
        chunk_size=chunk_size,
        price_only=price_only,
        score_requested=score_requested,
    )


async def materialize_backfill_scope(
    db: AsyncSession,
    *,
    preview: BackfillScopePreview,
) -> None:
    if not preview.resolved_from_provider_tickers:
        return
    for ticker in preview.resolved_from_provider_tickers:
        payload = await resolve_symbol_payload(ticker, preview.market)
        if payload is None:
            continue
        await upsert_resolved_instrument(db, payload)
    await db.flush()


async def create_admin_backfill_run(
    db: AsyncSession,
    *,
    preview: BackfillScopePreview,
    requester_source: str,
    requester_user_id: Optional[str],
    result_metadata: Optional[dict[str, Any]] = None,
) -> AdminBackfillRun:
    run = AdminBackfillRun(
        market=preview.market,
        requested_tickers=preview.requested_tickers,
        selected_tickers=preview.selected_tickers,
        limit_requested=preview.limit_requested,
        chunk_size=preview.chunk_size,
        price_only=preview.price_only,
        score_requested=preview.score_requested,
        status="queued",
        requester_source=requester_source,
        requester_user_id=requester_user_id,
        requested_count=preview.requested_count,
        selected_count=preview.selected_count,
        processed_count=0,
        failed_count=0,
        result_metadata=result_metadata or {},
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    return run


async def get_admin_backfill_run(db: AsyncSession, run_id: int) -> Optional[AdminBackfillRun]:
    return await db.get(AdminBackfillRun, run_id)


def _merge_metadata(
    current: Optional[dict[str, Any]],
    updates: Optional[dict[str, Any]],
) -> dict[str, Any]:
    merged = dict(current or {})
    for key, value in (updates or {}).items():
        merged[key] = value
    return merged


async def set_admin_backfill_run_status(
    db: AsyncSession,
    *,
    run_id: int,
    status: str,
    celery_task_id: Optional[str] = None,
    processed_count: Optional[int] = None,
    failed_count: Optional[int] = None,
    error_message: Optional[str] = None,
    result_metadata: Optional[dict[str, Any]] = None,
) -> AdminBackfillRun:
    run = await db.get(AdminBackfillRun, run_id)
    if run is None:
        raise ValueError(f"AdminBackfillRun {run_id} does not exist")

    now = datetime.now(timezone.utc)
    run.status = status
    run.updated_at = now
    if celery_task_id is not None:
        run.celery_task_id = celery_task_id
    if processed_count is not None:
        run.processed_count = processed_count
    if failed_count is not None:
        run.failed_count = failed_count
    if error_message is not None:
        run.error_message = error_message
    run.result_metadata = _merge_metadata(run.result_metadata, result_metadata)

    if status == "running":
        run.started_at = run.started_at or now
    elif status == "completed":
        run.completed_at = now
    elif status == "failed":
        run.failed_at = now

    await db.flush()
    await db.refresh(run)
    return run
