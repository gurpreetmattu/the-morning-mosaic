"""Engine and session management.

Sessions are synchronous. The jobs are batch processes and the API serves a
few hundred subscribers, so async buys nothing here while making row locking
in the delivery job harder to reason about. See docs/adr/0001.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings


def normalise_url(url: str) -> str:
    """Force the psycopg 3 driver.

    SQLAlchemy maps a bare ``postgresql://`` to psycopg2, which is not
    installed. Neon and most providers hand out the bare form.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        normalise_url(settings.database_url.get_secret_value()),
        # Neon drops idle connections; without this the first query after an
        # idle period fails instead of transparently reconnecting.
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=300,
        connect_args={
            # Classic transaction-mode PgBouncer can't carry a server-side
            # prepared statement across a backend swap between requests.
            # Verified against the real Neon endpoint (docs/BACKLOG.md) that
            # its current PgBouncer already handles this itself (its own
            # PGBOUNCER_N-named passthrough survives 60 rounds past
            # psycopg's auto-prepare threshold with no error either way) —
            # so this is no longer fixing a reproducible bug here, but it's
            # free insurance against an older or differently-configured
            # pooler, so it stays.
            "prepare_threshold": None,
        },
    )


@lru_cache(maxsize=1)
def get_direct_engine() -> Engine:
    """A connection outside Neon's pooler, for anything needing real session
    state (currently: the job lock's advisory lock — see app/jobs/locking.py
    and Settings.database_direct_url). Small and short-lived: this is never
    used for the ordinary request/job workload the pooled engine handles."""
    settings = get_settings()
    url = settings.database_direct_url or settings.database_url
    return create_engine(
        normalise_url(url.get_secret_value()),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
        connect_args={"prepare_threshold": None},
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """A transaction that commits on success and rolls back on any exception."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engine() -> None:
    """Drop pooled connections. Jobs call this before exiting."""
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    if get_direct_engine.cache_info().currsize:
        get_direct_engine().dispose()
    get_direct_engine.cache_clear()
