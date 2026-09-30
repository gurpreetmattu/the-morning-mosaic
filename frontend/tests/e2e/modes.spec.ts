import { expect, test } from "@playwright/test";
import { hasHorizontalOverflow } from "./helpers";

test.describe("user preferences and modes", () => {
  test("reduced motion removes the stamp animation", async ({ browser }) => {
    const context = await browser.newContext({ reducedMotion: "reduce" });
    const page = await context.newPage();
    await page.goto("/subscribe?genres=ai");

    const seconds = await page
      .locator(".postmark")
      .first()
      .evaluate((el) => parseFloat(getComputedStyle(el).animationDuration));
    expect(seconds).toBeLessThan(0.01);
    await context.close();
  });

  test.describe("with motion allowed", () => {
    test.use({ reducedMotion: "no-preference" });

    test("normal motion keeps the stamp animation", async ({ page }) => {
      await page.goto("/subscribe?genres=ai");
      const seconds = await page
        .locator(".postmark")
        .first()
        .evaluate((el) => parseFloat(getComputedStyle(el).animationDuration));
      expect(seconds).toBeGreaterThan(0.1);
    });
  });

  test("forced colours (high contrast) still show a usable page", async ({ page }) => {
    await page.emulateMedia({ forcedColors: "active" });
    for (const path of ["/", "/subscribe", "/sample"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      expect(await hasHorizontalOverflow(page)).toBe(false);
    }
  });

  test("the theme toggle switches to the Late edition and remembers it", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/");
    const bg = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    const lightBg = await bg();

    await page.getByRole("button", { name: "Switch to Late edition" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect(await bg()).not.toBe(lightBg);

    // The choice is applied before first paint on the next visit (no flash).
    await page.goto("/how-we-report", { waitUntil: "commit" });
    // At "commit" the document may not exist yet, so the check must tolerate a null root.
    await page.waitForFunction(() => document.documentElement?.dataset.theme === "dark");
    await page.getByRole("button", { name: "Switch to Morning edition" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("the skip link is the first focusable element and jumps to the main content", async ({
    page,
  }) => {
    await page.goto("/how-we-report");
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Skip to content" });
    await expect(skip).toBeFocused();
    await expect(skip).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#main$/);
  });

  test("every page has exactly one h1", async ({ page }) => {
    const paths = [
      "/",
      "/subscribe",
      "/sample",
      "/how-we-report",
      "/editions",
      "/privacy",
      "/terms",
      "/status",
      "/no-such-page",
    ];
    for (const path of paths) {
      await page.goto(path);
      await expect(page.locator("h1"), path).toHaveCount(1);
    }
  });

  test("the signed-in preferences page shows the saved choices", async ({ page, context }) => {
    await context.addCookies([
      { name: "mm_test_signed_in", value: "1", url: "http://localhost:3100" },
    ]);
    await page.goto("/preferences");
    await expect(page.getByRole("heading", { name: "Your subscription" })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: /^AI/ })).toBeChecked();
    await expect(page.getByLabel("City", { exact: true })).toHaveValue("Pune, Maharashtra");
    await expect(page.getByRole("button", { name: "Save changes" })).toBeVisible();
  });
});
