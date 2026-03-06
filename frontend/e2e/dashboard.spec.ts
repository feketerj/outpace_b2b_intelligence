const E2E_ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@example.com';
const E2E_ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'changeme';
import { test, expect } from '@playwright/test';

/**
 * Dashboard E2E Tests
 *
 * Tests for the admin dashboard and its interactive elements.
 */

test.describe('Super Admin Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.getByTestId('login-email-input').fill(E2E_ADMIN_EMAIL);
    await page.getByTestId('login-password-input').fill(E2E_ADMIN_PASSWORD);
    await page.getByTestId('login-submit-button').click();
    await expect(page).toHaveURL(/\/admin/, { timeout: 10000 });
  });

  test('displays dashboard with key metrics', async ({ page }) => {
    // Dashboard should show key stats - use heading role to avoid ambiguity
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

    // Look for typical dashboard elements
    const cards = page.locator('[class*="card"]');
    await expect(cards.first()).toBeVisible();
  });

  test('navigation menu is visible and clickable', async ({ page }) => {
    // Check sidebar/navigation elements
    const nav = page.locator('nav, [role="navigation"]');
    await expect(nav.first()).toBeVisible();

    // Try clicking on Tenants link
    const tenantsLink = page.locator('a[href*="tenant"], button:has-text("Tenants")');
    if (await tenantsLink.first().isVisible()) {
      await tenantsLink.first().click();
      await expect(page).toHaveURL(/tenant/i);
    }
  });
});

test.describe('Tenants Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByTestId('login-email-input').fill(E2E_ADMIN_EMAIL);
    await page.getByTestId('login-password-input').fill(E2E_ADMIN_PASSWORD);
    await page.getByTestId('login-submit-button').click();
    await expect(page).toHaveURL(/\/admin/, { timeout: 10000 });
  });

  test('can navigate to tenants page', async ({ page }) => {
    await page.goto('/admin/tenants');
    await expect(page).toHaveURL(/\/admin\/tenants/);
  });

  test('displays tenant list', async ({ page }) => {
    await page.goto('/admin/tenants');

    // Wait for tenant list to load (could be table or card layout)
    const tenantContent = page.locator('table, [role="table"], [class*="card"]');
    await expect(tenantContent.first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Users Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByTestId('login-email-input').fill(E2E_ADMIN_EMAIL);
    await page.getByTestId('login-password-input').fill(E2E_ADMIN_PASSWORD);
    await page.getByTestId('login-submit-button').click();
    await expect(page).toHaveURL(/\/admin/, { timeout: 10000 });
  });

  test('can navigate to users page', async ({ page }) => {
    await page.goto('/admin/users');
    await expect(page).toHaveURL(/\/admin\/users/);
  });
});

test.describe('Export Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByTestId('login-email-input').fill(E2E_ADMIN_EMAIL);
    await page.getByTestId('login-password-input').fill(E2E_ADMIN_PASSWORD);
    await page.getByTestId('login-submit-button').click();
    await expect(page).toHaveURL(/\/admin/, { timeout: 10000 });
  });

  test('export button opens modal when clicked', async ({ page }) => {
    // Navigate to a page with export functionality
    await page.goto('/admin');

    // Look for export button
    const exportButton = page.locator('button:has-text("Export"), [data-testid="export-button"]');

    if (await exportButton.first().isVisible()) {
      await exportButton.first().click();

      // Modal should appear
      const modal = page.locator('[role="dialog"], [data-testid="export-modal"]');
      await expect(modal).toBeVisible();
    }
  });
});
