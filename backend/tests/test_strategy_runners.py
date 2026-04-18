from contextlib import asynccontextmanager
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base
from app.models.consensus_score import ConsensusScore
from app.models.fundamental import FundamentalAnnual, FundamentalQuarterly
from app.models.instrument import Instrument
from app.models.institutional import InstitutionalOwnership
from app.models.market_regime import MarketRegime
from app.models.price import Price
from app.models.strategy_score import StrategyScore
from app.services.strategies.canslim import engine as canslim_engine
from app.services.strategies import consensus as consensus_engine
from app.services.strategies.dual_momentum import engine as dual_momentum_engine
from app.services.strategies.minervini import engine as minervini_engine
from app.services.strategies.piotroski import engine as piotroski_engine
from app.services.strategies.weinstein import engine as weinstein_engine

# Use the real app schema — models now have explicit schema="consensus_app" so
# search_path / schema_translate_map are no longer needed.
TEST_SCHEMA = settings.postgres_schema  # "consensus_app"


def _truncate_all_tables_sql() -> str | None:
    table_names = [
        f'"{table.schema}"."{table.name}"' if table.schema else f'"{table.name}"'
        for table in reversed(Base.metadata.sorted_tables)
    ]
    if not table_names:
        return None
    return f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE"


@pytest.fixture
async def strategy_db_session():
    async_engine = create_async_engine(
        settings.database_url,
        echo=False,
        connect_args=settings.asyncpg_connect_args,
    )
    test_session_local = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_session_local() as session:
        truncate_sql = _truncate_all_tables_sql()
        if truncate_sql:
            await session.execute(text(truncate_sql))
            await session.commit()
        yield session
        if truncate_sql:
            await session.execute(text(truncate_sql))
            await session.commit()

    await async_engine.dispose()


def _patch_async_session(monkeypatch, module):
    test_engine = create_async_engine(
        settings.database_url,
        echo=False,
        connect_args=settings.asyncpg_connect_args,
    )
    test_session_local = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(module, "AsyncSessionLocal", test_session_local)
    return test_engine


def _build_linear_series(start: float, step: float, length: int = 260) -> list[float]:
    return [start + step * idx for idx in range(length)]


def _build_volume_series(base: int, surge: int, length: int = 260) -> list[int]:
    volumes = [base] * length
    for idx in range(length - 8, length):
        volumes[idx] = surge
    return volumes


def _seed_prices(
    db_session,
    instrument_id: int,
    start_date: date,
    closes: list[float],
    volumes: list[int],
):
    for idx, (close, volume) in enumerate(zip(closes, volumes)):
        db_session.add(
            Price(
                instrument_id=instrument_id,
                trade_date=start_date + timedelta(days=idx),
                open=close - 1,
                high=close + 2,
                low=close - 2,
                close=close,
                volume=volume,
                avg_volume_50d=max(1, int(volume * 0.7)),
            )
        )


def _seed_quarterlies(db_session, instrument_id: int, data_source: str, eps_values: list[float]):
    rows = [
        (2025, 1, date(2025, 3, 31), 1_000, 50, eps_values[0], 0.18, 0.16),
        (2025, 2, date(2025, 6, 30), 1_100, 60, eps_values[1], 0.22, 0.19),
        (2025, 3, date(2025, 9, 30), 1_250, 80, eps_values[2], 0.28, 0.22),
        (2025, 4, date(2025, 12, 31), 1_450, 110, eps_values[3], 0.35, 0.27),
        (2026, 1, date(2026, 3, 31), 1_850, 170, eps_values[4], 0.65, 0.35),
    ]
    for fiscal_year, fiscal_quarter, report_date, revenue, net_income, eps, eps_yoy, revenue_yoy in rows:
        db_session.add(
            FundamentalQuarterly(
                instrument_id=instrument_id,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
                report_date=report_date,
                revenue=revenue,
                net_income=net_income,
                eps=eps,
                eps_diluted=eps,
                eps_yoy_growth=eps_yoy,
                revenue_yoy_growth=revenue_yoy,
                data_source=data_source,
            )
        )


def _seed_annuals(
    db_session,
    instrument_id: int,
    data_source: str,
    eps_values: list[float],
):
    rows = [
        (2022, date(2023, 2, 15), 650, 250, 60, eps_values[0], 800, 220, 120, 260, 100, 75),
        (2023, date(2024, 2, 15), 760, 310, 85, eps_values[1], 820, 250, 115, 230, 98, 95),
        (2024, date(2025, 2, 15), 880, 390, 115, eps_values[2], 840, 280, 110, 200, 95, 130),
        (2025, date(2026, 2, 15), 1_020, 510, 155, eps_values[3], 860, 320, 105, 170, 92, 185),
    ]
    for fiscal_year, report_date, revenue, gross_profit, net_income, eps, total_assets, current_assets, current_liabilities, long_term_debt, shares, cfo in rows:
        db_session.add(
            FundamentalAnnual(
                instrument_id=instrument_id,
                fiscal_year=fiscal_year,
                report_date=report_date,
                revenue=revenue,
                gross_profit=gross_profit,
                net_income=net_income,
                eps=eps,
                eps_diluted=eps,
                eps_yoy_growth=0.2,
                total_assets=total_assets,
                current_assets=current_assets,
                current_liabilities=current_liabilities,
                long_term_debt=long_term_debt,
                shares_outstanding_annual=shares,
                operating_cash_flow=cfo,
                data_source=data_source,
            )
        )


async def _seed_full_strategy_fixture(db_session):
    score_date = date(2026, 4, 13)
    start_date = score_date - timedelta(days=259)

    us_stock = Instrument(
        ticker="AAPL",
        name="Apple",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        sector="Technology",
        industry_group="Consumer Electronics",
        shares_outstanding=1_000,
        float_shares=420,
        is_active=True,
    )
    kr_stock = Instrument(
        ticker="005930",
        name="Samsung Electronics",
        name_kr="삼성전자",
        market="KR",
        exchange="KOSPI",
        asset_type="stock",
        sector="Semiconductors",
        industry_group="Semiconductors",
        shares_outstanding=1_000,
        float_shares=260,
        is_active=True,
        is_chaebol_cross=True,
    )
    spy = Instrument(
        ticker="SPY",
        name="SPDR S&P 500 ETF",
        market="US",
        exchange="NYSE",
        asset_type="etf",
        is_active=True,
    )
    kodex = Instrument(
        ticker="069500",
        name="KODEX 200",
        market="KR",
        exchange="KOSPI",
        asset_type="etf",
        is_active=True,
    )
    db_session.add_all([us_stock, kr_stock, spy, kodex])
    await db_session.flush()

    _seed_prices(
        db_session,
        us_stock.id,
        start_date,
        _build_linear_series(100.0, 0.55),
        _build_volume_series(1_200_000, 2_800_000),
    )
    _seed_prices(
        db_session,
        kr_stock.id,
        start_date,
        _build_linear_series(70.0, 0.32),
        _build_volume_series(900_000, 2_200_000),
    )
    _seed_prices(
        db_session,
        spy.id,
        start_date,
        _build_linear_series(300.0, 0.22),
        _build_volume_series(5_000_000, 5_800_000),
    )
    _seed_prices(
        db_session,
        kodex.id,
        start_date,
        _build_linear_series(100.0, 0.14),
        _build_volume_series(2_500_000, 2_900_000),
    )

    _seed_quarterlies(db_session, us_stock.id, "EDGAR", [0.50, 0.65, 0.82, 1.05, 1.70])
    _seed_quarterlies(db_session, kr_stock.id, "DART", [0.40, 0.55, 0.72, 0.90, 1.45])
    _seed_annuals(db_session, us_stock.id, "EDGAR", [1.0, 1.35, 1.8, 2.5])
    _seed_annuals(db_session, kr_stock.id, "DART", [0.9, 1.15, 1.45, 1.95])

    db_session.add_all(
        [
            InstitutionalOwnership(
                instrument_id=us_stock.id,
                report_date=score_date,
                num_institutional_owners=180,
                institutional_pct=0.45,
                top_fund_quality_score=78,
                qoq_owner_change=12,
                is_buyback_active=True,
                data_source="13F",
            ),
            InstitutionalOwnership(
                instrument_id=kr_stock.id,
                report_date=score_date,
                foreign_ownership_pct=0.33,
                foreign_net_buy_30d=200_000,
                institutional_net_buy_30d=120_000,
                individual_net_buy_30d=-320_000,
                data_source="KIS",
            ),
            MarketRegime(
                market="US",
                effective_date=score_date,
                state="CONFIRMED_UPTREND",
                prior_state="UPTREND_UNDER_PRESSURE",
                trigger_reason="Follow-through day",
                distribution_day_count=2,
                follow_through_day=True,
            ),
            MarketRegime(
                market="KR",
                effective_date=score_date,
                state="UPTREND_UNDER_PRESSURE",
                prior_state="CONFIRMED_UPTREND",
                trigger_reason="Distribution cluster",
                distribution_day_count=6,
                follow_through_day=False,
            ),
            StrategyScore(
                instrument_id=us_stock.id,
                score_date=score_date,
                rs_rating=88.0,
                rs_line_new_high=True,
                patterns=[{"pattern_type": "cup_with_handle", "confidence": 0.82}],
                technical_composite=72.0,
            ),
        ]
    )

    await db_session.commit()
    return {
        "score_date": score_date,
        "us_stock": us_stock,
        "kr_stock": kr_stock,
        "spy": spy,
        "kodex": kodex,
    }


@pytest.mark.asyncio
async def test_build_market_rs_lookup_and_minervini_fallback_rs(strategy_db_session):
    fixture = await _seed_full_strategy_fixture(strategy_db_session)

    rs_lookup = await canslim_engine.build_market_rs_lookup(strategy_db_session, "US", fixture["score_date"])
    assert fixture["us_stock"].id in rs_lookup
    assert fixture["spy"].id in rs_lookup
    assert rs_lookup[fixture["us_stock"].id] > rs_lookup[fixture["spy"].id]

    scored = await minervini_engine.score_instrument(
        fixture["us_stock"].id,
        fixture["score_date"],
        strategy_db_session,
        rs_lookup=None,
    )

    assert scored is not None
    assert scored["minervini_score"] > 0
    assert scored["minervini_detail"]["T8_rs_rating_ge_70"]["pass"] is True


@pytest.mark.asyncio
async def test_canslim_runner_scores_and_upserts_us_and_kr_rows(strategy_db_session, monkeypatch):
    fixture = await _seed_full_strategy_fixture(strategy_db_session)
    runner_engine = _patch_async_session(monkeypatch, canslim_engine)
    try:
        results = await canslim_engine.run_canslim_scoring(
            score_date=fixture["score_date"],
            instrument_ids=[fixture["us_stock"].id, fixture["kr_stock"].id],
        )
    finally:
        await runner_engine.dispose()

    assert len(results) == 2

    us_row = (
        await strategy_db_session.execute(
            select(StrategyScore).where(
                StrategyScore.instrument_id == fixture["us_stock"].id,
                StrategyScore.score_date == fixture["score_date"],
            )
        )
    ).scalars().one()
    kr_row = (
        await strategy_db_session.execute(
            select(StrategyScore).where(
                StrategyScore.instrument_id == fixture["kr_stock"].id,
                StrategyScore.score_date == fixture["score_date"],
            )
        )
    ).scalars().one()

    assert us_row.canslim_score is not None
    assert us_row.canslim_detail["M"]["state"] == "CONFIRMED_UPTREND"
    assert us_row.patterns[0]["pattern_type"] == "cup_with_handle"
    assert kr_row.canslim_score is not None
    assert kr_row.market_regime == "UPTREND_UNDER_PRESSURE"
    assert float(kr_row.canslim_l) >= 0


@pytest.mark.asyncio
async def test_piotroski_runner_upserts_existing_and_new_rows(strategy_db_session, monkeypatch):
    fixture = await _seed_full_strategy_fixture(strategy_db_session)
    runner_engine = _patch_async_session(monkeypatch, piotroski_engine)
    try:
        results = await piotroski_engine.run_piotroski_scoring(
            score_date=fixture["score_date"],
            instrument_ids=[fixture["us_stock"].id, fixture["kr_stock"].id],
        )
    finally:
        await runner_engine.dispose()

    assert len(results) == 2

    us_row = (
        await strategy_db_session.execute(
            select(StrategyScore).where(
                StrategyScore.instrument_id == fixture["us_stock"].id,
                StrategyScore.score_date == fixture["score_date"],
            )
        )
    ).scalars().one()
    kr_row = (
        await strategy_db_session.execute(
            select(StrategyScore).where(
                StrategyScore.instrument_id == fixture["kr_stock"].id,
                StrategyScore.score_date == fixture["score_date"],
            )
        )
    ).scalars().one()

    assert us_row.piotroski_f_raw == 9
    assert float(us_row.piotroski_score) == 100.0
    assert float(kr_row.piotroski_score) > 0


@pytest.mark.asyncio
async def test_weinstein_runner_upserts_existing_and_new_rows(strategy_db_session, monkeypatch):
    fixture = await _seed_full_strategy_fixture(strategy_db_session)
    runner_engine = _patch_async_session(monkeypatch, weinstein_engine)
    try:
        results = await weinstein_engine.run_weinstein_scoring(
            score_date=fixture["score_date"],
            instrument_ids=[fixture["us_stock"].id, fixture["kr_stock"].id],
        )
    finally:
        await runner_engine.dispose()

    assert len(results) == 2

    us_row = (
        await strategy_db_session.execute(
            select(StrategyScore).where(
                StrategyScore.instrument_id == fixture["us_stock"].id,
                StrategyScore.score_date == fixture["score_date"],
            )
        )
    ).scalars().one()
    kr_row = (
        await strategy_db_session.execute(
            select(StrategyScore).where(
                StrategyScore.instrument_id == fixture["kr_stock"].id,
                StrategyScore.score_date == fixture["score_date"],
            )
        )
    ).scalars().one()

    assert us_row.weinstein_stage == "2_mid"
    assert float(us_row.weinstein_score) == 85.0
    assert kr_row.weinstein_stage is not None


@pytest.mark.asyncio
async def test_dual_momentum_fetchers_and_runner_upsert(strategy_db_session, monkeypatch):
    fixture = await _seed_full_strategy_fixture(strategy_db_session)
    runner_engine = _patch_async_session(monkeypatch, dual_momentum_engine)

    class FakeFredClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            if "fredgraph" in url:
                return SimpleNamespace(text="DATE,DGS3MO\n2026-04-10,5.11\n2026-04-11,5.09")
            return SimpleNamespace(
                json=lambda: {"StatisticSearch": {"row": [{"DATA_VALUE": "3.25"}]}}
            )

    monkeypatch.setattr(dual_momentum_engine.httpx, "AsyncClient", FakeFredClient)

    assert await dual_momentum_engine.fetch_us_risk_free_rate() == pytest.approx(0.0509, abs=1e-4)
    assert await dual_momentum_engine.fetch_kr_risk_free_rate() == pytest.approx(0.0325, abs=1e-4)

    async def fake_us_rate():
        return 0.05

    async def fake_kr_rate():
        return 0.0325

    monkeypatch.setattr(dual_momentum_engine, "fetch_us_risk_free_rate", fake_us_rate)
    monkeypatch.setattr(dual_momentum_engine, "fetch_kr_risk_free_rate", fake_kr_rate)

    try:
        results = await dual_momentum_engine.run_dual_momentum_scoring(
            score_date=fixture["score_date"],
            instrument_ids=[fixture["us_stock"].id, fixture["kr_stock"].id],
        )
    finally:
        await runner_engine.dispose()

    assert len(results) == 2

    us_row = (
        await strategy_db_session.execute(
            select(StrategyScore).where(
                StrategyScore.instrument_id == fixture["us_stock"].id,
                StrategyScore.score_date == fixture["score_date"],
            )
        )
    ).scalars().one()
    assert float(us_row.dual_mom_score) > 0
    assert us_row.dual_mom_abs is True


@pytest.mark.asyncio
async def test_consensus_runner_upserts_existing_and_new_rows(strategy_db_session, monkeypatch):
    score_date = date(2026, 4, 13)
    us_stock = Instrument(
        ticker="AAPL",
        name="Apple",
        market="US",
        exchange="NASDAQ",
        asset_type="stock",
        is_active=True,
    )
    kr_stock = Instrument(
        ticker="005930",
        name="Samsung Electronics",
        market="KR",
        exchange="KOSPI",
        asset_type="stock",
        is_active=True,
    )
    strategy_db_session.add_all([us_stock, kr_stock])
    await strategy_db_session.flush()

    strategy_db_session.add_all(
        [
            StrategyScore(
                instrument_id=us_stock.id,
                score_date=score_date,
                canslim_score=90.0,
                piotroski_score=85.0,
                minervini_score=88.0,
                weinstein_score=82.0,
                dual_mom_score=75.0,
                technical_composite=80.0,
            ),
            StrategyScore(
                instrument_id=kr_stock.id,
                score_date=score_date,
                canslim_score=72.0,
                piotroski_score=78.0,
                minervini_score=70.0,
                weinstein_score=68.0,
                dual_mom_score=74.0,
                technical_composite=65.0,
            ),
            MarketRegime(
                market="US",
                effective_date=score_date,
                state="MARKET_IN_CORRECTION",
                prior_state="CONFIRMED_UPTREND",
                trigger_reason="Distribution breach",
                distribution_day_count=8,
                follow_through_day=False,
            ),
            MarketRegime(
                market="KR",
                effective_date=score_date,
                state="CONFIRMED_UPTREND",
                prior_state="UPTREND_UNDER_PRESSURE",
                trigger_reason="Recovery",
                distribution_day_count=2,
                follow_through_day=True,
            ),
            ConsensusScore(
                instrument_id=us_stock.id,
                score_date=score_date,
                conviction_level="BRONZE",
                final_score=40.0,
                consensus_composite=38.0,
                technical_composite=45.0,
                strategy_pass_count=1,
                regime_warning=False,
            ),
        ]
    )
    await strategy_db_session.commit()

    runner_engine = _patch_async_session(monkeypatch, consensus_engine)

    try:
        results = await consensus_engine.run_consensus_scoring(
            score_date=score_date,
            instrument_ids=[us_stock.id, kr_stock.id],
        )
    finally:
        await runner_engine.dispose()

    assert len(results) == 2

    us_row = (
        await strategy_db_session.execute(
            select(ConsensusScore).where(
                ConsensusScore.instrument_id == us_stock.id,
                ConsensusScore.score_date == score_date,
            )
        )
    ).scalars().one()
    kr_row = (
        await strategy_db_session.execute(
            select(ConsensusScore).where(
                ConsensusScore.instrument_id == kr_stock.id,
                ConsensusScore.score_date == score_date,
            )
        )
    ).scalars().one()

    assert us_row.conviction_level == "SILVER"
    assert us_row.regime_warning is True
    assert kr_row.conviction_level in {"GOLD", "SILVER", "BRONZE", "DIAMOND"}
    assert float(kr_row.final_score) > 0


@pytest.mark.asyncio
async def test_fetch_kr_risk_free_rate_falls_back_on_error(monkeypatch):
    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            raise RuntimeError("network down")

    monkeypatch.setattr(dual_momentum_engine.httpx, "AsyncClient", FailingClient)

    assert await dual_momentum_engine.fetch_kr_risk_free_rate() == 0.035
