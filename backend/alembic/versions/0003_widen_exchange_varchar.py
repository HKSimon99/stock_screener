"""Widen instruments.exchange from VARCHAR(10) to VARCHAR(50)

NYSE American (12 chars) exceeded the old limit, causing StringDataRightTruncationError
during US instrument sync.

Revision ID: 0003_widen_exchange_varchar
Revises: e6b28b19d844
Create Date: 2026-04-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_widen_exchange_varchar"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "instruments",
        "exchange",
        existing_type=sa.String(10),
        type_=sa.String(50),
        existing_nullable=False,
        schema="consensus_app",
    )


def downgrade() -> None:
    op.alter_column(
        "instruments",
        "exchange",
        existing_type=sa.String(50),
        type_=sa.String(10),
        existing_nullable=False,
        schema="consensus_app",
    )
