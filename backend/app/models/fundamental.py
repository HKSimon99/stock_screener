from sqlalchemy import (
    BigInteger, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, UniqueConstraint, func
)
from app.core.database import Base


class FundamentalQuarterly(Base):
    __tablename__ = "fundamentals_quarterly"

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey("consensus_app.instruments.id"), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    fiscal_quarter = Column(Integer, nullable=False)    # 1–4
    report_date = Column(Date)                          # Date filed/reported
    revenue = Column(BigInteger)
    net_income = Column(BigInteger)
    eps = Column(Numeric(14, 4))
    eps_diluted = Column(Numeric(14, 4))

    # Pre-computed on ingestion
    eps_yoy_growth = Column(Numeric(10, 6))             # vs same quarter prior year
    revenue_yoy_growth = Column(Numeric(10, 6))

    data_source = Column(String(20))                    # 'EDGAR' | 'DART'
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "fiscal_year", "fiscal_quarter",
            name="uq_fundamental_q_instrument_period"
        ),
        {"schema": "consensus_app"},
    )


class FundamentalAnnual(Base):
    """
    Full annual snapshot: income statement + balance sheet + cash flow.
    All balance sheet / CF fields are required for Piotroski F-Score (Step 2.5).
    """
    __tablename__ = "fundamentals_annual"

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey("consensus_app.instruments.id"), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    report_date = Column(Date)

    # Income statement
    revenue = Column(BigInteger)
    gross_profit = Column(BigInteger)
    net_income = Column(BigInteger)
    eps = Column(Numeric(14, 4))
    eps_diluted = Column(Numeric(14, 4))
    eps_yoy_growth = Column(Numeric(10, 6))

    # Balance sheet (Piotroski F5, F6, F7)
    total_assets = Column(BigInteger)
    current_assets = Column(BigInteger)
    current_liabilities = Column(BigInteger)
    long_term_debt = Column(BigInteger)
    shares_outstanding_annual = Column(BigInteger)      # For dilution check (F7)

    # Cash flow (Piotroski F2, F4)
    operating_cash_flow = Column(BigInteger)

    # Pre-computed ratios (for Piotroski)
    roa = Column(Numeric(10, 6))                        # net_income / total_assets
    current_ratio = Column(Numeric(10, 6))              # current_assets / current_liabilities
    gross_margin = Column(Numeric(10, 6))               # gross_profit / revenue
    asset_turnover = Column(Numeric(10, 6))             # revenue / total_assets
    leverage_ratio = Column(Numeric(10, 6))             # long_term_debt / total_assets

    data_source = Column(String(20))
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "fiscal_year",
            name="uq_fundamental_a_instrument_year"
        ),
        {"schema": "consensus_app"},
    )
