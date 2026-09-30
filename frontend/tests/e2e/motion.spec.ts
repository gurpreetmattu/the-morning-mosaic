import { expect, test } from "@playwright/test";

// DESIGN.md section 10 (motion inventory) and 6.2 (genre motifs).

test.describe("first-visit masthead reveal", () => {
  test.use({ reducedMotion: "no-preference" });

  test("plays on the first landing visit of a session, and not again", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-reveal", "1");

    const animation = (selector: string) =>
      page
        .locator(selector)
        .first()
        .evaluate((el) => getComputedStyle(el).animationName);
    expect(await animation(".plate-letter")).toBe("press-in");
    expect(await animation(".plate-rule")).toBe("draw-rule");
    expect(await animation(".reveal-type")).toBe("type-in");
    expect(await animation(".preview-unfold")).toBe("unfold");

    // Same session, second visit: no flag, so nothing plays.
    await page.reload();
    await expect(page.locator("html")).not.toHaveAttribute("data-reveal", /.*/);
    expect(await animation(".plate-letter")).toBe("none");
  });

  test("is saved for the landing page, not spent on another first page", async ({ page }) => {
    await page.goto("/subscribe");
    await expect(page.locator("html")).not.toHaveAttribute("data-reveal", /.*/);

    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-reveal", "1");
  });

  test("finishes well inside a second", async ({ page }) => {
    await page.goto("/");
    // Last letter starts at 15 x 30 ms and runs 260 ms; the rule ends at 800 ms.
    await expect
      .poll(() =>
        page
          .locator(".plate-letter")
          .last()
          .evaluate((el) => getComputedStyle(el).opacity),
      )
      .toBe("1");
  });
});

test.describe("with reduced motion", () => {
  test("the reveal collapses to its end state instead of hiding the nameplate", async ({
    browser,
  }) => {
    const context = await browser.newContext({ reducedMotion: "reduce" });
    const page = await context.newPage();
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-reveal", "1");

    // No stagger delay and a ~0 duration: every letter is visible almost immediately.
    const opacities = await page
      .locator(".plate-letter")
      .evaluateAll((els) => els.map((el) => getComputedStyle(el).opacity));
    await expect
      .poll(async () =>
        page
          .locator(".plate-letter")
          .last()
          .evaluate((el) => getComputedStyle(el).opacity),
      )
      .toBe("1");
    expect(opacities.length).toBe(16);
    await context.close();
  });
});

test.describe("nameplate semantics", () => {
  test("the h1 reads as one name, not 16 letters", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: "The Morning Mosaic" })).toBeVisible();
  });
});

test.describe("genre motifs", () => {
  test("every genre stamp carries its own decorative motif in the genre ink", async ({ page }) => {
    await page.goto("/");
    const genres = [
      "india",
      "politics",
      "business",
      "technology",
      "ai",
      "sports",
      "gaming",
      "bollywood",
      "hollywood",
      "music",
    ];
    for (const genre of genres) {
      const motif = page.locator(`#genres .motif-${genre}`);
      await expect(motif, genre).toHaveCount(1);
      await expect(motif, genre).toHaveAttribute("aria-hidden", "true");
      const { mask, bg } = await motif.evaluate((el) => {
        const style = getComputedStyle(el);
        return { mask: style.maskImage || style.webkitMaskImage, bg: style.backgroundColor };
      });
      expect(mask, `${genre} mask`).toContain("data:image/svg+xml");
      expect(bg, `${genre} colour`).not.toBe("rgba(0, 0, 0, 0)");
    }
  });

  test("the ten motifs are all different", async ({ page }) => {
    await page.goto("/");
    const masks = await page
      .locator("#genres .motif")
      .evaluateAll((els) => els.map((el) => getComputedStyle(el).maskImage));
    expect(new Set(masks).size).toBe(10);
  });
});
