import { create } from "zustand";
import { persist } from "zustand/middleware";

type Market = "US" | "KR";
type AssetType = "stock" | "etf";

export interface SavedInstrument {
  ticker: string;
  market: Market;
  name?: string;
  exchange?: string;
}

interface UIStore {
  market: Market;
  assetType: AssetType;
  conviction: string;
  recentSearches: SavedInstrument[];
  pinnedInstruments: SavedInstrument[];
  chartInterval: "1d" | "1w" | "1m";
  chartRangeDays: number;
  setMarket: (m: Market) => void;
  setAssetType: (t: AssetType) => void;
  setConviction: (c: string) => void;
  setChartInterval: (interval: "1d" | "1w" | "1m") => void;
  setChartRangeDays: (days: number) => void;
  addRecentSearch: (instrument: SavedInstrument) => void;
  togglePinnedInstrument: (instrument: SavedInstrument) => void;
  isPinned: (ticker: string, market: Market) => boolean;
}

function dedupe(
  entries: SavedInstrument[],
  nextEntry: SavedInstrument,
  limit: number
): SavedInstrument[] {
  const filtered = entries.filter(
    (entry) =>
      !(
        entry.ticker.toUpperCase() === nextEntry.ticker.toUpperCase() &&
        entry.market === nextEntry.market
      )
  );
  return [nextEntry, ...filtered].slice(0, limit);
}

export const useUIStore = create<UIStore>()(
  persist(
    (set, get) => ({
      market: "US",
      assetType: "stock",
      conviction: "",
      recentSearches: [],
      pinnedInstruments: [],
      chartInterval: "1d",
      chartRangeDays: 350,
      setMarket: (market) => set({ market }),
      setAssetType: (assetType) => set({ assetType }),
      setConviction: (conviction) => set({ conviction }),
      setChartInterval: (chartInterval) => set({ chartInterval }),
      setChartRangeDays: (chartRangeDays) => set({ chartRangeDays }),
      addRecentSearch: (instrument) =>
        set((state) => ({
          recentSearches: dedupe(state.recentSearches, instrument, 10),
        })),
      togglePinnedInstrument: (instrument) =>
        set((state) => {
          const exists = state.pinnedInstruments.some(
            (entry) =>
              entry.ticker.toUpperCase() === instrument.ticker.toUpperCase() &&
              entry.market === instrument.market
          );
          return {
            pinnedInstruments: exists
              ? state.pinnedInstruments.filter(
                  (entry) =>
                    !(
                      entry.ticker.toUpperCase() === instrument.ticker.toUpperCase() &&
                      entry.market === instrument.market
                    )
                )
              : dedupe(state.pinnedInstruments, instrument, 12),
          };
        }),
      isPinned: (ticker, market) =>
        get().pinnedInstruments.some(
          (entry) =>
            entry.ticker.toUpperCase() === ticker.toUpperCase() &&
            entry.market === market
        ),
    }),
    {
      name: "consensus-ui-state",
      partialize: (state) => ({
        market: state.market,
        assetType: state.assetType,
        conviction: state.conviction,
        recentSearches: state.recentSearches,
        pinnedInstruments: state.pinnedInstruments,
        chartInterval: state.chartInterval,
        chartRangeDays: state.chartRangeDays,
      }),
    }
  )
);
