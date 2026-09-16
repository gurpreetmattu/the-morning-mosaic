"""Feedback aggregation: bounded, decaying, and counted exactly once."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.schemas import (
    DraftSentence,
    GenreOutcome,
    VerifiedStory,
    WrittenStory,
)
from app.db.persist import persist_genre
from app.db.seed import seed_cities, seed_sources
from app.jobs.feedback import (
    DECAY,
    PRUNE_BELOW,
    SCORE_CAP,
    clamp,
    run_feedback,
)
from app.models.content import Story
from app.models.editions import Feedback
from app.models.enums import (
    EditionPreference,
    Frequency,
    RunStatus,
    SectionStatus,
    SubscriptionStatus,
    Vote,
)
from app.models.operations import PipelineRun
from app.models.users import User, UserPreference
from app.sources.schemas import CollectedArticle, Passage

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)  # 04:00 IST on the 6th
EDITION = date(2026, 10, 5)
BODY = "The cabinet approved the eastern freight corridor on Tuesday, officials said."


@pytest.fixture(autouse=True)
def _reference_data(session: Session) -> None:
    seed_sources(session)
    seed_cities(session)
    session.flush()


def make_user(session: Session, email: str = "reader@example.com") -> User:
    user = User(
        email=email,
        name="Asha Rao",
        city_id="mumbai",
        status=SubscriptionStatus.ACTIVE,
        delivery_slot=time(7, 0),
        frequency=Frequency.DAILY,
        edition_preference=EditionPreference.MIXED,
        age_confirmed=True,
    )
    session.add(user)
    session.flush()
    return user


def make_story(session: Session, *topics: str, entities: tuple[str, ...] = ()) -> Story:
    article = CollectedArticle(
        source_key="the-hindu",
        genre="india",
        url=f"https://example.test/{'-'.join(topics) or 'story'}",
        title="Corridor",
        published_at=NOW,
        fetched_at=NOW,
        text=BODY,
        passages=[Passage(ordinal=1, text=BODY)],
        content_hash=f"hash-{'-'.join(topics)}",
    )
    persist_genre(
        session,
        edition_date=EDITION,
        outcome=GenreOutcome(
            genre="india",
            status=SectionStatus.OK,
            stories=[
                VerifiedStory(
                    story=WrittenStory(
                        headline=DraftSentence(text="Corridor cleared", passage_ids=["a1:p1"]),
                        summary=[DraftSentence(text="Ministers approved.", passage_ids=["a1:p1"])],
                        topic_tags=list(topics),
                        entity_tags=list(entities),
                    ),
                    articles=[article],
                    pool_rank=1,
                    attempts=1,
                )
            ],
        ),
    )
    story = session.scalars(select(Story)).first()
    assert story is not None
    return story


def vote(session: Session, user: User, story: Story, how: Vote) -> Feedback:
    row = Feedback(user_id=user.id, story_id=story.id, vote=how)
    session.add(row)
    session.flush()
    return row


def preferences(session: Session, user: User) -> dict[tuple[str, str], float]:
    return {
        (row.genre, row.topic_tag): row.score
        for row in session.scalars(select(UserPreference).where(UserPreference.user_id == user.id))
    }


# ------------------------------------------------------------------ units


def test_scores_are_clamped_in_both_directions() -> None:
    assert clamp(99.0) == SCORE_CAP
    assert clamp(-99.0) == -SCORE_CAP
    assert clamp(1.5) == 1.5


# ------------------------------------------------------------ aggregation


def test_a_thumbs_up_raises_the_topic(session: Session) -> None:
    user = make_user(session)
    story = make_story(session, "infrastructure")
    vote(session, user, story, Vote.UP)

    report = run_feedback(session, now=NOW)

    assert report.processed == 1
    assert preferences(session, user)[("india", "infrastructure")] == pytest.approx(1.0)


def test_a_thumbs_down_lowers_the_topic(session: Session) -> None:
    user = make_user(session)
    story = make_story(session, "infrastructure")
    vote(session, user, story, Vote.DOWN)

    run_feedback(session, now=NOW)

    assert preferences(session, user)[("india", "infrastructure")] == pytest.approx(-1.0)


def test_every_topic_tag_on_the_story_moves(session: Session) -> None:
    user = make_user(session)
    story = make_story(session, "infrastructure", "national-policy")
    vote(session, user, story, Vote.UP)

    run_feedback(session, now=NOW)
    scores = preferences(session, user)

    assert scores[("india", "infrastructure")] == pytest.approx(1.0)
    assert scores[("india", "national-policy")] == pytest.approx(1.0)


def test_entity_tags_are_not_treated_as_tastes(session: Session) -> None:
    """Liking one story about a company is not liking that company."""
    user = make_user(session)
    story = make_story(session, "infrastructure", entities=("cabinet",))
    vote(session, user, story, Vote.UP)

    run_feedback(session, now=NOW)

    assert set(preferences(session, user)) == {("india", "infrastructure")}


def test_preferences_are_scoped_to_the_story_genre(session: Session) -> None:
    user = make_user(session)
    story = make_story(session, "infrastructure")
    vote(session, user, story, Vote.UP)

    run_feedback(session, now=NOW)

    assert ("india", "infrastructure") in preferences(session, user)
    assert ("sports", "infrastructure") not in preferences(session, user)


def test_two_readers_keep_separate_preferences(session: Session) -> None:
    one = make_user(session, "one@example.com")
    two = make_user(session, "two@example.com")
    story = make_story(session, "infrastructure")
    vote(session, one, story, Vote.UP)
    vote(session, two, story, Vote.DOWN)

    run_feedback(session, now=NOW)

    assert preferences(session, one)[("india", "infrastructure")] > 0
    assert preferences(session, two)[("india", "infrastructure")] < 0


# ------------------------------------------------------------- bounding


def test_a_score_saturates_rather_than_growing_without_limit(session: Session) -> None:
    """Fifty cricket votes must not outweigh a keyword the reader asked for."""
    user = make_user(session)
    session.add(
        UserPreference(user_id=user.id, genre="india", topic_tag="infrastructure", score=SCORE_CAP)
    )
    story = make_story(session, "infrastructure")
    vote(session, user, story, Vote.UP)

    run_feedback(session, now=NOW)

    assert preferences(session, user)[("india", "infrastructure")] <= SCORE_CAP


# --------------------------------------------------------------- decay


def test_every_preference_decays_toward_zero(session: Session) -> None:
    user = make_user(session)
    session.add(UserPreference(user_id=user.id, genre="india", topic_tag="markets", score=4.0))
    session.flush()

    report = run_feedback(session, now=NOW)

    assert report.decayed == 1
    assert preferences(session, user)[("india", "markets")] == pytest.approx(4.0 * DECAY)


def test_a_faded_preference_is_removed(session: Session) -> None:
    user = make_user(session)
    session.add(
        UserPreference(user_id=user.id, genre="india", topic_tag="markets", score=PRUNE_BELOW / 2)
    )
    session.flush()

    report = run_feedback(session, now=NOW)

    assert report.pruned == 1
    assert preferences(session, user) == {}


def test_a_vote_cast_today_is_not_immediately_discounted(session: Session) -> None:
    """Decay runs first, so today's vote lands at its full weight."""
    user = make_user(session)
    story = make_story(session, "infrastructure")
    vote(session, user, story, Vote.UP)

    run_feedback(session, now=NOW)

    assert preferences(session, user)[("india", "infrastructure")] == pytest.approx(1.0)


# --------------------------------------------------------- exactly once


def test_a_vote_is_counted_once_however_often_the_job_runs(session: Session) -> None:
    user = make_user(session)
    story = make_story(session, "infrastructure")
    vote(session, user, story, Vote.UP)

    run_feedback(session, now=NOW)
    first = preferences(session, user)[("india", "infrastructure")]

    second_report = run_feedback(session, now=NOW)

    assert second_report.processed == 0
    # A same-day rerun applies neither the vote nor decay a second time.
    assert second_report.decayed == 0
    assert preferences(session, user)[("india", "infrastructure")] == pytest.approx(first)


def test_a_same_day_rerun_does_not_decay_twice(session: Session) -> None:
    user = make_user(session)
    session.add(UserPreference(user_id=user.id, genre="india", topic_tag="markets", score=4.0))
    session.flush()

    run_feedback(session, now=NOW)
    first = preferences(session, user)[("india", "markets")]
    second_report = run_feedback(session, now=NOW)

    assert second_report.decayed == 0
    assert preferences(session, user)[("india", "markets")] == pytest.approx(first)


def test_a_run_the_next_day_decays_again(session: Session) -> None:
    user = make_user(session)
    session.add(UserPreference(user_id=user.id, genre="india", topic_tag="markets", score=4.0))
    session.flush()

    run_feedback(session, now=NOW)
    first = preferences(session, user)[("india", "markets")]
    next_day_report = run_feedback(session, now=NOW + timedelta(days=1))

    assert next_day_report.decayed == 1
    assert preferences(session, user)[("india", "markets")] == pytest.approx(first * DECAY)


def test_a_skipped_day_still_decays_by_the_full_elapsed_amount(session: Session) -> None:
    """A gap of several days (the job missed a day, or several) decays by
    the corresponding power of DECAY in the one run that finally happens,
    rather than by a single day's worth regardless of the gap."""
    user = make_user(session)
    session.add(
        UserPreference(
            user_id=user.id, genre="india", topic_tag="markets", score=4.0, last_decayed_at=NOW
        )
    )
    session.flush()

    report = run_feedback(session, now=NOW + timedelta(days=3))

    assert report.decayed == 1
    assert preferences(session, user)[("india", "markets")] == pytest.approx(4.0 * DECAY**3)


def test_processed_feedback_is_stamped(session: Session) -> None:
    user = make_user(session)
    story = make_story(session, "infrastructure")
    row = vote(session, user, story, Vote.UP)

    run_feedback(session, now=NOW)

    assert row.aggregated_at is not None


# ------------------------------------------------------------- deletion


def test_an_anonymised_vote_belongs_to_nobody(session: Session) -> None:
    """The reader exercised their deletion right; the vote stays, unattributed."""
    story = make_story(session, "infrastructure")
    session.add(Feedback(user_id=None, story_id=story.id, vote=Vote.UP))
    session.flush()

    report = run_feedback(session, now=NOW)

    assert report.anonymised_skipped == 1
    assert session.scalar(select(func.count()).select_from(UserPreference)) == 0


def test_an_anonymised_vote_is_still_stamped(session: Session) -> None:
    story = make_story(session, "infrastructure")
    row = Feedback(user_id=None, story_id=story.id, vote=Vote.UP)
    session.add(row)
    session.flush()

    run_feedback(session, now=NOW)
    assert row.aggregated_at is not None


# ------------------------------------------------------------------ run


def test_the_run_is_recorded(session: Session) -> None:
    user = make_user(session)
    story = make_story(session, "infrastructure")
    vote(session, user, story, Vote.UP)

    run_feedback(session, now=NOW)

    run = session.scalar(select(PipelineRun).where(PipelineRun.started_at == NOW))
    assert run is not None
    assert run.status is RunStatus.SUCCEEDED
    assert run.detail is not None
    assert run.detail["processed"] == 1


def test_no_feedback_is_not_a_failure(session: Session) -> None:
    report = run_feedback(session, now=NOW)
    assert report.processed == 0
