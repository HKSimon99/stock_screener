"""search indexes and coverage summary

Revision ID: 0006
Revises: e6b28b19d844
Create Date: 2026-04-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0006"
down_revision: Union[str, None] = "e6b28b19d844"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "instrument_coverage_summary",
        sa.Column(
            "instrument_id",
            sa.Integer(),
            sa.ForeignKey("consensus_app.instruments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("coverage_state", sa.String(length=30), nullable=False, server_default="searchable"),
        sa.Column("price_bar_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price_as_of", sa.Date(), nullable=True),
        sa.Column("quarterly_as_of", sa.Date(), nullable=True),
        sa.Column("annual_as_of", sa.Date(), nullable=True),
        sa.Column("ranked_as_of", sa.Date(), nullable=True),
        sa.Column("ranking_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ranking_reasons", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "rank_model_version",
            sa.String(length=50),
            nullable=False,
            server_default="consensus-v1-foundation",
        ),
        sa.Column("delay_minutes", sa.Integer(), nullable=True),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="consensus_app",
    )
    op.create_index(
        "idx_covsum_coverage_state",
        "instrument_coverage_summary",
        ["coverage_state"],
        schema="consensus_app",
    )

    op.execute(
        """
        DO $$
        BEGIN
            BEGIN
                CREATE EXTENSION IF NOT EXISTS pg_trgm;
            EXCEPTION
                WHEN insufficient_privilege THEN
                    RAISE NOTICE 'Skipping pg_trgm extension install due to insufficient privilege';
            END;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_instruments_ticker_trgm
                         ON consensus_app.instruments USING gin (ticker public.gin_trgm_ops)';
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_instruments_name_trgm
                         ON consensus_app.instruments USING gin (name public.gin_trgm_ops)';
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_instruments_name_kr_trgm
                         ON consensus_app.instruments USING gin (name_kr public.gin_trgm_ops)';
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_instruments_exchange_trgm
                         ON consensus_app.instruments USING gin (exchange public.gin_trgm_ops)';
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_instruments_ticker_upper
        ON consensus_app.instruments ((upper(ticker)))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS consensus_app.idx_instruments_ticker_upper")
    op.execute("DROP INDEX IF EXISTS consensus_app.idx_instruments_exchange_trgm")
    op.execute("DROP INDEX IF EXISTS consensus_app.idx_instruments_name_kr_trgm")
    op.execute("DROP INDEX IF EXISTS consensus_app.idx_instruments_name_trgm")
    op.execute("DROP INDEX IF EXISTS consensus_app.idx_instruments_ticker_trgm")
    op.drop_index(
        "idx_covsum_coverage_state",
        table_name="instrument_coverage_summary",
        schema="consensus_app",
    )
    op.drop_table("instrument_coverage_summary", schema="consensus_app")
