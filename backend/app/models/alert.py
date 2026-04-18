from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
)
from app.core.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey("consensus_app.instruments.id"), nullable=True)  # NULL = market-level
    market = Column(String(4))

    # STOP_LOSS | REGIME_CHANGE | EARNINGS_DECEL | RS_BREAKDOWN
    # VOLUME_SURGE | PIOTROSKI_DROP | STAGE_CHANGE | SECTOR_CONCENTRATION
    alert_type = Column(String(30), nullable=False)

    # CRITICAL | WARNING | INFO
    severity = Column(String(10), nullable=False)

    title = Column(String(200))
    detail = Column(Text)
    threshold_value = Column(Numeric(14, 4))
    actual_value = Column(Numeric(14, 4))
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = {"schema": "consensus_app"}
