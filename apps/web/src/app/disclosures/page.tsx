"use client";

import { SiteChrome } from "@/components/site-chrome";
import { useT } from "@/hooks/use-t";
import type { TranslationKey } from "@/lib/i18n";

export default function DisclosuresPage() {
  const { t } = useT();

  const items: TranslationKey[] = [
    "disclosures.item.notAdvice",
    "disclosures.item.dataDelay",
    "disclosures.item.coverageMeaning",
    "disclosures.item.krLicensing",
  ];

  return (
    <div className="pb-16">
      <SiteChrome />
      <main className="app-shell pt-6 sm:pt-8">
        <section className="surface-panel rounded-2xl px-6 py-7 sm:px-8">
          <div className="section-kicker">{t("disclosures.kicker")}</div>
          <h1 className="mt-3 max-w-5xl font-heading text-4xl font-bold uppercase text-white sm:text-5xl lg:text-6xl">
            {t("disclosures.headline")}
          </h1>
          <div className="mt-6 grid gap-4">
            {items.map((key) => (
              <div key={key} className="rounded-xl border border-white/10 bg-white/[0.06] px-5 py-4 text-sm leading-6 text-quiet">
                {t(key)}
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
