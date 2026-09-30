import { expect, test } from "@playwright/test";
import { hasHorizontalOverflow, ROUTES, SCHEMES, VIEWPORTS, watch } from "./helpers";

// Every route, at every viewport, in both themes: it loads, nothing overflows
// sideways, the console is clean, and nothing talks to another origin
// (DESIGN.md sections 11, 20 and 22).
for (const viewport of VIEWPORTS) {
  for (const scheme of SCHEMES) {
    test.describe(`${viewport.name} ${scheme}`, () => {
      test.use({
        viewport: { width: viewport.width, height: viewport.height },
        colorScheme: scheme,
      });

      for (const route of ROUTES) {
        test(`${route.path} loads cleanly`, async ({ page }, testInfo) => {
          const seen = watch(page, route.status);
          const response = await page.goto(route.path);
          await page.waitForLoadState("networkidle");

          expect(response?.status()).toBe(route.status);
          expect(await hasHorizontalOverflow(page), "horizontal overflow").toBe(false);
          expect(seen.consoleErrors, "console errors").toEqual([]);
          expect(seen.foreignRequests, "requests to other origins").toEqual([]);
          expect(seen.failedRequests, "failed requests").toEqual([]);
          expect(seen.badResponses, "unexpected HTTP errors").toEqual([]);

          // Kept for human review (not compared): the spec asks for screenshots per route.
          const name = route.path === "/" ? "home" : route.path.slice(1).replaceAll("/", "_");
          await page.screenshot({
            path: testInfo.outputPath(`${name}-${viewport.name}-${scheme}.png`),
            fullPage: true,
          });
        });
      }
    });
  }
}
