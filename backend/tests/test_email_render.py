"""Assembling one reader's edition."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from app.config.schemas import GenreKey
from app.render.email import (
    BRAND,
    EmailRenderer,
    Links,
    RenderedEmail,
    Weather,
    date_label,
    reading_minutes,
)
from app.render.selection import Candidate, SourceLink
from app.render.weekend import LongerRead, QuizQuestion, RecapItem, WeekendContent

EDITION = date(2026, 10, 5)

LINKS = Links(
    unsubscribe_url="https://mosaic.example.com/u/tok",
    preferences_url="https://mosaic.example.com/me/tok",
    pdf_url="https://mosaic.example.com/pdf/tok",
)


# Distinguishes "use the default one-liner" from "this story has none".
AUTO: Any = object()


def candidate(
    rank: int,
    *,
    genre: GenreKey = "india",
    headline: str | None = None,
    one_liner: Any = AUTO,
    why: str | None = None,
    hedged: bool = False,
) -> Candidate:
    return Candidate(
        story_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{genre}-{rank}"),
        genre=genre,
        headline=headline or f"Headline {rank}",
        summary="Ministers approved the plan on Tuesday.",
        one_liner=f"One liner {rank}" if one_liner is AUTO else one_liner,
        why_this_matters=why,
        hedged=hedged,
        india_relevance=False,
        pool_rank=rank,
        topic_tags=frozenset(),
        entity_tags=frozenset(),
        sources=(SourceLink(name="The Hindu", url="https://example.test/a"),),
    )


def render(
    selected: dict[GenreKey, list[Candidate]] | None = None, **overrides: object
) -> RenderedEmail:
    kwargs: dict[str, object] = {
        "first_name": "Asha",
        "edition_date": EDITION,
        "edition_number": 5,
        "selected": selected or {"india": [candidate(1), candidate(2)]},
        "links": LINKS,
    }
    kwargs.update(overrides)
    return EmailRenderer().render(**kwargs)  # type: ignore[arg-type]


# ----------------------------------------------------------------- masthead


def test_the_masthead_carries_the_brand_date_and_edition_number() -> None:
    email = render()

    assert BRAND in email.html
    assert "Monday, 5 October 2026" in email.html
    assert "Edition 5" in email.html


def test_the_reader_is_named_in_both_formats() -> None:
    email = render()
    assert "Curated for Asha" in email.html
    assert "Curated for Asha" in email.text


def test_the_subject_names_the_edition_date() -> None:
    assert render().subject == f"{BRAND} — Monday, 5 October 2026"


def test_the_date_label_does_not_zero_pad_the_day() -> None:
    assert date_label(date(2026, 10, 5)) == "Monday, 5 October 2026"


def test_a_special_edition_is_named_when_there_is_one() -> None:
    email = render(special_edition="Gandhi Jayanti")
    assert "Gandhi Jayanti" in email.html


def test_the_weather_box_appears_only_when_there_is_weather() -> None:
    without = render()
    with_weather = render(weather=Weather(city="Mumbai", summary="Humid", low=26, high=32))

    assert "Mumbai" not in without.html
    assert "Mumbai" in with_weather.html
    assert "Mumbai" in with_weather.text


# ------------------------------------------------------ today in 60 seconds


def test_the_digest_takes_one_line_per_section() -> None:
    email = render(
        {
            "india": [candidate(1, one_liner="India line"), candidate(2, one_liner="Second")],
            "sports": [candidate(1, genre="sports", one_liner="Sport line")],
        }
    )

    assert "India line" in email.html
    assert "Sport line" in email.html
    # One per section, so no genre dominates the glance.
    assert "Second" not in email.html.split("Today in 60 seconds")[1].split("</ul>")[0]


def test_a_story_without_a_verified_one_liner_is_skipped_not_rewritten() -> None:
    """Summarising it here would be generation with no fact check."""
    email = render({"india": [candidate(1, one_liner=None), candidate(2, one_liner="Real")]})
    digest = email.html.split("Today in 60 seconds")[1].split("</ul>")[0]

    assert "Real" in digest


def test_reading_time_is_computed_from_the_words() -> None:
    assert reading_minutes([[candidate(1)]]) == 1
    assert reading_minutes([[candidate(i) for i in range(200)]]) > 5


# ------------------------------------------------------------------ content


def test_each_selected_story_appears_with_its_sources() -> None:
    email = render()

    assert "Headline 1" in email.html
    assert "Headline 2" in email.html
    assert 'href="https://example.test/a"' in email.html
    assert "The Hindu" in email.text


def test_sections_follow_config_order_not_dictionary_order() -> None:
    """A reader's sections must not shuffle between days."""
    email = render({"sports": [candidate(1, genre="sports")], "india": [candidate(1)]})
    html = email.html

    assert html.index("Across India") < html.index("Sport")


def test_a_hedged_story_keeps_its_warning_in_the_email() -> None:
    email = render({"india": [candidate(1, hedged=True), candidate(2)]})
    assert "unconfirmed" in email.html.lower()
    assert "unconfirmed" in email.text.lower()


def test_why_this_matters_is_carried_through() -> None:
    email = render({"india": [candidate(1, why="It relieves freight capacity."), candidate(2)]})
    assert "relieves freight capacity" in email.html


def test_model_text_is_escaped_in_the_assembled_email() -> None:
    email = render({"india": [candidate(1, headline="<script>x</script>"), candidate(2)]})
    assert "<script>" not in email.html


# ------------------------------------------------------------------- footer


def test_the_footer_carries_unsubscribe_preferences_and_pdf_links() -> None:
    email = render()

    for url in (LINKS.unsubscribe_url, LINKS.preferences_url, LINKS.pdf_url):
        assert url in email.html
        assert url in email.text


def test_a_correction_note_appears_when_there_is_one() -> None:
    email = render(corrections="Yesterday's rail story misstated the length.")

    assert "misstated the length" in email.html
    assert "misstated the length" in email.text


def test_the_email_reports_what_it_contains() -> None:
    email = render({"india": [candidate(1), candidate(2), candidate(3)]})
    assert email.story_count == 3
    assert email.reading_minutes >= 1


# ---------------------------------------------------------- weekend content


def weekend_content() -> WeekendContent:
    return WeekendContent(
        longer_reads=(
            LongerRead(
                genre="india",
                headline="Corridor cleared",
                summary="Ministers approved the plan.",
                why_this_matters="It relieves freight capacity.",
                hedged=False,
                sources=(SourceLink(name="The Hindu", url="https://example.test/a"),),
            ),
        ),
        weekly_recap=(
            RecapItem(
                genre="sports",
                headline="Final decided on penalties",
                one_liner="A dramatic finish.",
                sources=(SourceLink(name="ESPN", url="https://example.test/b"),),
            ),
        ),
        quiz=(
            QuizQuestion(
                question="Which of these actually happened in ai this week?",
                options=("Model launched", "Rover lands", "Budget passed", "Final decided"),
                correct_index=0,
                source_name="The Hindu",
                source_url="https://example.test/c",
            ),
        ),
    )


def test_no_weekend_block_appears_on_an_ordinary_weekday() -> None:
    email = render()
    assert "Weekend quiz" not in email.html
    assert "WEEKEND QUIZ" not in email.text


def test_longer_reads_appear_with_their_source() -> None:
    email = render(weekend=weekend_content())
    assert "Corridor cleared" in email.html
    assert "It relieves freight capacity" in email.html
    assert 'href="https://example.test/a"' in email.html


def test_the_recap_appears_as_a_compact_list() -> None:
    email = render(weekend=weekend_content())
    assert "Final decided on penalties" in email.html
    assert "A dramatic finish" in email.html
    assert "ESPN" in email.text


def test_the_quiz_shows_the_options_and_the_grounded_answer() -> None:
    email = render(weekend=weekend_content())
    assert "Which of these actually happened in ai this week?" in email.html
    assert "Model launched" in email.html
    assert "Answer: A" in email.html
    assert 'href="https://example.test/c"' in email.html
    assert "Answer: A" in email.text


def test_an_empty_weekend_content_renders_nothing_extra() -> None:
    without = render()
    empty = render(weekend=WeekendContent())
    assert without.html == empty.html
