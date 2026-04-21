"""
Targeted scoring: only score instruments that have price data.
Run with: cd backend && uv run python targeted_score.py
"""
import asyncio
import logging
import os
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.WARNING,   # suppress SQLAlchemy noise
    format="%(levelname)s %(name)s: %(message)s"
)
# Only show app-level logs at INFO
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("__main__").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


async def get_instrument_ids_with_prices():
    """Return list of instrument IDs that have at least one price row."""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text
    async with AsyncSessionLocal() as db:
        r = await db.execute(text("""
            SELECT DISTINCT p.instrument_id, i.market, i.ticker
            FROM consensus_app.prices p
            JOIN consensus_app.instruments i ON i.id = p.instrument_id
            ORDER BY i.market, i.ticker
        """))
        rows = r.fetchall()
    return rows


async def check_db_state():
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text
    async with AsyncSessionLocal() as db:
        # Price counts
        r = await db.execute(text("""
            SELECT i.market, COUNT(DISTINCT p.instrument_id) as instr, COUNT(*) as rows
            FROM consensus_app.prices p
            JOIN consensus_app.instruments i ON i.id = p.instrument_id
            GROUP BY i.market
        """))
        print("\n=== PRICE DATA ===")
        for row in r:
            print(f"  {row[0]}: {row[1]} instruments, {row[2]} price rows")

        # Consensus scores
        r = await db.execute(text("""
            SELECT COUNT(*) FROM consensus_app.consensus_scores
        """))
        print(f"\n  consensus_scores rows: {r.scalar()}")

        r = await db.execute(text("""
            SELECT COUNT(*) FROM consensus_app.scoring_snapshots
        """))
        print(f"  scoring_snapshots rows: {r.scalar()}")


async def main():
    await check_db_state()

    rows = await get_instrument_ids_with_prices()
    if not rows:
        print("\nERROR: No instruments have price data! Run price ingestion first.")
        return

    instrument_ids = [row[0] for row in rows]
    print(f"\nRunning full scoring for {len(instrument_ids)} instruments with price data:")
    for row in rows:
        print(f"  [{row[0]}] {row[1]} {row[2]}")

    from app.tasks.scoring_tasks import run_full_scoring_pipeline

    print("\nStarting scoring pipeline...")
    result = await run_full_scoring_pipeline(
        instrument_ids=instrument_ids,
    )

    print("\n=== SCORING RESULT ===")
    print(f"  CANSLIM scored:      {result['canslim_scored']}")
    print(f"  Piotroski scored:    {result['piotroski_scored']}")
    print(f"  Minervini scored:    {result['minervini_scored']}")
    print(f"  Weinstein scored:    {result['weinstein_scored']}")
    print(f"  Consensus scored:    {result['consensus_scored']}")
    print(f"  Snapshots generated: {result['snapshots_generated']}")
    print(f"  Conviction dist:     {result['conviction_distribution']}")
    print(f"  Total instruments:   {result['unique_instruments_scored']}")

    await check_db_state()


if __name__ == "__main__":
    asyncio.run(main())
