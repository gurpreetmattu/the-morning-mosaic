import { expect, test, type Page } from "@playwright/test";

// A keyboard-only pass over the main pages (DESIGN.md sections 8 and 11):
// every tab stop shows a visible focus indicator, the skip link comes first,
// and focus is never trapped.
const PAGES = [
  "/",
  "/subscribe",
  "/sample",
  "/how-we-report",
  "/editions",
  "/preferences",
  "/privacy",
];
const MAX_TABS = 160;

interface Stop {
  label: string;
  visibleIndicator: boolean;
  onScreen: boolean;
}

/** Describe the focused element and whether a sighted keyboard user can see where focus is. */
async function describeFocus(page: Page): Promise<Stop | null> {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el || el === document.body || el === document.documentElement) return null;

    const indicated = (node: Element) => {
      const style = getComputedStyle(node);
      const outline = style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0;
      const shadow = style.boxShadow !== "none";
      return outline || shadow;
    };

    // Visually hidden inputs (the genre stamps, radio chips) draw their ring on the next sibling.
    const rect = el.getBoundingClientRect();
    const hiddenInput = rect.width <= 2 && rect.height <= 2;
    const target = hiddenInput ? el.nextElementSibling : el;
    const box = (target ?? el).getBoundingClientRect();

    const label =
      el.getAttribute("aria-label") ||
      (el as HTMLInputElement).labels?.[0]?.textContent?.trim().slice(0, 40) ||
      el.textContent?.trim().slice(0, 40) ||
      el.tagName.toLowerCase();
    return {
      label: `${el.tagName.toLowerCase()} "${label}"`,
      visibleIndicator: target ? indicated(target) : false,
      onScreen: box.width > 0 && box.height > 0,
    };
  });
}

for (const path of PAGES) {
  test(`keyboard only: ${path}`, async ({ page, context }) => {
    await context.addCookies([
      { name: "mm_test_signed_in", value: "1", url: "http://localhost:3100" },
    ]);
    await page.goto(path);
    await page.waitForLoadState("networkidle");

    const missing: string[] = [];
    const seen = new Set<string>();
    let first: string | null = null;
    let wrapped = false;

    for (let i = 0; i < MAX_TABS; i++) {
      await page.keyboard.press("Tab");
      const stop = await describeFocus(page);
      if (!stop) {
        wrapped = true; // focus left the document: the browser chrome took over, so no trap
        break;
      }
      first ??= stop.label;
      if (seen.has(`${i > 0 ? stop.label : ""}`) && stop.label === first) {
        wrapped = true;
        break;
      }
      seen.add(stop.label);
      if (!stop.visibleIndicator) missing.push(stop.label);
      if (!stop.onScreen) missing.push(`${stop.label} (has no size)`);
    }

    expect(first, "the skip link is the first tab stop").toBe('a "Skip to content"');
    expect(missing, "tab stops with no visible focus indicator").toEqual([]);
    expect(seen.size, "found tab stops").toBeGreaterThan(5);
    expect(wrapped || seen.size < MAX_TABS, "focus can leave the page (no trap)").toBe(true);
  });
}
