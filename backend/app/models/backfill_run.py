from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class AdminBackfillRun(Base):
    __tablename__ = "admin_backfill_runs"

    id = Column(BigInteger, primary_key=True)
    market = Column(String(4), nullable=False)
    requested_tickers = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    selected_tickers = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    limit_requested = Column(Integer, nullable=True)
    chunk_size = Column(Integer, nullable=False, server_default="25")
    price_only = Column(Boolean, nullable=False, server_default="false")
    score_requested = Column(Boolean, nullable=False, server_default="false")
    status = Column(String(20), nullable=False, server_default="queued")
    requester_source = Column(String(30), nullable=False, server_default="api_key")
    requester_user_id = Column(String(128), nullable=True)
    celery_task_id = Column(String(155), nullable=True)
    requested_count = Column(Integer, nullable=False, server_default="0")
    selected_count = Column(Integer, nullable=False, server_default="0")
    processed_count = Column(Integer, nullable=False, server_default="0")
    failed_count = Column(Integer, nullable=False, server_default="0")
    queued_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    error_message = Column(Text, nullable=True)
    result_metadata = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        Index("idx_admin_backfill_runs_status_queued_at", "status", "queued_at"),
        Index("idx_admin_backfill_runs_market_queued_at", "market", "queued_at"),
        {"schema": "consensus_app"},
    )
