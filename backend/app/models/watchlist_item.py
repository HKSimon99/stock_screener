from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)

from app.core.database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(String(128), nullable=False)
    instrument_id = Column(
        Integer,
        ForeignKey("consensus_app.instruments.id", ondelete="CASCADE"),
        nullable=False,
    )
    market = Column(String(4), nullable=False)
    ticker = Column(String(20), nullable=False)
    added_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_watchlist_items_user_id_added_at", "user_id", "added_at"),
        UniqueConstraint(
            "user_id",
            "instrument_id",
            name="uq_watchlist_items_user_instrument",
        ),
        {"schema": "consensus_app"},
    )
