"""Structured JSON logging for jobs and the API.

Cloud Logging parses a Cloud Run container's stdout as structured data when
each line is a JSON object, so every entrypoint logs JSON to stdout instead
of plain text to stderr. This only changes how existing
`logging.getLogger(__name__)` call sites are rendered — structlog wraps the
stdlib root logger rather than replacing call sites one by one.
"""

from __future__ import annotations

import logging
import sys

import structlog

_SHARED_PROCESSORS: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]


def configure_logging(level: int | str = logging.INFO) -> None:
    """Route stdlib logging through structlog's JSON renderer, to stdout.

    Idempotent, so a job's `main()` and test setup can both call it without
    accumulating duplicate handlers on the root logger.
    """
    structlog.configure(
        processors=[*_SHARED_PROCESSORS, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=_SHARED_PROCESSORS,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
