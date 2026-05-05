from __future__ import annotations

import asyncio
import json
import statistics
from collections import defaultdict
from datetime import date
from typing import Optional

from sqlalchemy import desc, select

from app.core.database import AsyncSessionLocal
from app.models.consensus_score import ConsensusScore
from app.models.instrument import Instrument
from app.models.price import Price

DEFAULT_FORWARD_WINDOWS = {"5d": 5, "20d": 20, "60d": 60}


def _quantile_label(index: int, total: int, buckets: int = 5) -> str:
    if total <= 0:
        return "Q?"
    bucket = min(buckets, int(index * buckets / total) + 1)
    return f"Q{bucket}"


def _summarize_rows(rows: list[dict], forward_windows: dict[str, int]) -> dict:
    summary = {"n": len(rows), "horizons": {}}
    for label in forward_windows:
        valid = [row for row in rows if row["forward_metrics"].get(label)]
        if not valid:
            summary["horizons"][label] = {
                "n": 0,
                "avg_return_pct": None,
                "median_return_pct": None,
                "avg_max_drawdown_pct": None,
                "hit_rate_pct": None,
            }
            continue
        returns = [row["forward_metrics"][label]["return"] for row in valid]
        drawdowns = [row["forward_metrics"][label]["max_drawdown"] for row in valid]
        summary["horizons"][label] = {
            "n": len(valid),
            "avg_return_pct": round(statistics.mean(returns) * 100, 2),
            "median_return_pct": round(statistics.median(returns) * 100, 2),
            "avg_max_drawdown_pct": round(statistics.mean(drawdowns) * 100, 2),
            "hit_rate_pct": round(sum(1 for value in returns if value > 0) / len(returns) * 100, 1),
        }
    return summary


def _coverage_summary(rows: list[dict]) -> dict:
    strategy_keys = ["canslim", "piotroski", "magic_formula", "technical"]
    return {
        key: {
            "present": sum(1 for row in rows if row.get(key) is not None),
            "missing": sum(1 for row in rows if row.get(key) is None),
        }
        for key in strategy_keys
    }


async def _forward_metrics(instrument_id: int, score_date: date, bars: int, db) -> Optional[dict]:
    result = await db.execute(
        select(Price.close)
        .where(
            Price.instrument_id == instrument_id,
            Price.trade_date >= score_date,
        )
        .order_by(Price.trade_date.asc())
        .limit(bars + 1)
    )
    closes = [float(row[0]) for row in result.fetchall() if row[0] is not None]
    if len(closes) < 2 or closes[0] <= 0:
        return None

    peak = closes[0]
    max_drawdown = 0.0
    for close in closes:
        peak = max(peak, close)
        if peak > 0:
            max_drawdown = min(max_drawdown, close / peak - 1.0)

    return {
        "return": closes[-1] / closes[0] - 1.0,
        "max_drawdown": max_drawdown,
        "bars": len(closes),
    }


async def run_scoring_validation_report(
    *,
    scoring_date: Optional[date] = None,
    market: Optional[str] = None,
    forward_windows: Optional[dict[str, int]] = None,
    max_rows: Optional[int] = None,
) -> dict:
    """
    Validate already-persisted consensus scores against forward returns.

    This is intentionally dependency-light and read-only. It does not rerun
    scoring, mutate Neon, or require Alphalens/vectorbt.
    """
    forward_windows = forward_windows or DEFAULT_FORWARD_WINDOWS

    async with AsyncSessionLocal() as db:
        if scoring_date is None:
            stmt = select(ConsensusScore.score_date).order_by(desc(ConsensusScore.score_date)).limit(1)
            scoring_date = (await db.execute(stmt)).scalar_one_or_none()
        if scoring_date is None:
            return {"error": "no consensus scores found"}

        stmt = (
            select(ConsensusScore, Instrument)
            .join(Instrument, Instrument.id == ConsensusScore.instrument_id)
            .where(
                ConsensusScore.score_date == scoring_date,
                Instrument.asset_type == "stock",
                Instrument.is_active.is_(True),
            )
            .order_by(desc(ConsensusScore.final_score), Instrument.ticker.asc())
        )
        if market:
            stmt = stmt.where(Instrument.market == market)
        if max_rows:
            stmt = stmt.limit(max_rows)

        score_rows = (await db.execute(stmt)).all()

        rows: list[dict] = []
        total = len(score_rows)
        for idx, (score, instrument) in enumerate(score_rows):
            metrics = {
                label: await _forward_metrics(instrument.id, scoring_date, bars, db)
                for label, bars in forward_windows.items()
            }
            row = {
                "instrument_id": instrument.id,
                "ticker": instrument.ticker,
                "market": instrument.market,
                "sector": instrument.sector or "UNKNOWN",
                "conviction_level": score.conviction_level or "UNRANKED",
                "score_quantile": _quantile_label(idx, total),
                "final_score": float(score.final_score or 0),
                "canslim": float(score.canslim_score) if score.canslim_score is not None else None,
                "piotroski": float(score.piotroski_score) if score.piotroski_score is not None else None,
                "magic_formula": float(score.magic_formula_score) if score.magic_formula_score is not None else None,
                "technical": float(score.technical_composite) if score.technical_composite is not None else None,
                "forward_metrics": metrics,
            }
            rows.append(row)

    by_conviction: dict[str, list[dict]] = defaultdict(list)
    by_quantile: dict[str, list[dict]] = defaultdict(list)
    by_market: dict[str, list[dict]] = defaultdict(list)
    by_sector: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_conviction[row["conviction_level"]].append(row)
        by_quantile[row["score_quantile"]].append(row)
        by_market[row["market"]].append(row)
        by_sector[row["sector"]].append(row)

    return {
        "scoring_date": scoring_date.isoformat(),
        "market": market,
        "forward_windows": forward_windows,
        "n_scored": len(rows),
        "coverage": _coverage_summary(rows),
        "by_conviction": {
            key: _summarize_rows(value, forward_windows)
            for key, value in sorted(by_conviction.items())
        },
        "by_score_quantile": {
            key: _summarize_rows(value, forward_windows)
            for key, value in sorted(by_quantile.items())
        },
        "by_market": {
            key: _summarize_rows(value, forward_windows)
            for key, value in sorted(by_market.items())
        },
        "by_sector": {
            key: _summarize_rows(value, forward_windows)
            for key, value in sorted(by_sector.items())
        },
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_scoring_validation_report()), indent=2, default=str))
