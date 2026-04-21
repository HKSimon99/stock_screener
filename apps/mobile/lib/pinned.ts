import { storage } from "@/lib/storage";

const PINNED_INSTRUMENTS_KEY = "pinned-instruments";

export type PinnedInstrument = {
  ticker: string;
  market: "US" | "KR";
  name: string;
  name_kr?: string;
};

function readPinnedInstruments(): PinnedInstrument[] {
  const raw = storage.getString(PINNED_INSTRUMENTS_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw) as PinnedInstrument[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writePinnedInstruments(items: PinnedInstrument[]) {
  storage.set(PINNED_INSTRUMENTS_KEY, JSON.stringify(items));
}

export function getPinnedInstruments(): PinnedInstrument[] {
  return readPinnedInstruments();
}

export function isPinnedInstrument(ticker: string, market: "US" | "KR"): boolean {
  return readPinnedInstruments().some(
    (item) => item.ticker === ticker && item.market === market
  );
}

export function togglePinnedInstrument(instrument: PinnedInstrument): boolean {
  const items = readPinnedInstruments();
  const exists = items.some(
    (item) => item.ticker === instrument.ticker && item.market === instrument.market
  );

  if (exists) {
    writePinnedInstruments(
      items.filter(
        (item) => !(item.ticker === instrument.ticker && item.market === instrument.market)
      )
    );
    return false;
  }

  writePinnedInstruments([
    instrument,
    ...items.filter(
      (item) => !(item.ticker === instrument.ticker && item.market === instrument.market)
    ),
  ]);
  return true;
}
