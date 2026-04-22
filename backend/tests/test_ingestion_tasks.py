from app.tasks import ingestion_tasks


def test_normalize_tickers_deduplicates_and_trims():
    assert ingestion_tasks._normalize_tickers([" aapl ", "AAPL", " 005930 "]) == [
        "AAPL",
        "005930",
    ]


def test_run_us_fundamentals_task_uses_runner(monkeypatch):
    captured = {}

    async def fake_runner(ticker: str, years: int = 5):
        captured["ticker"] = ticker
        captured["years"] = years

    monkeypatch.setattr(ingestion_tasks, "run_us_fundamentals_ingestion", fake_runner)

    result = ingestion_tasks.run_us_fundamentals_task.run(" aapl ", years=4)

    assert captured["ticker"] == "AAPL"
    assert captured["years"] == 4
    assert result == {
        "market": "US",
        "ticker": "AAPL",
        "years": 4,
        "processed": True,
    }


def test_run_market_fundamentals_ingestion_uses_explicit_tickers(monkeypatch):
    processed = []

    async def fake_us_runner(ticker: str, years: int = 5):
        processed.append((ticker, years))

    async def unexpected_lookup(market: str, limit=None):
        raise AssertionError("Active ticker lookup should not be used when tickers are provided.")

    monkeypatch.setattr(ingestion_tasks, "run_us_fundamentals_ingestion", fake_us_runner)
    monkeypatch.setattr(ingestion_tasks, "_get_active_tickers", unexpected_lookup)

    result = ingestion_tasks.run_us_fundamentals_batch_task.run(
        tickers=["msft", " nvda "],
        years=3,
    )

    assert processed == [("MSFT", 3), ("NVDA", 3)]
    assert result["market"] == "US"
    assert result["processed_count"] == 2
    assert result["processed_tickers"] == ["MSFT", "NVDA"]
    assert result["failed_tickers"] == []


def test_run_kr_fundamentals_batch_task_uses_active_tickers_when_missing(monkeypatch):
    processed = []

    async def fake_lookup(market: str, limit=None):
        assert market == "KR"
        assert limit == 2
        return ["005930", "000660"]

    async def fake_kr_runner(ticker: str, years: int = 5):
        processed.append((ticker, years))

    monkeypatch.setattr(ingestion_tasks, "_get_active_tickers", fake_lookup)
    monkeypatch.setattr(ingestion_tasks, "run_kr_fundamentals_ingestion", fake_kr_runner)

    result = ingestion_tasks.run_kr_fundamentals_batch_task.run(years=2, limit=2)

    assert processed == [("005930", 2), ("000660", 2)]
    assert result["market"] == "KR"
    assert result["requested_count"] == 2
    assert result["processed_count"] == 2
    assert result["failed_count"] == 0


def test_run_market_fundamentals_ingestion_tracks_failures(monkeypatch):
    captured = {}

    async def fake_us_runner(ticker: str, years: int = 5):
        if ticker == "FAIL":
            raise RuntimeError("boom")

    async def fake_record(source_name, market, requested_count, processed_count, failed_tickers=None, error=None):
        captured.update(
            {
                "source_name": source_name,
                "market": market,
                "requested_count": requested_count,
                "processed_count": processed_count,
                "failed_tickers": failed_tickers,
                "error": error,
            }
        )

    monkeypatch.setattr(ingestion_tasks, "run_us_fundamentals_ingestion", fake_us_runner)
    monkeypatch.setattr(ingestion_tasks, "_record_source_freshness", fake_record)

    result = ingestion_tasks.run_us_fundamentals_batch_task.run(
        tickers=["AAPL", "FAIL"],
        years=5,
    )

    assert result["processed_tickers"] == ["AAPL"]
    assert result["failed_tickers"] == ["FAIL"]
    assert result["failed_count"] == 1
    assert captured == {
        "source_name": "US_FUNDAMENTALS",
        "market": "US",
        "requested_count": 2,
        "processed_count": 1,
        "failed_tickers": ["FAIL"],
        "error": None,
    }


def test_run_us_price_task_uses_runner(monkeypatch):
    captured = {}

    async def fake_runner(tickers=None, days=730, limit=None, sync_universe=False):
        captured["tickers"] = tickers
        captured["days"] = days
        captured["limit"] = limit
        captured["sync_universe"] = sync_universe
        return {
            "processed_tickers": ["MSFT"],
        }

    monkeypatch.setattr(ingestion_tasks, "run_us_price_ingestion", fake_runner)

    result = ingestion_tasks.run_us_price_task.run(" msft ", days=365, sync_universe=True)

    assert captured == {
        "tickers": ["MSFT"],
        "days": 365,
        "limit": None,
        "sync_universe": True,
    }
    assert result == {
        "market": "US",
        "ticker": "MSFT",
        "days": 365,
        "processed": True,
        "sync_universe": True,
    }


def test_run_us_price_ingestion_uses_refs_and_sync(monkeypatch):
    processed = []
    freshness = {}

    class FakeSession:
        pass

    class FakeSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def fake_sync(session):
        processed.append(("SYNC", None))

    async def fake_refs(session, market, tickers=None, limit=None, asset_types=None):
        assert market == "US"
        assert tickers == ["AAPL", "NVDA"]
        assert limit is None
        assert asset_types is None
        return [(40, "AAPL"), (346, "NVDA")]

    async def fake_fetch(session, instrument_id, ticker, days=730):
        processed.append((ticker, days, instrument_id))

    async def fake_record(source_name, market, requested_count, processed_count, failed_tickers=None, error=None):
        freshness.update(
            {
                "source_name": source_name,
                "market": market,
                "requested_count": requested_count,
                "processed_count": processed_count,
                "failed_tickers": failed_tickers,
                "error": error,
            }
        )

    monkeypatch.setattr(ingestion_tasks, "AsyncSessionLocal", FakeSessionFactory())
    monkeypatch.setattr(ingestion_tasks, "sync_instruments", fake_sync)
    monkeypatch.setattr(ingestion_tasks, "_get_instrument_refs", fake_refs)
    monkeypatch.setattr(ingestion_tasks, "fetch_and_store_prices", fake_fetch)
    monkeypatch.setattr(ingestion_tasks, "_record_source_freshness", fake_record)

    result = ingestion_tasks.run_us_price_batch_task.run(
        tickers=["aapl", "nvda"],
        days=400,
        sync_universe=True,
    )

    assert processed == [("SYNC", None), ("AAPL", 400, 40), ("NVDA", 400, 346)]
    assert result["market"] == "US"
    assert result["processed_count"] == 2
    assert result["processed_tickers"] == ["AAPL", "NVDA"]
    assert result["failed_tickers"] == []
    assert freshness == {
        "source_name": "US_PRICES",
        "market": "US",
        "requested_count": 2,
        "processed_count": 2,
        "failed_tickers": [],
        "error": None,
    }


def test_run_kr_price_task_uses_runner(monkeypatch):
    captured = {}

    async def fake_runner(tickers=None, days=730, limit=None, sync_universe=False):
        captured["tickers"] = tickers
        captured["days"] = days
        captured["limit"] = limit
        captured["sync_universe"] = sync_universe
        return {
            "processed_tickers": ["005930"],
        }

    monkeypatch.setattr(ingestion_tasks, "run_kr_price_ingestion", fake_runner)

    result = ingestion_tasks.run_kr_price_task.run(" 005930 ", days=365, sync_universe=True)

    assert captured == {
        "tickers": ["005930"],
        "days": 365,
        "limit": None,
        "sync_universe": True,
    }
    assert result == {
        "market": "KR",
        "ticker": "005930",
        "days": 365,
        "processed": True,
        "sync_universe": True,
    }


def test_run_kr_price_ingestion_uses_refs_and_client(monkeypatch):
    processed = []
    freshness = {}

    class FakeSession:
        pass

    class FakeSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def fake_sync(session):
        processed.append(("SYNC", None))

    async def fake_refs(session, market, tickers=None, limit=None, asset_types=None):
        assert market == "KR"
        assert tickers == ["005930", "000660"]
        assert limit is None
        assert asset_types is None
        return [(519, "005930"), (520, "000660")]

    async def fake_fetch(session, instrument_id, ticker, kis_client, days=730):
        processed.append((ticker, days, instrument_id, kis_client))

    async def fake_has_rows(session, instrument_id):
        return True

    async def fake_sleep(seconds):
        processed.append(("SLEEP", seconds))

    async def fake_record(source_name, market, requested_count, processed_count, failed_tickers=None, error=None):
        freshness.update(
            {
                "source_name": source_name,
                "market": market,
                "requested_count": requested_count,
                "processed_count": processed_count,
                "failed_tickers": failed_tickers,
                "error": error,
            }
        )

    monkeypatch.setattr(ingestion_tasks, "AsyncSessionLocal", FakeSessionFactory())
    monkeypatch.setattr(ingestion_tasks, "sync_kr_instruments", fake_sync)
    monkeypatch.setattr(ingestion_tasks, "_build_kis_client", lambda: "fake-kis")
    monkeypatch.setattr(ingestion_tasks, "_get_instrument_refs", fake_refs)
    monkeypatch.setattr(ingestion_tasks, "fetch_and_store_kr_prices", fake_fetch)
    monkeypatch.setattr(ingestion_tasks, "_has_price_rows", fake_has_rows)
    monkeypatch.setattr(ingestion_tasks.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(ingestion_tasks, "_record_source_freshness", fake_record)

    result = ingestion_tasks.run_kr_price_batch_task.run(
        tickers=["005930", "000660"],
        days=400,
        sync_universe=True,
    )

    assert processed == [
        ("SYNC", None),
        ("005930", 400, 519, "fake-kis"),
        ("SLEEP", ingestion_tasks.KR_PRICE_REQUEST_DELAY_SECONDS),
        ("000660", 400, 520, "fake-kis"),
    ]
    assert result["market"] == "KR"
    assert result["processed_count"] == 2
    assert result["processed_tickers"] == ["005930", "000660"]
    assert result["failed_tickers"] == []
    assert freshness == {
        "source_name": "KR_PRICES",
        "market": "KR",
        "requested_count": 2,
        "processed_count": 2,
        "failed_tickers": [],
        "error": None,
    }
