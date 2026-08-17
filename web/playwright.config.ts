/**
 * End-to-end web tests (Playwright).
 *
 * These run against the LIVE app: the running Next.js frontend + real API.
 * They are the "completeness gate" for the web surface — every route must
 * resolve and every action must round-trip through the real API.
 *
 * Setup:
 *   cd web
 *   npx playwright install chromium
 *   npm run dev            (frontend on :3000, proxying API via NEXT_PUBLIC_API_URL)
 *   (docker compose up -d --build db api  — backend on :8000)
 *
 * Run:
 *   npx playwright test
 *
 * NOTE: until Phase B of guidelines/E2E_AND_COMPLETENESS_PLAN.md lands,
 * `dashboard.spec.ts` is expected to FAIL on the dead 404 links
 * (/dashboard/vehicles, /dashboard/settings, /dashboard/requests/:id).
 */

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_WEB_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
