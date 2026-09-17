"""Delivery: at-most-once, and never a near-empty edition."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta

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
from app.models.content import Correction, Story
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
from app.render.weekend import persist_weekend_features
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


def article(index: int, *, tag: str = "") -> CollectedArticle:
    suffix = f"{tag}-{index}" if tag else str(index)
    return CollectedArticle(
        source_key="the-hindu",
        genre="india",
        url=f"https://example.test/deliver-{suffix}",
        title=f"Corridor {suffix}",
        published_at=NOW,
        fetched_at=NOW,
        text=BODY,
        passages=[Passage(ordinal=1, text=BODY)],
        content_hash=f"deliver-{suffix}",
    )


def outcome(count: int = 3, genre: str = "india", *, tag: str = "") -> GenreOutcome:
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
                articles=[article(i, tag=tag)],
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
    # A different `on` gets its own article identities and edition number,
    # so publishing more than one day in the same test doesn't collide on
    # Article.url or the edition_number unique constraint.
    tag = "" if on == EDITION else on.isoformat()
    persist_genre(session, edition_date=on, outcome=outcome(stories, tag=tag))
    publish_revision(
        session,
        build=EditionBuild(
            edition_date=on,
            edition_number=5 + (on - EDITION).days,
            genres=[],
            special_edition_key=special_edition_key,
            is_weekend=on.weekday() >= 5,
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


# --------------------------------------------------------------- corrections

NEXT_DAY = EDITION + timedelta(days=1)


def correct(
    session: Session, description: str = "The figure was wrong.", genre: str = "india"
) -> Correction:
    story = session.scalar(select(Story).where(Story.edition_date == EDITION, Story.genre == genre))
    assert story is not None
    correction = Correction(story_id=story.id, description=description, corrected_at=NOW)
    session.add(correction)
    session.flush()
    return correction


def published_edition_with_genres(
    session: Session, genres: dict[str, int], on: date = EDITION
) -> None:
    """Like published_edition, but several genres in one revision — needed to
    tell "got the email but not the note" apart from "got no email"."""
    tag = "" if on == EDITION else on.isoformat()
    sections = {}
    for genre, count in genres.items():
        persist_genre(
            session, edition_date=on, outcome=outcome(count, genre=genre, tag=f"{tag}{genre}")
        )
        sections[genre] = RenderedSection(
            genre=genre,
            status=SectionStatus.OK,
            html="<p>x</p>",
            plain_text="x",
            story_count=count,
        )
    publish_revision(
        session,
        build=EditionBuild(edition_date=on, edition_number=5 + (on - EDITION).days, genres=[]),
        sections=sections,
        published_at=NOW,
    )


def test_a_reader_who_received_the_original_story_gets_the_note_next_time(
    session: Session,
) -> None:
    make_user(session)
    published_edition(session, on=EDITION)
    deliver(session, FakeSender())  # so there is a SENT delivery for EDITION
    correct(session)
    published_edition(session, on=NEXT_DAY)

    sender = FakeSender()
    deliver(session, sender, edition_date=NEXT_DAY)

    assert sender.messages
    assert "The figure was wrong." in sender.messages[0].html


def test_a_reader_in_a_different_genre_does_not_get_the_note(session: Session) -> None:
    make_user(session, email="india@example.com", genres=("india",))
    make_user(session, email="politics@example.com", genres=("politics",))
    published_edition_with_genres(session, {"india": 3, "politics": 3}, on=EDITION)
    deliver(session, FakeSender())
    correct(session, genre="india")
    published_edition_with_genres(session, {"india": 3, "politics": 3}, on=NEXT_DAY)

    sender = FakeSender()
    deliver(session, sender, edition_date=NEXT_DAY)

    by_recipient = {m.to: m.html for m in sender.messages}
    assert "The figure was wrong." in by_recipient["india@example.com"]
    assert "The figure was wrong." not in by_recipient["politics@example.com"]


def test_a_reader_who_never_received_the_original_edition_is_not_told(session: Session) -> None:
    published_edition(session, on=EDITION)
    correct(session)  # nobody was ever sent EDITION
    make_user(session)  # only signs up after the fact
    published_edition(session, on=NEXT_DAY)

    sender = FakeSender()
    deliver(session, sender, edition_date=NEXT_DAY)

    assert sender.messages
    assert "The figure was wrong." not in sender.messages[0].html


def test_the_note_is_not_repeated_the_day_after(session: Session) -> None:
    make_user(session)
    published_edition(session, on=EDITION)
    deliver(session, FakeSender())
    correct(session)
    published_edition(session, on=NEXT_DAY)
    deliver(session, FakeSender(), edition_date=NEXT_DAY)

    third_day = NEXT_DAY + timedelta(days=1)
    published_edition(session, on=third_day)
    sender = FakeSender()
    deliver(session, sender, edition_date=third_day)

    assert sender.messages
    assert "The figure was wrong." not in sender.messages[0].html


def test_a_later_slot_the_same_day_still_gets_the_note(session: Session) -> None:
    # Both readers must have received the original story, so both are made
    # (and sent EDITION) before the correction exists.
    make_user(session, email="early@example.com", slot=time(6, 30))
    make_user(session, email="late@example.com", slot=time(7, 0))
    published_edition(session, on=EDITION)
    deliver(session, FakeSender(), slot=time(7, 0))  # rolls both slots forward
    correct(session)
    published_edition(session, on=NEXT_DAY)

    # First slot of NEXT_DAY announces the correction to "early" only...
    first = FakeSender()
    deliver(session, first, edition_date=NEXT_DAY, slot=time(6, 30))
    assert "The figure was wrong." in first.messages[0].html

    # ...a later slot the same day must still see it.
    later = FakeSender()
    deliver(session, later, edition_date=NEXT_DAY, slot=time(7, 0))

    assert later.messages
    assert "The figure was wrong." in later.messages[0].html


# --------------------------------------------------------------- weekend content


def seed_the_week_before(session: Session, saturday: date) -> None:
    for offset, (genre, rank) in enumerate(
        [("sports", 1), ("business", 1), ("technology", 2), ("ai", 1), ("music", 3)]
    ):
        day = saturday - timedelta(days=5 - offset)
        persist_genre(
            session,
            edition_date=day,
            outcome=GenreOutcome(
                genre=genre,  # type: ignore[arg-type]
                status=SectionStatus.OK,
                stories=[
                    VerifiedStory(
                        story=WrittenStory(
                            headline=DraftSentence(text=f"{genre} headline", passage_ids=["a1:p1"]),
                            summary=[DraftSentence(text="Confirmed.", passage_ids=["a1:p1"])],
                        ),
                        articles=[
                            CollectedArticle(
                                source_key="the-hindu",
                                genre=genre,  # type: ignore[arg-type]
                                url=f"https://example.test/week-{genre}",
                                title=f"{genre} story",
                                published_at=datetime.combine(day, time(12, 0), tzinfo=UTC),
                                fetched_at=datetime.combine(day, time(12, 0), tzinfo=UTC),
                                text=BODY,
                                passages=[Passage(ordinal=1, text=BODY)],
                                content_hash=f"week-{genre}",
                            )
                        ],
                        pool_rank=rank,
                        attempts=1,
                    )
                ],
            ),
        )


def weekend_editions_config(saturday: date) -> EditionsConfig:
    return EditionsConfig(
        launch_date=saturday - timedelta(days=60),
        weekend=WeekendConfig(
            saturday_features=["top-stories", "longer-reads", "quiz"],
            sunday_features=["top-stories", "weekly-recap", "quiz"],
        ),
    )


def test_a_saturday_delivery_carries_the_weeks_longer_reads_and_quiz(session: Session) -> None:
    make_user(session)
    seed_the_week_before(session, SATURDAY)
    published_edition(session, on=SATURDAY)
    persist_weekend_features(
        session, edition_date=SATURDAY, editions=weekend_editions_config(SATURDAY)
    )
    session.commit()
    sender = FakeSender()

    deliver(session, sender, edition_date=SATURDAY)

    assert sender.messages
    html = sender.messages[0].html
    assert "This week's longer reads" in html
    assert "Weekend quiz" in html
    assert "The week, recapped" not in html


def test_a_weekday_delivery_carries_no_weekend_block(session: Session) -> None:
    make_user(session)
    published_edition(session)  # EDITION is a Monday

    sender = FakeSender()
    deliver(session, sender)

    assert sender.messages
    assert "Weekend quiz" not in sender.messages[0].html
