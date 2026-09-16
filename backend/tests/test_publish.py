"""Publishing an edition revision. Revisions are immutable and numbered."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.schemas import EditionBuild, GenreOutcome
from app.db.publish import PublishError, latest_revision, publish_revision
from app.models.editions import Edition, EditionRevision, EditionSection
from app.models.enums import RevisionReason, SectionStatus
from app.render.sections import RenderedSection

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)
EDITION = date(2026, 10, 5)


def build(**overrides: object) -> EditionBuild:
    payload: dict[str, object] = {
        "edition_date": EDITION,
        "edition_number": 5,
        "special_edition_key": None,
        "is_weekend": False,
        "genres": [GenreOutcome(genre="india", status=SectionStatus.OK)],
    }
    payload.update(overrides)
    return EditionBuild.model_validate(payload)


def section(
    genre: str = "india",
    status: SectionStatus = SectionStatus.OK,
    stories: int = 3,
) -> RenderedSection:
    return RenderedSection(
        genre=genre,
        status=status,
        html=f"<section>{genre}</section>",
        plain_text=f"{genre}",
        story_count=stories,
    )


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


# ------------------------------------------------------------- happy path


def test_publishing_creates_the_edition_revision_and_sections(session: Session) -> None:
    revision = publish_revision(
        session, build=build(), sections={"india": section()}, published_at=NOW
    )

    assert revision.revision == 1
    assert revision.reason is RevisionReason.BUILD

    edition = session.scalar(select(Edition))
    assert edition is not None
    assert edition.edition_date == EDITION
    assert edition.edition_number == 5

    stored = session.scalar(select(EditionSection))
    assert stored is not None
    assert stored.genre == "india"
    assert stored.html == "<section>india</section>"
    assert stored.story_count == 3


def test_a_special_edition_and_weekend_flag_are_recorded(session: Session) -> None:
    publish_revision(
        session,
        build=build(
            edition_date=date(2026, 10, 3),
            edition_number=3,
            special_edition_key="gandhi-jayanti-2026",
            is_weekend=True,
        ),
        sections={"india": section()},
        published_at=NOW,
    )

    edition = session.scalar(select(Edition))
    assert edition is not None
    assert edition.special_edition_key == "gandhi-jayanti-2026"
    assert edition.is_weekend is True


# ------------------------------------------------------------- revisions


def test_a_second_publish_adds_a_revision_rather_than_editing(session: Session) -> None:
    first = publish_revision(
        session, build=build(), sections={"india": section(stories=3)}, published_at=NOW
    )
    second = publish_revision(
        session,
        build=build(),
        sections={"india": section(stories=4)},
        reason=RevisionReason.LATE_UPDATE,
        published_at=NOW,
    )

    assert (first.revision, second.revision) == (1, 2)
    assert count(session, Edition) == 1  # one edition, two revisions
    assert count(session, EditionRevision) == 2
    # The first revision's section is untouched: readers already served it.
    original = session.scalar(select(EditionSection).where(EditionSection.revision_id == first.id))
    assert original is not None
    assert original.story_count == 3


def test_revisions_share_the_edition_number(session: Session) -> None:
    publish_revision(session, build=build(), sections={"india": section()}, published_at=NOW)
    publish_revision(session, build=build(), sections={"india": section()}, published_at=NOW)

    numbers = {edition.edition_number for edition in session.scalars(select(Edition))}
    assert numbers == {5}


def test_the_latest_revision_is_findable(session: Session) -> None:
    publish_revision(session, build=build(), sections={"india": section()}, published_at=NOW)
    second = publish_revision(
        session, build=build(), sections={"india": section()}, published_at=NOW
    )

    assert latest_revision(session, EDITION) is not None
    found = latest_revision(session, EDITION)
    assert found is not None
    assert found.id == second.id


def test_a_conflicting_edition_number_is_refused(session: Session) -> None:
    publish_revision(session, build=build(), sections={"india": section()}, published_at=NOW)

    with pytest.raises(PublishError, match="check launch_date"):
        publish_revision(
            session,
            build=build(edition_number=99),
            sections={"india": section()},
            published_at=NOW,
        )


# ---------------------------------------------------------------- refusal


def test_a_revision_with_nothing_usable_is_refused(session: Session) -> None:
    """Publishing it would serve readers an edition of nothing but notices."""
    with pytest.raises(PublishError, match="no usable section"):
        publish_revision(
            session,
            build=build(),
            sections={
                "india": section(status=SectionStatus.QUIET_DAY, stories=0),
                "politics": section("politics", SectionStatus.FAILED, 0),
            },
            published_at=NOW,
        )

    assert count(session, Edition) == 0


def test_quiet_and_failed_sections_ride_along_with_a_usable_one(session: Session) -> None:
    publish_revision(
        session,
        build=build(),
        sections={
            "india": section(),
            "politics": section("politics", SectionStatus.QUIET_DAY, 0),
            "sports": section("sports", SectionStatus.FAILED, 0),
        },
        published_at=NOW,
    )

    statuses = {row.genre: row.status for row in session.scalars(select(EditionSection))}
    assert statuses == {
        "india": SectionStatus.OK,
        "politics": SectionStatus.QUIET_DAY,
        "sports": SectionStatus.FAILED,
    }
