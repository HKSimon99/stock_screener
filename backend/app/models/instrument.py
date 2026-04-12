from sqlalchemy import (
    Boolean, Column, DateTime, Integer, Numeric, String, UniqueConstraint, func
)
from app.core.database import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False)
    name = Column(String(200), nullable=False)
    name_kr = Column(String(200))                   # Korean name for KR stocks
    market = Column(String(4), nullable=False)       # 'US' | 'KR'
    exchange = Column(String(10), nullable=False)    # 'NYSE'|'NASDAQ'|'KOSPI'|'KOSDAQ'
    asset_type = Column(String(10), nullable=False)  # 'stock' | 'etf'
    sector = Column(String(100))
    industry_group = Column(String(100))
    shares_outstanding = Column(Numeric(20, 0))
    float_shares = Column(Numeric(20, 0))
    is_active = Column(Boolean, default=True, nullable=False)

    # KR-specific
    corp_code = Column(String(8))                    # OpenDART 8-digit code
    is_chaebol_cross = Column(Boolean, default=False, nullable=False)

    # ETF-specific
    is_leveraged = Column(Boolean, default=False, nullable=False)
    is_inverse = Column(Boolean, default=False, nullable=False)
    expense_ratio = Column(Numeric(6, 4))
    aum = Column(Numeric(20, 0))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("ticker", "market", name="uq_instrument_ticker_market"),
    )
