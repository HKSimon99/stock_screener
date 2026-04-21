"""
Populate KR prices (via pykrx fallback) for top stocks, then run full scoring pipeline.
Run with: cd backend && uv run python populate_kr_and_score.py
"""
import asyncio
import os
import sys
import logging

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Top KR stocks by market cap (KOSPI + KOSDAQ)
TOP_KR_TICKERS = [
    "005930",  # Samsung Electronics
    "000660",  # SK Hynix
    "035420",  # NAVER
    "005380",  # Hyundai Motor
    "051910",  # LG Chem
    "006400",  # Samsung SDI
    "068270",  # Celltrion
    "028260",  # Samsung C&T
    "000270",  # Kia
    "207940",  # Samsung Biologics
    "373220",  # LG Energy Solution
    "003550",  # LG Corp
    "035720",  # Kakao
    "086790",  # Hana Financial Group
    "105560",  # KB Financial Group
    "055550",  # Shinhan Financial Group
    "032830",  # Samsung Life Insurance
    "009150",  # Samsung Electro-Mechanics
    "066570",  # LG Electronics
    "011200",  # HMM (Hyundai Merchant Marine)
]


async def run_kr_prices():
    from app.tasks.ingestion_tasks import run_kr_price_ingestion
    logger.info("Starting KR price ingestion for %d tickers via pykrx...", len(TOP_KR_TICKERS))
    result = await run_kr_price_ingestion(
        tickers=TOP_KR_TICKERS,
        days=365,
    )
    logger.info(
        "KR price ingestion done: processed=%d, failed=%d",
        result["processed_count"],
        result["failed_count"],
    )
    if result["failed_tickers"]:
        logger.warning("Failed tickers: %s", result["failed_tickers"])
    return result


async def run_scoring():
    from app.tasks.scoring_tasks import run_full_scoring_pipeline
    logger.info("Running full scoring pipeline (US + KR)...")
    result = await run_full_scoring_pipeline()
    logger.info(
        "Scoring done: consensus_scored=%d, conviction_distribution=%s",
        result["consensus_scored"],
        result["conviction_distribution"],
    )
    return result


async def main():
    # Step 1: KR prices
    kr_result = await run_kr_prices()

    # Step 2: Full scoring pipeline
    score_result = await run_scoring()

    print("\n=== SUMMARY ===")
    print(f"KR prices processed: {kr_result['processed_count']}/{kr_result['requested_count']}")
    print(f"KR prices failed:    {kr_result['failed_count']}")
    print(f"Instruments scored:  {score_result['unique_instruments_scored']}")
    print(f"Conviction dist:     {score_result['conviction_distribution']}")
    print(f"Snapshots generated: {score_result['snapshots_generated']}")


if __name__ == "__main__":
    asyncio.run(main())
