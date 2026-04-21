"""
GET /api/v1/instruments/{ticker}

Returns the full scoring breakdown for a single instrument — all 5 strategy
scores with their detailed sub-criteria, plus the technical composite and
consensus conviction.

Path parameters
---------------
ticker   Stock ticker (e.g. AAPL, 005930)

Query parameters
----------------
market        US | KR  (required when ticker is ambiguous)
score_date    ISO date (default: latest available for this instrument)
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.database import AsyncSessionLocal
from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.price import Price
from app.models.strategy_score import StrategyScore
from app.schemas.v1 import (
    ChartLinePoint, ChartPatternAnchor, ChartPatternOverlay, ChartPriceBar,
    CANSLIMDetail, InstrumentDetailResponse,
    InstrumentChartResponse,
    ScoreHistoryPoint, WeinsteinStageHistoryPoint,
    MinerviniDetail, PiotroskiDetail, TechnicalDetail, WeinsteinDetail,
)
from app.services.universe import build_coverage_map

router = APIRouter()
BENCHMARK_TICKER = {"US": "SPY", "KR": "069500"}


def _f(val) -> Optional[float]:
    return float(val) if val is not None else None


def _i(val) -> Optional[int]:
    return int(val) if val is not None else None


async def _resolve_instrument(
    ticker: str,
    market: Optional[str],
    db: AsyncSession,
) -> Instrument:
    stmt = select(Instrument).where(
        func.upper(Instrument.ticker) == ticker.upper(),
        Instrument.is_active == True,
    )
    if market:
        stmt = stmt.where(Instrument.market == market)

    result = await db.execute(stmt)
    instruments = result.scalars().all()

    if not instruments:
        raise HTTPException(404, detail=f"Instrument '{ticker}' not found.")
    if len(instruments) > 1 and not market:
        markets_found = [i.market for i in instruments]
        raise HTTPException(
            400,
            detail=f"Ticker '{ticker}' exists in multiple markets: {markets_found}. "
                   f"Please specify ?market=US or ?market=KR."
        )
    instrument = instruments[0]
    return instrument


async def _resolve_reference_date(
    instrument_id: int,
    *,
    score_date: Optional[date],
    db: AsyncSession,
) -> Optional[date]:
    if score_date is not None:
        return score_date

    candidate_queries = [
        select(func.max(ConsensusScore.score_date)).where(ConsensusScore.instrument_id == instrument_id),
        select(func.max(StrategyScore.score_date)).where(StrategyScore.instrument_id == instrument_id),
        select(func.max(Price.trade_date)).where(Price.instrument_id == instrument_id),
    ]
    for query in candidate_queries:
        result = await db.execute(query)
        resolved = result.scalar_one_or_none()
        if resolved is not None:
            return resolved
    return None


def _rolling_sma(values: list[float], window: int) -> list[Optional[float]]:
    result: list[Optional[float]] = []
    running_sum = 0.0
    buffer: list[float] = []

    for value in values:
        buffer.append(value)
        running_sum += value
        if len(buffer) > window:
            running_sum -= buffer.pop(0)

        result.append(running_sum / window if len(buffer) >= window else None)

    return result


def _resample_price_rows(price_rows: list[Price], stride: int) -> list[Price]:
    if stride <= 1:
        return price_rows

    sampled: list[Price] = []
    for start_idx in range(0, len(price_rows), stride):
        chunk = price_rows[start_idx:start_idx + stride]
        if not chunk:
            continue
        first = chunk[0]
        last = chunk[-1]
        highs = [float(row.high) for row in chunk if row.high is not None]
        lows = [float(row.low) for row in chunk if row.low is not None]
        volumes = [int(row.volume or 0) for row in chunk]
        sampled.append(
            Price(
                instrument_id=first.instrument_id,
                trade_date=last.trade_date,
                open=first.open,
                high=max(highs) if highs else last.high,
                low=min(lows) if lows else last.low,
                close=last.close,
                volume=sum(volumes),
                avg_volume_50d=last.avg_volume_50d,
            )
        )
    return sampled


def _trade_date_for_bar(price_rows: list[Price], bar_index: Any) -> Optional[date]:
    if isinstance(bar_index, int) and 0 <= bar_index < len(price_rows):
        return price_rows[bar_index].trade_date
    return None


def _close_for_bar(price_rows: list[Price], bar_index: Any) -> Optional[float]:
    if isinstance(bar_index, int) and 0 <= bar_index < len(price_rows):
        return _f(price_rows[bar_index].close)
    return None


def _append_anchor(
    anchors: list[ChartPatternAnchor],
    seen: set[tuple[date, float, Optional[str]]],
    time: Optional[date],
    value: Optional[float],
    label: Optional[str],
) -> None:
    if time is None or value is None:
        return
    key = (time, value, label)
    if key in seen:
        return
    seen.add(key)
    anchors.append(ChartPatternAnchor(time=time, value=value, label=label))


def _build_pattern_overlays(
    patterns: list[dict],
    price_rows: list[Price],
) -> list[ChartPatternOverlay]:
    overlays: list[ChartPatternOverlay] = []

    for pattern in patterns:
        detail = pattern.get("detail") or {}
        start_bar = pattern.get("start_bar")
        end_bar = pattern.get("end_bar")
        start_date = _trade_date_for_bar(price_rows, start_bar)
        end_date = _trade_date_for_bar(price_rows, end_bar)
        anchors: list[ChartPatternAnchor] = []
        seen: set[tuple[date, float, Optional[str]]] = set()

        _append_anchor(
            anchors,
            seen,
            start_date,
            _f(detail.get("left_lip_price")) or _close_for_bar(price_rows, start_bar),
            "Start",
        )

        midpoint_bar = (
            (start_bar + end_bar) // 2
            if isinstance(start_bar, int) and isinstance(end_bar, int)
            else None
        )
        _append_anchor(
            anchors,
            seen,
            _trade_date_for_bar(price_rows, midpoint_bar),
            _f(detail.get("bottom_price")),
            "Base",
        )

        _append_anchor(
            anchors,
            seen,
            end_date,
            _f(detail.get("right_lip_price")) or _close_for_bar(price_rows, end_bar),
            "End",
        )

        for key in ("low1", "low2", "low3"):
            point = detail.get(key)
            if isinstance(point, dict):
                _append_anchor(
                    anchors,
                    seen,
                    _trade_date_for_bar(price_rows, point.get("bar")),
                    _f(point.get("price")),
                    key.upper(),
                )

        peaks = detail.get("peaks")
        if isinstance(peaks, list):
            for idx, point in enumerate(peaks, start=1):
                if isinstance(point, dict):
                    _append_anchor(
                        anchors,
                        seen,
                        _trade_date_for_bar(price_rows, point.get("bar")),
                        _f(point.get("price")),
                        f"PEAK {idx}",
                    )

        for bar_key, price_key, label in (
            ("low1_bar", "low1_price", "L1"),
            ("low2_bar", "low2_price", "L2"),
            ("middle_peak_bar", "middle_peak_price", "MID"),
        ):
            _append_anchor(
                anchors,
                seen,
                _trade_date_for_bar(price_rows, detail.get(bar_key)),
                _f(detail.get(price_key)),
                label,
            )

        overlays.append(
            ChartPatternOverlay(
                pattern_type=pattern.get("pattern_type", "pattern"),
                status=pattern.get("status"),
                confidence=_f(pattern.get("confidence")) or 0.0,
                pivot_price=_f(pattern.get("pivot_price")),
                start_date=start_date,
                end_date=end_date,
                anchors=sorted(anchors, key=lambda anchor: anchor.time),
            )
        )

    return overlays


@router.get(
    "/{ticker}/chart",
    response_model=InstrumentChartResponse,
    summary="Chart payload for a ticker",
)
async def get_instrument_chart(
    ticker: str,
    market: Optional[str] = Query(None, pattern="^(US|KR)$"),
    score_date: Optional[date] = Query(None),
    interval: str = Query("1d", pattern="^(1d|1w|1m)$"),
    range_days: int = Query(350, ge=30, le=1500),
    include_indicators: bool = Query(True),
    db: AsyncSession = Depends(get_db),
) -> InstrumentChartResponse:
    instrument = await _resolve_instrument(ticker=ticker, market=market, db=db)
    reference_date = await _resolve_reference_date(
        instrument.id,
        score_date=score_date,
        db=db,
    )

    from datetime import date as date_type  # noqa: PLC0415
    _empty_date = reference_date or date_type.today()

    if reference_date is None:
        return InstrumentChartResponse(
            ticker=ticker,
            market=instrument.market,
            score_date=_empty_date,
            interval=interval,
            range_days=range_days,
            bars=[],
            rs_line=[],
            patterns=[],
            benchmark_note="Price data not yet ingested. Run price ingestion to see the chart.",
        )

    price_q = await db.execute(
        select(Price)
        .where(
            Price.instrument_id == instrument.id,
            Price.trade_date <= reference_date,
        )
        .order_by(desc(Price.trade_date))
        .limit(max(range_days * 2, 420))
    )
    price_rows = list(reversed(price_q.scalars().all()))

    valid_rows = [
        row
        for row in price_rows
        if row.open is not None
        and row.high is not None
        and row.low is not None
        and row.close is not None
    ]
    if not valid_rows:
        return InstrumentChartResponse(
            ticker=ticker,
            market=instrument.market,
            score_date=_empty_date,
            interval=interval,
            range_days=range_days,
            bars=[],
            rs_line=[],
            patterns=[],
            benchmark_note="Price data not yet ingested. Run price ingestion to see the chart.",
        )

    stride = {"1d": 1, "1w": 5, "1m": 21}[interval]
    sampled_rows = _resample_price_rows(valid_rows[-range_days:], stride)
    closes = [float(row.close) for row in sampled_rows]
    sma_50 = _rolling_sma(closes, 50) if include_indicators else [None] * len(sampled_rows)
    sma_150 = _rolling_sma(closes, 150) if include_indicators else [None] * len(sampled_rows)
    sma_200 = _rolling_sma(closes, 200) if include_indicators else [None] * len(sampled_rows)

    ss_q = await db.execute(
        select(StrategyScore).where(
            StrategyScore.instrument_id == instrument.id,
            StrategyScore.score_date == reference_date,
        )
    )
    ss = ss_q.scalars().first()
    pattern_overlays = (
        _build_pattern_overlays(ss.patterns or [], sampled_rows)
        if ss and interval == "1d"
        else []
    )

    benchmark_ticker = BENCHMARK_TICKER.get(instrument.market)
    benchmark_available = False
    benchmark_note: Optional[str] = None
    rs_line: list[ChartLinePoint] = []

    if benchmark_ticker:
        benchmark_inst_q = await db.execute(
            select(Instrument.id).where(
                func.upper(Instrument.ticker) == benchmark_ticker.upper(),
                Instrument.market == instrument.market,
            )
        )
        benchmark_id = benchmark_inst_q.scalar_one_or_none()

        if benchmark_id is None:
            benchmark_note = f"Benchmark ticker '{benchmark_ticker}' is not loaded in the instrument universe."
        else:
            benchmark_q = await db.execute(
                select(Price.trade_date, Price.close)
                .where(
                    Price.instrument_id == benchmark_id,
                    Price.trade_date <= reference_date,
                )
                .order_by(desc(Price.trade_date))
                .limit(max(range_days * 2, 420))
            )
            benchmark_rows = list(reversed(benchmark_q.all()))
            benchmark_by_date = {
                trade_date: float(close)
                for trade_date, close in benchmark_rows
                if close is not None
            }

            first_ratio: Optional[float] = None
            for row in sampled_rows:
                benchmark_close = benchmark_by_date.get(row.trade_date)
                if benchmark_close is None or benchmark_close <= 0:
                    continue

                raw_ratio = float(row.close) / benchmark_close
                if first_ratio is None:
                    first_ratio = raw_ratio
                rs_line.append(
                    ChartLinePoint(
                        time=row.trade_date,
                        value=(raw_ratio / first_ratio) * 100.0 if first_ratio else 100.0,
                    )
                )

            benchmark_available = len(rs_line) > 0
            if not benchmark_available:
                benchmark_note = (
                    f"Benchmark prices for '{benchmark_ticker}' are not available for the chart range."
                )
    else:
        benchmark_note = "No benchmark mapping is configured for this market."

    coverage_map = await build_coverage_map(db, [instrument], score_date=reference_date)
    coverage = coverage_map[instrument.id]

    return InstrumentChartResponse(
        ticker=instrument.ticker,
        market=instrument.market,
        score_date=reference_date,
        interval=interval,
        range_days=range_days,
        benchmark_ticker=benchmark_ticker,
        benchmark_available=benchmark_available,
        benchmark_note=benchmark_note,
        freshness=coverage.freshness,
        delay_minutes=coverage.delay_minutes,
        bars=[
            ChartPriceBar(
                time=row.trade_date,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=int(row.volume or 0),
                avg_volume_50d=_i(row.avg_volume_50d),
                sma_50=sma_50[idx],
                sma_150=sma_150[idx],
                sma_200=sma_200[idx],
            )
            for idx, row in enumerate(sampled_rows)
        ],
        rs_line=rs_line,
        patterns=pattern_overlays,
    )


@router.get("/{ticker}", response_model=InstrumentDetailResponse, summary="Full scoring breakdown for a ticker")
async def get_instrument(
    ticker:     str,
    market:     Optional[str]  = Query(None, pattern="^(US|KR)$"),
    score_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> InstrumentDetailResponse:
    """
    Return complete breakdown for one instrument:
    - Consensus conviction + final_score
    - All 5 strategy scores with sub-criteria
    - Technical composite with patterns and indicators
    """
    instrument = await _resolve_instrument(ticker=ticker, market=market, db=db)
    coverage_map = await build_coverage_map(db, [instrument], score_date=score_date)
    coverage = coverage_map[instrument.id]
    reference_date = await _resolve_reference_date(
        instrument.id,
        score_date=score_date or coverage.freshness.get("ranked_as_of"),
        db=db,
    )
    if reference_date is None:
        reference_date = coverage.freshness.get("price_as_of") or date.today()

    # Fetch strategy_scores row
    ss_q = await db.execute(
        select(StrategyScore).where(
            StrategyScore.instrument_id == instrument.id,
            StrategyScore.score_date == reference_date,
        )
    )
    ss = ss_q.scalars().first()

    # Fetch consensus_scores row
    cs_q = await db.execute(
        select(ConsensusScore).where(
            ConsensusScore.instrument_id == instrument.id,
            ConsensusScore.score_date == reference_date,
        )
    )
    cs = cs_q.scalars().first()

    score_history_rows: list[tuple[date, Optional[float], Optional[float], Optional[float]]] = []
    if cs is not None:
        score_history_q = await db.execute(
            select(
                ConsensusScore.score_date,
                ConsensusScore.final_score,
                ConsensusScore.consensus_composite,
                ConsensusScore.technical_composite,
            )
            .where(
                ConsensusScore.instrument_id == instrument.id,
                ConsensusScore.score_date <= reference_date,
            )
            .order_by(desc(ConsensusScore.score_date))
            .limit(30)
        )
        score_history_rows = list(reversed(score_history_q.all()))

    stage_history_rows: list[tuple[date, Optional[str], Optional[float]]] = []
    if ss is not None:
        stage_history_q = await db.execute(
            select(
                StrategyScore.score_date,
                StrategyScore.weinstein_stage,
                StrategyScore.weinstein_score,
            )
            .where(
                StrategyScore.instrument_id == instrument.id,
                StrategyScore.score_date <= reference_date,
            )
            .order_by(desc(StrategyScore.score_date))
            .limit(12)
        )
        stage_history_rows = list(reversed(stage_history_q.all()))

    # Build response
    return InstrumentDetailResponse(
        instrument_id        = instrument.id,
        ticker               = instrument.ticker,
        name                 = instrument.name or "",
        name_kr              = instrument.name_kr,
        market               = instrument.market,
        asset_type           = instrument.asset_type,
        score_date           = reference_date,
        exchange             = instrument.exchange,
        listing_status       = instrument.listing_status,
        sector               = instrument.sector,
        industry_group       = instrument.industry_group,
        shares_outstanding   = _i(instrument.shares_outstanding),
        float_shares         = _i(instrument.float_shares),
        is_test_issue        = instrument.is_test_issue,
        coverage_state       = coverage.coverage_state,
        ranking_eligibility  = coverage.ranking_eligibility,
        freshness            = coverage.freshness,
        delay_minutes        = coverage.delay_minutes,
        rank_model_version   = coverage.rank_model_version,

        conviction_level     = cs.conviction_level   if cs else "UNRANKED",
        final_score          = _f(cs.final_score)    if cs else None,
        consensus_composite  = _f(cs.consensus_composite) if cs else None,
        strategy_pass_count  = cs.strategy_pass_count if cs else None,
        weinstein_stage      = ss.weinstein_stage if ss else None,
        score_breakdown      = cs.score_breakdown     if cs else None,
        factor_breakdown     = (cs.score_breakdown or {}).get("factor_core") if cs else None,
        score_history        = [
            ScoreHistoryPoint(
                date                = hist_date,
                final_score         = _f(final_score),
                consensus_composite = _f(consensus_composite),
                technical_composite = _f(technical_composite),
            )
            for hist_date, final_score, consensus_composite, technical_composite in score_history_rows
        ],
        weinstein_stage_history = [
            WeinsteinStageHistoryPoint(
                date  = hist_date,
                stage = stage,
                score = _f(stage_score),
            )
            for hist_date, stage, stage_score in stage_history_rows
        ],
        computed_at          = cs.computed_at         if cs else None,

        canslim = CANSLIMDetail(
            score = _f(ss.canslim_score) if ss else None,
            c     = _f(ss.canslim_c)     if ss else None,
            a     = _f(ss.canslim_a)     if ss else None,
            n     = _f(ss.canslim_n)     if ss else None,
            s     = _f(ss.canslim_s)     if ss else None,
            l     = _f(ss.canslim_l)     if ss else None,
            i     = _f(ss.canslim_i)     if ss else None,
            raw   = ss.canslim_detail    if ss else None,
        ),
        piotroski = PiotroskiDetail(
            score  = _f(ss.piotroski_score)  if ss else None,
            f_raw  = ss.piotroski_f_raw       if ss else None,
            criteria = ss.piotroski_detail    if ss else None,
        ),
        minervini = MinerviniDetail(
            score          = _f(ss.minervini_score)          if ss else None,
            criteria_count = ss.minervini_criteria_count      if ss else None,
            criteria       = ss.minervini_detail             if ss else None,
        ),
        weinstein = WeinsteinDetail(
            score  = _f(ss.weinstein_score) if ss else None,
            stage  = ss.weinstein_stage      if ss else None,
            detail = ss.weinstein_detail     if ss else None,
        ),
        technical = TechnicalDetail(
            composite        = _f(ss.technical_composite) if ss else None,
            rs_rating        = _f(ss.rs_rating)            if ss else None,
            ad_rating        = ss.ad_rating                if ss else None,
            bb_squeeze       = ss.bb_squeeze               if ss else None,
            rs_line_new_high = ss.rs_line_new_high         if ss else None,
            patterns         = ss.patterns                 if ss and ss.patterns else [],
            detail           = ss.technical_detail         if ss else None,
        ),
    )
