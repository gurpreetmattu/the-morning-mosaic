import { afterEach, describe, expect, it, vi } from "vitest";

import LatestEditionPage from "./page";

const redirect = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ redirect }));

function stubArchive(body: unknown, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok, json: async () => body })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  redirect.mockReset();
});

describe("LatestEditionPage", () => {
  it("redirects to the newest published edition", async () => {
    stubArchive({
      editions: [
        { edition_date: "2026-10-04", edition_number: 5 },
        { edition_date: "2026-10-03", edition_number: 4 },
      ],
      has_more: false,
    });
    await LatestEditionPage();
    expect(redirect).toHaveBeenCalledWith("/editions/2026-10-04");
  });

  it("falls back to the layout example when nothing is published", async () => {
    stubArchive({ editions: [], has_more: false });
    await LatestEditionPage();
    expect(redirect).toHaveBeenCalledWith("/sample");
  });

  it("falls back to the layout example when the backend is down", async () => {
    stubArchive({}, false);
    await LatestEditionPage();
    expect(redirect).toHaveBeenCalledWith("/sample");
  });
});
