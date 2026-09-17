"""RateLimiter: a real shared counter, not one per process."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.security import RateLimiter

pytestmark = pytest.mark.integration

NOW = datetime(2026, 9, 17, 10, 0, 0, tzinfo=UTC)


def limiter(name: str = "test", limit: int = 3, window_seconds: float = 60) -> RateLimiter:
    return RateLimiter(name=name, limit=limit, window_seconds=window_seconds)


def test_a_fresh_key_is_allowed(session: Session) -> None:
    assert limiter().check(session, "1.2.3.4", now=NOW)


def test_the_limit_is_enforced_within_the_window(session: Session) -> None:
    subject = limiter(limit=3)
    assert subject.check(session, "1.2.3.4", now=NOW)
    assert subject.check(session, "1.2.3.4", now=NOW)
    assert subject.check(session, "1.2.3.4", now=NOW)
    assert not subject.check(session, "1.2.3.4", now=NOW)


def test_two_separate_limiter_instances_share_the_same_count(session: Session) -> None:
    """The bug this replaces: an in-memory limiter kept a separate count per
    process, so with N Cloud Run instances the real limit was limit x N.
    Two independently constructed RateLimiter objects (standing in for two
    instances) with the same name must still share one count."""
    on_instance_a = limiter(name="shared", limit=3)
    on_instance_b = limiter(name="shared", limit=3)

    assert on_instance_a.check(session, "1.2.3.4", now=NOW)
    assert on_instance_b.check(session, "1.2.3.4", now=NOW)
    assert on_instance_a.check(session, "1.2.3.4", now=NOW)

    # The limit is 3 total, split across both "instances" — not 3 each.
    assert not on_instance_b.check(session, "1.2.3.4", now=NOW)


def test_different_keys_do_not_share_a_window(session: Session) -> None:
    subject = limiter(limit=1)
    assert subject.check(session, "1.2.3.4", now=NOW)
    assert subject.check(session, "5.6.7.8", now=NOW)


def test_different_buckets_do_not_share_a_window(session: Session) -> None:
    assert limiter(name="signup", limit=1).check(session, "1.2.3.4", now=NOW)
    assert limiter(name="feedback", limit=1).check(session, "1.2.3.4", now=NOW)


def test_a_new_window_lifts_the_limit(session: Session) -> None:
    subject = limiter(limit=1, window_seconds=60)
    assert subject.check(session, "1.2.3.4", now=NOW)
    assert not subject.check(session, "1.2.3.4", now=NOW)

    later = NOW + timedelta(seconds=61)
    assert subject.check(session, "1.2.3.4", now=later)


def test_reset_clears_only_this_buckets_rows(session: Session) -> None:
    a = limiter(name="a", limit=1)
    b = limiter(name="b", limit=1)
    assert a.check(session, "1.2.3.4", now=NOW)
    assert b.check(session, "1.2.3.4", now=NOW)

    a.reset(session)

    assert a.check(session, "1.2.3.4", now=NOW)  # a's window is clear again
    assert not b.check(session, "1.2.3.4", now=NOW)  # b's is untouched


def test_enforce_raises_past_the_limit(session: Session) -> None:
    subject = limiter(limit=1)
    subject.enforce(session, "1.2.3.4")
    with pytest.raises(HTTPException) as excinfo:
        subject.enforce(session, "1.2.3.4")
    assert excinfo.value.status_code == 429
