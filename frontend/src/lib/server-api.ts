// Server Components read public, unauthenticated data (the archive) directly
// from the backend, server-side. Anything that needs the reader's or admin's
// session cookie is a Client Component instead (see src/lib/api.ts), because
// that cookie lives in the browser, not on this server.

const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

const TIMEOUT_MS = 5000;

export async function serverGet<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${backendOrigin}${path}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

/**
 * For a page that is "not found" only when the backend says so (404). Any other failure — the
 * backend down, a 5xx, a timeout — throws, so the reader gets the error page with a retry
 * instead of a misleading 404 that search engines and links would remember.
 */
export async function serverGetStrict<T>(path: string): Promise<T | null> {
  const response = await fetch(`${backendOrigin}${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Backend returned ${response.status} for ${path}`);
  return (await response.json()) as T;
}

/**
 * For public pages that may be cached briefly (the landing page): revalidated
 * every `seconds`, bounded by a timeout, and null on any failure — including
 * the backend being unreachable, as it is during `next build`.
 */
export async function serverGetRevalidated<T>(path: string, seconds: number): Promise<T | null> {
  try {
    const response = await fetch(`${backendOrigin}${path}`, {
      next: { revalidate: seconds },
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}
