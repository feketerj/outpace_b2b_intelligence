import { test, expect } from '@playwright/test';
import fs from 'fs';

const BASE_URL = 'http://localhost:3000';
const TENANT_ID = 'bec8a414-b00d-4a58-9539-5f732db23b35';

test.describe('Export Download Verification', () => {
  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto(BASE_URL);
    await page.waitForSelector('input[type="email"]', { timeout: 10000 });
    await page.fill('input[type="email"]', 'admin@outpace.ai');
    await page.fill('input[type="password"]', 'Admin123!');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(3000);
  });

  test('Export PDF triggers a real download', async ({ page }) => {
    // Navigate to preview page with data
    await page.goto(`${BASE_URL}/preview?tenant_id=${TENANT_ID}`);
    await page.waitForTimeout(3000);

    // Track PDF response
    let pdfResponseSeen = false;
    page.on('response', (resp) => {
      const ct = resp.headers()['content-type'] || '';
      if (ct.includes('application/pdf')) pdfResponseSeen = true;
    });

    // Click Export button to open modal
    const exportBtn = await page.locator('button:has-text("Export")');
    await expect(exportBtn).toBeEnabled({ timeout: 5000 });
    await exportBtn.click();
    await page.waitForTimeout(1000);

    // Select the opportunity (click Select All or first checkbox)
    const selectAllBtn = await page.locator('button:has-text("Select All")');
    if (await selectAllBtn.isVisible()) {
      await selectAllBtn.click();
      await page.waitForTimeout(500);
    }

    // Click Export PDF button
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 30000 }),
      page.click('[data-testid="export-pdf-btn"]')
    ]);

    const filename = download.suggestedFilename();
    expect(filename.toLowerCase()).toMatch(/\.pdf$/);

    const path = await download.path();
    expect(path).toBeTruthy();

    const stat = fs.statSync(path);
    expect(stat.size).toBeGreaterThan(1024); // 1KB floor to avoid error page masquerading as PDF

    expect(pdfResponseSeen).toBeTruthy();
  });

  test('Export Excel triggers a real download', async ({ page }) => {
    // Navigate to preview page with data
    await page.goto(`${BASE_URL}/preview?tenant_id=${TENANT_ID}`);
    await page.waitForTimeout(3000);

    // Track Excel response
    let excelResponseSeen = false;
    page.on('response', (resp) => {
      const ct = resp.headers()['content-type'] || '';
      if (ct.includes('spreadsheet') || ct.includes('excel')) excelResponseSeen = true;
    });

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
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 30000 }),
      page.click('[data-testid="export-excel-btn"]')
    ]);

    const filename = download.suggestedFilename();
    expect(filename.toLowerCase()).toMatch(/\.xlsx$/);

    const path = await download.path();
    expect(path).toBeTruthy();

    const stat = fs.statSync(path);
    expect(stat.size).toBeGreaterThan(1024); // 1KB floor

    expect(excelResponseSeen).toBeTruthy();
  });
});
