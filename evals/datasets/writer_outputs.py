"""Synthetic Writer-shaped text for the neutrality eval — samples of the
kind of sentence a politics story might publish, some neutral and some
deliberately loaded, so the heuristic's own accuracy can be checked."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NeutralityCase:
    name: str
    text: str
    expected_neutral: bool


_CASES: list[NeutralityCase] = [
    NeutralityCase(
        name="neutral-budget-summary",
        text=(
            "The finance minister presented the annual budget on Tuesday, "
            "proposing changes to income tax slabs and an increase in "
            "infrastructure spending. Opposition leaders said the changes did "
            "not go far enough to address unemployment."
        ),
        expected_neutral=True,
    ),
    NeutralityCase(
        name="neutral-bill-passage",
        text=(
            "Parliament passed the amendment after a debate lasting six hours. "
            "Members from both the ruling party and the opposition spoke, and "
            "the bill passed by a margin of 40 votes."
        ),
        expected_neutral=True,
    ),
    NeutralityCase(
        name="loaded-adjectives",
        text=(
            "The minister's shameful and disastrous handling of the crisis drew "
            "outrage, as critics called the policy a reckless betrayal of "
            "ordinary citizens."
        ),
        expected_neutral=False,
    ),
    NeutralityCase(
        name="loaded-praise",
        text=(
            "The party's brilliant strategy and heroic leadership delivered a "
            "landslide victory, crushing a hapless and incompetent opposition."
        ),
        expected_neutral=False,
    ),
]


def neutrality_cases() -> list[NeutralityCase]:
    return list(_CASES)
