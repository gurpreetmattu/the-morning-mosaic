import { gzipSync } from "node:zlib";
import { expect, test } from "@playwright/test";

// DESIGN.md section 13 budgets, measured on the production build of the landing
// page. This guards against regressions; it is not a substitute for Lighthouse
// on throttled 4G, because nothing here is network- or CPU-throttled.
const KB = 1024;

for (const viewport of [
  { name: "desktop 1280x720", width: 1280, height: 720 },
  { name: "phone 412x823", width: 412, height: 823 },
]) {
  test(`the landing page stays inside its weight and layout-shift budgets (${viewport.name})`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.addInitScript(() => {
      const w = window as unknown as { __cls: number; __lcp: number };
      w.__cls = 0;
      w.__lcp = 0;
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries() as unknown as {
          value: number;
          hadRecentInput: boolean;
        }[]) {
          if (!entry.hadRecentInput) w.__cls += entry.value;
        }
      }).observe({ type: "layout-shift", buffered: true });
      new PerformanceObserver((list) => {
        const last = list.getEntries().at(-1);
        if (last) w.__lcp = last.startTime;
      }).observe({ type: "largest-contentful-paint", buffered: true });
    });

    const sizes = { js: 0, css: 0, fonts: 0, images: 0, other: 0 };
    const pending: Promise<void>[] = [];
    page.on("response", (response) => {
      pending.push(
        (async () => {
          const type = response.request().resourceType();
          const body = await response.body().catch(() => Buffer.alloc(0));
          // Text assets travel compressed, so measure them gzipped; fonts and images already are.
          const bytes = ["script", "stylesheet", "document"].includes(type)
            ? gzipSync(body).length
            : body.length;
          if (type === "script") sizes.js += bytes;
          else if (type === "stylesheet") sizes.css += bytes;
          else if (type === "font") sizes.fonts += bytes;
          else if (type === "image") sizes.images += bytes;
          else sizes.other += bytes;
        })(),
      );
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => document.fonts.ready);
    await Promise.all(pending);

    // Field CLS includes shifts while the reader scrolls (deferred sections rendering as they
    // approach the viewport), so scroll the whole page before reading the score.
    await page.evaluate(async () => {
      const step = Math.max(200, Math.round(window.innerHeight / 2));
      for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
        window.scrollTo(0, y);
        await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 60)));
      }
      window.scrollTo(0, document.documentElement.scrollHeight);
      await new Promise((r) => setTimeout(r, 300));
    });

    const { cls, lcp } = await page.evaluate(() => {
      const w = window as unknown as { __cls: number; __lcp: number };
      return { cls: w.__cls, lcp: w.__lcp };
    });
    const totalWithoutFonts = sizes.js + sizes.css + sizes.images + sizes.other;
    console.log(
      `landing: js ${(sizes.js / KB).toFixed(1)} KB gz, css ${(sizes.css / KB).toFixed(1)} KB, ` +
        `fonts ${(sizes.fonts / KB).toFixed(1)} KB, other ${((sizes.other + sizes.images) / KB).toFixed(1)} KB, ` +
        `total excl. fonts ${(totalWithoutFonts / KB).toFixed(1)} KB, ` +
        `CLS ${cls.toFixed(4)}, LCP ${Math.round(lcp)} ms`,
    );

    expect(sizes.js, "JS (gzipped)").toBeLessThanOrEqual(180 * KB);
    expect(totalWithoutFonts, "total page weight excluding fonts").toBeLessThanOrEqual(500 * KB);
    expect(sizes.fonts, "fonts").toBeLessThanOrEqual(200 * KB);
    expect(cls, "cumulative layout shift").toBeLessThanOrEqual(0.05);
    expect(lcp, "largest contentful paint (unthrottled)").toBeLessThanOrEqual(2500);
  });
}
