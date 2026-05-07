"use client";

import { Moon, Sun } from "lucide-react";
import { useUIStore } from "@/lib/store";
import { cn } from "@/lib/utils";

interface ThemeToggleProps {
  className?: string;
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const theme = useUIStore((state) => state.theme);
  const setTheme = useUIStore((state) => state.setTheme);

  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      className={cn(
        "motion-press flex size-11 items-center justify-center rounded-full border transition-colors",
        "border-[var(--rv-header-border)] bg-[var(--rv-header-bg)] text-[var(--rv-mute)] hover:text-[var(--rv-ink)]",
        className
      )}
    >
      {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );
}
