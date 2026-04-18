import { test, expect } from '@playwright/test';

// ──────────────────────���──────────────────────────────────────────────────────
// Public surface
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Public pages', () => {
  test('home page loads and has title', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/consensus/i);
    // Should not be a 404/500 page
    await expect(page.locator('body')).toBeVisible();
  });

  test('sign-in page renders without error', async ({ page }) => {
    const response = await page.goto('/sign-in');
    expect(response?.status()).not.toBe(404);
    expect(response?.status()).not.toBe(500);
    await expect(page).toHaveURL(/sign-in/);
  });

  test('sign-up page renders without error', async ({ page }) => {
    const response = await page.goto('/sign-up');
    expect(response?.status()).not.toBe(404);
    expect(response?.status()).not.toBe(500);
    await expect(page).toHaveURL(/sign-up/);
  });

  test('methodology page renders', async ({ page }) => {
    const response = await page.goto('/methodology');
    expect(response?.status()).not.toBe(404);
    expect(response?.status()).not.toBe(500);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Auth guards (Clerk middleware)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Protected routes redirect unauthenticated users', () => {
  const protectedRoutes = [
    '/app/rankings',
    '/app/market-regime',
    '/app/alerts',
  ];

  for (const route of protectedRoutes) {
    test(`${route} → redirects to /sign-in`, async ({ page }) => {
      await page.goto(route);
      await expect(page).toHaveURL(/sign-in/);
    });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Static assets / manifest
// ─────────────────────────────────────────────────────────────────────────────
test('web manifest is accessible', async ({ page }) => {
  const response = await page.request.get('/manifest.webmanifest');
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body).toHaveProperty('name');
});
