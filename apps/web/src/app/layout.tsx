import type { Metadata } from "next";
import {
  Inter,
  Plus_Jakarta_Sans,
  JetBrains_Mono,
} from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { Observability } from "@/components/observability";
import { Providers } from "@/components/providers";
import SentryErrorBoundary from "@/components/sentry-error-boundary";
import { TosConsentGate } from "@/components/tos-consent-gate";
import { LangSync } from "@/components/lang-sync";
import "./globals.css";

/**
 * Body font: Inter — Revolut's workhorse for UI labels, body copy, buttons.
 * Revolut uses Inter at 400 (body) and 600 (emphatic / button).
 */
const bodyFont = Inter({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

/**
 * Display font: Plus Jakarta Sans — closest freely-licensed match to Revolut's
 * proprietary Aeonik Pro. Both are humanist geometric sans-serifs at weight 500
 * with excellent large-scale display legibility.
 * Apply letter-spacing: -0.04em at display sizes in CSS to match Revolut's tight stacking.
 */
const displayFont = Plus_Jakarta_Sans({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const monoFont = JetBrains_Mono({
  variable: "--font-code",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

export const metadata: Metadata = {
  title: {
    default: "Consensus Signal Research",
    template: "%s | Consensus Signal Research",
  },
  description:
    "Full-market US and Korea stock search, ranking, and chart research with explicit coverage and freshness.",
  manifest: "/manifest.webmanifest",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${bodyFont.variable} ${displayFont.variable} ${monoFont.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full bg-background text-foreground font-sans">
        <a
          href="#content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-full focus:bg-white focus:px-4 focus:py-2 focus:text-black"
        >
          Skip to content
        </a>
        <SentryErrorBoundary>
          <ClerkProvider>
            <Providers>
              <LangSync />
              <TosConsentGate>
                <div id="content">{children}</div>
              </TosConsentGate>
            </Providers>
          </ClerkProvider>
        </SentryErrorBoundary>
        <Observability />
      </body>
    </html>
  );
}
