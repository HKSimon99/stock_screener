import asyncio
import csv
import io
import logging
from datetime import datetime, timedelta

import httpx
import pandas as pd
import yfinance as yf
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.price import Price

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NASDAQ_DIRECTORY_URLS = {
    "nasdaqlisted": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "otherlisted": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}
EXCHANGE_CODE_MAP = {
    "A": "NYSEAMER",
    "N": "NYSE",
    "P": "NYSEARCA",
    "Q": "NASDAQ",
    "V": "IEX",
    "Z": "CBOEBZX",
}
UNSUPPORTED_SECURITY_TOKENS = (
    " warrant",
    " rights",
    " right",
    " unit",
    " notes",
    " note",
    " preferred",
    " depositary",
)


def _normalize_ticker(symbol: str) -> str:
    return symbol.strip().replace("$", "").replace(".", "-")


def _is_supported_security(security_name: str, *, etf_flag: str) -> bool:
    if etf_flag == "Y":
        return True
    lowered = f" {security_name.lower()} "
    return not any(token in lowered for token in UNSUPPORTED_SECURITY_TOKENS)


def _build_instrument_payload(row: dict[str, str], source_name: str) -> dict | None:
    if source_name == "nasdaqlisted":
        symbol = row.get("Symbol", "")
        security_name = row.get("Security Name", "").strip()
        test_issue = row.get("Test Issue", "N").strip().upper() == "Y"
        etf_flag = row.get("ETF", "N").strip().upper()
        normalized_ticker = _normalize_ticker(symbol)
        if (
            not symbol
            or not security_name
            or len(normalized_ticker) > 10
            or not _is_supported_security(security_name, etf_flag=etf_flag)
        ):
            return None
        return {
            "ticker": normalized_ticker,
            "name": security_name[:200],
            "market": "US",
            "exchange": "NASDAQ",
            "asset_type": "etf" if etf_flag == "Y" else "stock",
            "listing_status": "LISTED",
            "sector": None,
            "industry_group": None,
            "is_active": not test_issue,
            "is_test_issue": test_issue,
            "source_provenance": "NASDAQ_TRADER:nasdaqlisted",
            "source_symbol": symbol.strip()[:40],
            "is_chaebol_cross": False,
            "is_leveraged": False,
            "is_inverse": False,
        }

    symbol = row.get("ACT Symbol", "")
    security_name = row.get("Security Name", "").strip()
    test_issue = row.get("Test Issue", "N").strip().upper() == "Y"
    etf_flag = row.get("ETF", "N").strip().upper()
    normalized_ticker = _normalize_ticker(symbol)
    if (
        not symbol
        or not security_name
        or len(normalized_ticker) > 10
        or not _is_supported_security(security_name, etf_flag=etf_flag)
    ):
        return None
    exchange_code = row.get("Exchange", "").strip().upper()
    return {
        "ticker": normalized_ticker,
        "name": security_name[:200],
        "market": "US",
        "exchange": EXCHANGE_CODE_MAP.get(exchange_code, exchange_code or "OTHER"),
        "asset_type": "etf" if etf_flag == "Y" else "stock",
        "listing_status": "LISTED",
        "sector": None,
        "industry_group": None,
        "is_active": not test_issue,
        "is_test_issue": test_issue,
        "source_provenance": "NASDAQ_TRADER:otherlisted",
        "source_symbol": symbol.strip()[:40],
        "is_chaebol_cross": False,
        "is_leveraged": False,
        "is_inverse": False,
    }


async def _download_directory(name: str) -> list[dict]:
    url = NASDAQ_DIRECTORY_URLS[name]
    async with httpx.AsyncClient(headers={"User-Agent": "Consensus/1.0"}) as client:
        resp = await client.get(url, timeout=30.0)
        resp.raise_for_status()

    text_payload = resp.text
    lines = [line for line in text_payload.splitlines() if line and not line.startswith("File Creation Time")]
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter="|")
    records: list[dict] = []
    for row in reader:
        payload = _build_instrument_payload(row, name)
        if payload is not None:
            records.append(payload)
    return records


async def fetch_us_tickers() -> list[dict]:
    try:
        listed, other = await asyncio.gather(
            _download_directory("nasdaqlisted"),
            _download_directory("otherlisted"),
        )
    except Exception as exc:
        logger.error("Error fetching NASDAQ Trader directories: %s", exc)
        return []

    instruments_by_key: dict[tuple[str, str], dict] = {}
    for instrument in [*listed, *other]:
        key = (instrument["ticker"], instrument["market"])
        existing = instruments_by_key.get(key)
        if existing is None:
            instruments_by_key[key] = instrument
            continue

        if existing["exchange"] != "NASDAQ" and instrument["exchange"] == "NASDAQ":
            instruments_by_key[key] = instrument
            continue

        existing["is_active"] = existing["is_active"] or instrument["is_active"]
        existing["source_provenance"] = f"{existing['source_provenance']}|{instrument['source_provenance']}"

    return list(instruments_by_key.values())


async def sync_instruments(session: AsyncSession):
    instruments_data = await fetch_us_tickers()
    if not instruments_data:
        logger.error("No instruments fetched, skipping sync.")
        return

    logger.info("Upserting %d US instruments from official symbol directories...", len(instruments_data))

    # asyncpg hard limit: 32767 bind parameters per query.
    # Each row has 15 columns → 500 rows = 7 500 params (well within limit).
    CHUNK_SIZE = 500
    total = len(instruments_data)
    upserted = 0
    for i in range(0, total, CHUNK_SIZE):
        chunk = instruments_data[i : i + CHUNK_SIZE]
        try:
            stmt = insert(Instrument).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "market"],
                set_={
                    "name": stmt.excluded.name,
                    "exchange": stmt.excluded.exchange,
                    "asset_type": stmt.excluded.asset_type,
                    "listing_status": stmt.excluded.listing_status,
                    "is_active": stmt.excluded.is_active,
                    "is_test_issue": stmt.excluded.is_test_issue,
                    "source_provenance": stmt.excluded.source_provenance,
                    "source_symbol": stmt.excluded.source_symbol,
                    "updated_at": text("CURRENT_TIMESTAMP"),
                },
            )
            await session.execute(stmt)
            await session.flush()
            upserted += len(chunk)
            logger.info("  upserted %d/%d instruments", upserted, total)
        except Exception as exc:
            logger.error("Error upserting chunk %d-%d: %s", i, i + len(chunk), exc)
            await session.rollback()
            raise

    await session.commit()
    logger.info("US instrument sync finished — %d instruments upserted.", upserted)


async def fetch_and_store_prices(
    session: AsyncSession, instrument_id: int, ticker: str, days: int = 730
):
    try:
        dt_end = datetime.now()
        dt_start = dt_end - timedelta(days=days)

        logger.info("Fetching %s prices...", ticker)
        ticker_obj = yf.Ticker(ticker)
        df = await asyncio.to_thread(
            ticker_obj.history,
            start=dt_start.strftime("%Y-%m-%d"),
            end=dt_end.strftime("%Y-%m-%d"),
        )

        if df.empty:
            logger.warning("No price data found for %s", ticker)
            return

        df = df.reset_index()
        if pd.api.types.is_datetime64_any_dtype(df["Date"]):
            df["Date"] = df["Date"].dt.date

        df.rename(
            columns={
                "Date": "trade_date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            },
            inplace=True,
        )

        needed_cols = ["trade_date", "open", "high", "low", "close", "volume"]
        for col in needed_cols:
            if col not in df.columns:
                logger.warning("Missing column %s for %s", col, ticker)
                return

        df["avg_volume_50d"] = df["volume"].rolling(window=50, min_periods=1).mean()

        prices_data = []
        for _, row in df.iterrows():
            prices_data.append(
                {
                    "instrument_id": instrument_id,
                    "trade_date": row["trade_date"],
                    "open": float(row["open"]) if pd.notnull(row["open"]) else None,
                    "high": float(row["high"]) if pd.notnull(row["high"]) else None,
                    "low": float(row["low"]) if pd.notnull(row["low"]) else None,
                    "close": float(row["close"]) if pd.notnull(row["close"]) else None,
                    "volume": int(row["volume"]) if pd.notnull(row["volume"]) else 0,
                    "avg_volume_50d": int(row["avg_volume_50d"])
                    if pd.notnull(row["avg_volume_50d"])
                    else 0,
                }
            )

        if not prices_data:
            return

        stmt = insert(Price).values(prices_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["instrument_id", "trade_date"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "avg_volume_50d": stmt.excluded.avg_volume_50d,
            },
        )
        await session.execute(stmt)
        await session.commit()
        logger.info("Stored %d days of prices for %s", len(prices_data), ticker)
    except Exception as exc:
        logger.error("Error fetching prices for %s: %s", ticker, exc)


async def test_run():
    async with AsyncSessionLocal() as session:
        await sync_instruments(session)
        result = await session.execute(select(Instrument).where(Instrument.ticker == "AAPL"))
        aapl = result.scalar_one_or_none()
        if aapl:
            await fetch_and_store_prices(session, aapl.id, aapl.ticker)


if __name__ == "__main__":
    asyncio.run(test_run())
