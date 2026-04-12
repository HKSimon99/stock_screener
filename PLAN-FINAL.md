# Multi-Strategy Consensus Stock Research Platform — US & Korea

## Context

### Why Multi-Strategy Consensus > Single Strategy

A single strategy (even CANSLIM) has blind spots. CANSLIM ignores balance sheet health. Piotroski ignores momentum. Minervini ignores earnings quality. **But a stock that independently scores well across ALL of these has been validated through multiple orthogonal lenses — earnings growth, financial health, price trend, and momentum — making it a far higher-conviction pick with lower false-positive rate.**

The core idea: run 5 independent strategy engines. A stock appearing in the top tier of 4-5 strategies simultaneously is extraordinarily rare and extraordinarily strong. We call this the **Consensus Score**.

### Critique of Prior CANSLIM-Only Plan

1. **Single-strategy survivorship bias.** O'Neil studied winners retroactively; many stocks meeting CANSLIM criteria still failed. No cross-validation catches these.
2. **Blind to financial health.** 50% EPS growth + deteriorating balance sheet (rising debt, declining cash flow) passes CANSLIM perfectly. Piotroski F-Score catches this — it examines completely different data.
3. **~2% strict pass rate is restrictive, but loosening thresholds adds noise.** Multi-strategy consensus achieves selectivity through *agreement*, not through making any one strategy more extreme.
4. **Shallow technical analysis.** Only cup-with-handle and proximity to 52w high. Missing: VCP, double bottom, flat base, ascending base, high tight flag, volume dry-up, Bollinger squeeze, multi-timeframe confirmation.
5. **Outdated supply thresholds.** O'Neil's 25M shares cap was set in the 1960s-80s. Today mega-caps like NVDA (24B shares) make huge moves. Focus on float ratio and volume behavior instead.
6. **No trend phase awareness.** CANSLIM doesn't distinguish early Stage 2 (ideal) from late Stage 2 (risky) or Stage 3 (distribution). Weinstein Stage Analysis and Minervini's Trend Template fill this gap.

### Strategy Selection — Orthogonality Matrix

| Data Domain | CANSLIM | Piotroski | Minervini TT | Weinstein | Dual Momentum |
|-------------|---------|-----------|--------------|-----------|---------------|
| Earnings growth / acceleration | ★★★ | — | — | — | — |
| Balance sheet / cash flow | — | ★★★ | — | — | — |
| Price trend structure | ★★ | — | ★★★ | ★★★ | ★★ |
| Volume behavior | ★ | — | ★★ | ★ | — |
| Institutional activity | ★★★ | — | — | — | — |
| Market regime | ★★ | — | ★ | ★★ | ★★★ |
| Relative performance | ★★ | — | ★ | — | ★★★ |
| Financial quality | — | ★★★ | — | — | — |

Each strategy looks at fundamentally different aspects. A stock passing all 5 has: strong earnings growth (CANSLIM) + solid balance sheet (Piotroski) + confirmed uptrend structure (Minervini) + right cycle phase (Weinstein) + outperforming both risk-free and benchmark (Dual Momentum).

---

## 1. Technology Stack

### Backend
- **uv** for Python/package/project management on Windows
- **Python 3.12+** with **FastAPI** (async, Pydantic validation, auto-generated OpenAPI docs)
- **SQLAlchemy 2.0** async ORM
- **PostgreSQL 16 + TimescaleDB** (hypertables for price time-series, continuous aggregates for rolling computations)
- **Celery + Redis** (scheduled ingestion pipelines, nightly scoring batch jobs)
- **pandas-ta** or **ta-lib** (technical indicator computation)

### Frontend
- **Next.js 14+** (App Router, TypeScript)
- **Tailwind CSS + shadcn/ui** components
- **Lightweight Charts** (TradingView open-source) for price/volume charts with pattern overlay
- **TanStack Query** for server-state caching
- **Recharts** for strategy radar/spider charts per instrument

### Infrastructure — Cloud-Managed (Primary Path)

The primary development and production infrastructure uses **managed cloud services**, eliminating the need for Docker or native database installations on Windows. This is the recommended path.

| Service | Role | Free Tier | Notes |
|---------|------|-----------|-------|
| **Neon** | PostgreSQL 16 + TimescaleDB | 0.5 GB storage, 100 CU-hrs/mo, scale-to-zero | Serverless, built-in PgBouncer, DB branching for dev/test |
| **Upstash** | Redis (Celery broker + API cache) | 500K commands/mo | Serverless, TLS by default, works with Celery (tuned config required) |

**Why Neon over Supabase?** Supabase deprecated TimescaleDB on PostgreSQL 17+. Neon fully supports TimescaleDB as an extension. Neon also offers database branching for instant dev/test copies.

**Why Upstash over local Redis/Memurai?** No Windows compatibility issues. No local installation. Works over TLS. The Celery broker runs in the cloud, eliminating one of the biggest Windows pain points.

**Storage planning:** Full dataset (~7000 instruments × 2 years daily OHLCV) ≈ 700MB. Options:
- Dev with S&P 500 subset only → stays within 0.5 GB free tier
- Neon Launch plan ($5/mo) → covers full dataset
- Aiven free tier (5 GB storage) → alternative if more room needed

#### Upstash Celery Configuration (Command Optimization)

```python
# celery_config.py — optimized for Upstash free tier (500K commands/mo)
app.conf.update(
    broker_url="rediss://:PASSWORD@HOST:PORT",
    broker_transport_options={
        'heartbeat': 120,           # Reduce PING frequency
        'visibility_timeout': 3600,  # 1 hour for long-running scoring tasks
    },
    worker_prefetch_multiplier=1,    # Reduce overhead
    result_backend=None,             # Disable if not needed (saves ~40% commands)
)
```

### Infrastructure — Native Windows (Alternative Path)

For developers who prefer full local control or need offline development:

- **PostgreSQL 16** native installation with TimescaleDB extension
- **Memurai** (Windows-native Redis-compatible server) for Celery broker/cache
- **Celery worker pool:** `--pool=solo` (Windows does not support `prefork` — Celery officially dropped Windows support in v4.x; `--pool=solo` is the single-threaded workaround)
- **Process launcher:** PowerShell scripts in `scripts/` directory
- **Fallback processes:** separate terminals using `.venv` Python directly

This is a runtime/tooling choice only. It does **not** change the product roadmap, strategy lineup, or data-provider roadmap. The application code is identical regardless of which infrastructure path is used.

### Data Sources — Verified Availability (All Free or Included with Brokerage)

#### US Market — Fully Free Stack

| Need | Source | Library | Cost | Notes |
|------|--------|---------|------|-------|
| OHLCV (daily) | Yahoo Finance | `yfinance` | Free | Reliable for EOD. 2000 req/hr unauth. Backup: FMP free tier |
| OHLCV (intraday, optional) | Financial Modeling Prep | `fmpsdk` / HTTP | Free (250 req/day) | 1-min to daily bars. Free tier sufficient for EOD |
| Quarterly financials | SEC EDGAR XBRL | `edgartools` | Free | Official 10-Q data, no API key needed, <1s latency |
| Annual financials (IS+BS+CF) | SEC EDGAR XBRL | `edgartools` | Free | Full income stmt, balance sheet, cash flow for Piotroski |
| Shares outstanding / float | Yahoo Finance | `yfinance` | Free | `.info['floatShares']`, `.info['sharesOutstanding']` |
| Institutional ownership (13F) | SEC EDGAR 13F bulk | `edgartools` | Free | Quarterly institutional holdings |
| Stock listings / metadata | Yahoo Finance | `yfinance` | Free | Ticker screener, sector/industry |
| Risk-free rate | FRED (Federal Reserve) | `fredapi` | Free | DGS3MO (3-month T-bill rate) |
| ETF constituents | ETF provider websites | Web scrape / manual | Free | iShares/Vanguard publish holdings CSVs |

**US cost: $0/month.** yfinance is the most widely-used free financial data library in Python. SEC EDGAR is the official government source — unlimited, no authentication. FMP free tier (250 req/day) serves as backup for pre-computed ratios.

#### yfinance Reliability & Fallback Strategy

yfinance is a web scraper, not an official API. Yahoo periodically changes their endpoints. The platform must handle this gracefully:

```
Primary: yfinance for all US OHLCV
Fallback: FMP free tier (250 req/day) for critical instruments
Detection: If yfinance returns errors for >10% of batch → auto-switch to FMP
Alert: DATA_SOURCE_DEGRADED alert generated on fallback activation
```

#### KR Market — KIS Developers + Free Supplementary

| Need | Source | Library | Cost | Notes |
|------|--------|---------|------|-------|
| **Real-time quotes** | **KIS Developers API** | `mojito` / `pykis` | **Free (with KIS account)** | WebSocket real-time, REST historical |
| **Historical OHLCV** | **KIS Developers API** | `mojito` | **Free** | Daily/weekly/monthly candles |
| **Current price / volume** | **KIS Developers API** | `mojito` | **Free** | Live bid/ask, volume, VWAP |
| Quarterly financials | OpenDART | `OpenDartReader` | Free (API key) | K-IFRS quarterly reports (45-day lag) |
| Annual financials (IS+BS+CF) | OpenDART | `OpenDartReader` | Free | Full financials for Piotroski |
| Foreign ownership / investor flows | KIS Developers API | `mojito` | Free | Foreign/institutional/individual breakdown |
| Stock listings / metadata | FinanceDataReader | `FinanceDataReader` | Free | KOSPI/KOSDAQ/KONEX listings |
| Supplementary price data | Research-only fallback | `pykrx` | Free | Optional backup for manual validation, not part of the primary runtime path |
| Risk-free rate | Bank of Korea | Web scrape | Free | BOK base rate |
| ETF constituents | KRX / ETF providers | Manual / scrape | Free | KRX publishes ETF PDF holdings |

**KR cost: $0/month** (requires KIS brokerage account — free to open).

#### KIS Developers API — Key Capabilities

KIS (Korea Investment & Securities) Open Trading API provides:
- **Real-time WebSocket quotes**: Live bid/ask/last/volume for all KOSPI/KOSDAQ stocks
- **Historical chart data**: Daily/weekly/monthly OHLCV going back years
- **Investor category breakdown**: Foreign, institutional, individual net buy/sell per stock — **this replaces the KRX Data Marketplace license requirement**
- **Financial data**: Some pre-computed fundamentals (PER, PBR, EPS)
- **Order execution** (not needed for screener, but available)
- **Rate limits**: Generous — 20 requests/second for REST, unlimited WebSocket subscriptions
- **Python libraries**: `mojito` (most popular), `pykis`, official `open-trading-api`
- **Setup**: Open KIS account → Get APP_KEY + APP_SECRET from KIS Developers portal → Authenticate via OAuth token

#### KIS vs Previous KRX Data Marketplace Approach
| Capability | KRX Data Marketplace | KIS Developers |
|------------|---------------------|----------------|
| Real-time quotes | License required ($) | Free with account |
| Historical OHLCV | License required ($) | Free |
| Foreign ownership | License required ($) | Free (investor category API) |
| Institutional flows | Limited | Free (investor breakdown) |
| Cost | Paid license | Free (brokerage account) |
| Rate limit | Unknown | 20 req/sec |
| Python library | None official | `mojito` (well-maintained) |

**KIS Developers solves three problems at once:** real-time quotes, historical data, AND investor flow breakdowns — all free.

### Data Field Verification for Each Strategy

**CANSLIM needs:** Quarterly EPS + revenue (EDGAR/DART ✓), shares outstanding (yfinance/KIS ✓), float (yfinance ✓, KR: computed from DART major shareholder data), volume (yfinance/KIS ✓), institutional holders (13F ✓, KR: KIS investor category API ✓)

**Piotroski needs:** Net income, total assets, operating cash flow, long-term debt, current assets, current liabilities, shares outstanding, gross profit, revenue — ALL from EDGAR XBRL (US) and OpenDART (KR) ✓

**Minervini Trend Template needs:** 50/150/200-day MAs, 52-week high/low, RS rating — ALL computed from price data (yfinance/KIS) ✓

**Weinstein Stage needs:** 150-day MA slope, price vs MA, volume patterns — ALL from price/volume data ✓

**Dual Momentum needs:** 12-month returns, benchmark returns, risk-free rate — Price data ✓, FRED/BOK ✓

**Verdict: All data for all 5 strategies is obtainable for $0/month.** US uses yfinance + SEC EDGAR. KR uses KIS Developers + OpenDART. No paid subscriptions required.

---

## 2. Project Structure

```
consensus-platform/
  backend/
    alembic/versions/
    app/
      api/v1/endpoints/
        rankings.py          # GET /rankings (consensus-ranked)
        instruments.py       # GET /instruments/{ticker}
        filters.py           # POST /filters/query
        snapshots.py         # GET /snapshots/latest
        market_regime.py     # GET /market-regime
        alerts.py            # GET /alerts
        strategies.py        # GET /strategies/{name}/rankings
      core/
        config.py
        database.py
      models/
        instrument.py
        price.py
        fundamental.py        # Quarterly + annual + balance sheet + cash flow
        institutional.py
        strategy_score.py     # Per-strategy scores
        consensus_score.py    # Multi-strategy consensus
        market_regime.py
        technical.py          # Patterns, indicators
        etf.py
        alert.py
        snapshot.py
      schemas/
      services/
        strategies/
          base.py             # Abstract strategy interface
          canslim/
            engine.py         # Orchestrates C-A-N-S-L-I-M
            c_earnings.py
            a_annual.py
            n_new_highs.py
            s_supply.py
            l_leader.py
            i_institutional.py
          piotroski/
            engine.py         # 9-point F-Score
          minervini/
            engine.py         # 8-criteria Trend Template
          weinstein/
            engine.py         # 4-stage classification
          dual_momentum/
            engine.py         # Absolute + Relative momentum
          consensus.py        # Multi-strategy aggregator
          etf_scorer.py
        technical/
          pattern_detector.py # Cup-handle, double bottom, flat base, VCP, etc.
          indicators.py       # RS line, A/D rating, OBV, MFI, BB squeeze, etc.
          multi_timeframe.py  # Daily/weekly/monthly alignment
        ingestion/
          us_price.py          # yfinance EOD (free), FMP backup
          us_fundamental.py    # edgartools / SEC EDGAR XBRL
          us_institutional.py  # SEC EDGAR 13F bulk
          kr_price.py          # KIS Developers API (mojito)
          kr_fundamental.py    # OpenDART (OpenDartReader)
          kr_investor_flow.py  # KIS Developers investor category API
          freshness.py
        market_regime/
          state_machine.py
          detector.py
        risk/
          stop_loss.py
          position_sizer.py
        korea/
          chaebol_filter.py
          sector_normalizer.py
      tasks/
      main.py
    tests/
    pyproject.toml
  frontend/
    src/app/
    src/components/
      StrategyRadar.tsx      # Spider/radar chart showing 5 strategy scores
      ConsensusBoard.tsx     # Main leaderboard with conviction badges
      PatternOverlay.tsx     # Chart pattern visualization
      RegimeBanner.tsx
    package.json
  Procfile                   # For local multi-process orchestration
  .python-version
  uv.lock
  .env.example
  scripts/                   # Windows-native dev convenience scripts
    dev.ps1
    stop-dev.ps1
    start-api.ps1
    start-worker.ps1
    start-beat.ps1
    status-dev.ps1
```

---

## Local Configuration Defaults

### Cloud-Managed Path (Primary)

```env
# Neon PostgreSQL + TimescaleDB
DATABASE_URL=postgresql+psycopg://user:password@your-project.neon.tech:5432/neondb?sslmode=require

# Upstash Redis (Celery broker + cache)
REDIS_URL=rediss://:password@your-instance.upstash.io:6379
CELERY_BROKER_URL=rediss://:password@your-instance.upstash.io:6379/0
CELERY_RESULT_BACKEND_URL=  # Leave empty to disable (saves Upstash commands)
```

### Native Windows Path (Alternative)

```env
DATABASE_URL=postgresql+psycopg://consensus:changeme@localhost:5432/consensus
POSTGRES_SCHEMA=consensus_app
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND_URL=redis://localhost:6379/0
```

### Provider Keys (Both Paths)

```env
HTTP_USER_AGENT=...
OPENDART_API_KEY=...
KIS_APP_KEY=...
KIS_APP_SECRET=...
FMP_API_KEY=...
FRED_API_KEY=...
```

Notes:
- `CELERY_BROKER_URL` defaults to `REDIS_URL` if not explicitly set
- On cloud path, disable `CELERY_RESULT_BACKEND_URL` to conserve Upstash commands
- On native Windows path, Celery worker must use `--pool=solo`
- On native Windows path, `POSTGRES_SCHEMA` can isolate the app into a dedicated schema inside an existing local database, avoiding collisions with legacy tables
- On native Windows path, if TimescaleDB is not yet installed, local development may proceed with `prices` as a plain PostgreSQL table; hypertable enablement remains an explicit follow-up task
- The project does **not** use PostgreSQL as the Celery broker because Kombu's SQLAlchemy transport has feature limits

---

## 3. Strategy Engines — Exact Formulas

### 3.1. CANSLIM Engine (Growth + Momentum + Institutional)

Each sub-factor returns 0-100. CANSLIM composite = weighted average.

#### C — Current Quarterly Earnings
```
eps_yoy = (eps_q0 - eps_same_q_prior_yr) / |eps_same_q_prior_yr|
revenue_yoy = (rev_q0 - rev_same_q_prior_yr) / |rev_same_q_prior_yr|

Acceleration: last 3 quarters' YoY growth rates → q0 > q1 > q2 = accelerating
Deceleration: 2+ consecutive quarters of declining growth rate

Scoring:
  eps_q0 ≤ 0        → 0
  eps_yoy < 18%     → 0
  18-24%             → 40
  25-39%             → 60
  40-59%             → 75
  ≥ 60%              → 90
  +10 if revenue_yoy ≥ 25%
  +5  if accelerating
  -15 if deceleration ≥ 2 (triggers alert)
  Clamp [0, 100]

Korea adaptation:
  Semiconductors/Display: 2-quarter trailing avg EPS, thresholds ×0.8
  Shipbuilding/Heavy Industry: 3-quarter trailing avg, thresholds ×0.6
```

#### A — Annual Earnings Growth
```
cagr_3yr = (eps_yr[-1] / eps_yr[-4])^(1/3) - 1
consecutive_3yr = each of last 3 years EPS > prior year
any_negative = any negative EPS in last 3 years

Scoring:
  any_negative → 0
  cagr < 15%  → 10
  15-19%      → 30
  20-24%      → 50
  25-34%      → 70
  35-49%      → 85
  ≥ 50%       → 95
  +5  if consecutive all 5 years
  -20 if NOT consecutive_3yr
  Clamp [0, 100]
```

#### N — New Highs / Base Breakouts
```
proximity = close / high_52w

Base detection (see Section 4 pattern library for full algorithms):
  Identifies cup-with-handle, double bottom, flat base, VCP, ascending base
  best_pattern_score = max score from any detected pattern

Volume confirmation:
  If proximity ≥ 0.98: breakout_confirmed = volume > 1.5 × avg_vol_50d

Scoring:
  proximity < 70%  → 0
  70-79%           → 15
  80-84%           → 30
  85-89%           → 50
  90-94%           → 65
  ≥ 95%            → 80
  +10 if valid base pattern detected (from pattern library)
  +5  if breakout volume confirmed
  +5  if RS line making new high before price (leading indicator)
  Clamp [0, 100]
```

#### S — Supply and Demand
```
float_ratio = float_shares / shares_outstanding
volume_surge_days = days in last 20 where volume > 2× avg_vol_50d
ud_ratio = up_volume_50d / down_volume_50d  (see Section 4)

Scoring:
  Base from float_ratio:
    > 0.90 (very liquid)    → 20
    0.70-0.90               → 35
    0.50-0.70               → 50
    0.30-0.50               → 70
    < 0.30 (tight float)    → 85

  +10 if volume_surge_days ≥ 2 (accumulation)
  +10 if ud_ratio > 1.5 (buying > selling)
  +5  if buyback active
  -10 if ud_ratio < 0.7 (distribution)
  Clamp [0, 100]

  Korea KOSDAQ: +5 if avg_vol_50d > 1.5× sector median
```

#### L — Leader (RS Rating)
```
IBD RS formula:
  strength = 0.40×ret_3m + 0.20×ret_6m + 0.20×ret_9m + 0.20×ret_12m
  rs_rating = percentile_rank(strength, ALL instruments in market) × 99 + 1

Industry Group RS:
  group_median = median strength per industry_group
  ig_rs = percentile_rank(group_median, all groups) × 99 + 1

Scoring:
  rs < 50   → 0
  50-59     → 10
  60-69     → 25
  70-79     → 45
  80-84     → 65
  85-89     → 80
  90-94     → 90
  ≥ 95      → 98
  +5  if ig_rs ≥ 80 (leader in leading group)
  -10 if rs dropped 10+ pts in 4 weeks
  Clamp [0, 100]
```

#### I — Institutional Sponsorship
```
US (from 13F): num_owners, institutional_pct, qoq_change, fund_quality
KR (KIS Developers investor category API):
  foreign_pct, foreign_net_buy_30d, institutional_net_buy_30d
  KIS provides daily foreign/institutional/individual breakdown per stock
  Chaebol filter: if cross-holding → 40% haircut on ownership_pct

Scoring (bell-curve sweet spot at 30-60%):
  < 5%     → 10
  5-14%    → 30
  15-29%   → 55
  30-59%   → 80  (sweet spot)
  60-79%   → 55
  80-89%   → 30
  ≥ 90%    → 10  (too crowded)

  US: +10 if qoq_change > 0, +5 if fund_quality ≥ 70, cap at 15 if owners < 3
  KR: +10 if foreign net buying (KIS), +10 if institutional net buying (KIS), -5 if chaebol cross
  Clamp [0, 100]
```

#### M — Market Direction (Gate)
```
States: CONFIRMED_UPTREND → UPTREND_UNDER_PRESSURE → MARKET_IN_CORRECTION

Detection (daily, per market, on index: SPY / KOSPI / KOSDAQ):
  distribution_day = index DOWN ≥ 0.2% on volume > prior day
  Count in rolling 25-session window
  ≥ 5 distribution days → UPTREND_UNDER_PRESSURE

  drawdown = (52w_high - close) / 52w_high
  ≥ 10% → MARKET_IN_CORRECTION
  ≥ 20% → MARKET_IN_CORRECTION (severity=BEAR)

  Follow-through day: index UP ≥ 1.7% on day 4-7 of rally, volume > prior
  → Triggers recovery to CONFIRMED_UPTREND

  Death cross (50DMA < 200DMA) → UPTREND_UNDER_PRESSURE
  Golden cross → supporting signal for CONFIRMED_UPTREND

Bear-market mode:
  Rankings still computed but flagged with regime warning
  Defensive watchlist: sort by RS resilience + base quality
  REGIME_CHANGE alert (severity=CRITICAL) generated
```

#### CANSLIM Composite
```
Weights: C: 0.20 | A: 0.15 | N: 0.15 | S: 0.10 | L: 0.20 | I: 0.10 | M_gate: 0.10
M_gate values: CONFIRMED=100, UNDER_PRESSURE=40, CORRECTION=0

canslim_composite = Σ(weight × factor_score)
```

---

### 3.2. Piotroski F-Score Engine (Financial Health)

9 binary criteria, each worth 1 point. Score: 0-9.

```
Data needed: Annual financials (income statement, balance sheet, cash flow)
Source: EDGAR 10-K XBRL (US), OpenDART annual reports (KR)

PROFITABILITY (4 points):
  F1: ROA > 0                    (net_income / total_assets > 0)
  F2: Operating cash flow > 0    (cfo > 0)
  F3: ΔROA > 0                   (roa_this_year > roa_last_year)
  F4: Accruals: CFO > net_income (cash flow exceeds accounting earnings)

LEVERAGE / LIQUIDITY (3 points):
  F5: ΔLeverage < 0              (lt_debt/total_assets decreased YoY)
  F6: ΔCurrent Ratio > 0         (current_assets/current_liabilities increased)
  F7: No share dilution           (shares_outstanding_this_year ≤ last_year)

OPERATING EFFICIENCY (2 points):
  F8: ΔGross Margin > 0          (gross_profit/revenue increased YoY)
  F9: ΔAsset Turnover > 0        (revenue/total_assets increased YoY)

f_score = F1 + F2 + F3 + F4 + F5 + F6 + F7 + F8 + F9  (0-9)

Normalized to 0-100:
  f_score 0-1  → 0
  f_score 2    → 15
  f_score 3    → 25
  f_score 4    → 35
  f_score 5    → 50
  f_score 6    → 65
  f_score 7    → 78
  f_score 8    → 90
  f_score 9    → 100

Interpretation:
  8-9: Financially very strong (buy candidates)
  5-7: Average financial health
  0-4: Financially weak (avoid, or short candidates)

Piotroski_composite = normalized score (0-100)
```

---

### 3.3. Minervini Trend Template Engine (Technical Stage)

8 binary criteria. All 8 must pass for "confirmed Stage 2 uptrend."

```
Data needed: Daily OHLCV (computed indicators)

Criteria:
  T1: close > sma_150                    (above 150-day MA)
  T2: close > sma_200                    (above 200-day MA)
  T3: sma_150 > sma_200                  (bullish MA stack)
  T4: sma_200 today > sma_200 22d ago    (200-day MA trending up ≥1 month)
  T5: close > sma_50                     (above 50-day MA)
  T6: close ≥ low_52w × 1.25            (≥25% above 52-week low)
  T7: close ≥ high_52w × 0.75           (within 25% of 52-week high)
  T8: rs_rating ≥ 70                     (relative strength from L factor)

count_passing = sum(T1..T8)

Scoring (0-100):
  8/8 → 100  (perfect trend template — Stage 2 confirmed)
  7/8 → 80
  6/8 → 60
  5/8 → 40
  4/8 → 20
  <4  → 0

  Bonuses:
    +5 if rs_rating ≥ 90
    +5 if sma_50 > sma_150 > sma_200 (perfectly stacked)
    +5 if close > sma_21 (above short-term MA, immediate trend strong)
  Clamp [0, 100]

Minervini_composite = score
```

---

### 3.4. Weinstein Stage Analysis Engine (Cycle Phase)

Classifies each stock into one of 4 stages based on the 30-week (150-day) moving average.

```
Data needed: Daily OHLCV (computed indicators)

Indicators:
  ma_150 = SMA(close, 150)
  ma_slope_20d = (ma_150_today - ma_150_20d_ago) / ma_150_20d_ago
  price_vs_ma = close / ma_150 - 1
  cross_count_60d = times price crossed ma_150 in last 60 trading days
  vol_on_up_days = avg volume on days price rose, last 50 days
  vol_on_down_days = avg volume on days price fell, last 50 days

Stage Detection:
  Stage 1 — Basing (Accumulation):
    |ma_slope_20d| < 0.005 AND cross_count_60d ≥ 3
    → MA is flat, price oscillating around it
    → Often 3-12 months duration

  Stage 2 — Advancing (Mark-up) ← IDEAL BUY ZONE:
    price_vs_ma > 0 AND ma_slope_20d > 0.005
    → Price above rising MA, confirmed uptrend
    Sub-stages:
      Early Stage 2: ma_slope just turned positive in last 40 days
      Mid Stage 2: sustained uptrend, price 5-25% above MA
      Late Stage 2: price > 30% above MA (extended, higher risk)

  Stage 3 — Topping (Distribution):
    |ma_slope_20d| < 0.005 AND price_vs_ma is near 0 AND
    vol_on_down_days > vol_on_up_days (volume heavier on declines)

  Stage 4 — Declining (Mark-down) ← AVOID:
    price_vs_ma < 0 AND ma_slope_20d < -0.005
    → Price below declining MA

Scoring (0-100):
  Stage 2 early   → 100
  Stage 2 mid     → 85
  Stage 2 late    → 55  (extended, caution)
  Stage 1 late    → 60  (about to break out)
  Stage 1 early   → 25
  Stage 3         → 10
  Stage 4         → 0

Weinstein_composite = score
```

---

### 3.5. Dual Momentum Engine (Regime-Aware Momentum)

Two independent momentum tests. Based on Gary Antonacci's research.

```
Data needed: 12-month returns, benchmark returns, risk-free rate

Absolute Momentum (vs risk-free):
  ret_12m = (close_today / close_252d_ago) - 1
  risk_free_12m = trailing 12-month 3-month T-bill rate (US: FRED DGS3MO, KR: BOK base rate)
  abs_mom = ret_12m > risk_free_12m

Relative Momentum (vs benchmark):
  benchmark_ret_12m = benchmark index 12-month return
    US: S&P 500 total return
    KR: KOSPI total return (for KOSPI stocks), KOSDAQ (for KOSDAQ stocks)
  rel_mom = ret_12m > benchmark_ret_12m

Additional signal — Momentum breadth:
  ret_6m = 6-month return
  ret_3m = 3-month return
  all_positive = ret_12m > 0 AND ret_6m > 0 AND ret_3m > 0 (momentum across timeframes)

Scoring (0-100):
  abs_mom AND rel_mom AND all_positive → 100
  abs_mom AND rel_mom                  → 85
  abs_mom AND all_positive             → 70
  abs_mom only                         → 50
  rel_mom only (market bad, stock ok)  → 30
  neither                              → 0

  Modifier: +10 if ret_3m > ret_6m > ret_12m (accelerating momentum)
  Clamp [0, 100]

DualMomentum_composite = score
```

---

## 4. Deep Technical Analysis Engine

### 4.1. Pattern Detection Library

All patterns store: `pattern_name`, `confidence` (0-100), `pivot_price` (breakout trigger), `base_depth`, `base_length_days`.

#### Cup with Handle
```
Algorithm:
  1. Find highest high in lookback window (left lip)
  2. Find lowest low after left lip (cup bottom)
  3. cup_depth = (left_lip - cup_bottom) / left_lip
  4. Validate: 0.12 ≤ cup_depth ≤ 0.35 (0.50 max in bear mkt)
  5. Find recovery: price returns to within 5% of left_lip (right lip)
  6. cup_length = trading days from left lip to right lip
  7. Validate: cup_length ≥ 30 (roughly 6 weeks minimum)
  8. Handle detection: after right lip, look for 5-15 day pullback
  9. handle_depth = (right_lip_high - handle_low) / right_lip_high
  10. Validate: handle_depth ≤ 0.12 (max 15%)
  11. Handle should form in upper half of the cup range
  12. Volume: should dry up during handle (avg_vol_handle < 0.7 × avg_vol_50d)
  13. Pivot price = handle_high + $0.10 (or + 0.1%)
  14. Breakout confirmation: close > pivot AND volume > 1.5× avg_vol_50d

  Confidence scoring:
    Base: 60
    +10 if cup_depth 20-30% (ideal range)
    +10 if handle forms in upper 1/3 of cup
    +10 if volume dries up in handle
    +10 if cup length 7-20 weeks (ideal)
    -15 if cup_depth > 40% (too deep)
    -10 if handle too long (>25 days)
```

#### Double Bottom (W-Pattern)
```
Algorithm:
  1. Find first trough (T1): local minimum in lookback
  2. Find middle peak (P): highest point between T1 and next trough
  3. Find second trough (T2): next local minimum after P
  4. Validate: |T1 - T2| / T1 < 0.05 (troughs within 5% of each other)
  5. Bonus: T2 slightly undercuts T1 (shakeout) → stronger pattern
  6. base_depth = (P - min(T1, T2)) / P
  7. Validate: base_depth 15-35%
  8. Total length: ≥ 35 trading days (7 weeks)
  9. Pivot price = P (middle peak) + 0.1%
  10. Breakout: close > pivot on volume > 1.5× avg

  Confidence: 60 base
    +15 if T2 slightly undercuts T1 (by 1-3%)
    +10 if volume higher on right side rally than left side
    +5  if RS line making new high
```

#### Flat Base
```
Algorithm:
  1. Find a range where max_high - min_low < 15% of max_high
  2. Duration: ≥ 25 trading days (5 weeks)
  3. Should follow a prior advance of ≥ 20%
  4. Volume: generally declining during base (dry-up)
  5. Pivot price = max_high + 0.1%

  Confidence: 70 base (flat bases are reliable)
    +10 if preceded by 30%+ advance
    +10 if volume contracting throughout
    -10 if range > 12% (getting loose)
```

#### VCP (Volatility Contraction Pattern — Minervini)
```
Algorithm:
  1. Identify swing highs and lows in last 150 days
  2. Group into contractions: each peak-to-trough pair
  3. For each contraction measure:
     - depth_i = (swing_high_i - swing_low_i) / swing_high_i
     - volume_i = avg volume during contraction
  4. Require ≥ 2 contractions (prefer 3-4)
  5. Validate tightening: depth[i] < depth[i-1] for each successive
     Example: -25%, then -15%, then -8%, then -4%
  6. Validate volume dry-up: volume[i] < volume[i-1]
  7. Pivot line = high of most recent (tightest) contraction
  8. Breakout: close > pivot AND volume > 1.5× avg

  Confidence: 65 base
    +15 if 3+ contractions with strict tightening
    +10 if final contraction < 8% depth
    +10 if volume on final contraction < 50% of first
    +5  if the entire pattern < 100 days (compact)
```

#### High Tight Flag
```
Algorithm:
  1. Pole: stock advanced ≥ 100% in ≤ 40 trading days (8 weeks)
  2. Flag: correction of only 10-25% over 15-25 trading days (3-5 weeks)
  3. Volume: declines during flag formation
  4. Pivot price = flag high
  5. Very rare pattern — extremely bullish when valid

  Confidence: 80 base (rare but powerful)
    +10 if pole gain > 120%
    +10 if flag correction < 20%
    -20 if flag correction > 30% (pattern invalid)
```

#### Ascending Base
```
Algorithm:
  1. Identify 3 pullbacks during an advancing trend
  2. Each pullback: 10-20% correction from prior swing high
  3. Each pullback low is HIGHER than previous pullback low
  4. Stock generally follows 10-week (50-day) MA
  5. Pivot = high of third pullback

  Confidence: 70 base
    +10 if all 3 lows are clearly ascending
    +10 if each pullback finds support near 50-day MA
    +5  if volume decreases on each successive pullback
```

### 4.2. Advanced Technical Indicators

#### Accumulation/Distribution Rating
```
For each day in last 65 trading days (13 weeks):
  clv = ((close - low) - (high - close)) / (high - low)  // Close Location Value
  daily_ad = clv × volume

ad_sum_up = sum of positive daily_ad values
ad_sum_down = abs(sum of negative daily_ad values)
ad_ratio = ad_sum_up / (ad_sum_up + ad_sum_down)

Rating:
  ad_ratio > 0.80 → A (heavy accumulation, score: 95)
  0.60-0.80       → B (moderate accumulation, score: 75)
  0.40-0.60       → C (neutral, score: 50)
  0.20-0.40       → D (moderate distribution, score: 25)
  < 0.20          → E (heavy distribution, score: 5)
```

#### Up/Down Volume Ratio
```
up_vol_50d = sum of volume on days where close > prior close, last 50 days
dn_vol_50d = sum of volume on days where close < prior close, last 50 days
ud_ratio = up_vol_50d / dn_vol_50d

Interpretation:
  > 1.5 = strong accumulation (institutions buying)
  1.0-1.5 = neutral to positive
  < 1.0 = distribution (institutions selling)
```

#### Volume Dry-Up (Base Quality)
```
During detected base period:
  vol_during_base = avg daily volume during base
  vol_before_base = avg daily volume 50 days before base started
  dry_up_ratio = vol_during_base / vol_before_base

  < 0.50 = excellent dry-up (score: 95)
  0.50-0.65 = good dry-up (score: 75)
  0.65-0.80 = moderate (score: 50)
  > 0.80 = poor dry-up (score: 25)
```

#### RS Line Analysis
```
rs_line_daily = close / benchmark_close  (SPY for US, KOSPI for KR)
rs_line_52w_high = max(rs_line) over 252 days

rs_line_new_high = rs_line_today ≥ rs_line_52w_high

CRITICAL SIGNAL: RS line making new high BEFORE price makes new high
is extremely bullish (institutions accumulating ahead of breakout)

rs_line_leading = rs_line_new_high AND close < high_52w
```

#### Bollinger Band Squeeze
```
sma_20 = SMA(close, 20)
std_20 = STDDEV(close, 20)
upper = sma_20 + 2 × std_20
lower = sma_20 - 2 × std_20
bb_width = (upper - lower) / sma_20

bb_width_percentile = percentile of bb_width over last 252 days
squeeze = bb_width_percentile < 10  (bottom 10% of volatility)

Squeeze → volatility expansion imminent
Direction: confirmed by first decisive close outside bands after squeeze
```

#### Money Flow Index (Volume-Weighted RSI)
```
typical_price = (high + low + close) / 3
raw_money_flow = typical_price × volume

positive_flow_14d = sum(raw_money_flow) on days where TP > prior TP
negative_flow_14d = sum(raw_money_flow) on days where TP < prior TP

money_ratio = positive_flow_14d / negative_flow_14d
mfi = 100 - (100 / (1 + money_ratio))

> 80 = overbought  |  < 20 = oversold
MFI divergence vs price = key signal (bullish: price lower low, MFI higher low)
```

#### On-Balance Volume (OBV)
```
For each day:
  if close > prior_close: obv += volume
  if close < prior_close: obv -= volume
  if close == prior_close: obv unchanged

OBV trend (rising/falling) compared to price trend:
  OBV rising + price flat = accumulation (bullish)
  OBV falling + price flat = distribution (bearish)
  OBV confirms price trend = trend is healthy
```

### 4.3. Technical Composite Score

```
pattern_score = max(confidence) across all detected patterns, or 0 if none
ad_score = Accumulation/Distribution rating (0-100)
ud_score = normalize(ud_ratio) to 0-100
vol_dry_up = volume dry-up score (if in base)
rs_line_bonus = +15 if rs_line_leading, +10 if rs_line_new_high
bb_squeeze_bonus = +10 if squeeze detected (volatility expansion imminent)
mfi_score = normalize MFI to 0-100 (50 = neutral)

technical_composite = (
    0.30 × pattern_score +
    0.25 × ad_score +
    0.15 × ud_score +
    0.10 × mfi_score +
    0.10 × vol_dry_up +
    0.10 × (bb_squeeze_bonus normalized)
) + rs_line_bonus

Clamp [0, 100]
```

### 4.4. Multi-Timeframe Analysis

```
Three timeframes: Daily, Weekly, Monthly

For each timeframe:
  trend_up = close > SMA(close, 10-period)  (10-day, 10-week, 10-month)
  ma_rising = SMA slope > 0

  Timeframe signal:
    trend_up AND ma_rising → BULLISH
    else → NOT_BULLISH

Alignment:
  All 3 BULLISH    → alignment_bonus = +15
  2/3 BULLISH      → alignment_bonus = +8
  1/3 BULLISH      → alignment_bonus = 0
  0/3 BULLISH      → alignment_bonus = -15

Applied as modifier to technical_composite.
```

### 4.5. Korea-Specific Technical Adjustments

```
1. Daily price limit (±30% on KOSPI/KOSDAQ):
   - Limit-up days: if close = high = prior_close × 1.30
     → Don't count as volume confirmation (artificial ceiling)
     → Flag as "limit hit" in pattern detection
   - Limit-down days: can create false double-bottoms
     → Require extra confirmation day after limit-down

2. Foreign flow as technical signal:
   foreign_net_buy_streak = consecutive days of net foreign buying
   foreign_flow_pct = foreign_net_buy / avg_daily_volume

   streak ≥ 5 AND flow_pct > 10% → strong institutional signal (+10 technical bonus)
   streak ≥ 10 → very strong (+15)

3. Tick size differences:
   Korean stocks have different tick sizes by price level
   → Use percentage-based thresholds, not absolute price
```

---

## 5. Consensus Scoring — The Core Innovation

### How It Works

```
For each instrument, 5 strategy engines run independently:
  canslim_score     (0-100, from Section 3.1)
  piotroski_score   (0-100, from Section 3.2)
  minervini_score   (0-100, from Section 3.3)
  weinstein_score   (0-100, from Section 3.4)
  dual_mom_score    (0-100, from Section 3.5)

Step 1: Count strategies where instrument scores in top tier (≥ 70):
  strategy_pass_count = count of scores ≥ 70 (out of 5)

Step 2: Conviction level:
  5/5 → DIAMOND   (all strategies agree — ultra-high conviction)
  4/5 → GOLD      (4 strategies agree — high conviction)
  3/5 → SILVER    (3 strategies agree — moderate conviction)
  2/5 → BRONZE    (2 strategies agree — low conviction)
  ≤1  → UNRANKED

Step 3: Consensus composite (weighted):
  consensus_composite = (
      0.25 × canslim_score +     // Growth + institutional
      0.20 × piotroski_score +   // Financial health
      0.20 × minervini_score +   // Trend template
      0.20 × weinstein_score +   // Cycle phase
      0.15 × dual_mom_score      // Momentum confirmation
  )

Step 4: Technical overlay:
  final_score = consensus_composite × 0.75 + technical_composite × 0.25
  (technical analysis from Section 4 contributes 25% of final score)

Step 5: Regime gate (from CANSLIM M factor):
  If MARKET_IN_CORRECTION:
    All conviction levels capped at SILVER
    final_score annotated with regime_warning = true
    Banner: "Market in correction — reduce exposure"
```

### Why This Is Superior

- A **DIAMOND** stock has: accelerating earnings (C), solid balance sheet (P), perfect trend (M), early Stage 2 (W), and outperforming everything (D). False positive rate is near zero.
- A stock with CANSLIM 95 but Piotroski 2/9 gets caught — it's a growth trap with weak financials. **CANSLIM alone would miss this.**
- A stock with Piotroski 9/9 but Weinstein Stage 4 gets caught — it's financially strong but in a downtrend. **Value alone would miss this.**
- Each strategy acts as an independent error-checker on the others.

---

## 6. ETF Scoring

ETFs cannot use CANSLIM/Piotroski directly. Hybrid approach:

```
Exclude: leveraged, inverse, derivative-heavy ETFs.

1. Constituent Consensus Score (0-100):
   For each ETF constituent with a stock score:
     weighted_consensus = Σ(weight × constituent_final_score) / Σ(weights)
     pct_diamond_gold = % of constituents at DIAMOND or GOLD conviction

2. ETF Momentum (0-100):
   rs_vs_sector = ETF's RS rating ranked among sector peers
   Scoring: same as L factor mapping

3. Fund Flow (0-100):
   aum_change_30d relative: > 10% → 90, > 5% → 70, > 0% → 50, else → 20

4. Cost (0-100):
   expense < 0.10% → 95, < 0.25% → 80, < 0.50% → 60, < 1.00% → 40, else → 15

5. Liquidity (0-100):
   aum > $1B → 90, > $500M → 75, > $100M → 55, > $50M → 35, else → 15

ETF composite = 0.35×constituent_consensus + 0.25×momentum + 0.15×flow + 0.15×cost + 0.10×liquidity
```

---

## 7. Risk Management

### Stop-Loss Monitor
```
CANSLIM standard: 7-8% stop-loss from buy point.
Reference: price when stock first achieved current GOLD+ conviction.

stop_7pct = entry_ref × 0.93
stop_10pct = entry_ref × 0.90

current ≤ stop_7pct → CRITICAL alert
current within 2% of stop → WARNING alert
```

### Position Sizing (display-only)
```
atr_14d = 14-day Average True Range
max_risk_per_position = 1% of portfolio
position_shares = (portfolio_value × 0.01) / (2 × atr_14d)
max_position_pct = 5% per stock (4% for KOSDAQ)
max_positions = 10-15
```

### Concentration Warnings
```
- >3 of top 10 in same sector → SECTOR_CONCENTRATION warning
- >5 of top 10 on same exchange → EXCHANGE_CONCENTRATION warning
- Top pick has any strategy score < 50 → WEAK_FACTOR warning
- Regime under pressure + portfolio 80%+ invested → EXPOSURE warning
```

---

## 8. Database Schema (Key Tables)

```
instruments          — ticker, market, exchange, asset_type, sector, industry_group,
                       shares_outstanding, float_shares, corp_code (KR),
                       is_chaebol_cross (KR), is_leveraged/is_inverse (ETF)

prices               — TimescaleDB hypertable: instrument_id, trade_date, OHLCV,
                       avg_volume_50d (pre-computed)

fundamentals_quarterly — instrument_id, fiscal_year, fiscal_quarter,
                         eps, revenue, eps_yoy_growth, revenue_yoy_growth

fundamentals_annual  — instrument_id, fiscal_year, eps, revenue, net_income,
                       total_assets, operating_cashflow, lt_debt,
                       current_assets, current_liabilities,
                       shares_outstanding, gross_profit
                       (ALL fields needed for Piotroski F-Score)

institutional        — instrument_id, report_date, num_owners, institutional_pct,
                       qoq_change, fund_quality (US), foreign_pct,
                       foreign_net_buy_30d, institutional_net_buy_30d (KR, from KIS),
                       individual_net_buy_30d (KR, from KIS), is_buyback

strategy_scores      — instrument_id, score_date,
                       canslim_score, canslim_detail JSONB,
                       piotroski_score, piotroski_detail JSONB (F1-F9),
                       minervini_score, minervini_detail JSONB (T1-T8),
                       weinstein_score, weinstein_stage,
                       dual_mom_score, dual_mom_detail JSONB,
                       technical_composite, patterns JSONB

consensus_scores     — instrument_id, score_date,
                       consensus_composite, conviction_level,
                       strategy_pass_count, final_score,
                       regime_state, regime_warning

market_regime        — market, effective_date, state, prior_state,
                       trigger_reason, distribution_day_count,
                       drawdown_from_high, index_vs_50dma, index_vs_200dma

etf_constituents     — etf_id, constituent_id, weight, as_of_date
etf_scores           — instrument_id, score_date, constituent_consensus,
                       momentum, flow, cost, liquidity, composite

alerts               — instrument_id, alert_type, severity, detail,
                       threshold_value, actual_value, created_at
scoring_snapshots    — snapshot_date, market, asset_type, rankings_json, config_hash
data_freshness       — source_name, market, last_success, last_failure, staleness_hours
```

---

## 9. API Endpoints

### `GET /api/v1/rankings`
**Params:** `market=US|KR`, `asset_type=stock|etf`, `conviction=DIAMOND|GOLD|SILVER|BRONZE`, `limit`, `offset`

Returns: regime state, freshness, ranked items with:
- All 5 strategy scores + details
- Conviction level (DIAMOND/GOLD/SILVER/BRONZE)
- Technical composite + detected patterns
- Final consensus score
- Risk: stop-loss, position size, active alerts

### `GET /api/v1/instruments/{ticker}?market=US|KR`
Returns: profile, all 5 strategy breakdowns (CANSLIM per-factor, Piotroski F1-F9, Minervini T1-T8, Weinstein stage, Dual Momentum abs/rel), technical patterns, indicators, 30-day score trail, risk data.

### `GET /api/v1/strategies/{name}/rankings?market=US|KR`
Individual strategy leaderboard (e.g., `/strategies/canslim/rankings`, `/strategies/piotroski/rankings`).

### `POST /api/v1/filters/query`
Filters on any strategy score, conviction level, sector, exchange, specific factors (e.g., piotroski_f_score ≥ 7, rs_rating ≥ 80), technical pattern type.

### `GET /api/v1/market-regime?market=US|KR`
Current state, history, distribution day count, drawdown, index MA positions.

### `GET /api/v1/snapshots/latest?market=US&asset_type=stock`
Frozen point-in-time rankings with config hash for reproducibility.

### `GET /api/v1/alerts`
Types: `STOP_LOSS`, `REGIME_CHANGE`, `EARNINGS_DECEL`, `RS_BREAKDOWN`, `VOLUME_SURGE`, `PIOTROSKI_DROP`, `STAGE_CHANGE`, `SECTOR_CONCENTRATION`, `DATA_SOURCE_DEGRADED`

---

## 10. Data Pipeline Schedule

| Task | Source | Market | Schedule | Lag |
|------|--------|--------|----------|-----|
| Prices (EOD) | yfinance | US | Daily 6 PM ET | <1 min |
| Prices (EOD + real-time) | KIS Developers (mojito) | KR | Daily 4:00 PM KST / WebSocket live | Real-time |
| Investor flows (foreign/inst/indiv) | KIS Developers | KR | Daily after close | <1 hour |
| Quarterly financials | SEC EDGAR XBRL (edgartools) | US | Daily scan for new 10-Q | 40-45 day |
| Annual financials (full: IS+BS+CF) | SEC EDGAR XBRL (edgartools) | US | Daily scan for new 10-K | 60-90 day |
| Quarterly financials | OpenDART (OpenDartReader) | KR | Daily scan for filings | 45 day |
| Annual financials (full) | OpenDART (OpenDartReader) | KR | Daily scan for filings | 45 day |
| Institutional (13F) | SEC EDGAR bulk | US | Quarterly (Feb/May/Aug/Nov 15) | 45 day |
| Risk-free rate | FRED (fredapi) / BOK | Both | Weekly | 0 |
| Technical indicators | Computed | Both | Daily post-prices | 0 |
| Pattern detection | Computed | Both | Daily post-prices | 0 |
| RS ratings (full-market batch) | Computed | Both | Nightly | 0 |
| All 5 strategy scores | Computed | Both | Daily after ingestion | 0 |
| Consensus scores | Computed | Both | Daily after strategies | 0 |
| Snapshots | Computed | Both | Daily after consensus | 0 |

**KIS Developers real-time mode (optional):** When enabled, the KR price ingestor maintains a WebSocket connection during market hours (9:00 AM - 3:30 PM KST) for live quotes. Provisional intraday rankings can be computed. After market close, official EOD data is fetched via REST and used for definitive daily scoring.

---

## 11. Step-by-Step Implementation Guide

Each step has a clear deliverable, test checkpoint, and dependencies. Complete each step fully before moving to the next. Steps within a phase can sometimes be parallelized where noted.

---

### PHASE 0: Dev Environment Bootstrap

Choose ONE infrastructure path. Cloud-managed is recommended.

#### Step 0.1 — Install `uv`
- [ ] Install `uv` on Windows
- [ ] Verify `uv --version`
- [ ] Add `.python-version` (Python 3.12+)
- **Test:** `uv --version` succeeds. Python 3.12 is selected for the backend project.

#### Step 0.2 — Provision Cloud Infrastructure (Cloud Path)
- [ ] Create Neon account → Create project → Enable TimescaleDB extension
- [ ] Create Upstash account → Create Redis database
- [ ] Copy connection strings to `.env`
- [ ] Verify connectivity: `psql` to Neon, `redis-cli` to Upstash
- **Test:** `CREATE EXTENSION IF NOT EXISTS timescaledb;` succeeds on Neon. Celery can ping Upstash broker.

#### Step 0.2-ALT — Install Native Infrastructure (Native Path)
- [ ] Install native PostgreSQL 16 + TimescaleDB on Windows
- [ ] Install Memurai as local Redis-compatible service
- [ ] Create local user/database, verify connectivity
- **Test:** `CREATE EXTENSION timescaledb;` succeeds locally. Celery can ping Memurai broker.

#### Step 0.3 — Sync Dependencies With `uv`
- [ ] Use `backend/pyproject.toml` as the project root for Python dependencies
- [ ] Generate `uv.lock`
- **Test:** `uv sync --project backend` completes successfully on Windows.

#### Step 0.4 — Configure `.env` And Verify
- [ ] Copy `.env.example` to `.env`
- [ ] Fill provider keys and infrastructure connection strings
- [ ] Verify database connectivity from Python
- **Test:** `python -c "from sqlalchemy import create_engine; ..."` connects successfully.

#### Step 0.5 — Start Local Processes
- [ ] Add `Procfile` with `api`, `worker`, and `beat`
- [ ] Add `scripts/dev.ps1` convenience wrapper and `scripts/stop-dev.ps1`
- [ ] Add individual `scripts/start-api.ps1`, `scripts/start-worker.ps1`, `scripts/start-beat.ps1`
- [ ] On native Windows path: standardize worker command on `--pool=solo`
- **Test:** API starts. `GET /health` returns 200.

**PHASE 0 CHECKPOINT:** Dev environment is fully runnable. Database and Redis are accessible. `uv sync` works.

---

### PHASE 1: Foundation + Data Infrastructure

#### Step 1.1 — Project Scaffolding
- [ ] Init git repo
- [ ] Create FastAPI app skeleton with `pyproject.toml`, dependencies
- [ ] Set up Alembic for migrations
- [ ] Create `.env.example` with all config keys
- [ ] Create project directory structure (Section 2)
- [ ] Add `Procfile` for local process management
- **Test:** `uvicorn app.main:app --app-dir backend` starts the API. `GET /health` returns 200.

#### Step 1.2 — Database Schema
- [ ] Write Alembic migration for all tables (Section 8): instruments, prices, fundamentals_quarterly, fundamentals_annual, institutional, strategy_scores, consensus_scores, market_regime, etf_constituents, etf_scores, alerts, scoring_snapshots, data_freshness
- [ ] Enable TimescaleDB hypertable on `prices`
- [ ] Create indexes on common query patterns
- **Test:** `alembic upgrade head` succeeds. All tables exist. Insert/query sample row in each table.

#### Step 1.3 — US Instrument + Price Ingestion
- [ ] Build `us_price.py` ingestor using `yfinance`
- [ ] Implement FMP fallback logic (auto-switch if yfinance error rate >10%)
- [ ] Fetch S&P 500 + NASDAQ 100 instrument list → populate `instruments`
- [ ] Fetch 2 years historical daily OHLCV → populate `prices` hypertable
- [ ] Compute and store `avg_volume_50d` rolling average
- [ ] Update `data_freshness` on success/failure
- **Test:** Query `SELECT count(*) FROM prices WHERE instrument_id = (AAPL)` returns ~500 rows. Spot-check AAPL close price for a known date matches Yahoo Finance.

#### Step 1.4 — KR Instrument + Price Ingestion (KIS Developers)
- [ ] Register KIS Developers account, get APP_KEY + APP_SECRET
- [ ] Build `kr_price.py` ingestor using `mojito` library
- [ ] Fetch KOSPI + KOSDAQ instrument lists via `FinanceDataReader` → populate `instruments`
- [ ] Fetch 2 years historical OHLCV via KIS REST API → populate `prices`
- [ ] (Optional) Set up WebSocket connection for real-time quotes during market hours
- [ ] Update `data_freshness`
- **Test:** Query Samsung Electronics (005930) prices. Verify count and spot-check a known close. Verify KIS API auth token refresh works.

#### Step 1.5 — Basic Technical Indicators
- [ ] Compute SMAs (21, 50, 150, 200-day) for all instruments
- [ ] Compute 52-week high/low per instrument
- [ ] Compute ATR (14-day)
- [ ] Compute IBD RS Rating (batch: rank ALL instruments per market) → store in `strategy_scores` or dedicated column
- [ ] Build `indicators.py` service with reusable computation functions
- **Test:** Verify SMA(50) for AAPL matches TradingView. Verify RS rating produces 1-99 distribution. Verify top RS stocks are known momentum leaders.

#### Step 1.6 — Market Regime State Machine (M Factor)
- [ ] Build `state_machine.py` with 3 states: CONFIRMED_UPTREND, UPTREND_UNDER_PRESSURE, MARKET_IN_CORRECTION
- [ ] Implement distribution day counter (rolling 25-session)
- [ ] Implement drawdown-from-high detection (10% → correction, 20% → bear)
- [ ] Implement follow-through day detection
- [ ] Implement death cross / golden cross detection
- [ ] Run historical regime detection on loaded price data → populate `market_regime`
- **Test:** Replay 2022 bear market data → regime should detect MARKET_IN_CORRECTION. Replay 2023 recovery → should detect follow-through day + CONFIRMED_UPTREND. Verify distribution day count for known dates.

**PHASE 1 CHECKPOINT:** Prices flowing for both markets, indicators computing correctly, regime state machine producing sensible historical states.

---

### PHASE 2: Fundamental Data + CANSLIM & Piotroski Engines

#### Step 2.1 — US Fundamental Ingestion (SEC EDGAR)
- [ ] Build `us_fundamental.py` using `edgartools`
- [ ] Ingest quarterly financials (10-Q): EPS, revenue, net income → `fundamentals_quarterly`
- [ ] Ingest annual financials (10-K): full income statement + balance sheet + cash flow → `fundamentals_annual`
- [ ] Pre-compute `eps_yoy_growth`, `revenue_yoy_growth` on ingestion
- [ ] Handle fiscal year variations (not all companies are Jan-Dec)
- **Test:** Query AAPL quarterly EPS for last 8 quarters. Compare to known values. Verify Piotroski fields present: total_assets, operating_cashflow, lt_debt, current_assets, current_liabilities, gross_profit.

#### Step 2.2 — KR Fundamental Ingestion (OpenDART)
- [ ] Register OpenDART API key
- [ ] Build `kr_fundamental.py` using `OpenDartReader`
- [ ] Ingest quarterly financials via `fnlttSinglAcnt` → `fundamentals_quarterly`
- [ ] Ingest annual financials (full: IS+BS+CF) → `fundamentals_annual`
- [ ] Handle K-IFRS field name mapping (매출액 → revenue, 당기순이익 → net_income, etc.)
- [ ] Rate-limit to OpenDART limits (1000 req/day)
- **Test:** Query Samsung Electronics (005930) quarterly EPS. Compare to published earnings. Verify balance sheet fields populated.

#### Step 2.3 — Korea Adaptations
- [ ] Build `sector_normalizer.py`: semiconductor 2Q avg, shipbuilding 3Q avg thresholds
- [ ] Build `chaebol_filter.py`: maintain group membership mapping, flag cross-holdings
- [ ] Verify normalization on Samsung (semi) vs Hyundai Heavy (shipbuilding)
- **Test:** Samsung's C-score uses 2Q avg. A chaebol cross-holding instrument gets is_chaebol_cross = True.

#### Step 2.4 — CANSLIM Engine (C-A-N-S-L-I)
- [ ] Build `c_earnings.py` — quarterly EPS growth scoring (Section 3.1 C)
- [ ] Build `a_annual.py` — annual EPS CAGR scoring (Section 3.1 A)
- [ ] Build `n_new_highs.py` — proximity + base detection scoring (Section 3.1 N)
- [ ] Build `s_supply.py` — float ratio + volume surge scoring (Section 3.1 S)
- [ ] Build `l_leader.py` — RS rating mapping (Section 3.1 L)
- [ ] Build `i_institutional.py` — ownership sweet spot scoring (Section 3.1 I)
- [ ] Build `engine.py` — orchestrate all 6 factors + M gate → CANSLIM composite
- [ ] Run scoring on all US + KR instruments → store in `strategy_scores`
- **Test:** Score NVDA (known growth leader) — expect high C, A, L scores. Score a declining stock — expect low scores. Manually verify 3 stocks' CANSLIM breakdowns against hand calculations.

#### Step 2.5 — Piotroski F-Score Engine
- [ ] Build `engine.py` with 9 binary criteria (Section 3.2)
- [ ] F1: ROA > 0, F2: CFO > 0, F3: ΔROA > 0, F4: CFO > NI
- [ ] F5: ΔLeverage < 0, F6: ΔCurrent Ratio > 0, F7: No dilution
- [ ] F8: ΔGross Margin > 0, F9: ΔAsset Turnover > 0
- [ ] Normalize F-score (0-9) to 0-100 scale
- [ ] Run on all instruments → store in `strategy_scores`
- **Test:** Score a financially strong company (e.g., AAPL) → expect F-score 7-9. Score a struggling company → expect 0-3. Verify each of the 9 criteria individually with hand calculation.

#### Step 2.6 — Early Backtesting Validation
- [ ] Run CANSLIM + Piotroski on 6 months of historical data
- [ ] Track forward 3-month returns for top-scoring vs bottom-scoring stocks
- [ ] Verify that high-scoring stocks have meaningfully better outcomes
- **Test:** Basic signal validation — catch formula errors early before building remaining engines.

**PHASE 2 CHECKPOINT:** Two strategies producing scores for all instruments. Manually verify 5 US + 5 KR stocks against hand calculations. Check that CANSLIM and Piotroski identify *different* top stocks (they should, since they're orthogonal). Early backtest shows positive signal.

---

### PHASE 3: Remaining Strategies + Deep Technical Analysis

#### Step 3.1 — Minervini Trend Template Engine
- [ ] Build `engine.py` with 8 criteria (Section 3.3)
- [ ] T1-T5: MA position checks, T6-T7: price range checks, T8: RS ≥ 70
- [ ] Score: count passing / 8 → normalize to 0-100
- [ ] Run on all instruments → store in `strategy_scores`
- **Test:** A stock in a clear uptrend (price > all MAs, MAs stacked) → 8/8 = 100. A stock in decline → 0-2/8. Verify T1-T8 individually.

#### Step 3.2 — Weinstein Stage Analysis Engine
- [ ] Build `engine.py` with stage detection (Section 3.4)
- [ ] Compute 150-day MA slope, price-vs-MA, cross count, volume patterns
- [ ] Classify into Stage 1/2/3/4 with sub-stages (early/mid/late Stage 2)
- [ ] Score: Stage 2 early = 100, Stage 4 = 0
- [ ] Run on all instruments → store
- **Test:** A stock that bottomed 6 months ago and is now rising above 150MA → Stage 2. A stock that peaked and is below declining 150MA → Stage 4.

#### Step 3.3 — Dual Momentum Engine
- [ ] Ingest risk-free rate: FRED DGS3MO (US) via `fredapi`, BOK base rate (KR)
- [ ] Build `engine.py` (Section 3.5)
- [ ] Compute absolute momentum (ret_12m > risk-free), relative momentum (ret_12m > benchmark)
- [ ] Score: both pass + all timeframes positive → 100, neither → 0
- [ ] Run on all instruments → store
- **Test:** A stock up 50% in 12m while S&P up 15% → abs_mom TRUE, rel_mom TRUE → high score. A stock down 10% → both FALSE → 0.

#### Step 3.4 — Pattern Detection Library
- [ ] Build `pattern_detector.py` with detection algorithms for:
  - [ ] Cup with Handle (Section 4.1)
  - [ ] Double Bottom / W-Pattern
  - [ ] Flat Base
  - [ ] VCP (Volatility Contraction Pattern)
  - [ ] High Tight Flag
  - [ ] Ascending Base
- [ ] Each returns: pattern_name, confidence (0-100), pivot_price, base_depth, base_length
- [ ] Store detected patterns in `strategy_scores.patterns` JSONB
- **Test:** Load historical NVDA data (known cup-with-handle in 2023). Verify pattern detected with reasonable confidence. Test each pattern type with synthetic/historical data.

#### Step 3.5 — Advanced Technical Indicators
- [ ] Build `indicators.py` with:
  - [ ] Accumulation/Distribution Rating (13-week, A-E scale)
  - [ ] Up/Down Volume Ratio (50-day)
  - [ ] Volume Dry-Up score (base quality)
  - [ ] RS Line analysis (new highs, leading indicator detection)
  - [ ] Bollinger Band Squeeze detection
  - [ ] Money Flow Index (14-day)
  - [ ] On-Balance Volume + trend detection
- **Test:** Verify A/D rating for a known accumulation stock. Verify BB squeeze triggers before a known volatility expansion.

#### Step 3.6 — Technical Composite + Multi-Timeframe
- [ ] Build `multi_timeframe.py`: daily/weekly/monthly alignment scoring
- [ ] Build technical composite aggregation (Section 4.3): pattern + indicators → single 0-100 score
- [ ] Store `technical_composite` in `strategy_scores`
- **Test:** A stock with a detected pattern + good A/D + multi-TF alignment → high composite. A stock with no patterns + distribution → low.

**PHASE 3 CHECKPOINT:** All 5 strategies + technical engine producing scores. Run `strategy_scores` stats: each strategy should have a reasonable distribution (not all 0s or all 100s). Verify that the strategies rank stocks differently (low correlation between rankings).

---

### PHASE 4: Consensus Engine + Institutional Data

#### Step 4.1 — US Institutional Ingestion (13F)
- [ ] Build `us_institutional.py` to parse SEC EDGAR 13F bulk data
- [ ] Extract: num_owners, institutional_pct, qoq_change per instrument
- [ ] Compute fund_quality_score (avg performance rank of top 10 holders)
- [ ] Populate `institutional` table
- **Test:** Verify AAPL institutional ownership % matches known value (~60%). Verify qoq_change computation.

#### Step 4.2 — KR Investor Flow Ingestion (KIS Developers)
- [ ] Build `kr_investor_flow.py` using KIS investor category API
- [ ] Fetch daily foreign/institutional/individual net buy/sell per instrument
- [ ] Compute 30-day rolling sums → populate `institutional` table
- [ ] Integrate with chaebol filter
- **Test:** Verify Samsung foreign/institutional flow fields are internally consistent and spot-check them against available public KIS or exchange reference data. Verify daily investor breakdown sums correctly.

#### Step 4.3 — Consensus Scoring Engine
- [ ] Build `consensus.py` (Section 5)
- [ ] Read all 5 strategy scores per instrument
- [ ] Count strategies ≥ 70 → conviction level (DIAMOND/GOLD/SILVER/BRONZE)
- [ ] Compute weighted consensus composite
- [ ] Apply technical overlay (25% weight)
- [ ] Apply regime gate (cap at SILVER during correction)
- [ ] Populate `consensus_scores` table
- **Test:** Manually construct a stock with all 5 scores ≥ 70 → DIAMOND. Construct one with only 2 → BRONZE. Verify regime capping works. Verify final_score computation.

#### Step 4.4 — Snapshot Generation
- [ ] Build snapshot task: freeze `consensus_scores` + rankings for a given date/market/asset_type
- [ ] Store in `scoring_snapshots` with config_hash for reproducibility
- **Test:** Generate snapshot, then re-run scoring on same data → verify identical rankings_json.

**PHASE 4 CHECKPOINT:** Full consensus pipeline producing DIAMOND/GOLD/SILVER/BRONZE rankings for both markets. Check: DIAMOND stocks should be rare (0-5 per market). GOLD more common (10-30). Distribution should feel right.

---

### PHASE 5: API Layer + Risk Management

#### Step 5.1 — Rankings Endpoint
- [ ] `GET /api/v1/rankings` with market, asset_type, conviction, limit, offset params
- [ ] Include regime state, freshness, all 5 strategy scores, conviction, technical, risk data
- [ ] Pagination support
- [ ] Redis cache for rankings responses (TTL: 1 hour, invalidate on new scoring run)
- **Test:** `curl /rankings?market=US&conviction=DIAMOND` returns 0-5 stocks. `conviction=GOLD` returns more.

#### Step 5.2 — Instruments Endpoint
- [ ] `GET /api/v1/instruments/{ticker}?market=US`
- [ ] Full profile + all 5 strategy breakdowns + technical patterns + 30-day trail + risk
- **Test:** `curl /instruments/AAPL?market=US` returns complete breakdown. Verify Piotroski F1-F9 detail, Minervini T1-T8 checklist.

#### Step 5.3 — Strategy-Specific + Filter Endpoints
- [ ] `GET /api/v1/strategies/{name}/rankings` for individual strategy leaderboards
- [ ] `POST /api/v1/filters/query` with strategy-specific filter params
- **Test:** `/strategies/piotroski/rankings` returns stocks sorted by F-score. Filter by `piotroski_f_score >= 8` returns subset.

#### Step 5.4 — Regime + Snapshots + Alerts Endpoints
- [ ] `GET /api/v1/market-regime`
- [ ] `GET /api/v1/snapshots/latest`
- [ ] `GET /api/v1/alerts`
- **Test:** Regime endpoint shows current state with history. Snapshot returns frozen data.

#### Step 5.5 — Risk Management
- [ ] Build `stop_loss.py` monitor: 7% stop-loss alerts from entry reference
- [ ] Build `position_sizer.py`: ATR-based sizing guidance
- [ ] Build concentration checker: sector/exchange warnings
- [ ] Generate alerts and store in `alerts` table
- **Test:** Simulate a stock dropping 8% from entry → CRITICAL alert generated. Verify position sizing calculation.

#### Step 5.6 — API Authentication
- [ ] Add API key authentication middleware
- [ ] Rate limiting per API key
- **Test:** Unauthenticated requests return 401. Valid API key returns data.

**PHASE 5 CHECKPOINT:** Full API functional. Run complete flow: ingest → score → rank → serve via API. All endpoints return correct data. Alerts fire on simulated risk events.

---

### PHASE 6: ETF Scoring + Frontend

#### Step 6.1 — ETF Ingestion + Scoring
- [ ] Ingest ETF constituent mappings (US + KR)
- [ ] Build `etf_scorer.py` (Section 6): constituent consensus, momentum, flow, cost, liquidity
- [ ] Exclude leveraged/inverse ETFs
- [ ] Populate `etf_scores`
- **Test:** SPY ETF gets a score reflecting its constituents' average. A leveraged ETF is excluded.

#### Step 6.2 — Frontend: Consensus Leaderboard
- [ ] Set up Next.js project with Tailwind + shadcn/ui
- [ ] Build main rankings table with conviction badges (DIAMOND/GOLD/SILVER/BRONZE)
- [ ] Market selector (US/KR), asset type toggle, conviction filter
- [ ] Regime banner at top (color-coded: green/yellow/red)
- [ ] Data freshness indicators
- **Test:** Load page → see ranked stocks with correct conviction levels. Filter by DIAMOND shows only top picks.

#### Step 6.3 — Frontend: Instrument Detail Page
- [ ] Strategy radar/spider chart (5 axes: CANSLIM, Piotroski, Minervini, Weinstein, Dual Mom)
- [ ] CANSLIM sub-factor breakdown (C/A/N/S/L/I bars)
- [ ] Piotroski F1-F9 checklist (green/red checkmarks)
- [ ] Minervini T1-T8 checklist
- [ ] Weinstein stage badge + stage history
- [ ] Score history chart (30-day trail)
- **Test:** Click NVDA → see all 5 strategy breakdowns. Radar chart renders correctly.

#### Step 6.4 — Frontend: Price Chart + Pattern Overlay
- [ ] Integrate Lightweight Charts (TradingView)
- [ ] Overlay detected patterns (cup-with-handle drawn, pivot line, etc.)
- [ ] Show SMA lines (50, 150, 200)
- [ ] Volume bars with accumulation/distribution coloring
- [ ] RS Line secondary chart
- **Test:** Chart loads with correct price data. Cup-with-handle pattern visible as overlay on a stock that has one.

#### Step 6.5 — Frontend: Filters, Alerts, Settings
- [ ] Advanced filter builder (strategy scores, sectors, patterns, etc.)
- [ ] Alert feed page (sortable by severity, type)
- [ ] Market regime detail page
- **Test:** Apply filter → results update. Alert list shows recent alerts.

**PHASE 6 CHECKPOINT:** Fully functional web application. End-to-end: open browser → see leaderboard → click stock → see full analysis with chart + patterns + all 5 strategies.

---

### PHASE 7: Validation + Polish

#### Step 7.1 — Full Backtesting Framework
- [ ] Build replay engine: load historical data, run scoring as-of each past date
- [ ] Track which stocks entered DIAMOND/GOLD tier and their forward returns (1/3/6/12 month)
- [ ] Compare: DIAMOND vs GOLD vs CANSLIM-only vs S&P 500/KOSPI benchmark
- [ ] Compute: hit rate, avg return, max drawdown, Sharpe-like ratio
- **Test:** Key hypothesis: DIAMOND consensus picks outperform any single strategy alone on risk-adjusted basis.

#### Step 7.2 — Full Test Suite
- [ ] Unit tests per strategy (boundary conditions, edge cases)
- [ ] Pattern detection tests (historical data with known patterns)
- [ ] Consensus logic tests (strategy agreement → correct conviction)
- [ ] Regime gate tests (correction → caps conviction)
- [ ] API integration tests
- **Test:** `pytest` passes 100%. Coverage > 80% on scoring engines.

#### Step 7.3 — Data Integrity Monitoring
- [ ] Daily task: check for missing prices, stale fundamentals
- [ ] RS distribution check (should be ~uniform 1-99)
- [ ] Piotroski distribution (should be roughly normal, centered ~5)
- [ ] Snapshot reproducibility: re-run → identical output
- **Test:** Monitoring alerts fire when test data is intentionally made stale.

#### Step 7.4 — Korea-Specific Verification
- [ ] Verify chaebol filter catches Samsung-to-Samsung cross-holdings
- [ ] Verify sector normalization adjusts semiconductor thresholds
- [ ] Verify KIS investor flow data is stable, internally consistent, and reasonable versus public market reference totals
- [ ] Verify price limit (±30%) handling in pattern detection
- **Test:** Side-by-side comparison with published Korean financial data.

**PHASE 7 CHECKPOINT:** Platform validated. Backtesting shows meaningful signal. All tests pass. Data integrity clean.

---

## 12. Future Considerations

These items are not in the current implementation scope but should be addressed as the platform matures:

1. **CI/CD Pipeline** — GitHub Actions for automated testing, linting, and deployment on push.
2. **Structured Logging & Observability** — Integrate structured logging (e.g., `structlog`) and consider metrics collection for pipeline health monitoring.
3. **WebSocket/SSE for Frontend** — Replace TanStack Query polling with WebSocket or Server-Sent Events for real-time regime change notifications and alert delivery.
4. **Bulk Load Estimation** — Initial historical data load for ~7000 instruments is a multi-hour operation. Document rate-limit handling, batch sizing, and expected duration.
5. **Multi-User Support** — If deployed beyond personal use, add user accounts, watchlists, and personalized alert preferences.
6. **Neon Storage Monitoring** — Track database size growth. At ~500 trading days/year × 7000 instruments × ~200 bytes, annual growth is ~700MB. Plan storage tier upgrades accordingly.
