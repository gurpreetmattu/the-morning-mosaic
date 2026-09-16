"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.db.engine import get_sessionmaker


def db_session() -> Iterator[Session]:
    """A request-scoped transaction: committed on success, rolled back on error.

    Routes are synchronous, so Starlette runs them in its threadpool and each
    gets its own session (see docs/adr/0001).
    """
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def settings() -> Settings:
    return get_settings()
