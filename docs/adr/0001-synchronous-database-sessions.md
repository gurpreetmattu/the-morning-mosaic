# ADR 0001 — Synchronous SQLAlchemy sessions

**Status:** accepted
**Date:** 2026-09-16

## Context

SQLAlchemy 2 and psycopg 3 both support sync and async. The choice has to be
made once, at the session layer, because it propagates into every agent, job,
and API route.

Two facts shape the decision:

- `MAX_ACTIVE_SUBSCRIBERS` starts at 400, capped by the Gmail sending quota of
  roughly 500 recipients per day. The API serves signup, preferences, archive,
  and feedback for that population — traffic measured in requests per minute,
  not per second.
- The work is dominated by batch jobs, not concurrent requests. The build job
  fans out across ten genres; the delivery job claims rows with
  `SELECT ... FOR UPDATE` and must guarantee at-most-once sending.

## Decision

Use synchronous sessions throughout. FastAPI routes are declared with `def`
rather than `async def`, so Starlette runs them in its threadpool.

## Consequences

- Row-level locking in the delivery job stays easy to read and to test. The
  at-most-once guarantee is the highest-risk invariant in the system, and
  `async` adds a class of ordering bugs there for no throughput benefit.
- LangGraph and the LLM client may still be async internally; they do not hold
  database sessions across await points, so the two do not mix.
- The API's concurrency ceiling is the threadpool size. At the subscriber cap
  this is far from binding. If the cap were raised by an order of magnitude,
  this decision should be revisited before anything else.
- Migrating later means touching every call site. Accepted deliberately: the
  cost of being wrong is a mechanical refactor, not a redesign.

## Notes

Two connection settings, both verified for real against the actual Neon
endpoint (2026-09-29 — see `docs/BACKLOG.md`), not just reasoned about:

- `pool_pre_ping=True` — **confirmed load-bearing.** An 8-minute real idle
  wait on a pooled connection, then a query: without this setting,
  `OperationalError: SSL connection has been closed unexpectedly`; with it,
  the same idle period recovers transparently. Neon does close idle
  connections, exactly as this ADR originally assumed.
- `prepare_threshold=None` — kept, but the original reasoning for it no
  longer reproduces. The classic failure ("PgBouncer in transaction mode
  can't carry a server-side prepared statement across a backend swap") was
  pushed through 60 rounds past psycopg's auto-prepare threshold, with the
  override on and off, on the real endpoint: zero errors either way. Neon's
  current PgBouncer already re-prepares statements itself across backend
  swaps (its own `PGBOUNCER_N`-named passthrough). Left in place as free,
  harmless insurance against an older or differently-configured pooler, not
  because the original bug is still reproducible here.
