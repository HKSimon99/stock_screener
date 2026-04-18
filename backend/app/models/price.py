from sqlalchemy import BigInteger, Column, Date, ForeignKey, Integer, Numeric, PrimaryKeyConstraint
from app.core.database import Base


class Price(Base):
    """Daily OHLCV — converted to a TimescaleDB hypertable in the migration."""
    __tablename__ = "prices"

    instrument_id = Column(Integer, ForeignKey("consensus_app.instruments.id"), nullable=False)
    trade_date = Column(Date, nullable=False)
    open = Column(Numeric(14, 4))
    high = Column(Numeric(14, 4))
    low = Column(Numeric(14, 4))
    close = Column(Numeric(14, 4))
    volume = Column(BigInteger)
    avg_volume_50d = Column(BigInteger)   # Pre-computed rolling 50-day average

    __table_args__ = (
        PrimaryKeyConstraint("instrument_id", "trade_date"),
        {"schema": "consensus_app"},
    )
