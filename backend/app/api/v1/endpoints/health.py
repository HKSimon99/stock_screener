from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    counts = (
        await db.execute(
            text(
                """
                select
                  (select count(*) from consensus_app.instruments) as instruments,
                  (select count(*) from consensus_app.consensus_scores) as consensus_scores,
                  (select count(*) from consensus_app.instrument_coverage_summary) as coverage_summary
                """
            )
        )
    ).one()

    data_ready = bool(counts.instruments and counts.consensus_scores)
    return {
        "status": "ok" if data_ready else "degraded",
        "db": "connected",
        "data_ready": data_ready,
        "core_counts": {
            "instruments": counts.instruments,
            "consensus_scores": counts.consensus_scores,
            "coverage_summary": counts.coverage_summary,
        },
    }
