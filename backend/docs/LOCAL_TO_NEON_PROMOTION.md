# Local-to-Neon Promotion Workflow

This workflow promotes the tuned local Postgres database into a fresh Neon branch and verifies parity before any application environment is switched.

## Why this workflow exists

- The local Postgres database is the source of truth for schema tuning and latency work.
- Neon should receive a validated copy of that tuned state, not an ad hoc or partially populated database.
- Promotion must prove parity for the tables and symbols the app depends on, especially `NVDA`, `005930`, `SPY`, and `069500`.

## Recommended branch strategy

Use a fresh Neon branch for every promotion. Neon branches are copy-on-write and isolated, so they are safe for promotion testing before cutover.

Recommended branch names:

- `promote-2026-04-22-latency-pass`
- `release-phase9-db`

## Preferred Neon path

Neon's Import Data Assistant is the safest official entrypoint when you want Neon to run compatibility checks and pre-populate `pg_dump` / `pg_restore` commands for you.

Official references:

- [Neon Import Data Assistant](https://neon.com/migration)
- [Neon Branching](https://neon.com/docs/introduction/branching)
- [Neon Branching tooling and automation](https://neon.com/flow/tooling-and-automation)

If you already have a fresh Neon branch and its direct connection string, the repo scripts below are enough on their own.

## Environment variables

These scripts read the following optional environment variables:

- `PROMOTION_SOURCE_DATABASE_URL`
- `PROMOTION_TARGET_DATABASE_URL`
- `PROMOTION_SCHEMA`
- `PROMOTION_DUMP_FILE`
- `PROMOTION_RESTORE_JOBS`

If `PROMOTION_SOURCE_DATABASE_URL` is omitted, the scripts default to the backend sync database URL from the local backend settings.

## Step 1: Verify the local source database

```powershell
Set-Location C:\Users\kyusu\vibecoding_projects\claude\backend
.\.venv\Scripts\python check_source_db.py
```

This confirms the source database is populated and includes the representative US and KR tickers plus benchmark instruments.

## Step 2: Create a fresh Neon branch

Create a new branch in Neon before restoring data into it.

Good options:

- Neon Console
- Neon CLI
- Neon API
- Neon Import Data Assistant

Important:

- Use the branch's **direct** connection string for restore work.
- Do not use the `-pooler` hostname for `pg_restore`.

## Step 3: Run the promotion

```powershell
Set-Location C:\Users\kyusu\vibecoding_projects\claude\backend
$env:PROMOTION_TARGET_DATABASE_URL = "postgresql://..."
.\.venv\Scripts\python promote_local_to_neon.py
```

What the script does:

1. Verifies the source looks like a populated local database.
2. Refuses to promote if `instrument_coverage_summary` is out of sync with the active instrument universe.
3. Refuses to write into a non-empty target branch unless you explicitly allow it.
4. Runs `pg_dump` against the local source database.
5. Runs `pg_restore` into the fresh Neon branch.
6. Validates parity between the source and target databases.

Useful flags:

- `--dump-file tmp\consensus_release.dump`
- `--keep-dump`
- `--allow-nonempty-target`
- `--skip-validate`
- `--jobs 4`

## Step 4: Re-run parity checks independently

```powershell
Set-Location C:\Users\kyusu\vibecoding_projects\claude\backend
$env:PROMOTION_TARGET_DATABASE_URL = "postgresql://..."
.\.venv\Scripts\python validate_db_promotion.py
```

The validator compares:

- core table counts
- active instruments by market
- latest `strategy_scores` and `consensus_scores` dates
- latest score dates by market
- representative tickers and their price coverage

## Step 5: Only then switch application envs

Do not point the app, workers, or benchmarks at the new Neon branch until both of these are true:

- `promote_local_to_neon.py` completed successfully
- `validate_db_promotion.py` reports `Promotion parity passed`

## Operational notes

- Keep local schema tuning and benchmark work on local Postgres first.
- Treat each Neon promotion branch as a deployable DB artifact.
- If parity fails, discard the Neon branch and create a new one for the next attempt.
- If you need repeatable preview environments later, this same workflow can be extended with Neon branch automation in CI.
