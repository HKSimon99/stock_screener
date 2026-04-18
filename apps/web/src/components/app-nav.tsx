"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, Layers3, Radar, Search, Star } from "lucide-react";
import { FormEvent, useState } from "react";
import { UserButton } from "@clerk/nextjs";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/store";

const NAV_ITEMS = [
  { href: "/app/rankings", label: "Rankings", icon: Layers3 },
  { href: "/app/search", label: "Search", icon: Search },
  { href: "/app/alerts", label: "Alerts", icon: Bell },
  { href: "/app/market-regime", label: "Regime", icon: Radar },
] as const;

export function AppNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const pinnedCount = useUIStore((state) => state.pinnedInstruments.length);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleaned = query.trim();
    if (!cleaned) return;
    router.push(`/app/search?q=${encodeURIComponent(cleaned)}`);
  }

  return (
    <>
      <header className="app-shell pt-4 sm:pt-6">
        <div className="surface-panel rounded-[1.65rem] px-4 py-4 sm:px-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex items-end justify-between gap-3">
              <div>
                <div className="tiny-label">Consensus Research App</div>
                <Link
                  href="/app/rankings"
                  className="mt-1 inline-block font-heading text-3xl uppercase tracking-[0.05em] text-white"
                >
                  Signal Research Desk
                </Link>
              </div>
              <div className="flex items-center gap-2">
                <Link
                  href="/app/search"
                  className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-2 text-[0.72rem] uppercase tracking-[0.16em] text-faint transition-colors hover:text-white xl:hidden"
                >
                  <Search className="size-3.5" />
                  Search
                </Link>
                <UserButton />
              </div>
            </div>

            <form onSubmit={submitSearch} className="flex flex-1 items-center gap-3 xl:max-w-xl">
              <label className="relative hidden min-w-0 flex-1 md:block">
                <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-faint" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search ticker, company, Korean name, or exchange"
                  className="w-full rounded-full border border-white/10 bg-black/18 py-3 pl-11 pr-4 text-sm text-white outline-none transition-colors placeholder:text-faint focus:border-[oklch(0.78_0.11_84_/_0.42)]"
                />
              </label>
              <Link
                href="/app/search"
                className="hidden rounded-full border border-white/10 px-4 py-3 text-[0.72rem] font-medium uppercase tracking-[0.16em] text-faint transition-colors hover:text-white md:inline-flex"
              >
                Open search
              </Link>
              <div className="hidden items-center gap-2 rounded-full border border-white/10 px-4 py-3 text-[0.72rem] uppercase tracking-[0.16em] text-faint lg:inline-flex">
                <Star className="size-3.5" />
                {pinnedCount} pinned
              </div>
            </form>
          </div>

          <nav className="mt-4 hidden flex-wrap gap-2 md:flex">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-[0.72rem] uppercase tracking-[0.16em] transition-all",
                    active
                      ? "border-[oklch(0.78_0.11_84_/_0.42)] bg-[oklch(0.8_0.11_84_/_0.12)] text-white"
                      : "border-white/8 bg-black/12 text-faint hover:border-white/16 hover:text-white"
                  )}
                >
                  <Icon className="size-3.5" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      <nav className="fixed inset-x-4 bottom-4 z-50 md:hidden">
        <div className="surface-panel rounded-[1.45rem] px-2 py-2">
          <div className="grid grid-cols-4 gap-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex flex-col items-center gap-1 rounded-[1rem] px-2 py-2 text-[0.65rem] uppercase tracking-[0.12em] transition-colors",
                    active ? "bg-white/10 text-white" : "text-faint"
                  )}
                >
                  <Icon className="size-4" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      </nav>
    </>
  );
}
