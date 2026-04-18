// This file is loaded in the browser. NEXT_PUBLIC_SENTRY_DSN is baked into
// the bundle at build time; if the env var is absent the SDK is a no-op.
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NODE_ENV,

    // 10 % of page-loads generate a performance trace.
    tracesSampleRate: 0.1,

    // Don't send PII (e.g. user email) unless explicitly set.
    sendDefaultPii: false,

    // Show Sentry overlay in dev mode so errors surface immediately.
    debug: process.env.NODE_ENV === "development",
  });
}
