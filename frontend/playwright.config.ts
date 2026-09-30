import { defineConfig } from "@playwright/test";

// Browser tests (DESIGN.md section 20). They run against a production build
// of the site and a small mock of the backend API, so nothing needs a database.
//
//   npx playwright test                 # everything
//   E2E_DEV=1 npx playwright test       # against `next dev` (faster to start)
//
// Locally the tests drive your installed Chrome (no browser download); CI sets
// E2E_BROWSER_CHANNEL="" to use Playwright's own Chromium.
const PORT = 3100;
const API_PORT = 8000;
const dev = process.env.E2E_DEV === "1";
const channel = process.env.E2E_BROWSER_CHANNEL ?? "chrome";

export default defineConfig({
  testDir: "tests/e2e",
  testMatch: /.*\.spec\.ts/,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  reporter: [["list"]],
  outputDir: "test-results",
  use: {
    baseURL: `http://localhost:${PORT}`,
    // Animations are checked by dedicated tests that opt back in; everything else runs with
    // reduced motion so screenshots and axe scans never catch a half-played reveal.
    reducedMotion: "reduce",
    ...(channel ? { channel } : {}),
    trace: "off",
  },
  webServer: [
    {
      command: "node tests/e2e/mock-api.mjs",
      url: `http://127.0.0.1:${API_PORT}/api/config`,
      reuseExistingServer: !process.env.CI,
      env: { MOCK_API_PORT: String(API_PORT) },
    },
    {
      command: dev ? `npx next dev -p ${PORT}` : `npm run build && npx next start -p ${PORT}`,
      url: `http://localhost:${PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 300_000,
      env: { BACKEND_ORIGIN: `http://127.0.0.1:${API_PORT}` },
    },
  ],
});
