from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class InstrumentCoverageSummary(Base):
    __tablename__ = "instrument_coverage_summary"

    instrument_id = Column(
        Integer,
        ForeignKey("consensus_app.instruments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    coverage_state = Column(String(30), nullable=False, default="searchable")
    price_bar_count = Column(Integer, nullable=False, default=0)
    price_as_of = Column(Date)
    quarterly_as_of = Column(Date)
    annual_as_of = Column(Date)
    ranked_as_of = Column(Date)
    ranking_eligible = Column(Boolean, nullable=False, default=False)
    ranking_reasons = Column(JSONB, nullable=False, default=list)
    delay_minutes = Column(Integer)
    rank_model_version = Column(String(50), nullable=False, default="consensus-v1-foundation")
    refreshed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = ({"schema": "consensus_app"},)
