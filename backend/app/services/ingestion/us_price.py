import asyncio
import logging
from datetime import datetime, timedelta
import httpx
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.price import Price

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_sp500_tickers() -> list[dict]:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    instruments = []
    try:
        async with httpx.AsyncClient(headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}) as client:
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        table = soup.find('table', {'class': 'wikitable'})
        for row in table.find_all('tr')[1:]:
            cols = row.find_all('td')
            if len(cols) >= 4:
                ticker = cols[0].text.strip().replace('.', '-')
                name = cols[1].text.strip()
                sector = cols[3].text.strip()
                industry = cols[4].text.strip() if len(cols) > 4 else None
                instruments.append({
                    "ticker": ticker,
                    "name": name,
                    "market": "US",
                    "exchange": "NYSE",
                    "asset_type": "stock",
                    "sector": sector,
                    "industry_group": industry,
                    "is_active": True,
                    "is_chaebol_cross": False,
                    "is_leveraged": False,
                    "is_inverse": False
                })
    except Exception as e:
        logger.error(f"Error fetching S&P 500: {e}")
    return instruments

async def fetch_nasdaq100_tickers() -> list[dict]:
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    instruments = []
    try:
        async with httpx.AsyncClient(headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}) as client:
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        tables = soup.find_all('table', {'class': 'wikitable'})
        for table in tables:
            headers = [th.text.strip().lower() for th in table.find_all('th')]
            if 'ticker' in headers:
                ticker_idx = headers.index('ticker')
                company_idx = headers.index('company') if 'company' in headers else 0
                sector_idx = headers.index('gics sector') if 'gics sector' in headers else None
                
                for row in table.find_all('tr')[1:]:
                    cols = row.find_all('td')
                    if len(cols) > ticker_idx:
                        ticker = cols[ticker_idx].text.strip().replace('.', '-')
                        name = cols[company_idx].text.strip() if company_idx < len(cols) else ticker
                        sector = cols[sector_idx].text.strip() if sector_idx is not None and sector_idx < len(cols) else "Technology"
                        instruments.append({
                            "ticker": ticker,
                            "name": name,
                            "market": "US",
                            "exchange": "NASDAQ",
                            "asset_type": "stock",
                            "sector": sector,
                            "industry_group": None,
                            "is_active": True,
                            "is_chaebol_cross": False,
                            "is_leveraged": False,
                            "is_inverse": False
                        })
                break
    except Exception as e:
        logger.error(f"Error fetching NASDAQ 100: {e}")
    return instruments

async def sync_instruments(session: AsyncSession):
    sp500 = await fetch_sp500_tickers()
    nasdaq = await fetch_nasdaq100_tickers()
    
    instruments_dict = {i['ticker']: i for i in sp500}
    for i in nasdaq:
        if i['ticker'] in instruments_dict:
            instruments_dict[i['ticker']]['exchange'] = 'NASDAQ'
        else:
            instruments_dict[i['ticker']] = i
            
    instruments_data = list(instruments_dict.values())
    if not instruments_data:
        logger.error("No instruments fetched, skipping sync.")
        return

    logger.info(f"Upserting {len(instruments_data)} US instruments...")
    stmt = insert(Instrument).values(instruments_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=['ticker', 'market'],
        set_={
            'name': stmt.excluded.name,
            'exchange': stmt.excluded.exchange,
            'sector': stmt.excluded.sector,
            'industry_group': stmt.excluded.industry_group,
            'is_active': stmt.excluded.is_active,
            'updated_at': text("CURRENT_TIMESTAMP"),
        }
    )
    await session.execute(stmt)
    await session.commit()
    logger.info("Sync finished.")

async def fetch_and_store_prices(session: AsyncSession, instrument_id: int, ticker: str, days: int = 730):
    try:
        dt_end = datetime.now()
        dt_start = dt_end - timedelta(days=days)
        
        logger.info(f"Fetching {ticker} prices...")
        ticker_obj = yf.Ticker(ticker)
        df = await asyncio.to_thread(
            ticker_obj.history, 
            start=dt_start.strftime('%Y-%m-%d'), 
            end=dt_end.strftime('%Y-%m-%d')
        )
        
        if df.empty:
            logger.warning(f"No price data found for {ticker}")
            return
            
        df = df.reset_index()
        # Convert timezone-aware datetimes to naive dates
        if pd.api.types.is_datetime64_any_dtype(df['Date']):
            df['Date'] = df['Date'].dt.date
        
        df.rename(columns={
            'Date': 'trade_date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        }, inplace=True)
        
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
    async with AsyncSessionLocal() as session:
        await sync_instruments(session)
        # Fetch AAPL just to test
        result = await session.execute(select(Instrument).where(Instrument.ticker == 'AAPL'))
        aapl = result.scalar_one_or_none()
        if aapl:
            await fetch_and_store_prices(session, aapl.id, aapl.ticker)

if __name__ == "__main__":
    asyncio.run(test_run())
