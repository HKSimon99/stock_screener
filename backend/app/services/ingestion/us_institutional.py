"""
US Institutional Ownership — Live yfinance Fetcher
====================================================
Fetches institutional holder data from Yahoo Finance at **scoring time**.
No DB writes — same architecture as kr_kis_finance.py.

Design principle
----------------
Institutional ownership counts change every quarter and Yahoo Finance makes
this data freely available on demand.  There is no reason to persist it;
fetching live during the nightly scoring run is fast enough (~1 HTTP call
per ticker) and always returns the latest data.

yfinance endpoints used
-----------------------
  yf.Ticker(t).institutional_holders
      DataFrame: Holder | Shares | Date Reported | % Out | Value

  yf.Ticker(t).major_holders
      DataFrame: Value | Breakdown  (% held by institutions, % by insiders)

Rate limits
-----------
Yahoo Finance is undocumented but tolerant.  Semaphore(15) keeps us
within safe concurrency bounds.

Usage
-----
    from app.services.ingestion.us_institutional import bulk_fetch_us_institutional

    data = await bulk_fetch_us_institutional(tickers=["AAPL", "MSFT"])
    # data["AAPL"].num_institutional_owners → int
    # data["AAPL"].institutional_pct         → float (0–1)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ── Fund quality heuristic ────────────────────────────────────────────────────
# Well-known institutional investors get a higher quality score (0–100).
# This is a lightweight proxy — a full implementation would track historical returns.

_FUND_QUALITY_MAP: dict[str, float] = {
    "VANGUARD":          72,
    "BLACKROCK":         74,
    "FIDELITY":          78,
    "T. ROWE PRICE":     82,
    "CAPITAL RESEARCH":  80,
    "WELLINGTON":        81,
    "BAILLIE GIFFORD":   85,
    "PRIMECAP":          88,
    "POLEN CAPITAL":     87,
    "ARTISAN":           84,
    "BROWN ADVISORY":    83,
    "AMERICAN FUNDS":    79,
    "BERKSHIRE":         90,
    "TIGER":             83,
    "DUQUESNE":          85,
    "SOROS":             80,
}


def _fund_quality(name: str) -> float:
    n = name.upper()
    for key, score in _FUND_QUALITY_MAP.items():
        if key in n:
            return score
    return 65.0  # neutral default


# ── Data containers ───────────────────────────────────────────────────────────

@dataclass
class HolderRecord:
    institution_name: str
    shares: float
    pct_out: Optional[float] = None


@dataclass
class UsInstitutionalData:
    ticker: str
    report_date: Optional[date] = None
    num_institutional_owners: Optional[int] = None
    institutional_pct: Optional[float] = None
    top_fund_quality_score: Optional[float] = None
    holders: list[HolderRecord] = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_float(val) -> Optional[float]:
    try:
        v = float(val)
        return v if pd.notna(v) else None
    except (TypeError, ValueError):
        return None


def _parse_holders(holders_df: pd.DataFrame) -> tuple[list[HolderRecord], Optional[date], Optional[float]]:
    """
    Parse yfinance institutional_holders DataFrame.
    Returns (holders, latest_report_date, total_institutional_pct).
    """
    holders: list[HolderRecord] = []
    latest_date: Optional[date] = None
    total_pct: Optional[float] = None

    if holders_df is None or holders_df.empty:
        return holders, latest_date, total_pct

    pct_sum = 0.0
    pct_count = 0

    for _, row in holders_df.iterrows():
        # Column names vary slightly across yfinance versions
        name   = str(row.get("Holder") or row.get("Institution") or "").strip()
        shares = _safe_float(row.get("Shares") or row.get("Value"))

        # Date Reported
        dr = row.get("Date Reported") or row.get("dateReported")
        if dr is not None:
            try:
                d = pd.Timestamp(dr).date()
                if latest_date is None or d > latest_date:
                    latest_date = d
            except Exception:
                pass

        # % Out
        pct = _safe_float(row.get("% Out") or row.get("pctHeld"))

        if name and shares:
            holders.append(HolderRecord(institution_name=name, shares=shares, pct_out=pct))
            if pct is not None:
                pct_sum   += pct
                pct_count += 1

    if pct_count:
        total_pct = min(1.0, pct_sum)

    return holders, latest_date, total_pct


def _parse_major_holders(major_df: pd.DataFrame) -> Optional[float]:
    """
    Try to extract total institutional % from major_holders DataFrame.
    Returns a value in [0, 1] or None.
    """
    if major_df is None or major_df.empty:
        return None
    try:
        # yfinance may return rows labelled "% of Shares Held by Institutions" etc.
        for col in major_df.columns:
            if "institution" in str(col).lower():
                val = _safe_float(major_df.iloc[0][col])
                if val is not None:
                    return min(1.0, val)
        # Alternative layout: rows with "Breakdown" column
        if "Breakdown" in major_df.columns:
            for _, row in major_df.iterrows():
                desc = str(row.get("Breakdown") or "").lower()
                if "institution" in desc:
                    val = _safe_float(row.get("Value") or row.get("value"))
                    if val is not None:
                        return min(1.0, val)
    except Exception:
        pass
    return None


# ── Single-ticker fetch ───────────────────────────────────────────────────────

async def _fetch_one(ticker: str, semaphore: asyncio.Semaphore) -> UsInstitutionalData:
    async with semaphore:
        try:
            t = await asyncio.to_thread(yf.Ticker, ticker)
            holders_df = await asyncio.to_thread(lambda: t.institutional_holders)
            major_df   = await asyncio.to_thread(lambda: t.major_holders)
        except Exception as exc:
            logger.debug("yfinance institutional fetch failed for %s: %s", ticker, exc)
            return UsInstitutionalData(ticker=ticker)

    data = UsInstitutionalData(ticker=ticker)

    holders, report_date, holders_pct = _parse_holders(holders_df)
    data.holders                = holders
    data.num_institutional_owners = len(holders) if holders else None
    data.report_date            = report_date
    data.institutional_pct      = holders_pct

    # major_holders gives a more reliable total institutional %
    major_pct = _parse_major_holders(major_df)
    if major_pct is not None:
        data.institutional_pct = major_pct

    # Top-10 quality score
    top10 = sorted(holders, key=lambda h: h.shares, reverse=True)[:10]
    if top10:
        data.top_fund_quality_score = sum(
            _fund_quality(h.institution_name) for h in top10
        ) / len(top10)

    return data


# ── Public API ────────────────────────────────────────────────────────────────

async def bulk_fetch_us_institutional(
    tickers: list[str],
    *,
    concurrency: int = 15,
) -> dict[str, UsInstitutionalData]:
    """
    Batch-fetch live institutional ownership data for a list of US tickers.

    Uses a semaphore to stay within Yahoo Finance rate limits.
    Returns dict[ticker → UsInstitutionalData].  Tickers that fail are omitted.
    """
    if not tickers:
        return {}

    semaphore = asyncio.Semaphore(concurrency)
    fetched = await asyncio.gather(
        *[_fetch_one(t, semaphore) for t in tickers],
        return_exceptions=True,
    )

    out: dict[str, UsInstitutionalData] = {}
    for item in fetched:
        if isinstance(item, Exception):
            logger.debug("Institutional gather error: %s", item)
            continue
        out[item.ticker] = item

    logger.info(
        "US institutional fetch: %d/%d tickers returned holder data",
        sum(1 for v in out.values() if v.num_institutional_owners),
        len(tickers),
    )
    return out
