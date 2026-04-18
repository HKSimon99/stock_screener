from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, ForeignKey,
    Integer, Numeric, String, UniqueConstraint, func
)
from app.core.database import Base


class InstitutionalOwnership(Base):
    """
    US: sourced from SEC 13F quarterly bulk data.
    KR: sourced from KIS Developers investor-category API (foreign/institutional/individual).
    """
    __tablename__ = "institutional_ownership"

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey("consensus_app.instruments.id"), nullable=False)
    report_date = Column(Date, nullable=False)

    # US fields (from 13F)
    num_institutional_owners = Column(Integer)
    institutional_pct = Column(Numeric(8, 6))       # 0.0 – 1.0
    top_fund_quality_score = Column(Numeric(6, 2))  # Avg perf rank of top-10 holders
    qoq_owner_change = Column(Integer)              # Net new institutions vs prior quarter

    # KR fields (from KIS investor-category API)
    foreign_ownership_pct = Column(Numeric(8, 6))
    foreign_net_buy_30d = Column(BigInteger)        # Net foreign shares bought, 30 days
    institutional_net_buy_30d = Column(BigInteger)  # Net institutional shares bought, 30d
    individual_net_buy_30d = Column(BigInteger)     # Net individual shares bought, 30d

    # Common
    is_buyback_active = Column(Boolean, default=False, nullable=False)
    data_source = Column(String(20))
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "report_date",
            name="uq_institutional_instrument_date"
        ),
        {"schema": "consensus_app"},
    )
