/**
 * useT — translation hook.
 *
 * Usage:
 *   const { t, lang } = useT();
 *   t("nav.rankings")  // → "Rankings" or "랭킹"
 *
 * Stock names (name, name_kr) and tickers are NOT translated — they are data.
 * Only UI chrome strings defined in src/lib/i18n.ts are covered.
 */

import { useUIStore } from "@/lib/store";
import { translations, type TranslationKey } from "@/lib/i18n";

export function useT() {
  const lang = useUIStore((state) => state.lang);

  function t(key: TranslationKey): string {
    return translations[lang][key] ?? translations["en"][key] ?? key;
  }

  return { t, lang };
}
