from __future__ import annotations

from typing import Final

import psycopg2
from psycopg2 import sql

from db_promotion_common import normalize_postgres_url


RANK_MODEL_VERSION: Final[str] = "consensus-v1-foundation"


def _connect(url: str):
    conn = psycopg2.connect(normalize_postgres_url(url))
    conn.autocommit = True
    return conn


def reset_target_schema(url: str, *, schema: str) -> None:
    with _connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))


def ensure_post_restore_state(url: str, *, schema: str) -> None:
    with _connect(url) as conn:
        with conn.cursor() as cur:
            _ensure_extensions(cur)
            _ensure_coverage_summary_table(cur, schema=schema)
            _ensure_read_indexes(cur, schema=schema)
            _refresh_coverage_summary(cur, schema=schema)


def _ensure_extensions(cur) -> None:
    cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def _ensure_coverage_summary_table(cur, *, schema: str) -> None:
    cur.execute(
        sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {}.instrument_coverage_summary (
                instrument_id INTEGER PRIMARY KEY REFERENCES {}.instruments(id) ON DELETE CASCADE,
                coverage_state VARCHAR(30) NOT NULL DEFAULT 'searchable',
                price_bar_count INTEGER NOT NULL DEFAULT 0,
                price_as_of DATE NULL,
                quarterly_as_of DATE NULL,
                annual_as_of DATE NULL,
                ranked_as_of DATE NULL,
                ranking_eligible BOOLEAN NOT NULL DEFAULT FALSE,
                ranking_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
                delay_minutes INTEGER NULL,
                rank_model_version VARCHAR(50) NOT NULL DEFAULT %s,
                refreshed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        ).format(sql.Identifier(schema), sql.Identifier(schema)),
        (RANK_MODEL_VERSION,),
    )
    cur.execute(
        sql.SQL(
            "CREATE INDEX IF NOT EXISTS idx_covsum_coverage_state ON {}.instrument_coverage_summary (coverage_state)"
        ).format(sql.Identifier(schema))
    )


def _ensure_read_indexes(cur, *, schema: str) -> None:
    statements = [
        """
        CREATE INDEX IF NOT EXISTS idx_instruments_ticker_upper
        ON {schema}.instruments ((upper(ticker)))
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_instruments_market_upper_ticker_active
        ON {schema}.instruments (market, upper(ticker))
        WHERE is_active IS TRUE
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_strategy_scores_instrument_date_desc
        ON {schema}.strategy_scores (instrument_id, score_date DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_consensus_scores_instrument_date_desc
        ON {schema}.consensus_scores (instrument_id, score_date DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_strategy_scores_canslim_rank
        ON {schema}.strategy_scores (score_date, canslim_score DESC, instrument_id)
        WHERE canslim_score IS NOT NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_strategy_scores_piotroski_rank
        ON {schema}.strategy_scores (score_date, piotroski_score DESC, instrument_id)
        WHERE piotroski_score IS NOT NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_strategy_scores_minervini_rank
        ON {schema}.strategy_scores (score_date, minervini_score DESC, instrument_id)
        WHERE minervini_score IS NOT NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_strategy_scores_weinstein_rank
        ON {schema}.strategy_scores (score_date, weinstein_score DESC, instrument_id)
        WHERE weinstein_score IS NOT NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_strategy_scores_dual_mom_rank
        ON {schema}.strategy_scores (score_date, dual_mom_score DESC, instrument_id)
        WHERE dual_mom_score IS NOT NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_strategy_scores_technical_rank
        ON {schema}.strategy_scores (score_date, technical_composite DESC, instrument_id)
        WHERE technical_composite IS NOT NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_instruments_ticker_trgm
        ON {schema}.instruments USING gin (ticker public.gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_instruments_name_trgm
        ON {schema}.instruments USING gin (name public.gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_instruments_name_kr_trgm
        ON {schema}.instruments USING gin (name_kr public.gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_instruments_exchange_trgm
        ON {schema}.instruments USING gin (exchange public.gin_trgm_ops)
        """,
    ]

    for statement in statements:
        cur.execute(sql.SQL(statement.format(schema=schema)))


def _refresh_coverage_summary(cur, *, schema: str) -> None:
    cur.execute(
        sql.SQL(
            """
            DELETE FROM {}.instrument_coverage_summary
            WHERE instrument_id NOT IN (
                SELECT id FROM {}.instruments WHERE is_active IS TRUE
            )
            """
        ).format(sql.Identifier(schema), sql.Identifier(schema))
    )

    cur.execute(
        sql.SQL(
            """
            WITH price AS (
                SELECT instrument_id, COUNT(*)::INT AS price_bar_count, MAX(trade_date) AS price_as_of
                FROM {}.prices
                GROUP BY instrument_id
            ),
            annual AS (
                SELECT instrument_id, MAX(report_date) AS annual_as_of
                FROM {}.fundamentals_annual
                GROUP BY instrument_id
            ),
            quarterly AS (
                SELECT instrument_id, MAX(report_date) AS quarterly_as_of
                FROM {}.fundamentals_quarterly
                GROUP BY instrument_id
            ),
            ranked AS (
                SELECT instrument_id, MAX(score_date) AS ranked_as_of
                FROM {}.consensus_scores
                GROUP BY instrument_id
            ),
            assembled AS (
                SELECT
                    i.id AS instrument_id,
                    CASE
                        WHEN r.ranked_as_of IS NOT NULL THEN 'ranked'
                        WHEN a.annual_as_of IS NOT NULL OR q.quarterly_as_of IS NOT NULL THEN 'fundamentals_ready'
                        WHEN p.price_as_of IS NOT NULL THEN 'price_ready'
                        ELSE 'searchable'
                    END AS coverage_state,
                    COALESCE(p.price_bar_count, 0) AS price_bar_count,
                    p.price_as_of,
                    q.quarterly_as_of,
                    a.annual_as_of,
                    r.ranked_as_of,
                    ARRAY_REMOVE(
                        ARRAY[
                            CASE
                                WHEN COALESCE(i.is_active, FALSE) IS NOT TRUE
                                    OR COALESCE(i.listing_status, 'LISTED') <> 'LISTED'
                                THEN 'inactive_listing'
                            END,
                            CASE
                                WHEN COALESCE(i.is_test_issue, FALSE) THEN 'test_issue'
                            END,
                            CASE
                                WHEN i.asset_type NOT IN ('stock', 'etf') THEN 'unsupported_asset_type'
                            END,
                            CASE
                                WHEN p.price_as_of IS NULL THEN 'no_price_history'
                                WHEN COALESCE(p.price_bar_count, 0) < 126 THEN 'insufficient_price_history'
                            END,
                            CASE
                                WHEN i.asset_type = 'stock'
                                    AND a.annual_as_of IS NULL
                                    AND q.quarterly_as_of IS NULL
                                THEN 'no_fundamentals'
                            END,
                            CASE
                                WHEN r.ranked_as_of IS NULL THEN 'score_not_generated'
                            END
                        ],
                        NULL
                    ) AS ranking_reasons,
                    CASE
                        WHEN i.market = 'US' THEN 15
                        WHEN i.market = 'KR' THEN 0
                        ELSE NULL
                    END AS delay_minutes
                FROM {}.instruments i
                LEFT JOIN price p ON p.instrument_id = i.id
                LEFT JOIN annual a ON a.instrument_id = i.id
                LEFT JOIN quarterly q ON q.instrument_id = i.id
                LEFT JOIN ranked r ON r.instrument_id = i.id
                WHERE i.is_active IS TRUE
            )
            INSERT INTO {}.instrument_coverage_summary (
                instrument_id,
                coverage_state,
                price_bar_count,
                price_as_of,
                quarterly_as_of,
                annual_as_of,
                ranked_as_of,
                ranking_eligible,
                ranking_reasons,
                delay_minutes,
                rank_model_version,
                refreshed_at
            )
            SELECT
                instrument_id,
                coverage_state,
                price_bar_count,
                price_as_of,
                quarterly_as_of,
                annual_as_of,
                ranked_as_of,
                COALESCE(CARDINALITY(ranking_reasons), 0) = 0 AS ranking_eligible,
                COALESCE(to_jsonb(ranking_reasons), '[]'::jsonb) AS ranking_reasons,
                delay_minutes,
                %s,
                NOW()
            FROM assembled
            ON CONFLICT (instrument_id) DO UPDATE SET
                coverage_state = EXCLUDED.coverage_state,
                price_bar_count = EXCLUDED.price_bar_count,
                price_as_of = EXCLUDED.price_as_of,
                quarterly_as_of = EXCLUDED.quarterly_as_of,
                annual_as_of = EXCLUDED.annual_as_of,
                ranked_as_of = EXCLUDED.ranked_as_of,
                ranking_eligible = EXCLUDED.ranking_eligible,
                ranking_reasons = EXCLUDED.ranking_reasons,
                delay_minutes = EXCLUDED.delay_minutes,
                rank_model_version = EXCLUDED.rank_model_version,
                refreshed_at = EXCLUDED.refreshed_at
            """
        ).format(
            sql.Identifier(schema),
            sql.Identifier(schema),
            sql.Identifier(schema),
            sql.Identifier(schema),
            sql.Identifier(schema),
            sql.Identifier(schema),
        ),
        (RANK_MODEL_VERSION,),
    )
