# Task Tracker — Multi-Strategy Consensus Stock Research Platform

> Reference plan: `c:\Users\kyusu\vibecoding_projects\claude\PLAN-FINAL.md`
> Updated: 2026-04-13

---

## Current State Assessment

| Area | Status | Notes |
|------|--------|-------|
| `uv` installed | ✅ Installed | `uv 0.11.6` installed in `C:\Users\kyusu\.local\bin` |
| Git repo | ✅ Exists | `.git` present |
| `.python-version` | ✅ `3.12` | File exists |
| `Procfile` | ✅ Exists | api/worker/beat configured with `--pool=solo` |
| `.env` / `.env.example` | ✅ Exists | Uses native/local defaults with `POSTGRES_SCHEMA=consensus_app`. Local PostgreSQL and Redis are reachable. **No Neon/Upstash yet** |
| `backend/pyproject.toml` | ✅ Exists | All dependencies declared |
| `backend/.venv` | ✅ Exists | Synced with `uv`. Current interpreter is Python 3.14.3 |
| `backend/app/` | ✅ Skeleton exists | `main.py`, `core/config.py`, `core/database.py` present |
| `backend/app/models/` | ✅ All 11 model files exist | `instrument.py`, `price.py`, `fundamental.py`, etc. |
| `backend/alembic/versions/` | ⚠️ Migration exists with local fallback | `0001_initial_schema.py` now tolerates missing TimescaleDB locally, but isolated-schema Alembic materialization still needs follow-up |
| `backend/app/api/v1/` | ✅ Health endpoint verified | `health.py` executes `SELECT 1`; live `/api/v1/health` returns `{"status":"ok","db":"connected"}` |
| `backend/tests/` | ✅ Basic tests passing | `conftest.py` isolates tests into `consensus_test` schema; `test_health.py` passes |
| `backend/app/services/` | ⚠️ Directory skeletons only | `ingestion/`, `strategies/`, `korea/`, `market_regime/`, `risk/` — all empty (`__init__.py` only) |
| `backend/app/tasks/` | ⚠️ Stubs only | `celery_app.py` exists; `ingestion_tasks.py`, `scoring_tasks.py`, etc. are empty stubs |
| `scripts/` | ✅ Created | `common.ps1`, `dev.ps1`, `stop-dev.ps1`, `start-api.ps1`, `start-worker.ps1`, `start-beat.ps1`, `status-dev.ps1` |
| `frontend/` | ❌ Empty | Not started |
| Neon account | ❓ Unknown | `.env` uses localhost — not yet updated to cloud |
| Upstash account | ❓ Unknown | `.env` uses localhost Redis |

**Summary:** Phase 0 is effectively complete on the native/local path except for Timescale-native provisioning. `uv` is installed, the backend venv is synced, local PostgreSQL/Redis are reachable, local operator scripts exist, direct Python DB connectivity is verified, and the live health endpoint plus the automated health test both pass. For Phase 1, the clean application schema now lives in `consensus_app` inside the existing local database so development can proceed without touching the legacy `public` schema. The remaining schema caveats are TimescaleDB availability and Alembic's isolated-schema materialization behavior.

---

## PHASE 0: Dev Environment Bootstrap

- [x] **0.1a** — `.python-version` file exists with `3.12`
- [x] **0.1b** — Install `uv` on Windows (`winget install --id astral-sh.uv`)
- [x] **0.1c** — Verify `uv --version` succeeds
- [x] **0.1d** — Re-create `.venv` using `uv sync` (currently created by pip, not uv)
- [ ] **0.2** — Provision Neon (PostgreSQL + TimescaleDB) + Upstash (Redis) — OR choose native path
  - [ ] Option A (Cloud): Create Neon project → enable TimescaleDB → copy DSN
  - [ ] Option A (Cloud): Create Upstash Redis → copy `rediss://` URL
  - [ ] Option B (Native): Install PostgreSQL 16 + TimescaleDB locally
  - [ ] Option B (Native): Install Memurai locally
  - [x] Option B (Native): Local PostgreSQL is reachable on `localhost:5432`
  - [x] Option B (Native): Local Redis-compatible service is reachable on `localhost:6379`
- [x] **0.3** — Run `uv sync --project backend` to install all deps from `pyproject.toml`
  - [x] Verify `TA-Lib` installs (requires C build tools on Windows)
  - [x] Verify `psycopg[binary]` installs correctly
- [x] **0.4** — Update `.env` with correct connection strings (Neon DSN or local)
  - [x] Set `DATABASE_URL` / `POSTGRES_*` vars
  - [x] Set `POSTGRES_SCHEMA=consensus_app` to isolate the app from legacy local tables
  - [x] Set `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
  - [x] Verify DB connectivity from Python
- [x] **0.5** — Create `scripts/` PowerShell convenience scripts
  - [x] `scripts/dev.ps1` (start all processes)
  - [x] `scripts/stop-dev.ps1`
  - [x] `scripts/start-api.ps1`
  - [x] `scripts/start-worker.ps1`
  - [x] `scripts/start-beat.ps1`
  - [x] `scripts/status-dev.ps1`
  - [x] **Test:** `.\scripts\start-api.ps1` → `GET /health` returns 200

**PHASE 0 CHECKPOINT:** `uv` installed, `.venv` managed by `uv`, DB reachable, API starts.

---

## PHASE 1: Foundation + Data Infrastructure

- [x] **1.1a** — Git repo initialized
- [x] **1.1b** — FastAPI app skeleton (`main.py`, `core/config.py`, `core/database.py`)
- [x] **1.1c** — Alembic configured (`alembic.ini`, `alembic/env.py`)
- [x] **1.1d** — `.env.example` created
- [x] **1.1e** — Project directory structure created (models, services, tasks stubs)
- [x] **1.1f** — `Procfile` created
- [x] **1.1g** — Add `/health` endpoint with DB connectivity check
- [x] **1.1h** — **Test:** `GET /health` returns 200 with DB status

- [x] **1.2a** — All SQLAlchemy model files exist (`instrument.py`, `price.py`, `fundamental.py`, etc.)
- [x] **1.2b** — Alembic migration `0001_initial_schema.py` written
- [x] **1.2c** — Run `alembic upgrade head` against target DB (Neon or local)
  - [x] Created isolated app schema `consensus_app` inside the local `consensus` database
  - [x] `uv run alembic upgrade head` successfully materialized tables in isolated schema
- [ ] **1.2d** — Enable TimescaleDB hypertable on `prices` table
  - [ ] Local PostgreSQL does not currently expose the `timescaledb` extension
- [x] **1.2e** — Create indexes for common query patterns
- [x] **1.2f** — **Test:** All tables exist. Insert + query sample row in each table.
  - [x] Current model tables exist in `consensus_app`
  - [x] Verified via async SQLAlchemy session insert/query scripts

- [x] **1.3** — US Instrument + Price Ingestion (`us_price.py`)
  - [x] Build `services/ingestion/us_price.py` using `yfinance`
  - [ ] Implement FMP fallback logic (auto-switch if error rate >10%)
  - [x] Fetch S&P 500 + NASDAQ 100 list → populate `instruments`
  - [x] Fetch 2 years historical OHLCV → populate `prices` hypertable
  - [x] Compute + store `avg_volume_50d` rolling average
  - [ ] Update `data_freshness` on success/failure
  - [x] **Test:** AAPL has ~500 rows in `prices`. Spot-check a known close date.

- [ ] **1.4** — KR Instrument + Price Ingestion (`kr_price.py`)
  - [x] Register KIS Developers account (APP_KEY + APP_SECRET)
  - [x] Build `services/ingestion/kr_price.py` using `python-kis`
  - [x] Fetch KOSPI + KOSDAQ lists via `FinanceDataReader` → populate `instruments`
  - [x] Fetch 2 years historical OHLCV via KIS REST → populate `prices`
  - [ ] Update `data_freshness`
  - [x] **Test:** Samsung (005930) prices: correct count + spot-check close. KIS token refresh works.

- [ ] **1.5** — Basic Technical Indicators (`indicators.py`)
  - [ ] Compute SMAs: 21, 50, 150, 200-day for all instruments
  - [ ] Compute 52-week high/low
  - [ ] Compute ATR (14-day)
  - [ ] Compute IBD RS Rating (batch percentile rank per market)
  - [ ] Build `services/technical/indicators.py` with reusable functions
  - [ ] **Test:** SMA(50) for AAPL matches TradingView. RS rating is 1-99 distributed.

- [ ] **1.6** — Market Regime State Machine (`state_machine.py`)
  - [ ] Build `services/market_regime/state_machine.py` with 3 states
  - [ ] Distribution day counter (rolling 25-session)
  - [ ] Drawdown-from-high detection (10% → correction, 20% → bear)
  - [ ] Follow-through day detection
  - [ ] Death cross / golden cross detection
  - [ ] Run historical detection → populate `market_regime`
  - [ ] **Test:** 2022 bear market → MARKET_IN_CORRECTION. 2023 recovery → CONFIRMED_UPTREND.

**PHASE 1 CHECKPOINT:** Prices flowing for both markets. Indicators computing. Regime state machine producing sensible historical states.

---

## PHASE 2: Fundamental Data + CANSLIM & Piotroski Engines

- [ ] **2.1** — US Fundamental Ingestion (SEC EDGAR via `edgartools`)
  - [ ] Build `services/ingestion/us_fundamental.py`
  - [ ] Ingest quarterly (10-Q): EPS, revenue, net income → `fundamentals_quarterly`
  - [ ] Ingest annual (10-K): full IS+BS+CF → `fundamentals_annual`
  - [ ] Pre-compute `eps_yoy_growth`, `revenue_yoy_growth`
  - [ ] Handle fiscal year variations
  - [ ] **Test:** AAPL last 8 quarters EPS match known values. All Piotroski fields present.

- [ ] **2.2** — KR Fundamental Ingestion (OpenDART via `OpenDartReader`)
  - [ ] Register OpenDART API key
  - [ ] Build `services/ingestion/kr_fundamental.py`
  - [ ] Ingest quarterly financials via `fnlttSinglAcnt`
  - [ ] Ingest annual financials (full IS+BS+CF)
  - [ ] Map K-IFRS field names (매출액→revenue, 당기순이익→net_income, etc.)
  - [ ] Rate-limit to 1000 req/day
  - [ ] **Test:** Samsung (005930) quarterly EPS vs published earnings. Balance sheet fields populated.

- [ ] **2.3** — Korea Adaptations
  - [ ] Build `services/korea/sector_normalizer.py`: semiconductor 2Q avg, shipbuilding 3Q avg
  - [ ] Build `services/korea/chaebol_filter.py`: group membership + cross-holding flag
  - [ ] **Test:** Samsung C-score uses 2Q avg. Chaebol cross-holding → `is_chaebol_cross=True`.

- [ ] **2.4** — CANSLIM Engine (C-A-N-S-L-I)
  - [ ] `services/strategies/canslim/c_earnings.py` — quarterly EPS growth scoring
  - [ ] `services/strategies/canslim/a_annual.py` — annual EPS CAGR scoring
  - [ ] `services/strategies/canslim/n_new_highs.py` — proximity + base detection scoring
  - [ ] `services/strategies/canslim/s_supply.py` — float ratio + volume surge scoring
  - [ ] `services/strategies/canslim/l_leader.py` — RS rating mapping
  - [ ] `services/strategies/canslim/i_institutional.py` — ownership sweet spot scoring
  - [ ] `services/strategies/canslim/engine.py` — orchestrate all 6 + M gate → composite
  - [ ] Run against all US + KR instruments → store in `strategy_scores`
  - [ ] **Test:** NVDA → high C, A, L. Declining stock → low scores. Hand-verify 3 stocks.

- [ ] **2.5** — Piotroski F-Score Engine
  - [ ] `services/strategies/piotroski/engine.py` with 9 binary criteria (F1-F9)
  - [ ] Normalize F-score (0-9) to 0-100
  - [ ] Run on all instruments → store in `strategy_scores`
  - [ ] **Test:** AAPL → F-score 7-9. Struggling company → 0-3. Hand-verify each criterion.

- [ ] **2.6** — Early Backtesting Validation
  - [ ] Run CANSLIM + Piotroski on 6 months of historical data
  - [ ] Track forward 3-month returns for top-scoring vs bottom-scoring
  - [ ] Verify meaningful signal exists
  - [ ] **Test:** High scorers outperform low scorers in forward returns.

**PHASE 2 CHECKPOINT:** Two strategies producing scores. 5 US + 5 KR hand-verified. CANSLIM and Piotroski rank *different* stocks. Early backtest shows positive signal.

---

## PHASE 3: Remaining Strategies + Deep Technical Analysis

- [ ] **3.1** — Minervini Trend Template Engine
  - [ ] `services/strategies/minervini/engine.py` — 8 criteria (T1-T8)
  - [ ] Score: count passing / 8 → 0-100
  - [ ] Run on all instruments → store
  - [ ] **Test:** Clear uptrend stock → 8/8 = 100. Declining stock → 0-2/8.

- [ ] **3.2** — Weinstein Stage Analysis Engine
  - [ ] `services/strategies/weinstein/engine.py` — 4-stage classification
  - [ ] 150-day MA slope, price-vs-MA, cross count, volume patterns
  - [ ] Sub-stages: early/mid/late Stage 2
  - [ ] **Test:** 6-month recovery above 150MA → Stage 2. Below declining MA → Stage 4.

- [ ] **3.3** — Dual Momentum Engine
  - [ ] Ingest FRED DGS3MO (US) and BOK base rate (KR)
  - [ ] `services/strategies/dual_momentum/engine.py` — absolute + relative momentum
  - [ ] **Test:** Stock up 50% vs S&P up 15% → abs+rel TRUE → high score. Down 10% → 0.

- [ ] **3.4** — Pattern Detection Library
  - [ ] `services/technical/pattern_detector.py`
  - [ ] Cup with Handle algorithm
  - [ ] Double Bottom (W-Pattern)
  - [ ] Flat Base
  - [ ] VCP (Volatility Contraction Pattern)
  - [ ] High Tight Flag
  - [ ] Ascending Base
  - [ ] Store in `strategy_scores.patterns` JSONB
  - [ ] **Test:** Historical NVDA data → cup-with-handle detected. Each pattern type tested.

- [ ] **3.5** — Advanced Technical Indicators
  - [ ] Accumulation/Distribution Rating (13-week, A-E)
  - [ ] Up/Down Volume Ratio (50-day)
  - [ ] Volume Dry-Up score (base quality)
  - [ ] RS Line analysis (new highs, leading indicator)
  - [ ] Bollinger Band Squeeze detection
  - [ ] Money Flow Index (14-day)
  - [ ] On-Balance Volume + trend
  - [ ] **Test:** A/D rating for known accumulation stock. BB squeeze before volatility expansion.

- [ ] **3.6** — Technical Composite + Multi-Timeframe
  - [ ] `services/technical/multi_timeframe.py` — daily/weekly/monthly alignment
  - [ ] Technical composite aggregation → single 0-100 score
  - [ ] Store `technical_composite` in `strategy_scores`
  - [ ] **Test:** Pattern + good A/D + multi-TF alignment → high composite.

**PHASE 3 CHECKPOINT:** All 5 strategies + technical engine producing scores. Each strategy has reasonable distribution. Strategies rank stocks differently (low correlation).

---

## PHASE 4: Consensus Engine + Institutional Data

- [ ] **4.1** — US Institutional Ingestion (SEC EDGAR 13F)
  - [ ] `services/ingestion/us_institutional.py` — parse 13F bulk data
  - [ ] Extract: num_owners, institutional_pct, qoq_change per instrument
  - [ ] Compute fund_quality_score
  - [ ] **Test:** AAPL institutional % ≈ 60%. qoq_change computed correctly.

- [ ] **4.2** — KR Investor Flow Ingestion (KIS Developers)
  - [ ] `services/ingestion/kr_investor_flow.py` — KIS investor category API
  - [ ] Fetch daily foreign/institutional/individual net buy/sell
  - [ ] 30-day rolling sums → populate `institutional`
  - [ ] Integrate chaebol filter
  - [ ] **Test:** Samsung flows internally consistent. Breakdown sums correctly.

- [ ] **4.3** — Consensus Scoring Engine
  - [ ] `services/strategies/consensus.py`
  - [ ] Read 5 strategy scores → count ≥ 70 → conviction level (DIAMOND/GOLD/SILVER/BRONZE)
  - [ ] Weighted consensus composite
  - [ ] Technical overlay (25% weight)
  - [ ] Regime gate (cap SILVER during correction)
  - [ ] Populate `consensus_scores`
  - [ ] **Test:** All 5 scores ≥ 70 → DIAMOND. Only 2 → BRONZE. Regime capping works.

- [ ] **4.4** — Snapshot Generation
  - [ ] Build snapshot task: freeze consensus rankings per date/market/asset_type
  - [ ] Store in `scoring_snapshots` with `config_hash`
  - [ ] **Test:** Generate snapshot → re-run → identical `rankings_json`.

**PHASE 4 CHECKPOINT:** Full consensus pipeline producing DIAMOND/GOLD/SILVER/BRONZE. DIAMOND: 0-5 per market. GOLD: 10-30. Distribution feels right.

---

## PHASE 5: API Layer + Risk Management

- [ ] **5.1** — Rankings Endpoint (`GET /api/v1/rankings`)
  - [ ] `endpoints/rankings.py` with market, asset_type, conviction, limit, offset
  - [ ] Include all 5 scores, conviction, technical, risk
  - [ ] Pagination
  - [ ] Redis cache (TTL 1hr, invalidate on new scoring run)
  - [ ] **Test:** DIAMOND returns 0-5 stocks. GOLD returns more.

- [ ] **5.2** — Instruments Endpoint (`GET /api/v1/instruments/{ticker}`)
  - [ ] `endpoints/instruments.py` — full breakdown per instrument
  - [ ] **Test:** AAPL returns Piotroski F1-F9 detail + Minervini T1-T8 checklist.

- [ ] **5.3** — Strategy + Filter Endpoints
  - [ ] `GET /api/v1/strategies/{name}/rankings`
  - [ ] `POST /api/v1/filters/query` with all filter params
  - [ ] **Test:** `/strategies/piotroski/rankings` sorts by F-score. Filter `f_score >= 8` returns subset.

- [ ] **5.4** — Regime + Snapshots + Alerts Endpoints
  - [ ] `GET /api/v1/market-regime`
  - [ ] `GET /api/v1/snapshots/latest`
  - [ ] `GET /api/v1/alerts`
  - [ ] **Test:** Regime endpoint shows state + history. Snapshot returns frozen data.

- [ ] **5.5** — Risk Management
  - [ ] `services/risk/stop_loss.py` — 7% stop-loss alerts from entry reference
  - [ ] `services/risk/position_sizer.py` — ATR-based sizing guidance
  - [ ] Concentration checker: sector/exchange warnings
  - [ ] Generate + store alerts in `alerts`
  - [ ] **Test:** 8% drop → CRITICAL alert. Position sizing calculated correctly.

- [ ] **5.6** — API Authentication
  - [ ] API key middleware
  - [ ] Rate limiting per key
  - [ ] **Test:** No key → 401. Valid key → data returned.

**PHASE 5 CHECKPOINT:** Full API functional. Complete flow: ingest → score → rank → serve. All endpoints correct. Alerts fire on simulated risk events.

---

## PHASE 6: ETF Scoring + Frontend

- [ ] **6.1** — ETF Ingestion + Scoring
  - [ ] Ingest ETF constituent mappings (US + KR)
  - [ ] `services/strategies/etf_scorer.py` — constituent consensus, momentum, flow, cost, liquidity
  - [ ] Exclude leveraged/inverse ETFs
  - [ ] **Test:** SPY reflects constituents' avg. Leveraged ETF excluded.

- [ ] **6.2** — Frontend: Consensus Leaderboard
  - [ ] Set up Next.js with Tailwind + shadcn/ui
  - [ ] Rankings table with DIAMOND/GOLD/SILVER/BRONZE badges
  - [ ] Market selector, asset type toggle, conviction filter
  - [ ] Regime banner (green/yellow/red)
  - [ ] **Test:** Page loads. DIAMOND filter → correct picks. Regime banner matches API.

- [ ] **6.3** — Frontend: Instrument Detail Page
  - [ ] Strategy radar/spider chart (5 axes)
  - [ ] CANSLIM C/A/N/S/L/I breakdown bars
  - [ ] Piotroski F1-F9 checklist (✅/❌)
  - [ ] Minervini T1-T8 checklist
  - [ ] Weinstein stage badge + history
  - [ ] 30-day score trail chart
  - [ ] **Test:** Click NVDA → all 5 breakdowns visible. Radar renders correctly.

- [ ] **6.4** — Frontend: Price Chart + Pattern Overlay
  - [ ] Lightweight Charts (TradingView)
  - [ ] Pattern overlay (cup-with-handle drawn, pivot line)
  - [ ] SMA lines (50, 150, 200)
  - [ ] Volume bars with A/D coloring
  - [ ] RS Line secondary chart
  - [ ] **Test:** Chart loads. Cup-with-handle visible on a stock that has one.

- [ ] **6.5** — Frontend: Filters, Alerts, Settings
  - [ ] Advanced filter builder
  - [ ] Alert feed (sortable by severity/type)
  - [ ] Market regime detail page
  - [ ] **Test:** Apply filter → results update. Alert list shows recent alerts.

**PHASE 6 CHECKPOINT:** Full web app working. End-to-end: browser → leaderboard → stock → analysis + chart + all 5 strategies.

---

## PHASE 7: Validation + Polish

- [ ] **7.1** — Full Backtesting Framework
  - [ ] Replay engine: historical scoring as-of past dates
  - [ ] Track DIAMOND/GOLD forward returns (1/3/6/12 months)
  - [ ] Compare vs CANSLIM-only vs S&P 500/KOSPI
  - [ ] Compute hit rate, avg return, max drawdown
  - [ ] **Test:** DIAMOND outperforms any single strategy on risk-adjusted basis.

- [ ] **7.2** — Full Test Suite
  - [ ] Unit tests per strategy (boundary conditions, edge cases)
  - [ ] Pattern detection tests (historical data with known patterns)
  - [ ] Consensus logic tests
  - [ ] Regime gate tests
  - [ ] API integration tests
  - [ ] **Test:** `pytest` passes 100%. Coverage >80% on scoring engines.

- [ ] **7.3** — Data Integrity Monitoring
  - [ ] Daily task: check missing prices, stale fundamentals
  - [ ] RS distribution check (~uniform 1-99)
  - [ ] Piotroski distribution (roughly normal, centered ~5)
  - [ ] Snapshot reproducibility check
  - [ ] **Test:** Monitoring alerts fire when data intentionally made stale.

- [ ] **7.4** — Korea-Specific Verification
  - [ ] Chaebol filter catches Samsung cross-holdings
  - [ ] Sector normalization adjusts semi thresholds
  - [ ] KIS investor flows internally consistent
  - [ ] Price limit (±30%) handling in pattern detection
  - [ ] **Test:** Side-by-side vs published Korean financial data.

**PHASE 7 CHECKPOINT:** Platform validated. Backtesting shows meaningful signal. All tests pass. Data integrity clean.

---

## Progress Summary

| Phase | Steps | Done | In Progress | Remaining |
|-------|-------|------|-------------|-----------|
| 0: Dev Bootstrap | 5 | 4 | 1 | 0 |
| 1: Foundation | 6 | ~85% of 1.1-1.2 | 1.2c, 1.2d, 1.2f | 1.3, 1.4, 1.5, 1.6 |
| 2: Fundamentals + CANSLIM/Piotroski | 6 | 0 | 0 | 6 |
| 3: Remaining Strategies + Tech Analysis | 6 | 0 | 0 | 6 |
| 4: Consensus + Institutional | 4 | 0 | 0 | 4 |
| 5: API + Risk | 6 | 0 | 0 | 6 |
| 6: ETF + Frontend | 5 | 0 | 0 | 5 |
| 7: Validation | 4 | 0 | 0 | 4 |
| **Total** | **42** | **~10** | **~4** | **~28** |

**Next action: PHASE 1 — Finish schema verification in `consensus_app` (sample inserts and Alembic isolated-schema follow-up), then begin US instrument and price ingestion in `services/ingestion/us_price.py`.**
