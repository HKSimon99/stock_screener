"""
KR KIS Live Finance Fetcher
============================
Fetches quarterly and annual financial data (EPS, revenue) from the KIS
Developers financial-ratio API at **scoring time**.

Design principle
----------------
KIS is free and can be called any time, so there is no reason to persist
this data to the database.  Live data (current-quarter EPS, investor flows)
that changes quarter-to-quarter or daily is fetched fresh during each nightly
scoring run and used in-memory only.  Only immutable historical data (OpenDART
XBRL) and computed strategy scores are stored persistently.

KIS API endpoint
----------------
  FHKST66430200 — 국내주식 기간별 재무비율
  /uapi/domestic-stock/v1/finance/financial-ratio

  PO_DIV_CODE : Q = quarterly  |  Y = annual

Rate limits
-----------
KIS allows ~20 requests/second per app key.  The bulk fetcher uses an
asyncio.Semaphore to bound concurrency to 15 concurrent calls so we stay
comfortably below the ceiling.

Usage
-----
    from app.services.ingestion.kr_kis_finance import bulk_fetch_kr_finance

    # Returns dict[ticker → KisFinanceData] for all active KR stocks
    kis_data = await bulk_fetch_kr_finance(tickers=["005930", "000660"])
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

KIS_BASE_URL  = "https://openapi.koreainvestment.com:9443"
KIS_PAPER_URL = "https://openapivts.koreainvestment.com:29443"

FINANCE_RATIO_PATH  = "/uapi/domestic-stock/v1/finance/financial-ratio"
TR_ID_FINANCE_RATIO = "FHKST66430200"

# Quarter-end month → (month, last_day)
_Q_END: dict[int, tuple[int, int]] = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}


# ── Data containers ───────────────────────────────────────────────────────────

@dataclass
class KisQuarterlyRecord:
    fiscal_year: int
    fiscal_quarter: int
    report_date: date
    eps: Optional[float] = None
    revenue: Optional[float] = None
    net_income: Optional[float] = None


@dataclass
class KisAnnualRecord:
    fiscal_year: int
    report_date: date
    eps: Optional[float] = None
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    roa: Optional[float] = None


@dataclass
class KisFinanceData:
    ticker: str
    quarterlies: list[KisQuarterlyRecord] = field(default_factory=list)
    annuals: list[KisAnnualRecord] = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_float(value: object) -> Optional[float]:
    if value in (None, "", "-", "N/A"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _quarter_from_month(month: int) -> int:
    """Map quarter-end month to quarter number: 3→1, 6→2, 9→3, 12→4."""
    mapping = {3: 1, 6: 2, 9: 3, 12: 4}
    return mapping.get(month, (month - 1) // 3 + 1)


async def _get_kis_token(app_key: str, app_secret: str, is_paper: bool) -> Optional[str]:
    base = KIS_PAPER_URL if is_paper else KIS_BASE_URL
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{base}/oauth2/tokenP",
                json={"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret},
            )
            resp.raise_for_status()
            return resp.json().get("access_token")
    except Exception as exc:
        logger.error("KIS token error: %s", exc)
        return None


async def _fetch_ratio_rows(
    ticker: str,
    period_type: str,   # "Q" = quarterly, "Y" = annual
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    is_paper: bool,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> list[dict]:
    """Single KIS call under semaphore; returns raw JSON rows."""
    base = KIS_PAPER_URL if is_paper else KIS_BASE_URL
    headers = {
        "authorization": f"Bearer {access_token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": TR_ID_FINANCE_RATIO,
        "content-type": "application/json; charset=utf-8",
    }
    params = {
        "PDNO": ticker,
        "COND_MRKT_DIV_CODE": "J",
        "PO_DIV_CODE": period_type,
    }
    async with semaphore:
        try:
            resp = await client.get(f"{base}{FINANCE_RATIO_PATH}", headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            output = data.get("output") or data.get("output2") or []
            return output if isinstance(output, list) else [output]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("KIS rate limit for %s (%s) — backing off 2s", ticker, period_type)
                await asyncio.sleep(2)
            else:
                logger.debug("KIS finance HTTP %s for %s (%s)", exc.response.status_code, ticker, period_type)
        except Exception as exc:
            logger.debug("KIS finance failed for %s (%s): %s", ticker, period_type, exc)
    return []


def _parse_quarterly_rows(ticker: str, rows: list[dict]) -> list[KisQuarterlyRecord]:
    records: list[KisQuarterlyRecord] = []
    for item in rows:
        stac_yymm = str(item.get("stac_yymm") or item.get("STAC_YYMM") or "")
        if len(stac_yymm) < 6:
            continue
        try:
            yr, mo = int(stac_yymm[:4]), int(stac_yymm[4:6])
        except ValueError:
            continue
        quarter = _quarter_from_month(mo)
        end_mo, end_day = _Q_END.get(quarter, (mo, 30))
        records.append(KisQuarterlyRecord(
            fiscal_year=yr,
            fiscal_quarter=quarter,
            report_date=date(yr, end_mo, end_day),
            eps=_parse_float(item.get("eps") or item.get("EPS")),
            revenue=_parse_float(item.get("sale_totl_prfi") or item.get("SALE_TOTL_PRFI")),
            net_income=_parse_float(item.get("thtr_ntin") or item.get("THTR_NTIN")),
        ))
    return sorted(records, key=lambda r: (r.fiscal_year, r.fiscal_quarter))


def _parse_annual_rows(ticker: str, rows: list[dict]) -> list[KisAnnualRecord]:
    records: list[KisAnnualRecord] = []
    for item in rows:
        stac_yymm = str(item.get("stac_yymm") or item.get("STAC_YYMM") or "")
        if len(stac_yymm) < 6:
            continue
        try:
            yr = int(stac_yymm[:4])
        except ValueError:
            continue
        records.append(KisAnnualRecord(
            fiscal_year=yr,
            report_date=date(yr, 12, 31),
            eps=_parse_float(item.get("eps") or item.get("EPS")),
            revenue=_parse_float(item.get("sale_totl_prfi") or item.get("SALE_TOTL_PRFI")),
            net_income=_parse_float(item.get("thtr_ntin") or item.get("THTR_NTIN")),
            roa=_parse_float(item.get("roa_val") or item.get("ROA_VAL") or item.get("roa")),
        ))
    return sorted(records, key=lambda r: r.fiscal_year)


# ── Public API ────────────────────────────────────────────────────────────────

async def bulk_fetch_kr_finance(
    tickers: list[str],
    *,
    concurrency: int = 15,
) -> dict[str, KisFinanceData]:
    """
    Batch-fetch KIS financial ratio data for a list of KR tickers.

    Uses a semaphore to stay within KIS rate limits (~20 req/sec).
    Each ticker requires 2 calls (quarterly + annual) made concurrently.

    Returns:
        dict mapping ticker → KisFinanceData (may be missing tickers on failure)
    """
    app_key    = os.environ.get("KIS_APP_KEY", "")
    app_secret = os.environ.get("KIS_APP_SECRET", "")
    is_paper   = os.environ.get("KIS_ENV", "paper").lower() == "paper"

    if not app_key or not app_secret:
        logger.warning("KIS_APP_KEY / KIS_APP_SECRET not set — skipping live KIS finance fetch.")
        return {}

    access_token = await _get_kis_token(app_key, app_secret, is_paper)
    if not access_token:
        logger.warning("Could not obtain KIS access token — skipping live finance fetch.")
        return {}

    if not tickers:
        return {}

    semaphore = asyncio.Semaphore(concurrency)
    result: dict[str, KisFinanceData] = {}

    # Use a single shared client for connection pooling
    async with httpx.AsyncClient(timeout=15, limits=httpx.Limits(max_connections=concurrency + 5)) as client:

        async def _fetch_one(ticker: str) -> tuple[str, KisFinanceData]:
            q_rows, a_rows = await asyncio.gather(
                _fetch_ratio_rows(
                    ticker, "Q",
                    access_token=access_token, app_key=app_key, app_secret=app_secret,
                    is_paper=is_paper, client=client, semaphore=semaphore,
                ),
                _fetch_ratio_rows(
                    ticker, "Y",
                    access_token=access_token, app_key=app_key, app_secret=app_secret,
                    is_paper=is_paper, client=client, semaphore=semaphore,
                ),
            )
            return ticker, KisFinanceData(
                ticker=ticker,
                quarterlies=_parse_quarterly_rows(ticker, q_rows),
                annuals=_parse_annual_rows(ticker, a_rows),
            )

        tasks = [_fetch_one(t) for t in tickers]
        fetched = await asyncio.gather(*tasks, return_exceptions=True)

    for item in fetched:
        if isinstance(item, Exception):
            logger.debug("KIS finance gather error: %s", item)
            continue
        ticker, data = item
        result[ticker] = data

    logger.info(
        "KIS live finance fetch: %d/%d tickers returned data",
        len(result),
        len(tickers),
    )
    return result


def merge_kis_quarterlies(
    db_quarterlies: list,
    kis_data: Optional[KisFinanceData],
) -> list:
    """
    Merge KIS live quarterly records into the DB quarterly list.

    - DB rows (OpenDART) are authoritative — never replaced.
    - KIS rows that fill gaps (fiscal_year/quarter not in DB) are appended.
    - Result is sorted oldest-first.

    Works with either ORM FundamentalQuarterly objects or scoring_context
    QuarterlyReport dataclass instances — duck-typed on `.fiscal_year` and
    `.fiscal_quarter`.
    """
    if not kis_data or not kis_data.quarterlies:
        return db_quarterlies

    # Build set of (year, quarter) already present in DB
    existing_keys = {(r.fiscal_year, r.fiscal_quarter) for r in db_quarterlies}

    # Build KisQuarterlyRecord → QuarterlyReport-compatible shim for missing gaps
    from app.services.scoring_context import QuarterlyReport  # local import avoids circulars

    extra: list = []
    for kr in kis_data.quarterlies:
        key = (kr.fiscal_year, kr.fiscal_quarter)
        if key in existing_keys:
            continue
        # Wrap as a QuarterlyReport so the CANSLIM engine handles it uniformly
        extra.append(QuarterlyReport(
            fiscal_year=kr.fiscal_year,
            fiscal_quarter=kr.fiscal_quarter,
            report_date=kr.report_date,
            eps=kr.eps,
            eps_yoy_growth=None,        # computed later by engine if needed
            revenue_yoy_growth=None,
        ))

    if not extra:
        return db_quarterlies

    combined = list(db_quarterlies) + extra
    combined.sort(key=lambda r: (r.fiscal_year, r.fiscal_quarter))
    return combined


def merge_kis_annuals(
    db_annuals: list,
    kis_data: Optional[KisFinanceData],
) -> list:
    """
    Merge KIS live annual records into the DB annual list.

    Same rules as merge_kis_quarterlies — DB data wins on conflict.
    """
    if not kis_data or not kis_data.annuals:
        return db_annuals

    existing_years = {r.fiscal_year for r in db_annuals}

    from app.services.scoring_context import AnnualReport  # local import

    extra: list = []
    for ar in kis_data.annuals:
        if ar.fiscal_year in existing_years:
            continue
        extra.append(AnnualReport(
            fiscal_year=ar.fiscal_year,
            report_date=ar.report_date,
            revenue=ar.revenue,
            gross_profit=None,
            net_income=ar.net_income,
            eps=ar.eps,
            total_assets=None,
            current_assets=None,
            current_liabilities=None,
            long_term_debt=None,
            shares_outstanding_annual=None,
            operating_cash_flow=None,
            ebit=None,
            total_debt=None,
            cash_and_equivalents=None,
            net_fixed_assets=None,
        ))

    if not extra:
        return db_annuals

    combined = list(db_annuals) + extra
    combined.sort(key=lambda r: r.fiscal_year)
    return combined
