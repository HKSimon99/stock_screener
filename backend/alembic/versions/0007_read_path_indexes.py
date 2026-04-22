"""Add read-path indexes for strategy rankings and instrument detail.

Revision ID: 0007_read_path_indexes
Revises: 0006_search_indexes_and_coverage_summary
Create Date: 2026-04-22
"""

from alembic import op


revision = "0007_read_path_indexes"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_strategy_scores_instrument_date_desc
        ON consensus_app.strategy_scores (instrument_id, score_date DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_consensus_scores_instrument_date_desc
        ON consensus_app.consensus_scores (instrument_id, score_date DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_instruments_market_upper_ticker_active
        ON consensus_app.instruments (market, upper(ticker))
        WHERE is_active IS TRUE
        """
    )

    for strategy_name in (
        "canslim",
        "piotroski",
        "minervini",
        "weinstein",
        "dual_mom",
        "technical",
    ):
        column_name = "technical_composite" if strategy_name == "technical" else f"{strategy_name}_score"
        op.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_strategy_scores_{strategy_name}_rank
            ON consensus_app.strategy_scores (score_date, {column_name} DESC, instrument_id)
            WHERE {column_name} IS NOT NULL
            """
        )


def downgrade() -> None:
    for strategy_name in (
        "canslim",
        "piotroski",
        "minervini",
        "weinstein",
        "dual_mom",
        "technical",
    ):
        op.execute(f"DROP INDEX IF EXISTS consensus_app.idx_strategy_scores_{strategy_name}_rank")

    op.execute("DROP INDEX IF EXISTS consensus_app.idx_instruments_market_upper_ticker_active")
    op.execute("DROP INDEX IF EXISTS consensus_app.idx_consensus_scores_instrument_date_desc")
    op.execute("DROP INDEX IF EXISTS consensus_app.idx_strategy_scores_instrument_date_desc")
