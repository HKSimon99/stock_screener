"use client";

import { SiteChrome } from "@/components/site-chrome";
import { useT } from "@/hooks/use-t";
import type { TranslationKey } from "@/lib/i18n";

export default function FreshnessPolicyPage() {
  const { t } = useT();

  const rows: Array<{ labelKey: TranslationKey; bodyKey: TranslationKey }> = [
    { labelKey: "freshness.row.needsPrice.label",        bodyKey: "freshness.row.needsPrice.body" },
    { labelKey: "freshness.row.needsFundamentals.label", bodyKey: "freshness.row.needsFundamentals.body" },
    { labelKey: "freshness.row.needsScoring.label",      bodyKey: "freshness.row.needsScoring.body" },
    { labelKey: "freshness.row.stale.label",             bodyKey: "freshness.row.stale.body" },
    { labelKey: "freshness.row.ranked.label",            bodyKey: "freshness.row.ranked.body" },
  ];

  return (
    <div className="pb-16">
      <SiteChrome />
      <main className="app-shell pt-6 sm:pt-8">
        <section className="surface-panel rounded-2xl px-6 py-7 sm:px-8">
          <div className="section-kicker">{t("freshness.kicker")}</div>
          <h1 className="mt-3 max-w-5xl font-heading text-4xl font-bold uppercase text-white sm:text-5xl lg:text-6xl">
            {t("freshness.headline")}
          </h1>
          <p className="mt-5 max-w-3xl text-sm leading-7 text-quiet sm:text-base">
            {t("freshness.intro")}
          </p>
        </section>

        <section className="mt-6 overflow-hidden rounded-2xl border border-[var(--rv-hairline-dark)] bg-[var(--rv-surface-card)] shadow-[0_16px_42px_rgba(15,23,42,0.06)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-[var(--rv-surface-soft)]">
              <tr>
                <th className="px-5 py-4 tiny-label">{t("freshness.col.state")}</th>
                <th className="px-5 py-4 tiny-label">{t("freshness.col.meaning")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.labelKey} className="border-t border-[var(--rv-hairline-dark)]">
                  <td className="px-5 py-4 font-heading text-2xl font-bold uppercase text-[var(--rv-ink)]">
                    {t(row.labelKey)}
                  </td>
                  <td className="px-5 py-4 text-[var(--rv-mute)]">{t(row.bodyKey)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}
