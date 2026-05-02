import datetime
from sqlalchemy import String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    """
    Per-user app state, keyed by Clerk user_id.

    Created lazily on first ToS acceptance (or on first auth-required call
    that needs to read user state). Email is captured at acceptance time so
    we can reach the user about ToS changes without round-tripping Clerk.
    """
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_clerk_user_id", "clerk_user_id", unique=True),
        {"schema": "consensus_app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    clerk_user_id: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    tos_accepted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tos_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserPushToken(Base):
    __tablename__ = "user_push_tokens"
    __table_args__ = (
        Index("ix_user_push_tokens_user_id", "user_id"),
        {"schema": "consensus_app"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    expo_push_token: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
