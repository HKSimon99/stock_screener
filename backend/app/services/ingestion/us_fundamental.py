"""
US Fundamental Ingestion (yfinance)
=====================================
Fetches quarterly and annual fundamentals using yfinance.  One call per
statement type per ticker returns ALL available history at once.

Replaces the previous EDGAR edgartools implementation which required one
HTTP call per filing (20–30 calls/ticker) and slow XBRL XML parsing.

Speed: ~4 calls per ticker vs 20–30.  No XBRL parsing overhead.
Cost: free (Yahoo Finance, no API key needed).
Rate limits: yfinance hits undocumented Yahoo endpoints; Semaphore(10)
keeps concurrent calls within typical rate-limit windows (~0.1–0.2 s/call).
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import date
from typing import Optional

import pandas as pd
import yfinance as yf
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.fundamental import FundamentalAnnual, FundamentalQuarterly
from app.models.instrument import Instrument

logger = logging.getLogger(__name__)

# ── helpers ───────────────────────────────────────────────────────────────────

def _col(df: pd.DataFrame, col, *row_names: str) -> Optional[float]:
    """Pull a single finite float from (row_name, col) in a yfinance statement DataFrame."""
    if df.empty or col not in df.columns:
        return None
    for name in row_names:
        if name in df.index:
            val = df.loc[name, col]
            if pd.notnull(val):
                try:
                    v = float(val)
                    return v if math.isfinite(v) else None
                except (TypeError, ValueError):
                    pass
    return None


def _date_key(ts) -> Optional[date]:
    try:
        return pd.Timestamp(ts).date()
    except Exception:
        return None


def _quarter_from_date(d: date) -> int:
    return (d.month - 1) // 3 + 1


# ── single-ticker fetch ───────────────────────────────────────────────────────

async def _fetch_yf_frames(ticker: str, semaphore: asyncio.Semaphore) -> dict:
    """
    Fetch all yfinance statement DataFrames for one ticker under a semaphore.
    Returns dict of DataFrames; empty DataFrames on failure.
    """
    empty = {k: pd.DataFrame() for k in
             ["income_q", "balance_q", "income_a", "balance_a", "cashflow_a"]}
    async with semaphore:
        try:
            t = await asyncio.to_thread(yf.Ticker, ticker)
            income_q   = await asyncio.to_thread(lambda: t.quarterly_income_stmt)
            balance_q  = await asyncio.to_thread(lambda: t.quarterly_balance_sheet)
            income_a   = await asyncio.to_thread(lambda: t.income_stmt)
            balance_a  = await asyncio.to_thread(lambda: t.balance_sheet)
            cashflow_a = await asyncio.to_thread(lambda: t.cashflow)
            return {
                "income_q":   income_q   if income_q   is not None else pd.DataFrame(),
                "balance_q":  balance_q  if balance_q  is not None else pd.DataFrame(),
                "income_a":   income_a   if income_a   is not None else pd.DataFrame(),
                "balance_a":  balance_a  if balance_a  is not None else pd.DataFrame(),
                "cashflow_a": cashflow_a if cashflow_a is not None else pd.DataFrame(),
            }
        except Exception as exc:
            logger.debug("yfinance fetch failed for %s: %s", ticker, exc)
            return empty


# ── record builders ───────────────────────────────────────────────────────────

def _build_quarterly_records(instrument_id: int, frames: dict) -> list[dict]:
    income_q = frames.get("income_q", pd.DataFrame())
    if income_q.empty:
        return []

    records: list[dict] = []
    for col in income_q.columns:
        d = _date_key(col)
        if d is None:
            continue
        records.append({
            "instrument_id":  instrument_id,
            "fiscal_year":    d.year,
            "fiscal_quarter": _quarter_from_date(d),
            "report_date":    d,
            "revenue":    _col(income_q, col, "Total Revenue"),
            "net_income": _col(income_q, col, "Net Income", "Net Income Common Stockholders"),
            "eps":        _col(income_q, col, "Basic EPS", "Diluted EPS"),
            "data_source": "YFINANCE",
        })

    # Sort oldest-first, then compute YoY growth (Q(t) vs Q(t-4))
    records.sort(key=lambda r: r["report_date"])
    for i in range(4, len(records)):
        prev, curr = records[i - 4], records[i]
        if curr.get("revenue") and prev.get("revenue") and prev["revenue"] != 0:
            curr["revenue_yoy_growth"] = (curr["revenue"] - prev["revenue"]) / abs(prev["revenue"])
        if curr.get("eps") and prev.get("eps") and prev["eps"] != 0:
            curr["eps_yoy_growth"] = (curr["eps"] - prev["eps"]) / abs(prev["eps"])

    return records


def _build_annual_records(instrument_id: int, frames: dict) -> list[dict]:
    income_a   = frames.get("income_a",   pd.DataFrame())
    balance_a  = frames.get("balance_a",  pd.DataFrame())
    cashflow_a = frames.get("cashflow_a", pd.DataFrame())

    if income_a.empty:
        return []

    records: list[dict] = []
    for col in income_a.columns:
        d = _date_key(col)
        if d is None:
            continue

        revenue      = _col(income_a, col, "Total Revenue")
        gross_profit = _col(income_a, col, "Gross Profit")
        net_income   = _col(income_a, col, "Net Income", "Net Income Common Stockholders")
        eps          = _col(income_a, col, "Basic EPS", "Diluted EPS")
        ebit         = _col(income_a, col, "EBIT", "Operating Income")

        total_assets        = _col(balance_a, col, "Total Assets")
        current_assets      = _col(balance_a, col, "Current Assets")
        current_liabilities = _col(balance_a, col, "Current Liabilities")
        long_term_debt      = _col(balance_a, col, "Long Term Debt")
        short_term_debt     = _col(balance_a, col, "Current Debt", "Short Long Term Debt")
        cash                = _col(balance_a, col, "Cash And Cash Equivalents", "Cash Financial")
        shares              = _col(balance_a, col, "Ordinary Shares Number", "Share Issued")

        operating_cf = _col(cashflow_a, col, "Operating Cash Flow")

        rec: dict = {
            "instrument_id":             instrument_id,
            "fiscal_year":               d.year,
            "report_date":               d,
            "revenue":                   revenue,
            "gross_profit":              gross_profit,
            "net_income":                net_income,
            "eps":                       eps,
            "ebit":                      ebit,
            "total_assets":              total_assets,
            "current_assets":            current_assets,
            "current_liabilities":       current_liabilities,
            "long_term_debt":            long_term_debt,
            "shares_outstanding_annual": shares,
            "operating_cash_flow":       operating_cf,
            "cash_and_equivalents":      cash,
            "data_source":               "YFINANCE",
        }

        # Derived fields
        ltd = long_term_debt or 0
        std = short_term_debt or 0
        if ltd or std:
            rec["total_debt"] = ltd + std

        if total_assets is not None and current_assets is not None:
            rec["net_fixed_assets"] = max(0.0, total_assets - current_assets)

        if net_income is not None and total_assets:
            rec["roa"] = net_income / total_assets

        if current_assets is not None and current_liabilities:
            rec["current_ratio"] = current_assets / current_liabilities

        if gross_profit is not None and revenue:
            rec["gross_margin"] = gross_profit / revenue

        if revenue is not None and total_assets:
            rec["asset_turnover"] = revenue / total_assets

        if long_term_debt is not None and total_assets:
            rec["leverage_ratio"] = long_term_debt / total_assets

        records.append(rec)

    # Sort oldest-first, compute YoY growth
    records.sort(key=lambda r: r["report_date"])
    for i in range(1, len(records)):
        prev, curr = records[i - 1], records[i]
        if curr.get("revenue") and prev.get("revenue") and prev["revenue"] != 0:
            curr["revenue_yoy_growth"] = (curr["revenue"] - prev["revenue"]) / abs(prev["revenue"])
        if curr.get("eps") and prev.get("eps") and prev["eps"] != 0:
            curr["eps_yoy_growth"] = (curr["eps"] - prev["eps"]) / abs(prev["eps"])

    return records


# ── DB upsert helpers ─────────────────────────────────────────────────────────

_QUARTERLY_REQUIRED = {"instrument_id", "fiscal_year", "fiscal_quarter", "report_date", "data_source"}
_ANNUAL_REQUIRED    = {"instrument_id", "fiscal_year", "report_date", "data_source"}


async def _upsert_quarterly(db, records: list[dict]) -> None:
    for rec in records:
        result = await db.execute(
            select(FundamentalQuarterly).where(
                FundamentalQuarterly.instrument_id  == rec["instrument_id"],
                FundamentalQuarterly.fiscal_year    == rec["fiscal_year"],
                FundamentalQuarterly.fiscal_quarter == rec["fiscal_quarter"],
            )
        )
        existing = result.scalars().first()
        if existing:
            for k, v in rec.items():
                if v is not None:
                    setattr(existing, k, v)
        else:
            db.add(FundamentalQuarterly(
                **{k: v for k, v in rec.items() if v is not None or k in _QUARTERLY_REQUIRED}
            ))


async def _upsert_annual(db, records: list[dict]) -> None:
    for rec in records:
        result = await db.execute(
            select(FundamentalAnnual).where(
                FundamentalAnnual.instrument_id == rec["instrument_id"],
                FundamentalAnnual.fiscal_year   == rec["fiscal_year"],
            )
        )
        existing = result.scalars().first()
        if existing:
            for k, v in rec.items():
                if v is not None:
                    setattr(existing, k, v)
        else:
            db.add(FundamentalAnnual(
                **{k: v for k, v in rec.items() if v is not None or k in _ANNUAL_REQUIRED}
            ))


# ── public API ────────────────────────────────────────────────────────────────

async def run_us_fundamentals_ingestion(
    symbol: str,
    years: int = 5,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> None:
    """
    Fetch and persist quarterly + annual fundamentals for one US ticker.
    `years` is accepted for API compatibility but ignored — yfinance returns
    all available history in a single call.
    """
    if semaphore is None:
        semaphore = asyncio.Semaphore(10)

    logger.info("Fetching yfinance fundamentals for %s", symbol)
    frames = await _fetch_yf_frames(symbol, semaphore)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Instrument).where(
                Instrument.ticker == symbol,
                Instrument.market == "US",
            )
        )
        instrument = result.scalars().first()
        if not instrument:
            logger.error("Instrument %s not found in DB — skipping.", symbol)
            return

        q_records = _build_quarterly_records(instrument.id, frames)
        a_records = _build_annual_records(instrument.id, frames)

        if q_records:
            await _upsert_quarterly(db, q_records)
        if a_records:
            await _upsert_annual(db, a_records)

        await db.commit()
        logger.info(
            "%s: persisted %d quarterly + %d annual records",
            symbol, len(q_records), len(a_records),
        )


async def run_us_fundamentals_batch(
    tickers: list[str],
    *,
    concurrency: int = 10,
) -> dict:
    """
    Batch-ingest fundamentals for multiple US tickers with bounded concurrency.
    """
    semaphore = asyncio.Semaphore(concurrency)
    processed, failed = 0, 0

    async def _one(ticker: str) -> None:
        nonlocal processed, failed
        try:
            await run_us_fundamentals_ingestion(ticker, semaphore=semaphore)
            processed += 1
        except Exception as exc:
            logger.warning("Fundamentals failed for %s: %s", ticker, exc)
            failed += 1

    await asyncio.gather(*[_one(t) for t in tickers])
    return {"processed": processed, "failed": failed, "total": len(tickers)}


if __name__ == "__main__":
    import sys
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    _ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    asyncio.run(run_us_fundamentals_ingestion(_ticker))
