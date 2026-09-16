// A thin fetch wrapper. Every call is relative ("/api/...", "/admin/api/..."),
// so the browser only ever talks to this frontend's own origin — see
// next.config.ts for why that matters for cookies.

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown) {
    const message =
      body && typeof body === "object" && "message" in body
        ? String((body as { message?: unknown }).message)
        : `Request failed with status ${status}`;
    super(message);
    this.status = status;
    this.body = body;
  }
}

/**
 * Find one cookie's value in a `document.cookie`-style string. Pure, so it's
 * tested directly; `readCookie` below is the thin, untestable wrapper around
 * the real `document.cookie`.
 */
export function parseCookie(cookieHeader: string, name: string): string | null {
  const prefix = `${name}=`;
  for (const part of cookieHeader.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }
  return null;
}

/**
 * Read one cookie by name. Only cookies the backend deliberately marked
 * non-HttpOnly (the CSRF ones) are readable this way; a session cookie
 * never is, by design.
 */
export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  return parseCookie(document.cookie, name);
}

export const READER_CSRF_COOKIE = "csrf";
export const READER_CSRF_HEADER = "X-CSRF-Token";
export const ADMIN_CSRF_COOKIE = "admin_csrf";
export const ADMIN_CSRF_HEADER = "X-CSRF-Token";

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  const body = await parseBody(response);
  if (!response.ok) {
    throw new ApiError(response.status, body);
  }
  return body as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

/** A write that needs the double-submit CSRF pair: the cookie plus the header echoing it. */
function csrfWrite<T>(
  path: string,
  method: "POST" | "PATCH" | "DELETE",
  body: unknown,
  cookieName: string,
  headerName: string,
): Promise<T> {
  const token = readCookie(cookieName);
  const headers: Record<string, string> = {};
  if (token) headers[headerName] = token;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  return request<T>(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function readerPost<T>(path: string, body?: unknown): Promise<T> {
  return csrfWrite<T>(path, "POST", body, READER_CSRF_COOKIE, READER_CSRF_HEADER);
}

export function readerPatch<T>(path: string, body?: unknown): Promise<T> {
  return csrfWrite<T>(path, "PATCH", body, READER_CSRF_COOKIE, READER_CSRF_HEADER);
}

export function adminPost<T>(path: string, body?: unknown): Promise<T> {
  return csrfWrite<T>(path, "POST", body, ADMIN_CSRF_COOKIE, ADMIN_CSRF_HEADER);
}

// Signup has no session yet, so it needs no CSRF pair — the request is
// authorised by nothing but rate limiting and Turnstile, same as the
// backend route itself.
export function publicPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
