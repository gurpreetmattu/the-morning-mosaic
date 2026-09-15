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

Two connection settings are not optional against Neon's pooled endpoint:

- `pool_pre_ping=True` — Neon closes idle connections, and without this the
  first query after an idle period raises instead of reconnecting.
- `prepare_threshold=None` — the pooled endpoint is PgBouncer in transaction
  mode, which cannot carry server-side prepared statements across
  transactions. psycopg 3 prepares automatically after a few executions, so it
  has to be told not to.
