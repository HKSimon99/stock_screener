"""Compare a source Postgres database against a promoted target database."""

from __future__ import annotations

import argparse
import json
import os

from app.core.config import settings
from db_promotion_common import (
    collect_db_summary,
    compare_db_summaries,
    print_db_summary,
    promotion_readiness_issues,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-url",
        default=os.getenv("PROMOTION_SOURCE_DATABASE_URL") or settings.sync_database_url,
        help="Source Postgres URL. Defaults to the local backend sync database URL.",
    )
    parser.add_argument(
        "--target-url",
        default=os.getenv("PROMOTION_TARGET_DATABASE_URL"),
        help="Target Postgres URL, typically the fresh Neon branch direct connection string.",
    )
    parser.add_argument(
        "--schema",
        default=os.getenv("PROMOTION_SCHEMA", settings.postgres_schema),
        help="Schema to compare. Defaults to consensus_app.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.target_url:
        parser.error("--target-url is required (or set PROMOTION_TARGET_DATABASE_URL)")

    source = collect_db_summary(args.source_url, schema=args.schema)
    target = collect_db_summary(args.target_url, schema=args.schema)
    mismatches = compare_db_summaries(source, target)
    source_issues = promotion_readiness_issues(source)
    target_issues = promotion_readiness_issues(target)

    if args.json:
        print(
            json.dumps(
                {
                    "source": source.to_dict(),
                    "target": target.to_dict(),
                    "source_issues": source_issues,
                    "target_issues": target_issues,
                    "mismatches": mismatches,
                    "matches": not mismatches and not source_issues and not target_issues,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print_db_summary(source, label="source")
        print_db_summary(target, label="target")
        print()
        if source_issues:
            print("Source readiness issues:")
            for issue in source_issues:
                print(f"  - {issue}")
            print()
        if target_issues:
            print("Target readiness issues:")
            for issue in target_issues:
                print(f"  - {issue}")
            print()
        if mismatches:
            print("Promotion parity failed:")
            for mismatch in mismatches:
                print(f"  - {mismatch}")
        elif source_issues or target_issues:
            print("Promotion parity matched, but one side is not promotion-ready.")
        else:
            print("Promotion parity passed.")

    return 1 if mismatches or source_issues or target_issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
