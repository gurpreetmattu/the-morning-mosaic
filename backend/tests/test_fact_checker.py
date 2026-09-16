"""Fact-checker: code catches invented figures, the model catches meaning."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import respx

from app.agents.checking import (
    dates_in,
    is_optional,
    names_in,
    numbers_in,
    story_elements,
    unsupported_facts,
)
from app.agents.fact_checker import FactChecker
from app.agents.schemas import (
    Corroboration,
    DraftSentence,
    PooledStory,
    WrittenStory,
)
from app.agents.verification import write_and_verify
from app.agents.writer import Writer
from app.agents.writing import build_passages
from app.config.schemas import ModelsConfig
from app.config.settings import Settings
from app.llm.client import LlmClient
from app.models.enums import CheckMethod, ClaimVerdict
from app.sources.schemas import CollectedArticle, Passage

PRIMARY = "https://primary.llm"
NOW = datetime(2026, 9, 17, 4, 30, tzinfo=UTC)

P1 = (
    "The Reserve Bank of India kept the repo rate unchanged at 6.5 percent on Friday, "
    "the fourth consecutive hold by the monetary policy committee."
)
P2 = "Governor Shaktikanta Das said retail inflation had eased but stayed above target."


def article() -> CollectedArticle:
    return CollectedArticle(
        source_key="wire",
        genre="business",
        url="https://wire.example/rbi",
        title="RBI holds repo rate",
        published_at=NOW,
        fetched_at=NOW,
        text=f"{P1} {P2}",
        passages=[Passage(ordinal=1, text=P1), Passage(ordinal=2, text=P2)],
        content_hash="h-wire",
    )


def passages() -> dict[str, Any]:
    return build_passages([article()])


def sentence(text: str, *ids: str) -> DraftSentence:
    return DraftSentence(text=text, passage_ids=list(ids))


def story(**overrides: Any) -> WrittenStory:
    base: dict[str, Any] = {
        "headline": sentence("RBI leaves its policy rate untouched", "a1:p1"),
        "summary": [sentence("The central bank held its rate on Friday.", "a1:p1")],
        "one_liner": sentence("Rate held again", "a1:p1"),
        "why_this_matters": [],
        "topic_tags": ["banking"],
        "entity_tags": [],
    }
    base.update(overrides)
    return WrittenStory.model_validate(base)


# ------------------------------------------------------- deterministic units


def test_digit_and_spelled_numbers_are_both_extracted() -> None:
    assert numbers_in("the rate is 6.5 percent") == {Decimal("6.5")}
    assert Decimal(900) in numbers_in("about nine hundred kilometres")


def test_indian_scales_are_understood() -> None:
    assert Decimal(20_000_000) in numbers_in("two crore rupees")
    assert Decimal(500_000) in numbers_in("five lakh applications")


def test_a_figure_written_as_digits_matches_a_spelled_passage() -> None:
    assert unsupported_facts("The line runs 900 km.", ["It runs nine hundred kilometres."]) == []


def test_an_invented_figure_is_caught() -> None:
    problems = unsupported_facts("The rate is 7.25 percent.", [P1])
    assert any("7.25" in problem for problem in problems)


def test_a_figure_present_in_the_passage_passes() -> None:
    assert unsupported_facts("The rate stayed at 6.5 percent.", [P1]) == []


def test_an_invented_date_is_caught() -> None:
    problems = unsupported_facts("The decision came on Monday.", [P1])
    assert any("Monday" in problem for problem in problems)


def test_a_date_present_in_the_passage_passes() -> None:
    assert unsupported_facts("The decision came on Friday.", [P1]) == []


def test_an_invented_name_is_caught() -> None:
    problems = unsupported_facts("Governor Raghuram Rajan spoke.", [P2])
    assert any("Rajan" in problem for problem in problems)


def test_a_name_present_in_the_passage_passes() -> None:
    assert unsupported_facts("Shaktikanta Das spoke about inflation.", [P2]) == []


def test_sentence_initial_words_are_not_treated_as_names() -> None:
    assert "The" not in names_in("The committee met.")


def test_date_and_name_extraction_basics() -> None:
    assert dates_in("on Friday in March") == {"friday", "march"}
    assert "Reserve Bank of India" in names_in("The Reserve Bank of India acted.")


def test_optional_elements_are_identified() -> None:
    assert is_optional("one_liner")
    assert is_optional("why_this_matters[0]")
    assert not is_optional("headline")
    assert not is_optional("summary[0]")


def test_every_published_sentence_is_labelled() -> None:
    labels = [label for label, _ in story_elements(story())]
    assert labels == ["headline", "summary[0]", "one_liner"]


# ---------------------------------------------------------------- the agent


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
    spec = {"model": "m", "temperature": 0.0, "max_output_tokens": 512, "pinned": False}
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


def client() -> LlmClient:
    return LlmClient(settings=settings(), models=models_config(), sleep=lambda _: None)


def reply(content: Any) -> httpx.Response:
    body = content if isinstance(content, str) else json.dumps(content)
    return httpx.Response(
        200,
        json={
            "choices": [{"index": 0, "message": {"role": "assistant", "content": body}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )


def verdicts(*items: tuple[str, str]) -> dict[str, Any]:
    return {
        "claims": [
            {"element": element, "claim": "c", "verdict": verdict, "detail": "d"}
            for element, verdict in items
        ]
    }


@respx.mock
def test_a_fully_supported_story_passes() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=reply(
            verdicts(
                ("headline", "supported"), ("summary[0]", "supported"), ("one_liner", "supported")
            )
        )
    )
    result = FactChecker(llm=client()).check(story(), passages())
    assert result.passed
    assert result.story is not None


@respx.mock
def test_an_unsupported_summary_drops_the_story_and_returns_feedback() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=reply(
            {
                "claims": [
                    {"element": "headline", "claim": "c", "verdict": "supported", "detail": ""},
                    {
                        "element": "summary[0]",
                        "claim": "the rate was cut",
                        "verdict": "unsupported",
                        "detail": "the passages say the rate was held, not cut",
                    },
                ]
            }
        )
    )
    result = FactChecker(llm=client()).check(story(), passages())
    assert result.story is None
    assert result.feedback is not None
    assert "summary[0]" in result.feedback
    assert "held, not cut" in result.feedback


@respx.mock
def test_a_partial_verdict_counts_as_a_failure() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=reply(verdicts(("headline", "partial")))
    )
    result = FactChecker(llm=client()).check(story(), passages())
    assert result.story is None


@respx.mock
def test_an_unsupported_optional_element_is_removed_not_fatal() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=reply(
            verdicts(
                ("headline", "supported"), ("summary[0]", "supported"), ("one_liner", "unsupported")
            )
        )
    )
    result = FactChecker(llm=client()).check(story(), passages())
    assert result.story is not None
    assert result.story.one_liner is None
    assert result.passed


@respx.mock
def test_why_this_matters_is_removed_when_unverified() -> None:
    subject = story(
        why_this_matters=[sentence("Economists expect further holds.", "a1:p1")],
    )
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=reply(
            verdicts(
                ("headline", "supported"),
                ("summary[0]", "supported"),
                ("one_liner", "supported"),
                ("why_this_matters[0]", "unsupported"),
            )
        )
    )
    result = FactChecker(llm=client()).check(subject, passages())
    assert result.story is not None
    assert result.story.why_this_matters == []


@respx.mock
def test_code_catches_a_figure_the_model_waved_through() -> None:
    """The whole reason numbers are checked in code as well."""
    subject = story(summary=[sentence("The rate is now 7.25 percent.", "a1:p1")])
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=reply(
            verdicts(
                ("headline", "supported"), ("summary[0]", "supported"), ("one_liner", "supported")
            )
        )
    )
    result = FactChecker(llm=client()).check(subject, passages())

    assert result.story is None
    deterministic = [f for f in result.findings if f.method is CheckMethod.DETERMINISTIC]
    assert any("7.25" in finding.detail for finding in deterministic)


@respx.mock
def test_an_unavailable_checker_fails_everything_rather_than_passing_it() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(return_value=httpx.Response(500))
    result = FactChecker(llm=client()).check(story(), passages())

    assert result.story is None
    assert all(f.verdict is ClaimVerdict.UNSUPPORTED for f in result.failures())


@respx.mock
def test_a_verdict_about_an_unknown_element_is_ignored() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=reply(
            verdicts(
                ("headline", "supported"),
                ("summary[0]", "supported"),
                ("one_liner", "supported"),
                ("summary[9]", "unsupported"),
            )
        )
    )
    result = FactChecker(llm=client()).check(story(), passages())
    assert result.passed


@respx.mock
def test_an_unrecognised_verdict_is_not_a_pass() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        return_value=reply(verdicts(("headline", "looks fine to me")))
    )
    assert FactChecker(llm=client()).check(story(), passages()).story is None


# ------------------------------------------------------------- the loop


def pooled() -> PooledStory:
    return PooledStory(
        event_label="rbi",
        articles=[article()],
        corroboration=Corroboration.PRIMARY_OFFICIAL,
        hedged=False,
        score=5.0,
        rank=1,
    )


GOOD_DRAFT = {
    "headline": {"text": "RBI leaves its policy rate untouched", "passage_ids": ["a1:p1"]},
    "summary": [{"text": "The central bank held its rate on Friday.", "passage_ids": ["a1:p1"]}],
    "one_liner": {"text": "Rate held again", "passage_ids": ["a1:p1"]},
    "why_this_matters": [],
    "topic_tags": ["banking"],
    "entity_tags": [],
}

ALL_SUPPORTED = verdicts(
    ("headline", "supported"), ("summary[0]", "supported"), ("one_liner", "supported")
)


@respx.mock
def test_the_loop_returns_on_the_first_clean_pass() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        side_effect=[reply(GOOD_DRAFT), reply(ALL_SUPPORTED)]
    )
    shared = client()
    outcome = write_and_verify(
        writer=Writer(llm=shared),
        checker=FactChecker(llm=shared),
        pooled=pooled(),
        genre="business",
    )
    assert outcome.verified is not None
    assert outcome.attempts == 1


@respx.mock
def test_the_loop_retries_with_the_checkers_own_wording() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        side_effect=[
            reply(GOOD_DRAFT),
            reply(
                {
                    "claims": [
                        {
                            "element": "summary[0]",
                            "claim": "c",
                            "verdict": "unsupported",
                            "detail": "the passages do not mention a cut",
                        }
                    ]
                }
            ),
            reply(GOOD_DRAFT),
            reply(ALL_SUPPORTED),
        ]
    )
    shared = client()
    outcome = write_and_verify(
        writer=Writer(llm=shared),
        checker=FactChecker(llm=shared),
        pooled=pooled(),
        genre="business",
    )

    assert outcome.verified is not None
    assert outcome.attempts == 2
    retry_prompt = json.loads(respx.calls[2].request.content)["messages"][1]["content"]
    assert "do not mention a cut" in retry_prompt


@respx.mock
def test_the_loop_gives_up_after_two_retries() -> None:
    respx.post(f"{PRIMARY}/chat/completions").mock(
        side_effect=[
            reply(GOOD_DRAFT),
            reply(verdicts(("summary[0]", "unsupported"))),
            reply(GOOD_DRAFT),
            reply(verdicts(("summary[0]", "unsupported"))),
            reply(GOOD_DRAFT),
            reply(verdicts(("summary[0]", "unsupported"))),
        ]
    )
    shared = client()
    outcome = write_and_verify(
        writer=Writer(llm=shared),
        checker=FactChecker(llm=shared),
        pooled=pooled(),
        genre="business",
    )

    assert outcome.verified is None
    assert outcome.attempts == 3  # one attempt plus two retries
    assert outcome.reason is not None
