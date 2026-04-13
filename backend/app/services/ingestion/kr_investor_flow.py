"""
KR Investor Flow Ingestion — Step 4.2
======================================
Fetches daily foreign / institutional / individual net buy-sell data from the
KIS Developers investor-category API and stores 30-day rolling sums in the
institutional_ownership table.

KIS API endpoint used:
  FHKST01010900 — 주식 투자자별 매매동향 (Investor Category Trading Trend)

Data flow:
  1. For each KR instrument, call KIS REST to get daily investor flows
  2. Compute 30-day rolling net buy/sell sums for each category
  3. Apply chaebol cross-holding flag from instruments table
  4. Upsert into institutional_ownership (KR-side fields)
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, timedelta
from typing import Optional

import httpx
from sqlalchemy import select, desc

from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.institutional import InstitutionalOwnership
from app.services.korea.chaebol_filter import is_chaebol_cross

logger = logging.getLogger(__name__)

KIS_BASE_URL = "https://openapi.koreainvestment.com:9443"
KIS_PAPER_URL = "https://openapivts.koreainvestment.com:29443"

# KIS investor flow API endpoint
INVESTOR_FLOW_PATH = "/uapi/domestic-stock/v1/quotations/inquire-investor"


async def _get_kis_token(app_key: str, app_secret: str, is_paper: bool) -> Optional[str]:
    """Obtain a KIS OAuth access token."""
    base = KIS_PAPER_URL if is_paper else KIS_BASE_URL
    url = f"{base}/oauth2/tokenP"
    payload = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("access_token")
    except Exception as exc:
        logger.error("Failed to obtain KIS token: %s", exc)
        return None


async def _fetch_investor_flow(
    ticker: str,
    access_token: str,
    app_key: str,
    is_paper: bool,
    days: int = 30,
) -> list[dict]:
    """
    Fetch daily investor category data for a single ticker.
    Returns list of dicts with keys: date, foreign_net, institutional_net, individual_net.
    """
    base = KIS_PAPER_URL if is_paper else KIS_BASE_URL
    url = f"{base}{INVESTOR_FLOW_PATH}"

    end_date = date.today()
    start_date = end_date - timedelta(days=days + 10)  # buffer for weekends/holidays

    headers = {
        "authorization": f"Bearer {access_token}",
        "appkey": app_key,
        "appsecret": os.environ.get("KIS_APP_SECRET", ""),
        "tr_id": "FHKST01010900",
        "content-type": "application/json; charset=utf-8",
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",  # KOSPI/KOSDAQ
        "FID_INPUT_ISCD": ticker,
        "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
        "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
    }

    rows: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        output = data.get("output") or data.get("output2") or []
        if isinstance(output, dict):
            output = [output]

        for item in output:
            try:
                row_date_str = item.get("stck_bsop_date") or item.get("STCK_BSOP_DATE") or ""
                if not row_date_str or len(row_date_str) < 8:
                    continue
                row_date = date(
                    int(row_date_str[:4]),
                    int(row_date_str[4:6]),
                    int(row_date_str[6:8]),
                )
                # Net buy = buy - sell; field names may vary
                foreign_net = int(
                    item.get("frgn_ntby_qty") or item.get("FRGN_NTBY_QTY") or 0
                )
                inst_net = int(
                    item.get("orgn_ntby_qty") or item.get("ORGN_NTBY_QTY") or 0
                )
                indiv_net = int(
                    item.get("indvd_ntby_qty") or item.get("INDVD_NTBY_QTY") or 0
                )
                rows.append({
                    "date": row_date,
                    "foreign_net": foreign_net,
                    "institutional_net": inst_net,
                    "individual_net": indiv_net,
                })
            except (ValueError, TypeError):
                continue

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            logger.warning("KIS rate limit hit for %s — sleeping 2s", ticker)
            await asyncio.sleep(2)
        else:
            logger.error("KIS HTTP error for %s: %s", ticker, exc)
    except Exception as exc:
        logger.error("KIS flow fetch failed for %s: %s", ticker, exc)

    return sorted(rows, key=lambda r: r["date"])


def _rolling_sum(rows: list[dict], field: str, days: int = 30) -> int:
    """Sum `field` over the last `days` calendar days."""
    if not rows:
        return 0
    cutoff = rows[-1]["date"] - timedelta(days=days)
    return sum(r[field] for r in rows if r["date"] >= cutoff)


async def ingest_kr_investor_flows(
    tickers: Optional[list[str]] = None,
    report_date: Optional[date] = None,
) -> dict:
    """
    Ingest KR investor category flows for a list of tickers.

    Args:
        tickers:     KR tickers (6-digit codes). None = all active KR stocks.
        report_date: Reference date for the row (defaults to today).

    Returns:
        Summary dict with processed/skipped counts.
    """
    if report_date is None:
        report_date = date.today()

    app_key = os.environ.get("KIS_APP_KEY", "")
    app_secret = os.environ.get("KIS_APP_SECRET", "")
    is_paper = os.environ.get("KIS_ENV", "paper").lower() == "paper"

    if not app_key or not app_secret:
        logger.error("KIS_APP_KEY / KIS_APP_SECRET not set. Skipping KR investor flows.")
        return {"processed": 0, "skipped": 0, "error": "KIS credentials missing"}

    # Obtain access token
    access_token = await _get_kis_token(app_key, app_secret, is_paper)
    if not access_token:
        return {"processed": 0, "skipped": 0, "error": "KIS token acquisition failed"}

    async with AsyncSessionLocal() as db:
        # Fetch instruments
        stmt = (
            select(Instrument)
            .where(
                Instrument.market == "KR",
                Instrument.asset_type == "stock",
                Instrument.is_active.is_(True),
            )
            .order_by(Instrument.ticker.asc())
        )
        if tickers:
            stmt = stmt.where(Instrument.ticker.in_(tickers))

        result = await db.execute(stmt)
        instruments = result.scalars().all()

        if not instruments:
            logger.warning("No active KR instruments found for investor flow ingestion.")
            return {"processed": 0, "skipped": 0}

        logger.info(
            "Starting KR investor flow ingestion for %d instruments", len(instruments)
        )

        processed = 0
        skipped = 0

        for inst in instruments:
            try:
                rows = await _fetch_investor_flow(
                    ticker=inst.ticker,
                    access_token=access_token,
                    app_key=app_key,
                    is_paper=is_paper,
                    days=40,
                )

                if not rows:
                    skipped += 1
                    continue

                # 30-day rolling sums
                foreign_net_30d = _rolling_sum(rows, "foreign_net", days=30)
                inst_net_30d = _rolling_sum(rows, "institutional_net", days=30)
                indiv_net_30d = _rolling_sum(rows, "individual_net", days=30)

                # Foreign ownership pct from most recent row (if available)
                # KIS flow API may not return total pct — use inst model flag
                foreign_pct = float(inst.float_shares / inst.shares_outstanding) if (
                    inst.float_shares and inst.shares_outstanding and inst.shares_outstanding > 0
                ) else None

                # Chaebol filter
                chaebol_flag = inst.is_chaebol_cross

                # Upsert
                existing_q = await db.execute(
                    select(InstitutionalOwnership).where(
                        InstitutionalOwnership.instrument_id == inst.id,
                        InstitutionalOwnership.report_date == report_date,
                    )
                )
                existing = existing_q.scalars().first()

                if existing:
                    existing.foreign_ownership_pct = foreign_pct
                    existing.foreign_net_buy_30d = foreign_net_30d
                    existing.institutional_net_buy_30d = inst_net_30d
                    existing.individual_net_buy_30d = indiv_net_30d
                    existing.data_source = "KIS_INVESTOR_FLOW"
                else:
                    db.add(InstitutionalOwnership(
                        instrument_id=inst.id,
                        report_date=report_date,
                        foreign_ownership_pct=foreign_pct,
                        foreign_net_buy_30d=foreign_net_30d,
                        institutional_net_buy_30d=inst_net_30d,
                        individual_net_buy_30d=indiv_net_30d,
                        data_source="KIS_INVESTOR_FLOW",
                    ))

                processed += 1

                # KIS rate limit: 20 req/sec — be conservative
                await asyncio.sleep(0.06)

            except Exception as exc:
                logger.error("Investor flow failed for %s: %s", inst.ticker, exc)
                skipped += 1

        await db.commit()
        logger.info(
            "KR investor flow ingestion complete: %d processed, %d skipped",
            processed,
            skipped,
        )

    return {"processed": processed, "skipped": skipped}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    tickers_arg = sys.argv[1:] or None
    result = asyncio.run(ingest_kr_investor_flows(tickers=tickers_arg))
    print(result)
