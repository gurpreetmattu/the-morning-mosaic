"""Assembling one reader's edition. No LLM.

The masthead is identical for every reader except the name and the weather
box, and the stories are chosen in code from pools that were verified once.
Two readers who receive the same story receive exactly the same words.

Reading time is computed, not estimated by a model, and "Today in 60 seconds"
is assembled from one-liners the Writer already produced and the Fact-checker
already verified — never written fresh here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from jinja2 import Environment
from pydantic import BaseModel, ConfigDict

from app.agents.image_finder import ImageResult
from app.agents.orchestrator import QUIET_DAY_NOTE
from app.config.loader import load_genres
from app.config.schemas import GenreKey, GenresConfig
from app.render.sections import build_environment, text_environment, tidy
from app.render.selection import Candidate, ai_tool_from_candidates, music_releases_from_candidates
from app.render.weekend import WeekendContent

BRAND = "The Morning Mosaic"
TAGLINE = "The morning paper, set to your interests."

# Ordinary adult reading speed for news prose.
WORDS_PER_MINUTE = 220
# The digest is a glance, not a second edition.
MAX_SIXTY_SECOND_LINES = 6


@dataclass(frozen=True)
class Weather:
    city: str
    summary: str
    low: int
    high: int


@dataclass(frozen=True)
class Quote:
    text: str
    author: str
    source_url: str


@dataclass(frozen=True)
class OnThisDay:
    year: int
    text: str
    source_url: str


@dataclass(frozen=True)
class MarketStrip:
    label: str
    rate: float
    as_of: date
    source_url: str


@dataclass(frozen=True)
class SectionExtras:
    """Everything about one genre's extras that isn't derivable from the
    reader's own selected Candidates (those, like "AI tool of the day" and
    music releases, are computed directly in `render()` below instead).

    Never personalised — every reader who gets a given genre on a given
    edition_date sees the same image/releases/scores/deals, only their
    story selection differs — so the caller (delivery.py) loads this once
    per genre per run, not once per reader.
    """

    image: ImageResult | None = None
    movie_releases: list[dict[str, str]] | None = None
    scores: list[dict[str, str]] | None = None
    fixtures: list[dict[str, str]] | None = None
    game_deals: list[dict[str, str]] | None = None


@dataclass(frozen=True)
class Links:
    unsubscribe_url: str
    preferences_url: str
    pdf_url: str


class RenderedEmail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str
    html: str
    text: str
    reading_minutes: int
    story_count: int


def reading_minutes(sections: Sequence[Sequence[Candidate]]) -> int:
    words = sum(
        len(f"{story.headline} {story.summary} {story.why_this_matters or ''}".split())
        for section in sections
        for story in section
    )
    return max(1, round(words / WORDS_PER_MINUTE))


def date_label(edition_date: date) -> str:
    """ "Monday, 5 October 2026".

    Built by hand rather than with strftime: the no-pad day directive is
    %-d on Linux and %#d on Windows, and this runs on both.
    """
    return f"{edition_date:%A}, {edition_date.day} {edition_date:%B} {edition_date.year}"


class EmailRenderer:
    def __init__(
        self,
        *,
        genres: GenresConfig | None = None,
        environment: Environment | None = None,
    ) -> None:
        self._genres = genres or load_genres()
        self._html = environment or build_environment()
        self._text = text_environment()

    def render(
        self,
        *,
        first_name: str,
        edition_date: date,
        edition_number: int,
        selected: Mapping[GenreKey, list[Candidate]],
        links: Links,
        weather: Weather | None = None,
        quote: Quote | None = None,
        on_this_day: OnThisDay | None = None,
        market: MarketStrip | None = None,
        special_edition: str | None = None,
        special_edition_note: str | None = None,
        special_edition_accent: str | None = None,
        corrections: str | None = None,
        weekend: WeekendContent | None = None,
        section_extras: Mapping[GenreKey, SectionExtras] | None = None,
        quiet_genres: Sequence[GenreKey] = (),
    ) -> RenderedEmail:
        by_key = self._genres.by_key()
        # Config order, so a reader's sections do not shuffle between days.
        quiet = set(quiet_genres) - set(selected)
        ordered = [
            genre.key
            for genre in self._genres.genres
            if genre.key in selected or genre.key in quiet
        ]
        extras_by_genre = section_extras or {}

        def quiet_section(key: GenreKey) -> dict[str, object]:
            """A followed genre with too few stories: header and the quiet-day note only."""
            return {
                "genre": key,
                "title": by_key[key].section_title,
                "blurb": by_key[key].blurb,
                "theme": by_key[key].theme.model_dump(),
                "quiet": True,
                "quiet_note": QUIET_DAY_NOTE,
                "stories": [],
            }

        sections = [
            quiet_section(key)
            if key in quiet
            else {
                "genre": key,
                "title": by_key[key].section_title,
                "blurb": by_key[key].blurb,
                "theme": by_key[key].theme.model_dump(),
                "quiet": False,
                "stories": selected[key],
                "image": (extras_by_genre.get(key) or SectionExtras()).image,
                "movie_releases": (extras_by_genre.get(key) or SectionExtras()).movie_releases,
                "scores": (extras_by_genre.get(key) or SectionExtras()).scores,
                "fixtures": (extras_by_genre.get(key) or SectionExtras()).fixtures,
                "game_deals": (extras_by_genre.get(key) or SectionExtras()).game_deals,
                # Never externally sourced, and never personalised either —
                # deterministic from this genre's own selected stories, the
                # same as the build-time render (see ai_tool_from_candidates).
                "ai_tool": ai_tool_from_candidates(key, selected[key]),
                "music_releases": music_releases_from_candidates(key, selected[key]),
            }
            for key in ordered
        ]
        chosen = [selected[key] for key in ordered if key in selected]
        minutes = reading_minutes(chosen)

        context = {
            "brand": BRAND,
            "tagline": TAGLINE,
            "first_name": first_name,
            "date_label": date_label(edition_date),
            "edition_number": edition_number,
            "special_edition": special_edition,
            "special_edition_note": special_edition_note,
            "special_edition_accent": special_edition_accent,
            "weather": weather,
            "quote": quote,
            "on_this_day": on_this_day,
            "market": market,
            "sixty_seconds": self._digest(chosen),
            "reading_minutes": minutes,
            "sections": sections,
            "corrections": corrections,
            "weekend": weekend if weekend else None,
            "genre_themes": {key: by_key[key].theme.model_dump() for key in by_key},
            "unsubscribe_url": links.unsubscribe_url,
            "preferences_url": links.preferences_url,
            "pdf_url": links.pdf_url,
        }

        return RenderedEmail(
            subject=f"{BRAND} — {date_label(edition_date)}",
            html=self._html.get_template("email.html.j2").render(**context).strip(),
            text=tidy(self._text.get_template("email.txt.j2").render(**context)),
            reading_minutes=minutes,
            story_count=sum(len(stories) for stories in chosen),
        )

    def _digest(self, chosen: Sequence[Sequence[Candidate]]) -> list[str]:
        """Top stories' one-liners, in section order.

        Stories whose one-liner failed verification are skipped rather than
        summarised again here: that would be generation without a check.
        """
        lines: list[str] = []
        for section in chosen:
            for story in section:
                if story.one_liner:
                    lines.append(story.one_liner)
                    break  # one per section, so no genre dominates the glance
        return lines[:MAX_SIXTY_SECOND_LINES]
