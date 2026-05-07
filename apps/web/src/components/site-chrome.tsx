"use client";

import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { useUIStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { useT } from "@/hooks/use-t";
import type { TranslationKey } from "@/lib/i18n";

export function SiteChrome() {
  const lang = useUIStore((state) => state.lang);
  const setLang = useUIStore((state) => state.setLang);
  const { t } = useT();

  const SITE_LINKS: Array<{ href: string; labelKey: TranslationKey }> = [
    { href: "/methodology",     labelKey: "nav.methodology" },
    { href: "/data-sources",    labelKey: "nav.dataSources" },
    { href: "/freshness-policy", labelKey: "nav.freshness" },
    { href: "/disclosures",     labelKey: "nav.disclosures" },
  ];

  return (
    <header
      className="sticky top-0 z-50 border-b"
      style={{
        background: "var(--rv-header-bg)",
        borderColor: "var(--rv-header-border)",
        boxShadow: "var(--rv-header-shadow)",
        backdropFilter: "blur(18px)",
      }}
    >
      <div className="app-shell flex h-16 items-center justify-between gap-4">
        <Link href="/" className="motion-press flex min-h-11 shrink-0 items-center gap-2">
          <span className="flex size-10 items-center justify-center rounded-xl bg-[var(--rv-primary)] text-white shadow-[0_8px_18px_rgba(37,99,235,0.14)]">
            <Sparkles className="size-4" />
          </span>
          <span className="font-heading text-lg font-bold uppercase text-[var(--rv-ink)]">
            Consensus
          </span>
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          {SITE_LINKS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="motion-press inline-flex min-h-11 items-center text-sm font-semibold text-[var(--rv-mute)] transition-colors hover:text-[var(--rv-ink)]"
            >
              {t(item.labelKey)}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          {/* Language toggle */}
          <div
            className="flex h-12 items-center rounded-full border p-0.5"
            style={{
              background: "var(--rv-lang-toggle-bg)",
              borderColor: "var(--rv-header-border)",
            }}
          >
            {(["en", "ko"] as const).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setLang(item)}
                className={cn(
                  "h-11 min-w-11 rounded-full px-2 text-xs font-bold uppercase tracking-[0.08em] transition-colors",
                  lang === item
                    ? "bg-[var(--rv-ink)] text-[var(--rv-canvas-light)]"
                    : "text-[var(--rv-stone)] hover:text-[var(--rv-ink)]"
                )}
              >
                {item}
              </button>
            ))}
          </div>

          <ThemeToggle />

          <Link href="/rankings" transitionTypes={["nav-forward"]} className="btn-primary shrink-0 px-4 py-2 text-sm">
            {t("nav.openApp")}
            <ArrowRight className="size-4" />
          </Link>
        </div>
      </div>
    </header>
  );
}
