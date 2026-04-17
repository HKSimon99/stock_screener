from datetime import date, datetime, timezone
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update
from sqlalchemy.dialects.postgresql import insert

from app.models.instrument import Instrument
from app.models.etf import EtfConstituent, EtfScore
from app.models.consensus_score import ConsensusScore

class EtfScorer:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def score_all_etfs(self, score_date: date) -> tuple[int, int]:
        """
        Calculates consensus scores for all active ETFs by aggregating their constituent scores.
        Only processes ETFs that have constituent data for the given date (or latest prior date).
        
        Returns: (scored_count, skipped_count)
        """
        # Get all active ETFs
        etf_q = await self.db.execute(
            select(Instrument).where(Instrument.asset_type == "etf", Instrument.is_active == True)
        )
        etfs = etf_q.scalars().all()
        
        skipped = 0
        scored = 0

        for etf in etfs:
            if "bear" in (etf.name or "").lower() or "inverse" in (etf.name or "").lower() or "short" in (etf.name or "").lower() or "2x" in (etf.name or "").lower() or "3x" in (etf.name or "").lower():
                # Exclude leveraged/inverse ETFs based on heuristics
                skipped += 1
                continue
                
            # Get latest constituent mapping for this ETF
            lat_date_q = await self.db.execute(
                select(func.max(EtfConstituent.as_of_date))
                .where(EtfConstituent.etf_id == etf.id, EtfConstituent.as_of_date <= score_date)
            )
            lat_date_res = lat_date_q.scalar_one_or_none()
            
            if not lat_date_res:
                skipped += 1
                continue
                
            # Fetch constituents and their consensus scores for `score_date`
            stmt = (
                select(EtfConstituent, ConsensusScore)
                .join(ConsensusScore, ConsensusScore.instrument_id == EtfConstituent.constituent_id)
                .where(
                    EtfConstituent.etf_id == etf.id,
                    EtfConstituent.as_of_date == lat_date_res,
                    ConsensusScore.score_date == score_date
                )
            )
            res = await self.db.execute(stmt)
            rows = res.all()
            
            if not rows:
                skipped += 1
                continue
                
            # We don't normalize weights here; we just sum them. Assuming weights sum to ~1.0.
            total_weight = 0.0
            weighted_score_sum = 0.0
            high_conviction_weight = 0.0
            total_mapped_weight = 0.0

            for const_row, cons_row in rows:
                w = float(const_row.weight)
                fs = float(cons_row.final_score) if cons_row.final_score else 0.0
                
                weighted_score_sum += (fs * w)
                total_mapped_weight += w
                
                if cons_row.conviction_level in ("DIAMOND", "GOLD"):
                    high_conviction_weight += w
                    
            if total_mapped_weight == 0:
                skipped += 1
                continue
                
            # Normalize in case we didn't map 100% of holdings
            avg_score = weighted_score_sum / total_mapped_weight
            pct_high = high_conviction_weight / total_mapped_weight * 100.0
            
            # Formulate the composite score for the ETF itself
            # We'll weigh the aggregated average (70%) and % High conviction holdings (30%)
            # e.g. An ETF with 50% GOLD components and average score of 60:
            # 60 * 0.70 + 50 * 0.30 = 42 + 15 = 57 final_score
            final_composite = (avg_score * 0.70) + (pct_high * 0.30)
            
            # Map back to Conviction Levels for standardizing APIs
            if final_composite >= 70:
                conviction = "DIAMOND"
            elif final_composite >= 55:
                conviction = "GOLD"
            elif final_composite >= 40:
                conviction = "SILVER"
            elif final_composite >= 25:
                conviction = "BRONZE"
            else:
                conviction = "UNRANKED"
                
            # Save to EtfScore
            etf_score_values = dict(
                instrument_id=etf.id,
                score_date=score_date,
                weighted_consensus=avg_score,
                pct_diamond_gold=pct_high,
                composite=final_composite,
                computed_at=datetime.now(timezone.utc)
            )
            
            es_stmt = insert(EtfScore).values(**etf_score_values)
            es_stmt = es_stmt.on_conflict_do_update(
                index_elements=["instrument_id", "score_date"],
                set_=dict(
                    weighted_consensus=es_stmt.excluded.weighted_consensus,
                    pct_diamond_gold=es_stmt.excluded.pct_diamond_gold,
                    composite=es_stmt.excluded.composite,
                    computed_at=es_stmt.excluded.computed_at
                )
            )
            await self.db.execute(es_stmt)
            
            # Also save to ConsensusScore so it shows up seamlessly in the Leaderboard
            score_breakdown = {
                "scored_constituents_weight_pct": total_mapped_weight * 100.0,
                "weighted_consensus": avg_score,
                "pct_diamond_gold": pct_high
            }
            cs_values = dict(
                instrument_id=etf.id,
                score_date=score_date,
                final_score=final_composite,
                consensus_composite=avg_score,
                conviction_level=conviction,
                strategy_pass_count=0, # Not applicable
                regime_warning=False,
                score_breakdown=score_breakdown,
                computed_at=datetime.now(timezone.utc)
            )
            
            cs_stmt = insert(ConsensusScore).values(**cs_values)
            cs_stmt = cs_stmt.on_conflict_do_update(
                index_elements=["instrument_id", "score_date"],
                set_=dict(
                    final_score=cs_stmt.excluded.final_score,
                    consensus_composite=cs_stmt.excluded.consensus_composite,
                    conviction_level=cs_stmt.excluded.conviction_level,
                    score_breakdown=cs_stmt.excluded.score_breakdown,
                    computed_at=cs_stmt.excluded.computed_at
                )
            )
            await self.db.execute(cs_stmt)
            scored += 1
            
        await self.db.commit()
        return scored, skipped

async def debug_etf_scorer():
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        scorer = EtfScorer(db)
        s, sk = await scorer.score_all_etfs(date.today())
        print(f"Scored {s} ETFs, skipped {sk}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(debug_etf_scorer())
