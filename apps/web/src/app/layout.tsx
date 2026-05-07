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
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";

// Reads theme from localStorage before React hydrates to prevent flash of wrong theme
const THEME_SCRIPT = `(function(){try{var s=localStorage.getItem('consensus-ui-state');if(s){var t=JSON.parse(s);if(t&&t.state&&t.state.theme==='dark'){document.documentElement.classList.add('dark');}}}catch(e){}})();`;

const bodyFont = Inter({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

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
      <head>
        {/* Anti-FOUC: apply dark class before first paint */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
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
              <ThemeProvider />
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
