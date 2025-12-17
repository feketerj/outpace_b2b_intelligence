import { test, expect } from '@playwright/test';
import fs from 'fs';

const BASE_URL = 'http://localhost:3000';
const TENANT_ID = 'bec8a414-b00d-4a58-9539-5f732db23b35';

test.describe('Export Download Verification', () => {
  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto(BASE_URL);
    await page.waitForSelector('input[type="email"]', { timeout: 10000 });
    await page.fill('input[type="email"]', 'admin@example.com');
    await page.fill('input[type="password"]', 'REDACTED_ADMIN_PASSWORD');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(3000);
  });

  test('Export PDF triggers a real download', async ({ page }) => {
    // Navigate to preview page with data
    await page.goto(`${BASE_URL}/preview?tenant_id=${TENANT_ID}`);
    await page.waitForTimeout(3000);

    // Click Export button to open modal
    const exportBtn = await page.locator('button:has-text("Export")');
    await expect(exportBtn).toBeEnabled({ timeout: 5000 });
    await exportBtn.click();
    await page.waitForTimeout(1000);

    // Select the opportunity
    const selectAllBtn = await page.locator('button:has-text("Select All")');
    if (await selectAllBtn.isVisible()) {
      await selectAllBtn.click();
      await page.waitForTimeout(500);
    }

    // Click Export PDF button
    await page.click('[data-testid="export-pdf-btn"]');

    const download = await page.waitForEvent('download');
    const filename = download.suggestedFilename().toLowerCase();
    expect(filename).toMatch(/\.pdf$/);

    const path = await download.path();
    expect(path).toBeTruthy();

    const stat = fs.statSync(path);
    expect(stat.size).toBeGreaterThan(1024);
  });

  test('Export Excel triggers a real download', async ({ page }) => {
    // Navigate to preview page with data
    await page.goto(`${BASE_URL}/preview?tenant_id=${TENANT_ID}`);
    await page.waitForTimeout(3000);

    // Click Export button to open modal
    const exportBtn = await page.locator('button:has-text("Export")');
    await expect(exportBtn).toBeEnabled({ timeout: 5000 });
    await exportBtn.click();
    await page.waitForTimeout(1000);

    // Select the opportunity
    const selectAllBtn = await page.locator('button:has-text("Select All")');
    if (await selectAllBtn.isVisible()) {
      await selectAllBtn.click();
      await page.waitForTimeout(500);
    }

    // Click Export Excel button
    await page.click('[data-testid="export-excel-btn"]');

    const download = await page.waitForEvent('download');
    const filename = download.suggestedFilename().toLowerCase();
    expect(filename).toMatch(/\.xlsx$/);

    const path = await download.path();
    expect(path).toBeTruthy();

    const stat = fs.statSync(path);
    expect(stat.size).toBeGreaterThan(1024);
  });
});
