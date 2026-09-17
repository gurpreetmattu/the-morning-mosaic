// A tiny router around a mocked `fetch`, shared by the page component
// tests. Real backend responses are JSON bodies over HTTP status codes;
// this reproduces just enough of `Response` for `app/lib/api.ts`'s
// `parseBody`/`request` to work against it.

import { vi } from "vitest";

export interface RouteResult {
  status?: number;
  body?: unknown;
}

export type RouteHandler =
  RouteResult | ((path: string, init?: RequestInit) => RouteResult | Promise<RouteResult>);

export interface FetchMock {
  fetchMock: ReturnType<typeof vi.fn>;
  calls: { path: string; init?: RequestInit }[];
}

/**
 * Routes are matched by exact path, or by longest-prefix for paths that
 * carry an id or date segment (e.g. "/admin/api/stories/" matches
 * "/admin/api/stories/abc/withdraw").
 */
export function mockFetch(routes: Record<string, RouteHandler>): FetchMock {
  const calls: { path: string; init?: RequestInit }[] = [];
  const keys = Object.keys(routes).sort((a, b) => b.length - a.length);

  const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
    calls.push({ path, init });
    const key = keys.find((candidate) => path === candidate || path.startsWith(candidate));
    if (!key) throw new Error(`test-fetch: no mocked route for ${path}`);

    const value = routes[key];
    const result = typeof value === "function" ? await value(path, init) : value;
    const status = result.status ?? 200;
    const body = result.body;

    return {
      ok: status >= 200 && status < 300,
      status,
      text: async () => (body === undefined ? "" : JSON.stringify(body)),
    } as unknown as Response;
  });

  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, calls };
}
