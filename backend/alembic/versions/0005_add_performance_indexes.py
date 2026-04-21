"""Add performance indexes for rankings and scoring queries

Revision ID: 0005_add_performance_indexes
Revises: 0004_add_platinum_conviction
Create Date: 2026-04-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005_add_performance_indexes"
down_revision: Union[str, None] = "0004_add_platinum_conviction"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "consensus_app"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_cs_score_date
        ON {_SCHEMA}.consensus_scores (score_date DESC, instrument_id)
        """
    )
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_ss_score_date
        ON {_SCHEMA}.strategy_scores (score_date DESC, instrument_id)
        """
    )
    # Only create if TimescaleDB hasn't already created a covering index.
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_prices_range
        ON {_SCHEMA}.prices (instrument_id, trade_date DESC)
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_SCHEMA}.idx_cs_score_date")
    op.execute(f"DROP INDEX IF EXISTS {_SCHEMA}.idx_ss_score_date")
    op.execute(f"DROP INDEX IF EXISTS {_SCHEMA}.idx_prices_range")
