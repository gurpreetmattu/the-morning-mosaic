import type { Page } from "@playwright/test";

/** Routes covered by the health and accessibility suites. `status` is the expected HTTP status. */
export const ROUTES: { path: string; status: number }[] = [
  { path: "/", status: 200 },
  { path: "/subscribe", status: 200 },
  { path: "/sample", status: 200 },
  { path: "/how-we-report", status: 200 },
  { path: "/editions", status: 200 },
  { path: "/editions/2026-09-30", status: 200 },
  { path: "/preferences", status: 200 },
  { path: "/privacy", status: 200 },
  { path: "/terms", status: 200 },
  { path: "/status", status: 200 },
  { path: "/no-such-page", status: 404 },
];

/** DESIGN.md section 20 viewports. */
export const VIEWPORTS = [
  { name: "360x800", width: 360, height: 800 },
  { name: "390x844", width: 390, height: 844 },
  { name: "768x1024", width: 768, height: 1024 },
  { name: "1280x800", width: 1280, height: 800 },
  { name: "1536x900", width: 1536, height: 900 },
] as const;

export const SCHEMES = ["light", "dark"] as const;

// Must match `PORT` in playwright.config.ts.
const SITE_HOST = "localhost:3100";

/** Console errors and requests to any origin other than the site itself. */
export function watch(page: Page, expectedDocumentStatus = 200) {
  const consoleErrors: string[] = [];
  const foreignRequests: string[] = [];
  const failedRequests: string[] = [];
  const badResponses: string[] = [];

  page.on("console", (msg) => {
    // Chrome logs every HTTP error status as a console error. Those are judged by the
    // response check below (which knows which statuses are expected), not here.
    if (msg.type() === "error" && !msg.text().startsWith("Failed to load resource:")) {
      consoleErrors.push(msg.text());
    }
  });
  page.on("response", (res) => {
    if (res.status() < 400) return;
    const { pathname } = new URL(res.url());
    const isDocument = res.request().resourceType() === "document";
    const signedOutSessionCheck = pathname === "/api/me" && res.status() === 401;
    if ((isDocument && res.status() === expectedDocumentStatus) || signedOutSessionCheck) return;
    badResponses.push(`${res.status()} ${res.url()}`);
  });
  page.on("pageerror", (err) => consoleErrors.push(err.message));
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.protocol.startsWith("http") && url.host !== SITE_HOST) foreignRequests.push(req.url());
  });
  page.on("requestfailed", (req) => {
    // The browser cancels in-flight Next link prefetches (?_rsc=) when a page settles or
    // navigates; that is not a failure. Anything else that fails is.
    if (req.failure()?.errorText === "net::ERR_ABORTED") return;
    failedRequests.push(`${req.method()} ${req.url()}`);
  });
  return { consoleErrors, foreignRequests, failedRequests, badResponses };
}

/** True when the page is wider than the viewport (a horizontal scrollbar would appear). */
export async function hasHorizontalOverflow(page: Page): Promise<boolean> {
  return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
}
