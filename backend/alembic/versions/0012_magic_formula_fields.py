"""Add Magic Formula fields to fundamentals_annual

Revision ID: 0012
Revises: 0011_repair_exchange_column
Create Date: 2026-05-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0012"
down_revision: Union[str, None] = "0011_repair_exchange_column"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # fundamentals_annual — Magic Formula source fields
    op.add_column("fundamentals_annual", sa.Column("ebit", sa.BigInteger(), nullable=True), schema="consensus_app")
    op.add_column("fundamentals_annual", sa.Column("total_debt", sa.BigInteger(), nullable=True), schema="consensus_app")
    op.add_column("fundamentals_annual", sa.Column("cash_and_equivalents", sa.BigInteger(), nullable=True), schema="consensus_app")
    op.add_column("fundamentals_annual", sa.Column("net_fixed_assets", sa.BigInteger(), nullable=True), schema="consensus_app")

    # strategy_scores — Magic Formula score columns
    op.add_column("strategy_scores", sa.Column("magic_formula_score", sa.Numeric(5, 2), nullable=True), schema="consensus_app")
    op.add_column("strategy_scores", sa.Column("magic_formula_roic", sa.Numeric(10, 6), nullable=True), schema="consensus_app")
    op.add_column("strategy_scores", sa.Column("magic_formula_ey", sa.Numeric(10, 6), nullable=True), schema="consensus_app")
    op.add_column("strategy_scores", sa.Column("magic_formula_detail", JSONB(), nullable=True), schema="consensus_app")

    # consensus_scores — Magic Formula aggregate score
    op.add_column("consensus_scores", sa.Column("magic_formula_score", sa.Numeric(5, 2), nullable=True), schema="consensus_app")


def downgrade() -> None:
    op.drop_column("consensus_scores", "magic_formula_score", schema="consensus_app")
    op.drop_column("strategy_scores", "magic_formula_detail", schema="consensus_app")
    op.drop_column("strategy_scores", "magic_formula_ey", schema="consensus_app")
    op.drop_column("strategy_scores", "magic_formula_roic", schema="consensus_app")
    op.drop_column("strategy_scores", "magic_formula_score", schema="consensus_app")
    op.drop_column("fundamentals_annual", "net_fixed_assets", schema="consensus_app")
    op.drop_column("fundamentals_annual", "cash_and_equivalents", schema="consensus_app")
    op.drop_column("fundamentals_annual", "total_debt", schema="consensus_app")
    op.drop_column("fundamentals_annual", "ebit", schema="consensus_app")
