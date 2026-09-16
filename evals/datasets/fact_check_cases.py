"""Planted-error cases for the fact-checker catch-rate eval.

CLAUDE.md's own list of planted-error categories: wrong figure, wrong day,
wrong person, invented fact, reversed meaning, unstated causation. Each
category appears once per base story, alongside a "control" — the
unmodified, fully-supported sentence — because a checker that flags
everything is exactly as useless as one that flags nothing.

Four categories (figure, date, person, a numeric invented fact) are, in
this project's design, deterministically catchable: `unsupported_facts`
compares numbers/dates/names in the sentence against the cited passages
directly, no model involved. The other three (a prose invented fact,
reversed meaning, unstated causation) carry no number/date/name marker for
code to compare — CLAUDE.md is explicit that "the model catches meaning the
regexes cannot" — so those three genuinely need the LLM claim-verdict step.
`requires_llm` records which is which; the eval runner uses it to report a
score for the deterministic tier even when the gateway is unreachable.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.schemas import DraftSentence, PassageRef, WrittenStory


@dataclass(frozen=True)
class FactCheckCase:
    name: str
    base_story: str
    error_type: str
    requires_llm: bool
    # False only for "control": every other case plants a real error.
    should_be_flagged: bool
    passage_text: str
    headline_text: str
    summary_text: str


_CASES: list[FactCheckCase] = [
    # ---------------------------------------------------------- business/RBI
    FactCheckCase(
        name="rbi-control",
        base_story="rbi",
        error_type="control",
        requires_llm=False,
        should_be_flagged=False,
        passage_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday. Governor Shaktikanta Das said inflation "
            "remained a concern."
        ),
        headline_text="Reserve Bank of India raises repo rate by 25 basis points",
        summary_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday, and Governor Shaktikanta Das said "
            "inflation remained a concern."
        ),
    ),
    FactCheckCase(
        name="rbi-wrong-figure",
        base_story="rbi",
        error_type="wrong_figure",
        requires_llm=False,
        should_be_flagged=True,
        passage_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday. Governor Shaktikanta Das said inflation "
            "remained a concern."
        ),
        headline_text="Reserve Bank of India raises repo rate by 25 basis points",
        summary_text=(
            "The Reserve Bank of India raised the repo rate by 50 basis points "
            "to 6.50 percent on Tuesday, and Governor Shaktikanta Das said "
            "inflation remained a concern."
        ),
    ),
    FactCheckCase(
        name="rbi-wrong-day",
        base_story="rbi",
        error_type="wrong_day",
        requires_llm=False,
        should_be_flagged=True,
        passage_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday. Governor Shaktikanta Das said inflation "
            "remained a concern."
        ),
        headline_text="Reserve Bank of India raises repo rate by 25 basis points",
        summary_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Wednesday, and Governor Shaktikanta Das said "
            "inflation remained a concern."
        ),
    ),
    FactCheckCase(
        name="rbi-wrong-person",
        base_story="rbi",
        error_type="wrong_person",
        requires_llm=False,
        should_be_flagged=True,
        passage_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday. Governor Shaktikanta Das said inflation "
            "remained a concern."
        ),
        headline_text="Reserve Bank of India raises repo rate by 25 basis points",
        summary_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday, and Governor Urjit Patel said inflation "
            "remained a concern."
        ),
    ),
    FactCheckCase(
        name="rbi-invented-fact-numeric",
        base_story="rbi",
        error_type="invented_fact_numeric",
        requires_llm=False,
        should_be_flagged=True,
        passage_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday. Governor Shaktikanta Das said inflation "
            "remained a concern."
        ),
        headline_text="Reserve Bank of India raises repo rate by 25 basis points",
        summary_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday and also cut the cash reserve ratio by "
            "15 basis points."
        ),
    ),
    FactCheckCase(
        name="rbi-invented-fact-prose",
        base_story="rbi",
        error_type="invented_fact_prose",
        requires_llm=True,
        should_be_flagged=True,
        passage_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday. Governor Shaktikanta Das said inflation "
            "remained a concern."
        ),
        headline_text="Reserve Bank of India raises repo rate by 25 basis points",
        summary_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday, a move markets had widely expected for "
            "months."
        ),
    ),
    FactCheckCase(
        name="rbi-reversed-meaning",
        base_story="rbi",
        error_type="reversed_meaning",
        requires_llm=True,
        should_be_flagged=True,
        passage_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday. Governor Shaktikanta Das said inflation "
            "remained a concern."
        ),
        headline_text="Reserve Bank of India raises repo rate by 25 basis points",
        summary_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday, and Governor Shaktikanta Das said "
            "inflation was no longer a concern."
        ),
    ),
    FactCheckCase(
        name="rbi-unstated-causation",
        base_story="rbi",
        error_type="unstated_causation",
        requires_llm=True,
        should_be_flagged=True,
        passage_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday. Governor Shaktikanta Das said inflation "
            "remained a concern."
        ),
        headline_text="Reserve Bank of India raises repo rate by 25 basis points",
        summary_text=(
            "The Reserve Bank of India raised the repo rate by 25 basis points "
            "to 6.50 percent on Tuesday, and Governor Shaktikanta Das said "
            "inflation remained a concern because of a surge in global oil "
            "prices."
        ),
    ),
    # ------------------------------------------------------- india/corridor
    FactCheckCase(
        name="corridor-control",
        base_story="corridor",
        error_type="control",
        requires_llm=False,
        should_be_flagged=False,
        passage_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday. Minister Ashwini "
            "Vaishnaw said the project would be completed by 2029."
        ),
        headline_text="Ministry of Railways clears 350 kilometre high speed corridor",
        summary_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday, and Minister "
            "Ashwini Vaishnaw said the project would be completed by 2029."
        ),
    ),
    FactCheckCase(
        name="corridor-wrong-figure",
        base_story="corridor",
        error_type="wrong_figure",
        requires_llm=False,
        should_be_flagged=True,
        passage_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday. Minister Ashwini "
            "Vaishnaw said the project would be completed by 2029."
        ),
        headline_text="Ministry of Railways clears 350 kilometre high speed corridor",
        summary_text=(
            "The Ministry of Railways cleared a 500 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday, and Minister "
            "Ashwini Vaishnaw said the project would be completed by 2029."
        ),
    ),
    FactCheckCase(
        name="corridor-wrong-day",
        base_story="corridor",
        error_type="wrong_day",
        requires_llm=False,
        should_be_flagged=True,
        passage_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday. Minister Ashwini "
            "Vaishnaw said the project would be completed by 2029."
        ),
        headline_text="Ministry of Railways clears 350 kilometre high speed corridor",
        summary_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Sunday, and Minister "
            "Ashwini Vaishnaw said the project would be completed by 2029."
        ),
    ),
    FactCheckCase(
        name="corridor-wrong-person",
        base_story="corridor",
        error_type="wrong_person",
        requires_llm=False,
        should_be_flagged=True,
        passage_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday. Minister Ashwini "
            "Vaishnaw said the project would be completed by 2029."
        ),
        headline_text="Ministry of Railways clears 350 kilometre high speed corridor",
        summary_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday, and Minister "
            "Piyush Goyal said the project would be completed by 2029."
        ),
    ),
    FactCheckCase(
        name="corridor-invented-fact-numeric",
        base_story="corridor",
        error_type="invented_fact_numeric",
        requires_llm=False,
        should_be_flagged=True,
        passage_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday. Minister Ashwini "
            "Vaishnaw said the project would be completed by 2029."
        ),
        headline_text="Ministry of Railways clears 350 kilometre high speed corridor",
        summary_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday, at a cost of "
            "40000 crore rupees."
        ),
    ),
    FactCheckCase(
        name="corridor-invented-fact-prose",
        base_story="corridor",
        error_type="invented_fact_prose",
        requires_llm=True,
        should_be_flagged=True,
        passage_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday. Minister Ashwini "
            "Vaishnaw said the project would be completed by 2029."
        ),
        headline_text="Ministry of Railways clears 350 kilometre high speed corridor",
        summary_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday, a route expected "
            "to boost tourism across both cities."
        ),
    ),
    FactCheckCase(
        name="corridor-reversed-meaning",
        base_story="corridor",
        error_type="reversed_meaning",
        requires_llm=True,
        should_be_flagged=True,
        passage_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday. Minister Ashwini "
            "Vaishnaw said the project would be completed by 2029."
        ),
        headline_text="Ministry of Railways clears 350 kilometre high speed corridor",
        summary_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday, and Minister "
            "Ashwini Vaishnaw said the project faced delays and would likely "
            "miss the 2029 deadline."
        ),
    ),
    FactCheckCase(
        name="corridor-unstated-causation",
        base_story="corridor",
        error_type="unstated_causation",
        requires_llm=True,
        should_be_flagged=True,
        passage_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday. Minister Ashwini "
            "Vaishnaw said the project would be completed by 2029."
        ),
        headline_text="Ministry of Railways clears 350 kilometre high speed corridor",
        summary_text=(
            "The Ministry of Railways cleared a 350 kilometre high speed "
            "corridor between Mumbai and Ahmedabad on Monday, and Minister "
            "Ashwini Vaishnaw said the project would be completed by 2029 "
            "thanks to strong political will."
        ),
    ),
]


def fact_check_cases() -> list[FactCheckCase]:
    return list(_CASES)


def build_story(case: FactCheckCase) -> tuple[WrittenStory, dict[str, PassageRef]]:
    """The WrittenStory and its citable passages, ready for FactChecker.check()."""
    passage = PassageRef(
        citation_id="a1:p1",
        article_index=0,
        source_key="synthetic",
        url="https://example.test/synthetic",
        text=case.passage_text,
    )
    story = WrittenStory(
        headline=DraftSentence(text=case.headline_text, passage_ids=["a1:p1"]),
        summary=[DraftSentence(text=case.summary_text, passage_ids=["a1:p1"])],
    )
    return story, {"a1:p1": passage}
