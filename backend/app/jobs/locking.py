"""Single-instance guard for the scheduled jobs.

"Only one instance of each job runs at a time." Cloud Run's own concurrency
settings are the first line of defence, but a manual rerun launched while the
scheduled run is still going would slip past them, so the guard lives in the
database where both can see it.

A PostgreSQL advisory lock is used rather than a table row: it is released
automatically when the connection drops, so a job killed mid-run — a Cloud Run
timeout, an OOM — never leaves a stale lock that blocks tomorrow.

pg_advisory_lock (unlike pg_advisory_xact_lock) is scoped to the physical
backend connection, not to a transaction — which is exactly why this must
hold a raw Connection of its own for the job's whole life, rather than an ORM
Session from the shared pool: a Session returns its connection to the pool on
every commit (and may hand a *different* Session a lock-holder's own
still-open connection right back, letting a "second" lock holder trivially
re-acquire a lock its own physical connection already holds — found live via
a test that only failed once this module started committing after acquiring
the lock). A Connection checked out directly from the engine is never
returned to the pool until `.close()` runs, so it stays pinned to one backend
process for as long as this context manager is open.

The default connection comes from `get_direct_engine()`, not the ordinary
pooled engine: Neon's pooled endpoint is PgBouncer in transaction mode, which
can hand the *next* transaction on the same client connection to a different
physical backend — session-scoped locks do not survive that at all, pinned
Connection or not. `get_direct_engine()` bypasses the pooler entirely (see
Settings.database_direct_url).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, func, select

from app.db.engine import get_direct_engine

# Postgres advisory locks take a signed 64-bit key.
_SIGNED_64_MAX = 2**63


def lock_key(name: str) -> int:
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=False) - _SIGNED_64_MAX


@contextmanager
def job_lock(name: str, *, connect: Callable[[], Connection] | None = None) -> Iterator[bool]:
    """Yields True if this process holds the lock for `name`.

    The caller decides what to do when it does not; for a scheduled job that
    means exiting quietly, because another instance is already doing the work.
    """
    key = lock_key(name)
    connection = (connect or get_direct_engine().connect)()
    acquired = False
    try:
        acquired = bool(connection.scalar(select(func.pg_try_advisory_lock(key))))
        # Ends the transaction the lock-acquiring statement opened, without
        # releasing the connection itself (see module docstring) — otherwise
        # this connection sits idle-in-transaction for the whole job
        # (collection, ranking, writing — real minutes of LLM I/O with no
        # further statements on it), and Neon kills it with
        # IdleInTransactionSessionTimeout before the job can finish and
        # release the lock itself. Found live: a real business-genre build
        # ran long enough to hit exactly this.
        connection.commit()
        yield acquired
    finally:
        if acquired:
            connection.scalar(select(func.pg_advisory_unlock(key)))
            connection.commit()
        connection.close()
