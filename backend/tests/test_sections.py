"""Section rendering: email-safe, escaped, and always sourced."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.agents.image_finder import ImageResult
from app.agents.schemas import (
    DraftSentence,
    GenreOutcome,
    VerifiedStory,
    WrittenStory,
)
from app.models.enums import ImageProvider, SectionStatus
from app.render.sections import SectionRenderer
from app.render.selection import Candidate, SourceLink
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
    one_liner: str | None = None,
    pool_rank: int = 1,
    articles: list[CollectedArticle] | None = None,
    topic_tags: list[str] | None = None,
) -> VerifiedStory:
    return VerifiedStory(
        story=WrittenStory(
            headline=DraftSentence(text=headline, passage_ids=["a1:p1"]),
            summary=[DraftSentence(text="Ministers approved it.", passage_ids=["a1:p1"])],
            one_liner=DraftSentence(text=one_liner, passage_ids=["a1:p1"]) if one_liner else None,
            why_this_matters=([DraftSentence(text=why, passage_ids=["a1:p1"])] if why else []),
            hedged=hedged,
            topic_tags=topic_tags or [],
        ),
        articles=articles or [article()],
        pool_rank=pool_rank,
        attempts=1,
    )


def outcome(
    status: SectionStatus = SectionStatus.OK,
    *stories: VerifiedStory,
    genre: str = "india",
    note: str | None = None,
) -> GenreOutcome:
    return GenreOutcome(
        genre=genre,  # type: ignore[arg-type]
        status=status,
        stories=list(stories) if status is SectionStatus.OK else [],
        note=note,
    )


def candidate(
    rank: int,
    *,
    genre: str = "ai",
    headline: str = "Model launched",
    one_liner: str | None = "A quick summary.",
    source: SourceLink | None = None,
    topic_tags: frozenset[str] = frozenset(),
) -> Candidate:
    return Candidate(
        story_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{genre}-{rank}-{headline}"),
        genre=genre,  # type: ignore[arg-type]
        headline=headline,
        summary="Summary.",
        one_liner=one_liner,
        why_this_matters=None,
        hedged=False,
        india_relevance=False,
        pool_rank=rank,
        topic_tags=topic_tags,
        entity_tags=frozenset(),
        sources=(source,)
        if source
        else (SourceLink(name="The Hindu", url="https://example.test/tool"),),
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


# --------------------------------------------------------- ai tool of the day


def test_the_top_ai_story_becomes_the_ai_tool_of_the_day() -> None:
    html, text = render(
        outcome(
            SectionStatus.OK,
            verified("Model launches with new benchmark", one_liner="A faster, cheaper model."),
            genre="ai",
        )
    )

    assert "AI tool of the day" in html
    assert "Model launches with new benchmark" in html
    assert "A faster, cheaper model." in html
    assert "AI tool of the day" in text
    assert "A faster, cheaper model." in text


def test_the_ai_tool_falls_back_to_the_first_summary_sentence_with_no_one_liner() -> None:
    html, _ = render(outcome(SectionStatus.OK, verified("Model launches"), genre="ai"))

    assert "AI tool of the day" in html
    assert "Ministers approved it." in html  # the fixture's default summary sentence


def test_only_the_top_ranked_ai_story_is_featured() -> None:
    html, _ = render(
        outcome(
            SectionStatus.OK,
            verified("First place story", pool_rank=1),
            verified("Second place story", pool_rank=2),
            genre="ai",
        )
    )

    tool_line = html.split("AI tool of the day:")[1].split("</p>")[0]
    assert "First place story" in tool_line
    assert "Second place story" not in tool_line


def test_no_ai_tool_callout_for_a_non_ai_genre() -> None:
    html, text = render(outcome(SectionStatus.OK, verified(), genre="india"))

    assert "AI tool of the day" not in html
    assert "AI tool of the day" not in text


def test_no_ai_tool_callout_on_a_quiet_ai_day() -> None:
    html, _ = render(outcome(SectionStatus.QUIET_DAY, genre="ai", note="A quiet news day."))

    assert "AI tool of the day" not in html


def test_render_candidates_also_features_the_top_ranked_ai_story() -> None:
    rendered = SectionRenderer().render_candidates(
        "ai",
        [
            candidate(2, headline="Runner-up tool"),
            candidate(1, headline="Top tool", one_liner="The one that matters."),
        ],
    )

    assert "AI tool of the day" in rendered.html
    assert "Top tool" in rendered.html.split("AI tool of the day:")[1].split("</p>")[0]
    assert "The one that matters." in rendered.html


def test_render_candidates_has_no_ai_tool_for_other_genres() -> None:
    rendered = SectionRenderer().render_candidates("india", [candidate(1, genre="india")])

    assert "AI tool of the day" not in rendered.html


# ------------------------------------------------------------------ image


def image(*, credit: str = "Jane Doe / Wikimedia Commons (CC BY-SA 4.0)") -> ImageResult:
    return ImageResult(
        provider=ImageProvider.WIKIMEDIA,
        display_url="https://upload.wikimedia.org/example.jpg",
        page_url="https://commons.wikimedia.org/wiki/File:example.jpg",
        author="Jane Doe",
        license_name="CC BY-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0",
        width=1200,
        height=800,
        credit=credit,
    )


def test_a_section_image_and_its_credit_render() -> None:
    rendered = SectionRenderer().render(outcome(SectionStatus.OK, verified()), image=image())

    assert 'src="https://upload.wikimedia.org/example.jpg"' in rendered.html
    assert "Jane Doe / Wikimedia Commons (CC BY-SA 4.0)" in rendered.html
    assert "Jane Doe / Wikimedia Commons (CC BY-SA 4.0)" in rendered.plain_text


def test_no_image_block_when_none_was_found() -> None:
    rendered = SectionRenderer().render(outcome(SectionStatus.OK, verified()))

    assert "<img" not in rendered.html


def test_render_candidates_never_carries_an_image() -> None:
    """Late update re-renders from persisted candidates, not fresh agent
    output — the Image finder never runs there (see docs/BACKLOG.md)."""
    rendered = SectionRenderer().render_candidates("india", [candidate(1, genre="india")])

    assert "<img" not in rendered.html


# --------------------------------------------------------------- movie releases


def test_movie_releases_and_tmdb_attribution_render() -> None:
    releases = [
        {"title": "Sooner Movie", "release_date": "2026-10-02", "overview": ""},
        {"title": "Later Movie", "release_date": "2026-10-16", "overview": ""},
    ]
    rendered = SectionRenderer().render(
        outcome(SectionStatus.OK, verified(), genre="bollywood"), movie_releases=releases
    )

    assert "Coming soon" in rendered.html
    assert "Sooner Movie (2026-10-02)" in rendered.html
    assert "Later Movie (2026-10-16)" in rendered.html
    assert "not endorsed, certified, or otherwise approved by TMDB" in rendered.html
    assert "Coming soon" in rendered.plain_text
    assert "not endorsed, certified, or otherwise approved by TMDB" in rendered.plain_text


def test_no_movie_releases_block_when_none_were_found() -> None:
    rendered = SectionRenderer().render(outcome(SectionStatus.OK, verified()))

    assert "Coming soon" not in rendered.html
    assert "TMDB" not in rendered.html


# --------------------------------------------------------------- scores/fixtures


def test_scores_and_fixtures_render_in_both_formats() -> None:
    scores = [{"team1": "India", "team2": "Pakistan", "status": "India won by 4 wickets"}]
    fixtures = [{"team1": "Sri Lanka", "team2": "Nepal", "when": "29 Sep, 05:30 IST"}]
    rendered = SectionRenderer().render(
        outcome(SectionStatus.OK, verified(), genre="sports"), scores=scores, fixtures=fixtures
    )

    assert "Scores:" in rendered.html
    assert "India v Pakistan: India won by 4 wickets" in rendered.html
    assert "Fixtures:" in rendered.html
    assert "Sri Lanka v Nepal (29 Sep, 05:30 IST)" in rendered.html
    assert "Scores:" in rendered.plain_text
    assert "Fixtures:" in rendered.plain_text


def test_no_scores_or_fixtures_block_when_none_were_found() -> None:
    rendered = SectionRenderer().render(outcome(SectionStatus.OK, verified(), genre="sports"))

    assert "Scores:" not in rendered.html
    assert "Fixtures:" not in rendered.html


# ------------------------------------------------------------------ game deals


def test_game_deals_render_in_both_formats() -> None:
    deals = [
        {
            "title": "Game A",
            "savings_percent": "50",
            "store": "Steam",
            "url": "https://www.cheapshark.com/redirect?dealID=abc",
        }
    ]
    rendered = SectionRenderer().render(
        outcome(SectionStatus.OK, verified(), genre="gaming"), game_deals=deals
    )

    assert "Deals:" in rendered.html
    assert "Game A" in rendered.html
    assert "50% off (Steam)" in rendered.html
    assert 'href="https://www.cheapshark.com/redirect?dealID=abc"' in rendered.html
    assert "Deals:" in rendered.plain_text
    assert "50% off (Steam)" in rendered.plain_text


def test_no_game_deals_block_when_none_were_found() -> None:
    rendered = SectionRenderer().render(outcome(SectionStatus.OK, verified(), genre="gaming"))

    assert "Deals:" not in rendered.html


# --------------------------------------------------------------- music releases


def test_a_tagged_music_story_becomes_a_new_release() -> None:
    html, text = render(
        outcome(
            SectionStatus.OK,
            verified("Artist drops surprise album", topic_tags=["album-releases"]),
            genre="music",
        )
    )

    assert "New releases:" in html
    assert "Artist drops surprise album" in html
    assert "New releases:" in text
    assert "Artist drops surprise album" in text


def test_an_untagged_music_story_is_not_a_new_release() -> None:
    html, _ = render(
        outcome(
            SectionStatus.OK, verified("A tour is announced", topic_tags=["tours"]), genre="music"
        )
    )

    assert "New releases:" not in html


def test_no_new_releases_callout_for_a_non_music_genre() -> None:
    html, _ = render(
        outcome(
            SectionStatus.OK,
            verified("Something else", topic_tags=["album-releases"]),
            genre="india",
        )
    )

    assert "New releases:" not in html


def test_up_to_three_tagged_stories_become_new_releases() -> None:
    stories = [
        verified(f"Release {i}", topic_tags=["single-releases"], pool_rank=i + 1) for i in range(4)
    ]
    html, _ = render(outcome(SectionStatus.OK, *stories, genre="music"))
    callout = html.split("New releases:")[1].split("</p>")[0]

    assert "Release 0" in callout
    assert "Release 1" in callout
    assert "Release 2" in callout
    assert "Release 3" not in callout


def test_render_candidates_also_surfaces_tagged_music_releases() -> None:
    rendered = SectionRenderer().render_candidates(
        "music",
        [
            candidate(
                1,
                genre="music",
                headline="Tagged single",
                topic_tags=frozenset({"single-releases"}),
            )
        ],
    )

    assert "New releases:" in rendered.html
    assert "Tagged single" in rendered.html
