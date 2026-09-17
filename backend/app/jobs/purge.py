"""Raw-article purge job — 03:00 IST, before feedback aggregation.

    uv run python -m app.jobs.purge [--older-than-days 30]

CLAUDE.md: "Raw article text is stored for internal processing only, never
published, and purged after 30 days (published sentences, cited passage
excerpts, and URLs are kept)." The audit trail lives in `SentenceCitation`'s
own frozen excerpts (app/models/content.py), never in `Article.raw_text`,
so clearing it here loses nothing the audit trail depends on — only the
now-unneeded full text an already-published or already-dropped article was
fetched with.

Also clears old `rate_limit_hits` rows (app/api/security.py): every window
is at most a few minutes, so nothing past a day is ever read again, and
without this the table would grow forever.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.clock import edition_date_for, now_utc
from app.config.settings import get_settings
from app.db.engine import dispose_engine, session_scope
from app.jobs.locking import job_lock
from app.logging_config import configure_logging
from app.models.content import Article
from app.models.enums import JobName, RunStatus
from app.models.operations import PipelineRun, RateLimitHit

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 30
RATE_LIMIT_HIT_RETENTION_DAYS = 1


@dataclass
class PurgeReport:
    purged: int = 0
    rate_limit_hits_cleared: int = 0


def run_purge(
    session: Session,
    *,
    now: datetime | None = None,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    rate_limit_hit_retention_days: int = RATE_LIMIT_HIT_RETENTION_DAYS,
) -> PurgeReport:
    started = now or now_utc()
    report = PurgeReport()

    run = PipelineRun(
        job=JobName.PURGE,
        edition_date=edition_date_for(started),
        status=RunStatus.RUNNING,
        started_at=started,
    )
    session.add(run)
    session.flush()

    cutoff = started - timedelta(days=retention_days)
    result = session.execute(
        update(Article)
        .where(Article.raw_text.is_not(None), Article.fetched_at < cutoff)
        .values(raw_text=None, raw_text_purged_at=started)
    )
    report.purged = cast(CursorResult[Any], result).rowcount

    rate_limit_cutoff = started - timedelta(days=rate_limit_hit_retention_days)
    rate_limit_result = session.execute(
        delete(RateLimitHit).where(RateLimitHit.window_start < rate_limit_cutoff)
    )
    report.rate_limit_hits_cleared = cast(CursorResult[Any], rate_limit_result).rowcount

    run.status = RunStatus.SUCCEEDED
    run.finished_at = now_utc()
    run.detail = {
        "purged": report.purged,
        "retention_days": retention_days,
        "rate_limit_hits_cleared": report.rate_limit_hits_cleared,
    }
    session.commit()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Purge raw article text past the retention window."
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help="purge raw text from articles fetched more than this many days ago",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)

    try:
        with job_lock(JobName.PURGE.value) as acquired:
            if not acquired:
                logger.warning("another purge run is in progress; exiting")
                return 0
            with session_scope() as session:
                report = run_purge(session, retention_days=args.older_than_days)
    finally:
        dispose_engine()

    print(f"purged={report.purged} rate_limit_hits_cleared={report.rate_limit_hits_cleared}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
