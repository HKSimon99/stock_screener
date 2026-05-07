"use client";

import { SiteChrome } from "@/components/site-chrome";
import { useT } from "@/hooks/use-t";
import type { TranslationKey } from "@/lib/i18n";

export default function MethodologyPage() {
  const { t } = useT();

  const sections: Array<{ titleKey: TranslationKey; bodyKey: TranslationKey }> = [
    {
      titleKey: "methodology.section.coverage.title",
      bodyKey:  "methodology.section.coverage.body",
    },
    {
      titleKey: "methodology.section.strategies.title",
      bodyKey:  "methodology.section.strategies.body",
    },
    {
      titleKey: "methodology.section.pit.title",
      bodyKey:  "methodology.section.pit.body",
    },
  ];

  return (
    <div className="pb-16">
      <SiteChrome />
      <main className="app-shell pt-6 sm:pt-8">
        <section className="surface-panel rounded-2xl px-6 py-7 sm:px-8">
          <div className="section-kicker">{t("methodology.kicker")}</div>
          <h1 className="mt-3 max-w-5xl font-heading text-4xl font-bold uppercase text-white sm:text-5xl lg:text-6xl">
            {t("methodology.headline")}
          </h1>
          <p className="mt-5 max-w-3xl text-sm leading-7 text-quiet sm:text-base">
            {t("methodology.intro")}
          </p>
        </section>

        <section className="mt-6 grid gap-4 lg:grid-cols-3">
          {sections.map((section) => (
            <article key={section.titleKey} className="metric-tile">
              <h2 className="font-heading text-2xl font-bold uppercase text-[var(--rv-ink)] sm:text-3xl">
                {t(section.titleKey)}
              </h2>
              <p className="mt-3 text-sm leading-6 text-[var(--rv-mute)]">{t(section.bodyKey)}</p>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
