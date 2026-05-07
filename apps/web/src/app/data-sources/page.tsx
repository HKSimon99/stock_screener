"use client";

import { SiteChrome } from "@/components/site-chrome";
import { useT } from "@/hooks/use-t";
import type { TranslationKey } from "@/lib/i18n";

export default function DataSourcesPage() {
  const { t } = useT();

  const sources: Array<{ titleKey: TranslationKey; bodyKey: TranslationKey }> = [
    { titleKey: "dataSources.row.usListings.title",     bodyKey: "dataSources.row.usListings.body" },
    { titleKey: "dataSources.row.krListings.title",     bodyKey: "dataSources.row.krListings.body" },
    { titleKey: "dataSources.row.usFundamentals.title", bodyKey: "dataSources.row.usFundamentals.body" },
    { titleKey: "dataSources.row.krFundamentals.title", bodyKey: "dataSources.row.krFundamentals.body" },
    { titleKey: "dataSources.row.usPrices.title",       bodyKey: "dataSources.row.usPrices.body" },
    { titleKey: "dataSources.row.krPrices.title",       bodyKey: "dataSources.row.krPrices.body" },
  ];

  return (
    <div className="pb-16">
      <SiteChrome />
      <main className="app-shell pt-6 sm:pt-8">
        <section className="surface-panel rounded-2xl px-6 py-7 sm:px-8">
          <div className="section-kicker">{t("dataSources.kicker")}</div>
          <h1 className="mt-3 max-w-5xl font-heading text-4xl font-bold uppercase text-white sm:text-5xl lg:text-6xl">
            {t("dataSources.headline")}
          </h1>
          <p className="mt-5 max-w-3xl text-sm leading-7 text-quiet sm:text-base">
            {t("dataSources.intro")}
          </p>
        </section>

        <section className="mt-6 grid gap-4 lg:grid-cols-2">
          {sources.map((source) => (
            <article key={source.titleKey} className="metric-tile">
              <div className="tiny-label">{t(source.titleKey)}</div>
              <p className="mt-3 text-sm leading-6 text-[var(--rv-mute)]">{t(source.bodyKey)}</p>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
