import type { NextConfig } from "next";

/**
 * This app and the FastAPI backend must share one public origin: the
 * backend's session and CSRF cookies (app/api/session.py,
 * app/api/admin_session.py) are first-party by design, and every emailed
 * link (opt-in, unsubscribe, feedback, PDF, magic-link login) is built from
 * `BASE_URL` as if it were a single hostname shared by both.
 *
 * Rather than standing up a load balancer to unify two Cloud Run services
 * under a custom domain — infrastructure this project doesn't have yet, and
 * a domain nobody has bought — this app IS that single origin, in prod as
 * well as in dev: `src/proxy.ts` forwards everything the backend needs to
 * serve server-side to BACKEND_ORIGIN, and Cloud Run's own `.run.app` URL
 * for *this* service is `BASE_URL`. When a custom domain exists later,
 * mapping it to this service is the only change required — see
 * infra/README.md.
 */

const nextConfig: NextConfig = {
  // A self-contained `server.js` plus only the dependencies actually used,
  // for a minimal production image (see Dockerfile).
  output: "standalone",
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
