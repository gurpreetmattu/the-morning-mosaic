# The Morning Mosaic — frontend

Next.js (App Router) + TypeScript + Tailwind. This app only talks to the
FastAPI backend (`../backend`) over HTTP; it never touches the database
directly.

## Pages

- `/` — landing
- `/signup` — genre picker, city, delivery slot, frequency, edition
  preference, followed keywords, Turnstile
- `/archive`, `/archive/[date]` — the public, non-personalised archive
- `/preferences` — magic-link sign-in, then genres/city/slot, pause/resume,
  data export, account deletion
- `/admin` — magic-link sign-in restricted to `ADMIN_EMAIL`, then recent job
  runs, stuck deliveries, failure-notice batch approve/suppress, and the
  story-withdrawal kill switch
- `/privacy`, `/terms` — draft legal pages; see the in-page notice

## Running it

```
npm install
cp .env.local.example .env.local   # set BACKEND_ORIGIN if not the default
npm run dev
```

The backend must be running separately (`uv run uvicorn app.api.app:create_app --factory`
from `../backend`, or `python -m app.jobs.seed` first if the database is
empty — see the root README/CLAUDE.md).

## Commands

```
npm run dev          # dev server, Turbopack
npm run build         # production build
npm run start          # run the production build
npm run lint            # eslint
npm run format:check     # prettier --check
npm run typecheck         # tsc --noEmit
npm test                   # vitest
```

## Why this app proxies the backend, in prod too

The backend's session and CSRF cookies (`app/api/session.py`,
`app/api/admin_session.py`) are first-party by design, and every emailed
link (opt-in, unsubscribe, feedback, PDF, magic-link login) is built from
`BASE_URL` as if it were one hostname shared by both services. Rather than
standing up a load balancer to unify two Cloud Run services under a custom
domain nobody has bought yet, this app _is_ that single origin: `BASE_URL`
in prod is this service's own Cloud Run URL, and `src/proxy.ts` (Next 16's
Proxy, née Middleware) forwards everything FastAPI needs to serve directly
— the JSON API (`/api/*`, `/admin/api/*`) and every emailed-link page
(`/opt-in/*`, `/unsubscribe/*`, `/feedback/*`, `/pdf/*`, `/login/*`,
`/admin/login/*`) — to `BACKEND_ORIGIN` (the api service's own URL, set as
an env var in `infra/`). Cookies and redirects pass through untouched, so
from the browser's point of view there is exactly one origin, in dev and in
prod alike.

This has to be Proxy rather than `next.config.ts`'s `rewrites()`: Next
resolves `rewrites()` once, at build time, into the routes manifest, so a
`process.env` read inside it is frozen into the built image and ignores
whatever `BACKEND_ORIGIN` is set to at `docker run` or deploy time — the
opposite of "build once, configure per environment." Confirmed by actually
building the image and running it with a different `BACKEND_ORIGIN`; see
git history on this file if that regresses again.

Locally, `BACKEND_ORIGIN` points at wherever `uvicorn` is running
(`http://127.0.0.1:8000` by default). In prod, Terraform (`../infra`) wires
it to the `api` Cloud Run service's URL as an environment variable on the
`web` service — see `infra/README.md`. When a custom domain exists later,
mapping it to `web` is the only change required anywhere.
