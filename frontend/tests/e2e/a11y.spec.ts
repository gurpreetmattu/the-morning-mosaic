import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { ROUTES, SCHEMES } from "./helpers";

// axe on every route in both themes, on a phone and a desktop width.
// Zero serious or critical violations (DESIGN.md sections 11 and 20).
for (const viewport of [
  { name: "390x844", width: 390, height: 844 },
  { name: "1280x800", width: 1280, height: 800 },
]) {
  for (const scheme of SCHEMES) {
    test.describe(`axe ${viewport.name} ${scheme}`, () => {
      test.use({
        viewport: { width: viewport.width, height: viewport.height },
        colorScheme: scheme,
      });

      for (const route of ROUTES) {
        test(`${route.path} has no serious or critical violations`, async ({ page }) => {
          await page.goto(route.path);
          await page.waitForLoadState("networkidle");

          const results = await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
            .analyze();
          const blocking = results.violations.filter(
            (v) => v.impact === "serious" || v.impact === "critical",
          );

          expect(
            blocking.map(
              (v) =>
                `${v.id} (${v.impact}): ${v.nodes
                  .map((n) => n.target.join(" "))
                  .slice(0, 3)
                  .join(" | ")}`,
            ),
          ).toEqual([]);
        });
      }
    });
  }
}
