# Consensus Platform — Master Remaster Plan

## Self-Critique of Previous Version

Before the final plan, here are weaknesses in the prior draft that this version fixes:

1. **CORS fix was in Phase 8** — should be Phase 1. Auth fails because CORS is wrong. Fix it first.
2. **Weinstein gate was wrong** — capping at GOLD means a Stage 1 stock could still be GOLD. Correct gate: cap at SILVER (not GOLD) if not Stage 2.
3. **WebSocket is a mock** — the streaming endpoint returns simulated quotes. It's unused by any real client. Better to remove it than "fix" it to avoid wasted effort.
4. **Missing rollback plan** — Alembic downgrades need to be tested locally before running in production.
5. **Phase ordering was off** — conviction color fix (Phase 4) is a 15-min change that unblocks visual debugging; it should happen right after triage.
6. **No "done" criteria per step** — added explicit verification for each step.
7. **Korea strategy unclear** — Piotroski and Minervini apply to KR market but CANSLIM was designed for US growth stocks. Plan now clarifies KR uses Piotroski + Minervini only (CANSLIM is US-only).
8. **Score thresholds need to be validated** against actual score distribution in DB before locking PLATINUM at 90.
9. **Mobile is over-scoped for one sprint** — scoped more realistically.

---

## Strategy Decisions (locked)

| Strategy | Markets | Consensus Role |
|---|---|---|
| CANSLIM | US only | Core score (50% weight for US) |
| Piotroski F-Score | US + KR | Core score (25% US, 50% KR) |
| Minervini SEPA | US + KR | Core score (25% US, 50% KR) |
| Weinstein Stage Analysis | US + KR | Gate only: Stage 2 required for GOLD+ |
| Dual Momentum | — | **Removed** |

**Conviction levels:** `DIAMOND > PLATINUM > GOLD > SILVER > BRONZE > UNRANKED`

**Workflow:** Fix locally → test → commit → CI → deploy Railway/Vercel

---

## Token Threshold Legend

| Level | Token Budget | When to use |
|---|---|---|
| **Low** | < 5k | Mechanical changes: constants, types, simple renames, 1-file edits |
| **Medium** | 5–20k | Standard feature work: new component, refactoring a service, adding tests |
| **High** | 20–50k | Multi-file features, complex logic, debugging non-obvious issues |
| **Max** (Opus 4.7 only) | > 50k | Architecture decisions, complex async/concurrency bugs, full module rewrites |

**Model selection:**
- `Low/Medium` → Haiku 4.5 (fast, cheap)
- `Medium/High` → Sonnet 4.6 (balanced)
- `High/Max` → Opus 4.7 (deep reasoning)

---

## Status Legend

`[ ]` Not started · `[~]` In progress · `[x]` Done · `[!]` Blocked

## Current Status Snapshot

**As of 2026-04-21, the mobile design-first rebuild is implemented through Phase 7.10, and Phase 8.1 verification is complete.**

- `[x]` Phases 1–6 were completed in a previous session
- `[x]` Phase 7.1–7.10 shipped in code
- `[x]` Phase 4.1 Celery reliability settings landed in `backend/app/tasks/celery_app.py`
- `[x]` Phase 8.1 verification is complete:
  - `pnpm --filter mobile exec tsc --noEmit` passes
  - `pnpm --filter mobile lint` passes with 1 pre-existing warning in `apps/mobile/components/BiometricGate.tsx`
  - `python -m compileall backend/app` passes
  - `cd backend && uv run pytest tests/ -v` passes: `83 passed`
  - `pnpm --filter web build` passes

**Important scope note:** this plan is a master remaster plan. Phases 1–6 were completed in another session and Phase 7 was completed in this session, so the practical next step is now the release/deploy tranche in Phase 8.

**Recommended next move:**
- Proceed to **Phase 8.2 — Local smoke test (manual)**.
- After that, move into **Phase 8.3–8.8** for commit, CI, and deploy.

---

## Phase 1 — Local Environment + Auth Triage

**Priority: Highest. Get everything running locally before touching any production config.**

### Step 1.1 — Verify local `.env` files are complete
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- Check `backend/.env` has: `POSTGRES_*`, `CLERK_SECRET_KEY`, `SECRET_KEY` (not `changeme`), `CORS_ORIGINS`
- Check `apps/web/.env.local` has: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1`
- Done when: both files exist with no `changeme` or empty required values

### Step 1.2 — Start backend and confirm it's healthy
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- Run: `cd backend && uv run uvicorn app.main:app --reload`
- Hit `GET http://localhost:8000/health` → must return 200
- Done when: no startup errors in terminal, health check passes

### Step 1.3 — Fix CORS for local + production
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- File: `backend/app/core/config.py`
- Ensure `cors_origins_list` correctly parses comma-separated env var
- `CORS_ORIGINS` local value: `http://localhost:3000,http://localhost:19006`
- Add startup warning log if no production domain detected and `APP_ENV=production`
- Done when: frontend can call backend without CORS errors in browser console

### Step 1.4 — Start frontend and confirm auth flow locally
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- Run: `pnpm --filter web dev`
- Navigate to `http://localhost:3000`, sign in with Clerk test account
- Done when: sign in succeeds, redirects to `/app/rankings`

### Step 1.5 — Check DB state with diagnostic queries
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- Run these SQL queries against Neon:
  ```sql
  SELECT COUNT(*) FROM consensus_app.scoring_snapshots;
  SELECT COUNT(*) FROM consensus_app.consensus_scores;
  SELECT MAX(score_date) FROM consensus_app.consensus_scores;
  SELECT COUNT(*) FROM consensus_app.instruments WHERE is_active = true;
  ```
- If all zeros → proceed to Step 1.6. If data exists but rankings empty → DB query bug.
- Done when: understand actual data state

### Step 1.6 — Manually trigger scoring pipeline (if DB is empty)
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- If consensus_scores is empty, run: `POST http://localhost:8000/api/v1/market-regime/trigger-scoring` with admin API key header
- Monitor Celery worker output for errors
- Done when: at least 1 scoring_snapshot row exists

### Step 1.7 — Run existing test suite baseline
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- Run: `cd backend && uv run pytest tests/ -v --tb=short`
- Record which tests pass/fail as baseline
- Do NOT fix failures yet — just document them
- Done when: baseline pass/fail count is known

---

## Phase 2 — Critical Visual Bug: Conviction Colors

**Do this immediately after triage — it's 30 minutes of work that makes the whole app visually debuggable.**

### Step 2.1 — Add PLATINUM to conviction level constants
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- File: `packages/ui-tokens/src/index.ts`
- Add `CONVICTION_COLORS` with 6 levels using OKLCH:
  ```typescript
  export const CONVICTION_COLORS = {
    DIAMOND:  { text: "oklch(0.88 0.10 195)", border: "oklch(0.88 0.10 195 / 0.4)" }, // cyan
    PLATINUM: { text: "oklch(0.88 0.04 290)", border: "oklch(0.88 0.04 290 / 0.4)" }, // lavender
    GOLD:     { text: "oklch(0.88 0.12 85)",  border: "oklch(0.88 0.12 85 / 0.4)"  }, // amber
    SILVER:   { text: "oklch(0.80 0.03 240)", border: "oklch(0.80 0.03 240 / 0.4)" }, // slate
    BRONZE:   { text: "oklch(0.78 0.09 55)",  border: "oklch(0.78 0.09 55 / 0.4)"  }, // orange
    UNRANKED: { text: "oklch(0.45 0 0)",      border: "oklch(0.45 0 0 / 0.15)"     }, // grey
  };
  ```
- Done when: constants exported correctly, no TS errors

### Step 2.2 — Fix conviction badge in instrument detail
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- File: `apps/web/src/app/app/instruments/[market]/[ticker]/_components/instrument-detail-client.tsx`
- Replace `convictionBadge()` function: use `CONVICTION_COLORS[level]` lookup, remove all `HIGH/MEDIUM` checks
- Done when: DIAMOND/PLATINUM/GOLD badges show correct colors, no "undefined" style

### Step 2.3 — Fix conviction color in rankings
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- File: `apps/web/src/app/app/rankings/_components/rankings-client.tsx`
- Replace `convictionColor()` function with `CONVICTION_COLORS` lookup
- Done when: rankings rows show colored conviction labels

### Step 2.4 — Update shared conviction-badge component
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- File: `apps/web/src/components/conviction-badge.tsx`
- Update to 6-level system with PLATINUM
- Done when: component renders all 6 levels correctly

### Step 2.5 — Update API client types
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- File: `packages/api-client/src/index.ts`
- Add `"PLATINUM"` to `ConvictionLevel` union type
- Done when: TypeScript compiles without errors

---

## Phase 3 — Schema Cleanup (Alembic Migrations)

### Step 3.1 — Check actual score distribution before setting PLATINUM threshold
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- Run this query to see score distribution:
  ```sql
  SELECT
    COUNT(*) FILTER (WHERE final_score >= 90) AS above_90,
    COUNT(*) FILTER (WHERE final_score >= 80) AS above_80,
    COUNT(*) FILTER (WHERE final_score >= 70) AS above_70,
    COUNT(*) total
  FROM consensus_app.consensus_scores
  WHERE score_date = (SELECT MAX(score_date) FROM consensus_app.consensus_scores);
  ```
- Use results to validate PLATINUM threshold (target: ~2-5% of universe gets PLATINUM)
- Done when: threshold confirmed

### Step 3.2 — Write migration: add PLATINUM conviction level
- Status: `[ ]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- File: `backend/alembic/versions/0005_add_platinum_conviction.py`
- PostgreSQL can only ADD values to an existing enum, not insert between existing ones
- If using varchar/string (not PG enum): simple constraint check update
- If using PG native enum: `ALTER TYPE conviction_level_enum ADD VALUE 'PLATINUM'` (order is appended, not inserted — query ordering handles display order)
- Include `downgrade()` that drops the value (PG doesn't support removing enum values — downgrade must recreate the type)
- Done when: `alembic upgrade head` runs cleanly locally, `alembic downgrade -1` tested and works

### Step 3.3 — Write migration: add performance indexes
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- File: `backend/alembic/versions/0006_add_performance_indexes.py`
- Three `CREATE INDEX IF NOT EXISTS` statements:
  - `idx_cs_score_date ON consensus_app.consensus_scores (score_date DESC, instrument_id)`
  - `idx_ss_score_date ON consensus_app.strategy_scores (score_date DESC, instrument_id)`
  - `idx_prices_range ON consensus_app.prices (instrument_id, trade_date DESC)` — skip if TimescaleDB already creates this
- `downgrade()`: drop each index
- Done when: migrations run cleanly, `EXPLAIN` on rankings query shows index scan

### Step 3.4 — Update consensus.py: strategy weights + Weinstein gate + PLATINUM
- Status: `[ ]`
- Model: **Opus 4.7** | Threshold: **Max**
- File: `backend/app/services/strategies/consensus.py`
- Changes (carefully, this is the core scoring logic):
  1. Separate US and KR weight configs:
     ```python
     STRATEGY_WEIGHTS = {
         "US": {"canslim": 0.50, "piotroski": 0.25, "minervini": 0.25},
         "KR": {"piotroski": 0.50, "minervini": 0.50},
     }
     ```
  2. Add `PLATINUM` threshold. Calibrate against Step 3.1 query results.
  3. Weinstein gate (after conviction is computed):
     ```python
     if weinstein_stage not in ("2_early", "2_mid", "2_late"):
         # Cap at SILVER if not in Stage 2 — stock may be Stage 1 (base-building), 3 (topping), or 4 (declining)
         conviction_level = min(conviction_level, "SILVER")
     ```
  4. Remove `dual_mom` from all weight dicts and scoring logic
  5. Update `REGIME_CAPS` to include `PLATINUM`
- Run all strategy tests after
- Done when: all tests pass, conviction output changes make sense (fewer DIAMOND, some PLATINUM)

### Step 3.5 — Update Pydantic schemas: remove dual_mom, add PLATINUM
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- Files: `backend/app/schemas/` — all schemas with `ConvictionLevel`, `dual_mom_score`, `dual_mom_detail`
- Remove `dual_mom_detail` from response, keep DB column (historical data)
- Add `weinstein_stage: str | None` to response so UI can show gate reason
- Done when: `uv run python -c "from app.schemas import *"` imports without error

### Step 3.6 — Remove Dual Momentum from instrument detail + rankings response
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- Files: API client types + web instrument detail component
- Remove Dual Momentum section from `instrument-detail-client.tsx`
- Remove `dual_mom_score` from sort fields in API client
- Done when: no TypeScript errors, Dual Momentum section gone from UI

### Step 3.7 — Run full test suite + fix broken tests
- Status: `[ ]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- Fix any tests that hardcode `dual_mom`, old conviction levels, or old strategy counts
- Add test for PLATINUM conviction assignment
- Add test for Weinstein gate (Stage 1 instrument capped at SILVER)
- Done when: all tests pass

---

## Phase 4 — Backend Reliability Fixes

### Step 4.1 — Fix Celery task configuration
- Status: `[x]`
- Model: Haiku 4.5 | Threshold: **Low**
- File: `backend/app/tasks/celery_app.py`
- Add to `celery_app.conf.update(...)`:
  ```python
  task_acks_late=True,
  task_reject_on_worker_lost=True,
  task_time_limit=3600,
  task_soft_time_limit=3300,
  result_expires=86400,
  worker_max_tasks_per_child=100,
  ```
- Done when: Celery worker starts without warnings about these settings

### Step 4.2 — Add tenacity to pyproject.toml + apply to ingestion tasks
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- Add `tenacity>=8.2.0` to `backend/pyproject.toml` dependencies
- File: `backend/app/tasks/ingestion_tasks.py`
- Wrap task body with `@tenacity.retry(wait=wait_exponential(min=2, max=60), stop=stop_after_attempt(3))`
- Also add `bind=True, max_retries=3` to `@celery_app.task` decorator
- Done when: a simulated failure retries 3 times then fails with clear log

### Step 4.3 — Fix Korea ingestion silent failures
- Status: `[ ]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- Files: `backend/app/services/ingestion/kr_price.py`, `kr_fundamental.py`
- Replace all `except Exception as e: logger.error(...)` + `return partial_data` with proper retry/raise
- Add minimum row count check: if `len(result) < MIN_EXPECTED`, raise `InsufficientDataError`
- Add pykrx fallback for price data when KIS API fails:
  ```python
  try:
      prices = await fetch_from_kis(ticker, start, end)
  except KISAPIError:
      logger.warning("KIS failed, falling back to pykrx for %s", ticker)
      prices = fetch_from_pykrx(ticker, start, end)
  ```
- Done when: intentional KIS failure triggers pykrx fallback, logged clearly

### Step 4.4 — Fix US ingestion EDGAR rate limiting
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- File: `backend/app/services/ingestion/us_fundamental.py`
- Add tenacity retry with `wait_exponential` + 429/503 status detection
- Add `asyncio.sleep(0.1)` between EDGAR requests to stay under 10 req/sec limit
- Done when: EDGAR calls retry on 429, don't crash the pipeline

### Step 4.5 — Remove WebSocket streaming endpoint
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- File: `backend/app/api/v1/endpoints/instruments.py`
- Remove the `stream_quotes` WebSocket endpoint (it mocks data, no client uses it)
- Remove from router if separately registered
- Reason: it's a mock, wastes DB connections, misleads users who find the endpoint
- Done when: no WebSocket routes in `GET /openapi.json`

### Step 4.6 — Fix instrument detail crash (graceful 404)
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- File: `backend/app/api/v1/endpoints/instruments.py`
- When instrument has no scoring data, return `HTTPException(status_code=404, detail="No scoring data available yet for this instrument")`
- Instead of unhandled NoneType exception
- Done when: `GET /api/v1/instruments/FAKE_TICKER?market=US` returns 404 with clear message, not 500

### Step 4.7 — Fix N+1 in rankings: direct query instead of snapshot JSON
- Status: `[ ]`
- Model: **Opus 4.7** | Threshold: **High**
- File: `backend/app/api/v1/endpoints/rankings.py`
- Replace Python-side snapshot JSON filtering with direct `consensus_scores JOIN instruments` query
- Use `COUNT(*) OVER ()` window function to avoid separate count query
- Include Weinstein stage in SELECT for gate display
- Fix ETag: include `market`, `asset_type`, `conviction` params in hash so different filter combos get different cache entries
- Done when: rankings query uses EXPLAIN with index scan, response time < 100ms locally

### Step 4.8 — Fix startup: add health validation
- Status: `[ ]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- File: `backend/app/main.py`
- Add `@app.on_event("startup")` that checks and logs:
  - `SELECT 1` DB connection test
  - Whether scoring_snapshots table has any rows (warn if empty)
  - Whether CORS origins include a non-localhost value in production
  - Whether `SECRET_KEY` is not `changeme`
- Done when: startup logs clearly show green/warn for each check

### Step 4.9 — Parallelize scoring engine data fetches
- Status: `[ ]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- File: `backend/app/services/strategies/canslim/engine.py` (lines ~175-197)
- Replace 4 sequential `await` calls with single `asyncio.gather()`
- Done when: test run shows reduced time per instrument scored

---

## Phase 5 — Web: Chart Implementation

**The #1 missing user-visible feature. lightweight-charts v5.1.0 is already in package.json.**

### Step 5.1 — Read lightweight-charts v5 docs
- Status: `[ ]`
- Model: N/A | Threshold: N/A (research step)
- `lightweight-charts` v5 has a different API than v4 — read `node_modules/lightweight-charts/dist/lightweight-charts.esm.development.js` header or check `AGENTS.md` note about breaking changes
- Key v5 changes: `createChart()` returns different object, series API changed
- Done when: understand correct v5 API surface before writing code

### Step 5.2 — Create useChart hook
- Status: `[ ]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- File: `apps/web/src/hooks/use-chart.ts`
- Manages: create chart on container ref attach, destroy on unmount, resize on window resize
- Returns: `{ containerRef, chart }` where chart is the lightweight-charts instance
- Done when: hook creates/destroys chart correctly, no memory leaks on navigation

### Step 5.3 — Build InstrumentChart component
- Status: `[ ]`
- Model: **Sonnet 4.6** | Threshold: **High**
- File: `apps/web/src/components/instrument-chart.tsx`
- Props: `{ chart: InstrumentChart | null, interval: string, rangeDays: number, onIntervalChange: fn, onRangeChange: fn }`
- Implement in order:
  1. Candlestick series: map `chart.bars` → `{ time, open, high, low, close }` (time must be UTC seconds or YYYY-MM-DD string)
  2. RS line: secondary right-axis `LineSeries` from `chart.rs_line` (only if `rs_line` array is non-empty — some instruments don't have RS data)
  3. SMA 50/150/200: compute from close prices client-side using sliding window, add as `LineSeries` (50=blue, 150=orange, 200=red)
  4. Pattern markers: use `series.setMarkers([{ time, position: 'belowBar', shape: 'arrowUp', color, text }])` for each pattern
  5. Dark theme config: `background: { type: 'solid', color: 'oklch(0.11 0.01 240)' }`, `textColor: 'oklch(0.65 0 0)'`, `grid.vertLines/horzLines: color: 'rgba(255,255,255,0.06)'`
  6. Interval buttons: 1D / 1W / 1M chips below chart, wire to `onIntervalChange`
  7. Range buttons: 6M / 1Y / 2Y chips, wire to `onRangeChange` (parent re-fetches)
- Done when: chart renders locally with AAPL data, RS line visible, MA ribbons visible, dark theme applied

### Step 5.4 — Integrate chart into instrument detail page
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- File: `apps/web/src/app/app/instruments/[market]/[ticker]/_components/instrument-detail-client.tsx`
- Replace "Price Data" text panel with `<InstrumentChart chart={chart} interval={chartInterval} rangeDays={chartRangeDays} ... />`
- Wire `chartInterval` and `chartRangeDays` from Zustand store
- Show skeleton div while `isFetching` is true
- Done when: chart appears on instrument detail page with real data

---

## Phase 6 — Web: Strategy Builder UI

### Step 6.1 — Rebuild strategies page: 3-tab layout
- Status: `[ ]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- File: `apps/web/src/app/app/strategies/page.tsx`
- Tab bar: CANSLIM | Piotroski | Minervini
- CANSLIM tab: left panel = filter builder, right = filtered results list
- Piotroski + Minervini tabs: just ranked list for that strategy
- Reuse `RankingItem` row component from rankings page (extract to shared component first)
- Done when: 3 tabs render, each loads correct strategy data

### Step 6.2 — Extract shared RankingRow component
- Status: `[ ]`
- Model: Haiku 4.5 | Threshold: **Low**
- File: `apps/web/src/components/ranking-row.tsx`
- Extract the row markup from `rankings-client.tsx` into a reusable component
- Used in both rankings and strategies pages
- Done when: rankings page still works, strategies tabs use same component

### Step 6.3 — Build CANSLIM filter builder
- Status: `[ ]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- File: `apps/web/src/app/app/strategies/_components/canslim-filter-builder.tsx`
- UI (collapsible panel):
  - EPS QoQ growth slider (10-100%, default 25%)
  - Annual EPS growth slider (15-100%, default 20%)
  - RS rating minimum slider (50-99, default 70)
  - Toggle: N criterion (new product/management)
  - Toggle: I criterion (institutional sponsorship ≥ 30%)
  - Toggle: Weinstein Stage 2 gate
  - 3 preset buttons: "Growth" | "Quality" | "Momentum" (each sets preset values)
  - "Apply" button → POST `/api/v1/filters`, show results below
- Done when: applying filters returns a different list than unfiltered CANSLIM tab

---

## Phase 7 — Mobile Parity (Design-First Rebuild)

**Design reference:** `Consensus Mobile Prototype.html` from design bundle.
**Design system:** Space Grotesk + JetBrains Mono + Instrument Serif · dark-default amber-accent palette · conviction-edge cards.

**Navigation structure (expo-router):**
```
app/(app)/
  _layout.tsx              ← Stack (outer; instrument detail slides over tabs)
  (tabs)/
    _layout.tsx            ← Tabs (4 tabs, custom TabBar)
    rankings.tsx           ← Rankings tab
    search.tsx             ← Search tab
    strategies.tsx         ← Strategies tab
    me.tsx                 ← Me / Profile tab
  instrument/[market]/[ticker].tsx  ← Detail (full-screen stack push)
app/(auth)/
  sign-in.tsx              ← redesigned onboarding
```

**Removed from original plan:** Alerts tab (no dedicated tab in design; handled by push), Market Regime tab (not in design's bottom nav — embed regime banner in Rankings header).

---

### Step 7.1 — Fonts + theme tokens
- Status: `[x]`
- Model: Haiku 4.5 | Threshold: **Low**
- Install: `@expo-google-fonts/space-grotesk`, `@expo-google-fonts/jetbrains-mono`, `@expo-google-fonts/instrument-serif`
- Create `apps/mobile/lib/theme.ts`:
  - `THEMES.dark` / `THEMES.light` token objects (bg0–bg3, text, quiet, faint, primary `#e8b867`, line, conviction map, green/amber/red)
  - `CONVICTION_STYLE` — bg/border/text per level (from prototype THEMES.dark.conviction)
  - `FONTS` constant mapping: `heading: 'SpaceGrotesk_700Bold'`, `mono: 'JetBrainsMono_500Medium'`, `serif: 'InstrumentSerif_400Regular'`
- Load all fonts in `apps/mobile/app/_layout.tsx` via `useFonts()`; show `SplashScreen` until ready
- Done when: `npx tsc --noEmit` passes, fonts load without error in Expo Go

### Step 7.2 — Shared UI components
- Status: `[x]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- All files in `apps/mobile/components/ui/`:

  **`conviction-badge.tsx`**
  - Rounded pill: background/border/text from `THEMES.dark.conviction[level]`
  - Small circle dot (5×5) + uppercase label
  - Props: `level: ConvictionLevel`, `theme`, `size?: 'sm' | 'md'`

  **`sparkline.tsx`**
  - Pure SVG (react-native-svg): area gradient fill + 1.5px stroke line
  - Props: `data: number[]`, `color: string`, `width?: number`, `height?: number`
  - Gradient id uses color string to avoid SVG id collision

  **`panel.tsx`**
  - `View` with panel gradient background + 1px border + borderRadius 20
  - Props: `soft?: boolean` (uses bg3 + lineSoft), `style?`, `children`

  **`market-toggle.tsx`**
  - Animated pill: `Animated.Value` → `left` interpolation for slider indicator
  - 280ms `spring` animation on market change
  - Props: `market: 'US' | 'KR'`, `onChange`, `theme`

  **`ranking-row.tsx`**
  - Rich card (default) + compact variant
  - Rich: left conviction edge bar (3px), rank in JetBrains Mono, ticker 700 20px, Sparkline 60×22, score 700 22px, bottom row: ConvictionBadge + 5 pip bars
  - Compact: single-line rank + ticker/name + conviction dot + score
  - Props: `item: RankingItem | StrategyRankingItem`, `theme`, `density?: 'rich' | 'compact'`, `onPress`

- Done when: all components render in isolation, TypeScript clean

### Step 7.3 — Tab navigation restructure
- Status: `[x]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- Files:
  - `apps/mobile/app/(app)/_layout.tsx` → outer Stack (screens: `(tabs)` + `instrument/[market]/[ticker]`)
  - `apps/mobile/app/(app)/(tabs)/_layout.tsx` → `<Tabs>` with `tabBar` prop pointing to custom `TabBar` component
  - Create `apps/mobile/components/ui/tab-bar.tsx`:
    - 4 tabs: Rankings (bar-chart icon) | Search (search icon) | Strategies (waveform icon) | Me (person icon)
    - Active color: `t.primary` (#e8b867); inactive: `t.faint`
    - iOS: `paddingBottom: 34`, Android: `paddingBottom: 24`; backdrop blur on iOS
  - Move existing `rankings.tsx` → `(tabs)/rankings.tsx`
  - Stub `(tabs)/search.tsx`, `(tabs)/strategies.tsx`, `(tabs)/me.tsx` (filled in next steps)
- Done when: bottom tabs visible, active amber highlight correct, instrument detail slides over tab bar

### Step 7.4 — Rankings screen redesign
- Status: `[x]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- File: `apps/mobile/app/(app)/(tabs)/rankings.tsx`
- Layout:
  - Header: `Kicker("Consensus Rankings")` + `Display("US RANKINGS")` + `MarketToggle`
  - Regime warning banner (amber border) when `data.regime_warning_count > 0`
  - `FlatList` of `RankingRow` cards; `keyExtractor = ticker+market`
  - `refreshControl`: `RefreshControl` wired to `refetch()`
  - `ListFooterComponent`: loading spinner when `isFetchingNextPage`
- Data: `useQuery(['rankings', market, 'stock', 50], fetchRankings(...))`
- Tap row → `router.push('/instrument/${item.market}/${item.ticker}')`
- Done when: list loads, market toggle switches US/KR, pull-to-refresh works

### Step 7.5 — Instrument detail redesign
- Status: `[x]`
- Model: Sonnet 4.6 | Threshold: **High**
- File: `apps/mobile/app/(app)/instrument/[market]/[ticker].tsx` (full rewrite)
- Layout (ScrollView):
  1. **Header bar** — back chevron (amber) + ticker/name + price/change
  2. **Conviction + sector badges** row
  3. **Consensus score hero panel** — large score (64px JetBrains Mono), animated bar, 2×2 grid of mini strategy scores (CANSLIM / Piotroski / Minervini / Weinstein)
  4. **Price chart panel** — range buttons (1M/3M/6M/1Y) + existing `CandlestickChart` from wagmi-charts, styled to dark theme
  5. **Strategy breakdown panel** — CANSLIM C/A/N/S/L/I/M pips, Piotroski F1–F9 pips, Minervini T1–T8 pips, Weinstein stage badge + MA slope text
- Components used: `Panel`, `ConvictionBadge`, `Pip` (new: 24px mono chip, green when active)
- Done when: all sections render with real API data, back button returns to rankings

### Step 7.6 — Search screen
- Status: `[x]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- File: `apps/mobile/app/(app)/(tabs)/search.tsx`
- Layout:
  - Header: `Kicker` + `Display("SEARCH")`
  - Search `TextInput` (bg2, rounded 14, search icon left) with 300ms debounce
  - Scope chips row: All markets / US / KR / Stocks / ETFs (active chip uses `primaryDim` bg + `primaryLine` border)
  - **Empty state:** "Pinned symbols" chips + "Trending today" FlatList with sparklines + scores
  - **Results state:** FlatList of result rows (ticker / exchange / name / ConvictionBadge)
- Data: `fetchSearch(query, { market, asset_type })` on debounced input change
- Tap → `router.push('/instrument/${market}/${ticker}')`
- Done when: "AAPL" query returns result, tap navigates to detail

### Step 7.7 — Strategies screen
- Status: `[x]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- File: `apps/mobile/app/(app)/(tabs)/strategies.tsx`
- Layout:
  - Header: `Kicker` + `Display("STRATEGY RANKINGS")`
  - 3-tab pill bar: CANSLIM | Piotroski | Minervini (same logic as web — CANSLIM US-only)
  - `MarketToggle` (hidden for CANSLIM)
  - Strategy explainer `Panel` (soft, 3-line description per strategy)
  - `FlatList` of `RankingRow` (rich density)
- Data: `fetchStrategyRankings(strategy, market)`
- Done when: tabs switch correctly, CANSLIM hides market toggle, rows tap to detail

### Step 7.8 — Sign-in screen redesign
- Status: `[x]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- File: `apps/mobile/app/(auth)/sign-in.tsx` (full rewrite)
- Layout:
  - Two ambient glow `View`s (radial bg with `#e8b867` and cyan tints — use `borderRadius: 999` + `opacity`)
  - Logo mark: 32×32 amber square (borderRadius 8) with "C" in JetBrains Mono + "CONSENSUS" label
  - `Kicker("Signal over noise")`
  - Instrument Serif hero: "Four strategies.\n" + italic amber "One verdict."
  - Conviction badge preview row (all 5 levels)
  - Email input + "Continue" button (amber bg, dark text)
  - Divider "or"
  - Apple + Google SSO buttons (existing Clerk auth, restyle)
- Done when: screen matches design, existing Google OAuth still works

### Step 7.9 — Me screen + push registration
- Status: `[x]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- File: `apps/mobile/app/(app)/(tabs)/me.tsx` (new)
- Layout:
  - Profile header: avatar initials circle + email + sign-out button
  - "Pinned Instruments" section (FlatList from Zustand/MMKV store)
  - "Notifications" toggle (wires push registration)
  - On toggle on: `registerForPushNotificationsAsync()` → POST `/api/v1/me/push-token` with Clerk token
  - Handle `NotAllowedError` gracefully (show system dialog explanation)
- Done when: pinned list shows, push token registered in `user_push_tokens` DB table

### Step 7.10 — Backend: push notification sender
- Status: `[x]`
- Model: Sonnet 4.6 | Threshold: **Medium**
- File: `backend/app/services/alerts/push.py`
- Complete `send_push_notifications()` via `httpx` → `POST https://exp.host/--/api/v2/push/send`
- Celery beat task: daily conviction-change check — instruments that moved BRONZE/SILVER → GOLD/PLATINUM/DIAMOND send push to subscribed users
- Current implementation note: notifications currently go to all registered device tokens; user-level subscription targeting is still a follow-up enhancement
- Done when: test push sends to Expo Go device

---

## Phase 8 — Final Local Test + Production Deploy

### Step 8.1 — Full test suite
- Status: `[x]`
- Model: Haiku 4.5 | Threshold: **Low**
- `cd backend && uv run pytest tests/ -v` — all pass
- `pnpm --filter web build` — TypeScript + build succeeds
- Done when: zero failures

### Step 8.2 — Local smoke test (manual)
- Status: `[ ]`
- Model: N/A | Threshold: N/A
- Sign in → rankings shows data with correct conviction colors
- Click instrument → chart renders with candlesticks, RS line, MA ribbons
- CANSLIM tab → filter builder applies filters
- Done when: all features work locally

### Step 8.3 — Commit in logical order
- Status: `[ ]`
- Model: N/A | Threshold: N/A
- Recommended commit sequence (keep each small and reviewable):
  1. `fix: CORS config + startup health check` (Phase 1.3, 4.8)
  2. `fix: conviction badge colors + add PLATINUM type` (Phase 2)
  3. `feat: PLATINUM conviction level + Alembic migrations` (Phase 3.1-3.3)
  4. `refactor: remove Dual Momentum, add Weinstein gate, market-specific weights` (Phase 3.4-3.6)
  5. `fix: Celery reliability + tenacity retries + ingestion error handling` (Phase 4.1-4.4)
  6. `fix: remove mock WebSocket, graceful 404 on detail, rankings N+1` (Phase 4.5-4.7)
  7. `feat: instrument chart (lightweight-charts v5, RS line, MA, patterns)` (Phase 5)
  8. `feat: strategy tabs + CANSLIM filter builder` (Phase 6)
  9. `feat: mobile design system (fonts, theme tokens, shared UI components)` (Phase 7.1–7.2)
  10. `feat: mobile nav restructure + rankings redesign` (Phase 7.3–7.4)
  11. `feat: mobile detail, search, strategies screens` (Phase 7.5–7.7)
  12. `feat: mobile sign-in redesign + Me screen + push notifications` (Phase 7.8–7.10)

### Step 8.4 — CI gate (GitHub Actions)
- Status: `[ ]`
- All CI checks must pass: ruff, pytest, mypy, next build, tsc
- If any fail: fix before proceeding

### Step 8.5 — Update Railway env vars
- Status: `[ ]`
- Model: N/A | Threshold: N/A
- Railway dashboard → `api` service:
  - `CORS_ORIGINS`: add production Vercel URL
  - Verify `CLERK_SECRET_KEY`, `POSTGRES_*` all set
- Railway dashboard → `worker` + `beat` services:
  - Same env vars
  - `CELERY_BROKER_URL`: must be set (Redis or PostgreSQL broker)
- Done when: Railway shows all env vars present

### Step 8.6 — Run Alembic migrations in production
- Status: `[ ]`
- Model: N/A | Threshold: N/A
- Via Railway shell on `api` service: `uv run alembic upgrade head`
- Verify: `alembic current` shows `0006_add_performance_indexes`
- Done when: migrations applied, no error

### Step 8.7 — Update Vercel env vars
- Status: `[ ]`
- Ensure `NEXT_PUBLIC_API_BASE_URL` = production Railway URL
- Ensure `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` set
- Ensure Clerk dashboard allowed redirect URLs include Vercel production domain

### Step 8.8 — Production smoke test
- Status: `[ ]`
- Sign in on Vercel production URL
- Rankings loads with colored conviction badges (amber GOLD, not grey)
- Instrument detail loads with chart
- Mobile app: all 4 tabs work, sign-in works
- Done when: all 4 original broken symptoms are resolved

---

## File Change Map

| File | Phase | Model | Threshold |
|---|---|---|---|
| `backend/app/core/config.py` | 1.3 | Haiku | Low |
| `packages/ui-tokens/src/index.ts` | 2.1 | Haiku | Low |
| `apps/web/src/.../instrument-detail-client.tsx` | 2.2, 5.4 | Haiku | Low |
| `apps/web/src/.../rankings-client.tsx` | 2.3 | Haiku | Low |
| `apps/web/src/components/conviction-badge.tsx` | 2.4 | Haiku | Low |
| `packages/api-client/src/index.ts` | 2.5, 3.6 | Haiku | Low |
| `backend/alembic/versions/0005_add_platinum.py` | 3.2 | Sonnet | Medium |
| `backend/alembic/versions/0006_add_indexes.py` | 3.3 | Haiku | Low |
| `backend/app/services/strategies/consensus.py` | 3.4 | **Opus** | **Max** |
| `backend/app/schemas/*.py` | 3.5 | Haiku | Low |
| `backend/app/tasks/celery_app.py` | 4.1 | Haiku | Low |
| `backend/app/tasks/ingestion_tasks.py` | 4.2 | Haiku | Low |
| `backend/app/services/ingestion/kr_price.py` | 4.3 | Sonnet | Medium |
| `backend/app/services/ingestion/kr_fundamental.py` | 4.3 | Sonnet | Medium |
| `backend/app/services/ingestion/us_fundamental.py` | 4.4 | Haiku | Low |
| `backend/app/api/v1/endpoints/instruments.py` | 4.5, 4.6 | Haiku | Low |
| `backend/app/api/v1/endpoints/rankings.py` | 4.7 | **Opus** | **High** |
| `backend/app/main.py` | 4.8 | Sonnet | Medium |
| `backend/app/services/strategies/canslim/engine.py` | 4.9 | Sonnet | Medium |
| `apps/web/src/hooks/use-chart.ts` | 5.2 | Sonnet | Medium |
| `apps/web/src/components/instrument-chart.tsx` | 5.3 | Sonnet | **High** |
| `apps/web/src/components/ranking-row.tsx` | 6.2 | Haiku | Low |
| `apps/web/src/app/app/strategies/page.tsx` | 6.1 | Sonnet | Medium |
| `apps/web/src/app/app/strategies/_components/canslim-filter-builder.tsx` | 6.3 | Sonnet | Medium |
| `apps/mobile/app/(app)/_layout.tsx` | 7.1 | Sonnet | Medium |
| `apps/mobile/app/(app)/search.tsx` | 7.2 | Sonnet | Medium |
| `apps/mobile/app/(app)/alerts.tsx` | 7.3 | Sonnet | Medium |
| `apps/mobile/app/(app)/regime.tsx` | 7.4 | Sonnet | Medium |
| `apps/mobile/app/_layout.tsx` | 7.5 | Sonnet | Medium |
| `backend/app/services/alerts/push.py` | 7.6 | Sonnet | Medium |
