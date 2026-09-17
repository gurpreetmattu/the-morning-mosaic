"""Delivery claim: at-most-once holds across two real, separate database
connections racing for the same reader — not just within one transaction.

Every other delivery test uses the shared `session` fixture, which runs
each test inside one savepoint-scoped transaction. That's real isolation
for one connection, but it can never exercise `SELECT ... FOR UPDATE SKIP
LOCKED` racing a *second* transaction, since there is no second
transaction — two "sessions" bound to the same connection are still one
transaction as far as Postgres locking is concerned. These tests open two
independent sessions against the real test database (via the session-scoped
`engine` fixture, not `session`), synchronise them with a barrier so both
attempt the same claim at the same moment, and clean up everything they
commit themselves, since the usual per-test rollback does not apply here.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from datetime import date, time
from typing import Any

import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.jobs.delivery import claim
from app.models.editions import Delivery
from app.models.enums import (
    DeliveryStatus,
    DeliveryType,
    EditionPreference,
    Frequency,
    SubscriptionStatus,
)
from app.models.users import User

pytestmark = pytest.mark.integration

EDITION = date(2099, 1, 1)  # a date no other test uses, for a clean footprint


@pytest.fixture
def race(engine: Engine) -> Iterator[tuple[sessionmaker[Session], uuid.UUID]]:
    """A real committed User, cleaned up (User + any Delivery it claimed)
    when the test finishes, regardless of outcome."""
    factory = sessionmaker(bind=engine)
    setup = factory()
    user = User(
        email=f"racer-{uuid.uuid4()}@example.com",
        name="Racer",
        status=SubscriptionStatus.ACTIVE,
        delivery_slot=time(7, 0),
        frequency=Frequency.DAILY,
        edition_preference=EditionPreference.MIXED,
        age_confirmed=True,
    )
    setup.add(user)
    setup.commit()
    user_id = user.id
    setup.close()

    try:
        yield factory, user_id
    finally:
        cleanup = factory()
        cleanup.execute(delete(Delivery).where(Delivery.user_id == user_id))
        cleanup.execute(delete(User).where(User.id == user_id))
        cleanup.commit()
        cleanup.close()


def race_for_claim(
    factory: sessionmaker[Session], user_id: uuid.UUID, *, attempts: int
) -> list[Any]:
    """Runs `attempts` threads that all call `claim()` for the same
    (user_id, EDITION) at the same moment, and returns each thread's
    outcome — a `Delivery`, `None`, or a raised exception."""
    ready = threading.Barrier(attempts)
    results: list[Any] = [None] * attempts

    def attempt(index: int) -> None:
        session = factory()
        try:
            ready.wait(timeout=5)
            try:
                delivery = claim(session, user_id=user_id, edition_date=EDITION)
                if delivery is not None:
                    # The real exclusivity guarantee: run_delivery marks the
                    # row SENDING and commits immediately after claim()
                    # returns it (app/jobs/delivery.py). claim() alone
                    # returns an existing PENDING row to any caller — it is
                    # this immediate commit that stops a second caller from
                    # doing the same.
                    delivery.status = DeliveryStatus.SENDING
                results[index] = delivery
                session.commit()
            except BaseException as exc:  # recorded below, not swallowed
                results[index] = exc
                session.rollback()
        finally:
            session.close()

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(attempts)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    return results


def test_two_processes_racing_for_the_first_claim_produce_exactly_one_row(
    race: tuple[sessionmaker[Session], uuid.UUID],
) -> None:
    factory, user_id = race

    results = race_for_claim(factory, user_id, attempts=2)

    claimed = [r for r in results if isinstance(r, Delivery)]
    turned_away = [r for r in results if r is None]
    assert len(claimed) == 1, results
    assert len(turned_away) == 1, results

    check = factory()
    try:
        rows = list(
            check.scalars(
                select(Delivery).where(
                    Delivery.user_id == user_id, Delivery.edition_date == EDITION
                )
            )
        )
        assert len(rows) == 1
        assert rows[0].status is DeliveryStatus.SENDING
    finally:
        check.close()


def test_six_processes_racing_still_produce_exactly_one_row(
    race: tuple[sessionmaker[Session], uuid.UUID],
) -> None:
    factory, user_id = race

    results = race_for_claim(factory, user_id, attempts=6)

    claimed = [r for r in results if isinstance(r, Delivery)]
    turned_away = [r for r in results if r is None]
    assert len(claimed) == 1, results
    assert len(turned_away) == 5, results


def test_a_row_already_marked_sending_is_never_claimed_twice(
    race: tuple[sessionmaker[Session], uuid.UUID],
) -> None:
    factory, user_id = race

    setup = factory()
    setup.add(
        Delivery(
            user_id=user_id,
            edition_date=EDITION,
            type=DeliveryType.NEWSLETTER,
            status=DeliveryStatus.SENDING,
        )
    )
    setup.commit()
    setup.close()

    results = race_for_claim(factory, user_id, attempts=3)

    assert all(r is None for r in results), results
