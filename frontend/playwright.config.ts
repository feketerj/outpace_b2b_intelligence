import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for browser-based UI testing.
 *
 * This tests ACTUAL button clicks, form submissions, and user flows.
 * API tests are NOT a substitute for this.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // Disabled - rate limiting blocks parallel logins
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1, // 1 retry locally to handle flaky rate limits
  workers: 1, // Single worker to avoid rate limiting on login endpoint
  reporter: 'html',

  use: {
    // Base URL for the frontend (using port 3333 to avoid conflicts)
    baseURL: 'http://localhost:3333',

    // Collect trace on failure for debugging
    trace: 'on-first-retry',

    // Screenshot on failure
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Start the frontend dev server before running tests
  webServer: {
    command: 'npx vite --port 3333',
    url: 'http://localhost:3333',
    reuseExistingServer: !process.env.CI, // Reuse existing server locally for faster iteration
    timeout: 60000, // 1 minute (Vite is fast)
    env: {
      // Point frontend to local backend API (not Docker's host.docker.internal)
      REACT_APP_BACKEND_URL: 'http://localhost:8000',
    },
  },
});
