"""Agent 5 — Fact-checker. Model plus deterministic code.

Two independent checks run over the same written story:

- code compares every number, date and name in a sentence against the exact
  passages that sentence cited;
- the model splits each sentence into atomic claims and judges each one.

Either can fail a sentence. They are independent on purpose: the model catches
meaning the regexes cannot, and the code catches invented figures the model
will wave through.

A failed headline or summary sentence drops the story. A failed optional
element is removed and the story survives.
"""

from __future__ import annotations

import json

from app.agents.checking import is_optional, story_elements, unsupported_facts
from app.agents.schemas import (
    CheckFinding,
    CheckResult,
    DraftSentence,
    PassageRef,
    WrittenStory,
)
from app.llm.client import LlmClient, Message, is_outage, strip_json_fence
from app.llm.errors import LlmError
from app.llm.guard import redact_identifiers
from app.llm.prompts import fact_checker_v1
from app.models.enums import CheckMethod, ClaimVerdict


class FactChecker:
    def __init__(self, *, llm: LlmClient) -> None:
        self._llm = llm

    def check(self, story: WrittenStory, passages: dict[str, PassageRef]) -> CheckResult:
        texts = {citation_id: ref.text for citation_id, ref in passages.items()}
        elements = story_elements(story)

        findings = self._deterministic(elements, texts)
        model_findings, unavailable = self._model_claims(elements, passages)
        findings += model_findings

        if unavailable:
            # Nothing was judged, so the story still fails closed. But the story is not
            # at fault and a rewrite cannot make the model answer: say so explicitly,
            # so the retry loop stops instead of burning Writer and checker calls.
            return CheckResult(
                story=None, findings=findings, feedback=_feedback(findings), unavailable=True
            )

        failed = {finding.element for finding in findings if finding.failed}
        fatal = {element for element in failed if not is_optional(element)}

        if fatal:
            return CheckResult(
                story=None,
                findings=findings,
                feedback=_feedback(findings),
            )

        if failed:
            # Optional elements only: strip them and keep the story.
            return CheckResult(
                story=_without(story, failed),
                findings=findings,
                feedback=None,
            )

        return CheckResult(story=story, findings=findings, feedback=None)

    # ------------------------------------------------------------ code checks

    def _deterministic(
        self,
        elements: list[tuple[str, DraftSentence]],
        texts: dict[str, str],
    ) -> list[CheckFinding]:
        findings: list[CheckFinding] = []
        for element, sentence in elements:
            cited = [texts[pid] for pid in sentence.passage_ids if pid in texts]
            # The headline is Title Case by convention, not a signal of
            # real proper nouns — see unsupported_facts' own docstring.
            check_names = element != "headline"
            for problem in unsupported_facts(sentence.text, cited, check_names=check_names):
                findings.append(
                    CheckFinding(
                        element=element,
                        claim=sentence.text,
                        verdict=ClaimVerdict.UNSUPPORTED,
                        method=CheckMethod.DETERMINISTIC,
                        detail=problem,
                    )
                )
        return findings

    # ----------------------------------------------------------- model checks

    def _model_claims(
        self,
        elements: list[tuple[str, DraftSentence]],
        passages: dict[str, PassageRef],
    ) -> tuple[list[CheckFinding], bool]:
        """The model's verdicts, and whether the model could not run at all."""
        rendered_passages = "\n".join(
            fact_checker_v1.render_passage(citation_id, redact_identifiers(ref.text))
            for citation_id, ref in passages.items()
        )
        rendered_sentences = "\n".join(
            fact_checker_v1.render_sentence(
                element, redact_identifiers(sentence.text), sentence.passage_ids
            )
            for element, sentence in elements
        )

        try:
            result = self._llm.complete(
                "fact_checker",
                [
                    Message(role="system", content=fact_checker_v1.SYSTEM),
                    Message(
                        role="user",
                        content=fact_checker_v1.USER_TEMPLATE.format(
                            passages=rendered_passages, sentences=rendered_sentences
                        ),
                    ),
                ],
                json_object=True,
                prompt_version=fact_checker_v1.VERSION,
            )
            # LlmClient itself already retried a malformed (unparseable)
            # response before returning it (see strip_json_fence's docstring
            # in app/llm/client.py) — what's left to catch here is either a
            # real LlmError (every route/attempt exhausted) or a
            # syntactically valid but wrongly-shaped payload (no "claims"
            # key, wrong types), which is not something a retry would fix.
            payload = json.loads(strip_json_fence(result.text))
            claims = payload["claims"]
        except (LlmError, ValueError, KeyError, TypeError) as exc:
            # The checker is the safety net. If it cannot run, nothing is
            # verified, so every element fails rather than passing by default.
            return (
                [
                    CheckFinding(
                        element=element,
                        claim=sentence.text,
                        verdict=ClaimVerdict.UNSUPPORTED,
                        method=CheckMethod.LLM,
                        detail=f"verification unavailable: {type(exc).__name__}",
                    )
                    for element, sentence in elements
                ],
                is_outage(exc),
            )

        known = {element for element, _ in elements}
        findings: list[CheckFinding] = []
        for claim in claims:
            element = str(claim.get("element", ""))
            if element not in known:
                # A verdict about a sentence we did not send cannot be acted on.
                continue
            findings.append(
                CheckFinding(
                    element=element,
                    claim=str(claim.get("claim", ""))[:500],
                    verdict=_verdict(claim.get("verdict")),
                    method=CheckMethod.LLM,
                    detail=str(claim.get("detail", ""))[:300],
                )
            )
        return findings, False


def _verdict(raw: object) -> ClaimVerdict:
    try:
        return ClaimVerdict(str(raw).strip().lower())
    except ValueError:
        # An unrecognised verdict is not a pass.
        return ClaimVerdict.UNSUPPORTED


def _without(story: WrittenStory, failed: set[str]) -> WrittenStory:
    keep_why = [
        sentence
        for index, sentence in enumerate(story.why_this_matters)
        if f"why_this_matters[{index}]" not in failed
    ]
    return story.model_copy(
        update={
            "one_liner": None if "one_liner" in failed else story.one_liner,
            "why_this_matters": keep_why,
        }
    )


def _feedback(findings: list[CheckFinding]) -> str:
    lines = [
        f"- {finding.element}: {finding.detail or finding.verdict.value}"
        for finding in findings
        if finding.failed
    ]
    return "\n".join(lines)
