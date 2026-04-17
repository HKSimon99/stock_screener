from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.ingestion.kr_fundamental import KRFundamentalIngester


@pytest.fixture
def ingester(monkeypatch):
    monkeypatch.setattr(settings, "opendart_api_key", "test-key")
    return KRFundamentalIngester()


def test_build_record_maps_full_open_dart_statement_fields(ingester):
    annual_statement = [
        {"sj_div": "IS", "account_nm": "매출액", "thstrm_amount": "333,605,938,000,000"},
        {"sj_div": "IS", "account_nm": "매출총이익", "thstrm_amount": "142,260,000,000,000"},
        {"sj_div": "IS", "account_nm": "당기순이익(손실)", "thstrm_amount": "45,206,805,000,000"},
        {
            "sj_div": "CIS",
            "account_nm": "기본주당순이익(손실)",
            "account_id": "ifrs-full_BasicEarningsLossPerShare",
            "thstrm_amount": "6,605",
        },
        {
            "sj_div": "CIS",
            "account_nm": "보통주 희석주당이익",
            "account_id": "ifrs-full_DilutedEarningsLossPerShare",
            "thstrm_amount": "6,603",
        },
        {"sj_div": "BS", "account_nm": "자산총계", "thstrm_amount": "566,942,110,000,000"},
        {"sj_div": "BS", "account_nm": "유동자산", "thstrm_amount": "247,684,612,000,000"},
        {"sj_div": "BS", "account_nm": "유동부채", "thstrm_amount": "106,411,348,000,000"},
        {
            "sj_div": "BS",
            "account_nm": "차입금",
            "account_id": "ifrs-full_LongtermBorrowings",
            "thstrm_amount": "6,479,517,000,000",
        },
        {"sj_div": "BS", "account_nm": "사채", "thstrm_amount": "500,000,000,000"},
        {"sj_div": "CF", "account_nm": "영업활동 현금흐름", "thstrm_amount": "85,315,148,000,000"},
    ]

    record = ingester._build_record(annual_statement, ingester.annual_concept_map)

    assert record["revenue"] == 333605938000000.0
    assert record["gross_profit"] == 142260000000000.0
    assert record["net_income"] == 45206805000000.0
    assert record["eps"] == 6605.0
    assert record["eps_diluted"] == 6603.0
    assert record["total_assets"] == 566942110000000.0
    assert record["current_assets"] == 247684612000000.0
    assert record["current_liabilities"] == 106411348000000.0
    assert record["long_term_debt"] == 6979517000000.0
    assert record["operating_cash_flow"] == 85315148000000.0


def test_build_record_maps_quarterly_net_income_aliases(ingester):
    quarterly_statement = [
        {"sj_div": "IS", "account_nm": "매출액", "thstrm_amount": "86,061,747,000,000"},
        {"sj_div": "IS", "account_nm": "분기순이익", "account_id": "ifrs-full_ProfitLoss", "thstrm_amount": "12,225,747,000,000"},
        {"sj_div": "IS", "account_nm": "기본주당이익", "account_id": "ifrs-full_BasicEarningsLossPerShare", "thstrm_amount": "1,802"},
    ]

    record = ingester._build_record(quarterly_statement, ingester.quarterly_concept_map)

    assert record["revenue"] == 86061747000000.0
    assert record["net_income"] == 12225747000000.0
    assert record["eps"] == 1802.0


def test_prepare_annual_record_adds_ratios_and_share_count_fallback(ingester):
    instrument = SimpleNamespace(shares_outstanding=5969782550)

    prepared = ingester._prepare_annual_record(
        {
            "instrument_id": 519,
            "fiscal_year": 2025,
            "report_date": "2025-12-31",
            "revenue": 200.0,
            "gross_profit": 80.0,
            "net_income": 20.0,
            "eps": 4.0,
            "eps_diluted": 3.9,
            "eps_yoy_growth": 0.25,
            "total_assets": 400.0,
            "current_assets": 120.0,
            "current_liabilities": 60.0,
            "long_term_debt": 50.0,
            "operating_cash_flow": 30.0,
        },
        instrument,
    )

    assert prepared["shares_outstanding_annual"] == 5969782550
    assert prepared["data_source"] == "DART"
    assert prepared["roa"] == pytest.approx(0.05)
    assert prepared["current_ratio"] == pytest.approx(2.0)
    assert prepared["gross_margin"] == pytest.approx(0.4)
    assert prepared["asset_turnover"] == pytest.approx(0.5)
    assert prepared["leverage_ratio"] == pytest.approx(0.125)
    assert "revenue_yoy_growth" not in prepared
