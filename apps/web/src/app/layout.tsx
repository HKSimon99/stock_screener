import type { Metadata } from "next";
import {
  Barlow_Condensed,
  JetBrains_Mono,
  Public_Sans,
} from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { Observability } from "@/components/observability";
import { Providers } from "@/components/providers";
import "./globals.css";

const bodyFont = Public_Sans({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const displayFont = Barlow_Condensed({
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
        <ClerkProvider>
          <Providers>
            <div id="content">{children}</div>
          </Providers>
        </ClerkProvider>
        <Observability />
      </body>
    </html>
  );
}
