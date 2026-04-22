from datetime import date
from types import SimpleNamespace

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
    assert result["profile"]["sql_query_count"] >= 0
    assert result["profile"]["stages"]["canslim"]["result_count"] == 2
    assert result["profile"]["stages"]["piotroski"]["result_count"] == 1
    assert result["profile"]["total_duration_ms"] >= 0


def test_run_full_pipeline_task_includes_profile(monkeypatch):
    async def fake_resolve_targets(*, market=None, instrument_ids=None):
        return [(1, "US"), (2, "US")]

    async def fake_load_market_inputs(*, markets=None, score_date=None):
        return (
            {"US": [100.0] * 260},
            {"US": 0.05},
            {"US": {1: 88.0, 2: 75.0}},
            {"US": {1: 82.0, 2: 70.0}},
        )

    async def fake_load_batch_context(db, *, instrument_ids, score_date):
        contexts = {}
        for inst_id in instrument_ids:
            contexts[inst_id] = SimpleNamespace(
                instrument=SimpleNamespace(
                    id=inst_id,
                    market="US",
                    ticker=f"T{inst_id}",
                    exchange="NASDAQ",
                    sector="Technology",
                    shares_outstanding=1000.0,
                    float_shares=500.0,
                    is_chaebol_cross=False,
                ),
                prices=(SimpleNamespace(close=100.0, high=101.0, low=99.0, volume=1000.0, avg_volume_50d=900.0),) * 260,
                quarterlies=(),
                annuals=(),
                institutional=None,
            )
        return SimpleNamespace(
            instruments=contexts,
            regimes_by_market={"US": SimpleNamespace(state="CONFIRMED_UPTREND")},
        )

    def fake_patterns(*, instrument=None, score_date=None, prices=None):
        return {"instrument_id": instrument.id, "score_date": score_date, "patterns": [{"confidence": 0.9}], "pattern_count": 1}

    def fake_technical(*, instrument_id=None, score_date=None, prices=None, benchmark_closes=None):
        return {
            "instrument_id": instrument_id,
            "score_date": score_date,
            "ad_rating": "A",
            "bb_squeeze": True,
            "rs_line_new_high": True,
            "technical_detail": {"obv_trend": "rising"},
        }

    def fake_piotroski(*, instrument_id=None, score_date=None, annuals=None):
        return {"instrument_id": instrument_id, "score_date": score_date, "piotroski_score": 90.0}

    def fake_minervini(*, instrument_id=None, score_date=None, prices=None, rs_rating=None):
        return {
            "instrument_id": instrument_id,
            "score_date": score_date,
            "minervini_score": 80.0,
            "minervini_criteria_count": 7,
        }

    def fake_weinstein(*, instrument_id=None, score_date=None, prices=None):
        return {"instrument_id": instrument_id, "score_date": score_date, "weinstein_score": 85.0}

    def fake_dual_momentum(*, instrument_id=None, score_date=None, prices=None, benchmark_closes=None, risk_free=None):
        return {"instrument_id": instrument_id, "score_date": score_date, "dual_mom_score": 70.0}

    def fake_canslim(*, instrument=None, quarterlies=None, annuals=None, prices=None, institutional=None, regime=None, score_date=None, rs_lookup=None, rs_4w_lookup=None, patterns=None, rs_line_new_high=None):
        return {"instrument_id": instrument.id, "score_date": score_date, "canslim_score": 95.0}

    def fake_composite(*, instrument_id=None, score_date=None, prices=None, patterns=None, technical_detail=None, minervini_criteria_count=None):
        return {
            "instrument_id": instrument_id,
            "score_date": score_date,
            "technical_composite": 77.0,
            "technical_detail": {"composite": {"ok": True}},
        }

    async def fake_consensus(score_date=None, market=None, instrument_ids=None):
        return [{"instrument_id": 1, "conviction_level": "GOLD"}]

    async def fake_snapshot_generation(snapshot_date=None, markets=None):
        return [{"market": market, "instruments": 1} for market in (markets or [])]

    async def fake_bulk_upsert(db, rows):
        return None

    monkeypatch.setattr(scoring_tasks, "_resolve_target_instruments", fake_resolve_targets)
    monkeypatch.setattr(scoring_tasks, "_load_market_inputs", fake_load_market_inputs)
    monkeypatch.setattr(scoring_tasks, "load_batch_scoring_context", fake_load_batch_context)
    monkeypatch.setattr(scoring_tasks, "compute_patterns_from_context", fake_patterns)
    monkeypatch.setattr(scoring_tasks, "compute_technical_indicators_from_context", fake_technical)
    monkeypatch.setattr(scoring_tasks, "compute_piotroski_from_context", fake_piotroski)
    monkeypatch.setattr(scoring_tasks, "compute_minervini_from_context", fake_minervini)
    monkeypatch.setattr(scoring_tasks, "compute_weinstein_from_context", fake_weinstein)
    monkeypatch.setattr(scoring_tasks, "compute_dual_momentum_from_context", fake_dual_momentum)
    monkeypatch.setattr(scoring_tasks, "compute_canslim_from_context", fake_canslim)
    monkeypatch.setattr(scoring_tasks, "compute_technical_composite_from_context", fake_composite)
    monkeypatch.setattr(scoring_tasks, "bulk_upsert_strategy_scores", fake_bulk_upsert)
    monkeypatch.setattr(
        "app.services.strategies.consensus.run_consensus_scoring",
        fake_consensus,
    )
    monkeypatch.setattr(
        "app.services.strategies.snapshot_generator.run_snapshot_generation",
        fake_snapshot_generation,
    )

    result = scoring_tasks.run_full_pipeline_task.run(score_date="2026-04-13", market="US")

    assert result["canslim_scored"] == 2
    assert result["patterns_with_detections"] == 2
    assert result["snapshots_generated"] == 1
    assert result["pipeline_mode"] == "context"
    assert result["profile"]["sql_query_count"] >= 0
    assert result["profile"]["stages"]["technical_composite_compute"]["result_count"] == 2
    assert result["profile"]["stages"]["consensus"]["result_count"] == 1
    assert result["profile"]["stages"]["snapshot_generation"]["result_count"] == 1
    assert result["profile"]["stages"]["strategy_score_upsert"]["result_count"] == 2


def test_run_full_pipeline_task_skips_snapshots_when_requested(monkeypatch):
    async def fake_context_pipeline(*, parsed_date, market, instrument_ids, generate_snapshots):
        assert generate_snapshots is False
        return {
            "score_date": parsed_date.isoformat(),
            "market": market,
            "canslim_scored": 1,
            "piotroski_scored": 1,
            "minervini_scored": 1,
            "weinstein_scored": 1,
            "dual_momentum_scored": 1,
            "technical_scored": 1,
            "patterns_scanned": 1,
            "patterns_with_detections": 0,
            "composite_scored": 1,
            "avg_technical_composite": 75.0,
            "consensus_scored": 1,
            "conviction_distribution": {"SILVER": 1},
            "snapshots_generated": 0,
            "unique_instruments_scored": 1,
            "scored_instrument_ids": [7],
            "profile": {
                "sql_query_count": 0,
                "total_duration_ms": 0,
                "stages": {"snapshot_generation": {"duration_ms": 0.0, "result_count": 0, "skipped": True}},
            },
        }

    monkeypatch.setattr(scoring_tasks, "_run_context_full_scoring_pipeline", fake_context_pipeline)

    result = scoring_tasks.run_full_pipeline_task.run(
        score_date="2026-04-13",
        market="US",
        instrument_ids=[7],
        generate_snapshots=False,
    )

    assert result["snapshots_generated"] == 0
    assert result["profile"]["stages"]["snapshot_generation"]["skipped"] is True
    assert result["pipeline_mode"] == "context"


def test_run_full_pipeline_task_dispatches_to_legacy_mode(monkeypatch):
    async def fake_legacy_pipeline(*, parsed_date, market, instrument_ids, generate_snapshots):
        return {
            "score_date": parsed_date.isoformat(),
            "market": market,
            "canslim_scored": 0,
            "piotroski_scored": 0,
            "minervini_scored": 0,
            "weinstein_scored": 0,
            "dual_momentum_scored": 0,
            "technical_scored": 0,
            "patterns_scanned": 0,
            "patterns_with_detections": 0,
            "composite_scored": 0,
            "avg_technical_composite": 0.0,
            "consensus_scored": 0,
            "conviction_distribution": {},
            "snapshots_generated": 0,
            "unique_instruments_scored": 0,
            "scored_instrument_ids": [],
            "profile": {"sql_query_count": 0, "total_duration_ms": 0, "stages": {}},
        }

    async def fail_context_pipeline(**kwargs):
        raise AssertionError("context pipeline should not run in legacy mode")

    monkeypatch.setattr(scoring_tasks, "_run_legacy_full_scoring_pipeline", fake_legacy_pipeline)
    monkeypatch.setattr(scoring_tasks, "_run_context_full_scoring_pipeline", fail_context_pipeline)

    result = scoring_tasks.run_full_pipeline_task.run(
        score_date="2026-04-13",
        market="KR",
        pipeline_mode="legacy",
    )

    assert result["pipeline_mode"] == "legacy"


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
