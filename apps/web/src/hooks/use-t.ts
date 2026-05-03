"use client";

/**
 * useT — translation hook.
 *
 * Usage:
 *   const { t, lang } = useT();
 *   t("nav.rankings")  // → "Rankings" or "랭킹"
 *
 * Stock names (name, name_kr) and tickers are NOT translated — they are data.
 * Only UI chrome strings defined in src/lib/i18n.ts are covered.
 *
 * Hydration safety:
 *   Zustand persist reads from localStorage, which is unavailable on the server.
 *   The server always renders lang="en". Before the client store has rehydrated
 *   from localStorage, we must also render "en" — otherwise React throws a
 *   hydration mismatch when a Korean user loads the page.
 *   We use useSyncExternalStore to detect the hydrated state safely.
 */

import { useSyncExternalStore } from "react";
import { useUIStore } from "@/lib/store";
import { translations, type TranslationKey } from "@/lib/i18n";

function subscribe(cb: () => void) {
  return useUIStore.persist.onFinishHydration(cb);
}

function getHydrated() {
  return useUIStore.persist.hasHydrated();
}

function getServerHydrated() {
  return false; // server always returns "not hydrated"
}

export function useT() {
  const lang        = useUIStore((state) => state.lang);
  const isHydrated  = useSyncExternalStore(subscribe, getHydrated, getServerHydrated);

  // Before hydration: fall back to "en" to match server-rendered HTML.
  const activeLang  = isHydrated ? lang : "en";

  function t(key: TranslationKey): string {
    return translations[activeLang][key] ?? translations["en"][key] ?? key;
  }

  return { t, lang: activeLang };
}
