from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select

from app.models.fundamental import FundamentalAnnual, FundamentalQuarterly
from app.models.instrument import Instrument
from app.models.institutional import InstitutionalOwnership
from app.models.market_regime import MarketRegime
from app.models.price import Price

PRICE_LOOKBACK_DAYS = 550


def _float(value: Optional[Decimal | float | int]) -> Optional[float]:
    if value is None:
        return None
    return float(value)


@dataclass(frozen=True)
class InstrumentMeta:
    id: int
    ticker: str
    market: str
    exchange: Optional[str]
    sector: Optional[str]
    shares_outstanding: Optional[float]
    float_shares: Optional[float]
    is_chaebol_cross: bool


@dataclass(frozen=True)
class PriceBar:
    trade_date: date
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[float]
    avg_volume_50d: Optional[float]


@dataclass(frozen=True)
class QuarterlyReport:
    fiscal_year: int
    fiscal_quarter: int
    report_date: date
    eps: Optional[float]
    eps_yoy_growth: Optional[float]
    revenue_yoy_growth: Optional[float]


@dataclass(frozen=True)
class AnnualReport:
    fiscal_year: int
    report_date: date
    revenue: Optional[float]
    gross_profit: Optional[float]
    net_income: Optional[float]
    eps: Optional[float]
    total_assets: Optional[float]
    current_assets: Optional[float]
    current_liabilities: Optional[float]
    long_term_debt: Optional[float]
    shares_outstanding_annual: Optional[float]
    operating_cash_flow: Optional[float]


@dataclass(frozen=True)
class InstitutionalSnapshot:
    report_date: date
    num_institutional_owners: Optional[int]
    institutional_pct: Optional[float]
    top_fund_quality_score: Optional[float]
    qoq_owner_change: Optional[int]
    is_buyback_active: Optional[bool]
    foreign_ownership_pct: Optional[float]
    foreign_net_buy_30d: Optional[float]
    institutional_net_buy_30d: Optional[float]


@dataclass(frozen=True)
class RegimeSnapshot:
    effective_date: date
    state: str


@dataclass(frozen=True)
class InstrumentScoringContext:
    instrument: InstrumentMeta
    prices: tuple[PriceBar, ...]
    quarterlies: tuple[QuarterlyReport, ...]
    annuals: tuple[AnnualReport, ...]
    institutional: Optional[InstitutionalSnapshot]


@dataclass(frozen=True)
class BatchScoringContext:
    instruments: dict[int, InstrumentScoringContext]
    regimes_by_market: dict[str, Optional[RegimeSnapshot]]


def _group_take_latest_desc(rows, key_fn, limit: int):
    grouped: dict[int, list] = {}
    for row in rows:
        key = key_fn(row)
        bucket = grouped.setdefault(key, [])
        if len(bucket) < limit:
            bucket.append(row)
    return grouped


async def load_batch_scoring_context(
    db,
    *,
    instrument_ids: list[int],
    score_date: date,
) -> BatchScoringContext:
    """
    Load the shared scoring context for a chunk of instruments using one session.
    All series are normalized to oldest-first tuples before leaving this loader.
    """
    if not instrument_ids:
        return BatchScoringContext(instruments={}, regimes_by_market={})

    instrument_rows = (
        await db.execute(
            select(Instrument).where(Instrument.id.in_(instrument_ids))
        )
    ).scalars().all()
    instruments_by_id = {
        row.id: InstrumentMeta(
            id=row.id,
            ticker=row.ticker,
            market=row.market,
            exchange=row.exchange,
            sector=row.sector,
            shares_outstanding=_float(row.shares_outstanding),
            float_shares=_float(row.float_shares),
            is_chaebol_cross=bool(row.is_chaebol_cross),
        )
        for row in instrument_rows
    }
    markets = sorted({row.market for row in instrument_rows})

    price_rows = (
        await db.execute(
            select(Price)
            .where(
                Price.instrument_id.in_(instrument_ids),
                Price.trade_date <= score_date,
                Price.trade_date >= score_date - timedelta(days=PRICE_LOOKBACK_DAYS),
            )
            .order_by(Price.instrument_id.asc(), Price.trade_date.desc())
        )
    ).scalars().all()
    grouped_prices_desc = _group_take_latest_desc(price_rows, lambda row: row.instrument_id, 350)

    quarterly_rows = (
        await db.execute(
            select(FundamentalQuarterly)
            .where(
                FundamentalQuarterly.instrument_id.in_(instrument_ids),
                FundamentalQuarterly.report_date <= score_date,
            )
            .order_by(
                FundamentalQuarterly.instrument_id.asc(),
                FundamentalQuarterly.report_date.desc(),
            )
        )
    ).scalars().all()
    grouped_quarterlies_desc = _group_take_latest_desc(
        quarterly_rows,
        lambda row: row.instrument_id,
        8,
    )

    annual_rows = (
        await db.execute(
            select(FundamentalAnnual)
            .where(
                FundamentalAnnual.instrument_id.in_(instrument_ids),
                FundamentalAnnual.report_date <= score_date,
            )
            .order_by(
                FundamentalAnnual.instrument_id.asc(),
                FundamentalAnnual.report_date.desc(),
            )
        )
    ).scalars().all()
    grouped_annuals_desc = _group_take_latest_desc(
        annual_rows,
        lambda row: row.instrument_id,
        6,
    )

    institutional_rows = (
        await db.execute(
            select(InstitutionalOwnership)
            .where(
                InstitutionalOwnership.instrument_id.in_(instrument_ids),
                InstitutionalOwnership.report_date <= score_date,
            )
            .order_by(
                InstitutionalOwnership.instrument_id.asc(),
                InstitutionalOwnership.report_date.desc(),
            )
        )
    ).scalars().all()
    grouped_institutional_desc = _group_take_latest_desc(
        institutional_rows,
        lambda row: row.instrument_id,
        1,
    )

    regime_rows = (
        await db.execute(
            select(MarketRegime)
            .where(
                MarketRegime.market.in_(markets),
                MarketRegime.effective_date <= score_date,
            )
            .order_by(MarketRegime.market.asc(), MarketRegime.effective_date.desc())
        )
    ).scalars().all()
    grouped_regimes_desc = _group_take_latest_desc(regime_rows, lambda row: row.market, 1)

    regimes_by_market = {
        market_name: (
            RegimeSnapshot(
                effective_date=rows[0].effective_date,
                state=rows[0].state,
            )
            if rows else None
        )
        for market_name, rows in grouped_regimes_desc.items()
    }

    contexts: dict[int, InstrumentScoringContext] = {}
    for instrument_id in instrument_ids:
        instrument = instruments_by_id.get(instrument_id)
        if instrument is None:
            continue

        prices = tuple(
            PriceBar(
                trade_date=row.trade_date,
                open=_float(row.open),
                high=_float(row.high),
                low=_float(row.low),
                close=_float(row.close),
                volume=_float(row.volume),
                avg_volume_50d=_float(row.avg_volume_50d),
            )
            for row in reversed(grouped_prices_desc.get(instrument_id, []))
        )
        quarterlies = tuple(
            QuarterlyReport(
                fiscal_year=row.fiscal_year,
                fiscal_quarter=row.fiscal_quarter,
                report_date=row.report_date,
                eps=_float(row.eps),
                eps_yoy_growth=_float(row.eps_yoy_growth),
                revenue_yoy_growth=_float(row.revenue_yoy_growth),
            )
            for row in reversed(grouped_quarterlies_desc.get(instrument_id, []))
        )
        annuals = tuple(
            AnnualReport(
                fiscal_year=row.fiscal_year,
                report_date=row.report_date,
                revenue=_float(row.revenue),
                gross_profit=_float(row.gross_profit),
                net_income=_float(row.net_income),
                eps=_float(row.eps),
                total_assets=_float(row.total_assets),
                current_assets=_float(row.current_assets),
                current_liabilities=_float(row.current_liabilities),
                long_term_debt=_float(row.long_term_debt),
                shares_outstanding_annual=_float(row.shares_outstanding_annual),
                operating_cash_flow=_float(row.operating_cash_flow),
            )
            for row in reversed(grouped_annuals_desc.get(instrument_id, []))
        )
        institutional_rows = grouped_institutional_desc.get(instrument_id, [])
        institutional = None
        if institutional_rows:
            latest = institutional_rows[0]
            institutional = InstitutionalSnapshot(
                report_date=latest.report_date,
                num_institutional_owners=latest.num_institutional_owners,
                institutional_pct=_float(latest.institutional_pct),
                top_fund_quality_score=_float(latest.top_fund_quality_score),
                qoq_owner_change=latest.qoq_owner_change,
                is_buyback_active=latest.is_buyback_active,
                foreign_ownership_pct=_float(latest.foreign_ownership_pct),
                foreign_net_buy_30d=_float(latest.foreign_net_buy_30d),
                institutional_net_buy_30d=_float(latest.institutional_net_buy_30d),
            )

        contexts[instrument_id] = InstrumentScoringContext(
            instrument=instrument,
            prices=prices,
            quarterlies=quarterlies,
            annuals=annuals,
            institutional=institutional,
        )

    return BatchScoringContext(
        instruments=contexts,
        regimes_by_market=regimes_by_market,
    )


async def load_instrument_scoring_context(
    db,
    *,
    instrument_id: int,
    score_date: date,
) -> Optional[InstrumentScoringContext]:
    batch = await load_batch_scoring_context(
        db,
        instrument_ids=[instrument_id],
        score_date=score_date,
    )
    return batch.instruments.get(instrument_id)
