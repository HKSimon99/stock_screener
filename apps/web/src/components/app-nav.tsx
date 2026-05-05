"use client";

/**
 * AppNav — authenticated research desk header + mobile bottom nav.
 *
 * Layout:
 *  - Sticky true-black header: Wordmark | Search (md+) | Lang toggle | UserButton
 *  - Sub-nav pills below header bar (desktop only)
 *  - Mobile: floating bottom nav-rail (5 tabs), lang toggle in header
 *
 * Mobile thumb-zone principle:
 *  - Bottom nav: primary navigation (thumb zone)
 *  - Lang toggle: top-right header (reachable, rarely changed)
 *  - Search: both top-right icon (mobile) and center bar (desktop)
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, BookOpen, Layers3, Search } from "lucide-react";
import { FormEvent, useState } from "react";
import { UserButton } from "@clerk/nextjs";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/store";
import { useT } from "@/hooks/use-t";

export function AppNav() {
  const pathname      = usePathname();
  const router        = useRouter();
  const [query, setQuery] = useState("");
  const lang          = useUIStore((state) => state.lang);
  const setLang       = useUIStore((state) => state.setLang);
  const { t }         = useT();

  const NAV_ITEMS = [
    { href: "/rankings",       label: t("nav.rankings"),   icon: Layers3  },
    { href: "/app/search",     label: t("nav.search"),     icon: Search   },
    { href: "/app/strategies", label: t("nav.strategies"), icon: BookOpen },
    { href: "/app/alerts",     label: t("nav.alerts"),     icon: Bell     },
  ] as const;

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleaned = query.trim();
    if (!cleaned) return;
    router.push(`/app/search?q=${encodeURIComponent(cleaned)}`);
  }

  return (
    <>
      {/* ── Sticky header ──────────────────────────────────────────── */}
      <header
        className="sticky top-0 z-40 w-full"
        style={{
          background: "#000000",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <div className="app-shell flex h-16 items-center gap-3">

          {/* Wordmark */}
          <Link
            href="/rankings"
            className="shrink-0 font-heading text-xl font-semibold uppercase text-white"
            style={{ letterSpacing: "-0.02em" }}
          >
            Consensus
          </Link>

          {/* Search bar — grows to fill space (desktop only) */}
          <form
            onSubmit={submitSearch}
            className="hidden flex-1 md:block"
          >
            <label className="relative block">
              <Search
                className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-white/40"
                style={{ width: 16, height: 16 }}
              />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("search.placeholder")}
                className="w-full rounded-full border py-2.5 pl-11 pr-5 text-sm text-white outline-none transition-colors placeholder:text-white/35"
                style={{
                  background: "#16181a",
                  borderColor: "rgba(255,255,255,0.10)",
                  height: 40,
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = "#494fdf")}
                onBlur={(e)  => (e.currentTarget.style.borderColor = "rgba(255,255,255,0.10)")}
              />
            </label>
          </form>

          {/* Right cluster */}
          <div className="ml-auto flex items-center gap-2">

            {/* KO / EN language toggle — visible on all screen sizes */}
            <div
              className="flex items-center rounded-full border"
              style={{
                borderColor: "rgba(255,255,255,0.12)",
                background:  "#16181a",
                padding:     2,
              }}
            >
              {(["en", "ko"] as const).map((l) => (
                <button
                  key={l}
                  type="button"
                  onClick={() => setLang(l)}
                  className="rounded-full font-semibold transition-colors"
                  style={{
                    fontSize:      "0.6rem",
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    padding:       "5px 10px",
                    minWidth:      36,
                    background:    lang === l ? "#494fdf" : "transparent",
                    color:         lang === l ? "#ffffff" : "rgba(255,255,255,0.45)",
                  }}
                >
                  {l === "en" ? "EN" : "KO"}
                </button>
              ))}
            </div>

            {/* Mobile search shortcut */}
            <Link
              href="/app/search"
              className="flex size-9 items-center justify-center rounded-full text-white/60 transition-colors hover:text-white md:hidden"
              style={{ background: "#16181a" }}
              aria-label="Search"
            >
              <Search style={{ width: 16, height: 16 }} />
            </Link>

            <UserButton />
          </div>
        </div>

        {/* ── Sub-nav pills (desktop) ──────────────────────────────── */}
        <div className="app-shell hidden pb-3 md:block">
          <div className="flex flex-wrap gap-1.5">
            {NAV_ITEMS.map((item) => {
              const Icon   = item.icon;
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-medium transition-colors",
                    active
                      ? "border-[#494fdf] bg-[rgba(73,79,223,0.18)] text-white"
                      : "text-white/55 hover:text-white"
                  )}
                  style={{
                    borderColor: active ? "#494fdf" : "rgba(255,255,255,0.10)",
                    background:  active ? "rgba(73,79,223,0.18)" : "#16181a",
                  }}
                >
                  <Icon style={{ width: 14, height: 14 }} />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      </header>

      {/* ── Mobile bottom nav-rail ─────────────────────────────────── */}
      <nav
        className="fixed inset-x-2 bottom-3 z-50 md:hidden"
        style={{ borderRadius: 22, background: "#16181a", border: "1px solid rgba(255,255,255,0.10)" }}
        aria-label="Main navigation"
      >
        <div className="grid grid-cols-5 p-1.5 gap-0.5">
          {NAV_ITEMS.map((item) => {
            const Icon   = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex flex-col items-center gap-1 rounded-[15px] px-1 py-2.5 transition-colors",
                  active
                    ? "bg-[rgba(73,79,223,0.22)] text-white"
                    : "text-white/45 hover:text-white"
                )}
              >
                <Icon style={{ width: 18, height: 18 }} />
                <span style={{ fontSize: "0.55rem", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", lineHeight: 1 }}>
                  {item.label}
                </span>
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
