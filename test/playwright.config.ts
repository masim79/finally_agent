import { defineConfig, devices } from "@playwright/test";

/**
 * BASE_URL is the one knob that makes this suite portable across both run paths:
 *   - docker-compose.test.yml sets it to http://app:8000 (container-to-container).
 *   - run-against-uvicorn.mjs sets it to http://127.0.0.1:<port> (host-to-host).
 * No spec file reads env vars directly — everything goes through `baseURL` /
 * `request` fixtures so the exact same spec runs unchanged against either path.
 */
const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  testDir: "./specs",
  // The suite shares one live backend + one SQLite file across every spec file (there is no
  // per-test reset endpoint), so specs run serially in one worker. Each spec either seeds its
  // own state through the API or claims tickers no other spec touches — see the comment atop
  // each spec file — but serial execution removes an entire class of cross-test race flake.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  forbidOnly: !!process.env.CI,
  timeout: 30_000,
  expect: {
    // Generous default: prices stream at ~500ms and several assertions wait on a tick or a
    // debounced UI update rather than a fixed sleep.
    timeout: 10_000,
  },
  // Waits for whichever app instance the run path already started to answer /api/health
  // before any spec runs — see fixtures/global-setup.ts. Neither run path's startup race is
  // this config's problem to solve twice.
  globalSetup: "./fixtures/global-setup.ts",
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
  ],
});
