import { test, expect, Page } from '@playwright/test';

// Randomised per-run so the e2e run is idempotent against a shared DB.
const uniq = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
const email = `e2e-${uniq}@test.com`;
const password = 'password123';

async function register(page: Page) {
  await page.goto('/register');
  await page.fill('#email', email);
  await page.fill('#password', password);
  await page.fill('#confirmPassword', password);
  await page.click('button[type="submit"]');
  // redirects to /login
  await page.waitForURL('**/login', { timeout: 10000 });
  await expect(page.locator('h2')).toContainText('Sign in');
}

async function login(page: Page) {
  await page.goto('/login');
  await page.fill('#email', email);
  await page.fill('#password', password);
  await page.click('button[type="submit"]');
  await page.waitForURL('**/dashboard', { timeout: 10000 });
}

test.describe('Auth', () => {
  test('landing page loads and links to request', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h1')).toContainText('Reliable Towing');
    await expect(page.getByRole('link', { name: 'Request Service Now' })).toBeVisible();
  });

  test('register -> login -> dashboard', async ({ page }) => {
    await register(page);
    await login(page);
    await expect(page.locator('text=Active Requests').first()).toBeVisible();
  });

  test('login rejects wrong credentials', async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'nobody@test.com');
    await page.fill('#password', 'wrongpass');
    await page.click('button[type="submit"]');
    // stays on login, shows an error toast
    await expect(page).not.toHaveURL(/dashboard/, { timeout: 5000 });
  });
});

test.describe('Request service', () => {
  test('submits a request and lands on dashboard', async ({ page }) => {
    await register(page);
    await login(page);

    await page.goto('/request');
    await page.fill('#description', 'Flat tire on the highway, need roadside assistance');
    await page.fill('#location', '1234 Main Street, Springfield');
    await page.fill('#name', 'Jane Doe');
    await page.fill('#phoneNumber', '5551234567');
    await page.selectOption('#serviceType', 'towing');
    await page.selectOption('#vehicleType', 'car');
    await page.click('button[type="submit"]');

    // redirected to dashboard after success
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    await expect(page.locator('text=Active Requests').first()).toBeVisible();
  });
});

test.describe('Dashboard completeness', () => {
  test('every quick-action link resolves (NO 404)', async ({ page }) => {
    await register(page);
    await login(page);

    const links = ['/dashboard/vehicles', '/dashboard/settings'];
    for (const href of links) {
      const resp = await page.goto(href);
      // Fails today until Phase B adds these pages. This is the intentional
      // completeness test.
      expect(resp.status(), `${href} should not 404`).toBeLessThan(400);
    }
  });
});
