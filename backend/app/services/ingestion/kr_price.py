import asyncio
import logging
import os
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
import FinanceDataReader as fdr

from dotenv import load_dotenv
load_dotenv()

# Import pykis specifically configured for KIS
try:
    import pykis
except ImportError:
    pykis = None

from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.price import Price
from app.services.taxonomy import normalize_exchange, normalize_sector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Minimum bars required to consider a price fetch successful
MIN_PRICE_ROWS = 5


class KISAPIError(Exception):
    """Raised when the KIS API fails to return valid price data."""


class InsufficientDataError(Exception):
    """Raised when fetched price data has fewer rows than MIN_PRICE_ROWS."""


async def _fetch_prices_via_kis(
    kis_client: "pykis.PyKis",
    ticker: str,
    dt_start: datetime,
    dt_end: datetime,
) -> pd.DataFrame:
    """Fetch OHLCV bars via KIS (pykis). Raises KISAPIError on any failure."""
    try:
        stock = kis_client.stock(ticker)
        price_data = await asyncio.to_thread(
            stock.chart, start=dt_start.date(), end=dt_end.date(), adjust=True
        )
        df = price_data.df()
        if df is None or df.empty:
            raise KISAPIError(f"KIS returned empty DataFrame for {ticker}")
        return df
    except KISAPIError:
        raise
    except Exception as exc:
        raise KISAPIError(f"KIS chart fetch failed for {ticker}: {exc}") from exc


async def _fetch_prices_via_pykrx(
    ticker: str,
    dt_start: datetime,
    dt_end: datetime,
) -> pd.DataFrame:
    """Fetch OHLCV bars via pykrx (KRX web scraping). Used as KIS fallback."""
    try:
        from pykrx import stock as pkrx_stock  # noqa: PLC0415

        start_str = dt_start.strftime("%Y%m%d")
        end_str = dt_end.strftime("%Y%m%d")
        df = await asyncio.to_thread(
            pkrx_stock.get_market_ohlcv_by_date, start_str, end_str, ticker
        )
        if df is None or df.empty:
            raise InsufficientDataError(f"pykrx returned empty DataFrame for {ticker}")

        # pykrx uses Korean column names — normalise to English
        col_map = {"시가": "open", "고가": "high", "저가": "low", "종가": "close", "거래량": "volume"}
        df = df.rename(columns=col_map)
        df.index.name = "trade_date"
        df = df.reset_index()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df

    except InsufficientDataError:
        raise
    except Exception as exc:
        raise InsufficientDataError(f"pykrx fetch failed for {ticker}: {exc}") from exc


async def _fetch_prices_via_fdr(
    ticker: str,
    dt_start: datetime,
    dt_end: datetime,
) -> pd.DataFrame:
    """Fetch OHLCV bars via FinanceDataReader as a broader KR fallback."""
    try:
        df = await asyncio.to_thread(
            fdr.DataReader,
            ticker,
            dt_start.strftime("%Y-%m-%d"),
            dt_end.strftime("%Y-%m-%d"),
        )
        if df is None or df.empty:
            raise InsufficientDataError(f"FinanceDataReader returned empty DataFrame for {ticker}")

        col_map = {
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
        df = df.rename(columns=col_map)
        df.index.name = "trade_date"
        df = df.reset_index()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df
    except InsufficientDataError:
        raise
    except Exception as exc:
        raise InsufficientDataError(f"FinanceDataReader fetch failed for {ticker}: {exc}") from exc

async def fetch_kr_tickers() -> list[dict]:
    """Fetch official KRX stock listings plus KR ETF listings using FinanceDataReader."""
    instruments = []
    seen: set[str] = set()
    try:
        krx_df = await asyncio.to_thread(fdr.StockListing, "KRX")

        for _, row in krx_df.iterrows():
            code = str(row["Code"])
            name = str(row["Name"])
            market_raw = str(row["Market"]) if "Market" in row else ""
            dept = str(row["Dept"]) if "Dept" in row else ""

            if market_raw not in ["KOSPI", "KOSDAQ", "KONEX"]:
                continue

            seen.add(code)
            instruments.append({
                "ticker": code,
                "name": name,
                "name_kr": name,
                "market": "KR",
                "exchange": normalize_exchange(market_raw),
                "asset_type": "stock",
                "listing_status": "LISTED",
                "sector": normalize_sector(dept),
                "industry_group": None,
                "is_active": True,
                "is_test_issue": False,
                "source_provenance": "KRX:FDR",
                "source_symbol": code,
                "is_chaebol_cross": False,
                "is_leveraged": False,
                "is_inverse": False
            })

        etf_df = await asyncio.to_thread(fdr.StockListing, "ETF/KR")
        for _, row in etf_df.iterrows():
            symbol = str(row["Symbol"]) if "Symbol" in row else ""
            name = str(row["Name"]) if "Name" in row else symbol
            if not symbol or symbol in seen:
                continue

            lowered_name = name.lower()
            seen.add(symbol)
            instruments.append({
                "ticker": symbol,
                "name": name,
                "name_kr": name,
                "market": "KR",
                "exchange": normalize_exchange("ETF"),
                "asset_type": "etf",
                "listing_status": "LISTED",
                "sector": normalize_sector(str(row["Category"]) if "Category" in row else None),
                "industry_group": None,
                "is_active": True,
                "is_test_issue": False,
                "source_provenance": "KRX:ETF:FDR",
                "source_symbol": symbol,
                "is_chaebol_cross": False,
                "is_leveraged": "lever" in lowered_name or "2x" in lowered_name,
                "is_inverse": "inverse" in lowered_name or "인버스" in name,
            })
    except Exception as e:
        logger.error(f"Error fetching KRX tickers: {e}")
    return instruments

async def sync_kr_instruments(session: AsyncSession):
    kr_tickers = await fetch_kr_tickers()
    if not kr_tickers:
        logger.error("No KR instruments fetched, skipping sync.")
        return

    logger.info(f"Upserting {len(kr_tickers)} KR instruments...")
    # asyncpg limit: 32767 bind params. Each row has ~15 cols → chunk at 500 rows.
    CHUNK_SIZE = 500
    for i in range(0, len(kr_tickers), CHUNK_SIZE):
        chunk = kr_tickers[i : i + CHUNK_SIZE]
        stmt = insert(Instrument).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=['ticker', 'market'],
            set_={
                'name': stmt.excluded.name,
                'name_kr': stmt.excluded.name_kr,
                'exchange': stmt.excluded.exchange,
                'asset_type': stmt.excluded.asset_type,
                'listing_status': stmt.excluded.listing_status,
                'sector': stmt.excluded.sector,
                'is_active': stmt.excluded.is_active,
                'source_provenance': stmt.excluded.source_provenance,
                'source_symbol': stmt.excluded.source_symbol,
                'updated_at': text("CURRENT_TIMESTAMP"),
            }
        )
        await session.execute(stmt)
    await session.commit()
    logger.info("KR Instruments Sync finished.")


def _normalise_price_df(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Rename columns to standard names and sort by trade_date ascending."""
    # KIS returns a 'time' column; pykrx returns index already converted by caller
    if "time" in df.columns:
        df = df.rename(columns={"time": "trade_date"})

    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df = df.sort_values("trade_date")

    needed_cols = ["trade_date", "open", "high", "low", "close", "volume"]
    missing = [c for c in needed_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Price DataFrame for {ticker} missing columns: {missing}")

    return df


async def fetch_and_store_kr_prices(
    session: AsyncSession,
    instrument_id: int,
    ticker: str,
    kis_client: "pykis.PyKis",
    days: int = 730,
) -> int:
    """
    Fetch and store historical KR prices.

    Attempts KIS (pykis) first. On KISAPIError falls back to pykrx.
    Raises InsufficientDataError when fewer than MIN_PRICE_ROWS bars are returned
    by both sources (so the Celery task can retry via tenacity).

    Returns the number of rows upserted.
    """
    dt_end = datetime.now()
    dt_start = dt_end - timedelta(days=days)

    logger.info("Fetching %s prices (from %s to %s) …", ticker, dt_start.date(), dt_end.date())

    # ------------------------------------------------------------------
    # 1. Fetch from KIS; fall back to pykrx if KIS fails
    # ------------------------------------------------------------------
    try:
        df = await _fetch_prices_via_kis(kis_client, ticker, dt_start, dt_end)
        source = "KIS"
    except KISAPIError as exc:
        logger.warning("KIS failed for %s (%s); falling back to FinanceDataReader", ticker, exc)
        try:
            df = await _fetch_prices_via_fdr(ticker, dt_start, dt_end)
            source = "FinanceDataReader"
        except InsufficientDataError as fdr_exc:
            logger.warning(
                "FinanceDataReader failed for %s (%s); falling back to pykrx",
                ticker,
                fdr_exc,
            )
            df = await _fetch_prices_via_pykrx(ticker, dt_start, dt_end)
            source = "pykrx"

    # ------------------------------------------------------------------
    # 2. Normalise columns and validate minimum row count
    # ------------------------------------------------------------------
    df = _normalise_price_df(df, ticker)

    if len(df) < MIN_PRICE_ROWS:
        raise InsufficientDataError(
            f"{source} returned only {len(df)} rows for {ticker} (minimum {MIN_PRICE_ROWS})"
        )

    # ------------------------------------------------------------------
    # 3. Build upsert payload
    # ------------------------------------------------------------------
    df["avg_volume_50d"] = df["volume"].rolling(window=50, min_periods=1).mean()

    prices_data = [
        {
            "instrument_id": instrument_id,
            "trade_date": row["trade_date"],
            "open":  float(row["open"])  if pd.notnull(row["open"])  else None,
            "high":  float(row["high"])  if pd.notnull(row["high"])  else None,
            "low":   float(row["low"])   if pd.notnull(row["low"])   else None,
            "close": float(row["close"]) if pd.notnull(row["close"]) else None,
            "volume":        int(row["volume"])        if pd.notnull(row["volume"])        else 0,
            "avg_volume_50d": int(row["avg_volume_50d"]) if pd.notnull(row["avg_volume_50d"]) else 0,
        }
        for _, row in df.iterrows()
    ]

    stmt = insert(Price).values(prices_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["instrument_id", "trade_date"],
        set_={
            "open":          stmt.excluded.open,
            "high":          stmt.excluded.high,
            "low":           stmt.excluded.low,
            "close":         stmt.excluded.close,
            "volume":        stmt.excluded.volume,
            "avg_volume_50d": stmt.excluded.avg_volume_50d,
        },
    )
    await session.execute(stmt)
    await session.commit()

    logger.info("Stored %d days of prices for %s (source: %s)", len(prices_data), ticker, source)
    return len(prices_data)

async def test_run():
    if not pykis:
        logger.error("pykis is not installed.")
        return

    # KIS Authentication
    appkey = os.environ.get('KIS_APP_KEY')
    secretkey = os.environ.get('KIS_APP_SECRET')
    hts_id = os.environ.get('KIS_HTS_ID', '')
    account = os.environ.get('KIS_ACCOUNT_NO', '')
    
    if not appkey or not secretkey or not hts_id or not account:
        logger.error("Missing KIS env vars. Ensure KIS_APP_KEY, KIS_APP_SECRET, KIS_HTS_ID, and KIS_ACCOUNT_NO are set in .env")
        logger.info("Proceeding with only Instrument sync (Skipping price history for KIS).")
        async with AsyncSessionLocal() as session:
            await sync_kr_instruments(session)
        return

    try:
        kis_client = pykis.PyKis(
            id=hts_id,
            account=account,
            appkey=appkey,
            secretkey=secretkey
        )
        logger.info("Connected to KIS successfully.")
    except Exception as e:
        logger.error(f"Failed to connect to KIS: {e}")
        return

    async with AsyncSessionLocal() as session:
        await sync_kr_instruments(session)
        
        # Test fetching Samsung Electronics (005930) prices
        result = await session.execute(select(Instrument).where(Instrument.ticker == '005930'))
        samsung = result.scalar_one_or_none()
        if samsung:
            await fetch_and_store_kr_prices(session, samsung.id, samsung.ticker, kis_client)

if __name__ == "__main__":
    asyncio.run(test_run())
