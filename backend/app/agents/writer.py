"""Agent 4 — Writer. The first agent whose output reaches a reader.

It sees passages and nothing else: no article URLs, no source names, no
outside context. Everything it returns is then checked in code against those
same passages (app/agents/writing.py), because the prompt can ask for
grounding but only the checks can guarantee it.

A story that fails the core checks is dropped rather than repaired. Per
CLAUDE.md: a missing item is acceptable, a wrong one is not.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from app.agents.schemas import (
    Corroboration,
    PassageRef,
    PooledStory,
    WriterIssue,
    WriterProblem,
    WriterResult,
)
from app.agents.writing import build_passages, validate_draft
from app.config.loader import load_genres
from app.config.schemas import GenreKey, GenresConfig
from app.llm.client import LlmClient, Message, is_outage, strip_json_fence
from app.llm.errors import LlmError
from app.llm.guard import redact_identifiers
from app.llm.prompts import writer_v1


class Writer:
    def __init__(self, *, llm: LlmClient, genres: GenresConfig | None = None) -> None:
        self._llm = llm
        self._genres = genres or load_genres()

    def write(
        self,
        story: PooledStory,
        genre: GenreKey,
        *,
        feedback: str | None = None,
    ) -> WriterResult:
        """Write one story. `feedback` carries a Fact-checker rejection back in."""
        passages = build_passages(story.articles)
        if not passages:
            return WriterResult(
                problems=[
                    WriterProblem(issue=WriterIssue.UNPARSEABLE, detail="story has no passages")
                ]
            )

        allowed = frozenset(self._genres.by_key()[genre].topic_tags)
        require_hedge = story.corroboration == Corroboration.TIER3_ONLY

        try:
            payload, model = self._draft(passages, allowed, require_hedge, feedback)
        except (LlmError, ValueError, TypeError) as exc:
            # An unreachable model is not bad output: it must not be retried as if a
            # rewrite could help (see write_and_verify), nor filed as unparseable.
            issue = WriterIssue.MODEL_UNAVAILABLE if is_outage(exc) else WriterIssue.UNPARSEABLE
            return WriterResult(
                problems=[WriterProblem(issue=issue, detail=f"{type(exc).__name__}: {exc}")]
            )

        return validate_draft(
            payload,
            passages=passages,
            allowed_topic_tags=allowed,
            require_hedge=require_hedge,
            model=model,
            prompt_version=writer_v1.VERSION,
        )

    def _draft(
        self,
        passages: Mapping[str, PassageRef],
        allowed_tags: frozenset[str],
        require_hedge: bool,
        feedback: str | None,
    ) -> tuple[object, str]:
        rendered = "\n".join(
            writer_v1.render_passage(citation_id, redact_identifiers(ref.text))
            for citation_id, ref in passages.items()
        )
        user = writer_v1.USER_TEMPLATE.format(
            topic_tags=", ".join(sorted(allowed_tags)),
            passages=rendered,
            hedge_note=writer_v1.HEDGE_NOTE if require_hedge else "",
        )
        if feedback:
            # A previous attempt failed verification; name the problem rather
            # than re-running the identical prompt and hoping.
            user += f"\n\nA previous attempt was rejected. Fix exactly this:\n{feedback}"

        result = self._llm.complete(
            "writer",
            [
                Message(role="system", content=writer_v1.SYSTEM),
                Message(role="user", content=user),
            ],
            json_object=True,
            prompt_version=writer_v1.VERSION,
        )
        # LlmClient itself already retried a malformed (unparseable)
        # response before returning it — see strip_json_fence's docstring in
        # app/llm/client.py.
        return json.loads(strip_json_fence(result.text)), result.model
