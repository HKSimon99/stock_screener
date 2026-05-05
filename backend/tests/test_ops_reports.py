from app.services.ops.neon_cleanup_audit import AUDIT_SQL
from app.services.ops.scoring_validation_report import (
    DEFAULT_FORWARD_WINDOWS,
    _coverage_summary,
    _quantile_label,
    _summarize_rows,
)


def test_neon_cleanup_audit_contains_etf_preflight_counts():
    assert "legacy_etf_instruments" in AUDIT_SQL
    assert "etf_dependent_prices" in AUDIT_SQL
    assert "etf_dependent_strategy_scores" in AUDIT_SQL
    assert "delete" not in " ".join(AUDIT_SQL.values()).lower()


def test_scoring_validation_report_uses_5_20_60_day_windows():
    assert DEFAULT_FORWARD_WINDOWS == {"5d": 5, "20d": 20, "60d": 60}
    assert _quantile_label(0, 100) == "Q1"
    assert _quantile_label(99, 100) == "Q5"


def test_scoring_validation_summary_reports_hit_rate_and_drawdown():
    rows = [
        {
            "forward_metrics": {
                "5d": {"return": 0.10, "max_drawdown": -0.03},
                "20d": None,
                "60d": None,
            }
        },
        {
            "forward_metrics": {
                "5d": {"return": -0.05, "max_drawdown": -0.12},
                "20d": None,
                "60d": None,
            }
        },
    ]

    summary = _summarize_rows(rows, DEFAULT_FORWARD_WINDOWS)

    assert summary["horizons"]["5d"]["n"] == 2
    assert summary["horizons"]["5d"]["hit_rate_pct"] == 50.0
    assert summary["horizons"]["5d"]["avg_max_drawdown_pct"] == -7.5


def test_scoring_validation_coverage_counts_missing_magic_formula():
    rows = [
        {"canslim": 80.0, "piotroski": 70.0, "magic_formula": None, "technical": 50.0},
        {"canslim": None, "piotroski": 60.0, "magic_formula": 90.0, "technical": None},
    ]

    coverage = _coverage_summary(rows)

    assert coverage["magic_formula"] == {"present": 1, "missing": 1}
    assert coverage["piotroski"] == {"present": 2, "missing": 0}
