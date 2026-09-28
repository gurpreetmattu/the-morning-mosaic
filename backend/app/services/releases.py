"""Movie releases (a genre extra, part of agent 8/Layout's extras) for the
bollywood and hollywood genres. No LLM: one HTTP call to TMDB per genre per
edition_date, persisted once in `extras` — the first extra scoped to a
single genre rather than the whole edition (`Extra.genre` existed in the
schema for exactly this, unused until now).

**Terms, checked before building, the same way market data's provider was**:
TMDB's free API key is for non-commercial use — their own definition of
"commercial" covers charging users, running ads, or recommendation-driven
revenue, none of which apply to this (free, unmonetised) newsletter, so the
free key is the right fit. Their terms also require attribution: a specific
text notice (included below, verbatim) *and* their logo, sized per their own
rules. Only the text notice is shown here — no reliable official logo asset
URL was sourced, and guessing one risks getting their branding rules wrong.
Flagged as an open item in docs/BACKLOG.md rather than skipped silently.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now_utc
from app.models.content import Extra
from app.models.enums import ExtraKind
from app.sources.fetch import Fetcher, FetchError

logger = logging.getLogger(__name__)

TMDB_UPCOMING_API = "https://api.themoviedb.org/3/movie/upcoming"
TMDB_SOURCE = "TMDB"
TMDB_ATTRIBUTION = (
    "This newsletter uses TMDB and the TMDB APIs but is not endorsed, "
    "certified, or otherwise approved by TMDB."
)
RELEASES_PER_GENRE = 3

# CLAUDE.md: bollywood is "Indian cinema" (broader than Hindi-language films
# alone, per the genre's own blurb), hollywood is "Global film and
# television" — TMDB's own region codes are the natural fit for both.
GENRE_REGIONS: dict[str, str] = {"bollywood": "IN", "hollywood": "US"}


class ReleasesFetchError(Exception):
    """The releases could not be fetched or did not parse as expected."""


def region_for(genre: str) -> str | None:
    return GENRE_REGIONS.get(genre)


def fetch_movie_releases(fetcher: Fetcher, *, region: str, api_key: str) -> list[dict[str, str]]:
    """TMDB's own `upcoming` endpoint already scopes to a near-term window
    (observed live: roughly the next three weeks), so no extra date
    filtering is needed here — only sorting and a top-N cap.
    """
    url = f"{TMDB_UPCOMING_API}?api_key={api_key}&region={region}&language=en-US"
    try:
        response = fetcher.get(url)
        results = response.json()["results"]
    except (FetchError, KeyError, TypeError) as exc:
        raise ReleasesFetchError(f"movie releases ({region}): {exc}") from exc

    releases = [
        {
            "title": str(item["title"]),
            "release_date": str(item["release_date"]),
            "overview": str(item.get("overview") or "")[:300],
        }
        for item in results
        if item.get("title") and item.get("release_date")
    ]
    releases.sort(key=lambda r: r["release_date"])
    return releases[:RELEASES_PER_GENRE]


def _existing(session: Session, *, edition_date: date, genre: str) -> Extra | None:
    return session.scalar(
        select(Extra).where(
            Extra.edition_date == edition_date,
            Extra.kind == ExtraKind.MOVIE_RELEASE,
            Extra.genre == genre,
        )
    )


def persist_movie_releases(
    session: Session,
    *,
    edition_date: date,
    genre: str,
    fetcher: Fetcher,
    api_key: str | None,
    now: datetime | None = None,
) -> Extra | None:
    """Fetch and store this genre's upcoming releases, once per edition_date.

    None whenever there is nothing to do (a non-movie genre, no API key, an
    already-persisted day) or nothing could be fetched — never raises, same
    posture as every other extra: a missing item is acceptable.
    """
    region = region_for(genre)
    if region is None or api_key is None:
        return None
    if _existing(session, edition_date=edition_date, genre=genre) is not None:
        return None

    try:
        releases = fetch_movie_releases(fetcher, region=region, api_key=api_key)
    except ReleasesFetchError:
        logger.warning("movie releases fetch failed for genre=%s", genre, exc_info=True)
        return None
    if not releases:
        return None

    row = Extra(
        edition_date=edition_date,
        kind=ExtraKind.MOVIE_RELEASE,
        genre=genre,
        payload={"releases": releases},
        source_name=TMDB_SOURCE,
        source_url="https://www.themoviedb.org/",
        data_at=now or now_utc(),
    )
    session.add(row)
    session.flush()
    return row


def load_movie_releases(
    session: Session, *, edition_date: date, genre: str
) -> list[dict[str, str]]:
    row = _existing(session, edition_date=edition_date, genre=genre)
    if row is None:
        return []
    releases: list[dict[str, str]] = row.payload["releases"]
    return releases
