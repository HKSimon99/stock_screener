"""Repair a promoted database so Neon/runtime read paths are complete."""

from __future__ import annotations

import argparse
import os

from app.core.config import settings
from db_promotion_common import collect_db_summary, print_db_summary
from db_promotion_repair import ensure_post_restore_state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target-url",
        default=os.getenv("PROMOTION_TARGET_DATABASE_URL"),
        help="Target Postgres URL to repair.",
    )
    parser.add_argument(
        "--schema",
        default=os.getenv("PROMOTION_SCHEMA", settings.postgres_schema),
        help="Schema to repair. Defaults to consensus_app.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.target_url:
        parser.error("--target-url is required (or set PROMOTION_TARGET_DATABASE_URL)")

    ensure_post_restore_state(args.target_url, schema=args.schema)
    summary = collect_db_summary(args.target_url, schema=args.schema)
    print_db_summary(summary, label="repaired-target")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
