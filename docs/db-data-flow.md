# Database & Data Flow Status
_Last updated: 2026-05-03_

---

## Current DB Size (Neon, post-cleanup)

| Table | Size | Notes |
|---|---|---|
| `prices` | 224 MB | Was 427 MB — pruned 1.2M rows older than 300 trading days on 2026-05-03 |
| `strategy_scores` | 24 MB | Per-strategy scores per instrument per day |
| `instruments` | 16 MB | Master instrument list (6,565 instruments) |
| `consensus_scores` | 2.7 MB | Final score + conviction per instrument per day |
| `fundamentals_quarterly` | 2.2 MB | Last 8 quarters per instrument |
| `instrument_coverage_summary` | 2.0 MB | Freshness/coverage state per instrument |
| `fundamentals_annual` | 896 kB | Last 6 years per instrument |
| `scoring_snapshots` | 472 kB | Legacy JSON blobs — no longer used by API |
| `hydration_jobs` | 112 kB | One-off enrichment jobs |
| `alerts` | 80 kB | Push alert history |
| `data_freshness` | 48 kB | Source freshness records |
| `users` | 48 kB | User TOS acceptance records |
| `user_push_tokens` | 32 kB | Mobile push tokens |
| `admin_backfill_runs` | 32 kB | Internal backfill tooling |
| **Total** | **~290 MB** | Neon cap: 512 MB (free) → upgraded |

---

## Data Sources

| Source | Data | Market |
|---|---|---|
| **yfinance** | Daily OHLCV prices, 50d avg volume | US |
| **SEC EDGAR** | Quarterly/annual fundamentals (EPS, revenue, EBIT, FCF, balance sheet) | US |
| **KIS Developers** | Daily OHLCV prices | KR |
| **OpenDART** | Quarterly/annual fundamentals (Korean GAAP) | KR |
| **yfinance** (institutional) | Institutional ownership % changes | US |

All sources are **free**. Polygon was evaluated and rejected (cost).

---

## Raw Storage Schema

### `instruments` — master list, retained forever
```
id, ticker, name, name_kr (KR only), market (US|KR), exchange,
asset_type (stock|etf), listing_status, sector, industry_group,
shares_outstanding, float_shares, is_active, is_test_issue,
corp_code (KR OpenDART), is_chaebol_cross,
is_leveraged, is_inverse, expense_ratio, aum (ETF)
```

### `prices` — rolling 300 trading days
```
instrument_id, trade_date, open, high, low, close, volume, avg_volume_50d
```
**Nightly purge job (UTC 06:45)** deletes rows older than 300 trading days.
300 days covers MA200 + 52-week high detection + buffer.

### `fundamentals_quarterly` — last 8 quarters per instrument
```
instrument_id, fiscal_year, fiscal_quarter, report_date,
revenue, net_income, eps, eps_diluted,
eps_yoy_growth, revenue_yoy_growth,
data_source (EDGAR|DART)
```

### `fundamentals_annual` — last 6 years per instrument
```
instrument_id, fiscal_year, report_date,
revenue, gross_profit, net_income, eps, eps_diluted, eps_yoy_growth,
total_assets, current_assets, current_liabilities, long_term_debt,
shares_outstanding_annual,
operating_cash_flow, ebit, total_debt, cash_and_equivalents, net_fixed_assets,
roa, current_ratio, gross_margin, asset_turnover, leverage_ratio,
data_source (EDGAR|DART)
```

### `strategy_scores` — per instrument per score_date
```
instrument_id, score_date,
canslim_score, canslim_c/a/n/s/l/i (pass flags), canslim_detail (JSON),
piotroski_score, piotroski_f_raw (0-9), piotroski_detail (JSON),
minervini_score [LEGACY — weight=0], minervini_criteria_count, minervini_detail,
weinstein_score [GATE ONLY — not weighted], weinstein_stage, weinstein_detail,
magic_formula_score, magic_formula_rank, magic_formula_detail,
technical_composite, rs_rating, ad_rating, rs_line_new_high,
dual_momentum_score [REMOVED — always null]
```

### `consensus_scores` — final output per instrument per score_date
```
instrument_id, score_date,
final_score (0-100), conviction_level (DIAMOND|PLATINUM|GOLD|SILVER|BRONZE|UNRANKED),
consensus_composite, technical_composite,
strategy_pass_count, regime_at_scoring,
rank (within market), market
```

### `market_regime` — regime per market per date
```
market (US|KR), regime_date,
regime (CONFIRMED_UPTREND | UPTREND_UNDER_PRESSURE | MARKET_IN_CORRECTION)
```

---

## Nightly Beat Schedule (UTC)

```
06:45  purge_old_prices          DELETE prices older than 300 trading days
07:00  nightly-kr-prices         KIS → prices (KR, ~970 instruments)
07:30  nightly-kr-fundamentals   OpenDART → fundamentals_quarterly + fundamentals_annual (KR)
08:00  nightly-kr-magic-formula  Compute EBIT/EV ranks for KR → strategy_scores.magic_formula_*
09:30  nightly-kr-scoring        Full pipeline → strategy_scores + consensus_scores (KR)

22:00  nightly-us-prices         yfinance → prices (US, ~6,000+ instruments)
22:30  nightly-us-fundamentals   SEC EDGAR → fundamentals_quarterly + fundamentals_annual (US)
23:00  nightly-us-magic-formula  Compute EBIT/EV ranks for US
00:30  nightly-us-scoring        Full pipeline → strategy_scores + consensus_scores (US)

01:15  data-integrity-monitor    Freshness checks, flag stale instruments
01:30  conviction-upgrade-push   Push alerts for instruments that crossed a conviction level
```

---

## Scoring Pipeline Detail

Runs at **09:30 UTC (KR)** and **00:30 UTC (US)** in 100-instrument chunks.

### Context loaded per chunk
```
prices            → last 350 rows (~300 trading days)
fundamentals_q    → last 8 quarters
fundamentals_a    → last 6 years
institutional     → latest snapshot
market_regime     → current regime for the market
```

### Per-instrument scoring
| Engine | Input | Output | Weight |
|---|---|---|---|
| CANSLIM | prices + quarterly EPS + institutional | 0–100 score + C/A/N/S/L/I pass flags | 40% |
| Piotroski | annual fundamentals | 0–100 (derived from F-score 0–9) | 30% |
| Magic Formula | annual EBIT + market cap + debt | 0–100 (combined ROIC+EY rank) | 30% |
| Minervini | prices + MA criteria | stored, **weight = 0** (legacy) | — |
| Weinstein | prices + MA + volume | Stage 1/2/3/4 — **gate only, not scored** | — |
| Technical composite | RS rating, AD rating, patterns | 0–100 | 20% of final (additive) |

### Consensus formula
```
strategy_composite = canslim×0.40 + piotroski×0.30 + magic_formula×0.30
  (weights renormalized over strategies that actually have data)

final_score = strategy_composite×0.80 + technical_composite×0.20
  (technical_composite only included if both are present)
```

### Conviction thresholds
```
DIAMOND   ≥ 88  AND strategy_pass_count ≥ 3
PLATINUM  ≥ 78  AND strategy_pass_count ≥ 2
GOLD      ≥ 65  AND strategy_pass_count ≥ 2
SILVER    ≥ 50  AND strategy_pass_count ≥ 1
BRONZE    ≥ 35
UNRANKED  < 35
```

### Regime cap
```
CONFIRMED_UPTREND       → no cap (DIAMOND allowed)
UPTREND_UNDER_PRESSURE  → capped at PLATINUM
MARKET_IN_CORRECTION    → capped at SILVER
```

### Weinstein gate
```
Not in Stage 2 (2_early | 2_mid | 2_late) → capped at SILVER
```

---

## API Layer

| Endpoint | Returns | Source |
|---|---|---|
| `GET /rankings` | Paginated list: rank, ticker, name, market, conviction_level, final_score, sub-scores, sector, coverage_state | `consensus_scores` JOIN `instruments` |
| `GET /strategies/canslim` | CANSLIM rankings + C/A/N/S/L/I flags | `strategy_scores` |
| `GET /strategies/piotroski` | Piotroski F-score rankings | `strategy_scores` |
| `GET /strategies/magic_formula` | Magic Formula rank | `strategy_scores` |
| `GET /instruments/{ticker}` | Full detail: all scores + prices + fundamentals + freshness | Multiple |
| `GET /search` | Typeahead: ticker, name, market | `instruments` |
| `GET /market-regime` | Current regime per market | `market_regime` |

Cache-Control: `public, max-age=300, stale-while-revalidate=60` on ranking endpoints.

---

## Dead / Orphaned Code and Data

These exist in the codebase or DB but are not active:

| Item | Location | Status |
|---|---|---|
| `minervini_score` | `strategy_scores` column | Stored, weight=0, legacy — never cleaned up |
| `dual_momentum_score` | `strategy_scores` column | Always NULL — engine removed |
| `scoring_snapshots` table | DB, 472 kB | Legacy JSON blobs — API no longer reads them |
| `snapshot_tasks.py` | `backend/app/tasks/` | Not in beat schedule |
| `storage/r2.py` | Cloudflare R2 upload | Only used by snapshot tasks (dead) |
| `services/risk/` (4 files) | analyzer, concentration, position_sizer, stop_loss | Built, no API endpoint exposes them |
| `services/strategies/dual_momentum/` | Engine file | Dead code |
| `services/strategies/etf_scorer.py` | ETF scoring | Exists, ETFs excluded from default rankings |
| `services/strategies/backtest_validation.py` | Backtesting | Not called from beat schedule |
| `admin_backfill_runs` | DB table | Internal one-time tooling |
| `hydration_jobs` | DB table | One-off enrichment, not recurring |

---

## Known Issues / TODO

| Issue | Severity | Status |
|---|---|---|
| `magic_formula_score` = 0 for most instruments | Low | EBIT column still NULL for many; nightly beat will backfill |
| US `score_date` stale after beat restart | Low | Auto-resolves on next 00:30 UTC run |
| Clerk development keys in production | Medium | Requires manual Clerk dashboard switch |
| `scoring_snapshots` table growing silently | Low | Not pruned; safe to truncate and remove |
| `minervini_score` / `dual_momentum_score` columns waste space | Low | Can be dropped after confirming no read paths exist |
| `risk/` services have no API exposure | Low | Either wire up or delete |
| Storage growth rate: ~900 KB/day (prices + scores) | Note | At current scale, headroom is >1 year on free tier; upgrade resolves indefinitely |

---

## Storage Growth Estimate

| Source | Daily rows added | Approx size/day |
|---|---|---|
| prices (US+KR) | ~6,565 | ~900 KB |
| strategy_scores | ~6,565 | ~800 KB |
| consensus_scores | ~6,565 | ~300 KB |
| **Total** | **~20,000** | **~2 MB/day** |

At 2 MB/day with 222 MB current headroom (free tier) → ~111 days before hitting 512 MB again.
**Neon free tier upgrade or the rolling purge job makes this a non-issue.**
The purge job deletes 1 day of prices for every new day added, keeping prices stable at ~224 MB.
