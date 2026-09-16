# ADR 0002 — `web` is the single public origin; there is no load balancer

**Status:** accepted
**Date:** 2026-09-17

## Context

The backend's session and CSRF cookies (`app/api/session.py`,
`app/api/admin_session.py`) are first-party by design: the CSRF cookie is
readable by page script only because it shares an origin with the page.
Every emailed link (opt-in, unsubscribe, feedback, PDF, magic-link login)
is also built from a single `BASE_URL`, as if the whole product had one
public hostname.

But there are two Cloud Run services — `web` (Next.js) and `api`
(FastAPI) — each with its own generated URL, and CLAUDE.md's own
"currently the Cloud Run `.run.app` URL; later the custom domain" phrasing
for `BASE_URL` only works if the browser genuinely sees one origin. The
conventional fix is a load balancer (an external HTTPS LB with serverless
NEGs for both services, URL-map path routing, a managed TLS certificate)
unifying both under one custom domain.

That requires a domain nobody has bought, and infrastructure this project
doesn't have yet (see `docs/BACKLOG.md`'s Blockers).

## Decision

`web` is the single public origin, in every environment, including
production. `frontend/src/proxy.ts` (Next.js 16's Proxy, formerly
Middleware) forwards everything FastAPI needs to serve — the JSON API
(`/api/*`, `/admin/api/*`) and every emailed-link path — to `BACKEND_ORIGIN`,
which points at the `api` Cloud Run service's own URL. `BASE_URL` is
`web`'s URL. A browser or an email client never addresses `api` directly.

## Consequences

- No load balancer, no managed certificate, no domain purchase required to
  reach a fully working, cookie-correct deployment. When a custom domain
  does exist later, mapping it to `web` is the only change needed anywhere
  — `api`'s URL never appears outside `BACKEND_ORIGIN`.
- `api` is invoked by `web`'s own Cloud Run instances, over the public
  internet, without an identity token — see the note directly in
  `infra/cloud_run_api.tf`. Locking `api`'s IAM invoker down to `web`'s
  service account would need `web`'s proxy code to mint one; not built.
  Recorded in `docs/BACKLOG.md`.
- Every request `web` proxies costs one extra hop (browser → `web` →
  `api`) versus a load balancer routing directly. At this project's scale
  (`MAX_ACTIVE_SUBSCRIBERS` starts at 400) this is not a binding
  constraint; revisit if traffic ever approaches Cloud Run's own limits.
- This had to be Proxy, not `next.config.ts`'s `rewrites()`. `rewrites()`
  is resolved once at build time into the routes manifest, so a
  `process.env.BACKEND_ORIGIN` read inside it gets frozen into the built
  image and ignores whatever the variable is set to at deploy time — the
  opposite of "build once, configure per environment" a container image
  needs. Confirmed by building the image and running it with a different
  `BACKEND_ORIGIN`, not by inspection alone. Proxy runs the request path
  fresh in the actual deployed process, so the env var is read where it's
  actually set.
