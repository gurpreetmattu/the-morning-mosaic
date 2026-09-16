import { NextRequest, NextResponse } from "next/server";

/**
 * Proxies FastAPI's paths to BACKEND_ORIGIN — see next.config.ts for why
 * this app and the backend must share one origin, and infra/README.md for
 * how BACKEND_ORIGIN is set in prod.
 *
 * This has to be Proxy (Next 16's rename of Middleware — see AGENTS.md),
 * not `next.config.ts`'s `rewrites()`: Next resolves `rewrites()` once, at
 * build time, into the routes manifest, so a `process.env` read inside it
 * is frozen into the image and can't be overridden per-deployment by an env
 * var — exactly the "build once, configure via env at deploy" a container
 * image needs. Proxy runs the request path fresh on every request in the
 * actual running process, so the env var is read where it's actually set.
 * Confirmed empirically: rewrites() baked in 127.0.0.1:8000 at build time
 * and ignored BACKEND_ORIGIN set on `docker run`; this doesn't.
 */
export function proxy(request: NextRequest) {
  const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";
  const target = new URL(request.nextUrl.pathname + request.nextUrl.search, backendOrigin);
  return NextResponse.rewrite(target);
}

// Must be a static array literal — Next.js parses `matcher` at build time
// and refuses anything computed. Keep in sync with the prefix list in the
// doc comment above: the JSON API, and every emailed-link path.
export const config = {
  matcher: [
    "/api/:path*",
    "/admin/api/:path*",
    "/opt-in/:path*",
    "/unsubscribe/:path*",
    "/feedback/:path*",
    "/pdf/:path*",
    "/login/:path*",
    "/admin/login/:path*",
  ],
};
