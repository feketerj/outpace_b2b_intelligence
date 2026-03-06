import { test, expect } from '@playwright/test';
import { statSync } from 'fs';

const E2E_ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@example.com';
const E2E_ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'changeme';

/**
 * Playwright e2e test — Export Download (PDF + Excel)
 *
 * Base URL is read from playwright.config.ts (baseURL = http://localhost:3333).
 * Location: frontend/e2e/export-download.spec.ts
 */

/**
 * Helper: log in and navigate to the dashboard.
 */
async function loginAndGoToDashboard(page: import('@playwright/test').Page) {
  await page.goto('/login');

  await page.fill('input[type="email"], input[name="email"]', E2E_ADMIN_EMAIL);
  await page.fill('input[type="password"], input[name="password"]', E2E_ADMIN_PASSWORD);
  await page.click('button[type="submit"]');

  await page.waitForURL('**/dashboard', { timeout: 15_000 });
  await page.waitForLoadState('networkidle');
}

/**
 * Helper: open the export modal.
 */
async function openExportModal(page: import('@playwright/test').Page) {
  const exportTrigger = page.locator(
    '[data-testid="export-modal-trigger"], button:has-text("Export"), [aria-label="Export"]'
  ).first();

  await exportTrigger.click();

  await page.waitForSelector('[role="dialog"], [data-testid="export-modal"]', {
    timeout: 5_000,
  });
}

// ─── Tests ──────────────────────────────────────────────────────────────────────────────

test.describe('Export Downloads', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGoToDashboard(page);
  });

  test('PDF export downloads a valid .pdf file larger than 1KB', async ({ page }) => {
    await openExportModal(page);

    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('[data-testid="export-pdf-btn"]'),
    ]);

    const filename = download.suggestedFilename();
    expect(filename, 'Downloaded filename should end with .pdf').toMatch(/\.pdf$/i);

    const filePath = await download.path();
    expect(filePath, 'Download path should exist').toBeTruthy();

    const stats = statSync(filePath!);
    expect(stats.size, 'PDF file should be larger than 1KB').toBeGreaterThan(1024);
  });

  test('Excel export downloads a valid .xlsx file larger than 1KB', async ({ page }) => {
    await openExportModal(page);

    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('[data-testid="export-excel-btn"]'),
    ]);

    const filename = download.suggestedFilename();
    expect(filename, 'Downloaded filename should end with .xlsx').toMatch(/\.xlsx$/i);

    const filePath = await download.path();
    expect(filePath, 'Download path should exist').toBeTruthy();

    const stats = statSync(filePath!);
    expect(stats.size, 'Excel file should be larger than 1KB').toBeGreaterThan(1024);
  });

  test('Export modal contains both PDF and Excel buttons', async ({ page }) => {
    await openExportModal(page);

    await expect(
      page.locator('[data-testid="export-pdf-btn"]'),
      'PDF export button should be visible'
    ).toBeVisible();

    await expect(
      page.locator('[data-testid="export-excel-btn"]'),
      'Excel export button should be visible'
    ).toBeVisible();
  });
});
