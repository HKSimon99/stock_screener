from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base


class ConsensusScore(Base):
    """
    Multi-strategy consensus result per instrument per day.
    Aggregates all 5 strategy scores → conviction level + final_score.
    """
    __tablename__ = "consensus_scores"

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey("consensus_app.instruments.id"), nullable=False)
    score_date = Column(Date, nullable=False)

    # Strategy composite scores (0–100 each)
    canslim_score = Column(Numeric(5, 2))
    piotroski_score = Column(Numeric(5, 2))
    minervini_score = Column(Numeric(5, 2))
    weinstein_score = Column(Numeric(5, 2))
    dual_mom_score = Column(Numeric(5, 2))
    technical_composite = Column(Numeric(5, 2))

    # Consensus aggregation
    strategy_pass_count = Column(Integer)           # Strategies scoring ≥ 70 (out of 5)
    consensus_composite = Column(Numeric(5, 2))     # Weighted avg of 5 strategies
    final_score = Column(Numeric(5, 2))             # 75% consensus + 25% technical

    # Conviction level: DIAMOND | GOLD | SILVER | BRONZE | UNRANKED
    conviction_level = Column(String(10), nullable=False, default="UNRANKED")

    # Regime gate
    regime_state = Column(String(30))
    regime_warning = Column(Boolean, default=False, nullable=False)

    # For display / debugging
    score_breakdown = Column(JSONB)

    computed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "score_date",
            name="uq_consensus_score_instrument_date"
        ),
        {"schema": "consensus_app"},
    )
