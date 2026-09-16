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

## Why a same-origin proxy in dev

The backend's session and CSRF cookies (`app/api/session.py`,
`app/api/admin_session.py`) are designed to be first-party: the CSRF cookie
is readable by this app's own script only because it shares an origin with
it. In production, that's true because one load balancer is meant to route
`/api/*`, `/admin/api/*`, and the emailed-link paths (`/opt-in/*`,
`/unsubscribe/*`, `/feedback/*`, `/pdf/*`, `/login/*`, `/admin/login/*`) to
the FastAPI service, and everything else to this one, all under a single
public hostname (see `docs/BACKLOG.md` — that routing doesn't exist yet;
Terraform hasn't been written).

Locally there's no load balancer, so `next.config.ts` rewrites `/api/*` and
`/admin/api/*` to `BACKEND_ORIGIN` as a stand-in: the browser only ever
talks to `localhost:3000`, and Next's own server proxies those two prefixes
to FastAPI, cookies and all. The emailed-link paths are **not** proxied —
they're pages a person reaches by clicking a link in an actual email, so in
dev you open them directly against the backend's own URL (e.g.
`http://127.0.0.1:8000/login/<token>`), exactly as the real load balancer
will route them once it exists.
