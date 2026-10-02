"""Small, pure helpers that turn what each pipeline step already knows into the
counts saved in `GenreDiagnostics`. No I/O, no model calls."""

from __future__ import annotations

import re
from collections import Counter

from app.agents.schemas import GenreDiagnostics, StoryPool
from app.sources.schemas import CollectionResult

# Writer problems arrive as "- <issue>: <detail>" lines (write_and_verify).
_WRITER_LINE = re.compile(r"^- ([a-z_]+):", re.MULTILINE)
UNAVAILABLE_MARKER = "verification unavailable"
# The Writer reports a failed model call as an "unparseable" problem whose detail
# starts with the error class ("LlmHttpError: HTTP 429 ..."); only an HTTP-level
# error means the model could not be reached or refused (quota, 5xx).
_WRITER_OUTAGE = re.compile(r"LlmHttpError|LlmUnavailableError")


def categorize_abandon(reason: str | None) -> str:
    """A short, stable key for why a story was given up on.

    `checker_unavailable` and `writer_unavailable` mean a model could not run
    (quota, outage), which says nothing about the story; `claims_unsupported`
    means the checker ran and rejected claims; `writer:<issue>` is the Writer's
    output being rejected on its merits before the checker was even called.
    """
    if not reason:
        return "no_reason"
    lowered = reason.lower()
    if UNAVAILABLE_MARKER in lowered:
        return "checker_unavailable"
    if _WRITER_OUTAGE.search(reason):
        return "writer_unavailable"
    writer_issue = _WRITER_LINE.search(reason)
    if writer_issue:
        return f"writer:{writer_issue.group(1)}"
    return "claims_unsupported"


def with_collection(diagnostics: GenreDiagnostics, collected: CollectionResult) -> GenreDiagnostics:
    by_source = Counter(article.source_key for article in collected.articles)
    drops = {str(reason): count for reason, count in collected.reason_counts().items()}
    return diagnostics.model_copy(
        update={
            "collected": len(collected.articles),
            "articles_by_source": dict(sorted(by_source.items())),
            "collector_drops": dict(sorted(drops.items())),
        }
    )


def with_pool(diagnostics: GenreDiagnostics, pool: StoryPool) -> GenreDiagnostics:
    drops = Counter(str(dropped.reason) for dropped in pool.dropped)
    return diagnostics.model_copy(
        update={
            "clusters": len(pool.stories) + len(pool.dropped),
            "used_fallback_clustering": pool.used_fallback_clustering,
            "requested_more_coverage": pool.requested_more_coverage,
            "pooled": len(pool.stories),
            "pool_drops": dict(sorted(drops.items())),
        }
    )
