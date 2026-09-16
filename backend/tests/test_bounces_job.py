"""Bounce processing: permanent failures only, and never touch the mailbox."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, time
from email import message_from_string
from email.message import Message
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.db.seed import seed_cities
from app.email.bounces import BOUNCE_SEARCH, ImapBounceSource, parse_bounce
from app.jobs.bounces import run_bounces
from app.models.enums import EditionPreference, Frequency, RunStatus, SubscriptionStatus
from app.models.users import User

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)
SINCE = date(2026, 10, 2)


def load(name: str) -> Message:
    return message_from_string((FIXTURES / name).read_text(encoding="utf-8"))


class FakeSource:
    def __init__(self, *names: str, raises: bool = False) -> None:
        self.names = names
        self.raises = raises
        self.since: date | None = None

    def fetch(self, *, since: date) -> Iterator[Message]:
        self.since = since
        if self.raises:
            raise OSError("connection refused")
        yield from (load(name) for name in self.names)


# ------------------------------------------------------------- the parser


def test_a_permanent_failure_is_recognised() -> None:
    bounce = parse_bounce(load("bounce_hard.eml"))

    assert bounce is not None
    assert bounce.address == "gone@example.com"
    assert bounce.permanent is True
    assert bounce.status == "5.1.1"


def test_a_full_mailbox_is_not_permanent() -> None:
    """Unsubscribing over a transient problem loses a reader for good."""
    bounce = parse_bounce(load("bounce_soft.eml"))

    assert bounce is not None
    assert bounce.address == "busy@example.com"
    assert bounce.permanent is False


def test_ordinary_mail_is_not_a_bounce() -> None:
    assert parse_bounce(load("ordinary_mail.eml")) is None


def test_a_delayed_report_is_not_a_verdict() -> None:
    raw = (FIXTURES / "bounce_hard.eml").read_text(encoding="utf-8")
    delayed = raw.replace("Action: failed", "Action: delayed")
    assert parse_bounce(message_from_string(delayed)) is None


def test_the_address_is_normalised() -> None:
    raw = (FIXTURES / "bounce_hard.eml").read_text(encoding="utf-8")
    messy = raw.replace(
        "Final-Recipient: rfc822; gone@example.com",
        "Final-Recipient: rfc822; <Gone@Example.COM>  ",
    )
    bounce = parse_bounce(message_from_string(messy))

    assert bounce is not None
    assert bounce.address == "gone@example.com"


def test_a_header_only_report_is_read_conservatively() -> None:
    """No structured report: permanent only if the body says 5.x.x."""
    raw = (
        "From: Mail Delivery System <mailer-daemon@example.net>\n"
        "X-Failed-Recipients: gone@example.com\n"
        "Content-Type: text/plain\n\n"
        "This is the mail system. Status: 5.1.1 user unknown\n"
    )
    bounce = parse_bounce(message_from_string(raw))
    assert bounce is not None
    assert bounce.permanent is True

    vague = raw.replace("Status: 5.1.1 user unknown", "could not be delivered")
    unclear = parse_bounce(message_from_string(vague))
    assert unclear is not None
    assert unclear.permanent is False


# ---------------------------------------------------------- mailbox safety


def test_the_search_is_narrowed_to_delivery_failures() -> None:
    """Ordinary mail is never fetched, so it is never parsed."""
    assert "mailer-daemon" in BOUNCE_SEARCH
    assert "FROM" in BOUNCE_SEARCH


def test_the_imap_source_opens_the_mailbox_read_only() -> None:
    """Read-only makes deleting and flagging impossible at the protocol level."""
    import inspect

    source = inspect.getsource(ImapBounceSource.fetch)
    assert "readonly=True" in source
    # Nothing in this class may mutate the mailbox.
    for forbidden in ("store(", "expunge(", "copy(", "append("):
        assert forbidden not in source


# ----------------------------------------------------------------- the job


@pytest.mark.integration
class TestJob:
    @pytest.fixture(autouse=True)
    def _cities(self, session: Session) -> None:
        seed_cities(session)
        session.flush()

    def make_user(
        self,
        session: Session,
        email: str,
        status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    ) -> User:
        user = User(
            email=email,
            name="Asha Rao",
            city_id="mumbai",
            status=status,
            delivery_slot=time(7, 0),
            frequency=Frequency.DAILY,
            edition_preference=EditionPreference.MIXED,
            age_confirmed=True,
        )
        session.add(user)
        session.flush()
        return user

    def test_a_hard_bounce_marks_the_reader(self, session: Session) -> None:
        user = self.make_user(session, "gone@example.com")

        report = run_bounces(session, source=FakeSource("bounce_hard.eml"), since=SINCE, now=NOW)

        assert report.marked == 1
        assert report.permanent == 1
        assert user.status is SubscriptionStatus.BOUNCED
        assert user.status_changed_at is not None

    def test_a_soft_bounce_leaves_the_reader_active(self, session: Session) -> None:
        user = self.make_user(session, "busy@example.com")

        report = run_bounces(session, source=FakeSource("bounce_soft.eml"), since=SINCE, now=NOW)

        assert report.transient == 1
        assert report.marked == 0
        assert user.status is SubscriptionStatus.ACTIVE

    def test_ordinary_mail_changes_nothing(self, session: Session) -> None:
        user = self.make_user(session, "reader@example.com")

        report = run_bounces(session, source=FakeSource("ordinary_mail.eml"), since=SINCE, now=NOW)

        assert report.examined == 0
        assert user.status is SubscriptionStatus.ACTIVE

    def test_a_bounce_for_an_unknown_address_is_counted_not_applied(self, session: Session) -> None:
        report = run_bounces(session, source=FakeSource("bounce_hard.eml"), since=SINCE, now=NOW)

        assert report.unknown_addresses == 1
        assert report.marked == 0

    def test_reprocessing_the_same_bounce_is_a_no_op(self, session: Session) -> None:
        self.make_user(session, "gone@example.com")

        first = run_bounces(session, source=FakeSource("bounce_hard.eml"), since=SINCE, now=NOW)
        second = run_bounces(session, source=FakeSource("bounce_hard.eml"), since=SINCE, now=NOW)

        assert first.marked == 1
        assert second.marked == 0

    def test_a_mix_is_handled_independently(self, session: Session) -> None:
        gone = self.make_user(session, "gone@example.com")
        busy = self.make_user(session, "busy@example.com")

        report = run_bounces(
            session,
            source=FakeSource("bounce_hard.eml", "bounce_soft.eml", "ordinary_mail.eml"),
            since=SINCE,
            now=NOW,
        )

        assert (report.permanent, report.transient, report.marked) == (1, 1, 1)
        assert gone.status is SubscriptionStatus.BOUNCED
        assert busy.status is SubscriptionStatus.ACTIVE

    def test_the_lookback_window_is_passed_through(self, session: Session) -> None:
        source = FakeSource()
        run_bounces(session, source=source, since=SINCE, now=NOW)
        assert source.since == SINCE

    def test_an_unreachable_mailbox_fails_the_run_without_touching_readers(
        self, session: Session
    ) -> None:
        user = self.make_user(session, "gone@example.com")

        report = run_bounces(session, source=FakeSource(raises=True), since=SINCE, now=NOW)

        assert report.errors
        assert report.marked == 0
        assert user.status is SubscriptionStatus.ACTIVE

    def test_the_run_is_recorded(self, session: Session) -> None:
        from sqlalchemy import select

        from app.models.operations import PipelineRun

        self.make_user(session, "gone@example.com")
        run_bounces(session, source=FakeSource("bounce_hard.eml"), since=SINCE, now=NOW)

        run = session.scalar(select(PipelineRun).where(PipelineRun.started_at == NOW))
        assert run is not None
        assert run.status is RunStatus.SUCCEEDED
        assert run.detail is not None
        assert run.detail["marked"] == 1
