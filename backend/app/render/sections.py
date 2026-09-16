"""Agent 8, part one — pre-rendering genre sections. No LLM.

A section is rendered once per revision and reused for every reader who chose
that genre. Per-user assembly (masthead, extras, ordering) happens later, at
delivery; nothing here is personalised, which is what makes the work shareable.

Email constraints are deliberate, not stylistic: inline styles only, no class
selectors, no flexbox. Gmail strips <style> from the head and Outlook renders
with Word's engine.
"""

from __future__ import annotations

from collections.abc import Sequence

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from pydantic import BaseModel, ConfigDict

from app.agents.orchestrator import QUIET_DAY_NOTE
from app.agents.schemas import GenreOutcome, VerifiedStory
from app.config.loader import load_genres, load_sources
from app.config.schemas import GenreKey, GenresConfig, SourcesConfig
from app.models.enums import SectionStatus
from app.render import TEMPLATE_DIR
from app.render.selection import Candidate


class RenderedSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    genre: str
    status: SectionStatus
    html: str
    plain_text: str
    story_count: int


def build_environment() -> Environment:
    """Escaping environment for HTML templates."""
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(enabled_extensions=("j2",), default_for_string=False),
        # A missing variable must fail the render, not publish a blank.
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def text_environment() -> Environment:
    """Non-escaping twin, for the plain-text templates.

    Autoescaping keys on the .j2 suffix, which the text templates also carry,
    so they need an environment of their own or readers would see &amp; in
    plain text.
    """
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=False,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


class SectionRenderer:
    def __init__(
        self,
        *,
        genres: GenresConfig | None = None,
        sources: SourcesConfig | None = None,
        environment: Environment | None = None,
    ) -> None:
        self._genres = genres or load_genres()
        self._source_names = {
            source.key: source.name for source in (sources or load_sources()).sources
        }
        self._env = environment or build_environment()

    def render(self, outcome: GenreOutcome) -> RenderedSection:
        return self._render(
            genre=outcome.genre,
            status=outcome.status,
            stories=[self._story(story) for story in outcome.stories],
            note=outcome.note or "",
        )

    def render_candidates(
        self, genre: GenreKey, candidates: Sequence[Candidate]
    ) -> RenderedSection:
        """Render a section from stored stories rather than fresh agent output.

        The late update re-renders a section that already holds published
        stories, and by then those exist only as database rows.
        """
        return self._render(
            genre=genre,
            status=SectionStatus.OK if candidates else SectionStatus.QUIET_DAY,
            stories=[
                {
                    "headline": candidate.headline,
                    "summary": candidate.summary,
                    "why_this_matters": candidate.why_this_matters or "",
                    "hedged": candidate.hedged,
                    "sources": [
                        {"name": source.name, "url": source.url} for source in candidate.sources
                    ],
                }
                for candidate in candidates
            ],
            note="" if candidates else QUIET_DAY_NOTE,
        )

    def _render(
        self,
        *,
        genre: str,
        status: SectionStatus,
        stories: list[dict[str, object]],
        note: str,
    ) -> RenderedSection:
        settings = self._genres.by_key()[genre]  # type: ignore[index]
        context = {
            "section_title": settings.section_title,
            "blurb": settings.blurb,
            "theme": settings.theme.model_dump(),
            "status": status.value,
            "stories": stories,
            "note": note,
        }

        html = self._env.get_template("section.html.j2").render(**context)
        plain = text_environment().get_template("section.txt.j2").render(**context)

        return RenderedSection(
            genre=genre,
            status=status,
            html=html.strip(),
            plain_text=tidy(plain),
            story_count=len(stories),
        )

    def _story(self, verified: VerifiedStory) -> dict[str, object]:
        written = verified.story
        return {
            "headline": written.headline.text,
            "summary": " ".join(sentence.text for sentence in written.summary),
            "why_this_matters": " ".join(sentence.text for sentence in written.why_this_matters),
            "hedged": written.hedged,
            "sources": self._sources(verified),
        }

    def _sources(self, verified: VerifiedStory) -> list[dict[str, str]]:
        seen: dict[str, dict[str, str]] = {}
        for article in verified.articles:
            if article.source_key in seen:
                continue
            seen[article.source_key] = {
                "name": self._source_names.get(article.source_key, article.source_key),
                "url": article.url,
            }
        return list(seen.values())


def tidy(text: str) -> str:
    """Collapse the blank lines Jinja block tags leave behind."""
    lines = [line.rstrip() for line in text.splitlines()]
    tidied: list[str] = []
    for line in lines:
        if not line and tidied and not tidied[-1]:
            continue
        tidied.append(line)
    return "\n".join(tidied).strip()
