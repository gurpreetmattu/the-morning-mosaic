"""Failure notices: never guess, never spam, never apologise late."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.seed import seed_cities
from app.email import tokens
from app.email.sender import Message, Sender, SendError, SendOutcome, SendResult
from app.jobs.failure_notice import (
    NoticeReport,
    batch_expiry,
    eligible_readers,
    needs_notice,
    run_failure_notices,
)
from app.models.editions import Delivery, Edition, EditionRevision
from app.models.enums import (
    DeliveryStatus,
    DeliveryType,
    EditionPreference,
    Frequency,
    NoticeBatchStatus,
    RevisionReason,
    RunStatus,
    SubscriptionStatus,
)
from app.models.operations import NoticeBatch, PipelineRun
from app.models.users import OutageState, User

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 5, 3, 35, tzinfo=UTC)  # 09:05 IST, a Monday
EDITION = date(2026, 10, 5)
SATURDAY = date(2026, 10, 3)


class FakeSender(Sender):
    """Records notices instead of speaking SMTP."""

    def __init__(self, *, fail: bool = False, suppress: bool = False) -> None:
        self.messages: list[Message] = []
        self.fail = fail
        self.suppress = suppress

    def send(self, message: Message) -> SendResult:
        if self.fail:
            raise SendError("SMTPServerDisconnected: connection lost")
        self.messages.append(message)
        if self.suppress:
            return SendResult(
                to=message.to, outcome=SendOutcome.SUPPRESSED, reason="not allowlisted"
            )
        return SendResult(to=message.to, outcome=SendOutcome.SENT, message_id="<id>")


def settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "base_url": "https://mosaic.example.com",
        "database_url": "postgresql://u:p@localhost/db",
        "smtp_host": "smtp.example.com",
        "sender_email": "news@example.com",
        "sender_name": "The Morning Mosaic",
        "gmail_app_password": "x",
        "imap_host": "imap.example.com",
        "admin_email": "admin@example.com",
        "llm_gateway_url": "https://llm.example.com",
        "llm_gateway_api_key": "x",
        "token_signing_key": "signing-key-for-tests",
        "app_env": "prod",
        "failure_notice_auto_limit": 50,
    }
    return Settings.model_validate(base | overrides)


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tokens, "get_settings", settings)


@pytest.fixture(autouse=True)
def _cities(session: Session) -> None:
    seed_cities(session)
    session.flush()


def make_user(
    session: Session,
    *,
    email: str = "reader@example.com",
    frequency: Frequency = Frequency.DAILY,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> User:
    user = User(
        email=email,
        name="Asha Rao",
        city_id="mumbai",
        status=status,
        delivery_slot=time(7, 0),
        frequency=frequency,
        edition_preference=EditionPreference.MIXED,
        age_confirmed=True,
    )
    session.add(user)
    session.flush()
    return user


def a_revision(session: Session) -> EditionRevision:
    """The schema refuses a sent newsletter that names no revision."""
    edition = Edition(edition_date=EDITION, edition_number=5)
    session.add(edition)
    session.flush()
    revision = EditionRevision(
        edition_id=edition.id, revision=1, reason=RevisionReason.BUILD, published_at=NOW
    )
    session.add(revision)
    session.flush()
    return revision


def add_delivery(session: Session, user: User, status: DeliveryStatus) -> Delivery:
    revision = a_revision(session) if status is DeliveryStatus.SENT else None
    row = Delivery(
        user_id=user.id,
        edition_date=EDITION,
        type=DeliveryType.NEWSLETTER,
        status=status,
        revision_id=revision.id if revision else None,
        attempts=1,
    )
    session.add(row)
    session.flush()
    return row


def notify(session: Session, sender: FakeSender, **overrides: object) -> NoticeReport:
    kwargs: dict[str, object] = {
        "edition_date": EDITION,
        "sender": sender,
        "settings": settings(),
        "now": NOW,
    }
    kwargs.update(overrides)
    return run_failure_notices(session, **kwargs)  # type: ignore[arg-type]


def notices(session: Session) -> list[Delivery]:
    return list(
        session.scalars(select(Delivery).where(Delivery.type == DeliveryType.FAILURE_NOTICE))
    )


# ------------------------------------------------------------ who qualifies


def test_a_reader_with_no_delivery_row_qualifies(session: Session) -> None:
    user = make_user(session)
    assert needs_notice(session, user, edition_date=EDITION)


def test_a_failed_delivery_qualifies(session: Session) -> None:
    user = make_user(session)
    add_delivery(session, user, DeliveryStatus.FAILED)
    assert needs_notice(session, user, edition_date=EDITION)


def test_a_reader_stuck_in_sending_is_excluded(session: Session) -> None:
    """They may well have received it; apologising would be worse."""
    user = make_user(session)
    add_delivery(session, user, DeliveryStatus.SENDING)
    assert not needs_notice(session, user, edition_date=EDITION)


def test_a_delivered_reader_is_excluded(session: Session) -> None:
    user = make_user(session)
    add_delivery(session, user, DeliveryStatus.SKIPPED)
    assert not needs_notice(session, user, edition_date=EDITION)


def test_weekday_only_readers_are_not_notified_at_the_weekend(session: Session) -> None:
    make_user(session, frequency=Frequency.WEEKDAYS)
    assert eligible_readers(session, edition_date=SATURDAY) == []
    assert len(eligible_readers(session, edition_date=EDITION)) == 1


def test_inactive_readers_are_not_notified(session: Session) -> None:
    make_user(session, status=SubscriptionStatus.PAUSED)
    assert eligible_readers(session, edition_date=EDITION) == []


# --------------------------------------------------------------- happy path


def test_an_affected_reader_gets_a_generic_apology(session: Session) -> None:
    make_user(session)
    sender = FakeSender()

    report = notify(session, sender)

    assert report.sent == 1
    message = sender.messages[0]
    assert "didn't make it out" in message.text
    assert "nothing you need to do" in message.text
    # Generic: no technical detail reaches the reader.
    for leak in ("exception", "traceback", "SMTP", "genre", "revision"):
        assert leak.lower() not in message.text.lower()


def test_the_notice_carries_an_unsubscribe_header(session: Session) -> None:
    make_user(session)
    sender = FakeSender()
    notify(session, sender)

    assert "/unsubscribe/" in (sender.messages[0].unsubscribe_url or "")


def test_at_most_one_notice_per_reader_per_day(session: Session) -> None:
    make_user(session)

    first = FakeSender()
    notify(session, first)
    second = FakeSender()
    notify(session, second)

    assert len(first.messages) == 1
    assert second.messages == []
    assert len(notices(session)) == 1


def test_the_run_is_recorded(session: Session) -> None:
    make_user(session)
    notify(session, FakeSender())

    run = session.scalar(select(PipelineRun).where(PipelineRun.started_at == NOW))
    assert run is not None
    assert run.status is RunStatus.SUCCEEDED
    assert run.detail is not None
    assert run.detail["sent"] == 1


# ------------------------------------------------------------ batch safety


def test_an_abnormally_large_batch_is_held_not_sent(session: Session) -> None:
    for index in range(4):
        make_user(session, email=f"reader{index}@example.com")
    sender = FakeSender()

    report = notify(session, sender, settings=settings(failure_notice_auto_limit=2))

    assert sender.messages == []
    assert report.status is NoticeBatchStatus.HELD
    assert "held for approval" in (report.reason or "")


def test_a_held_batch_expires_unsent_at_noon(session: Session) -> None:
    """A late apology is worse than none."""
    make_user(session)
    session.add(
        NoticeBatch(
            edition_date=EDITION,
            status=NoticeBatchStatus.HELD,
            recipient_count=1,
            expires_at=batch_expiry(EDITION),
        )
    )
    session.commit()

    sender = FakeSender()
    report = notify(session, sender, now=batch_expiry(EDITION) + timedelta(minutes=1))

    assert sender.messages == []
    assert report.status is NoticeBatchStatus.EXPIRED


def test_an_approved_batch_sends(session: Session) -> None:
    make_user(session)
    session.add(
        NoticeBatch(
            edition_date=EDITION,
            status=NoticeBatchStatus.APPROVED,
            recipient_count=1,
            expires_at=batch_expiry(EDITION),
        )
    )
    session.commit()

    sender = FakeSender()
    assert notify(session, sender).sent == 1


def test_a_suppressed_batch_sends_nothing(session: Session) -> None:
    make_user(session)
    session.add(
        NoticeBatch(
            edition_date=EDITION,
            status=NoticeBatchStatus.SUPPRESSED,
            recipient_count=1,
            expires_at=batch_expiry(EDITION),
        )
    )
    session.commit()

    sender = FakeSender()
    report = notify(session, sender)

    assert sender.messages == []
    assert "suppressed" in (report.reason or "")


def test_the_expiry_is_noon_ist() -> None:
    assert batch_expiry(EDITION) == datetime(2026, 10, 5, 6, 30, tzinfo=UTC)


# -------------------------------------------------------- prolonged outage


def test_the_third_consecutive_day_sends_a_paused_message_instead(
    session: Session,
) -> None:
    user = make_user(session)
    session.add(
        OutageState(
            user_id=user.id,
            consecutive_failed_days=2,
            last_failed_on=EDITION - timedelta(days=1),
        )
    )
    session.commit()

    sender = FakeSender()
    report = notify(session, sender)

    assert report.paused_sent == 1
    assert report.sent == 0
    assert "pausing these notices" in sender.messages[0].subject
    # Whitespace-normalised: the plain-text template wraps at 78 columns.
    flowed = " ".join(sender.messages[0].text.split())
    assert "subscription is unchanged" in flowed


def test_after_the_paused_message_nothing_further_is_sent(session: Session) -> None:
    user = make_user(session)
    session.add(
        OutageState(
            user_id=user.id,
            consecutive_failed_days=5,
            last_failed_on=EDITION - timedelta(days=1),
            paused_notice_sent_on=EDITION - timedelta(days=2),
        )
    )
    session.commit()

    sender = FakeSender()
    report = notify(session, sender)

    assert sender.messages == []
    assert report.sent == 0
    # No row is left implying a send.
    assert notices(session) == []


def test_the_failure_count_does_not_inflate_on_a_rerun(session: Session) -> None:
    user = make_user(session)
    notify(session, FakeSender())
    notify(session, FakeSender())

    state = session.get(OutageState, user.id)
    assert state is not None
    assert state.consecutive_failed_days == 1


# ------------------------------------------------------------ mail is down


def test_repeated_send_failures_abort_the_batch(session: Session) -> None:
    """Sending is broken, not this batch; hammering it helps nobody."""
    for index in range(6):
        make_user(session, email=f"reader{index}@example.com")

    report = notify(session, FakeSender(fail=True))

    assert report.failed == 3
    assert "unavailable" in (report.reason or "")

    run = session.scalar(select(PipelineRun).where(PipelineRun.started_at == NOW))
    assert run is not None
    assert run.status is RunStatus.FAILED


def test_dev_suppression_is_recorded_as_skipped(session: Session) -> None:
    make_user(session)
    report = notify(session, FakeSender(suppress=True))

    assert report.suppressed == 1
    assert report.failed == 0
    assert notices(session)[0].status is DeliveryStatus.SKIPPED


def test_nobody_affected_means_nothing_sent(session: Session) -> None:
    user = make_user(session)
    add_delivery(session, user, DeliveryStatus.SENT)
    session.commit()

    sender = FakeSender()
    report = notify(session, sender)

    assert report.eligible == 0
    assert sender.messages == []
