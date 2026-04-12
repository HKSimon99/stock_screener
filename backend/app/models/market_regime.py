from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint, func
)
from app.core.database import Base


class MarketRegime(Base):
    """
    Daily market regime state per market (US / KR).
    Drives the M-factor gate across all strategy scoring.
    """
    __tablename__ = "market_regime"

    id = Column(Integer, primary_key=True)
    market = Column(String(4), nullable=False)       # 'US' | 'KR'
    effective_date = Column(Date, nullable=False)

    # State: CONFIRMED_UPTREND | UPTREND_UNDER_PRESSURE | MARKET_IN_CORRECTION
    state = Column(String(30), nullable=False)
    prior_state = Column(String(30))
    trigger_reason = Column(Text)

    # Underlying signals
    index_ticker = Column(String(10))               # 'SPY' | 'KOSPI' | 'KOSDAQ'
    index_close = Column(Numeric(14, 4))
    index_50dma = Column(Numeric(14, 4))
    index_200dma = Column(Numeric(14, 4))
    drawdown_from_high = Column(Numeric(8, 6))      # e.g. 0.12 = 12% below 52w high
    distribution_day_count = Column(Integer)        # In rolling 25-session window
    follow_through_day = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("market", "effective_date", name="uq_market_regime_market_date"),
    )
