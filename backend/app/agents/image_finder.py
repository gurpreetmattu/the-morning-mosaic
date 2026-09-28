"""Image finder (agent 6). LLM: text only (never the image itself) + code.

Scope, confirmed with the owner before building: one image per genre
section, attached to that section's top-ranked story — not one per verified
story, which would multiply API calls and LLM relevance checks by up to 6x
per genre for a rarely-decorative payoff. If no suitable licensed image is
found, the image is simply omitted; CLAUDE.md's "use the genre's default
artwork" fallback is not built, since no such artwork (actual illustrations,
or even a config field naming one) exists yet — see docs/BACKLOG.md.

Sources, per CLAUDE.md's Images section: Wikimedia Commons (license-checked
against an allowlist of clearly reusable licenses — CC0, public domain, and
plain CC BY / CC BY-SA variants; anything else, including unclear or
non-commercial licenses sometimes present on Commons, is rejected), Unsplash,
and Pexels. Every image is hotlinked from the provider's own URL — never
downloaded or rehosted — with its credit (author, source, license) recorded
for the edition's credits section. Unsplash's API guidelines require pinging
a download-tracking endpoint when a photo is actually used (not merely
returned by search); `_track_unsplash_download` does that only for the
candidate the model actually picks.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from urllib.parse import quote as urlquote

from app.agents.schemas import WrittenStory
from app.llm.client import LlmClient, Message
from app.llm.errors import LlmError
from app.llm.prompts import image_finder_v1
from app.models.enums import ImageProvider
from app.sources.fetch import Fetcher, FetchError

logger = logging.getLogger(__name__)

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
UNSPLASH_SEARCH_API = "https://api.unsplash.com/search/photos"
PEXELS_SEARCH_API = "https://api.pexels.com/v1/search"

CANDIDATES_PER_PROVIDER = 3

# Normalised (lowercased, trimmed) Commons `LicenseShortName` values that are
# unambiguously reusable with attribution. Everything else — including
# unclear, non-commercial, or no-derivatives licenses that do turn up on
# Commons despite its free-license policy — is rejected rather than trusted.
_LICENSE_ALLOWLIST = frozenset(
    {
        "cc0",
        "public domain",
        "cc by",
        "cc by 1.0",
        "cc by 2.0",
        "cc by 2.5",
        "cc by 3.0",
        "cc by 4.0",
        "cc by-sa",
        "cc by-sa 1.0",
        "cc by-sa 2.0",
        "cc by-sa 2.5",
        "cc by-sa 3.0",
        "cc by-sa 4.0",
    }
)

_HTML_TAG = re.compile(r"<[^>]+>")


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", _HTML_TAG.sub(" ", value)).strip()


@dataclass(frozen=True)
class ImageCandidate:
    provider: ImageProvider
    display_url: str
    page_url: str | None
    author: str | None
    license_name: str | None
    license_url: str | None
    width: int | None
    height: int | None
    caption: str
    # Unsplash only: pinged if and only if this candidate is chosen.
    download_location: str | None = None


@dataclass(frozen=True)
class ImageResult:
    provider: ImageProvider
    display_url: str
    page_url: str | None
    author: str | None
    license_name: str | None
    license_url: str | None
    width: int | None
    height: int | None
    credit: str


def _query_for(story: WrittenStory) -> str | None:
    """Entity tags make a far more concrete image search than a full
    headline (a headline is prose; "Narendra Modi", "Mumbai" are searchable
    subjects), so they're preferred. Falls back to the headline itself only
    when a story has none.
    """
    if story.entity_tags:
        return " ".join(story.entity_tags[:3])
    return story.headline.text.strip() or None


# ------------------------------------------------------------- providers


def _wikimedia_candidates(fetcher: Fetcher, query: str) -> list[ImageCandidate]:
    search_url = (
        f"{COMMONS_API}?action=query&list=search&srnamespace=6"
        f"&srlimit={CANDIDATES_PER_PROVIDER}&format=json&srsearch={urlquote(query)}"
    )
    try:
        response = fetcher.get(search_url)
        titles = [item["title"] for item in response.json()["query"]["search"]]
    except (FetchError, KeyError, TypeError):
        logger.warning("wikimedia search failed for query=%r", query, exc_info=True)
        return []
    if not titles:
        return []

    info_url = (
        f"{COMMONS_API}?action=query&titles={urlquote('|'.join(titles))}"
        "&prop=imageinfo&iiprop=url%7Cextmetadata%7Csize&format=json"
    )
    try:
        response = fetcher.get(info_url)
        pages = response.json()["query"]["pages"]
    except (FetchError, KeyError, TypeError):
        logger.warning("wikimedia imageinfo failed for query=%r", query, exc_info=True)
        return []

    candidates: list[ImageCandidate] = []
    for page in pages.values():
        infos = page.get("imageinfo")
        if not infos:
            continue
        info = infos[0]
        meta = info.get("extmetadata", {})
        license_name = meta.get("LicenseShortName", {}).get("value", "").strip()
        if license_name.lower() not in _LICENSE_ALLOWLIST:
            continue
        author = _strip_html(meta.get("Artist", {}).get("value", "")) or None
        description = _strip_html(meta.get("ImageDescription", {}).get("value", "")) or page.get(
            "title", ""
        )
        candidates.append(
            ImageCandidate(
                provider=ImageProvider.WIKIMEDIA,
                display_url=info["url"],
                page_url=info.get("descriptionurl"),
                author=author,
                license_name=license_name,
                license_url=meta.get("LicenseUrl", {}).get("value") or None,
                width=info.get("width"),
                height=info.get("height"),
                caption=description[:300],
            )
        )
    return candidates


def _unsplash_candidates(fetcher: Fetcher, query: str, api_key: str) -> list[ImageCandidate]:
    url = f"{UNSPLASH_SEARCH_API}?query={urlquote(query)}&per_page={CANDIDATES_PER_PROVIDER}"
    try:
        response = fetcher.get(url, headers={"Authorization": f"Client-ID {api_key}"})
        results = response.json()["results"]
    except (FetchError, KeyError, TypeError):
        logger.warning("unsplash search failed for query=%r", query, exc_info=True)
        return []

    candidates = []
    for item in results:
        caption = item.get("alt_description") or item.get("description") or ""
        if not caption:
            continue
        user = item.get("user", {})
        candidates.append(
            ImageCandidate(
                provider=ImageProvider.UNSPLASH,
                display_url=item["urls"]["regular"],
                page_url=user.get("links", {}).get("html"),
                author=user.get("name"),
                license_name="Unsplash License",
                license_url="https://unsplash.com/license",
                width=item.get("width"),
                height=item.get("height"),
                caption=caption[:300],
                download_location=item.get("links", {}).get("download_location"),
            )
        )
    return candidates


def _pexels_candidates(fetcher: Fetcher, query: str, api_key: str) -> list[ImageCandidate]:
    url = f"{PEXELS_SEARCH_API}?query={urlquote(query)}&per_page={CANDIDATES_PER_PROVIDER}"
    try:
        response = fetcher.get(url, headers={"Authorization": api_key})
        photos = response.json()["photos"]
    except (FetchError, KeyError, TypeError):
        logger.warning("pexels search failed for query=%r", query, exc_info=True)
        return []

    candidates = []
    for item in photos:
        caption = item.get("alt") or ""
        if not caption:
            continue
        candidates.append(
            ImageCandidate(
                provider=ImageProvider.PEXELS,
                display_url=item["src"]["large"],
                page_url=item.get("url"),
                author=item.get("photographer"),
                license_name="Pexels License",
                license_url="https://www.pexels.com/license/",
                width=item.get("width"),
                height=item.get("height"),
                caption=caption[:300],
            )
        )
    return candidates


def _track_unsplash_download(fetcher: Fetcher, download_location: str, api_key: str) -> None:
    """Fire-and-log: Unsplash's API guidelines require this ping whenever a
    photo is actually used, but a failure here must never cost a reader
    their story's image.
    """
    try:
        fetcher.get(download_location, headers={"Authorization": f"Client-ID {api_key}"})
    except FetchError:
        logger.warning("unsplash download-tracking ping failed", exc_info=True)


def _credit_for(candidate: ImageCandidate) -> str:
    author = candidate.author or "Unknown"
    if candidate.provider is ImageProvider.WIKIMEDIA:
        return f"{author} / Wikimedia Commons ({candidate.license_name})"
    if candidate.provider is ImageProvider.UNSPLASH:
        return f"Photo by {author} on Unsplash"
    return f"Photo by {author} on Pexels"


def _strip_fence(text: str) -> str:
    """Models wrap JSON in ``` fences often enough to be worth handling."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    return stripped.strip("`").removeprefix("json").strip()


# ------------------------------------------------------------- entry point


def find_image(
    llm: LlmClient,
    fetcher: Fetcher,
    *,
    story: WrittenStory,
    unsplash_api_key: str | None,
    pexels_api_key: str | None,
) -> ImageResult | None:
    """None whenever no licensed, genuinely relevant image can be found —
    never raises, since a missing image is cosmetic, not a reason to hold up
    or fail a story.
    """
    query = _query_for(story)
    if query is None:
        return None

    candidates: list[ImageCandidate] = _wikimedia_candidates(fetcher, query)
    if unsplash_api_key:
        candidates += _unsplash_candidates(fetcher, query, unsplash_api_key)
    if pexels_api_key:
        candidates += _pexels_candidates(fetcher, query, pexels_api_key)
    if not candidates:
        return None

    rendered = "\n".join(
        image_finder_v1.render_candidate(index, candidate.caption)
        for index, candidate in enumerate(candidates)
    )
    try:
        result = llm.complete(
            "image_finder",
            [
                Message(role="system", content=image_finder_v1.SYSTEM),
                Message(
                    role="user",
                    content=image_finder_v1.USER_TEMPLATE.format(
                        headline=story.headline.text, candidates=rendered
                    ),
                ),
            ],
            json_object=True,
            prompt_version=image_finder_v1.VERSION,
        )
        payload = json.loads(_strip_fence(result.text))
        index = payload.get("index")
    except (LlmError, ValueError, KeyError, TypeError):
        logger.warning("image finder relevance check failed", exc_info=True)
        return None

    if not isinstance(index, int) or not (0 <= index < len(candidates)):
        return None

    chosen = candidates[index]
    if chosen.provider is ImageProvider.UNSPLASH and chosen.download_location and unsplash_api_key:
        _track_unsplash_download(fetcher, chosen.download_location, unsplash_api_key)

    return ImageResult(
        provider=chosen.provider,
        display_url=chosen.display_url,
        page_url=chosen.page_url,
        author=chosen.author,
        license_name=chosen.license_name,
        license_url=chosen.license_url,
        width=chosen.width,
        height=chosen.height,
        credit=_credit_for(chosen),
    )
