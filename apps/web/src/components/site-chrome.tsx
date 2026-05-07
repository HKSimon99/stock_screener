import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";

const SITE_LINKS = [
  { href: "/methodology", label: "Methodology" },
  { href: "/data-sources", label: "Data Sources" },
  { href: "/freshness-policy", label: "Freshness" },
  { href: "/disclosures", label: "Disclosures" },
] as const;

export function SiteChrome() {
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
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Link href="/rankings" transitionTypes={["nav-forward"]} className="btn-primary shrink-0 px-4 py-2 text-sm">
            Open App
            <ArrowRight className="size-4" />
          </Link>
        </div>
      </div>
    </header>
  );
}
