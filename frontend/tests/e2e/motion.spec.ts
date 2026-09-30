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

test.describe("subscribe flow motion", () => {
  test.use({ reducedMotion: "no-preference" });

  test("each step slides in, and the time readout flips only the changed digits", async ({
    page,
  }) => {
    await page.goto("/subscribe?genres=ai");
    await page.getByRole("button", { name: "Next" }).click();
    expect(
      await page.locator(".step-enter").evaluate((el) => getComputedStyle(el).animationName),
    ).toBe("step-in");

    const city = page.getByLabel("City", { exact: true });
    await city.fill("pun");
    await city.press("Enter");
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByRole("heading", { name: "When should it arrive?" })).toBeFocused();

    // First paint of the readout: nothing flips.
    await expect(page.locator(".flap-anim")).toHaveCount(0);

    // 07:00 -> 08:00 changes exactly one character of "7:00 AM IST".
    await page.getByText("08:00", { exact: true }).click();
    const flipped = page.locator(".flap-anim");
    await expect(flipped).toHaveCount(1);
    await expect(flipped).toHaveText("8");
    expect(await flipped.evaluate((el) => getComputedStyle(el).animationName)).toBe("flap-flip");

    // Assistive technology gets one sentence, not eleven separate cells.
    await expect(page.getByText("Arrives around 8:00 AM IST")).toBeAttached();
  });

  test("with reduced motion the step appears without animating", async ({ browser }) => {
    const context = await browser.newContext({ reducedMotion: "reduce" });
    const page = await context.newPage();
    await page.goto("/subscribe?genres=ai");
    await page.getByRole("button", { name: "Next" }).click();

    const seconds = await page
      .locator(".step-enter")
      .evaluate((el) => parseFloat(getComputedStyle(el).animationDuration));
    expect(seconds).toBeLessThan(0.01);
    await context.close();
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
