"""Add durable admin backfill runs.

Revision ID: 0009_admin_backfill_runs
Revises: 0008_hydration_jobs
Create Date: 2026-04-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0009_admin_backfill_runs"
down_revision = "0008_hydration_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_backfill_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("market", sa.String(length=4), nullable=False),
        sa.Column("requested_tickers", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("selected_tickers", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("limit_requested", sa.Integer(), nullable=True),
        sa.Column("chunk_size", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("price_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("score_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("requester_source", sa.String(length=30), nullable=False, server_default="api_key"),
        sa.Column("requester_user_id", sa.String(length=128), nullable=True),
        sa.Column("celery_task_id", sa.String(length=155), nullable=True),
        sa.Column("requested_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema="consensus_app",
    )
    op.create_index(
        "idx_admin_backfill_runs_status_queued_at",
        "admin_backfill_runs",
        ["status", "queued_at"],
        schema="consensus_app",
    )
    op.create_index(
        "idx_admin_backfill_runs_market_queued_at",
        "admin_backfill_runs",
        ["market", "queued_at"],
        schema="consensus_app",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_admin_backfill_runs_market_queued_at",
        table_name="admin_backfill_runs",
        schema="consensus_app",
    )
    op.drop_index(
        "idx_admin_backfill_runs_status_queued_at",
        table_name="admin_backfill_runs",
        schema="consensus_app",
    )
    op.drop_table("admin_backfill_runs", schema="consensus_app")
