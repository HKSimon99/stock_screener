"""
US Institutional Ownership Ingestion — Step 4.1
================================================
Parses SEC EDGAR 13F bulk data via edgartools to extract institutional
ownership metrics per instrument:

  - num_institutional_owners   : count of 13F filers holding the stock
  - institutional_pct          : institutional shares / shares_outstanding
  - qoq_owner_change           : net new filers vs prior quarter
  - top_fund_quality_score     : avg RS-like performance rank of top-10 holders

Data flow:
  1. Pull the most recent 13F-HR filings for each quarter from SEC EDGAR
  2. For each instrument (matched by ticker), aggregate holdings across all filers
  3. Compute metrics and upsert into institutional_ownership

Notes:
  - 13F bulk XML from SEC EDGAR has no API key requirement
  - Filings are quarterly (Q1/Q2/Q3/Q4), ~45-day lag after period end
  - edgartools Company.get_filings(form="13F-HR") accesses this
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import date
from typing import Optional

from edgar import set_identity, Company, get_filings
from sqlalchemy import select, desc

from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.fundamental import FundamentalAnnual
from app.models.institutional import InstitutionalOwnership

logger = logging.getLogger(__name__)

# SEC requires identity disclosure for bulk access
set_identity("ConsensusApp consensus@example.com")

# Top institutional holders to use for quality score computation
TOP_N_FUNDS = 10

# Quality proxies: well-known high-performing fund managers get higher scores.
# This is a lightweight heuristic — a full implementation would track fund
# historical returns. Values are 0-100.
FUND_QUALITY_MAP: dict[str, float] = {
    "VANGUARD": 72,
    "BLACKROCK": 74,
    "FIDELITY": 78,
    "T. ROWE PRICE": 82,
    "CAPITAL RESEARCH": 80,
    "WELLINGTON": 81,
    "BAILLIE GIFFORD": 85,
    "PRIMECAP": 88,
    "Polen CAPITAL": 87,
    "ARTISAN": 84,
    "BROWN ADVISORY": 83,
    "AMERICAN FUNDS": 79,
    "SOROS": 80,
    "TIGER": 83,
    "DUQUESNE": 85,
    "BERKSHIRE": 90,
}


def _fund_quality_score(filer_name: str) -> float:
    """Return a quality score for a 13F filer based on name heuristics."""
    name_upper = filer_name.upper()
    for key, score in FUND_QUALITY_MAP.items():
        if key in name_upper:
            return score
    return 65.0  # default neutral score


def _parse_13f_holdings(filing) -> dict[str, float]:
    """
    Extract a {ticker: shares_held} dict from a single 13F-HR filing object.
    Returns an empty dict on any parse error.
    """
    holdings: dict[str, float] = {}
    try:
        obj = filing.obj()
        if obj is None:
            return holdings
        # edgartools returns a ThirteenF object with .infotable attribute
        if hasattr(obj, "infotable") and obj.infotable is not None:
            for row in obj.infotable.itertuples():
                ticker = getattr(row, "ticker", None) or getattr(row, "cusip", None)
                shares = getattr(row, "value", None) or getattr(row, "sshPrnamt", None)
                if ticker and shares:
                    try:
                        holdings[str(ticker).upper()] = float(shares)
                    except (ValueError, TypeError):
                        pass
    except Exception as exc:
        logger.debug("Could not parse 13F filing: %s", exc)
    return holdings


async def ingest_us_institutional(
    tickers: Optional[list[str]] = None,
    report_date: Optional[date] = None,
    max_filers: int = 200,
) -> dict:
    """
    Ingest institutional ownership for a list of US tickers.

    Args:
        tickers:     List of tickers to process. None = all active US stocks.
        report_date: Override the report date (defaults to today / most recent quarter).
        max_filers:  Max number of 13F filers to scan (performance guard).

    Returns:
        Summary dict with counts of processed/skipped instruments.
    """
    if report_date is None:
        report_date = date.today()

    async with AsyncSessionLocal() as db:
        # Fetch instruments
        stmt = (
            select(Instrument)
            .where(
                Instrument.market == "US",
                Instrument.asset_type == "stock",
                Instrument.is_active.is_(True),
            )
            .order_by(Instrument.ticker.asc())
        )
        if tickers:
            tickers_upper = [t.upper() for t in tickers]
            stmt = stmt.where(Instrument.ticker.in_(tickers_upper))

        result = await db.execute(stmt)
        instruments = result.scalars().all()

        if not instruments:
            logger.warning("No active US instruments found for institutional ingestion.")
            return {"processed": 0, "skipped": 0}

        ticker_to_inst: dict[str, Instrument] = {inst.ticker: inst for inst in instruments}
        target_tickers = set(ticker_to_inst.keys())

        logger.info(
            "Starting 13F institutional ingestion for %d instruments", len(instruments)
        )

        # ── Aggregate holdings across all recent 13F filers ─────────────────
        # holdings_agg[ticker] = {filer_name: shares}
        holdings_agg: dict[str, dict[str, float]] = defaultdict(dict)

        try:
            # Get the most recent quarterly 13F-HR filings
            filings = get_filings(form="13F-HR", date=str(report_date))
            filer_count = 0

            for filing in filings:
                if filer_count >= max_filers:
                    break
                filer_name = getattr(filing, "company", "") or ""
                parsed = _parse_13f_holdings(filing)

                for ticker, shares in parsed.items():
                    if ticker in target_tickers:
                        holdings_agg[ticker][filer_name] = shares

                filer_count += 1
                if filer_count % 25 == 0:
                    logger.info("Scanned %d 13F filers...", filer_count)

        except Exception as exc:
            logger.error("Failed to fetch 13F filings: %s", exc)
            return {"processed": 0, "skipped": len(instruments), "error": str(exc)}

        logger.info(
            "Scanned %d filers. Found holdings for %d/%d tickers",
            filer_count,
            len(holdings_agg),
            len(target_tickers),
        )

        # ── Compute per-ticker metrics ───────────────────────────────────────
        processed = 0
        skipped = 0

        for ticker, inst in ticker_to_inst.items():
            filer_holdings = holdings_agg.get(ticker, {})
            num_owners = len(filer_holdings)

            if num_owners == 0:
                # No 13F data found; skip rather than store 0s
                skipped += 1
                continue

            # Total institutional shares
            total_inst_shares = sum(filer_holdings.values())

            # shares_outstanding from most recent annual fundamental
            shares_out_q = await db.execute(
                select(FundamentalAnnual.shares_outstanding_annual)
                .where(FundamentalAnnual.instrument_id == inst.id)
                .order_by(desc(FundamentalAnnual.report_date))
                .limit(1)
            )
            shares_out_row = shares_out_q.scalar_one_or_none()
            shares_outstanding = float(shares_out_row) if shares_out_row else None

            # institutional_pct
            if shares_outstanding and shares_outstanding > 0:
                institutional_pct = min(1.0, total_inst_shares / shares_outstanding)
            else:
                # Fall back to instrument-level shares_outstanding
                inst_shares = float(inst.shares_outstanding) if inst.shares_outstanding else None
                institutional_pct = (
                    min(1.0, total_inst_shares / inst_shares) if inst_shares else None
                )

            # Top-10 fund quality score
            top_filers = sorted(filer_holdings.items(), key=lambda x: x[1], reverse=True)[:TOP_N_FUNDS]
            if top_filers:
                quality_scores = [_fund_quality_score(name) for name, _ in top_filers]
                top_fund_quality_score = sum(quality_scores) / len(quality_scores)
            else:
                top_fund_quality_score = None

            # QoQ owner change: compare with prior quarter's row
            prior_q = await db.execute(
                select(InstitutionalOwnership.num_institutional_owners)
                .where(
                    InstitutionalOwnership.instrument_id == inst.id,
                    InstitutionalOwnership.report_date < report_date,
                )
                .order_by(desc(InstitutionalOwnership.report_date))
                .limit(1)
            )
            prior_owners = prior_q.scalar_one_or_none()
            qoq_change = (num_owners - prior_owners) if prior_owners is not None else None

            # Upsert
            existing_q = await db.execute(
                select(InstitutionalOwnership).where(
                    InstitutionalOwnership.instrument_id == inst.id,
                    InstitutionalOwnership.report_date == report_date,
                )
            )
            existing = existing_q.scalars().first()

            if existing:
                existing.num_institutional_owners = num_owners
                existing.institutional_pct = institutional_pct
                existing.top_fund_quality_score = top_fund_quality_score
                existing.qoq_owner_change = qoq_change
                existing.data_source = "SEC_13F"
            else:
                db.add(InstitutionalOwnership(
                    instrument_id=inst.id,
                    report_date=report_date,
                    num_institutional_owners=num_owners,
                    institutional_pct=institutional_pct,
                    top_fund_quality_score=top_fund_quality_score,
                    qoq_owner_change=qoq_change,
                    data_source="SEC_13F",
                ))

            processed += 1

        await db.commit()
        logger.info(
            "US institutional ingestion complete: %d processed, %d skipped",
            processed,
            skipped,
        )

    return {"processed": processed, "skipped": skipped}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    tickers_arg = sys.argv[1:] or None
    result = asyncio.run(ingest_us_institutional(tickers=tickers_arg))
    print(result)
