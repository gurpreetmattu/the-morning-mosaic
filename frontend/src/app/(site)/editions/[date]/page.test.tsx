import { afterEach, describe, expect, it, vi } from "vitest";

import ArchiveEditionPage from "./page";

const notFound = vi.hoisted(() =>
  vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
);
vi.mock("next/navigation", () => ({ notFound }));

const call = (date: string) => ArchiveEditionPage({ params: Promise.resolve({ date }) });

function stubFetch(status: number, body: unknown = {}) {
  const fetchMock = vi.fn(async () => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  notFound.mockClear();
});

describe("ArchiveEditionPage", () => {
  it("never sends a malformed date to the backend", async () => {
    const fetchMock = stubFetch(200);
    for (const bad of ["..%2Fadmin", "../x", "2026-13-40", "2026-02-30", "latest-news"]) {
      await expect(call(bad)).rejects.toThrow("NEXT_NOT_FOUND");
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("is a 404 only when the backend says the edition does not exist", async () => {
    stubFetch(404);
    await expect(call("2026-10-04")).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("surfaces a backend failure as an error, not a 404", async () => {
    stubFetch(503);
    await expect(call("2026-10-04")).rejects.toThrow("Backend returned 503");
    expect(notFound).not.toHaveBeenCalled();
  });
});
