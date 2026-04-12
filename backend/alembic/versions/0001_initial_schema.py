"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── instruments ──────────────────────────────────────────────────────────
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_kr", sa.String(200)),
        sa.Column("market", sa.String(4), nullable=False),
        sa.Column("exchange", sa.String(10), nullable=False),
        sa.Column("asset_type", sa.String(10), nullable=False),
        sa.Column("sector", sa.String(100)),
        sa.Column("industry_group", sa.String(100)),
        sa.Column("shares_outstanding", sa.Numeric(20, 0)),
        sa.Column("float_shares", sa.Numeric(20, 0)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("corp_code", sa.String(8)),
        sa.Column("is_chaebol_cross", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_leveraged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_inverse", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("expense_ratio", sa.Numeric(6, 4)),
        sa.Column("aum", sa.Numeric(20, 0)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("ticker", "market", name="uq_instrument_ticker_market"),
    )
    op.create_index("idx_instruments_market_type", "instruments", ["market", "asset_type"])
    op.create_index("idx_instruments_sector", "instruments", ["market", "sector"])

    # ── prices (TimescaleDB hypertable) ──────────────────────────────────────
    op.create_table(
        "prices",
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(14, 4)),
        sa.Column("high", sa.Numeric(14, 4)),
        sa.Column("low", sa.Numeric(14, 4)),
        sa.Column("close", sa.Numeric(14, 4)),
        sa.Column("volume", sa.BigInteger()),
        sa.Column("avg_volume_50d", sa.BigInteger()),
        sa.PrimaryKeyConstraint("instrument_id", "trade_date"),
    )
    # Convert to a TimescaleDB hypertable when the extension is available.
    # Local dev can still proceed on plain PostgreSQL until TimescaleDB is installed.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb') THEN
                BEGIN
                    CREATE EXTENSION IF NOT EXISTS timescaledb;
                    PERFORM create_hypertable('prices', 'trade_date', if_not_exists => TRUE);
                EXCEPTION
                    WHEN OTHERS THEN
                        RAISE NOTICE 'Skipping TimescaleDB hypertable setup: %', SQLERRM;
                END;
            END IF;
        END
        $$;
        """
    )
    op.create_index("idx_prices_instrument_date", "prices", ["instrument_id", "trade_date"])

    # ── fundamentals_quarterly ───────────────────────────────────────────────
    op.create_table(
        "fundamentals_quarterly",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=False),
        sa.Column("report_date", sa.Date()),
        sa.Column("revenue", sa.BigInteger()),
        sa.Column("net_income", sa.BigInteger()),
        sa.Column("eps", sa.Numeric(14, 4)),
        sa.Column("eps_diluted", sa.Numeric(14, 4)),
        sa.Column("eps_yoy_growth", sa.Numeric(10, 6)),
        sa.Column("revenue_yoy_growth", sa.Numeric(10, 6)),
        sa.Column("data_source", sa.String(20)),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("instrument_id", "fiscal_year", "fiscal_quarter",
                            name="uq_fundamental_q_instrument_period"),
    )
    op.create_index("idx_fq_instrument", "fundamentals_quarterly", ["instrument_id"])

    # ── fundamentals_annual ──────────────────────────────────────────────────
    op.create_table(
        "fundamentals_annual",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("report_date", sa.Date()),
        sa.Column("revenue", sa.BigInteger()),
        sa.Column("gross_profit", sa.BigInteger()),
        sa.Column("net_income", sa.BigInteger()),
        sa.Column("eps", sa.Numeric(14, 4)),
        sa.Column("eps_diluted", sa.Numeric(14, 4)),
        sa.Column("eps_yoy_growth", sa.Numeric(10, 6)),
        # Balance sheet
        sa.Column("total_assets", sa.BigInteger()),
        sa.Column("current_assets", sa.BigInteger()),
        sa.Column("current_liabilities", sa.BigInteger()),
        sa.Column("long_term_debt", sa.BigInteger()),
        sa.Column("shares_outstanding_annual", sa.BigInteger()),
        # Cash flow
        sa.Column("operating_cash_flow", sa.BigInteger()),
        # Pre-computed ratios
        sa.Column("roa", sa.Numeric(10, 6)),
        sa.Column("current_ratio", sa.Numeric(10, 6)),
        sa.Column("gross_margin", sa.Numeric(10, 6)),
        sa.Column("asset_turnover", sa.Numeric(10, 6)),
        sa.Column("leverage_ratio", sa.Numeric(10, 6)),
        sa.Column("data_source", sa.String(20)),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("instrument_id", "fiscal_year",
                            name="uq_fundamental_a_instrument_year"),
    )
    op.create_index("idx_fa_instrument", "fundamentals_annual", ["instrument_id"])

    # ── institutional_ownership ──────────────────────────────────────────────
    op.create_table(
        "institutional_ownership",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("num_institutional_owners", sa.Integer()),
        sa.Column("institutional_pct", sa.Numeric(8, 6)),
        sa.Column("top_fund_quality_score", sa.Numeric(6, 2)),
        sa.Column("qoq_owner_change", sa.Integer()),
        sa.Column("foreign_ownership_pct", sa.Numeric(8, 6)),
        sa.Column("foreign_net_buy_30d", sa.BigInteger()),
        sa.Column("institutional_net_buy_30d", sa.BigInteger()),
        sa.Column("individual_net_buy_30d", sa.BigInteger()),
        sa.Column("is_buyback_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("data_source", sa.String(20)),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("instrument_id", "report_date",
                            name="uq_institutional_instrument_date"),
    )

    # ── strategy_scores ──────────────────────────────────────────────────────
    op.create_table(
        "strategy_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("score_date", sa.Date(), nullable=False),
        # CANSLIM
        sa.Column("canslim_score", sa.Numeric(5, 2)),
        sa.Column("canslim_c", sa.Numeric(5, 2)),
        sa.Column("canslim_a", sa.Numeric(5, 2)),
        sa.Column("canslim_n", sa.Numeric(5, 2)),
        sa.Column("canslim_s", sa.Numeric(5, 2)),
        sa.Column("canslim_l", sa.Numeric(5, 2)),
        sa.Column("canslim_i", sa.Numeric(5, 2)),
        sa.Column("canslim_detail", JSONB),
        # Piotroski
        sa.Column("piotroski_score", sa.Numeric(5, 2)),
        sa.Column("piotroski_f_raw", sa.Integer()),
        sa.Column("piotroski_detail", JSONB),
        # Minervini
        sa.Column("minervini_score", sa.Numeric(5, 2)),
        sa.Column("minervini_criteria_count", sa.Integer()),
        sa.Column("minervini_detail", JSONB),
        # Weinstein
        sa.Column("weinstein_score", sa.Numeric(5, 2)),
        sa.Column("weinstein_stage", sa.String(20)),
        sa.Column("weinstein_detail", JSONB),
        # Dual Momentum
        sa.Column("dual_mom_score", sa.Numeric(5, 2)),
        sa.Column("dual_mom_abs", sa.Boolean()),
        sa.Column("dual_mom_rel", sa.Boolean()),
        sa.Column("dual_mom_detail", JSONB),
        # Technical
        sa.Column("technical_composite", sa.Numeric(5, 2)),
        sa.Column("patterns", JSONB),
        sa.Column("rs_rating", sa.Numeric(5, 2)),
        sa.Column("rs_line_new_high", sa.Boolean()),
        sa.Column("ad_rating", sa.String(2)),
        sa.Column("bb_squeeze", sa.Boolean()),
        sa.Column("technical_detail", JSONB),
        # Meta
        sa.Column("market_regime", sa.String(30)),
        sa.Column("data_freshness", JSONB),
        sa.Column("score_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("instrument_id", "score_date",
                            name="uq_strategy_score_instrument_date"),
    )
    op.create_index("idx_ss_date_canslim", "strategy_scores", ["score_date", "canslim_score"])
    op.create_index("idx_ss_date_piotroski", "strategy_scores", ["score_date", "piotroski_score"])

    # ── consensus_scores ─────────────────────────────────────────────────────
    op.create_table(
        "consensus_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("score_date", sa.Date(), nullable=False),
        sa.Column("canslim_score", sa.Numeric(5, 2)),
        sa.Column("piotroski_score", sa.Numeric(5, 2)),
        sa.Column("minervini_score", sa.Numeric(5, 2)),
        sa.Column("weinstein_score", sa.Numeric(5, 2)),
        sa.Column("dual_mom_score", sa.Numeric(5, 2)),
        sa.Column("technical_composite", sa.Numeric(5, 2)),
        sa.Column("strategy_pass_count", sa.Integer()),
        sa.Column("consensus_composite", sa.Numeric(5, 2)),
        sa.Column("final_score", sa.Numeric(5, 2)),
        sa.Column("conviction_level", sa.String(10), nullable=False, server_default="UNRANKED"),
        sa.Column("regime_state", sa.String(30)),
        sa.Column("regime_warning", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("score_breakdown", JSONB),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("instrument_id", "score_date",
                            name="uq_consensus_score_instrument_date"),
    )
    op.create_index("idx_cs_date_conviction", "consensus_scores",
                    ["score_date", "conviction_level", "final_score"])

    # ── market_regime ─────────────────────────────────────────────────────────
    op.create_table(
        "market_regime",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("market", sa.String(4), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("prior_state", sa.String(30)),
        sa.Column("trigger_reason", sa.Text()),
        sa.Column("index_ticker", sa.String(10)),
        sa.Column("index_close", sa.Numeric(14, 4)),
        sa.Column("index_50dma", sa.Numeric(14, 4)),
        sa.Column("index_200dma", sa.Numeric(14, 4)),
        sa.Column("drawdown_from_high", sa.Numeric(8, 6)),
        sa.Column("distribution_day_count", sa.Integer()),
        sa.Column("follow_through_day", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("market", "effective_date", name="uq_market_regime_market_date"),
    )

    # ── etf_constituents ──────────────────────────────────────────────────────
    op.create_table(
        "etf_constituents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("etf_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("constituent_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("weight", sa.Numeric(10, 8)),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.UniqueConstraint("etf_id", "constituent_id", "as_of_date", name="uq_etf_constituent"),
    )

    # ── etf_scores ────────────────────────────────────────────────────────────
    op.create_table(
        "etf_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("score_date", sa.Date(), nullable=False),
        sa.Column("weighted_consensus", sa.Numeric(5, 2)),
        sa.Column("pct_diamond_gold", sa.Numeric(5, 2)),
        sa.Column("fund_flow_score", sa.Numeric(5, 2)),
        sa.Column("rs_vs_sector", sa.Numeric(5, 2)),
        sa.Column("expense_score", sa.Numeric(5, 2)),
        sa.Column("aum_score", sa.Numeric(5, 2)),
        sa.Column("composite", sa.Numeric(5, 2)),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("instrument_id", "score_date", name="uq_etf_score_instrument_date"),
    )

    # ── alerts ────────────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=True),
        sa.Column("market", sa.String(4)),
        sa.Column("alert_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("title", sa.String(200)),
        sa.Column("detail", sa.Text()),
        sa.Column("threshold_value", sa.Numeric(14, 4)),
        sa.Column("actual_value", sa.Numeric(14, 4)),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_alerts_unread", "alerts", ["is_read", "severity", "created_at"])

    # ── scoring_snapshots ─────────────────────────────────────────────────────
    op.create_table(
        "scoring_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("market", sa.String(4), nullable=False),
        sa.Column("asset_type", sa.String(10), nullable=False),
        sa.Column("regime_state", sa.String(30)),
        sa.Column("rankings_json", JSONB, nullable=False),
        sa.Column("metadata", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("snapshot_date", "market", "asset_type",
                            name="uq_snapshot_date_market_type"),
    )

    # ── data_freshness ────────────────────────────────────────────────────────
    op.create_table(
        "data_freshness",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_name", sa.String(50), nullable=False),
        sa.Column("market", sa.String(4), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_failure_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("records_updated", sa.Integer()),
        sa.Column("next_expected", sa.DateTime(timezone=True)),
        sa.Column("staleness_threshold_hours", sa.Integer()),
        sa.UniqueConstraint("source_name", "market", name="uq_data_freshness_source_market"),
    )


def downgrade() -> None:
    op.drop_table("data_freshness")
    op.drop_table("scoring_snapshots")
    op.drop_table("alerts")
    op.drop_table("etf_scores")
    op.drop_table("etf_constituents")
    op.drop_table("market_regime")
    op.drop_table("consensus_scores")
    op.drop_table("strategy_scores")
    op.drop_table("institutional_ownership")
    op.drop_table("fundamentals_annual")
    op.drop_table("fundamentals_quarterly")
    op.drop_table("prices")
    op.drop_table("instruments")
