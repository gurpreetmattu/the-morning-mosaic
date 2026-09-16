"""Single-instance guard for the scheduled jobs.

"Only one instance of each job runs at a time." Cloud Run's own concurrency
settings are the first line of defence, but a manual rerun launched while the
scheduled run is still going would slip past them, so the guard lives in the
database where both can see it.

A PostgreSQL advisory lock is used rather than a table row: it is released
automatically when the connection drops, so a job killed mid-run — a Cloud Run
timeout, an OOM — never leaves a stale lock that blocks tomorrow.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.engine import get_sessionmaker

# Postgres advisory locks take a signed 64-bit key.
_SIGNED_64_MAX = 2**63


def lock_key(name: str) -> int:
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=False) - _SIGNED_64_MAX


@contextmanager
def job_lock(name: str, *, session_factory: Callable[[], Session] | None = None) -> Iterator[bool]:
    """Yields True if this process holds the lock for `name`.

    The caller decides what to do when it does not; for a scheduled job that
    means exiting quietly, because another instance is already doing the work.

    The lock needs its own connection, held for the life of the job, so it
    cannot share the caller's session.
    """
    key = lock_key(name)
    session = (session_factory or get_sessionmaker())()
    acquired = False
    try:
        acquired = bool(session.scalar(select(func.pg_try_advisory_lock(key))))
        yield acquired
    finally:
        if acquired:
            session.scalar(select(func.pg_advisory_unlock(key)))
        session.close()
