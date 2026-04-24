"""Repair instruments.exchange VARCHAR(10) → VARCHAR(50) for fresh-migration resilience.

Migration 0003_widen_exchange_varchar already contained this ALTER but
it failed to persist on the production Neon instance (observed: alembic_version
at head=0010 yet column still VARCHAR(10)).  This repair migration runs the
same ALTER idempotently so that the correct column size is guaranteed after
any fresh alembic upgrade head run.

Revision ID: 0011_repair_exchange_column
Revises: 0010_watchlist
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa


revision = "0011_repair_exchange_column"
down_revision = "0010_watchlist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: if the column is already VARCHAR(50) (or wider) this is a
    # no-op.  If it is still VARCHAR(10) this brings it to the correct size.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'consensus_app'
                  AND table_name   = 'instruments'
                  AND column_name  = 'exchange'
                  AND character_maximum_length < 50
            ) THEN
                ALTER TABLE consensus_app.instruments
                    ALTER COLUMN exchange TYPE VARCHAR(50);
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # VARCHAR(10) was the original size from 0001; do not shrink back in a
    # repair migration — this is effectively a no-op downgrade.
    pass
