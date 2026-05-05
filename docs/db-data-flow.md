# Database & Data Flow Status
_Last updated: 2026-05-06_

---

## Current DB Size (Neon `consensus_app`, Railway-connected)

| Table | Size | Notes |
|---|---|---|
| `prices` | 528 MB | Largest table; rolling purge is required to keep Neon growth bounded |
| `strategy_scores` | 68 MB | Per-strategy scores per instrument per day |
| `instruments` | 16 MB | Master instrument list; Neon currently has both stock and legacy ETF rows |
| `consensus_scores` | 6.8 MB | Final score + conviction per instrument per day |
| `fundamentals_quarterly` | 2.2 MB | Last 8 quarters per instrument |
| `instrument_coverage_summary` | 2.0 MB | Freshness/coverage state per instrument |
| `fundamentals_annual` | 896 kB | Last 6 years per instrument |
| `scoring_snapshots` | 1.2 MB | Active snapshot source for `/snapshots/*` and latest date resolution |
| `hydration_jobs` | 112 kB | One-off enrichment jobs |
| `alerts` | 80 kB | Push alert history |
| `data_freshness` | 48 kB | Source freshness records |
| `users` | 48 kB | User TOS acceptance records |
| `user_push_tokens` | 32 kB | Mobile push tokens |
| `admin_backfill_runs` | 32 kB | Internal backfill tooling |
| **Verified on** | **2026-05-06** | Neon target: `neondb`, schema: `consensus_app` |

Current instrument composition in Neon:

| Asset type | Rows | Status |
|---|---:|---|
| `stock` | 8,481 | Active |
| `etf` | 6,205 | Legacy data; API rejects ETF requests and cleanup should be phased |

---

## Data Sources

| Source | Data | Market |
|---|---|---|
| **Alpaca Market Data** | Daily OHLCV prices, 50d avg volume | US |
| **SEC EDGAR** | Quarterly/annual fundamentals (EPS, revenue, EBIT, FCF, balance sheet) | US |
| **KIS Developers** | Daily OHLCV prices | KR |
| **OpenDART** | Quarterly/annual fundamentals (Korean GAAP) | KR |
| **SEC 13F** | Institutional ownership % changes | US |

All sources are **free**. Polygon was evaluated and rejected (cost).

---

## Raw Storage Schema

### `instruments` — master list, retained forever
```
id, ticker, name, name_kr (KR only), market (US|KR), exchange,
asset_type (stock), listing_status, sector, industry_group,
shares_outstanding, float_shares, is_active, is_test_issue,
corp_code (KR OpenDART), is_chaebol_cross,
is_leveraged, is_inverse, expense_ratio, aum (legacy ETF columns)
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
minervini_score [LEGACY — weight=0], minervini_criteria_count [ACTIVE technical input], minervini_detail,
weinstein_score [GATE ONLY — not weighted], weinstein_stage, weinstein_detail,
magic_formula_score, magic_formula_rank, magic_formula_detail,
technical_composite, rs_rating, ad_rating, rs_line_new_high,
dual_momentum_score [COMPUTED/STORED — unweighted in consensus]
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

22:00  nightly-us-prices         Alpaca → prices (US, ~6,000+ instruments)
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

These exist in the codebase or DB and need phased cleanup decisions:

| Item | Location | Status |
|---|---|---|
| Legacy ETF instruments | Neon `instruments.asset_type='etf'` | 6,205 rows remain; API is stock-only. Run read-only audit before deleting dependent rows. |
| ETF-specific instrument columns | `is_leveraged`, `is_inverse`, `expense_ratio`, `aum` | Kept for schema compatibility; defer column drops until after one stable release. |
| `minervini_score` | `strategy_scores`, `consensus_scores` | Legacy weighted score, but `minervini_criteria_count` actively feeds technical composite. Do not drop yet. |
| `dual_momentum_score` | `strategy_scores`, `consensus_scores` | Strategy engine and tasks still compute/store it, but consensus ignores it. Decide later: expose, remove compute, or retain as diagnostic. |
| `snapshot_tasks.py` | `backend/app/tasks/` | Placeholder only; actual snapshot task is in `scoring_tasks.py`. |
| `storage/r2.py` | Cloudflare R2 upload | Optional snapshot export path; not in beat schedule. |
| `services/strategies/backtest_validation.py` | Backtesting | Active validation utility, not part of nightly beat. Keep for scoring validation. |

Not dead:

| Item | Active path |
|---|---|
| `scoring_snapshots` | `/snapshots/latest`, `/snapshots/{date}`, and rankings latest-date resolution |
| `services/risk/` | `/risk/analyze-portfolio` endpoint |
| `admin_backfill_runs` | `/admin/backfill` preview/queue/status endpoints |
| `hydration_jobs` | instrument hydration endpoints and worker task |

---

## Known Issues / TODO

| Issue | Severity | Status |
|---|---|---|
| `magic_formula_score` absent for latest stock scores | High | Scoring blocker. Latest Neon audit found 0 Magic Formula rows; root cause is missing `instruments.shares_outstanding`. Code should fall back to `fundamentals_annual.shares_outstanding_annual` and ingestion should backfill instrument shares. |
| Legacy ETF rows still in Neon | Medium | API is stock-only, but 6,205 ETF instruments remain. Use `app.services.ops.neon_cleanup_audit` before any delete. |
| Missing-strategy renormalization can overstate scores | Medium | If only one or two strategies are available, weights renormalize. Add validation/coverage reporting before changing thresholds. |
| Conviction thresholds are heuristic | Medium | Validate DIAMOND/PLATINUM/GOLD/SILVER/BRONZE hit rates over 5/20/60-day forward returns. |
| CANSLIM minimum data gate differs from C/A subscore needs | Medium | The engine can pass the minimum data gate with fewer reports than C/A ideally need; distinguish insufficient data from weak fundamentals. |
| US `score_date` stale after beat restart | Low | Auto-resolves on next 00:30 UTC run |
| Clerk development keys in production | Medium | Requires manual Clerk dashboard switch |
| `scoring_snapshots` growth | Low | Active but small. Add retention only if it becomes material. |
| `minervini_score` / `dual_momentum_score` columns | Low | Do not drop until active compute/read paths are intentionally removed. |
| Storage growth rate: ~900 KB/day (prices + scores) | Note | At current scale, headroom is >1 year on free tier; upgrade resolves indefinitely |

---

## Scoring Critique / Validation Plan

Current consensus remains:

```
CANSLIM 40% + Piotroski 30% + Magic Formula 30%
technical_composite 20% additive when available
Weinstein Stage 2 = conviction gate only
Dual Momentum = computed/stored but unweighted
```

Critique:

| Risk | Why it matters | Next check |
|---|---|---|
| Magic Formula data fragility | ROIC/EY cannot rank without EBIT, invested capital, price, and shares outstanding. | Track ineligible reason counts in scoring profile. |
| Missing-strategy renormalization | A stock can receive a high score from a thin signal set. | Report strategy coverage by score quantile and conviction tier. |
| Piotroski context | Piotroski F-score is strongest as a value/quality screen, not necessarily a universal 30% weight. | Keep active, then validate by market/sector and forward windows. |
| Momentum double-counting | CANSLIM L/N, Minervini-derived technical composite, Weinstein gate, and Dual Momentum overlap. | Compare single-strategy quintiles and consensus tiers. |
| Threshold calibration | 88/78/65/50/35 thresholds are heuristic. | Validate hit rate, average/median return, and drawdown by tier. |

Use the read-only validation utility:

```
uv run python -m app.services.ops.scoring_validation_report
```

Default windows are 5, 20, and 60 trading days. The report groups by conviction level, final-score quantile, market, sector, and strategy coverage.

Use the read-only Neon cleanup audit before ETF deletion:

```
uv run python -m app.services.ops.neon_cleanup_audit
```

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
