"""add security master fields to instruments

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "instruments",
        sa.Column("listing_status", sa.String(length=20), nullable=False, server_default="LISTED"),
    )
    op.add_column(
        "instruments",
        sa.Column("is_test_issue", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("instruments", sa.Column("source_provenance", sa.String(length=80), nullable=True))
    op.add_column("instruments", sa.Column("source_symbol", sa.String(length=40), nullable=True))
    op.add_column("instruments", sa.Column("delisted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("instruments", "delisted_at")
    op.drop_column("instruments", "source_symbol")
    op.drop_column("instruments", "source_provenance")
    op.drop_column("instruments", "is_test_issue")
    op.drop_column("instruments", "listing_status")
