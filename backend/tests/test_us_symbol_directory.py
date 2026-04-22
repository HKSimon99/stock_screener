from app.services.ingestion.us_price import _build_instrument_payload


def test_build_instrument_payload_skips_ticker_longer_than_schema_limit():
    payload = _build_instrument_payload(
        {
            "Symbol": "ABCDEFGHIJK",
            "Security Name": "Too Long Holdings",
            "Test Issue": "N",
            "ETF": "N",
        },
        "nasdaqlisted",
    )

    assert payload is None


def test_build_instrument_payload_keeps_supported_exact_symbol():
    payload = _build_instrument_payload(
        {
            "Symbol": "TSSI",
            "Security Name": "TSS, Inc. Common Stock",
            "Test Issue": "N",
            "ETF": "N",
        },
        "nasdaqlisted",
    )

    assert payload is not None
    assert payload["ticker"] == "TSSI"


def test_build_instrument_payload_uses_schema_safe_exchange_codes():
    payload = _build_instrument_payload(
        {
            "ACT Symbol": "AETH",
            "Security Name": "Bitwise Ethereum ETF",
            "Test Issue": "N",
            "ETF": "Y",
            "Exchange": "A",
        },
        "otherlisted",
    )

    assert payload is not None
    assert payload["exchange"] == "NYSEAMER"
    assert len(payload["exchange"]) <= 10
