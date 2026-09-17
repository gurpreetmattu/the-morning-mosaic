"""Shared fixtures.

Database tests are opt-in: they run only when TEST_DATABASE_URL points at a
PostgreSQL instance, and skip otherwise, so the default `pytest` run needs no
services. Each test runs inside a transaction that is rolled back, so the
database is left exactly as it was found.

TEST_DATABASE_URL is also the database a developer points DATABASE_URL at to
run a job by hand (`python -m app.jobs.build`, say) — that run commits for
real. Rolling back each test's own transaction is not enough to keep those
two uses from interfering: a "this table holds exactly N rows" assertion
would see whatever a manual run left behind. The `engine` fixture truncates
everything once per test session, before any test runs, so the suite always
starts from empty regardless of what a manual run left in this database.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
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
    _truncate_all(created)
    yield created
    created.dispose()


def _truncate_all(engine: Engine) -> None:
    table_names = ", ".join(f'"{table}"' for table in Base.metadata.tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))


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
