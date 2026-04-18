import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  redirects: async () => [
    // Old root routes → /app/* authenticated equivalents (301 permanent)
    {
      source: "/rankings",
      destination: "/app/rankings",
      permanent: true,
    },
    {
      source: "/alerts",
      destination: "/app/alerts",
      permanent: true,
    },
    {
      source: "/market-regime",
      destination: "/app/market-regime",
      permanent: true,
    },
    {
      source: "/instruments/:ticker",
      destination: "/app/search?q=:ticker",
      permanent: true,
    },
  ],
};

// withSentryConfig is a no-op when SENTRY_DSN / NEXT_PUBLIC_SENTRY_DSN are
// not set — safe to always wrap.
export default withSentryConfig(nextConfig, {
  // Suppress the Sentry CLI source-map upload banner in CI / local builds
  // when SENTRY_AUTH_TOKEN is absent.
  silent: !process.env.SENTRY_AUTH_TOKEN,

  // Don't upload source maps until SENTRY_AUTH_TOKEN is configured.
  sourcemaps: {
    disable: true,
  },
});
