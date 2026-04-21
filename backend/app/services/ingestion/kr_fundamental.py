import asyncio
import logging
import zipfile
import io
from datetime import datetime, date
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any, Iterable

import httpx
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.models.fundamental import FundamentalAnnual, FundamentalQuarterly
from app.models.instrument import Instrument

logger = logging.getLogger(__name__)

# Minimum annual records to consider a fundamentals ingestion successful
MIN_ANNUAL_RECORDS = 1


class CorpCodeNotFoundError(Exception):
    """Raised when a KR ticker has no matching corp_code in OpenDART."""


class InsufficientDataError(Exception):
    """Raised when fundamentals ingestion produces fewer records than MIN_ANNUAL_RECORDS."""

ANNUAL_MODEL_FIELDS = {
    "instrument_id",
    "fiscal_year",
    "report_date",
    "revenue",
    "gross_profit",
    "net_income",
    "eps",
    "eps_diluted",
    "eps_yoy_growth",
    "total_assets",
    "current_assets",
    "current_liabilities",
    "long_term_debt",
    "shares_outstanding_annual",
    "operating_cash_flow",
    "roa",
    "current_ratio",
    "gross_margin",
    "asset_turnover",
    "leverage_ratio",
    "data_source",
}

QUARTERLY_MODEL_FIELDS = {
    "instrument_id",
    "fiscal_year",
    "fiscal_quarter",
    "report_date",
    "revenue",
    "net_income",
    "eps",
    "eps_diluted",
    "eps_yoy_growth",
    "revenue_yoy_growth",
    "data_source",
}

class KRFundamentalIngester:
    def __init__(self):
        self.api_key = settings.opendart_api_key
        if not self.api_key:
            raise ValueError("OPENDART_API_KEY is missing from environment variables.")
        self.corp_codes_cache: Dict[str, str] = {}

        # The "All" endpoint exposes balance sheet, income statement, cash flow,
        # and statement-of-changes rows in a single payload when fs_div is supplied.
        self.annual_concept_map: Dict[str, Dict[str, Any]] = {
            "revenue": {
                "sj_div": ("IS", "CIS"),
                "account_names": ["매출액", "영업수익", "수익(매출액)"],
            },
            "gross_profit": {
                "sj_div": ("IS", "CIS"),
                "account_names": ["매출총이익", "매출총이익(손실)"],
            },
            "net_income": {
                "sj_div": ("IS", "CIS"),
                "account_names": [
                    "당기순이익",
                    "당기순이익(손실)",
                    "연결당기순이익",
                    "분기순이익",
                    "분기순손익",
                ],
            },
            "eps": {
                "sj_div": ("IS", "CIS"),
                "account_names": [
                    "기본주당이익",
                    "기본주당이익(손실)",
                    "기본주당순이익",
                    "기본주당순이익(손실)",
                    "보통주기본주당이익",
                    "보통주기본주당이익(손실)",
                    "보통주기본주당순이익",
                    "보통주기본주당순이익(손실)",
                ],
                "account_ids": [
                    "ifrs-full_BasicEarningsLossPerShare",
                    "ifrs-full_BasicEarningsLossPerShareFromContinuingOperations",
                ],
            },
            "eps_diluted": {
                "sj_div": ("IS", "CIS"),
                "account_names": [
                    "희석주당이익",
                    "희석주당이익(손실)",
                    "희석주당순이익",
                    "희석주당순이익(손실)",
                    "보통주 희석주당이익",
                    "보통주희석주당이익",
                ],
                "account_ids": [
                    "ifrs-full_DilutedEarningsLossPerShare",
                    "ifrs-full_DilutedEarningsLossPerShareFromContinuingOperations",
                ],
            },
            "total_assets": {
                "sj_div": ("BS",),
                "account_names": ["자산총계"],
            },
            "current_assets": {
                "sj_div": ("BS",),
                "account_names": ["유동자산"],
            },
            "current_liabilities": {
                "sj_div": ("BS",),
                "account_names": ["유동부채"],
            },
            "long_term_debt": {
                "sj_div": ("BS",),
                "account_names": ["장기차입금", "사채"],
                "account_ids": [
                    "ifrs-full_LongtermBorrowings",
                    "ifrs-full_NoncurrentPortionOfNoncurrentLoansReceived",
                    "ifrs-full_NoncurrentPortionOfNoncurrentBondsIssued",
                ],
                "sum_matches": True,
            },
            "operating_cash_flow": {
                "sj_div": ("CF",),
                "account_names": [
                    "영업활동현금흐름",
                    "영업활동 현금흐름",
                    "영업활동으로 인한 현금흐름",
                    "영업에서 창출된 현금흐름",
                    "영업으로부터 창출된 현금흐름",
                ],
            },
        }
        self.quarterly_concept_map: Dict[str, Dict[str, Any]] = {
            "revenue": {
                "sj_div": ("IS", "CIS"),
                "account_names": ["매출액", "영업수익", "수익(매출액)"],
            },
            "net_income": {
                "sj_div": ("IS", "CIS"),
                "account_names": [
                    "당기순이익",
                    "당기순이익(손실)",
                    "연결당기순이익",
                    "분기순이익",
                    "분기순손익",
                ],
            },
            "eps": {
                "sj_div": ("IS", "CIS"),
                "account_names": [
                    "기본주당이익",
                    "기본주당이익(손실)",
                    "기본주당순이익",
                    "기본주당순이익(손실)",
                    "보통주기본주당이익",
                    "보통주기본주당이익(손실)",
                    "보통주기본주당순이익",
                    "보통주기본주당순이익(손실)",
                ],
                "account_ids": [
                    "ifrs-full_BasicEarningsLossPerShare",
                    "ifrs-full_BasicEarningsLossPerShareFromContinuingOperations",
                ],
            },
            "eps_diluted": {
                "sj_div": ("IS", "CIS"),
                "account_names": [
                    "희석주당이익",
                    "희석주당이익(손실)",
                    "희석주당순이익",
                    "희석주당순이익(손실)",
                    "보통주 희석주당이익",
                    "보통주희석주당이익",
                ],
                "account_ids": [
                    "ifrs-full_DilutedEarningsLossPerShare",
                    "ifrs-full_DilutedEarningsLossPerShareFromContinuingOperations",
                ],
            },
        }
        
    async def _populate_corp_codes(self):
        """Fetches the CORPCODE.xml from OpenDART and populates cache (stock_code -> corp_code)"""
        if self.corp_codes_cache:
            return
            
        url = "https://opendart.fss.or.kr/api/corpCode.xml"
        params = {"crtfc_key": self.api_key}
        
        logger.info("Downloading OpenDART corp_codes archive...")
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=30.0)
            resp.raise_for_status()  # Raises httpx.HTTPStatusError on 4xx/5xx

            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                with z.open("CORPCODE.xml") as f:
                    tree = ET.parse(f)
                    root = tree.getroot()

                    for list_node in root.findall("list"):
                        stock_code = list_node.find("stock_code").text
                        if stock_code and stock_code.strip():
                            corp_code = list_node.find("corp_code").text
                            self.corp_codes_cache[stock_code.strip()] = corp_code

            logger.info("Loaded %d Korean corporation codes from OpenDART.", len(self.corp_codes_cache))

    async def _fetch_finstate(self, corp_code: str, year: int, report_code: str) -> List[Dict]:
        """Fetch the full statement payload, preferring consolidated statements."""
        url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"

        async with httpx.AsyncClient() as client:
            for fs_div in ("CFS", "OFS"):
                params = {
                    "crtfc_key": self.api_key,
                    "corp_code": corp_code,
                    "bsns_year": str(year),
                    "reprt_code": report_code,  # Annual/Q1/Q2/Q3
                    "fs_div": fs_div,
                }
                resp = await client.get(url, params=params, timeout=15.0)
                if resp.status_code != 200:
                    logger.debug(
                        "DART HTTP error for corp=%s year=%s reprt=%s fs_div=%s status=%s",
                        corp_code,
                        year,
                        report_code,
                        fs_div,
                        resp.status_code,
                    )
                    continue

                data = resp.json()
                status = data.get("status")
                if status == "000":
                    rows = data.get("list", [])
                    if rows:
                        return rows
                elif status != "013":  # 013 = no data
                    logger.debug(
                        "DART error for corp=%s year=%s reprt=%s fs_div=%s: %s",
                        corp_code,
                        year,
                        report_code,
                        fs_div,
                        data.get("message"),
                    )

        return []

    def _parse_amount(self, raw_value: Optional[str]) -> Optional[float]:
        if raw_value is None:
            return None
        cleaned = str(raw_value).strip().replace(",", "")
        if not cleaned or cleaned == "-":
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _extract_value(
        self,
        finstate_list: List[Dict],
        *,
        account_names: Iterable[str],
        sj_divs: Iterable[str],
        account_ids: Optional[Iterable[str]] = None,
        sum_matches: bool = False,
    ) -> Optional[float]:
        """Find the current-period numeric value for the requested statement/account."""
        matches: List[float] = []
        normalized_sj_divs = tuple(sj_divs)
        normalized_account_ids = tuple(account_ids or ())
        seen_keys: set[tuple[str, str]] = set()

        for item in finstate_list:
            if item.get("sj_div") not in normalized_sj_divs:
                continue

            account_name = item.get("account_nm", "")
            account_id = item.get("account_id", "")
            matched = any(candidate in account_name for candidate in account_names)
            if not matched and normalized_account_ids:
                matched = account_id in normalized_account_ids
            if not matched:
                continue

            value = self._parse_amount(item.get("thstrm_amount"))
            if value is None:
                continue

            if not sum_matches:
                return value
            match_key = (account_id, account_name)
            if match_key in seen_keys:
                continue
            seen_keys.add(match_key)
            matches.append(value)

        if sum_matches and matches:
            return sum(matches)
        return None

    def _build_record(
        self,
        finstate_list: List[Dict],
        concept_map: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        record: Dict[str, Any] = {}
        for attr, config in concept_map.items():
            value = self._extract_value(
                finstate_list,
                account_names=config["account_names"],
                sj_divs=config["sj_div"],
                account_ids=config.get("account_ids"),
                sum_matches=config.get("sum_matches", False),
            )
            if value is not None:
                record[attr] = value
        return record

    def _prepare_annual_record(
        self,
        record: Dict[str, Any],
        instrument: Instrument,
    ) -> Dict[str, Any]:
        prepared = dict(record)
        if prepared.get("shares_outstanding_annual") is None and instrument.shares_outstanding is not None:
            prepared["shares_outstanding_annual"] = instrument.shares_outstanding

        prepared["data_source"] = "DART"

        net_income = prepared.get("net_income")
        total_assets = prepared.get("total_assets")
        current_assets = prepared.get("current_assets")
        current_liabilities = prepared.get("current_liabilities")
        gross_profit = prepared.get("gross_profit")
        revenue = prepared.get("revenue")
        long_term_debt = prepared.get("long_term_debt")

        if net_income is not None and total_assets not in (None, 0):
            prepared["roa"] = net_income / total_assets
        if current_assets is not None and current_liabilities not in (None, 0):
            prepared["current_ratio"] = current_assets / current_liabilities
        if gross_profit is not None and revenue not in (None, 0):
            prepared["gross_margin"] = gross_profit / revenue
        if revenue is not None and total_assets not in (None, 0):
            prepared["asset_turnover"] = revenue / total_assets
        if long_term_debt is not None and total_assets not in (None, 0):
            prepared["leverage_ratio"] = long_term_debt / total_assets

        return {key: value for key, value in prepared.items() if key in ANNUAL_MODEL_FIELDS}

    def _prepare_quarterly_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        prepared = dict(record)
        prepared["data_source"] = "DART"
        return {key: value for key, value in prepared.items() if key in QUARTERLY_MODEL_FIELDS}

    async def ingest_fundamentals(self, ticker: str, years: int = 5):
        """Fetches Annual and Quarterly financials for the KR ticker.

        Raises:
            CorpCodeNotFoundError: ticker absent from OpenDART corp_code registry.
            InsufficientDataError: fewer than MIN_ANNUAL_RECORDS annual rows produced.
        """
        if not self.corp_codes_cache:
            await self._populate_corp_codes()

        corp_code = self.corp_codes_cache.get(ticker)
        if not corp_code:
            raise CorpCodeNotFoundError(
                f"Ticker {ticker} not found in OpenDART corporation codes."
            )

        logger.info(
            "Starting KR fundamental ingestion for %s (corp_code=%s, years=%d)",
            ticker, corp_code, years,
        )

        async with AsyncSessionLocal() as db:
            stmt = select(Instrument).where(Instrument.ticker == ticker, Instrument.market == "KR")
            result = await db.execute(stmt)
            instrument = result.scalars().first()

            if not instrument:
                raise ValueError(f"Instrument {ticker} (KR) not found in DB — run sync first.")

            current_year = datetime.now().year
            target_years = [current_year - i for i in range(years)]
            
            annual_records = []
            quarterly_records = []
            
            # Reprt codes: Q1(11013), Q2(11012), Q3(11014), Annual(11011)
            q_codes = {1: '11013', 2: '11012', 3: '11014', 4: '11011'}
            
            for y in sorted(target_years):
                for q, reprt_code in q_codes.items():
                    data = await self._fetch_finstate(corp_code, y, reprt_code)
                    if not data:
                        continue

                    record_data = self._build_record(
                        data,
                        self.annual_concept_map if q == 4 else self.quarterly_concept_map,
                    )

                    if not record_data:
                        continue

                    if q == 4:
                        # Annual record
                        annual_records.append({
                            "instrument_id": instrument.id,
                            "fiscal_year": y,
                            "report_date": date(y, 12, 31), # DART doesn't cleanly give report date in finstate, default to Dec 31
                            "shares_outstanding_annual": instrument.shares_outstanding,
                        } | record_data)
                    else:
                        # Quarterly record
                        month = q * 3
                        # We use the end of the quarter as the report date
                        end_day = 30 if month in [6, 9] else 31
                        quarterly_records.append({
                            "instrument_id": instrument.id,
                            "fiscal_year": y,
                            "fiscal_quarter": q,
                            "report_date": date(y, month, end_day),
                        } | record_data)

            # Compute YoY for Annual
            for i in range(1, len(annual_records)):
                prev = annual_records[i-1]
                curr = annual_records[i]

                if curr.get('revenue') is not None and prev.get('revenue') and prev['revenue'] > 0:
                    curr['revenue_yoy_growth'] = (curr['revenue'] - prev['revenue']) / prev['revenue']
                if curr.get('eps') is not None and prev.get('eps') and prev['eps'] != 0:
                    curr['eps_yoy_growth'] = (curr['eps'] - prev['eps']) / abs(prev['eps'])
                    
            # Compute YoY for Quarterly
            for i in range(4, len(quarterly_records)):
                prev = quarterly_records[i-4]
                curr = quarterly_records[i]
                
                if curr.get('revenue') is not None and prev.get('revenue') and prev['revenue'] > 0:
                    curr['revenue_yoy_growth'] = (curr['revenue'] - prev['revenue']) / prev['revenue']
                if curr.get('eps') is not None and prev.get('eps') and prev['eps'] != 0:
                    curr['eps_yoy_growth'] = (curr['eps'] - prev['eps']) / abs(prev['eps'])

            # Validate minimum record count before touching the DB
            if len(annual_records) < MIN_ANNUAL_RECORDS:
                raise InsufficientDataError(
                    f"Only {len(annual_records)} annual record(s) produced for {ticker} "
                    f"(minimum {MIN_ANNUAL_RECORDS}). DART may be unavailable or the "
                    "ticker has no financial filings."
                )

            # Upsert Annual
            for rec in annual_records:
                filtered_rec = self._prepare_annual_record(rec, instrument)
                
                stmt = select(FundamentalAnnual).where(
                    FundamentalAnnual.instrument_id == rec["instrument_id"],
                    FundamentalAnnual.fiscal_year == rec["fiscal_year"]
                )
                existing = (await db.execute(stmt)).scalars().first()
                if existing:
                    for k, v in filtered_rec.items():
                        setattr(existing, k, v)
                else:
                    db.add(FundamentalAnnual(**filtered_rec))
                    
            # Upsert Quarterly
            for rec in quarterly_records:
                filtered_rec = self._prepare_quarterly_record(rec)
                
                stmt = select(FundamentalQuarterly).where(
                    FundamentalQuarterly.instrument_id == rec["instrument_id"],
                    FundamentalQuarterly.fiscal_year == rec["fiscal_year"],
                    FundamentalQuarterly.fiscal_quarter == rec["fiscal_quarter"]
                )
                existing = (await db.execute(stmt)).scalars().first()
                if existing:
                    for k, v in filtered_rec.items():
                        setattr(existing, k, v)
                else:
                    db.add(FundamentalQuarterly(**filtered_rec))
                    
            await db.commit()
            logger.info(
                "KR fundamentals ingested for %s: %d annual, %d quarterly records.",
                ticker, len(annual_records), len(quarterly_records),
            )

async def run_kr_fundamentals_ingestion(symbol: str, years: int = 5):
    ingester = KRFundamentalIngester()
    await ingester.ingest_fundamentals(symbol, years=years)

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    ticker = sys.argv[1] if len(sys.argv) > 1 else '005930' # Default to Samsung Elec
    asyncio.run(run_kr_fundamentals_ingestion(ticker))
