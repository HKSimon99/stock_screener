"""Add PLATINUM conviction level (document valid values via CHECK constraint)

conviction_level is VARCHAR(10) — PLATINUM (8 chars) fits without schema change.
This migration adds a CHECK constraint to enforce the full 6-level set and make
the valid values explicit in the DB schema.

Revision ID: 0004_add_platinum_conviction
Revises: 0003_widen_exchange_varchar
Create Date: 2026-04-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004_add_platinum_conviction"
down_revision: Union[str, None] = "0003_widen_exchange_varchar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_VALID_LEVELS = "('DIAMOND','PLATINUM','GOLD','SILVER','BRONZE','UNRANKED')"
_CHECK_NAME = "ck_consensus_conviction_level"
_TABLE = "consensus_scores"
_SCHEMA = "consensus_app"


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE {_SCHEMA}.{_TABLE}
        ADD CONSTRAINT {_CHECK_NAME}
        CHECK (conviction_level IN {_VALID_LEVELS})
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE {_SCHEMA}.{_TABLE}
        DROP CONSTRAINT IF EXISTS {_CHECK_NAME}
        """
    )
