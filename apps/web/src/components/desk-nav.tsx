"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, Layers3, Radar } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  {
    href: "/rankings",
    label: "Rankings",
    icon: Layers3,
  },
  {
    href: "/alerts",
    label: "Alerts",
    icon: Bell,
  },
  {
    href: "/market-regime",
    label: "Market Regime",
    icon: Radar,
  },
] as const;

export function DeskNav() {
  const pathname = usePathname();

  return (
    <div className="app-shell pt-4 sm:pt-6">
      <nav className="surface-panel rounded-[1.45rem] px-4 py-3 sm:px-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="tiny-label">Consensus Signal Desk</div>
            <div className="mt-1 font-heading text-2xl uppercase tracking-[0.06em] text-white">
              Operator Console
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active =
                pathname === item.href ||
                (item.href !== "/rankings" && pathname.startsWith(item.href));

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-full border px-3 py-2 text-[0.72rem] uppercase tracking-[0.16em] transition-all",
                    active
                      ? "border-[oklch(0.82_0.15_78_/_0.34)] bg-[oklch(0.32_0.03_78_/_0.24)] text-white shadow-[0_0_0_1px_oklch(0.82_0.15_78_/_0.14)]"
                      : "border-white/8 bg-black/12 text-faint hover:border-white/16 hover:text-white"
                  )}
                >
                  <Icon className="size-3.5" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      </nav>
    </div>
  );
}
