"""Feedback aggregation job — 04:00 IST, before the build.

    uv run python -m app.jobs.feedback

Folds thumbs up and down into per-reader topic preferences, which the delivery
job then uses to order each reader's sections.

Two properties matter more than the arithmetic:

- **Scores are bounded.** Selection multiplies a preference by a weight and
  adds it to the story's rank, and a followed keyword is worth 100. An
  unbounded sum would let fifty cricket votes swamp a keyword the reader
  explicitly asked for, so scores saturate at five in either direction.
- **Scores decay.** Without decay a single thumbs-down in 2026 would suppress
  that topic forever. Each run nudges every preference toward zero, so tastes
  that stop being reinforced fade instead of hardening.

Aggregation is idempotent: feedback is stamped once folded in, so a rerun on
the same morning does not count a vote twice.
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import edition_date_for, now_utc
from app.config.settings import get_settings
from app.db.engine import dispose_engine, session_scope
from app.jobs.locking import job_lock
from app.logging_config import configure_logging
from app.models.content import Story, StoryTag
from app.models.editions import Feedback
from app.models.enums import JobName, RunStatus, TagKind, Vote
from app.models.operations import PipelineRun
from app.models.users import UserPreference

logger = logging.getLogger(__name__)

VOTE_DELTA = {Vote.UP: 1.0, Vote.DOWN: -1.0}
# Selection weights a preference by 2 and a followed keyword by 100, so five
# keeps even a saturated topic well below something the reader asked for.
SCORE_CAP = 5.0
# Applied once per elapsed calendar day (see apply_decay), not once per
# call: a manual rerun on the same day must not decay a preference twice,
# and a day the job never ran must not skip decaying it. A saturated score
# falls to about half in a month without reinforcement.
DECAY = 0.98
# Below this a preference is indistinguishable from none; the row is removed
# rather than kept forever at 0.0001.
PRUNE_BELOW = 0.05


@dataclass
class FeedbackReport:
    processed: int = 0
    updated: int = 0
    anonymised_skipped: int = 0
    decayed: int = 0
    pruned: int = 0


def clamp(score: float) -> float:
    return max(-SCORE_CAP, min(SCORE_CAP, score))


def _elapsed_days(last_decayed_at: datetime | None, now: datetime) -> int:
    """Calendar days (IST) since a preference last decayed.

    A preference that has never decayed is treated as one day overdue,
    rather than as zero — the conservative, one-time choice for a row that
    predates `last_decayed_at` existing at all.
    """
    if last_decayed_at is None:
        return 1
    return max(0, (edition_date_for(now) - edition_date_for(last_decayed_at)).days)


def apply_decay(session: Session, *, now: datetime) -> tuple[int, int]:
    """Nudge every preference toward zero, once per elapsed day since it last
    decayed rather than once per call. Returns (decayed, pruned)."""
    preferences = list(session.scalars(select(UserPreference)))
    decayed = [p for p in preferences if _elapsed_days(p.last_decayed_at, now) > 0]
    for preference in decayed:
        days = _elapsed_days(preference.last_decayed_at, now)
        preference.score *= DECAY**days
        preference.last_decayed_at = now

    faded = [p for p in preferences if abs(p.score) < PRUNE_BELOW]
    for preference in faded:
        session.delete(preference)

    session.flush()
    return len(decayed), len(faded)


def run_feedback(session: Session, *, now: datetime | None = None) -> FeedbackReport:
    started = now or now_utc()
    report = FeedbackReport()

    run = PipelineRun(
        job=JobName.FEEDBACK,
        edition_date=edition_date_for(started),
        status=RunStatus.RUNNING,
        started_at=started,
    )
    session.add(run)
    session.commit()

    # Decay first, so a vote cast today is not immediately discounted.
    report.decayed, report.pruned = apply_decay(session, now=started)

    pending = list(
        session.scalars(
            select(Feedback).where(Feedback.aggregated_at.is_(None)).order_by(Feedback.created_at)
        )
    )

    for feedback in pending:
        report.processed += 1
        # Stamp first: even a vote we cannot attribute must not be re-read.
        feedback.aggregated_at = started

        if feedback.user_id is None:
            # The reader exercised their deletion right; the vote is anonymous
            # now and belongs to nobody's preferences.
            report.anonymised_skipped += 1
            continue

        story = session.get(Story, feedback.story_id)
        if story is None:
            continue

        for tag in _topic_tags(session, feedback.story_id):
            _adjust(
                session,
                user_id=feedback.user_id,
                genre=story.genre,
                tag=tag,
                delta=VOTE_DELTA[feedback.vote],
                now=started,
            )
            report.updated += 1

    _finish(run, report)
    session.commit()
    return report


def _topic_tags(session: Session, story_id: uuid.UUID) -> list[str]:
    """Only topic tags. Entity tags name people and places, which are not
    tastes: liking one story about a company is not liking that company."""
    return list(
        session.scalars(
            select(StoryTag.value).where(
                StoryTag.story_id == story_id, StoryTag.kind == TagKind.TOPIC
            )
        )
    )


def _adjust(
    session: Session, *, user_id: uuid.UUID, genre: str, tag: str, delta: float, now: datetime
) -> None:
    preference = session.scalar(
        select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.genre == genre,
            UserPreference.topic_tag == tag,
        )
    )
    if preference is None:
        # Freshly created, so not decayed again today (see _elapsed_days).
        session.add(
            UserPreference(
                user_id=user_id,
                genre=genre,
                topic_tag=tag,
                score=clamp(delta),
                last_decayed_at=now,
            )
        )
        session.flush()
        return

    preference.score = clamp(preference.score + delta)


def _finish(run: PipelineRun, report: FeedbackReport) -> None:
    run.status = RunStatus.SUCCEEDED
    run.finished_at = now_utc()
    run.detail = {
        "processed": report.processed,
        "updated": report.updated,
        "anonymised_skipped": report.anonymised_skipped,
        "decayed": report.decayed,
        "pruned": report.pruned,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fold feedback into topic preferences.")
    parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)

    try:
        with job_lock(JobName.FEEDBACK.value) as acquired:
            if not acquired:
                logger.warning("another feedback run is in progress; exiting")
                return 0
            with session_scope() as session:
                report = run_feedback(session)
    finally:
        dispose_engine()

    print(
        f"processed={report.processed} updated={report.updated} "
        f"anonymised={report.anonymised_skipped} decayed={report.decayed} "
        f"pruned={report.pruned}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
