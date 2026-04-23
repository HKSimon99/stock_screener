"""Add watchlist_items table for authenticated user watchlists.

Revision ID: 0010_watchlist
Revises: 0009_admin_backfill_runs
Create Date: 2026-04-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_watchlist"
down_revision = "0009_admin_backfill_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column(
            "instrument_id",
            sa.Integer(),
            sa.ForeignKey("consensus_app.instruments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("market", sa.String(length=4), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="consensus_app",
    )
    op.create_index(
        "idx_watchlist_items_user_id_added_at",
        "watchlist_items",
        ["user_id", "added_at"],
        schema="consensus_app",
    )
    op.create_unique_constraint(
        "uq_watchlist_items_user_instrument",
        "watchlist_items",
        ["user_id", "instrument_id"],
        schema="consensus_app",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_watchlist_items_user_instrument",
        "watchlist_items",
        schema="consensus_app",
        type_="unique",
    )
    op.drop_index(
        "idx_watchlist_items_user_id_added_at",
        table_name="watchlist_items",
        schema="consensus_app",
    )
    op.drop_table("watchlist_items", schema="consensus_app")
