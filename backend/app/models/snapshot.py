from sqlalchemy import (
    Column, Date, DateTime, Integer, String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base


class ScoringSnapshot(Base):
    """
    Immutable point-in-time ranking record.
    Same (date, market, asset_type) inputs must always produce identical rankings_json.
    config_hash captures the scoring config version for auditability.
    """
    __tablename__ = "scoring_snapshots"

    id = Column(Integer, primary_key=True)
    snapshot_date = Column(Date, nullable=False)
    market = Column(String(4), nullable=False)
    asset_type = Column(String(10), nullable=False)  # 'stock' | 'etf'
    regime_state = Column(String(30))
    rankings_json = Column(JSONB, nullable=False)    # Full ranked list with scores
    metadata_ = Column("metadata", JSONB)            # config_hash, freshness summary, version
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "snapshot_date", "market", "asset_type",
            name="uq_snapshot_date_market_type"
        ),
        {"schema": "consensus_app"},
    )


class DataFreshness(Base):
    """Tracks last success/failure time per data source for freshness warnings."""
    __tablename__ = "data_freshness"

    id = Column(Integer, primary_key=True)
    source_name = Column(String(50), nullable=False)     # 'US_PRICES' | 'KR_FUNDAMENTALS' etc.
    market = Column(String(4), nullable=False)
    last_success_at = Column(DateTime(timezone=True))
    last_failure_at = Column(DateTime(timezone=True))
    last_error = Column(Text)
    records_updated = Column(Integer)
    next_expected = Column(DateTime(timezone=True))
    staleness_threshold_hours = Column(Integer)          # Alert if older than this

    __table_args__ = (
        UniqueConstraint("source_name", "market", name="uq_data_freshness_source_market"),
        {"schema": "consensus_app"},
    )
