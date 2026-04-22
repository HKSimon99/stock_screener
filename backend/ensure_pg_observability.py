"""Enable and inspect PostgreSQL query observability for local or Neon targets."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

import psycopg2


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def merged_env(paths: Iterable[Path]) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in paths:
        values.update(load_env_file(path))
    return values


def select_env(target: str) -> dict[str, str]:
    root_env = REPO_ROOT / ".env"
    local_env = REPO_ROOT / ".env.local"
    if target == "local":
        return merged_env([root_env, local_env])
    if target == "neon":
        return merged_env([root_env])
    raise ValueError(f"Unsupported target: {target}")


def build_sync_dsn(env: dict[str, str]) -> str:
    host = env["POSTGRES_HOST"]
    port = env.get("POSTGRES_PORT", "5432")
    db = env["POSTGRES_DB"]
    user = env["POSTGRES_USER"]
    password = env["POSTGRES_PASSWORD"]
    ssl = env.get("POSTGRES_SSL", "false").lower() == "true"
    dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    if ssl:
        dsn += "?sslmode=require"
    return dsn


def build_local_superuser_dsn(env: dict[str, str]) -> str | None:
    host = env.get("POSTGRES_HOST", "")
    if host not in {"localhost", "127.0.0.1"}:
        return None
    port = env.get("POSTGRES_PORT", "5432")
    # Matches the working local superuser credential discovered on this machine.
    return f"postgresql://postgres:changeme@{host}:{port}/postgres"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["local", "neon"], default="local")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    env = select_env(args.target)
    dsn = build_sync_dsn(env)
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()

    print(f"Target: {args.target}")
    print(f"Host: {env['POSTGRES_HOST']}")

    installed = False
    try:
        cur.execute("create extension if not exists pg_stat_statements")
        installed = True
    except Exception as exc:
        print(f"create extension with app role failed: {type(exc).__name__}: {exc}")
        conn.rollback()
        superuser_dsn = build_local_superuser_dsn(env)
        if superuser_dsn:
            try:
                admin_conn = psycopg2.connect(superuser_dsn)
                admin_conn.autocommit = True
                admin_cur = admin_conn.cursor()
                admin_cur.execute(f"create extension if not exists pg_stat_statements with schema public")
                admin_conn.close()
                installed = True
                print("create extension with local postgres superuser: ok")
            except Exception as admin_exc:
                print(
                    "create extension with local postgres superuser failed: "
                    f"{type(admin_exc).__name__}: {admin_exc}"
                )
    cur.execute("select extname from pg_extension where extname = 'pg_stat_statements'")
    installed = bool(cur.fetchone()) or installed
    print(f"pg_stat_statements installed: {installed}")

    try:
        cur.execute("show shared_preload_libraries")
        print(f"shared_preload_libraries: {cur.fetchone()[0]}")
    except Exception as exc:
        print(f"shared_preload_libraries: unavailable ({type(exc).__name__}: {exc})")
        conn.rollback()

    if args.reset:
        try:
            cur.execute("select pg_stat_statements_reset()")
            print("pg_stat_statements_reset: ok")
        except Exception as exc:
            print(f"pg_stat_statements_reset: unavailable ({type(exc).__name__}: {exc})")
            conn.rollback()

    if not installed:
        print("Skipping pg_stat_statements query dump because the extension is unavailable.")
        conn.close()
        return 0

    try:
        cur.execute(
            """
            select
              calls,
              round(total_exec_time::numeric, 2) as total_ms,
              round(mean_exec_time::numeric, 2) as mean_ms,
              rows,
              left(query, 220) as query
            from pg_stat_statements
            where dbid = (select oid from pg_database where datname = current_database())
            order by total_exec_time desc
            limit %s
            """,
            (args.top,),
        )
        rows = cur.fetchall()
        if not rows:
            print("No pg_stat_statements rows yet.")
        else:
            print("\nTop statements by total_exec_time:")
            for calls, total_ms, mean_ms, row_count, query in rows:
                compact = " ".join(str(query).split())
                print(
                    f"calls={calls} total_ms={total_ms} mean_ms={mean_ms} "
                    f"rows={row_count} sql={compact}"
                )
    except Exception as exc:
        print(
            "pg_stat_statements query dump unavailable "
            f"({type(exc).__name__}: {exc})"
        )
        conn.rollback()
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
