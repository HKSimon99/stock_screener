import { defineConfig, devices } from '@playwright/test';

const PORT = 3000;
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${PORT}`;

/**
 * Clerk stub keys — real OAuth won't work, but middleware routing
 * and page rendering will behave correctly for smoke tests.
 */
const clerkStubEnv = {
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: 'pk_test_placeholder_for_ci_e2e',
  CLERK_SECRET_KEY: 'sk_test_placeholder_for_ci_e2e',
  NEXT_PUBLIC_CLERK_SIGN_IN_URL: '/sign-in',
  NEXT_PUBLIC_CLERK_SIGN_UP_URL: '/sign-up',
  NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL: '/app/rankings',
  NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL: '/app/rankings',
};

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  /* Fail fast on CI — no accidental .only left in code */
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'github' : 'html',

  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  /* Start a local Next.js dev server unless PLAYWRIGHT_BASE_URL is set
   * (i.e. running against a deployed environment). */
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: 'pnpm run dev',
        url: `http://localhost:${PORT}`,
        reuseExistingServer: !process.env.CI,
        timeout: 90_000,
        env: clerkStubEnv,
      },
});
