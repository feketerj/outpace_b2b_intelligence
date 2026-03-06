// @ts-check
/**
 * Playwright e2e test — Export Download (PDF + Excel)
 *
 * FIX: Base URL changed from http://localhost:3000 → http://localhost:3333
 *      to match playwright.config.ts webServer / baseURL setting.
 *
 * Location: frontend/e2e/export-download.spec.js
 * (moved from frontend/tests/ to frontend/e2e/)
 */

const { test, expect } = require('@playwright/test');
const path = require('path');

// Base URL matches playwright.config.ts
const BASE_URL = 'http://localhost:3333';

// Credentials from dev/test seed data
const ADMIN_EMAIL = 'admin@outpace.ai';
const ADMIN_PASSWORD = 'Admin123!';

/**
 * Helper: log in and navigate to the dashboard.
 */
async function loginAndGoToDashboard(page) {
  await page.goto(`${BASE_URL}/login`);

  await page.fill('input[type="email"], input[name="email"]', ADMIN_EMAIL);
  await page.fill('input[type="password"], input[name="password"]', ADMIN_PASSWORD);
  await page.click('button[type="submit"]');

  // Wait for redirect to dashboard
  await page.waitForURL(`${BASE_URL}/dashboard`, { timeout: 15_000 });
  await page.waitForLoadState('networkidle');
}

/**
 * Helper: open the export modal.
 * Assumes a visible "Export" button or similar trigger on the dashboard.
 */
async function openExportModal(page) {
  // Try common export trigger selectors
  const exportTrigger = page.locator(
    '[data-testid="export-modal-trigger"], button:has-text("Export"), [aria-label="Export"]'
  ).first();

  await exportTrigger.click();

  // Wait for the modal/dialog to appear
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

    // Wait for the PDF download to start when the button is clicked
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('[data-testid="export-pdf-btn"]'),
    ]);

    // Validate filename
    const filename = download.suggestedFilename();
    expect(filename, 'Downloaded filename should end with .pdf').toMatch(/\.pdf$/i);

    // Validate file size > 1KB (1024 bytes)
    const filePath = await download.path();
    expect(filePath, 'Download path should exist').toBeTruthy();

    const { statSync } = require('fs');
    const stats = statSync(filePath);
    expect(stats.size, 'PDF file should be larger than 1KB').toBeGreaterThan(1024);
  });

  test('Excel export downloads a valid .xlsx file larger than 1KB', async ({ page }) => {
    await openExportModal(page);

    // Wait for the Excel download to start when the button is clicked
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('[data-testid="export-excel-btn"]'),
    ]);

    // Validate filename
    const filename = download.suggestedFilename();
    expect(filename, 'Downloaded filename should end with .xlsx').toMatch(/\.xlsx$/i);

    // Validate file size > 1KB (1024 bytes)
    const filePath = await download.path();
    expect(filePath, 'Download path should exist').toBeTruthy();

    const { statSync } = require('fs');
    const stats = statSync(filePath);
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
