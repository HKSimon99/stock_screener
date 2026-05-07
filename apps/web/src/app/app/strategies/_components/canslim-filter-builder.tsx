"use client";

/**
 * CanslimTab — CANSLIM rankings with an optional advanced filter builder.
 *
 * Default view: standard fetchStrategyRankings("canslim", "US") list.
 * When filters are applied: switches to fetchFilteredRankings() which
 * calls POST /api/v1/filters/query with the Clerk bearer token.
 *
 * Filter controls exposed:
 *  • CANSLIM composite score min   → min_canslim
 *  • Piotroski F-score min         → min_piotroski_f
 *  • Minervini criteria passing    → minervini_criteria_min
 *  • Weinstein Stage 2 gate toggle → weinstein_stage
 *  • RS Line New High toggle       → rs_line_new_high
 *
 * Three presets wire these quickly: Growth / Quality / Momentum.
 */

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { SlidersHorizontal, ChevronDown, ChevronUp, X } from "lucide-react";
import {
  fetchStrategyRankings,
  fetchFilteredRankings,
  type AdvancedFilterQuery,
  type StrategyRankingsResponse,
  type RankingItem,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { RankingRow } from "@/components/ranking-row";
import { useT } from "@/hooks/use-t";

// ── Preset definitions ────────────────────────────────────────────────────────

type PresetKey = "Growth" | "Quality" | "Momentum";

interface FilterState {
  minCanslim:              number;   // 0–100
  minPiotroskiF:           number;   // 0–9
  minMinerviniCriteria:    number;   // 0–8
  requireWeinsteinStage2:  boolean;
  requireRsLineNewHigh:    boolean;
}

const EMPTY_FILTERS: FilterState = {
  minCanslim:              0,
  minPiotroskiF:           0,
  minMinerviniCriteria:    0,
  requireWeinsteinStage2:  false,
  requireRsLineNewHigh:    false,
};

const PRESETS: Record<PresetKey, FilterState> = {
  Growth: {
    minCanslim:              65,
    minPiotroskiF:           5,
    minMinerviniCriteria:    5,
    requireWeinsteinStage2:  true,
    requireRsLineNewHigh:    false,
  },
  Quality: {
    minCanslim:              50,
    minPiotroskiF:           7,
    minMinerviniCriteria:    4,
    requireWeinsteinStage2:  false,
    requireRsLineNewHigh:    false,
  },
  Momentum: {
    minCanslim:              45,
    minPiotroskiF:           4,
    minMinerviniCriteria:    5,
    requireWeinsteinStage2:  true,
    requireRsLineNewHigh:    true,
  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function filterStateToQuery(f: FilterState): AdvancedFilterQuery {
  const q: AdvancedFilterQuery = { market: "US", limit: 50 };
  if (f.minCanslim > 0)           q.min_canslim           = f.minCanslim;
  if (f.minPiotroskiF > 0)        q.min_piotroski_f       = f.minPiotroskiF;
  if (f.minMinerviniCriteria > 0) q.minervini_criteria_min = f.minMinerviniCriteria;
  if (f.requireWeinsteinStage2)   q.weinstein_stage        = ["2_early", "2_mid", "2_late"];
  if (f.requireRsLineNewHigh)     q.rs_line_new_high       = true;
  return q;
}

function activeFilterCount(f: FilterState): number {
  return (
    (f.minCanslim > 0 ? 1 : 0) +
    (f.minPiotroskiF > 0 ? 1 : 0) +
    (f.minMinerviniCriteria > 0 ? 1 : 0) +
    (f.requireWeinsteinStage2 ? 1 : 0) +
    (f.requireRsLineNewHigh ? 1 : 0)
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SliderRow({
  label,
  value,
  min,
  max,
  step = 1,
  format = (v: number) => String(v),
  onChange,
}: {
  label:    string;
  value:    number;
  min:      number;
  max:      number;
  step?:    number;
  format?:  (v: number) => string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[0.68rem] uppercase tracking-widest text-faint">{label}</span>
        <span className="font-mono text-[0.72rem] text-white">
          {value === min ? "—" : `≥ ${format(value)}`}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-white/10 accent-[oklch(0.78_0.11_84)]"
      />
      <div className="flex justify-between text-[0.58rem] text-faint/60">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}

function ToggleRow({
  label,
  description,
  value,
  onChange,
}: {
  label:       string;
  description: string;
  value:       boolean;
  onChange:    (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className={cn(
        "motion-press flex w-full items-start justify-between rounded-[0.9rem] border px-3 py-2.5 text-left transition-colors",
        value
          ? "border-[oklch(0.78_0.11_84_/_0.4)] bg-[oklch(0.78_0.11_84_/_0.1)] text-white"
          : "border-white/8 text-faint hover:border-white/15 hover:text-quiet"
      )}
    >
      <div>
        <div className="text-[0.7rem] uppercase tracking-widest">{label}</div>
        <div className="mt-0.5 text-[0.62rem] text-faint">{description}</div>
      </div>
      <div
        className={cn(
          "mt-0.5 h-4 w-4 shrink-0 rounded-full border transition-colors",
          value
            ? "border-[oklch(0.78_0.11_84)] bg-[oklch(0.78_0.11_84)]"
            : "border-white/20 bg-transparent"
        )}
      />
    </button>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface CanslimTabProps {
  initialData?: StrategyRankingsResponse;
}

export function CanslimTab({ initialData }: CanslimTabProps) {
  const { getToken } = useAuth();
  const { t } = useT();

  const [panelOpen, setPanelOpen]       = useState(false);
  const [draft, setDraft]               = useState<FilterState>(EMPTY_FILTERS);
  const [applied, setApplied]           = useState<FilterState | null>(null);
  const [activePreset, setActivePreset] = useState<PresetKey | null>(null);

  // ── Base CANSLIM list (always fetched, shown when no filters applied) ──────
  const { data: baseData, isFetching: baseFetching } = useQuery({
    queryKey:    ["strategy-rankings", "canslim", "US"],
    queryFn:     () => fetchStrategyRankings("canslim", "US"),
    initialData,
    staleTime:   60_000,
  });

  // ── Filtered results (only when Apply has been clicked) ───────────────────
  const { data: filteredData, isFetching: filterFetching, error: filterError } = useQuery({
    queryKey: ["canslim-filter", applied],
    queryFn:  async () => {
      const token = await getToken();
      return fetchFilteredRankings(filterStateToQuery(applied!), token ?? undefined);
    },
    enabled:   applied !== null,
    staleTime: 60_000,
  });

  // ── Handlers ──────────────────────────────────────────────────────────────
  const applyFilters = useCallback(() => {
    setApplied({ ...draft });
    setPanelOpen(false);
  }, [draft]);

  const resetFilters = useCallback(() => {
    setDraft(EMPTY_FILTERS);
    setApplied(null);
    setActivePreset(null);
  }, []);

  function applyPreset(key: PresetKey) {
    setDraft(PRESETS[key]);
    setActivePreset(key);
  }

  function patchDraft(patch: Partial<FilterState>) {
    setDraft((prev) => ({ ...prev, ...patch }));
    setActivePreset(null); // user deviated from preset
  }

  const filterCount = activeFilterCount(applied ?? EMPTY_FILTERS);
  const showFiltered = applied !== null;

  // Items to render
  const items: RankingItem[] = showFiltered
    ? (filteredData?.items ?? [])
    : [];

  const baseItems = baseData?.items ?? [];

  return (
    <div className="space-y-3">
      {/* ── Filter panel toggle ─────────────────────────────────────────── */}
      <div className="surface-panel motion-panel-in overflow-hidden rounded-[1.45rem]">
        {/* Toggle header */}
        <button
          type="button"
          onClick={() => setPanelOpen((v) => !v)}
          className="motion-press flex w-full items-center justify-between px-5 py-4"
        >
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="size-3.5 text-faint" />
            <span className="text-[0.72rem] uppercase tracking-[0.14em] text-quiet">
              {t("canslim.advancedFilters")}
            </span>
            {filterCount > 0 && (
              <span className="rounded-full bg-[oklch(0.78_0.11_84_/_0.25)] px-2 py-0.5 text-[0.6rem] text-[oklch(0.88_0.12_85)]">
                {filterCount} active
              </span>
            )}
          </div>
          {panelOpen ? (
            <ChevronUp className="size-3.5 text-faint" />
          ) : (
            <ChevronDown className="size-3.5 text-faint" />
          )}
        </button>

        {/* Expanded panel */}
        {panelOpen && (
          <div className="motion-panel-in border-t border-white/6 px-5 pb-5 pt-4">
            {/* Presets */}
            <div className="mb-5">
              <div className="mb-2 text-[0.62rem] uppercase tracking-widest text-faint">
                {t("canslim.presets")}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {(Object.keys(PRESETS) as PresetKey[]).map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => applyPreset(key)}
                    className={cn(
                      "motion-press rounded-full border px-3 py-1.5 text-[0.65rem] uppercase tracking-[0.14em] transition-colors",
                      activePreset === key
                        ? "border-[oklch(0.78_0.11_84_/_0.5)] bg-[oklch(0.78_0.11_84_/_0.18)] text-white"
                        : "border-white/10 text-faint hover:border-white/20 hover:text-quiet"
                    )}
                  >
                    {key}
                  </button>
                ))}
              </div>
            </div>

            {/* Sliders */}
            <div className="mb-5 grid gap-5 sm:grid-cols-3">
              <SliderRow
                label={t("canslim.scoreLabel")}
                value={draft.minCanslim}
                min={0}
                max={100}
                step={5}
                onChange={(v) => patchDraft({ minCanslim: v })}
              />
              <SliderRow
                label={t("canslim.piotroskiLabel")}
                value={draft.minPiotroskiF}
                min={0}
                max={9}
                onChange={(v) => patchDraft({ minPiotroskiF: v })}
              />
              <SliderRow
                label={t("canslim.minerviniLabel")}
                value={draft.minMinerviniCriteria}
                min={0}
                max={8}
                format={(v) => `${v}/8`}
                onChange={(v) => patchDraft({ minMinerviniCriteria: v })}
              />
            </div>

            {/* Toggles */}
            <div className="mb-5 grid gap-2 sm:grid-cols-2">
              <ToggleRow
                label={t("canslim.weinsteinLabel")}
                description={t("canslim.weinsteinDesc")}
                value={draft.requireWeinsteinStage2}
                onChange={(v) => patchDraft({ requireWeinsteinStage2: v })}
              />
              <ToggleRow
                label={t("canslim.rsLineLabel")}
                description={t("canslim.rsLineDesc")}
                value={draft.requireRsLineNewHigh}
                onChange={(v) => patchDraft({ requireRsLineNewHigh: v })}
              />
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-2">
              {(applied !== null || activeFilterCount(draft) > 0) && (
                <button
                  type="button"
                  onClick={resetFilters}
                  className="motion-press flex items-center gap-1.5 rounded-full border border-white/8 px-4 py-2 text-[0.65rem] uppercase tracking-[0.14em] text-faint transition-colors hover:text-white"
                >
                  <X className="size-3" />
                  {t("canslim.reset")}
                </button>
              )}
              <button
                type="button"
                onClick={applyFilters}
                className="motion-press rounded-full bg-[oklch(0.78_0.11_84_/_0.25)] px-5 py-2 text-[0.65rem] uppercase tracking-[0.14em] text-white transition-colors hover:bg-[oklch(0.78_0.11_84_/_0.35)]"
              >
                {t("canslim.apply")}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Active filter summary (when panel is closed) ────────────────── */}
      {!panelOpen && showFiltered && (
        <div className="motion-panel-in flex items-center justify-between rounded-[1rem] border border-[oklch(0.78_0.11_84_/_0.3)] bg-[oklch(0.78_0.11_84_/_0.08)] px-4 py-2">
          <span className="text-[0.65rem] text-[oklch(0.88_0.12_85)]">
            {filterCount} {t("canslim.advancedFilters").toLowerCase()}
            {filteredData && ` · ${filteredData.total}`}
            {filterFetching && ` · ${t("alerts.refreshing")}`}
          </span>
          <button
            type="button"
            onClick={resetFilters}
            className="motion-press flex items-center gap-1 text-[0.62rem] text-faint transition-colors hover:text-white"
          >
            <X className="size-3" />
            {t("canslim.clear")}
          </button>
        </div>
      )}

      {/* ── Error state ────────────────────────────────────────────────── */}
      {filterError && (
        <div className="rounded-[1rem] border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-300">
          {t("canslim.filterError")}
        </div>
      )}

      {/* ── Results ────────────────────────────────────────────────────── */}
      <div className="space-y-2">
        {(filterFetching || baseFetching) && !showFiltered && !baseData && (
          <div className="surface-panel rounded-[1.65rem] px-5 py-8 text-center text-sm text-quiet">
            {t("ui.loading")}
          </div>
        )}

        {showFiltered
          ? items.map((item) => (
              <RankingRow
                key={`${item.market}-${item.ticker}`}
                item={{
                  rank:               item.rank,
                  ticker:             item.ticker,
                  name:               item.name,
                  market:             item.market,
                  exchange:           item.exchange,
                  conviction_level:   item.conviction_level,
                  final_score:        item.final_score,
                  strategy_pass_count: item.strategy_pass_count,
                  regime_warning:     item.regime_warning,
                }}
              />
            ))
          : baseItems.map((item) => (
              <RankingRow
                key={`${item.market}-${item.ticker}`}
                item={{
                  rank:        item.rank,
                  ticker:      item.ticker,
                  name:        item.name,
                  market:      item.market,
                  final_score: item.score ?? 0,
                }}
              />
            ))}

        {showFiltered && !filterFetching && items.length === 0 && (
          <div className="surface-panel rounded-[1.65rem] px-5 py-8 text-center text-sm text-quiet">
            {t("canslim.noResults")}
          </div>
        )}

        {!showFiltered && !baseFetching && baseItems.length === 0 && (
          <div className="surface-panel rounded-[1.65rem] px-5 py-8 text-center text-sm text-quiet">
            {t("canslim.noBase")}
          </div>
        )}
      </div>
    </div>
  );
}
