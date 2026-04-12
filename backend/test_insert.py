import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument

async def test_db():
    async with AsyncSessionLocal() as session:
        # Insert a test instrument
        new_instrument = Instrument(
            ticker="TEST_AAPL",
            name="Test Apple Inc.",
            market="US",
            exchange="NASDAQ",
            asset_type="stock",
            sector="Technology",
            is_active=True
        )
        session.add(new_instrument)
        try:
            await session.commit()
            print("Successfully inserted instrument!")
        except Exception as e:
            await session.rollback()
            print("Insert failed. Exception:", e)

        # Query the instrument back
        result = await session.execute(
            select(Instrument).where(Instrument.ticker == "TEST_AAPL")
        )
        instrument = result.scalar_one_or_none()
        
        if instrument:
            print(f"Queried instrument: ID={instrument.id}, Name={instrument.name}, Sector={instrument.sector}")
            
            # Clean up the test instrument
            await session.delete(instrument)
            await session.commit()
            print("Cleaned up test instrument.")
        else:
            print("Query failed, instrument not found.")

if __name__ == "__main__":
    asyncio.run(test_db())
