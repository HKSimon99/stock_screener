from sqlalchemy import (
    Column, Date, DateTime, ForeignKey, Integer,
    Numeric, UniqueConstraint, func
)
from app.core.database import Base


class EtfConstituent(Base):
    __tablename__ = "etf_constituents"

    id = Column(Integer, primary_key=True)
    etf_id = Column(Integer, ForeignKey("consensus_app.instruments.id"), nullable=False)
    constituent_id = Column(Integer, ForeignKey("consensus_app.instruments.id"), nullable=False)
    weight = Column(Numeric(10, 8))                 # 0.0 – 1.0
    as_of_date = Column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "etf_id", "constituent_id", "as_of_date",
            name="uq_etf_constituent"
        ),
        {"schema": "consensus_app"},
    )


class EtfScore(Base):
    __tablename__ = "etf_scores"

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey("consensus_app.instruments.id"), nullable=False)
    score_date = Column(Date, nullable=False)

    # Constituent-derived
    weighted_consensus = Column(Numeric(5, 2))      # Weighted avg constituent final_score
    pct_diamond_gold = Column(Numeric(5, 2))        # % constituents at DIAMOND or GOLD

    # ETF-specific factors
    fund_flow_score = Column(Numeric(5, 2))         # AUM change 30d (S-proxy)
    rs_vs_sector = Column(Numeric(5, 2))            # RS rank among sector peers
    expense_score = Column(Numeric(5, 2))           # Lower expense = higher score
    aum_score = Column(Numeric(5, 2))               # Liquidity proxy

    composite = Column(Numeric(5, 2))
    computed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "score_date",
            name="uq_etf_score_instrument_date"
        ),
        {"schema": "consensus_app"},
    )
