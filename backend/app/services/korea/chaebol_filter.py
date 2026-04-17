"""
Chaebol Filter
==============
Identifies Korean chaebols and flags cross-holding relationships.

The CANSLIM 'I' (Institutional) and 'S' (Supply) components are less
meaningful for chaebol affiliates because:
  - Institutional % is inflated by intra-group holdings
  - Float is artificially suppressed by cross-holding

Usage:
    from app.services.korea.chaebol_filter import is_chaebol, get_group, flag_cross_holdings

The `flag_cross_holdings` function updates instruments.is_chaebol_cross in the DB.
"""

import asyncio
import logging
from typing import Optional

from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument

logger = logging.getLogger(__name__)

# ── Chaebol Group Definitions ────────────────────────────────────────────────
# Maps each known chaebol group name to a list of ticker prefixes or full tickers.
# Tickers follow the 6-digit KOSPI/KOSDAQ format.
CHAEBOL_GROUPS: dict[str, list[str]] = {
    "Samsung": [
        "005930",  # Samsung Electronics
        "005935",  # Samsung Electronics preferred
        "000810",  # Samsung Fire & Marine Insurance
        "028260",  # Samsung C&T
        "018260",  # Samsung SDS
        "012750",  # S-1 (Samsung)
        "008770",  # Hotel Shilla (Samsung)
        "010140",  # Samsung Heavy Industries
        "042660",  # Daewoo Shipbuilding (Samsung affil.)
        "032830",  # Samsung Life Insurance
        "016360",  # Samsung Securities
        "029780",  # Samsung Card
    ],
    "SK": [
        "034730",  # SK Inc.
        "000660",  # SK Hynix
        "096770",  # SK Innovation
        "017670",  # SK Telecom
        "011760",  # SK Networks
        "285130",  # SK Chemicals
        "001740",  # SK Securities
        "035420",  # NAVER (SK affil.)
        "402340",  # SK Square
        "272210",  # Han-On Systems (SK)
    ],
    "Hyundai": [
        "005380",  # Hyundai Motor
        "000270",  # Kia
        "012330",  # Hyundai Mobis
        "005490",  # POSCO Holdings (Hyundai affil.)
        "047050",  # Hyundai Marine & Fire Insurance
        "001450",  # Hyundai Marine
        "267250",  # Hyundai Electric & Energy
        "064350",  # Hyundai Rotem
        "011210",  # Hyundai WIA
    ],
    "LG": [
        "003550",  # LG Corp.
        "066570",  # LG Electronics
        "051910",  # LG Chem
        "034220",  # LG Display
        "032640",  # LG Uplus
        "010120",  # LS Electric (LG affil.)
        "018880",  # Hanon Systems
        "035720",  # Kakao (LG affiliated minority)
        "373220",  # LG Energy Solution
        "011070",  # LG Innotek
    ],
    "Lotte": [
        "023530",  # Lotte Shopping
        "004990",  # Lotte Chilsung
        "002270",  # Lotte Confectionery
        "011170",  # Lotte Chemical
        "016390",  # Lotte Fine Chemical
    ],
    "Hanwha": [
        "000880",  # Hanwha
        "009830",  # Hanwha Solutions
        "012450",  # Hanwha Aerospace
        "088350",  # Hanwha Life
        "003490",  # Korean Air (Hanwha affil.)
    ],
    "Doosan": [
        "000150",  # Doosan
        "034020",  # Doosan Energy
        "336260",  # Doosan Bobcat
        "042670",  # Doosan Infracore
    ],
    "Posco": [
        "005490",  # POSCO Holdings
        "047050",  # POSCO International
        "010130",  # Korea Zinc (POSCO affil.)
    ],
    "Celltrion": [
        "068270",  # Celltrion
        "068760",  # Celltrion Healthcare
        "091990",  # Celltrion Pharm
    ],
    "Kakao": [
        "035720",  # Kakao
        "293490",  # Kakao Games
        "035420",  # NAVER (cross-listed)
        "403550",  # Kakao Pay
        "450080",  # Kakao Bank
    ],
}

# Build a reverse lookup: ticker → group name
_TICKER_TO_GROUP: dict[str, str] = {}
for _group, _tickers in CHAEBOL_GROUPS.items():
    for _t in _tickers:
        _TICKER_TO_GROUP[_t] = _group


def is_chaebol(ticker: str) -> bool:
    """Return True if ticker belongs to a known chaebol group."""
    return ticker in _TICKER_TO_GROUP


def get_group(ticker: str) -> Optional[str]:
    """Return the chaebol group name for a ticker, or None if not a chaebol."""
    return _TICKER_TO_GROUP.get(ticker)


def shares_same_group(ticker_a: str, ticker_b: str) -> bool:
    """Return True if both tickers belong to the same chaebol group."""
    g_a = get_group(ticker_a)
    g_b = get_group(ticker_b)
    return g_a is not None and g_a == g_b


async def flag_cross_holdings() -> dict[str, int]:
    """
    Set instruments.is_chaebol_cross = True for all KR instruments that are
    in a known chaebol group.

    Returns a dict with 'flagged' and 'skipped' counts.
    """
    stats = {"flagged": 0, "skipped": 0}

    async with AsyncSessionLocal() as db:
        stmt = select(Instrument).where(Instrument.market == "KR")
        result = await db.execute(stmt)
        instruments = result.scalars().all()

        for inst in instruments:
            in_group = is_chaebol(inst.ticker)
            if in_group and not inst.is_chaebol_cross:
                inst.is_chaebol_cross = True
                stats["flagged"] += 1
            elif not in_group and inst.is_chaebol_cross:
                # Previously flagged but no longer in list — unset
                inst.is_chaebol_cross = False
            else:
                stats["skipped"] += 1

        await db.commit()

    logger.info(
        f"Chaebol cross-holding flag run: "
        f"{stats['flagged']} flagged, {stats['skipped']} unchanged"
    )
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(flag_cross_holdings())
