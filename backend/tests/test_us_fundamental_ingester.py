import pytest

from app.services.ingestion.us_fundamental import EdgarFundamentalIngester


def test_prepare_annual_record_maps_model_fields_and_ratios():
    ingester = EdgarFundamentalIngester()

    prepared = ingester._prepare_annual_record(
        {
            "instrument_id": 318,
            "fiscal_year": 2025,
            "report_date": "2025-07-30",
            "revenue": 200.0,
            "gross_profit": 120.0,
            "net_income": 40.0,
            "eps": 5.5,
            "eps_yoy_growth": 0.1,
            "total_assets": 400.0,
            "total_liabilities": 250.0,
            "current_assets": 100.0,
            "current_liabilities": 50.0,
            "long_term_debt": 80.0,
            "shares_outstanding": 10.0,
            "operating_cash_flow": 60.0,
        }
    )

    assert prepared["shares_outstanding_annual"] == 10.0
    assert "shares_outstanding" not in prepared
    assert "total_liabilities" not in prepared
    assert prepared["data_source"] == "EDGAR"
    assert prepared["roa"] == pytest.approx(0.1)
    assert prepared["current_ratio"] == pytest.approx(2.0)
    assert prepared["gross_margin"] == pytest.approx(0.6)
    assert prepared["asset_turnover"] == pytest.approx(0.5)
    assert prepared["leverage_ratio"] == pytest.approx(0.2)
