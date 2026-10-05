"""Late update job — 05:35 (deadline 05:55) and 07:05 (deadline 07:25) IST.

    uv run python -m app.jobs.late_update [--deadline-minutes 20]

Re-collects, re-verifies, and publishes a *new* revision carrying stories that
broke after the build. Three rules govern it:

- **It never publishes the first revision.** If the build produced nothing,
  this is not the job to paper over it; the admin alert and the failure-notice
  path exist for that.
- **Published revisions are never mutated.** New stories are appended to the
  day, not swapped in, because readers have already received the earlier ones
  and the audit trail must still explain what they read. Sections that did not
  change are carried forward byte for byte.
- **Missing the deadline publishes nothing.** Everything is assembled first
  and the clock is checked immediately before publishing, so a late run leaves
  the morning exactly as it found it rather than half-updating it.
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.clock import edition_date_for, now_utc
from app.config.schemas import GenreKey
from app.config.settings import get_settings
from app.db.engine import dispose_engine, session_scope
from app.db.persist import persist_new_stories
from app.db.publish import PublishError, latest_revision, publish_revision
from app.jobs.build import build_orchestrator
from app.jobs.locking import job_lock
from app.jobs.runs import fail_run
from app.llm.client import LlmClient
from app.llm.langfuse_recorder import build_call_recorder
from app.logging_config import configure_logging
from app.models.editions import Edition, EditionSection
from app.models.enums import JobName, RevisionReason, RunStatus, SectionStatus
from app.models.operations import PipelineRun
from app.render.sections import RenderedSection, SectionRenderer
from app.render.selection import load_candidates
from app.sources.fetch import Fetcher, user_agent_for

logger = logging.getLogger(__name__)

# The tighter of the two windows is 07:05 to 07:25.
DEFAULT_WINDOW_MINUTES = 20


@dataclass
class LateUpdateReport:
    edition_date: date
    published_revision: int | None = None
    new_stories: int = 0
    changed: list[str] = field(default_factory=list)
    carried_forward: list[str] = field(default_factory=list)
    reason: str | None = None
    # Why each genre came out as it did (GenreDiagnostics, as plain JSON).
    genre_diagnostics: dict[str, dict[str, object]] = field(default_factory=dict)

    @property
    def published(self) -> bool:
        return self.published_revision is not None


def run_late_update(
    session: Session,
    *,
    edition_date: date,
    deadline: datetime,
    orchestrator: Orchestrator,
    renderer: SectionRenderer,
    genres: list[GenreKey] | None = None,
    now: datetime | None = None,
    clock: Callable[[], datetime] = now_utc,
    run_id: uuid.UUID | None = None,
) -> LateUpdateReport:
    """Run and publish one late update. `run_id`, when given, becomes the
    committed `PipelineRun` id — needed before any LLM call so the recorder's
    own session can reference it (see `main()` and `app/jobs/build.py`)."""
    started = now or clock()
    report = LateUpdateReport(edition_date=edition_date)

    run = PipelineRun(
        id=run_id or uuid.uuid4(),
        job=JobName.LATE_UPDATE,
        edition_date=edition_date,
        status=RunStatus.RUNNING,
        started_at=started,
        deadline_at=deadline,
    )
    session.add(run)
    session.commit()

    previous = latest_revision(session, edition_date)
    if previous is None:
        # The build failed. Publishing a first revision here would dodge the
        # alerting and the failure-notice path that exist for exactly that.
        report.reason = "no published revision to update"
        _finish(run, RunStatus.FAILED, report)
        session.commit()
        return report

    edition = session.get(Edition, previous.edition_id)
    assert edition is not None
    # End the transaction the reads above opened BEFORE the minutes-long LLM phase.
    # Otherwise the session sits idle-in-transaction for the whole phase and Neon kills
    # the connection once it passes its limit (~6 min): the 2026-10-05 05:35 run took
    # 7 min and crashed at the first write after it. `previous` and `edition` stay
    # usable after the commit (expire_on_commit=False).
    session.commit()

    build = orchestrator.build(
        edition_date=edition_date, deadline=deadline, genres=genres, now=started
    )
    report.genre_diagnostics = {
        outcome.genre: outcome.diagnostics.model_dump(mode="json") for outcome in build.genres
    }

    for outcome in build.genres:
        if outcome.status is not SectionStatus.OK:
            continue
        added = persist_new_stories(session, edition_date=edition_date, outcome=outcome)
        if added:
            report.new_stories += len(added)
            report.changed.append(outcome.genre)

    if not report.changed:
        # A revision identical to the last one would give readers a second PDF
        # link for the same edition and tell them nothing.
        report.reason = "nothing new since the last revision"
        session.rollback()
        _finish(run, RunStatus.SUCCEEDED, report)
        session.commit()
        return report

    sections = _assemble(
        session,
        previous_revision_id=previous.id,
        edition_date=edition_date,
        changed=report.changed,
        renderer=renderer,
        report=report,
    )

    # Checked last, with everything already assembled and nothing committed.
    if clock() >= deadline:
        session.rollback()
        report.reason = "deadline passed before publishing; nothing was changed"
        report.new_stories = 0
        report.changed = []
        report.carried_forward = []
        # Same greppable message convention as app/jobs/build.py's own
        # deadline-miss log — infra/monitoring.tf's log-based metric matches
        # either job's log stream on this literal.
        logger.warning(
            "build_deadline_missed edition_date=%s deadline=%s",
            edition_date.isoformat(),
            deadline.isoformat(),
        )
        _finish(run, RunStatus.DEADLINE_MISSED, report)
        session.commit()
        return report

    try:
        revision = publish_revision(
            session,
            build=build.model_copy(
                update={
                    # Revisions share the edition's number and flags.
                    "edition_number": edition.edition_number,
                    "special_edition_key": edition.special_edition_key,
                    "is_weekend": edition.is_weekend,
                }
            ),
            sections=sections,
            reason=RevisionReason.LATE_UPDATE,
            published_at=clock(),
        )
    except PublishError as exc:
        session.rollback()
        report.reason = str(exc)
        _finish(run, RunStatus.FAILED, report)
        session.commit()
        return report

    report.published_revision = revision.revision
    _finish(run, RunStatus.SUCCEEDED, report)
    session.commit()
    return report


def _assemble(
    session: Session,
    *,
    previous_revision_id: uuid.UUID,
    edition_date: date,
    changed: list[str],
    renderer: SectionRenderer,
    report: LateUpdateReport,
) -> dict[str, RenderedSection]:
    """Re-render what changed; carry the rest of the revision forward intact."""
    sections: dict[str, RenderedSection] = {}

    previous_sections = session.scalars(
        select(EditionSection).where(EditionSection.revision_id == previous_revision_id)
    )
    for row in previous_sections:
        if row.genre in changed:
            continue
        # Unchanged: the identical bytes readers already received.
        sections[row.genre] = RenderedSection(
            genre=row.genre,
            status=row.status,
            html=row.html or "",
            plain_text=row.plain_text or "",
            story_count=row.story_count,
        )
        report.carried_forward.append(row.genre)

    for genre in changed:
        candidates = sorted(
            load_candidates(session, edition_date=edition_date, genres=[genre]),  # type: ignore[list-item]
            key=lambda candidate: candidate.pool_rank,
        )
        sections[genre] = renderer.render_candidates(genre, candidates)  # type: ignore[arg-type]

    return sections


def _finish(run: PipelineRun, status: RunStatus, report: LateUpdateReport) -> None:
    run.status = status
    run.finished_at = now_utc()
    run.detail = {
        "published_revision": report.published_revision,
        "new_stories": report.new_stories,
        "changed": report.changed,
        "carried_forward": report.carried_forward,
        "reason": report.reason,
        "genres": report.genre_diagnostics,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish a late-update revision.")
    parser.add_argument("--edition-date", type=date.fromisoformat, default=None)
    parser.add_argument("--genre", action="append", dest="genres", default=None)
    parser.add_argument(
        "--deadline-minutes",
        type=int,
        default=DEFAULT_WINDOW_MINUTES,
        help="minutes from now until this window closes",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)

    edition_date = args.edition_date or edition_date_for(now_utc())
    deadline = now_utc() + timedelta(minutes=args.deadline_minutes)

    try:
        with job_lock(JobName.LATE_UPDATE.value) as acquired:
            if not acquired:
                logger.warning("another late update is in progress; exiting")
                return 0
            user_agent = user_agent_for(str(settings.base_url))
            run_id = uuid.uuid4()
            recorder_bundle = build_call_recorder(run_id, settings=settings)
            try:
                with (
                    Fetcher(user_agent=user_agent) as fetcher,
                    LlmClient(recorder=recorder_bundle.recorder) as llm,
                    session_scope() as session,
                ):
                    report = run_late_update(
                        session,
                        edition_date=edition_date,
                        deadline=deadline,
                        orchestrator=build_orchestrator(llm, fetcher),
                        renderer=SectionRenderer(),
                        genres=args.genres,
                        run_id=run_id,
                    )
            except Exception as exc:
                # The session has already rolled back; record the death on a fresh one.
                with session_scope() as failed:
                    fail_run(failed, run_id, exc)
                raise
            finally:
                recorder_bundle.flush()
    finally:
        dispose_engine()

    print(
        f"edition_date={report.edition_date} revision={report.published_revision} "
        f"new_stories={report.new_stories} changed={report.changed}"
    )
    if report.reason:
        print(f"  {report.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
