"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, Layers3, Search, Sparkles } from "lucide-react";
import { FormEvent, useState } from "react";
import { UserButton } from "@clerk/nextjs";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/store";
import { useT } from "@/hooks/use-t";
import { ThemeToggle } from "@/components/theme-toggle";

export function AppNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const lang = useUIStore((state) => state.lang);
  const setLang = useUIStore((state) => state.setLang);
  const { t } = useT();

  const navItems = [
    { href: "/rankings", label: t("nav.rankings"), icon: Layers3 },
    { href: "/app/search", label: t("nav.search"), icon: Search },
    { href: "/app/alerts", label: t("nav.alerts"), icon: Bell },
  ] as const;

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleaned = query.trim();
    if (cleaned) router.push(`/app/search?q=${encodeURIComponent(cleaned)}`);
  }

  return (
    <>
      <header
        className="sticky top-0 z-40 border-b"
        style={{
          background: "var(--rv-header-bg)",
          borderColor: "var(--rv-header-border)",
          boxShadow: "var(--rv-header-shadow)",
          backdropFilter: "blur(18px)",
        }}
      >
        <div className="app-shell flex h-16 items-center gap-3">
          <Link href="/rankings" className="motion-press flex min-h-11 shrink-0 items-center gap-2">
            <span className="flex size-10 items-center justify-center rounded-xl bg-[var(--rv-primary)] text-white shadow-[0_8px_18px_rgba(37,99,235,0.14)]">
              <Sparkles className="size-4" />
            </span>
            <span className="font-heading text-lg font-bold uppercase text-[var(--rv-ink)]">
              Consensus
            </span>
          </Link>

          <form onSubmit={submitSearch} className="hidden min-w-0 flex-1 md:block">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-[var(--rv-stone)]" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("search.placeholder")}
                className="h-11 w-full rounded-full border bg-[var(--rv-surface-elevated)] pl-11 pr-5 text-sm font-medium text-[var(--rv-ink)] outline-none transition-colors placeholder:text-[var(--rv-stone)] focus:border-[rgba(37,99,235,0.42)]"
                style={{ borderColor: "var(--rv-header-border)" }}
              />
            </label>
          </form>

          <nav className="hidden items-center gap-1 lg:flex" aria-label="Main navigation">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="segmented-pill"
                  data-active={active ? "true" : undefined}
                >
                  <Icon className="size-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-2">
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

            <Link
              href="/app/search"
              className="motion-press flex size-11 items-center justify-center rounded-full border text-[var(--rv-mute)] transition-colors hover:text-[var(--rv-ink)] md:hidden"
              style={{
                borderColor: "var(--rv-header-border)",
                background: "var(--rv-header-bg)",
              }}
              aria-label="Search"
            >
              <Search className="size-4" />
            </Link>

            <UserButton />
          </div>
        </div>
      </header>

      {/* Mobile bottom nav */}
      <nav
        className="fixed inset-x-3 bottom-3 z-50 rounded-[1.35rem] border p-1.5 shadow-[0_14px_34px_rgba(15,23,42,0.16)] md:hidden"
        style={{
          background: "var(--rv-nav-bottom-bg)",
          borderColor: "var(--rv-header-border)",
        }}
        aria-label="Mobile main navigation"
      >
        <div className="grid grid-cols-3 gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "motion-press flex min-h-12 flex-col items-center justify-center gap-1 rounded-2xl px-2 py-2 text-xs font-bold uppercase tracking-[0.04em] transition-colors",
                  active
                    ? "bg-[rgba(15,186,157,0.13)] text-[#075e54] dark:text-[#2dd4bf]"
                    : "text-[var(--rv-stone)] hover:text-[var(--rv-ink)]"
                )}
              >
                <Icon className="size-[18px]" />
                <span className="leading-none">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
