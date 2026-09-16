import type { NextConfig } from "next";

/**
 * In production, this frontend and the FastAPI backend are meant to sit
 * behind one public hostname (a load balancer routing /api/*, /admin/api/*,
 * and the emailed-link paths to the API service — see docs/BACKLOG.md under
 * the frontend entry). That is what makes the backend's session and CSRF
 * cookies, which are first-party and same-origin by design, actually work:
 * the browser never sees two origins.
 *
 * Locally there is no load balancer, so this rewrite stands in for it: the
 * browser only ever talks to this Next.js server, which proxies API calls
 * to BACKEND_ORIGIN server-side. Cookies the backend sets flow through
 * untouched, becoming first-party to this origin exactly as they will once
 * the real routing exists.
 */
const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backendOrigin}/api/:path*` },
      { source: "/admin/api/:path*", destination: `${backendOrigin}/admin/api/:path*` },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
