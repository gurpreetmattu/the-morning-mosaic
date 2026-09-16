// Server Components read public, unauthenticated data (the archive) directly
// from the backend, server-side. Anything that needs the reader's or admin's
// session cookie is a Client Component instead (see src/lib/api.ts), because
// that cookie lives in the browser, not on this server.

const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

export async function serverGet<T>(path: string): Promise<T | null> {
  const response = await fetch(`${backendOrigin}${path}`, { cache: "no-store" });
  if (!response.ok) return null;
  return (await response.json()) as T;
}
