import asyncio
import csv
import io
import logging
from datetime import datetime, timedelta

import httpx
import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument
from app.models.price import Price
from app.services.taxonomy import normalize_exchange, normalize_sector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NASDAQ_DIRECTORY_URLS = {
    "nasdaqlisted": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "otherlisted": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}
ALPACA_DATA_BASE_URL = "https://data.alpaca.markets"
ALPACA_BARS_LIMIT = 10000
ALPACA_SYMBOL_CHUNK_SIZE = 100
PRICE_UPSERT_CHUNK_SIZE = 1000
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


class AlpacaPriceError(Exception):
    """Raised when Alpaca market data cannot be fetched or parsed."""


def _normalize_ticker(symbol: str) -> str:
    return symbol.strip().replace("$", "").replace(".", "-")


def _is_supported_security(security_name: str, *, etf_flag: str) -> bool:
    if etf_flag == "Y":
        return False
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
            "exchange": normalize_exchange("NASDAQ"),
            "asset_type": "stock",
            "listing_status": "LISTED",
            "sector": normalize_sector(None),
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
        "exchange": normalize_exchange(EXCHANGE_CODE_MAP.get(exchange_code, exchange_code or "OTHER")),
        "asset_type": "stock",
        "listing_status": "LISTED",
        "sector": normalize_sector(None),
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
) -> int:
    counts = await fetch_and_store_prices_batch(session, [(instrument_id, ticker)], days=days)
    return counts.get(ticker, 0)


def _alpaca_headers() -> dict[str, str]:
    if not settings.alpaca_api_key_id or not settings.alpaca_api_secret_key:
        raise AlpacaPriceError(
            "Missing Alpaca credentials. Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY."
        )
    return {
        "APCA-API-KEY-ID": settings.alpaca_api_key_id,
        "APCA-API-SECRET-KEY": settings.alpaca_api_secret_key,
        "User-Agent": "Consensus/1.0",
    }


def _chunked(values: list, size: int) -> list[list]:
    return [values[index : index + size] for index in range(0, len(values), size)]


async def _fetch_alpaca_bars(
    tickers: list[str],
    *,
    dt_start: datetime,
    dt_end: datetime,
) -> dict[str, pd.DataFrame]:
    if not tickers:
        return {}

    bars_by_ticker: dict[str, list[dict]] = {ticker: [] for ticker in tickers}
    params = {
        "symbols": ",".join(tickers),
        "timeframe": "1Day",
        "start": dt_start.date().isoformat(),
        "end": dt_end.date().isoformat(),
        "adjustment": "all",
        "feed": settings.alpaca_data_feed or "iex",
        "limit": ALPACA_BARS_LIMIT,
    }

    async with httpx.AsyncClient(headers=_alpaca_headers(), timeout=45.0) as client:
        page_token: str | None = None
        while True:
            request_params = dict(params)
            if page_token:
                request_params["page_token"] = page_token
            response = await client.get(
                f"{ALPACA_DATA_BASE_URL}/v2/stocks/bars",
                params=request_params,
            )
            response.raise_for_status()
            payload = response.json()
            raw_bars = payload.get("bars")
            if not isinstance(raw_bars, dict):
                raise AlpacaPriceError("Alpaca response did not include a bars object.")
            for ticker, rows in raw_bars.items():
                if ticker in bars_by_ticker and isinstance(rows, list):
                    bars_by_ticker[ticker].extend(rows)
            page_token = payload.get("next_page_token")
            if not page_token:
                break

    frames: dict[str, pd.DataFrame] = {}
    for ticker, rows in bars_by_ticker.items():
        if not rows:
            frames[ticker] = pd.DataFrame()
            continue
        df = pd.DataFrame(rows)
        column_map = {
            "t": "trade_date",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
        }
        df = df.rename(columns=column_map)
        needed_cols = ["trade_date", "open", "high", "low", "close", "volume"]
        missing = [column for column in needed_cols if column not in df.columns]
        if missing:
            raise AlpacaPriceError(f"Alpaca bars for {ticker} missing columns: {missing}")
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        frames[ticker] = df[needed_cols].sort_values("trade_date")
    return frames


def _price_rows_for_frame(instrument_id: int, df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    df = df.copy()
    df["avg_volume_50d"] = df["volume"].rolling(window=50, min_periods=1).mean()
    return [
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
        for _, row in df.iterrows()
    ]


async def _upsert_price_rows(session: AsyncSession, prices_data: list[dict]) -> None:
    if not prices_data:
        return
    for chunk in _chunked(prices_data, PRICE_UPSERT_CHUNK_SIZE):
        stmt = insert(Price).values(chunk)
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


async def fetch_and_store_prices_batch(
    session: AsyncSession,
    instrument_refs: list[tuple[int, str]],
    days: int = 730,
) -> dict[str, int]:
    if not instrument_refs:
        return {}

    dt_end = datetime.now()
    dt_start = dt_end - timedelta(days=days)
    counts: dict[str, int] = {ticker: 0 for _, ticker in instrument_refs}

    for refs_chunk in _chunked(instrument_refs, ALPACA_SYMBOL_CHUNK_SIZE):
        tickers = [ticker for _, ticker in refs_chunk]
        logger.info(
            "Fetching %d US tickers from Alpaca (%s to %s)...",
            len(tickers),
            dt_start.date(),
            dt_end.date(),
        )
        frames = await _fetch_alpaca_bars(tickers, dt_start=dt_start, dt_end=dt_end)
        rows_to_upsert: list[dict] = []
        for instrument_id, ticker in refs_chunk:
            frame = frames.get(ticker, pd.DataFrame())
            ticker_rows = _price_rows_for_frame(instrument_id, frame)
            if not ticker_rows:
                logger.warning("No Alpaca price data found for %s", ticker)
                continue
            counts[ticker] = len(ticker_rows)
            rows_to_upsert.extend(ticker_rows)

        await _upsert_price_rows(session, rows_to_upsert)
        await session.commit()
        logger.info("Stored %d US price rows from Alpaca.", len(rows_to_upsert))

    return counts


async def test_run():
    async with AsyncSessionLocal() as session:
        await sync_instruments(session)
        result = await session.execute(select(Instrument).where(Instrument.ticker == "AAPL"))
        aapl = result.scalar_one_or_none()
        if aapl:
            await fetch_and_store_prices(session, aapl.id, aapl.ticker)


if __name__ == "__main__":
    asyncio.run(test_run())
