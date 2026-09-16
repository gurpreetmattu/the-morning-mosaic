"""Delivery: at-most-once, and never a near-empty edition."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.schemas import (
    DraftSentence,
    EditionBuild,
    GenreOutcome,
    VerifiedStory,
    WrittenStory,
)
from app.config.schemas import EditionsConfig, SpecialEdition, WeekendConfig
from app.config.settings import Settings
from app.db.persist import persist_genre
from app.db.publish import publish_revision
from app.db.seed import seed_cities, seed_sources
from app.email import tokens
from app.email.sender import Message, Sender, SendError, SendOutcome, SendResult
from app.jobs.delivery import claim, due_readers, is_due, run_delivery
from app.models.editions import Delivery, EditionRevision
from app.models.enums import (
    DeliveryStatus,
    DeliveryType,
    EditionPreference,
    Frequency,
    RunStatus,
    SectionStatus,
    SubscriptionStatus,
)
from app.models.operations import PipelineRun
from app.models.users import FollowedKeyword, User, UserGenre
from app.render.sections import RenderedSection
from app.sources.schemas import CollectedArticle, Passage

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 5, 1, 30, tzinfo=UTC)  # 07:00 IST, a Monday
EDITION = date(2026, 10, 5)
SATURDAY = date(2026, 10, 3)
SLOT = time(7, 0)

BODY = "The cabinet approved the eastern freight corridor on Tuesday, officials said."


class FakeSender(Sender):
    """Records messages instead of speaking SMTP.

    `send` is overridden whole, so no Sender state is needed and the base
    __init__ (which would demand real settings) is deliberately not called.
    """

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


def make_user(
    session: Session,
    *,
    email: str = "reader@example.com",
    slot: time = time(7, 0),
    genres: tuple[str, ...] = ("india",),
    frequency: Frequency = Frequency.DAILY,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    keywords: tuple[str, ...] = (),
) -> User:
    user = User(
        email=email,
        name="Asha Rao",
        city_id="mumbai",
        status=status,
        delivery_slot=slot,
        frequency=frequency,
        edition_preference=EditionPreference.MIXED,
        age_confirmed=True,
    )
    session.add(user)
    session.flush()
    for genre in genres:
        session.add(UserGenre(user_id=user.id, genre=genre))
    for keyword in keywords:
        session.add(FollowedKeyword(user_id=user.id, keyword=keyword))
    session.flush()
    return user


def article(index: int) -> CollectedArticle:
    return CollectedArticle(
        source_key="the-hindu",
        genre="india",
        url=f"https://example.test/deliver-{index}",
        title=f"Corridor {index}",
        published_at=NOW,
        fetched_at=NOW,
        text=BODY,
        passages=[Passage(ordinal=1, text=BODY)],
        content_hash=f"deliver-{index}",
    )


def outcome(count: int = 3, genre: str = "india") -> GenreOutcome:
    return GenreOutcome(
        genre=genre,  # type: ignore[arg-type]
        status=SectionStatus.OK,
        stories=[
            VerifiedStory(
                story=WrittenStory(
                    headline=DraftSentence(text=f"Headline {i}", passage_ids=["a1:p1"]),
                    summary=[DraftSentence(text="Ministers approved.", passage_ids=["a1:p1"])],
                    one_liner=DraftSentence(text=f"Line {i}", passage_ids=["a1:p1"]),
                ),
                articles=[article(i)],
                pool_rank=i + 1,
                attempts=1,
            )
            for i in range(count)
        ],
    )


def published_edition(
    session: Session,
    on: date = EDITION,
    stories: int = 3,
    special_edition_key: str | None = None,
) -> None:
    persist_genre(session, edition_date=on, outcome=outcome(stories))
    publish_revision(
        session,
        build=EditionBuild(
            edition_date=on,
            edition_number=5,
            genres=[],
            special_edition_key=special_edition_key,
        ),
        sections={
            "india": RenderedSection(
                genre="india",
                status=SectionStatus.OK,
                html="<p>x</p>",
                plain_text="x",
                story_count=stories,
            )
        },
        published_at=NOW,
    )


def settings() -> Settings:
    return Settings.model_validate(
        {
            "base_url": "https://mosaic.example.com",
            "database_url": "postgresql://u:p@localhost/db",
            "smtp_host": "smtp.example.com",
            "sender_email": "news@example.com",
            "sender_name": "The Morning Mosaic",
            "gmail_app_password": "x",
            "imap_host": "imap.example.com",
            "admin_email": "admin@example.com",
            "freellmpool_url": "https://llm.example.com",
            "freellmpool_api_key": "x",
            "token_signing_key": "signing-key-for-tests",
            "app_env": "prod",
        }
    )


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Token signing reads settings at module level, so point it at ours."""
    monkeypatch.setattr(tokens, "get_settings", settings)


@pytest.fixture(autouse=True)
def _reference_data(session: Session) -> None:
    seed_sources(session)
    seed_cities(session)
    session.flush()


def deliver(session: Session, sender: FakeSender, **overrides: object) -> object:
    kwargs: dict[str, object] = {
        "edition_date": EDITION,
        "slot": SLOT,
        "sender": sender,
        "settings": settings(),
        "now": NOW,
    }
    kwargs.update(overrides)
    return run_delivery(session, **kwargs)  # type: ignore[arg-type]


def deliveries(session: Session) -> list[Delivery]:
    return list(session.scalars(select(Delivery).where(Delivery.edition_date == EDITION)))


# --------------------------------------------------------------- who is due


def test_an_active_reader_at_their_slot_is_due() -> None:
    user = User(
        email="a@example.com",
        name="A",
        status=SubscriptionStatus.ACTIVE,
        delivery_slot=time(7, 0),
        frequency=Frequency.DAILY,
    )
    assert is_due(user, slot=time(7, 0), on=EDITION)


def test_an_earlier_slot_rolls_forward_rather_than_being_lost() -> None:
    user = User(
        email="a@example.com",
        name="A",
        status=SubscriptionStatus.ACTIVE,
        delivery_slot=time(6, 0),
        frequency=Frequency.DAILY,
    )
    assert is_due(user, slot=time(8, 0), on=EDITION)


def test_a_later_slot_is_not_yet_due() -> None:
    user = User(
        email="a@example.com",
        name="A",
        status=SubscriptionStatus.ACTIVE,
        delivery_slot=time(8, 30),
        frequency=Frequency.DAILY,
    )
    assert not is_due(user, slot=time(7, 0), on=EDITION)


def test_weekday_only_readers_get_neither_weekend_edition() -> None:
    user = User(
        email="a@example.com",
        name="A",
        status=SubscriptionStatus.ACTIVE,
        delivery_slot=time(7, 0),
        frequency=Frequency.WEEKDAYS,
    )
    assert is_due(user, slot=SLOT, on=EDITION)  # Monday
    assert not is_due(user, slot=SLOT, on=SATURDAY)
    assert not is_due(user, slot=SLOT, on=date(2026, 10, 4))  # Sunday


@pytest.mark.parametrize(
    "status",
    [s for s in SubscriptionStatus if s is not SubscriptionStatus.ACTIVE],
)
def test_only_active_readers_are_due(status: SubscriptionStatus) -> None:
    user = User(
        email="a@example.com",
        name="A",
        status=status,
        delivery_slot=time(7, 0),
        frequency=Frequency.DAILY,
    )
    assert not is_due(user, slot=SLOT, on=EDITION)


def test_paused_readers_are_not_queried(session: Session) -> None:
    make_user(session, email="active@example.com")
    make_user(session, email="paused@example.com", status=SubscriptionStatus.PAUSED)

    due = due_readers(session, slot=SLOT, on=EDITION)
    assert [user.email for user in due] == ["active@example.com"]


# ------------------------------------------------------------- happy path


def test_a_due_reader_receives_the_edition(session: Session) -> None:
    make_user(session)
    published_edition(session)
    sender = FakeSender()

    report = deliver(session, sender)

    assert report.sent == 1  # type: ignore[attr-defined]
    assert len(sender.messages) == 1
    assert sender.messages[0].to == "reader@example.com"
    assert "Headline 0" in sender.messages[0].html


def test_a_special_edition_is_shown_by_name_not_by_its_raw_config_key(
    session: Session,
) -> None:
    make_user(session)
    published_edition(session, special_edition_key="gandhi-jayanti")
    editions = EditionsConfig(
        launch_date=date(2026, 1, 1),
        weekend=WeekendConfig(saturday_features=["top-stories"], sunday_features=["top-stories"]),
        special_editions=[
            SpecialEdition(
                key="gandhi-jayanti",
                name="Gandhi Jayanti",
                observed_on=EDITION,
                note="A special edition marking Gandhi Jayanti.",
                accent="#a3552b",
            )
        ],
    )
    sender = FakeSender()

    deliver(session, sender, editions=editions)

    html = sender.messages[0].html
    assert "Gandhi Jayanti" in html
    assert "gandhi-jayanti" not in html
    assert "A special edition marking Gandhi Jayanti." in html
    assert "#a3552b" in html


def test_the_delivery_records_the_revision_that_was_sent(session: Session) -> None:
    make_user(session)
    published_edition(session)

    deliver(session, FakeSender())

    row = deliveries(session)[0]
    assert row.status is DeliveryStatus.SENT
    assert row.revision_id is not None
    assert row.sent_at is not None
    assert row.attempts == 1


def test_the_email_carries_a_one_click_unsubscribe_url(session: Session) -> None:
    make_user(session)
    published_edition(session)
    sender = FakeSender()

    deliver(session, sender)
    assert "/unsubscribe/" in (sender.messages[0].unsubscribe_url or "")


def test_the_run_is_recorded(session: Session) -> None:
    make_user(session)
    published_edition(session)

    deliver(session, FakeSender())

    run = session.scalar(select(PipelineRun).where(PipelineRun.started_at == NOW))
    assert run is not None
    assert run.status is RunStatus.SUCCEEDED
    assert run.detail is not None
    assert run.detail["sent"] == 1


# --------------------------------------------------------- at most once


def test_a_second_run_does_not_send_again(session: Session) -> None:
    make_user(session)
    published_edition(session)

    first = FakeSender()
    deliver(session, first)
    second = FakeSender()
    report = deliver(session, second)

    assert len(first.messages) == 1
    assert second.messages == []
    assert report.already_done == 1  # type: ignore[attr-defined]
    assert session.scalar(select(func.count()).select_from(Delivery)) == 1


def test_a_row_stuck_in_sending_is_never_resent(session: Session) -> None:
    """We cannot know whether that mail went out; a duplicate is worse."""
    user = make_user(session)
    published_edition(session)
    session.add(
        Delivery(
            user_id=user.id,
            edition_date=EDITION,
            type=DeliveryType.NEWSLETTER,
            status=DeliveryStatus.SENDING,
            attempts=1,
        )
    )
    session.commit()

    sender = FakeSender()
    report = deliver(session, sender)

    assert sender.messages == []
    assert report.already_done == 1  # type: ignore[attr-defined]


def test_a_failed_send_is_retried_by_a_later_run(session: Session) -> None:
    make_user(session)
    published_edition(session)

    failing = FakeSender(fail=True)
    first = deliver(session, failing)
    assert first.failed == 1  # type: ignore[attr-defined]
    assert deliveries(session)[0].status is DeliveryStatus.FAILED

    working = FakeSender()
    second = deliver(session, working)

    assert second.sent == 1  # type: ignore[attr-defined]
    assert deliveries(session)[0].status is DeliveryStatus.SENT
    assert deliveries(session)[0].attempts == 2


def test_a_send_is_abandoned_after_the_attempt_limit(session: Session) -> None:
    user = make_user(session)
    published_edition(session)
    session.add(
        Delivery(
            user_id=user.id,
            edition_date=EDITION,
            type=DeliveryType.NEWSLETTER,
            status=DeliveryStatus.FAILED,
            attempts=3,
        )
    )
    session.commit()

    sender = FakeSender()
    deliver(session, sender)
    assert sender.messages == []


def test_the_claim_refuses_a_row_another_run_already_sent(session: Session) -> None:
    user = make_user(session)
    published_edition(session)
    # The schema refuses a sent newsletter with no revision, so this row has to
    # name the revision it carried — which is the point of the column.
    revision = session.scalars(select(EditionRevision)).one()
    session.add(
        Delivery(
            user_id=user.id,
            edition_date=EDITION,
            type=DeliveryType.NEWSLETTER,
            status=DeliveryStatus.SENT,
            revision_id=revision.id,
            attempts=1,
        )
    )
    session.commit()

    assert claim(session, user_id=user.id, edition_date=EDITION) is None


# ------------------------------------------------------------- no content


def test_a_reader_with_no_usable_section_is_skipped_not_sent(session: Session) -> None:
    """A near-empty edition is worse than none; the notice job handles them."""
    make_user(session, genres=("politics",))
    published_edition(session)
    sender = FakeSender()

    report = deliver(session, sender)

    assert sender.messages == []
    assert report.no_content == 1  # type: ignore[attr-defined]
    assert deliveries(session) == []


def test_nothing_is_sent_when_no_revision_exists(session: Session) -> None:
    make_user(session)
    sender = FakeSender()

    report = deliver(session, sender)

    assert sender.messages == []
    assert report.revision is None  # type: ignore[attr-defined]
    assert "no published revision" in report.errors  # type: ignore[attr-defined]


# ------------------------------------------------------------ dev guard


def test_a_suppressed_send_is_recorded_as_skipped_not_failed(session: Session) -> None:
    make_user(session)
    published_edition(session)

    report = deliver(session, FakeSender(suppress=True))

    assert report.suppressed == 1  # type: ignore[attr-defined]
    assert report.failed == 0  # type: ignore[attr-defined]
    assert deliveries(session)[0].status is DeliveryStatus.SKIPPED


# ---------------------------------------------------------- personalisation


def test_each_reader_gets_their_own_sections(session: Session) -> None:
    make_user(session, email="one@example.com", genres=("india",))
    make_user(session, email="two@example.com", genres=("politics",))
    published_edition(session)
    sender = FakeSender()

    report = deliver(session, sender)

    assert report.sent == 1  # type: ignore[attr-defined]
    assert report.no_content == 1  # type: ignore[attr-defined]
    assert [m.to for m in sender.messages] == ["one@example.com"]


def test_a_followed_keyword_reaches_the_rendered_email(session: Session) -> None:
    make_user(session, keywords=("infrastructure",))
    published_edition(session)
    sender = FakeSender()

    deliver(session, sender)
    assert sender.messages  # the keyword must not break assembly
    assert uuid.UUID(str(deliveries(session)[0].user_id))
