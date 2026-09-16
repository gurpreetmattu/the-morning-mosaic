"""Tag accuracy: how many of the model's proposed tags survive grounding.

`validate_draft` (app/agents/writing.py) already enforces both rules on
every real story — a topic tag must be in the genre's fixed taxonomy, an
entity tag must appear in the cited passages — so a `WrittenStory` can
never carry an invalid tag by construction. What's worth measuring isn't
whether the enforcement works (that has its own unit tests); it's how
often the *model's proposals* need it: a low survival rate means the
prompt is inviting tags it shouldn't, even though nothing wrong ever
reaches a reader.

Needs a live Writer call; skipped when the gateway is unreachable.
"""

from __future__ import annotations

from app.agents.writer import Writer
from app.llm.client import LlmClient
from evals.datasets.pooled_stories import pooled_stories
from evals.schemas import CaseResult, EvalResult, EvalStatus

THRESHOLD = 0.8

_DROPPED_TAG_ISSUES = {"dropped_topic_tag", "dropped_entity_tag"}


def run(llm: LlmClient) -> EvalResult:
    writer = Writer(llm=llm)

    cases: list[CaseResult] = []
    survived = 0
    proposed = 0

    for genre, story in pooled_stories():
        result = writer.write(story, genre)
        dropped = [p for p in result.problems if p.issue.value in _DROPPED_TAG_ISSUES]

        if result.story is not None:
            kept = len(result.story.topic_tags) + len(result.story.entity_tags)
        else:
            kept = 0

        case_proposed = kept + len(dropped)
        proposed += case_proposed
        survived += kept

        cases.append(
            CaseResult(
                name=story.event_label,
                passed=case_proposed == 0 or kept / case_proposed >= THRESHOLD,
                detail=(
                    f"{kept}/{case_proposed} proposed tags kept; "
                    f"dropped: {[d.detail for d in dropped]}"
                ),
            )
        )

    if proposed == 0:
        return EvalResult(
            name="tag_accuracy",
            status=EvalStatus.FAILED,
            score=0.0,
            threshold=THRESHOLD,
            detail="no tags were proposed to score",
            cases=cases,
        )

    score = survived / proposed
    return EvalResult(
        name="tag_accuracy",
        status=EvalStatus.PASSED if score >= THRESHOLD else EvalStatus.FAILED,
        score=score,
        threshold=THRESHOLD,
        detail=f"{survived}/{proposed} proposed tags survived taxonomy/grounding checks",
        cases=cases,
    )
