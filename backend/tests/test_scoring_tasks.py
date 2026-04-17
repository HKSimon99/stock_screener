from datetime import date

from app.tasks import scoring_tasks


def test_parse_score_date():
    assert scoring_tasks._parse_score_date("2026-04-13") == date(2026, 4, 13)
    assert scoring_tasks._parse_score_date(None) is None


def test_run_canslim_task_uses_runner(monkeypatch):
    captured = {}

    async def fake_runner(score_date=None, market=None, instrument_ids=None):
        captured["score_date"] = score_date
        captured["market"] = market
        captured["instrument_ids"] = instrument_ids
        return [{"instrument_id": 40}, {"instrument_id": 519}]

    monkeypatch.setattr(scoring_tasks, "run_canslim_scoring", fake_runner)

    result = scoring_tasks.run_canslim_task.run(
        score_date="2026-04-13",
        market="US",
        instrument_ids=[40, 519],
    )

    assert captured["score_date"] == date(2026, 4, 13)
    assert captured["market"] == "US"
    assert captured["instrument_ids"] == [40, 519]
    assert result["scored_count"] == 2
    assert result["scored_instrument_ids"] == [40, 519]


def test_run_phase2_pipeline_task_merges_ids(monkeypatch):
    async def fake_canslim(score_date=None, market=None, instrument_ids=None):
        return [{"instrument_id": 40}, {"instrument_id": 519}]

    async def fake_piotroski(score_date=None, market=None, instrument_ids=None):
        return [{"instrument_id": 519}]

    monkeypatch.setattr(scoring_tasks, "run_canslim_scoring", fake_canslim)
    monkeypatch.setattr(scoring_tasks, "run_piotroski_scoring", fake_piotroski)

    result = scoring_tasks.run_phase2_pipeline_task.run(score_date="2026-04-13")

    assert result["canslim_scored"] == 2
    assert result["piotroski_scored"] == 1
    assert result["unique_instruments_scored"] == 2
    assert result["scored_instrument_ids"] == [40, 519]


def test_run_phase2_backtest_task_passes_instrument_ids(monkeypatch):
    captured = {}

    async def fake_backtest(market=None, scoring_date=None, forward_days=63, instrument_ids=None):
        captured["market"] = market
        captured["scoring_date"] = scoring_date
        captured["forward_days"] = forward_days
        captured["instrument_ids"] = instrument_ids
        return {"ok": True, "instrument_ids": instrument_ids}

    monkeypatch.setattr(scoring_tasks, "run_backtest", fake_backtest)

    result = scoring_tasks.run_phase2_backtest_task.run(
        market="KR",
        scoring_date="2025-10-13",
        forward_days=63,
        instrument_ids=[519, 520, 522],
    )

    assert captured["market"] == "KR"
    assert captured["scoring_date"] == date(2025, 10, 13)
    assert captured["forward_days"] == 63
    assert captured["instrument_ids"] == [519, 520, 522]
    assert result == {"ok": True, "instrument_ids": [519, 520, 522]}


def test_run_consensus_backtest_task_passes_forward_windows(monkeypatch):
    captured = {}

    async def fake_backtest(market=None, scoring_date=None, forward_windows=None, instrument_ids=None):
        captured["market"] = market
        captured["scoring_date"] = scoring_date
        captured["forward_windows"] = forward_windows
        captured["instrument_ids"] = instrument_ids
        return {"ok": True, "forward_windows": forward_windows}

    monkeypatch.setattr(scoring_tasks, "run_consensus_backtest", fake_backtest)

    result = scoring_tasks.run_consensus_backtest_task.run(
        market="US",
        scoring_date="2025-10-13",
        forward_windows={"1m": 21, "3m": 63},
        instrument_ids=[40, 346],
    )

    assert captured["market"] == "US"
    assert captured["scoring_date"] == date(2025, 10, 13)
    assert captured["forward_windows"] == {"1m": 21, "3m": 63}
    assert captured["instrument_ids"] == [40, 346]
    assert result == {"ok": True, "forward_windows": {"1m": 21, "3m": 63}}
