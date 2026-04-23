"""Promote a tuned local Postgres database into a fresh Neon branch."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.core.config import settings
from db_promotion_common import (
    collect_db_summary,
    compare_db_summaries,
    host_label,
    is_pooled_neon_url,
    normalize_postgres_url,
    parsed_url,
    print_db_summary,
    promotion_readiness_issues,
)
from db_promotion_repair import ensure_post_restore_state, reset_target_schema


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
        help="Schema to promote. Defaults to consensus_app.",
    )
    parser.add_argument(
        "--dump-file",
        default=os.getenv("PROMOTION_DUMP_FILE") or str(Path("tmp") / "consensus_promotion.dump"),
        help="Path for the intermediate pg_dump file.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=int(os.getenv("PROMOTION_RESTORE_JOBS", "4")),
        help="Parallel jobs for pg_restore. Defaults to 4.",
    )
    parser.add_argument(
        "--allow-nonempty-target",
        action="store_true",
        help="Allow restore into a non-empty target branch. By default the script refuses.",
    )
    parser.add_argument(
        "--allow-remote-target-reset",
        action="store_true",
        help="Allow destructive schema reset on a non-local target. Requires --confirm-target-reset.",
    )
    parser.add_argument(
        "--confirm-target-reset",
        default="",
        help="Exact confirmation text required for non-local target resets.",
    )
    parser.add_argument(
        "--keep-dump",
        action="store_true",
        help="Keep the dump file after a successful promotion.",
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="Skip post-restore parity validation.",
    )
    return parser


def require_binary(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise SystemExit(f"{name} was not found on PATH. Install PostgreSQL client tools first.")
    return resolved


def run_command(args: list[str]) -> None:
    print(f"$ {' '.join(args)}")
    completed = subprocess.run(args, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def validate_endpoints(source_url: str, target_url: str) -> None:
    if host_label(source_url) != "local":
        raise SystemExit(
            "Source URL is not local. Action 9 expects a tuned local Postgres as the source of truth."
        )
    if is_pooled_neon_url(target_url):
        raise SystemExit(
            "Target URL points at a Neon pooler host. Use the direct Neon branch connection string for pg_restore."
        )


def reset_confirmation_text(target_url: str, schema: str) -> str:
    host = parsed_url(target_url).host or "<unknown-host>"
    return f"RESET {schema} ON {host}"


def validate_target_reset_confirmation(
    target_url: str,
    *,
    schema: str,
    allow_remote_target_reset: bool,
    confirm_target_reset: str,
) -> None:
    if os.getenv("APP_ENV", "").strip().lower() == "production":
        raise SystemExit(
            "Refusing destructive schema reset because APP_ENV=production. "
            "Run promotion only from a non-production operator environment."
        )

    if host_label(target_url) == "local":
        return

    required_confirmation = reset_confirmation_text(target_url, schema)
    if not allow_remote_target_reset:
        raise SystemExit(
            "Refusing destructive schema reset on a non-local target. "
            "Re-run with --allow-remote-target-reset only if this is an intentional fresh-branch restore.\n"
            f"Required confirmation text: {required_confirmation}"
        )

    if confirm_target_reset != required_confirmation:
        raise SystemExit(
            "Refusing destructive schema reset: confirmation text did not match.\n"
            f"Required confirmation text: {required_confirmation}"
        )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.target_url:
        parser.error("--target-url is required (or set PROMOTION_TARGET_DATABASE_URL)")

    validate_endpoints(args.source_url, args.target_url)
    validate_target_reset_confirmation(
        args.target_url,
        schema=args.schema,
        allow_remote_target_reset=args.allow_remote_target_reset,
        confirm_target_reset=args.confirm_target_reset,
    )

    pg_dump = require_binary("pg_dump")
    pg_restore = require_binary("pg_restore")

    source_summary = collect_db_summary(args.source_url, schema=args.schema)
    print_db_summary(source_summary, label="source")
    source_issues = promotion_readiness_issues(source_summary)
    if source_issues:
        raise SystemExit(
            "Source database is not promotion-ready:\n"
            + "\n".join(f"  - {issue}" for issue in source_issues)
        )

    target_summary_before = collect_db_summary(args.target_url, schema=args.schema)
    print_db_summary(target_summary_before, label="target-before")
    nonempty_tables = {
        table_name: count
        for table_name, count in target_summary_before.counts.items()
        if count not in (None, 0)
    }
    if nonempty_tables and not args.allow_nonempty_target:
        raise SystemExit(
            "Target branch is not empty. Create a fresh Neon branch or re-run with --allow-nonempty-target.\n"
            f"Non-empty tables: {nonempty_tables}"
        )

    dump_path = Path(args.dump_file).resolve()
    dump_path.parent.mkdir(parents=True, exist_ok=True)

    normalized_source_url = normalize_postgres_url(args.source_url)
    normalized_target_url = normalize_postgres_url(args.target_url)

    run_command(
        [
            pg_dump,
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            f"--schema={args.schema}",
            f"--file={dump_path}",
            normalized_source_url,
        ]
    )

    reset_target_schema(normalized_target_url, schema=args.schema)

    restore_cmd = [
        pg_restore,
        "--no-owner",
        "--no-privileges",
        f"--jobs={args.jobs}",
        f"--schema={args.schema}",
        f"--dbname={normalized_target_url}",
        str(dump_path),
    ]
    run_command(restore_cmd)
    ensure_post_restore_state(normalized_target_url, schema=args.schema)

    if args.skip_validate:
        print("Skipped post-restore parity validation.")
    else:
        target_summary_after = collect_db_summary(args.target_url, schema=args.schema)
        print_db_summary(target_summary_after, label="target-after")
        mismatches = compare_db_summaries(source_summary, target_summary_after)
        if mismatches:
            print()
            print("Promotion parity failed:")
            for mismatch in mismatches:
                print(f"  - {mismatch}")
            raise SystemExit(1)
        print()
        print("Promotion parity passed.")

    if not args.keep_dump and dump_path.exists():
        dump_path.unlink()
        print(f"Removed dump file: {dump_path}")
    elif dump_path.exists():
        print(f"Kept dump file: {dump_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
