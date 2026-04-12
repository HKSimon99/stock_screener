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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_kr_tickers() -> list[dict]:
    """Fetch KOSPI & KOSDAQ constituents using FinanceDataReader"""
    instruments = []
    try:
        krx_df = await asyncio.to_thread(fdr.StockListing, 'KRX')
        
        # Determine Market mapping (KOSPI vs KOSDAQ vs KONEX)
        for _, row in krx_df.iterrows():
            code = str(row['Code'])
            name = str(row['Name'])
            market_raw = str(row['Market']) if 'Market' in row else ''
            dept = str(row['Dept']) if 'Dept' in row else ''
            
            # We want strictly KOSPI & KOSDAQ to match our roadmap
            if market_raw not in ['KOSPI', 'KOSDAQ']:
                continue
                
            instruments.append({
                "ticker": code,
                "name": name,
                "market": "KR",
                "exchange": market_raw, # e.g. 'KOSPI' or 'KOSDAQ'
                "asset_type": "stock",
                "sector": dept if dept else None,
                "industry_group": None,
                "is_active": True,
                "is_chaebol_cross": False,
                "is_leveraged": False,
                "is_inverse": False
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
    stmt = insert(Instrument).values(kr_tickers)
    
    # Conflict behavior
    stmt = stmt.on_conflict_do_update(
        index_elements=['ticker', 'market'],
        set_={
            'name': stmt.excluded.name,
            'exchange': stmt.excluded.exchange,
            'sector': stmt.excluded.sector,
            'is_active': stmt.excluded.is_active,
            'updated_at': text("CURRENT_TIMESTAMP"),
        }
    )
    await session.execute(stmt)
    await session.commit()
    logger.info("KR Instruments Sync finished.")


async def fetch_and_store_kr_prices(session: AsyncSession, instrument_id: int, ticker: str, kis_client: 'pykis.PyKis', days: int = 730):
    """
    Fetch and store historical prices using KIS wrapper.
    `pykis` fetches historical data.
    """
    try:
        dt_end = datetime.now()
        dt_start = dt_end - timedelta(days=days)
        
        logger.info(f"Fetching {ticker} prices via KIS (from {dt_start.date()} to {dt_end.date()})...")
        stock = kis_client.stock(ticker)
        
        # chart fetches up to the exact dates requested
        price_data = await asyncio.to_thread(stock.chart, start=dt_start.date(), end=dt_end.date(), adjust=True)
        df = price_data.df()
        
        if df is None or df.empty:
            logger.warning(f"No price data found for {ticker}")
            return
            
        # KisChart.df() returns columns: time, open, high, low, close, volume
        rename_map = {'time': 'trade_date'}
        
        # Only rename columns that exist
        current_cols = df.columns.tolist()
        for k, v in rename_map.items():
            if k in current_cols:
                df.rename(columns={k: v}, inplace=True)
                
        # Ensure it's sorted by date ascending for rolling averages
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
        df = df.sort_values('trade_date')
        
        needed_cols = ['trade_date', 'open', 'high', 'low', 'close', 'volume']
        for col in needed_cols:
            if col not in df.columns:
                 logger.warning(f"Missing column {col} for {ticker}")
                 return

        df['avg_volume_50d'] = df['volume'].rolling(window=50, min_periods=1).mean()
        
        prices_data = []
        for _, row in df.iterrows():
            prices_data.append({
                'instrument_id': instrument_id,
                'trade_date': row['trade_date'],
                'open': float(row['open']) if pd.notnull(row['open']) else None,
                'high': float(row['high']) if pd.notnull(row['high']) else None,
                'low': float(row['low']) if pd.notnull(row['low']) else None,
                'close': float(row['close']) if pd.notnull(row['close']) else None,
                'volume': int(row['volume']) if pd.notnull(row['volume']) else 0,
                'avg_volume_50d': int(row['avg_volume_50d']) if pd.notnull(row['avg_volume_50d']) else 0,
            })
            
        if not prices_data:
            return

        stmt = insert(Price).values(prices_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=['instrument_id', 'trade_date'],
            set_={
                'open': stmt.excluded.open,
                'high': stmt.excluded.high,
                'low': stmt.excluded.low,
                'close': stmt.excluded.close,
                'volume': stmt.excluded.volume,
                'avg_volume_50d': stmt.excluded.avg_volume_50d
            }
        )
        await session.execute(stmt)
        await session.commit()
        logger.info(f"Stored {len(prices_data)} days of prices for {ticker}")
        
    except Exception as e:
        logger.error(f"Error fetching prices for {ticker}: {e}")

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
