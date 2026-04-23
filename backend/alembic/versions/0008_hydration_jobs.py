"""Add durable hydration jobs.

Revision ID: 0008_hydration_jobs
Revises: 0007_read_path_indexes
Create Date: 2026-04-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0008_hydration_jobs"
down_revision = "0007_read_path_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hydration_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("market", sa.String(length=4), nullable=False),
        sa.Column(
            "instrument_id",
            sa.Integer(),
            sa.ForeignKey("consensus_app.instruments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("requester_source", sa.String(length=30), nullable=False, server_default="user"),
        sa.Column("requester_user_id", sa.String(length=128), nullable=True),
        sa.Column("celery_task_id", sa.String(length=155), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("source_metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema="consensus_app",
    )
    op.create_index(
        "idx_hydration_jobs_market_ticker",
        "hydration_jobs",
        ["market", "ticker"],
        schema="consensus_app",
    )
    op.create_index(
        "idx_hydration_jobs_status_queued_at",
        "hydration_jobs",
        ["status", "queued_at"],
        schema="consensus_app",
    )
    op.create_index(
        "idx_hydration_jobs_instrument_id",
        "hydration_jobs",
        ["instrument_id"],
        schema="consensus_app",
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_hydration_jobs_requester_queued_at
        ON consensus_app.hydration_jobs (requester_user_id, queued_at)
        WHERE requester_user_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hydration_jobs_active_symbol
        ON consensus_app.hydration_jobs (market, ticker)
        WHERE status IN ('queued', 'running')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS consensus_app.uq_hydration_jobs_active_symbol")
    op.execute("DROP INDEX IF EXISTS consensus_app.idx_hydration_jobs_requester_queued_at")
    op.drop_index(
        "idx_hydration_jobs_instrument_id",
        table_name="hydration_jobs",
        schema="consensus_app",
    )
    op.drop_index(
        "idx_hydration_jobs_status_queued_at",
        table_name="hydration_jobs",
        schema="consensus_app",
    )
    op.drop_index(
        "idx_hydration_jobs_market_ticker",
        table_name="hydration_jobs",
        schema="consensus_app",
    )
    op.drop_table("hydration_jobs", schema="consensus_app")
