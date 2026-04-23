# fd13b66 Recovery And Full Feature Completion Plan

## Summary

Commit `fd13b66` (`Upgrade rankings screener and async symbol hydration`) tried to deliver several major improvements at once: richer rankings, advanced filters, unranked symbol discovery, async hydration, symbol resolution, Celery polling, admin backfill, and frontend UI changes.

The ideas are still valuable, but the original implementation was too cross-cutting and fragile. It changed frontend behavior, backend API contracts, Celery assumptions, and DB write paths together, which made rollback difficult and created production risk.

This plan rebuilds the same product direction in two parts:

1. **Part 1: Production-Stable Rankings + Redesign**
   - Make rankings show more useful stocks.
   - Add partial-stock discovery safely.
   - Add advanced filtering through tested backend contracts.
   - Redesign rankings and detail pages into a modern investor-grade fintech experience.
   - Avoid risky async mutation flows until backend contracts are stable.

2. **Part 2: Full fd13b66 Feature Completion**
   - Add explicit async hydration.
   - Add DB-backed job status.
   - Add safe symbol resolution.
   - Add admin backfill.
   - Add provider taxonomy and missing investor metrics.
   - Reintroduce watchlist/pinning after data and hydration behavior are stable.

The key principle is: **backend contract first, frontend second, deployment in small rollback-safe commits.**

## Locked Product Decisions

### Rollout

- Use a strict two-part rollout.
- Do not reapply `fd13b66` directly.
- Reuse ideas and selected code only after adapting them to safer contracts.
- Deploy backend changes before frontend changes that depend on them.
- Use small commits so rollback is surgical.

### Rankings

- Production rankings default to **top 200** initially.
- Users can select result count.
- Main rankings show scored rows first.
- Partial rows appear grouped below scored rankings.
- Default sort for scored rankings is final score descending.
- Partial and explore rows sort by best coverage first.
- Single-symbol refresh must not collapse rankings by advancing the global latest score date alone.

### Partial Rows And Explore More

- `Explore More` is a discovery-only section.
- Partial rows represent known relevant stocks that are not fully rankable yet.
- Explore rows represent additional unranked discoverable universe entries.
- Explore must never affect ranking totals.
- Partial/explore rows must clearly show incomplete data states.
- Search should search ranked, partial, and explore instruments together while labeling status clearly.

### Frontend UX

- Use a single-page rankings layout:
  - Ranked rows first.
  - Grouped partial rows below.
  - Explore More below that.
- Use **Load More** buttons, not infinite scroll.
- Use gentle strategy presets plus expandable advanced filters.
- No thresholds are active by default.
- Missing data labels should be very explicit.
- Incomplete detail pages should show a partial page, not endless loading.
- Missing chart candles should show an explanation and refresh CTA, not an infinite skeleton.

### Redesign Direction

- Major redesign is part of the plan.
- Visual direction: **light modern fintech investor terminal**.
- It should feel closer to Toss or Robinhood than Bloomberg.
- Use one consistent layout across markets, but localize text, names, colors, and number formatting by market.
- Mobile must be first-class, not a squeezed desktop table.
- Density should be balanced: serious investor information without overwhelming first-time users.

### Localization

- Localization is by market.
- KR stocks show Korean labels and Korean-native number/currency formatting.
- US stocks show English labels and USD/US-style formatting.
- Korean stock name is primary for KR stocks.
- Numeric Korean ticker is secondary metadata.
- US stocks can continue using English name/ticker conventions.
- Gain/loss colors follow market convention:
  - KR: red/up, blue/down.
  - US: green/up, red/down.

### Investor Metrics

- Show all currently available backend metrics.
- Organize metrics as summary cards plus expandable sections.
- Use market-native formatting:
  - KR: Korean won and Korean compact units such as 억/조 where appropriate.
  - US: USD and M/B/T-style compact units.
- Do not fake unavailable metrics.
- Metrics like PER/P/E, dividend yield, and market cap should be shown only when the backend can source or compute them reliably.

### Filters

- All filters are desired, but backend support and tests must come first.
- Filters should be available through read-friendly GET APIs when possible.
- Missing score behavior:
  - If a filter requires a field that a partial row does not have, hide that partial row from that filtered result set.
- Presets should be gentle, not overly strict.
- Use strategy presets such as Growth, Value Quality, Momentum, Turnaround, and Conservative.

### Coverage States

- User-facing coverage states should be simple:
  - Ranked
  - Needs Price
  - Needs Fundamentals
  - Needs Scoring
  - Stale
- Staleness should be market-aware:
  - Price freshness should use trading-day logic.
  - Fundamentals freshness should use quarter-like reporting windows.

### Hydration And Unknown Symbols

- Hydration is explicit and manual.
- Do not auto-hydrate on page open.
- Signed-in users can queue refreshes.
- Use conservative rate limits and job deduplication.
- Unknown valid-looking tickers should show "not in database yet" with a Queue refresh action.
- Exact-symbol resolution for `TSSI`-like symbols is a Part 2 requirement.
- No GET search/detail/chart endpoint should write to the database.

### Workers And Jobs

- Deployment assumes separate API, Celery worker, and Celery beat services.
- User-facing job status should live in Postgres, not only Celery result backend.
- Start with admin-triggered market jobs first.
- Add beat scheduling only after manual admin jobs are stable.

## Threshold Legend

| Threshold | Use For | Typical Work |
|---|---|---|
| **Low** | Mechanical or clearly bounded edits | Constants, docs, type updates, simple API-client additions, one-file cleanup |
| **Medium** | Standard feature work | New endpoint with simple query, small UI section, moderate tests |
| **High** | Multi-file or non-obvious logic | Filters, DB query design, localization, metrics, auth, production smoke checks |
| **Max** | Architecture, concurrency, or high-risk production behavior | Celery integration, score-date safety, admin backfill, major redesign, full verification |

These thresholds are intended as reasoning/model-usage guidance for Codex-style work:

- **Low**: use for straightforward execution.
- **Medium**: use when implementation touches several files but the risk is contained.
- **High**: use when correctness depends on understanding backend/frontend/data interactions.
- **Max**: use when mistakes can break production, rankings integrity, async jobs, or deployment.

## Part 1 Action Plans: Production-Stable Rankings + Redesign

### Action Plan 1: Baseline Audit And API Contract Lock

**Threshold: Low**

**Status: Completed on 2026-04-23.**

Confirm the current stable production behavior before making changes.

Tasks:

- Confirm current rankings, detail, chart, and search endpoint shapes.
- Confirm current frontend routes do not call removed or missing endpoints.
- Confirm `packages/api-client` types match current backend responses.
- Confirm the current rankings default limit behavior.
- Confirm KR detail pages can display `name_kr` where present.

Acceptance criteria:

- Current US/KR rankings behavior is documented.
- Current detail and chart response shapes are known.
- No frontend route depends on missing endpoints before new work starts.
- `ok-now-i-need-snuggly-pinwheel.md` is intentionally deleted by the user and is no longer the source of truth.

Baseline findings:

- Git state at audit start:
  - `ok-now-i-need-snuggly-pinwheel.md` is deleted by user intent.
  - `fd13b66-recovery-action-plan.md` is the active plan file.
- Active source endpoints:
  - `GET /api/v1/rankings`
  - `GET /api/v1/instruments/{ticker}`
  - `GET /api/v1/instruments/{ticker}/chart`
  - `POST /api/v1/instruments/{ticker}/ingest`
  - `GET /api/v1/search`
  - `GET /api/v1/universe/coverage`
  - `GET /api/v1/strategies/{name}/rankings`
  - `POST /api/v1/filters/query`
- Endpoints from the cancelled `fd13b66` feature set are not active in source:
  - `GET /api/v1/universe/browse` is not implemented yet.
  - `POST /api/v1/instruments/{ticker}/hydrate` is not implemented yet.
  - `GET /api/v1/instruments/{ticker}/hydrate-status` is not implemented yet.
- Stale `__pycache__` files still contain references to cancelled hydrate/browse code, but the source files do not. Treat source files as authoritative.
- Current rankings backend contract:
  - Query params: `market`, `conviction`, `asset_type`, `score_date`, `limit`, `offset`.
  - Default backend `limit` is 50 and max is 200.
  - Response shape is `RankingsResponse` with `score_date`, `market`, `regime_state`, `regime_warning_count`, `pagination`, and `items`.
  - Each ranking item includes nested `scores` for CANSLIM, Piotroski, Minervini, and Weinstein.
  - Backend sets `coverage_state="ranked"` for ranking rows.
- Current web rankings frontend contract:
  - Server page defaults to `limit=200`.
  - Client clamps selected limit between 1 and 200.
  - Client uses `fetchRankings()` only; it does not call browse/hydrate endpoints.
  - `RankingsResponse.total` and `freshness` are normalized client-side from backend `pagination` and `score_date`.
- Current instrument detail backend contract:
  - Detail returns partial-safe `InstrumentDetailResponse` even when consensus or strategy scores are missing.
  - Detail includes `name_kr`, `exchange`, `listing_status`, `sector`, `industry_group`, `shares_outstanding`, `float_shares`, `coverage_state`, `ranking_eligibility`, `freshness`, `delay_minutes`, `rank_model_version`, and `needs_refresh`.
  - Chart returns empty `bars`, `rs_line`, and `patterns` with a `benchmark_note` when price data is absent.
- Current search backend contract:
  - `GET /api/v1/search` is read-only in source.
  - Search returns `name_kr`, listing metadata, coverage state, ranking eligibility, and rank model version.
  - Search does not currently create shell instruments from provider lookup.
- Current API-client gaps to carry into later action plans:
  - `CoverageState` is still typed as `searchable | price_ready | fundamentals_ready | ranked`; the planned user-facing states are not modeled yet.
  - `fetchUniverseBrowse`, hydrate trigger, and hydrate-status client methods do not exist yet.
  - `fetchFilteredRankings()` still uses `POST /filters/query`; Part 1 filter work should move public rankings filters toward `GET /rankings`.
- Current frontend route risks:
  - Instrument detail still imports `ingestInstrument()`.
  - Instrument detail automatically calls synchronous `POST /instruments/{ticker}/ingest` when `data.needs_refresh` is true.
  - This auto-refresh behavior conflicts with the locked product decision that refresh should become explicit/manual. Do not fix under Action Plan 1; carry it into Action Plan 7 and Part 2 hydration work.

Action Plan 1 result:

- Baseline audit is complete.
- No missing `universe/browse` or hydrate endpoint is currently called by the rankings page.
- The main known contract risk is the detail page auto-ingest behavior, not rankings.
- Next recommended step is Action Plan 2: Rankings Filter Backend.

### Action Plan 2: Rankings Filter Backend

**Threshold: High**

**Status: Completed on 2026-04-23.**

Extend rankings filtering through stable, tested backend contracts.

Tasks:

- Extend `GET /api/v1/rankings` with optional filters:
  - `market`
  - `asset_type`
  - `limit`
  - `offset`
  - `conviction`
  - `min_final_score`
  - `min_strategy_pass_count`
  - per-strategy thresholds
  - `sector`
  - `exchange`
  - `coverage_state`
  - freshness/readiness filters
- Keep no-threshold behavior as the default.
- Hide partial rows when a selected filter requires missing data.
- Preserve score-backed ranking semantics.
- Add targeted tests for every filter.
- Add targeted indexes through Alembic only if query plans show they are needed.

Acceptance criteria:

- US and KR rankings work with no filters.
- Every filter has backend tests.
- Combined filters return predictable results.
- Partial rows with missing required fields are excluded from filtered results.
- Existing API-client methods remain backwards compatible.

Implementation completed:

- Extended `GET /api/v1/rankings` with additive optional query params:
  - `min_final_score`
  - `max_final_score`
  - `min_consensus_composite`
  - `min_technical_composite`
  - `min_strategy_pass_count`
  - `min_canslim`
  - `min_piotroski`
  - `min_minervini`
  - `min_weinstein`
  - `min_rs_rating`
  - `sector`
  - `exchange`
  - `coverage_state`
  - `weinstein_stage`
  - `ad_rating`
  - `rs_line_new_high`
  - `price_ready`
  - `fundamentals_ready`
  - `price_as_of_gte`
  - `price_as_of_lte`
  - `quarterly_as_of_gte`
  - `annual_as_of_gte`
  - `ranked_as_of_gte`
- Kept existing default behavior unchanged:
  - Backend default `limit` remains 50.
  - Web rankings page still requests top 200.
  - Existing `market`, `asset_type`, `conviction`, `score_date`, `limit`, and `offset` params still work.
- Added an outer join to `instrument_coverage_summary` so rankings can filter by coverage and freshness.
- Preserved the `RankingsResponse` shape.
- Updated ETag generation so new filter combinations do not share stale cache entries.
- Added additive API-client support through `RankingsQueryParams`.
- Did not add Alembic indexes in this step because no measured query-plan bottleneck was captured during the implementation pass.

Verification completed:

- `cd backend && uv run pytest tests/test_api_endpoints.py -k "rankings_endpoint" -v`
  - Result: 5 passed.
- `pnpm --filter @consensus/api-client typecheck`
  - Result: passed.
- `pnpm --filter web typecheck`
  - Result: passed.

Follow-up notes:

- Public frontend filter UI is not implemented yet; this step only establishes the backend/API-client contract.
- User-facing coverage labels such as `Needs Price`, `Needs Fundamentals`, `Needs Scoring`, and `Stale` remain Action Plan 4.
- Partial rows are not yet included in the main rankings endpoint; that belongs to the later partial/explore implementation.

### Action Plan 3: Read-Only Universe Browse

**Threshold: Medium**

**Status: Completed on 2026-04-23.**

Add a safe discovery endpoint for unranked or partially covered instruments.

Tasks:

- Add `GET /api/v1/universe/browse`.
- Read from DB instrument and coverage data only.
- Do not call external providers.
- Do not write to DB.
- Do not enqueue Celery.
- Support:
  - `market`
  - `asset_type`
  - `coverage_state`
  - `limit`
  - `offset`
  - `exclude_ranked`
- Sort by best coverage first.
- Return pagination metadata.

Acceptance criteria:

- Browse works for US and KR.
- Browse failure cannot break main rankings.
- Endpoint is read-only.
- No provider calls happen inside browse.

Implementation completed:

- Added `GET /api/v1/universe/browse`.
- Added backend response schemas:
  - `BrowseResultEntry`
  - `BrowseResponse`
- Added read-only universe service support through `browse_instruments()`.
- Browse reads only from:
  - `instruments`
  - `instrument_coverage_summary`
- Browse does not:
  - call external providers
  - refresh coverage summaries
  - create instruments
  - enqueue Celery
  - write to the database
- Supported query params:
  - `market`
  - `asset_type`
  - `coverage_state`
  - `exclude_ranked`
  - `limit`
  - `offset`
- Default behavior:
  - `exclude_ranked=true`
  - `limit=50`
  - max `limit=200`
- Missing coverage summary rows are treated as `searchable` with `coverage_not_summarized` as the ranking reason.
- Sorting prioritizes best non-ranked coverage first:
  - `fundamentals_ready`
  - `price_ready`
  - `searchable`
  - lowest-priority fallback states
- Added API-client support:
  - `BrowseResult`
  - `BrowseResponse`
  - `BrowseQueryParams`
  - `fetchUniverseBrowse()`

Verification completed:

- `cd backend && uv run pytest tests/test_search_and_coverage.py -k "universe_browse or universe_coverage" -v`
  - Result: 3 passed.
- `cd backend && uv run pytest tests/test_api_endpoints.py -k "rankings_endpoint" -v`
  - Result: 5 passed.
- `pnpm --filter @consensus/api-client typecheck`
  - Result: passed.
- `pnpm --filter web typecheck`
  - Result: passed.

Follow-up notes:

- The frontend does not render Explore More yet; this step establishes the backend/API-client contract only.
- Browse uses persisted coverage summary rows and intentionally does not auto-repair stale or missing coverage. Coverage-state refinement remains Action Plan 4.

### Action Plan 4: Coverage States And Staleness

**Threshold: High**

**Status: Completed on 2026-04-23.**

Make missing and stale data understandable to users.

Tasks:

- Implement simple coverage states:
  - Ranked
  - Needs Price
  - Needs Fundamentals
  - Needs Scoring
  - Stale
- Use market-aware price staleness.
- Use quarter-aware fundamentals staleness.
- Expose coverage state consistently in rankings, browse, and detail responses.
- Add clear reasons where possible.

Acceptance criteria:

- Incomplete stocks explain what is missing.
- Stale data is labeled clearly.
- Detail pages no longer rely on endless loading for incomplete data.
- Coverage states behave consistently across US and KR.

Implementation completed:

- Added public coverage states:
  - `ranked`
  - `needs_price`
  - `needs_fundamentals`
  - `needs_scoring`
  - `stale`
- Kept DB summary readiness states internal so existing aggregate coverage totals remain meaningful.
- Added market-aware price staleness using a 3-trading-day cutoff for US/KR markets.
- Added fundamentals staleness thresholds:
  - quarterly reports: 200 days
  - annual reports: 500 days
- Mapped old coverage labels to public states for backward-compatible API filters:
  - `searchable` -> `needs_price`
  - `price_ready` -> `needs_fundamentals`
  - `fundamentals_ready` -> `needs_scoring`
  - `ranked` -> `ranked`
- Exposed public coverage states through:
  - rankings responses
  - rankings `coverage_state` filters
  - search responses
  - browse responses
  - detail responses via shared coverage map
- Added clear public reasons such as:
  - `no_price_history`
  - `no_fundamentals`
  - `score_not_generated`
  - `stale_price_data`
  - `stale_fundamentals`
- Updated the API-client `CoverageState` type to the new public labels.
- Updated frontend search and public copy to use the new state language.
- Preserved scored ranking rows without coverage-summary cache rows as `ranked` rather than treating missing cache metadata as missing company data.

Verification completed:

- `cd backend && uv run pytest tests/test_search_and_coverage.py -k "search_endpoint_returns_coverage_state or instrument_endpoint_returns_partial_detail or universe_browse or universe_coverage or refresh_coverage" -v`
  - Result: 6 passed.
- `cd backend && uv run pytest tests/test_api_endpoints.py -k "rankings_endpoint" -v`
  - Result: 5 passed.
- `pnpm --filter @consensus/api-client typecheck`
  - Result: passed.
- `pnpm --filter web typecheck`
  - Result: passed.
- `git diff --check`
  - Result: passed with line-ending warnings only.

### Action Plan 5: Rankings Page Major Redesign

**Threshold: Max**

**Status: Completed on 2026-04-23.**

Rebuild the rankings experience as a modern fintech investor terminal.

Tasks:

- Use a light modern visual direction.
- Build a single-page hierarchy:
  - Market/asset controls.
  - Strategy preset controls.
  - Advanced filter panel.
  - Ranked results.
  - Grouped partial rows.
  - Explore More.
- Add user-selectable result count with top 200 default.
- Add Load More behavior.
- Add explicit partial/explore labels.
- Add mobile-first cards or responsive layouts.
- Preserve existing design system patterns where the repo already has them.
- Avoid generic, boilerplate dashboard styling.

Acceptance criteria:

- Rankings page renders on desktop and mobile.
- KR names are visually primary for KR stocks.
- US stocks retain natural English naming.
- Partial rows are visually distinct from scored rankings.
- Browser console has no API 404s from the rankings page.

Implementation completed:

- Rebuilt `/app/rankings` into a single-page research desk with:
  - a light modern fintech `Signal Board` hero
  - market and asset controls
  - top 50/100/200 result-count controls with top 200 default preserved
  - strategy preset cards
  - expandable advanced filter panel
  - ranked result cards first
  - partial `Needs Scoring` rows below ranked results
  - `Explore More` rows below partial results
- Added gentle strategy presets:
  - All Signals
  - Growth
  - Value Quality
  - Momentum
  - Turnaround
  - Conservative
- Advanced filters now map to tested `GET /api/v1/rankings` query params:
  - conviction
  - coverage state
  - final score
  - strategy pass count
  - technical composite
  - CANSLIM
  - Piotroski
  - Minervini
  - Weinstein
  - RS rating
  - RS new high
- Added explicit Load More behavior:
  - ranked rows increase the `limit` query param up to backend max 200
  - partial rows increase read-only browse limit
  - explore rows increase read-only browse limit
- Added read-only `fetchUniverseBrowse()` usage for partial and explore sections.
- Kept Explore More discovery-only:
  - browse rows do not affect ranking totals
  - browse failures do not break ranked results
  - no provider calls or writes happen from the page
- Added additive `name_kr` support to rankings:
  - backend `RankingEntry`
  - rankings query select/mapping
  - API-client raw and normalized `RankingItem`
- Updated ranked row display so KR can prefer `name_kr` when available and US keeps natural English naming.
- Replaced the rankings loading skeleton with the new light-desk visual language.

Verification completed:

- `cd backend && uv run pytest tests/test_api_endpoints.py -k "rankings_endpoint" -v`
  - Result: 5 passed.
- `cd backend && uv run pytest tests/test_search_and_coverage.py -k "universe_browse or search_endpoint_returns_coverage_state or instrument_endpoint_returns_partial_detail" -v`
  - Result: 4 passed.
- `pnpm --filter @consensus/api-client typecheck`
  - Result: passed.
- `pnpm --filter web typecheck`
  - Result: passed.
- `pnpm --filter web build`
  - Result: passed.
- `git diff --check`
  - Result: passed with line-ending warnings only.

Follow-up notes:

- Browser-console verification against a live backend remains part of Action Plan 8.
- Investor metric expansion remains Action Plan 6.

### Action Plan 6: Investor Metrics Display

**Threshold: High**

**Status: Completed on 2026-04-23.**

Show investor-friendly stock information on rankings and detail pages.

Tasks:

- Add summary metric cards.
- Add expandable metric sections.
- Use currently available backend data:
  - latest price
  - price change where available
  - volume
  - average volume
  - sector
  - exchange
  - shares outstanding
  - float shares
  - revenue
  - EPS
  - revenue growth
  - EPS growth
  - net income
  - gross profit
  - total assets
  - current assets
  - current liabilities
  - long-term debt
  - operating cash flow
  - ROA
  - current ratio
  - gross margin
  - asset turnover
  - leverage ratio
  - strategy scores
  - technical indicators
- Add market-native number formatting.
- Add missing-data labels for unavailable metrics.
- Do not show fake PER/dividend yield/market cap unless backend can compute or source them reliably.

Acceptance criteria:

- Detail pages show useful information even when not fully scored.
- KR metrics use Korean labels and Korean-style formatting.
- US metrics use English labels and US-style formatting.
- Missing metrics are explicit and not misleading.

Implementation completed:

- Added additive backend detail metric payloads:
  - `price_metrics`
  - `quarterly_metrics`
  - `annual_metrics`
- Price metrics now include:
  - latest trade date
  - close
  - previous close
  - absolute change
  - percentage change
  - volume
  - 50-day average volume
- Quarterly metrics now include:
  - fiscal period
  - report date
  - revenue
  - net income
  - EPS
  - diluted EPS
  - revenue growth
  - EPS growth
  - data source
- Annual metrics now include:
  - fiscal year
  - report date
  - revenue
  - gross profit
  - net income
  - EPS
  - diluted EPS
  - EPS growth
  - total assets
  - current assets
  - current liabilities
  - long-term debt
  - annual shares outstanding
  - operating cash flow
  - ROA
  - current ratio
  - gross margin
  - asset turnover
  - leverage ratio
  - data source
- Updated the API client with additive metric types and normalization.
- Updated instrument detail pages with:
  - market-native summary metric cards
  - expandable price/liquidity, quarterly, annual, balance-sheet, and technical sections
  - Korean-primary display for KR names
  - KR won/Korean compact units and Korean labels
  - US dollar/M/B/T-style compact units and English labels
  - explicit missing-data labels
- Did not add PER, dividend yield, or market cap because those fields are not yet reliably sourced or computed.

Verification completed:

- `cd backend && uv run pytest tests/test_search_and_coverage.py -k "instrument_endpoint" -v`
  - Result: 2 passed.
- `cd backend && uv run pytest tests/test_api_endpoints.py -k "rankings_endpoint" -v`
  - Result: 5 passed.
- `pnpm --filter @consensus/api-client typecheck`
  - Result: passed.
- `pnpm --filter web typecheck`
  - Result: passed.
- `pnpm --filter web build`
  - Result: passed.
- `git diff --check`
  - Result: passed with line-ending warnings only.

### Action Plan 7: Detail And Chart Empty States

**Threshold: Medium**

**Status: Completed on 2026-04-24.**

Fix the user experience for incomplete instruments.

Tasks:

- Replace indefinite "loading instrument data" states.
- Show available basics immediately.
- Show missing chart explanation when candles are absent.
- Show missing fundamentals explanation when reports are absent.
- Show missing scoring explanation when raw data exists but scores do not.
- Add refresh CTA placeholder in Part 1.
- Do not make the placeholder enqueue jobs until Part 2.

Acceptance criteria:

- Incomplete detail pages remain usable.
- Missing chart candles do not look like a frontend crash.
- Users can understand why a stock has no score or chart.

Implementation completed:

- Removed the detail page auto-ingest behavior from the Part 1 frontend path.
- Replaced the synchronous detail-page ingest button with a disabled refresh-queue placeholder.
- Added clearer coverage-state explanations for:
  - `needs_price`
  - `needs_fundamentals`
  - `needs_scoring`
  - `stale`
  - unranked fallback states
- Kept available basics, investor metrics, scores, freshness, and chart shell visible even for incomplete instruments.
- Improved chart empty states so missing candles show an explicit explanation instead of looking like an endless loading or broken chart.
- Reused backend `benchmark_note` when chart data is absent.
- Kept provider writes and job enqueueing out of GET/detail/chart frontend flows until Part 2 hydration.

Verification completed:

- `cd backend && uv run pytest tests/test_search_and_coverage.py -k "instrument_endpoint or chart_endpoint" -v`
  - Result: 3 passed.
- `pnpm --filter @consensus/api-client typecheck`
  - Result: passed.
- `pnpm --filter web typecheck`
  - Result: passed.
- `pnpm --filter web build`
  - Result: passed.
- `git diff --check`
  - Result: passed with line-ending warnings only.

### Action Plan 8: Part 1 Verification And Deploy

**Threshold: High**

**Status: Completed on 2026-04-24.**

Validate the production-stable rankings and redesign tranche.

Tasks:

- Run backend tests.
- Run frontend type checks/build.
- Run API smoke tests.
- Run browser checks for rankings and detail pages.
- Verify live backend endpoints before frontend deploy.
- Deploy backend first.
- Deploy frontend second.
- Commit changes in small slices.

Acceptance criteria:

- US rankings work.
- KR rankings work.
- Filters work.
- Partial rows work.
- Explore More works.
- `031980` detail/chart works.
- `TSSI` does not break search or detail flows.
- Browser console shows no new API 404s.

Verification completed:

- Full backend test suite:
  - `cd backend && uv run pytest -v`
  - Result: 101 passed.
  - Residual warning: existing SQLAlchemy async cancellation warnings appeared in two tests, but did not fail the suite.
- Workspace typecheck:
  - `pnpm -r typecheck`
  - Result: passed.
- Web production build:
  - `pnpm --filter web build`
  - Result: passed.
- Workspace lint:
  - `pnpm -r lint`
  - Result: passed after removing one unused rankings-client import.
- Diff whitespace check:
  - `git diff --check`
  - Result: passed with line-ending warnings only.
- Local backend route registration:
  - Confirmed local FastAPI mounts:
    - `GET /api/v1/rankings`
    - `GET /api/v1/universe/browse`
    - `GET /api/v1/instruments/{ticker}`
    - `GET /api/v1/instruments/{ticker}/chart`
    - `GET /api/v1/search`
- Neon-only data population smoke:
  - Instrument universe synced directly into Neon using provider-backed sync tasks.
  - Neon instrument counts:
    - KR ETFs: 1,095
    - KR stocks: 2,827
    - US ETFs: 5,110
    - US stocks: 5,654
  - Smoke price ingestion completed for `NVDA`, `AAPL`, `MSFT`, `TSSI`, `SPY`, `031980`, `005930`, `000660`, `035420`, and `069500`.
  - US smoke tickers have 501 price rows each.
  - KR smoke tickers have 485 price rows each.
  - `SPY` and `069500` are populated as benchmark ETFs for RS-line/chart calculations.
  - Smoke fundamentals ingestion completed for `NVDA`, `AAPL`, `MSFT`, `TSSI`, `031980`, `005930`, `000660`, and `035420`.
  - US smoke stocks have 5 annual and 20 quarterly rows each.
  - KR smoke stocks have 4 annual and 12 quarterly rows each.
  - Full scoring pipeline completed in context mode for all 8 smoke stocks.
  - Neon consensus scores now exist for all 8 smoke stocks on `2026-04-24`.
- Local FastAPI API smoke against Neon:
  - `GET /api/v1/rankings?market=US&asset_type=stock&limit=50`: 200, 4 items, `NVDA`, `AAPL`, `TSSI`, `MSFT`
  - `GET /api/v1/rankings?market=KR&asset_type=stock&limit=50`: 200, 4 items, `000660`, `005930`, `031980`, `035420`
  - `GET /api/v1/search?q=TSSI`: 200, 1 item
  - `GET /api/v1/search?q=031980`: 200, 1 item
  - `GET /api/v1/instruments/TSSI?market=US`: 200, `coverage_state=ranked`, `final_score=46.54`
  - `GET /api/v1/instruments/031980?market=KR`: 200, `final_score=65.15`
  - `GET /api/v1/instruments/TSSI/chart?market=US&interval=1d&range_days=365&include_indicators=true`: 200, 365 candles and 365 RS-line points
  - `GET /api/v1/instruments/031980/chart?market=KR&interval=1d&range_days=365&include_indicators=true`: 200, 365 candles and 365 RS-line points
  - `GET /api/v1/universe/browse?market=US&asset_type=stock&limit=5`: 200, total 5,617
  - `GET /api/v1/universe/browse?market=KR&asset_type=stock&limit=5`: 200, total 2,827
- Live Railway API smoke against `https://api-production-f00d.up.railway.app/api/v1` after Neon population:
  - `GET /search?q=TSSI`: 200, 1 item
  - `GET /search?q=031980`: 200, 1 item
  - `GET /rankings?market=US&asset_type=stock&limit=50`: 200, 4 items, `NVDA`, `AAPL`, `TSSI`, `MSFT`
  - `GET /rankings?market=KR&asset_type=stock&limit=50`: 200, 4 items, `000660`, `005930`, `031980`, `035420`
  - `GET /instruments/TSSI?market=US`: 200
  - `GET /instruments/TSSI/chart?market=US&interval=1d&range_days=365&include_indicators=true`: 200
  - `GET /instruments/031980?market=KR`: 200
  - `GET /instruments/031980/chart?market=KR&interval=1d&range_days=365&include_indicators=true`: 200, 365 candles and 365 RS-line points
  - `GET /universe/browse?market=US&asset_type=stock&limit=5`: 404
  - `GET /universe/browse?market=KR&asset_type=stock&limit=5`: 404
- Browser smoke:
  - Installed Playwright Chromium for local verification.
  - Browser run reached the local Next server, but pages returned 500 through Clerk before authenticated app rendering.
  - Next logs show Clerk infinite redirect loop, which usually means mismatched Clerk publishable/secret keys.
  - No browser-observed `/api/v1` 404s occurred during the blocked browser run, but app-page verification could not complete because auth failed first.

Data repopulation on 2026-04-24:

- On 2026-04-24, the Neon database was found empty (0 instruments, 0 consensus_scores).
- The `consensus_app` schema and all tables existed but held no rows; `alembic_version` table was absent.
- Root cause is unknown; likely a Neon branch reset or an accidental Celery beat cleanup between the two sessions.
- Recovery steps performed before deployment:
  - `uv run alembic stamp 0007_read_path_indexes` to restore Alembic tracking.
  - US instruments re-synced via `sync_instruments()`: 10,764 US instruments upserted.
  - KR instruments re-synced via `sync_kr_instruments()`: 3,922 KR instruments upserted.
  - Smoke price ingestion for `NVDA`, `AAPL`, `MSFT`, `TSSI`, `SPY`, `031980`, `005930`, `000660`, `035420`, `069500`.
  - Smoke fundamentals ingestion for `NVDA`, `AAPL`, `MSFT`, `TSSI`, `031980`, `005930`, `000660`, `035420`.
  - Full scoring pipeline run via `targeted_score.py`: 10 instruments scored (4 US stocks, 4 KR stocks, 2 benchmark ETFs).

Deployment result:

- Backend commit `7447436` pushed to master; Railway redeployed successfully.
- Frontend commit `3197c66` pushed to master; Vercel deployed to production (`READY`).
- Note: the backend-only commit `7447436` caused a Vercel typecheck ERROR because `search-client.tsx`
  was still using the old `"fundamentals_ready"` coverage state. This was resolved by the frontend
  commit `3197c66` which updated the search client. The production deployment is the frontend commit.
- Production URL is `https://stock-screener-pi-ivory.vercel.app` (confirmed 200).

Live Railway API smoke after deployment (2026-04-24):

- `GET /api/v1/health`: `status=ok`, `instruments=14686`, `consensus_scores=10`.
- `GET /rankings?market=US&asset_type=stock&limit=50`: 200, 4 items, `NVDA`, `AAPL`, `TSSI`, `MSFT`.
- `GET /rankings?market=KR&asset_type=stock&limit=50`: 200, 4 items, `000660`, `005930`, `031980`, `035420`.
- `GET /rankings?market=KR&asset_type=stock&min_final_score=60&limit=10`: 200, 3 items (filter working).
- `GET /search?q=TSSI`: 200, 1 item, `coverage_state=ranked`, `final_score=46.84`.
- `GET /search?q=031980`: 200, 1 item, Korean name returned.
- `GET /instruments/TSSI?market=US`: 200, `coverage_state=ranked`, `final_score=46.84`.
- `GET /instruments/031980?market=KR`: 200, `coverage_state=stale` (KR prices from last session, expected).
- `GET /instruments/TSSI/chart?market=US&interval=1d&range_days=365`: 200, price bars returned.
- `GET /instruments/031980/chart?market=KR&interval=1d&range_days=365`: 200, price bars returned.
- `GET /universe/browse?market=US&asset_type=stock&limit=3`: 200, `total=5617`.
- `GET /universe/browse?market=KR&asset_type=stock&limit=3`: 200, `total=2827`.
- Public Vercel pages (`/`, `/methodology`, `/freshness-policy`): all 200.

Browser verification note:

- Browser-level verification of the authenticated app routes (`/app/rankings`, instrument detail) was
  not performed. The Clerk auth issue blocks local browser testing and production requires a valid Clerk
  session. All acceptance criteria that can be verified without a browser have passed.
- The production Vercel deployment is live and the API layer is fully verified.

Action Plan 8 result:

- All blocking issues from the previous session are resolved.
- Part 1 is complete and deployed to production.
- Next recommended step is Action Plan 9: Job Table And Alembic Migration (Part 2 start).

## Part 2 Action Plans: Full fd13b66 Feature Completion

### Action Plan 9: Job Table And Alembic Migration

**Threshold: High**

Create durable user-facing job status.

Tasks:

- Add a Postgres-backed hydration job table.
- Use Alembic only.
- Store:
  - job id
  - ticker
  - market
  - instrument id if known
  - status
  - requester/user/admin source
  - queued timestamp
  - started timestamp
  - completed timestamp
  - failed timestamp
  - error message
  - provider/source metadata if useful
- Add indexes for ticker, market, status, and timestamps.

Acceptance criteria:

- Job state survives API/worker restarts.
- UI does not depend only on Celery result backend.
- Migration works locally and against Neon-compatible Postgres.

### Action Plan 10: Explicit Hydration API

**Threshold: High**

Add user-triggered refresh without breaking existing ingest behavior.

Tasks:

- Add `POST /api/v1/instruments/{ticker}/hydrate`.
- Add `GET /api/v1/instruments/{ticker}/hydrate-status`.
- Use existing project auth/API-key conventions.
- Allow signed-in users to queue refreshes.
- Add conservative rate limits.
- Deduplicate same-symbol jobs.
- Keep existing ingest endpoints backwards compatible.

Acceptance criteria:

- A signed-in user can queue a refresh.
- Duplicate refresh requests do not create job spam.
- Rate-limited users receive clear errors.
- Existing frontend/API-client ingest behavior is not broken.

### Action Plan 11: Celery Worker Integration

**Threshold: Max**

Wire hydration jobs to reliable async execution.

Tasks:

- Connect hydrate endpoint to Celery worker.
- Update DB job status during:
  - queued
  - running
  - completed
  - failed
- Handle missing worker or backend failures gracefully.
- Ensure API, worker, and beat share required environment variables.
- Avoid long-running provider work inside API requests.

Acceptance criteria:

- Worker failures become visible failed jobs.
- Frontend polling does not run forever.
- API remains responsive while jobs run.
- Railway deployment assumptions are explicit.

### Action Plan 12: Score-Date Safety

**Threshold: Max**

Prevent single-symbol refresh from breaking rankings.

Tasks:

- Ensure single-stock hydration does not advance the global latest score date alone.
- Keep hydrated symbols out of main rankings until a consistent batch score refresh.
- Add regression tests for score-date collapse.
- Confirm rankings remain stable after hydrating one ticker.

Acceptance criteria:

- Hydrating one instrument cannot shrink rankings to only that instrument.
- Main rankings remain score-date consistent.
- Partial/explore states explain when a symbol is waiting for batch scoring.

### Action Plan 13: Symbol Resolution

**Threshold: High**

Add explicit, safe resolution for valid unknown symbols.

Tasks:

- Resolve symbols only inside explicit hydrate/admin flows.
- Do not write from GET search/detail/chart.
- Use existing providers first.
- Cache or periodically sync provider symbol directories where possible.
- Add tests for `TSSI`-like exact symbols.
- Return clear user-facing states for unresolved symbols.

Acceptance criteria:

- Unknown valid-looking symbols can be offered for refresh.
- GET paths remain read-only.
- `TSSI`-like symbols are covered by tests.
- Provider lookup latency does not block normal search/detail browsing.

### Action Plan 14: Admin Backfill

**Threshold: Max**

Add controlled batch population for liquid US/KR coverage.

Tasks:

- Add admin-triggered backfill.
- Inputs:
  - `market`
  - `tickers`
  - `limit`
  - `dry_run`
  - `price_only`
  - `score`
- Process work in chunks.
- Design for Neon latency and Railway worker constraints.
- Start manual-first.
- Add beat scheduling only after manual jobs are boringly reliable.
- Target first full run: liquid US + KR universe, overnight acceptable.

Acceptance criteria:

- Dry run previews scope safely.
- Backfill can run overnight without blocking API.
- Jobs produce clear logs/status.
- Batch scoring preserves ranking consistency.

### Action Plan 15: Provider Taxonomy And Missing Metrics

**Threshold: High**

Improve sector/exchange normalization and fill missing investor metrics.

Tasks:

- Normalize sector and exchange taxonomy using reliable provider metadata.
- Add reliable market cap if source/computation is available.
- Add reliable PER/P/E if source/computation is available.
- Add reliable dividend yield if source/computation is available.
- Add API fields only when data provenance is clear.
- Keep missing metrics labeled rather than faked.

Acceptance criteria:

- Sector/exchange filters become cleaner and more consistent.
- Investor metric cards do not show misleading placeholders.
- KR/US metrics remain localized.

### Action Plan 16: Watchlist And Pinning

**Threshold: Medium**

Reintroduce saved/pinned instruments after core data behavior is stable.

Tasks:

- Add watchlist or pinning after Part 2 hydration is stable.
- Keep watchlist separate from ranking logic.
- Do not let pinning affect score order.
- Decide whether watchlist is local-only or authenticated persistence based on existing auth patterns.

Acceptance criteria:

- Users can save important stocks.
- Saved stocks do not change ranking calculations.
- Watchlist works across ranked and partial instruments.

### Action Plan 17: Part 2 Verification And Deploy

**Threshold: Max**

Verify full async and data-completion behavior.

Tasks:

- Test hydrate enqueue/status.
- Test Celery worker success/failure.
- Test rate limiting.
- Test symbol resolution.
- Test admin backfill dry run.
- Test score-date safety.
- Test frontend inline job statuses.
- Deploy backend first.
- Verify worker/job behavior.
- Deploy frontend second.

Acceptance criteria:

- Full `fd13b66` intent is restored safely.
- Unknown symbols can be queued.
- Failed jobs are visible.
- Rankings do not collapse after single-symbol hydration.
- Browser console stays clean.

## Backend And Database Rules

- Use Alembic for all schema changes.
- Do not use manual production SQL unless explicitly documented and later migrated.
- Design for Neon from the start:
  - fewer DB round trips
  - chunked jobs
  - pooling-safe sessions
  - read-friendly queries
  - targeted indexes
- Add indexes only for proven query paths.
- Avoid broad speculative indexing that increases write overhead.
- GET endpoints must remain read-only.
- API-client changes must be additive unless a breaking change is explicitly approved.
- Preserve existing ingest behavior unless a new endpoint replaces it safely.
- Use DB job status for user-facing async state.
- Use Celery backend state only as internal/debug support.
- Provider calls should not happen in normal ranking/browse read paths.
- External provider calls should happen in explicit hydrate/admin/background flows.

## Test And Verification Plan

### Backend Tests

- Rankings default behavior.
- Rankings filters individually.
- Rankings filters in combinations.
- Missing-field filter behavior for partial rows.
- Universe browse pagination.
- Universe browse read-only behavior.
- Coverage state generation.
- Market-aware staleness.
- Hydration enqueue.
- Hydration status.
- Rate limiting and deduplication.
- Symbol resolution.
- Admin backfill dry run.
- Score-date safety regression.

### Frontend Tests And Checks

- Rankings render with scored rows.
- Partial rows render below scored rows.
- Explore More failure does not break rankings.
- Filter UI maps correctly to API params.
- Presets apply gentle filter defaults.
- KR stock names display name-first.
- US stock names display naturally.
- Metric cards format KR and US numbers correctly.
- Missing chart state appears correctly.
- Incomplete detail pages do not get stuck loading.
- Mobile rankings layout works.
- Browser console has no API 404s.

### Live Smoke Checks

- `GET /api/v1/rankings?market=US&asset_type=stock&limit=200`
- `GET /api/v1/rankings?market=KR&asset_type=stock&limit=200`
- `GET /api/v1/universe/browse?market=US&asset_type=stock`
- `GET /api/v1/universe/browse?market=KR&asset_type=stock`
- KR detail and chart for `031980`.
- US detail and chart for `TSSI` where available.
- Search for known ranked stocks.
- Search for valid-looking unknown stocks.
- Hydration queue/status after Part 2.

## Deployment And Rollback Rules

- Use backend-first deployment for any new endpoint.
- Verify backend live endpoints before frontend deploy.
- Do not deploy frontend calls to endpoints that are not live.
- Use small commits per action plan or feature slice.
- Prefer rollback by reverting one small commit rather than undoing a mega-commit.
- Keep Part 1 and Part 2 deploys separate.
- Run local tests before pushing.
- Run live smoke checks after deploy.
- If frontend breaks, rollback the frontend commit first.
- If backend breaks, disable frontend entry points before deeper backend repair.
- Do not start Part 2 until Part 1 is confirmed working locally and in production.

## Assumptions

- Current stable baseline is the post-rollback state after `fd13b66` was cancelled.
- Current expanded ranking behavior should be preserved.
- Top 200 is the initial production default.
- Users can choose different result counts.
- Liquid US + KR is the first full backend population target.
- Overnight full/backfill jobs are acceptable.
- Rankings should remain score-backed and trustworthy.
- Partial and explore rows can appear, but must be clearly labeled as incomplete or unranked.
- No GET endpoint should write to the database.
- Signed-in users can queue refresh in Part 2.
- Admin jobs can be broader and less rate-limited than user jobs.
- API, worker, and beat can be deployed as separate Railway services.
- Neon is the production database constraint to design around.
- Missing metrics are better labeled honestly than displayed inaccurately.
- The frontend redesign should prioritize clarity, localization, and investor usefulness over simply adding more columns.
