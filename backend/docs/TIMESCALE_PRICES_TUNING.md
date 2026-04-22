# Timescale Tuning for `consensus_app.prices`

This project uses TimescaleDB only for the `consensus_app.prices` table, and only when the extension is actually available in the target database.

## Current policy

Do not enable Timescale compression blindly.

Reasons:

- The app's hottest reads are still recent single-instrument chart windows and recent scoring lookups.
- Compression is most useful once `prices` is large enough that storage and old-chunk scans dominate.
- On April 22, 2026, the local benchmark source database is still small:
  - about `27,933` rows
  - about `4 MB`
  - about `57` instruments with price history

At this size, compression is more likely to add operational complexity than a meaningful latency win.

## Audit command

```powershell
Set-Location C:\Users\kyusu\vibecoding_projects\claude\backend
.\.venv\Scripts\python timescale_prices_tuning.py
```

This reports:

- whether `timescaledb` is enabled
- whether `consensus_app.prices` is a hypertable
- current chunk interval
- existing compression settings and jobs
- row count, instrument count, date range, and relation size
- whether the table is ready for compression

## Apply command

The script supports applying conservative tuning only when the readiness checks pass:

```powershell
Set-Location C:\Users\kyusu\vibecoding_projects\claude\backend
.\.venv\Scripts\python timescale_prices_tuning.py --apply
```

The script refuses to apply if:

- `timescaledb` is not enabled
- `prices` is not a hypertable
- the table is still too small
- `compress_after_days` is set too aggressively

## Conservative defaults

When `--apply` is allowed, it uses:

- chunk interval: `30 days`
- compression segment-by: `instrument_id`
- compression order-by: `trade_date DESC`
- automatic compression after: `540 days`

Why these defaults:

- `instrument_id` matches the app's most common filter shape
- `trade_date DESC` aligns with recent-window chart and scoring reads
- `540 days` keeps the active one-year chart window uncompressed

## When to actually enable compression

Do not turn compression on until `prices` is materially larger. The current script uses these safety gates:

- at least `1,000,000` rows
- at least `256 MB` total relation size

Those numbers are intentionally conservative. If the dataset grows and old-history queries start to dominate, re-run the audit and benchmark before changing them.

## Neon note

Neon now supports the `timescaledb` extension, but you should still treat compression as an environment-specific operational step rather than an unconditional migration.

Relevant docs:

- [Neon changelog: TimescaleDB on Postgres 18](https://neon.com/docs/changelog/2026-02-27)
- [Neon extensions overview](https://neon.com/docs/extensions/pg-extensions)
- [Timescale compression settings](https://docs.timescale.com/api/latest/compression/alter_table_compression/)
- [Timescale compression policies](https://docs.timescale.com/use-timescale/latest/compression/compression-policy/)

## Recommendation today

Keep `prices` as a normal Postgres table in local development and as a hypertable only in environments where Timescale is already enabled.

For this repo's current data volume, higher-value wins remain:

- search indexing
- coverage-summary reuse
- read-replica routing
- strategy/detail query shape cleanup

Timescale compression should stay gated until the table grows far beyond the current local size.
