import { expect, test, type Page } from "@playwright/test";

// The checkbox inside a stamp is visually hidden; a reader clicks the stamp.
const stamp = (page: Page, name: string) =>
  page
    .locator("label.stamp-card")
    .filter({ has: page.getByRole("checkbox", { name: new RegExp(`^${name}`) }) });

const next = (page: Page) => page.getByRole("button", { name: "Next" });

async function pickCity(page: Page, typed: string) {
  const city = page.getByLabel("City", { exact: true });
  await city.fill(typed);
  await expect(page.getByRole("option").first()).toBeVisible();
  await city.press("Enter");
}

test.describe("subscribe flow", () => {
  test("a reader can finish all four steps, choosing the city by keyboard", async ({ page }) => {
    await page.goto("/subscribe?genres=ai,music");
    await expect(page.getByRole("checkbox", { name: /^AI/ })).toBeChecked();
    await expect(page.getByRole("checkbox", { name: /^Music/ })).toBeChecked();

    await next(page).click();
    await expect(
      page.getByRole("heading", { name: "Where should we check the weather?" }),
    ).toBeFocused();
    await pickCity(page, "pun");
    await expect(page.getByLabel("City", { exact: true })).toHaveValue("Pune, Maharashtra");
    await next(page).click();

    await expect(page.getByRole("heading", { name: "When should it arrive?" })).toBeFocused();
    await page.getByText("08:00", { exact: true }).click();
    await expect(page.getByText("8:00 AM IST").first()).toBeVisible();
    await next(page).click();

    await page.getByLabel("Name", { exact: true }).fill("Asha");
    await page.getByLabel("Email", { exact: true }).fill("asha@example.test");
    await page.getByLabel(/confirm I am 18/).check();
    await page.getByLabel(/Email me The Morning Mosaic/).check();
    await page.getByRole("button", { name: "Confirm and subscribe" }).click();

    await expect(page.getByRole("heading", { name: "Check your inbox" })).toBeVisible();
  });

  test("each step refuses to continue until it is valid", async ({ page }) => {
    await page.goto("/subscribe");
    await next(page).click();
    await expect(page.getByText("Choose at least one genre.")).toBeVisible();

    await stamp(page, "India").click();
    await next(page).click();
    await page.getByLabel("City", { exact: true }).fill("Atlantis");
    await next(page).click();
    await expect(page.getByText("Pick a city from the list.")).toBeVisible();
  });

  test("a refresh keeps the choices but never stores name or email", async ({ page }) => {
    await page.goto("/subscribe");
    await stamp(page, "Sports").click();
    await next(page).click();
    await pickCity(page, "mum");
    await next(page).click();
    await next(page).click();
    await page.getByLabel("Name", { exact: true }).fill("Asha");
    await page.getByLabel("Email", { exact: true }).fill("asha@example.test");

    const stored = await page.evaluate(() => sessionStorage.getItem("mm-subscribe-draft") ?? "");
    expect(stored).toContain("mumbai");
    expect(stored).not.toContain("Asha");
    expect(stored).not.toContain("asha@example.test");

    await page.reload();
    await expect(page.getByRole("checkbox", { name: /^Sports/ })).toBeChecked();
    await next(page).click();
    await expect(page.getByLabel("City", { exact: true })).toHaveValue("Mumbai, Maharashtra");
  });

  test("the landing stamp sheet hands its genres to the flow", async ({ page }) => {
    await page.goto("/");
    await stamp(page, "Gaming").click();
    await stamp(page, "Hollywood").click();
    await page.locator("#genres").getByRole("link", { name: "Start my edition" }).click();

    await expect(page).toHaveURL(/\/subscribe\?genres=gaming,hollywood/);
    await expect(page.getByRole("checkbox", { name: /^Gaming/ })).toBeChecked();
  });

  test("the old /signup URL redirects and keeps its query", async ({ page }) => {
    await page.goto("/signup?genres=ai");
    await expect(page).toHaveURL(/\/subscribe\?genres=ai/);
  });

  test.describe("on a phone", () => {
    test.use({ viewport: { width: 360, height: 800 } });

    test("the Back/Next bar stays reachable without scrolling", async ({ page }) => {
      await page.goto("/subscribe");
      const box = await next(page).boundingBox();
      expect(box).not.toBeNull();
      // Sticky bottom bar: inside the first screenful even though the form is long.
      expect(box!.y + box!.height).toBeLessThanOrEqual(800);
      expect(box!.height).toBeGreaterThanOrEqual(44);
    });
  });
});
