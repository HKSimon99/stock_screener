import asyncio
import logging
from datetime import date
from typing import Optional, List, Dict, Any
import math

import pandas as pd
from edgar import set_identity, Company
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception

from app.core.database import AsyncSessionLocal
from app.models.fundamental import FundamentalAnnual, FundamentalQuarterly
from app.models.instrument import Instrument
from sqlalchemy import select, String, cast

logger = logging.getLogger(__name__)

# Must set identity for SEC EDGAR access
set_identity('ConsensusApp consensus@example.com')

def is_rate_limit_error(exc: Exception) -> bool:
    """Check if exception is from EDGAR rate limiting (429/503)."""
    # edgartools wraps HTTPStatusError from requests/httpx
    exc_str = str(exc)
    return '429' in exc_str or '503' in exc_str

class EdgarFundamentalIngester:
    def __init__(self):
        # Mappings of our standard attributes to possible SEC XBRL concepts
        self.annual_concept_map = {
            'net_income': ['NetIncomeLoss'],
            'total_assets': ['Assets'],
            'total_liabilities': ['Liabilities'],
            'current_assets': ['AssetsCurrent'],
            'current_liabilities': ['LiabilitiesCurrent'],
            'operating_cash_flow': ['NetCashProvidedByUsedInOperatingActivities'],
            'long_term_debt': ['LongTermDebt', 'LongTermDebtNoncurrent'],
            'gross_profit': ['GrossProfit'],
            'revenue': ['Revenues', 'SalesRevenueNet', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'RevenuesNetOfYear2015To2016'],
            'shares_outstanding': ['CommonStockSharesOutstanding', 'EntityCommonStockSharesOutstanding'],
            'eps': ['EarningsPerShareBasic', 'EarningsPerShareDiluted']
        }
        
        self.quarterly_concept_map = {
            'net_income': ['NetIncomeLoss'],
            'revenue': ['Revenues', 'SalesRevenueNet', 'RevenueFromContractWithCustomerExcludingAssessedTax'],
            'eps': ['EarningsPerShareBasic', 'EarningsPerShareDiluted']
        }

    def _prepare_annual_record(self, record_dict: Dict[str, Any]) -> Dict[str, Any]:
        prepared = {
            "instrument_id": record_dict["instrument_id"],
            "fiscal_year": record_dict["fiscal_year"],
            "report_date": record_dict["report_date"],
            "revenue": record_dict.get("revenue"),
            "gross_profit": record_dict.get("gross_profit"),
            "net_income": record_dict.get("net_income"),
            "eps": record_dict.get("eps"),
            "eps_yoy_growth": record_dict.get("eps_yoy_growth"),
            "total_assets": record_dict.get("total_assets"),
            "current_assets": record_dict.get("current_assets"),
            "current_liabilities": record_dict.get("current_liabilities"),
            "long_term_debt": record_dict.get("long_term_debt"),
            "shares_outstanding_annual": record_dict.get("shares_outstanding"),
            "operating_cash_flow": record_dict.get("operating_cash_flow"),
            "data_source": "EDGAR",
        }

        total_assets = prepared.get("total_assets")
        revenue = prepared.get("revenue")
        current_liabilities = prepared.get("current_liabilities")

        if prepared.get("net_income") is not None and total_assets:
            prepared["roa"] = prepared["net_income"] / total_assets
        if prepared.get("current_assets") is not None and current_liabilities:
            prepared["current_ratio"] = prepared["current_assets"] / current_liabilities
        if prepared.get("gross_profit") is not None and revenue:
            prepared["gross_margin"] = prepared["gross_profit"] / revenue
        if revenue is not None and total_assets:
            prepared["asset_turnover"] = revenue / total_assets
        if prepared.get("long_term_debt") is not None and total_assets:
            prepared["leverage_ratio"] = prepared["long_term_debt"] / total_assets

        required_keys = {"instrument_id", "fiscal_year", "report_date", "data_source"}
        return {
            key: value
            for key, value in prepared.items()
            if value is not None or key in required_keys
        }

    def _extract_fact(self, df: pd.DataFrame, concept_list: List[str]) -> Optional[float]:
        """Extracts the most canonical value for a list of possible XBRL concept names."""
        for concept in concept_list:
            subset = df[df['concept'].str.endswith(':' + concept, na=False)]
            if not subset.empty:
                # Fallback filter for dimensions to get the primary consolidated value
                if 'is_dimensioned' in subset.columns:
                    # Filter for non-dimensioned facts
                    primary = subset[subset['is_dimensioned'] == False]
                    if not primary.empty:
                        subset = primary
                    elif 'dimension' in subset.columns:
                        # Fallback for old style dimension checks
                        primary = subset[subset['dimension'].isna() | (subset['dimension'] == '')]
                        if not primary.empty:
                            subset = primary

                if not subset.empty:
                    # Sort by the end period to get the most relevant
                    if 'period_end' in subset.columns and not subset['period_end'].isna().all():
                        subset = subset.sort_values(by='period_end', ascending=False)
                    elif 'period_instant' in subset.columns and not subset['period_instant'].isna().all():
                        subset = subset.sort_values(by='period_instant', ascending=False)
                    
                    val = subset.iloc[0]['value']
                    try:
                        return float(val) if not pd.isna(val) else None
                    except (ValueError, TypeError):
                        return None
        return None

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        retry=retry_if_exception(is_rate_limit_error),
        reraise=True
    )
    async def ingest_fundamentals(self, ticker: str, years: int = 5):
        """Fetches 10-K and 10-Q for the specified ticker and upserts into database.

        Retries automatically on 429 (Too Many Requests) or 503 (Service Unavailable)
        with exponential backoff (2s, 4s, 8s... max 60s).
        """
        logger.info(f"Starting US Fundamental ingestion for {ticker} over {years} years")
        
        async with AsyncSessionLocal() as db:
            # 1. Verify instrument exists
            stmt = select(Instrument).where(Instrument.ticker == ticker, Instrument.market == "US")
            result = await db.execute(stmt)
            instrument = result.scalars().first()
            
            if not instrument:
                logger.error(f"Cannot ingest fundamentals: Instrument {ticker} not found in DB.")
                return

            try:
                c = Company(ticker)
            except Exception as e:
                logger.error(f"Failed to initialize edgartools Company for {ticker}: {e}")
                return

            # --- Annual Fundamentals (10-K)
            logger.info(f"Fetching 10-K filings for {ticker}")
            try:
                filings_10k_list = c.get_filings(form="10-K").head(years)
                
                annual_records = []
                for filing in filings_10k_list:
                    try:
                        df = filing.xbrl().facts.to_dataframe()

                        record_dict = {
                            "instrument_id": instrument.id,
                            "fiscal_year": filing.filing_date.year, # Approximate fiscal year by filing date
                            "report_date": filing.filing_date
                        }

                        for attr, concepts in self.annual_concept_map.items():
                            val = self._extract_fact(df, concepts)
                            # Handle infinites or NaN
                            if val is not None and math.isfinite(val):
                                record_dict[attr] = val

                        annual_records.append(record_dict)
                    except Exception as e:
                        logger.warning(f"Error parsing 10-K {filing.accession_no} for {ticker}: {e}")
                    finally:
                        # Rate limiting: stay under 10 req/sec to avoid 429
                        await asyncio.sleep(0.1)
                
                # Compute YoY for Annual
                annual_records = sorted(annual_records, key=lambda x: x['report_date'])
                for i in range(1, len(annual_records)):
                    prev = annual_records[i-1]
                    curr = annual_records[i]
                    
                    if curr.get('revenue') and prev.get('revenue') and prev['revenue'] > 0:
                        curr['revenue_yoy_growth'] = (curr['revenue'] - prev['revenue']) / prev['revenue']
                        
                    if curr.get('eps') and prev.get('eps') and prev['eps'] != 0:
                        # EPS growth calculation (handle negative appropriately if needed, simple approach here)
                        curr['eps_yoy_growth'] = (curr['eps'] - prev['eps']) / abs(prev['eps'])
                        
                # Upsert into DB
                for rec in annual_records:
                    prepared_rec = self._prepare_annual_record(rec)
                    # Simple update or create
                    stmt = select(FundamentalAnnual).where(
                        FundamentalAnnual.instrument_id == prepared_rec["instrument_id"],
                        FundamentalAnnual.fiscal_year == prepared_rec["fiscal_year"]
                    )
                    existing_result = await db.execute(stmt)
                    existing = existing_result.scalars().first()
                    
                    if existing:
                        for k, v in prepared_rec.items():
                            setattr(existing, k, v)
                    else:
                        new_record = FundamentalAnnual(**prepared_rec)
                        db.add(new_record)
                        
                await db.commit()
                logger.info(f"Successfully processed {len(annual_records)} annual records for {ticker}")
                        
            except Exception as e:
                logger.error(f"Error processing 10-K for {ticker}: {e}")

            # --- Quarterly Fundamentals (10-Q)
            logger.info(f"Fetching 10-Q filings for {ticker}")
            try:
                filings_10q_list = c.get_filings(form="10-Q").head(years * 4) # 4 quarters per year
                quarterly_records = []
                for filing in filings_10q_list:
                    try:
                        df = filing.xbrl().facts.to_dataframe()

                        # Approximating Quarter by month
                        month = filing.filing_date.month
                        quarter = (month - 1) // 3 + 1

                        record_dict = {
                            "instrument_id": instrument.id,
                            "fiscal_year": filing.filing_date.year,
                            "fiscal_quarter": quarter,
                            "report_date": filing.filing_date
                        }

                        for attr, concepts in self.quarterly_concept_map.items():
                            val = self._extract_fact(df, concepts)
                            if val is not None and math.isfinite(val):
                                record_dict[attr] = val

                        quarterly_records.append(record_dict)
                    except Exception as e:
                        logger.warning(f"Error parsing 10-Q {filing.accession_no} for {ticker}: {e}")
                    finally:
                        # Rate limiting: stay under 10 req/sec to avoid 429
                        await asyncio.sleep(0.1)
                        
                # Compute YoY for Quarterly (Compare Q(t) with Q(t-4))
                quarterly_records = sorted(quarterly_records, key=lambda x: x['report_date'])
                for i in range(4, len(quarterly_records)):
                    prev = quarterly_records[i-4]
                    curr = quarterly_records[i]
                    
                    if curr.get('revenue') and prev.get('revenue') and prev['revenue'] > 0:
                        curr['revenue_yoy_growth'] = (curr['revenue'] - prev['revenue']) / prev['revenue']
                        
                    if curr.get('eps') and prev.get('eps') and prev['eps'] != 0:
                        curr['eps_yoy_growth'] = (curr['eps'] - prev['eps']) / abs(prev['eps'])
                        
                # Upsert into DB
                for rec in quarterly_records:
                    stmt = select(FundamentalQuarterly).where(
                        FundamentalQuarterly.instrument_id == rec["instrument_id"],
                        FundamentalQuarterly.fiscal_year == rec["fiscal_year"],
                        FundamentalQuarterly.fiscal_quarter == rec["fiscal_quarter"]
                    )
                    existing_result = await db.execute(stmt)
                    existing = existing_result.scalars().first()
                    
                    if existing:
                        for k, v in rec.items():
                            setattr(existing, k, v)
                    else:
                        new_record = FundamentalQuarterly(**rec)
                        db.add(new_record)
                        
                await db.commit()
                logger.info(f"Successfully processed {len(quarterly_records)} quarterly records for {ticker}")

            except Exception as e:
                logger.error(f"Error processing 10-Q for {ticker}: {e}")

async def run_us_fundamentals_ingestion(symbol: str, years: int = 5):
    ingester = EdgarFundamentalIngester()
    await ingester.ingest_fundamentals(symbol, years=years)

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    ticker = sys.argv[1] if len(sys.argv) > 1 else 'AAPL'
    asyncio.run(run_us_fundamentals_ingestion(ticker))
