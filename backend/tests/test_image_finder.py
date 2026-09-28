"""Image finder: text-only relevance check over real provider search results.

The LLM gateway is mocked via respx, exactly like test_ranker.py; provider
search endpoints (Wikimedia, Unsplash, Pexels) are mocked the same way.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import pytest
import respx

from app.agents.image_finder import (
    COMMONS_API,
    PEXELS_SEARCH_API,
    UNSPLASH_SEARCH_API,
    find_image,
)
from app.agents.schemas import DraftSentence, WrittenStory
from app.config.schemas import ModelsConfig
from app.config.settings import Settings
from app.llm.client import LlmClient
from app.models.enums import ImageProvider
from app.sources.fetch import Fetcher

pytestmark = pytest.mark.integration

PRIMARY = "https://primary.llm"
COMMONS_SEARCH_PATTERN = re.compile(rf"^{re.escape(COMMONS_API)}\?action=query&list=search.*")
COMMONS_INFO_PATTERN = re.compile(rf"^{re.escape(COMMONS_API)}\?action=query&titles=.*")
UNSPLASH_PATTERN = re.compile(rf"^{re.escape(UNSPLASH_SEARCH_API)}\?.*")
PEXELS_PATTERN = re.compile(rf"^{re.escape(PEXELS_SEARCH_API)}\?.*")


def fetcher() -> Fetcher:
    """No real sleeping: a failing test would otherwise pay full backoff."""
    clock = [0.0]
    return Fetcher(
        user_agent="TheMorningMosaic/0.1 (+test)",
        sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        monotonic=lambda: clock[0],
    )


def settings() -> Settings:
    return Settings.model_validate(
        {
            "base_url": "https://example.com",
            "database_url": "postgresql://u:p@localhost/db",
            "smtp_host": "smtp.example.com",
            "sender_email": "news@example.com",
            "sender_name": "Example",
            "gmail_app_password": "x",
            "imap_host": "imap.example.com",
            "admin_email": "admin@example.com",
            "llm_gateway_url": PRIMARY,
            "llm_gateway_api_key": "x",
            "token_signing_key": "x",
        }
    )


def models_config() -> ModelsConfig:
    spec = {"model": "img-1", "temperature": 0.0, "max_output_tokens": 256, "pinned": False}
    return ModelsConfig.model_validate(
        {
            "request_timeout_seconds": 5.0,
            "max_attempts": 1,
            "agents": {
                "orchestrator": spec,
                "ranker": spec,
                "writer": {**spec, "pinned": True},
                "fact_checker": {**spec, "pinned": True},
                "image_finder": spec,
            },
        }
    )


def llm() -> LlmClient:
    return LlmClient(settings=settings(), models=models_config(), sleep=lambda _: None)


def llm_picks(index: int | None) -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "c",
                "object": "chat.completion",
                "created": 0,
                "model": "img-1",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"index": index}),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
    )


def story(*, entity_tags: list[str] | None = None, headline: str = "Cricket final decided") -> Any:
    return WrittenStory(
        headline=DraftSentence(text=headline, passage_ids=["a1:p1"]),
        summary=[DraftSentence(text="It happened.", passage_ids=["a1:p1"])],
        entity_tags=entity_tags or [],
    )


def mock_empty_providers(*, unsplash: bool = True, pexels: bool = True) -> None:
    """A provider search that returns zero usable results, so tests exercise
    only the provider(s) they care about."""
    respx.get(COMMONS_SEARCH_PATTERN).mock(
        return_value=httpx.Response(200, json={"query": {"search": []}})
    )
    if unsplash:
        respx.get(UNSPLASH_PATTERN).mock(return_value=httpx.Response(200, json={"results": []}))
    if pexels:
        respx.get(PEXELS_PATTERN).mock(return_value=httpx.Response(200, json={"photos": []}))


@respx.mock
def test_a_relevant_wikimedia_candidate_is_chosen_and_credited() -> None:
    respx.get(COMMONS_SEARCH_PATTERN).mock(
        return_value=httpx.Response(
            200, json={"query": {"search": [{"title": "File:Cricket final.jpg"}]}}
        )
    )
    respx.get(COMMONS_INFO_PATTERN).mock(
        return_value=httpx.Response(
            200,
            json={
                "query": {
                    "pages": {
                        "1": {
                            "title": "File:Cricket final.jpg",
                            "imageinfo": [
                                {
                                    "url": "https://upload.wikimedia.org/cricket.jpg",
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Cricket_final.jpg",
                                    "width": 1200,
                                    "height": 800,
                                    "extmetadata": {
                                        "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                        "Artist": {"value": '<a href="#">Jane Doe</a>'},
                                        "LicenseUrl": {
                                            "value": "https://creativecommons.org/licenses/by-sa/4.0"
                                        },
                                        "ImageDescription": {
                                            "value": "A cricket final in progress"
                                        },
                                    },
                                }
                            ],
                        }
                    }
                }
            },
        )
    )
    respx.get(UNSPLASH_PATTERN).mock(return_value=httpx.Response(200, json={"results": []}))
    respx.get(PEXELS_PATTERN).mock(return_value=httpx.Response(200, json={"photos": []}))
    llm_picks(0)

    result = find_image(llm(), fetcher(), story=story(), unsplash_api_key="uk", pexels_api_key="pk")

    assert result is not None
    assert result.provider is ImageProvider.WIKIMEDIA
    assert result.display_url == "https://upload.wikimedia.org/cricket.jpg"
    assert result.author == "Jane Doe"
    assert result.credit == "Jane Doe / Wikimedia Commons (CC BY-SA 4.0)"


@respx.mock
def test_an_unlicensed_wikimedia_image_is_rejected() -> None:
    respx.get(COMMONS_SEARCH_PATTERN).mock(
        return_value=httpx.Response(
            200, json={"query": {"search": [{"title": "File:Restricted.jpg"}]}}
        )
    )
    respx.get(COMMONS_INFO_PATTERN).mock(
        return_value=httpx.Response(
            200,
            json={
                "query": {
                    "pages": {
                        "1": {
                            "title": "File:Restricted.jpg",
                            "imageinfo": [
                                {
                                    "url": "https://upload.wikimedia.org/restricted.jpg",
                                    "width": 800,
                                    "height": 600,
                                    "extmetadata": {
                                        "LicenseShortName": {"value": "All rights reserved"},
                                    },
                                }
                            ],
                        }
                    }
                }
            },
        )
    )
    respx.get(UNSPLASH_PATTERN).mock(return_value=httpx.Response(200, json={"results": []}))
    respx.get(PEXELS_PATTERN).mock(return_value=httpx.Response(200, json={"photos": []}))

    result = find_image(llm(), fetcher(), story=story(), unsplash_api_key="uk", pexels_api_key="pk")

    # No candidates survive licensing -> no LLM call was even needed/mocked.
    assert result is None


@respx.mock
def test_unsplash_candidate_is_chosen_and_pings_download_tracking() -> None:
    respx.get(COMMONS_SEARCH_PATTERN).mock(
        return_value=httpx.Response(200, json={"query": {"search": []}})
    )
    respx.get(UNSPLASH_PATTERN).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "urls": {"regular": "https://images.unsplash.com/cricket.jpg"},
                        "user": {"name": "Marcus W", "links": {"html": "https://unsplash.com/@m"}},
                        "alt_description": "Cricket players on a field",
                        "width": 1080,
                        "height": 720,
                        "links": {
                            "download_location": "https://api.unsplash.com/photos/x/download"
                        },
                    }
                ]
            },
        )
    )
    respx.get(PEXELS_PATTERN).mock(return_value=httpx.Response(200, json={"photos": []}))
    download_route = respx.get("https://api.unsplash.com/photos/x/download").mock(
        return_value=httpx.Response(200, json={})
    )
    llm_picks(0)

    result = find_image(llm(), fetcher(), story=story(), unsplash_api_key="uk", pexels_api_key="pk")

    assert result is not None
    assert result.provider is ImageProvider.UNSPLASH
    assert result.credit == "Photo by Marcus W on Unsplash"
    assert download_route.call_count == 1
    assert download_route.calls.last.request.headers["Authorization"] == "Client-ID uk"


@respx.mock
def test_pexels_candidate_is_chosen_and_credited() -> None:
    respx.get(COMMONS_SEARCH_PATTERN).mock(
        return_value=httpx.Response(200, json={"query": {"search": []}})
    )
    respx.get(UNSPLASH_PATTERN).mock(return_value=httpx.Response(200, json={"results": []}))
    respx.get(PEXELS_PATTERN).mock(
        return_value=httpx.Response(
            200,
            json={
                "photos": [
                    {
                        "src": {"large": "https://images.pexels.com/cricket.jpeg"},
                        "photographer": "Manoj Poosam",
                        "alt": "Close-up of a cricket ball",
                        "url": "https://www.pexels.com/photo/x",
                        "width": 4000,
                        "height": 6000,
                    }
                ]
            },
        )
    )
    llm_picks(0)

    result = find_image(llm(), fetcher(), story=story(), unsplash_api_key="uk", pexels_api_key="pk")

    assert result is not None
    assert result.provider is ImageProvider.PEXELS
    assert result.credit == "Photo by Manoj Poosam on Pexels"


@respx.mock
def test_no_candidates_from_any_provider_skips_the_llm_call() -> None:
    mock_empty_providers()
    llm_route = respx.post(f"{PRIMARY}/chat/completions")

    result = find_image(llm(), fetcher(), story=story(), unsplash_api_key="uk", pexels_api_key="pk")

    assert result is None
    assert llm_route.call_count == 0


@respx.mock
def test_the_model_saying_no_match_returns_none() -> None:
    respx.get(COMMONS_SEARCH_PATTERN).mock(
        return_value=httpx.Response(
            200, json={"query": {"search": [{"title": "File:Unrelated.jpg"}]}}
        )
    )
    respx.get(COMMONS_INFO_PATTERN).mock(
        return_value=httpx.Response(
            200,
            json={
                "query": {
                    "pages": {
                        "1": {
                            "title": "File:Unrelated.jpg",
                            "imageinfo": [
                                {
                                    "url": "https://upload.wikimedia.org/unrelated.jpg",
                                    "width": 100,
                                    "height": 100,
                                    "extmetadata": {
                                        "LicenseShortName": {"value": "CC0"},
                                        "ImageDescription": {"value": "A totally unrelated scene"},
                                    },
                                }
                            ],
                        }
                    }
                }
            },
        )
    )
    respx.get(UNSPLASH_PATTERN).mock(return_value=httpx.Response(200, json={"results": []}))
    respx.get(PEXELS_PATTERN).mock(return_value=httpx.Response(200, json={"photos": []}))
    llm_picks(None)

    result = find_image(llm(), fetcher(), story=story(), unsplash_api_key="uk", pexels_api_key="pk")

    assert result is None


@respx.mock
def test_a_failed_provider_does_not_block_the_others() -> None:
    respx.get(COMMONS_SEARCH_PATTERN).mock(return_value=httpx.Response(500))
    respx.get(UNSPLASH_PATTERN).mock(return_value=httpx.Response(200, json={"results": []}))
    respx.get(PEXELS_PATTERN).mock(
        return_value=httpx.Response(
            200,
            json={
                "photos": [
                    {
                        "src": {"large": "https://images.pexels.com/cricket.jpeg"},
                        "photographer": "Manoj Poosam",
                        "alt": "A cricket match",
                        "url": "https://www.pexels.com/photo/x",
                        "width": 4000,
                        "height": 6000,
                    }
                ]
            },
        )
    )
    llm_picks(0)

    result = find_image(llm(), fetcher(), story=story(), unsplash_api_key="uk", pexels_api_key="pk")

    assert result is not None
    assert result.provider is ImageProvider.PEXELS


@respx.mock
def test_a_story_with_no_entity_tags_searches_by_headline() -> None:
    route = respx.get(COMMONS_SEARCH_PATTERN).mock(
        return_value=httpx.Response(200, json={"query": {"search": []}})
    )
    mock_empty_providers()

    find_image(
        llm(),
        fetcher(),
        story=story(entity_tags=[], headline="Cricket final decided"),
        unsplash_api_key="uk",
        pexels_api_key="pk",
    )

    assert "Cricket" in route.calls.last.request.url.params["srsearch"]


@respx.mock
def test_entity_tags_are_preferred_over_the_headline_for_the_query() -> None:
    route = respx.get(COMMONS_SEARCH_PATTERN).mock(
        return_value=httpx.Response(200, json={"query": {"search": []}})
    )
    mock_empty_providers()

    find_image(
        llm(),
        fetcher(),
        story=story(entity_tags=["Virat Kohli"], headline="Something else entirely"),
        unsplash_api_key="uk",
        pexels_api_key="pk",
    )

    assert route.calls.last.request.url.params["srsearch"] == "Virat Kohli"


@respx.mock
def test_no_api_keys_still_tries_wikimedia_alone() -> None:
    respx.get(COMMONS_SEARCH_PATTERN).mock(
        return_value=httpx.Response(200, json={"query": {"search": []}})
    )

    result = find_image(llm(), fetcher(), story=story(), unsplash_api_key=None, pexels_api_key=None)

    assert result is None
