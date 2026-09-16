"""Writer: the prompt asks for grounding, these checks enforce it."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx

from app.agents.schemas import Corroboration, PooledStory, WriterIssue
from app.agents.writer import Writer
from app.agents.writing import (
    build_passages,
    copying_violation,
    has_hedge,
    longest_shared_run,
    mentions_india,
    validate_draft,
)
from app.config.loader import load_genres
from app.config.schemas import ModelsConfig
from app.config.settings import Settings
from app.llm.client import LlmClient
from app.sources.schemas import CollectedArticle, Passage

PRIMARY = "https://primary.llm"
NOW = datetime(2026, 9, 17, 4, 30, tzinfo=UTC)

P1 = (
    "The union cabinet approved a new eastern freight rail corridor on Tuesday, "
    "clearing the way for construction to begin in the next financial year."
)
P2 = (
    "Officials said the corridor would run for roughly nine hundred kilometres and "
    "move coal away from passenger lines operating close to capacity."
)
ALLOWED = frozenset(load_genres().by_key()["india"].topic_tags)


def article(source: str, *passage_texts: str) -> CollectedArticle:
    body = " ".join(passage_texts)
    return CollectedArticle(
        source_key=source,
        genre="india",
        url=f"https://{source}.example/story",
        title="Cabinet clears eastern rail corridor",
        published_at=NOW,
        fetched_at=NOW,
        text=body,
        passages=[Passage(ordinal=i, text=t) for i, t in enumerate(passage_texts, start=1)],
        content_hash=f"h-{source}",
    )


def passages() -> dict[str, Any]:
    return build_passages([article("wire", P1, P2)])


def good_draft(**overrides: Any) -> dict[str, Any]:
    draft: dict[str, Any] = {
        "headline": {"text": "Cabinet signs off on eastern freight line", "passage_ids": ["a1:p1"]},
        "summary": [
            {
                "text": "Ministers cleared the project on Tuesday, with building work due to start in the coming financial year.",
                "passage_ids": ["a1:p1"],
            },
            {
                "text": "The route stretches about nine hundred kilometres and is meant to shift coal traffic off busy passenger tracks.",
                "passage_ids": ["a1:p2"],
            },
        ],
        "one_liner": {"text": "Eastern freight corridor approved", "passage_ids": ["a1:p1"]},
        "why_this_matters": [],
        "topic_tags": ["infrastructure"],
        "entity_tags": [],
    }
    draft.update(overrides)
    return draft


def validate(draft: Any, *, require_hedge: bool = False) -> Any:
    return validate_draft(
        draft,
        passages=passages(),
        allowed_topic_tags=ALLOWED,
        require_hedge=require_hedge,
    )


def issues(result: Any) -> set[WriterIssue]:
    return {problem.issue for problem in result.problems}


# ------------------------------------------------------------- happy path


def test_a_well_formed_draft_validates() -> None:
    result = validate(good_draft())
    assert result.story is not None
    assert result.story.headline.passage_ids == ["a1:p1"]
    assert len(result.story.summary) == 2


def test_passages_are_addressed_per_article() -> None:
    refs = build_passages([article("wire", P1, P2), article("daily", P1)])
    assert set(refs) == {"a1:p1", "a1:p2", "a2:p1"}
    assert refs["a2:p1"].source_key == "daily"


# ---------------------------------------------------------- citation rules


def test_a_sentence_with_no_citation_is_refused() -> None:
    draft = good_draft(headline={"text": "Something happened", "passage_ids": []})
    result = validate(draft)
    assert result.dropped
    assert WriterIssue.MISSING_CITATION in issues(result)


def test_an_invented_passage_id_is_refused() -> None:
    draft = good_draft(headline={"text": "Something happened", "passage_ids": ["a9:p9"]})
    result = validate(draft)
    assert result.dropped
    assert WriterIssue.UNKNOWN_CITATION in issues(result)


def test_a_citation_into_another_story_is_refused() -> None:
    """Ids are story-local, so a neighbouring story's passage is unknown here."""
    draft = good_draft(summary=[{"text": "Unrelated claim.", "passage_ids": ["a2:p1"]}])
    result = validate(draft)
    assert result.dropped
    assert WriterIssue.UNKNOWN_CITATION in issues(result)


# ------------------------------------------------------------- copied text


def test_a_copied_sentence_is_refused() -> None:
    draft = good_draft(summary=[{"text": P1, "passage_ids": ["a1:p1"]}])
    result = validate(draft)
    assert result.dropped
    assert WriterIssue.COPIED_TEXT in issues(result)


def test_a_short_attributed_quote_is_allowed() -> None:
    draft = good_draft(
        summary=[
            {
                "text": 'Ministers described it as a route to "move coal away from passenger lines".',
                "passage_ids": ["a1:p2"],
            }
        ]
    )
    assert validate(draft).story is not None


def test_a_whole_quoted_paragraph_is_still_refused() -> None:
    draft = good_draft(summary=[{"text": f'A spokesperson said "{P1}".', "passage_ids": ["a1:p1"]}])
    result = validate(draft)
    assert result.dropped
    assert WriterIssue.COPIED_TEXT in issues(result)


def test_shared_run_is_measured_in_words() -> None:
    assert longest_shared_run("the union cabinet approved", [P1]) == 4
    assert longest_shared_run("entirely unrelated wording here", [P1]) <= 1


def test_paraphrase_is_not_flagged() -> None:
    assert copying_violation("Ministers gave the rail plan the go-ahead.", [P1]) is None


# ------------------------------------------------------------------- tags


def test_a_tag_outside_the_taxonomy_is_dropped_but_the_story_survives() -> None:
    draft = good_draft(topic_tags=["infrastructure", "not-a-real-tag"])
    result = validate(draft)
    assert result.story is not None
    assert result.story.topic_tags == ["infrastructure"]
    assert WriterIssue.DROPPED_TOPIC_TAG in issues(result)


def test_an_entity_absent_from_the_passages_is_dropped() -> None:
    draft = good_draft(entity_tags=["Ministry of Invented Affairs"])
    result = validate(draft)
    assert result.story is not None
    assert result.story.entity_tags == []
    assert WriterIssue.DROPPED_ENTITY_TAG in issues(result)


def test_a_generic_phrase_is_dropped_even_when_it_appears_in_the_passages() -> None:
    """"union cabinet" is in P1 verbatim, but it is not a proper noun —
    accepting it would let real entity tags drown in noise like this."""
    draft = good_draft(entity_tags=["union cabinet"])
    result = validate(draft)
    assert result.story is not None
    assert result.story.entity_tags == []
    assert WriterIssue.DROPPED_ENTITY_TAG in issues(result)


def test_a_proper_noun_grounded_in_the_passages_is_kept() -> None:
    refs = build_passages([article("wire", "Minister Nitin Gadkari opened the corridor.")])
    result = validate_draft(
        {
            "headline": {"text": "Corridor opens to freight traffic", "passage_ids": ["a1:p1"]},
            "summary": [
                {"text": "Officials marked the opening on Tuesday.", "passage_ids": ["a1:p1"]}
            ],
            "entity_tags": ["Nitin Gadkari"],
        },
        passages=refs,
        allowed_topic_tags=ALLOWED,
        require_hedge=False,
    )
    assert result.story is not None
    assert result.story.entity_tags == ["Nitin Gadkari"]
    assert issues(result) == set()


# --------------------------------------------------------- optional pieces


def test_a_bad_one_liner_is_dropped_without_losing_the_story() -> None:
    draft = good_draft(one_liner={"text": "Approved", "passage_ids": ["a9:p9"]})
    result = validate(draft)
    assert result.story is not None
    assert result.story.one_liner is None
    assert WriterIssue.DROPPED_ONE_LINER in issues(result)


def test_a_bad_why_this_matters_is_dropped_without_losing_the_story() -> None:
    draft = good_draft(why_this_matters=[{"text": "It is important.", "passage_ids": []}])
    result = validate(draft)
    assert result.story is not None
    assert result.story.why_this_matters == []
    assert WriterIssue.DROPPED_WHY_THIS_MATTERS in issues(result)


def test_an_unusable_headline_drops_the_story() -> None:
    result = validate(good_draft(headline={"text": "", "passage_ids": ["a1:p1"]}))
    assert result.dropped
    assert WriterIssue.EMPTY_HEADLINE in issues(result)


def test_an_empty_summary_drops_the_story() -> None:
    result = validate(good_draft(summary=[]))
    assert result.dropped
    assert WriterIssue.EMPTY_SUMMARY in issues(result)


def test_unparseable_output_drops_the_story() -> None:
    result = validate("not an object")
    assert result.dropped
    assert WriterIssue.UNPARSEABLE in issues(result)


# ----------------------------------------------------------------- hedging


def test_a_tier3_story_without_hedging_is_refused() -> None:
    result = validate(good_draft(), require_hedge=True)
    assert result.dropped
    assert WriterIssue.MISSING_HEDGE in issues(result)


def test_a_tier3_story_with_hedging_passes() -> None:
    draft = good_draft(
        headline={"text": "Corridor reportedly cleared", "passage_ids": ["a1:p1"]},
    )
    result = validate(draft, require_hedge=True)
    assert result.story is not None
    assert result.story.hedged is True


def test_hedge_markers_are_recognised() -> None:
    assert has_hedge(["The deal was reportedly signed."])
    assert not has_hedge(["The deal was signed."])


# -------------------------------------------------------- india relevance


def test_india_relevance_comes_from_the_passages_not_the_model() -> None:
    draft = good_draft(india_relevance=True)  # model's claim is ignored
    result = validate(draft)
    assert result.story is not None
    # Neither passage names an Indian place or term.
    assert result.story.india_relevance is False


def test_an_indian_place_sets_india_relevance() -> None:
    refs = build_passages([article("wire", "The corridor will terminate near Kolkata.")])
    result = validate_draft(
        {
            "headline": {
                "text": "Freight line to reach the eastern coast",
                "passage_ids": ["a1:p1"],
            },
            "summary": [{"text": "The route ends close to the city.", "passage_ids": ["a1:p1"]}],
        },
        passages=refs,
        allowed_topic_tags=ALLOWED,
        require_hedge=False,
    )
    assert result.story is not None
    assert result.story.india_relevance is True


def test_india_terms_are_matched_on_word_boundaries() -> None:
    assert mentions_india(["The Reserve Bank of India said so."])
    assert not mentions_india(["A report from Indiana."])


# ------------------------------------------------------ the agent end to end


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
            "freellmpool_url": PRIMARY,
            "freellmpool_api_key": "x",
            "token_signing_key": "x",
        }
    )


def models_config() -> ModelsConfig:
    spec = {"model": "w-1", "temperature": 0.0, "max_output_tokens": 512, "pinned": False}
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


def writer() -> Writer:
    client = LlmClient(settings=settings(), models=models_config(), sleep=lambda _: None)
    return Writer(llm=client)


def pooled(corroboration: Corroboration = Corroboration.PRIMARY_OFFICIAL) -> PooledStory:
    return PooledStory(
        event_label="rail corridor",
        articles=[article("wire", P1, P2)],
        corroboration=corroboration,
        hedged=corroboration == Corroboration.TIER3_ONLY,
        score=5.0,
        rank=1,
    )


def mock_reply(content: Any) -> None:
    body = content if isinstance(content, str) else json.dumps(content)
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": body}},
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
    )


@respx.mock
def test_the_writer_returns_a_validated_story() -> None:
    mock_reply(good_draft())
    result = writer().write(pooled(), "india")
    assert result.story is not None
    assert result.story.topic_tags == ["infrastructure"]


@respx.mock
def test_the_prompt_never_carries_urls_or_source_names() -> None:
    mock_reply(good_draft())
    writer().write(pooled(), "india")

    sent = json.loads(respx.calls[0].request.content)
    prompt = " ".join(message["content"] for message in sent["messages"])
    assert "wire.example" not in prompt
    assert "https://" not in prompt


@respx.mock
def test_fenced_json_is_still_accepted() -> None:
    mock_reply("```json\n" + json.dumps(good_draft()) + "\n```")
    assert writer().write(pooled(), "india").story is not None


@respx.mock
def test_a_model_failure_drops_the_story_rather_than_inventing_one() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(return_value=httpx.Response(500))
    result = writer().write(pooled(), "india")
    assert result.dropped
    assert WriterIssue.UNPARSEABLE in issues(result)


@respx.mock
def test_fact_checker_feedback_is_passed_back_into_the_prompt() -> None:
    mock_reply(good_draft())
    writer().write(pooled(), "india", feedback="summary[1]: figure not supported")

    sent = json.loads(respx.calls[0].request.content)
    prompt = " ".join(message["content"] for message in sent["messages"])
    assert "figure not supported" in prompt


@respx.mock
def test_a_tier3_story_asks_the_model_to_hedge() -> None:
    mock_reply(good_draft())
    writer().write(pooled(Corroboration.TIER3_ONLY), "india")

    sent = json.loads(respx.calls[0].request.content)
    prompt = " ".join(message["content"] for message in sent["messages"])
    assert "reportedly" in prompt


def test_a_story_without_passages_is_refused() -> None:
    with pytest.raises(ValueError, match="at least 1 item"):
        PooledStory(
            event_label="x",
            articles=[],
            corroboration=Corroboration.SINGLE_SOURCE,
            hedged=False,
            score=1.0,
            rank=1,
        )
