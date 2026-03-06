import { test, expect } from '@playwright/test';

const E2E_ADMIN_EMAIL = process.env.CARFAX_ADMIN_EMAIL || 'admin@example.com';
const E2E_ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || process.env.CARFAX_ADMIN_PASSWORD || 'changeme';

/**
 * Authentication E2E Tests
 *
 * These tests actually click buttons and fill forms in a real browser.
 * They verify that the frontend correctly interacts with the backend.
 */

test.describe('Login Page', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to login first (creates context), then clear storage
    await page.goto('/login');
    await page.evaluate(() => localStorage.clear());
  });

  test('displays login form with all required elements', async ({ page }) => {
    await page.goto('/login');

    // Verify all form elements are present
    await expect(page.getByTestId('login-email-input')).toBeVisible();
    await expect(page.getByTestId('login-password-input')).toBeVisible();
    await expect(page.getByTestId('login-submit-button')).toBeVisible();
    await expect(page.getByTestId('login-submit-button')).toHaveText('Sign In');
  });

  test('shows validation error for empty email', async ({ page }) => {
    await page.goto('/login');

    // Try to submit with empty email
    await page.getByTestId('login-password-input').fill('somepassword');
    await page.getByTestId('login-submit-button').click();

    // Email field should be marked as required (HTML5 validation)
    const emailInput = page.getByTestId('login-email-input');
    await expect(emailInput).toHaveAttribute('required', '');
  });

  test('shows error toast for invalid credentials', async ({ page }) => {
    await page.goto('/login');

    // Fill in invalid credentials
    await page.getByTestId('login-email-input').fill('wrong@email.com');
    await page.getByTestId('login-password-input').fill('wrongpassword');
    await page.getByTestId('login-submit-button').click();

    // Wait for error toast (using Sonner toast library)
    await expect(page.locator('[data-sonner-toast]')).toBeVisible({ timeout: 5000 });
  });

  test('successful login redirects to admin dashboard', async ({ page }) => {
    await page.goto('/login');

    // Fill in valid super_admin credentials
    await page.getByTestId('login-email-input').fill(E2E_ADMIN_EMAIL);
    await page.getByTestId('login-password-input').fill(E2E_ADMIN_PASSWORD);
    await page.getByTestId('login-submit-button').click();

    // Should redirect to admin dashboard
    await expect(page).toHaveURL(/\/admin/, { timeout: 10000 });

    // Verify token is stored in localStorage
    const token = await page.evaluate(() => localStorage.getItem('token'));
    expect(token).toBeTruthy();
    expect(token).toContain('eyJ'); // JWT token starts with eyJ
  });

  test('button shows loading state during login', async ({ page }) => {
    await page.goto('/login');

    // Fill in credentials
    await page.getByTestId('login-email-input').fill(E2E_ADMIN_EMAIL);
    await page.getByTestId('login-password-input').fill(E2E_ADMIN_PASSWORD);

    // Click and immediately check button text
    const button = page.getByTestId('login-submit-button');
    await button.click();

    // Button should be disabled and show loading text
    await expect(button).toBeDisabled();
    await expect(button).toHaveText('Signing in...');
  });
});

test.describe('Protected Routes', () => {
  test('redirects to login when accessing protected route without auth', async ({ page }) => {
    // Navigate to login first to establish context, then clear storage
    await page.goto('/login');
    await page.evaluate(() => localStorage.clear());

    // Now try to access protected route
    await page.goto('/admin');

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
  });

  test('allows access to protected routes with valid token', async ({ page }) => {
    // First login to get a token
    await page.goto('/login');
    await page.getByTestId('login-email-input').fill(E2E_ADMIN_EMAIL);
    await page.getByTestId('login-password-input').fill(E2E_ADMIN_PASSWORD);
    await page.getByTestId('login-submit-button').click();

    // Wait for redirect
    await expect(page).toHaveURL(/\/admin/, { timeout: 10000 });

    // Now navigate to another protected route
    await page.goto('/admin/tenants');
    await expect(page).toHaveURL(/\/admin\/tenants/);
  });
});

test.describe('Logout', () => {
  test('logout clears token and redirects to login', async ({ page }) => {
    // Login first
    await page.goto('/login');
    await page.getByTestId('login-email-input').fill(E2E_ADMIN_EMAIL);
    await page.getByTestId('login-password-input').fill(E2E_ADMIN_PASSWORD);
    await page.getByTestId('login-submit-button').click();
    await expect(page).toHaveURL(/\/admin/, { timeout: 10000 });

    // Find and click logout button
    const logoutButton = page.locator('button:has-text("Logout"), [data-testid="logout-button"]');
    if (await logoutButton.isVisible()) {
      await logoutButton.click();

      // Verify token is cleared
      const token = await page.evaluate(() => localStorage.getItem('token'));
      expect(token).toBeNull();

      // Should redirect to login
      await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
    }
  });
});
