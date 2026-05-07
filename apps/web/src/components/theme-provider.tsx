"use client";

import { useEffect } from "react";
import { useUIStore } from "@/lib/store";

/**
 * Applies the persisted theme preference to <html> on every render.
 * Render this once near the top of the component tree (inside <Providers>).
 * The anti-FOUC inline script in root layout.tsx handles the first paint.
 */
export function ThemeProvider() {
  const theme = useUIStore((state) => state.theme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  return null;
}
