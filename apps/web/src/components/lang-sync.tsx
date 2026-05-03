"use client";

/**
 * LangSync — keeps <html lang="..."> in sync with the user's language preference.
 *
 * layout.tsx is a Server Component and cannot read Zustand state, so the html
 * lang attribute is hardcoded to "en" at render time. This component runs on
 * the client after hydration and updates the attribute whenever the user
 * switches language via the KO/EN toggle.
 *
 * Usage: render once inside <Providers> in layout.tsx.
 */

import { useEffect } from "react";
import { useUIStore } from "@/lib/store";

export function LangSync() {
  const lang = useUIStore((s) => s.lang);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  return null;
}
