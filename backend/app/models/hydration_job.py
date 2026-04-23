from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class HydrationJob(Base):
    """Durable user-facing status for explicit instrument refresh jobs."""

    __tablename__ = "hydration_jobs"

    id = Column(BigInteger, primary_key=True)
    ticker = Column(String(20), nullable=False)
    market = Column(String(4), nullable=False)
    instrument_id = Column(
        Integer,
        ForeignKey("consensus_app.instruments.id", ondelete="SET NULL"),
        nullable=True,
    )

    status = Column(String(20), nullable=False, server_default="queued")
    requester_source = Column(String(30), nullable=False, server_default="user")
    requester_user_id = Column(String(128), nullable=True)
    celery_task_id = Column(String(155), nullable=True)

    queued_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    error_message = Column(Text, nullable=True)
    source_metadata = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        Index("idx_hydration_jobs_market_ticker", "market", "ticker"),
        Index("idx_hydration_jobs_status_queued_at", "status", "queued_at"),
        Index("idx_hydration_jobs_instrument_id", "instrument_id"),
        Index(
            "idx_hydration_jobs_requester_queued_at",
            "requester_user_id",
            "queued_at",
            postgresql_where=text("requester_user_id IS NOT NULL"),
        ),
        Index(
            "uq_hydration_jobs_active_symbol",
            "market",
            "ticker",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        {"schema": "consensus_app"},
    )
