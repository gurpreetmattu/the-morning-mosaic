"""Section rendering: email-safe, escaped, and always sourced."""

from __future__ import annotations

from datetime import UTC, datetime

from app.agents.schemas import (
    DraftSentence,
    GenreOutcome,
    VerifiedStory,
    WrittenStory,
)
from app.models.enums import SectionStatus
from app.render.sections import SectionRenderer
from app.sources.schemas import CollectedArticle, Passage

NOW = datetime(2026, 10, 5, 4, 15, tzinfo=UTC)


def article(source: str = "the-hindu", suffix: str = "a") -> CollectedArticle:
    text = "A passage with enough words in it to count as a citable passage body."
    return CollectedArticle(
        source_key=source,
        genre="india",
        url=f"https://example.test/{suffix}",
        title="Cabinet clears corridor",
        published_at=NOW,
        fetched_at=NOW,
        text=text,
        passages=[Passage(ordinal=1, text=text)],
        content_hash=f"h-{suffix}",
    )


def verified(
    headline: str = "Cabinet clears the eastern corridor",
    *,
    why: str = "",
    hedged: bool = False,
    articles: list[CollectedArticle] | None = None,
) -> VerifiedStory:
    return VerifiedStory(
        story=WrittenStory(
            headline=DraftSentence(text=headline, passage_ids=["a1:p1"]),
            summary=[DraftSentence(text="Ministers approved it.", passage_ids=["a1:p1"])],
            why_this_matters=([DraftSentence(text=why, passage_ids=["a1:p1"])] if why else []),
            hedged=hedged,
        ),
        articles=articles or [article()],
        pool_rank=1,
        attempts=1,
    )


def outcome(
    status: SectionStatus = SectionStatus.OK,
    *stories: VerifiedStory,
    note: str | None = None,
) -> GenreOutcome:
    return GenreOutcome(
        genre="india",
        status=status,
        stories=list(stories) if status is SectionStatus.OK else [],
        note=note,
    )


def render(subject: GenreOutcome) -> tuple[str, str]:
    rendered = SectionRenderer().render(subject)
    return rendered.html, rendered.plain_text


# ------------------------------------------------------------- happy path


def test_a_section_renders_its_stories_in_both_formats() -> None:
    html, text = render(outcome(SectionStatus.OK, verified()))

    assert "Cabinet clears the eastern corridor" in html
    assert "Cabinet clears the eastern corridor" in text
    assert "Ministers approved it." in html
    assert "Ministers approved it." in text


def test_the_genre_title_and_theme_are_applied() -> None:
    html, text = render(outcome(SectionStatus.OK, verified()))

    assert "Across India" in html  # genres.yaml section_title
    assert "ACROSS INDIA" in text
    assert "#c4571b" in html  # the india accent colour


def test_every_story_links_to_its_sources() -> None:
    html, text = render(outcome(SectionStatus.OK, verified()))

    assert 'href="https://example.test/a"' in html
    assert "The Hindu" in html  # the display name from sources.yaml
    assert "https://example.test/a" in text


def test_multiple_sources_are_listed_and_deduplicated() -> None:
    story = verified(
        articles=[article("the-hindu", "a"), article("ndtv", "b"), article("the-hindu", "c")]
    )
    html, _ = render(outcome(SectionStatus.OK, story))

    assert "Sources:" in html
    assert html.count("example.test/") == 2  # the-hindu once, ndtv once


def test_why_this_matters_appears_only_when_present() -> None:
    with_why, _ = render(outcome(SectionStatus.OK, verified(why="It relieves freight capacity.")))
    without, _ = render(outcome(SectionStatus.OK, verified()))

    assert "Why this matters" in with_why
    assert "Why this matters" not in without


def test_a_hedged_story_carries_a_visible_warning() -> None:
    html, text = render(outcome(SectionStatus.OK, verified(hedged=True)))

    assert "unconfirmed" in html.lower()
    assert "unconfirmed" in text.lower()


# --------------------------------------------------------------- safety


def test_model_output_is_escaped_not_injected() -> None:
    """Everything rendered came from a model; it is never trusted as markup."""
    html, _ = render(
        outcome(SectionStatus.OK, verified('<script>alert("x")</script> Cabinet acts'))
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_the_html_carries_no_style_block_or_classes() -> None:
    """Gmail strips head styles; Outlook renders with Word."""
    html, _ = render(outcome(SectionStatus.OK, verified()))

    assert "<style" not in html
    assert "class=" not in html
    assert "display:flex" not in html


# ------------------------------------------------------ quiet and failed


def test_a_quiet_day_renders_the_note_and_no_stories() -> None:
    html, text = render(outcome(SectionStatus.QUIET_DAY, note="A quiet news day."))

    assert "A quiet news day." in html
    assert "A quiet news day." in text
    assert "<article" not in html


def test_a_failed_section_renders_its_short_note() -> None:
    rendered = SectionRenderer().render(
        outcome(SectionStatus.FAILED, note="This section could not be prepared in time.")
    )

    assert "could not be prepared" in rendered.html
    assert rendered.story_count == 0
    assert rendered.status is SectionStatus.FAILED


def test_the_story_count_is_reported_for_the_section_row() -> None:
    rendered = SectionRenderer().render(outcome(SectionStatus.OK, verified("One"), verified("Two")))
    assert rendered.story_count == 2
