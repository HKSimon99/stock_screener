from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models.instrument import Instrument
from app.models.institutional import InstitutionalOwnership
from app.models.price import Price
from app.services.ingestion import kr_investor_flow
from app.services.korea import chaebol_filter, sector_normalizer
from app.services.technical.pattern_detector import (
    count_price_limit_events,
    score_instrument_patterns,
)


class BoundSessionFactory:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_flag_cross_holdings_marks_samsung_affiliates(monkeypatch, db_session):
    samsung_electronics = Instrument(
        ticker="005930",
        name="Samsung Electronics",
        market="KR",
        exchange="KOSPI",
        asset_type="stock",
        is_active=True,
    )
    samsung_life = Instrument(
        ticker="032830",
        name="Samsung Life",
        market="KR",
        exchange="KOSPI",
        asset_type="stock",
        is_active=True,
    )
    outsider = Instrument(
        ticker="091810",
        name="Tiann",
        market="KR",
        exchange="KOSDAQ",
        asset_type="stock",
        is_active=True,
    )
    db_session.add_all([samsung_electronics, samsung_life, outsider])
    await db_session.commit()

    monkeypatch.setattr(
        chaebol_filter,
        "AsyncSessionLocal",
        BoundSessionFactory(db_session),
    )

    stats = await chaebol_filter.flag_cross_holdings()
    await db_session.refresh(samsung_electronics)
    await db_session.refresh(samsung_life)
    await db_session.refresh(outsider)

    assert stats["flagged"] == 2
    assert samsung_electronics.is_chaebol_cross is True
    assert samsung_life.is_chaebol_cross is True
    assert outsider.is_chaebol_cross is False
    assert chaebol_filter.get_group("005930") == "Samsung"
    assert chaebol_filter.shares_same_group("005930", "032830") is True


def test_sector_normalizer_applies_semiconductor_and_shipbuilding_windows():
    assert sector_normalizer.get_avg_window("Semiconductor Equipment") == 2
    assert sector_normalizer.normalize_eps([1.0, 2.0, 3.0, 5.0], "반도체") == pytest.approx(4.0)

    assert sector_normalizer.get_avg_window("Shipbuilding & Marine") == 3
    assert sector_normalizer.normalize_revenue([100.0, 120.0, 140.0, 160.0], "조선") == pytest.approx(140.0)

    assert sector_normalizer.get_avg_window("Banks") == 1
    assert sector_normalizer.normalize_eps([1.0, 2.0, 3.0], "Banks") == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_fetch_investor_flow_maps_official_prsn_fields(monkeypatch):
    payload = {
        "output": [
            {
                "stck_bsop_date": "20260413",
                "prsn_ntby_qty": "1,758,260",
                "frgn_ntby_qty": "-1,437,638",
                "orgn_ntby_qty": "-2,225,119",
                "prsn_shnu_vol": "5,253,106",
                "frgn_shnu_vol": "5,762,543",
                "orgn_shnu_vol": "6,626,138",
                "prsn_seln_vol": "3,494,846",
                "frgn_seln_vol": "7,200,181",
                "orgn_seln_vol": "8,851,257",
            }
        ]
    }

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, params=None):
            assert url.endswith("/uapi/domestic-stock/v1/quotations/inquire-investor")
            assert params == {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": "005930",
            }
            return FakeResponse()

    monkeypatch.setattr(kr_investor_flow.httpx, "AsyncClient", FakeClient)

    rows = await kr_investor_flow._fetch_investor_flow(
        ticker="005930",
        access_token="token",
        app_key="app-key",
        is_paper=True,
    )

    assert rows == [
        {
            "date": date(2026, 4, 13),
            "foreign_net": -1437638,
            "institutional_net": -2225119,
            "individual_net": 1758260,
            "individual_buy": 5253106,
            "individual_sell": 3494846,
            "foreign_buy": 5762543,
            "foreign_sell": 7200181,
            "institutional_buy": 6626138,
            "institutional_sell": 8851257,
        }
    ]


def test_assess_investor_flow_consistency_uses_cohort_arithmetic_not_zero_sum():
    rows = [
        {
            "date": date(2026, 4, 13),
            "foreign_net": -1437638,
            "institutional_net": -2225119,
            "individual_net": 1758260,
            "individual_buy": 5253106,
            "individual_sell": 3494846,
            "foreign_buy": 5762543,
            "foreign_sell": 7200181,
            "institutional_buy": 6626138,
            "institutional_sell": 8851257,
        }
    ]

    consistency = kr_investor_flow.assess_investor_flow_consistency(rows)

    assert consistency["status"] == "ok"
    assert consistency["max_abs_imbalance"] == 0
    assert consistency["max_abs_market_residual"] == 1904497
    assert consistency["anomalous_dates"] == []


@pytest.mark.asyncio
async def test_ingest_kr_investor_flows_rolls_up_balanced_rows(monkeypatch, db_session):
    instrument = Instrument(
        ticker="005930",
        name="Samsung Electronics",
        market="KR",
        exchange="KOSPI",
        asset_type="stock",
        shares_outstanding=1_000,
        float_shares=250,
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.commit()

    rows = [
        {
            "date": date(2026, 4, 10),
            "foreign_net": 120,
            "institutional_net": -20,
            "individual_net": -100,
            "foreign_buy": 620,
            "foreign_sell": 500,
            "institutional_buy": 180,
            "institutional_sell": 200,
            "individual_buy": 400,
            "individual_sell": 500,
        },
        {
            "date": date(2026, 4, 11),
            "foreign_net": -60,
            "institutional_net": 10,
            "individual_net": 50,
            "foreign_buy": 140,
            "foreign_sell": 200,
            "institutional_buy": 210,
            "institutional_sell": 200,
            "individual_buy": 350,
            "individual_sell": 300,
        },
        {
            "date": date(2026, 4, 14),
            "foreign_net": 40,
            "institutional_net": -5,
            "individual_net": -35,
            "foreign_buy": 260,
            "foreign_sell": 220,
            "institutional_buy": 195,
            "institutional_sell": 200,
            "individual_buy": 365,
            "individual_sell": 400,
        },
    ]

    async def fake_get_token(app_key, app_secret, is_paper):
        return "token"

    async def fake_fetch(ticker, access_token, app_key, is_paper, days=30):
        assert ticker == "005930"
        return rows

    monkeypatch.setenv("KIS_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_APP_SECRET", "test-secret")
    monkeypatch.setattr(kr_investor_flow, "_get_kis_token", fake_get_token)
    monkeypatch.setattr(kr_investor_flow, "_fetch_investor_flow", fake_fetch)
    monkeypatch.setattr(
        kr_investor_flow,
        "AsyncSessionLocal",
        BoundSessionFactory(db_session),
    )

    consistency = kr_investor_flow.assess_investor_flow_consistency(rows)
    result = await kr_investor_flow.ingest_kr_investor_flows(
        tickers=["005930"],
        report_date=date(2026, 4, 14),
    )

    stored = (
        await db_session.execute(
            select(InstitutionalOwnership).where(
                InstitutionalOwnership.instrument_id == instrument.id,
                InstitutionalOwnership.report_date == date(2026, 4, 14),
            )
        )
    ).scalars().one()

    assert consistency["status"] == "ok"
    assert consistency["max_abs_imbalance"] == 0
    assert consistency["max_abs_market_residual"] == 0
    assert result == {
        "processed": 1,
        "skipped": 0,
        "consistency_failures": 0,
    }
    assert float(stored.foreign_ownership_pct) == pytest.approx(0.25)
    assert stored.foreign_net_buy_30d == 100
    assert stored.institutional_net_buy_30d == -15
    assert stored.individual_net_buy_30d == -85
    assert stored.data_source == "KIS_INVESTOR_FLOW"


@pytest.mark.asyncio
async def test_score_instrument_patterns_suppresses_recent_kr_price_limit_moves(db_session):
    instrument = Instrument(
        ticker="005930",
        name="Samsung Electronics",
        market="KR",
        exchange="KOSPI",
        asset_type="stock",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.flush()

    closes: list[float] = []
    price = 100.0
    for idx in range(80):
        if idx == 70:
            price *= 1.30
        else:
            price *= 1.002
        closes.append(round(price, 2))

    start = date(2026, 1, 1)
    for idx, close in enumerate(closes):
        trade_date = start + timedelta(days=idx)
        db_session.add(
            Price(
                instrument_id=instrument.id,
                trade_date=trade_date,
                open=round(close * 0.995, 2),
                high=round(close * 1.01, 2),
                low=round(close * 0.99, 2),
                close=close,
                volume=1_000_000 + idx * 1_000,
                avg_volume_50d=1_000_000,
            )
        )

    await db_session.commit()

    assert count_price_limit_events(closes) == 1

    result = await score_instrument_patterns(
        instrument.id,
        start + timedelta(days=len(closes) - 1),
        db_session,
    )

    assert result is not None
    assert result["pattern_count"] == 0
    assert result["patterns"] == []
    assert result["limit_move_count"] == 1
