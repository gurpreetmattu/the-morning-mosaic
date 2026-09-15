"""Shared fixtures.

Database tests are opt-in: they run only when TEST_DATABASE_URL points at a
PostgreSQL instance, and skip otherwise, so the default `pytest` run needs no
services. Each test runs inside a transaction that is rolled back, so the
database is left exactly as it was found.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.db.engine import normalise_url
from app.models import Base

TEST_DB_ENV = "TEST_DATABASE_URL"


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = os.getenv(TEST_DB_ENV)
    if not url:
        pytest.skip(f"{TEST_DB_ENV} is not set")
    created = create_engine(
        normalise_url(url),
        pool_pre_ping=True,
        connect_args={"prepare_threshold": None},
    )
    Base.metadata.create_all(created)
    yield created
    created.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    opened = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield opened
    finally:
        opened.close()
        transaction.rollback()
        connection.close()
