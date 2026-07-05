import { defineConfig, devices } from "@playwright/test";

/**
 * E2E smoke tests run against the built SPA served by `vite preview`. They do
 * not require a backend — API calls fail gracefully and the shell/empty-states
 * still render — so this is a lightweight, CI-friendly smoke of routing,
 * navigation, and the theme toggle.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL: "http://localhost:4173",
    trace: "on-first-retry",
  },
  webServer: {
    command: "npm run preview -- --port 4173 --strictPort",
    port: 4173,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
