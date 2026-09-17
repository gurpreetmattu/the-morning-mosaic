"""Edition build job — 04:15 IST, hard deadline 05:30 IST.

Runs the whole pipeline: collect, rank, write, verify, persist, render, and
publish the day's first revision.

    uv run python -m app.jobs.build [--edition-date YYYY-MM-DD] [--genre india ...]

Ordering matters. Every LLM call happens before the database is touched, so
the write phase is short and can be one transaction: an edition either gets a
complete revision or none at all. A half-published edition would be served to
readers.
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.agents.collector import Collector
from app.agents.fact_checker import FactChecker
from app.agents.orchestrator import Orchestrator
from app.agents.ranker import Ranker
from app.agents.schemas import EditionBuild, PooledStory, VerificationOutcome
from app.agents.verification import write_and_verify
from app.agents.writer import Writer
from app.clock import IST, edition_date_for, now_utc
from app.config.schemas import GenreKey
from app.config.settings import get_settings
from app.db.engine import dispose_engine, session_scope
from app.db.persist import persist_genre
from app.db.publish import PublishError, publish_revision
from app.jobs.locking import job_lock
from app.llm.client import LlmClient
from app.llm.recorder import DatabaseCallRecorder
from app.logging_config import configure_logging
from app.models.enums import JobName, RunStatus
from app.models.operations import PipelineRun
from app.render.sections import RenderedSection, SectionRenderer
from app.render.weekend import persist_weekend_features
from app.sources.fetch import Fetcher, user_agent_for
from app.sources.robots import RobotsPolicy

logger = logging.getLogger(__name__)

# The build starts at 04:15 IST and must be done by 05:30, so the first
# delivery run at 06:00 always has a revision to send.
BUILD_DEADLINE_IST = time(5, 30)


@dataclass
class BuildReport:
    edition_date: date
    published_revision: int | None = None
    stories_persisted: int = 0
    sections: dict[str, str] = field(default_factory=dict)
    weekend_features: list[str] = field(default_factory=list)
    deadline_missed: bool = False
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.published_revision is not None


def deadline_for(edition_date: date, at: time = BUILD_DEADLINE_IST) -> datetime:
    """The hard deadline as a UTC instant, from an IST wall-clock time."""
    return datetime.combine(edition_date, at, tzinfo=IST).astimezone(UTC)


def run_build(
    session: Session,
    *,
    edition_date: date,
    deadline: datetime,
    orchestrator: Orchestrator,
    renderer: SectionRenderer,
    genres: list[GenreKey] | None = None,
    now: datetime | None = None,
    run_id: uuid.UUID | None = None,
) -> BuildReport:
    """Build and publish one edition. The session is committed by the caller.

    `run_id`, when given, must already exist as a committed `PipelineRun` row
    (see `main()`) — the LLM client's recorder needs that row visible to its
    own, separate session before any `llm_calls` row can reference it via
    foreign key, and every LLM call in this build happens before this
    session touches the database at all.
    """
    report = BuildReport(edition_date=edition_date)
    started = now or now_utc()

    run = session.get(PipelineRun, run_id) if run_id is not None else None
    if run is None:
        run = PipelineRun(
            id=run_id or uuid.uuid4(),
            job=JobName.BUILD,
            edition_date=edition_date,
            status=RunStatus.RUNNING,
            started_at=started,
            deadline_at=deadline,
        )
        session.add(run)
        session.flush()

    try:
        orchestrator.edition_number(edition_date)
    except ValueError as exc:
        # edition_date precedes launch_date. Fail the run cleanly instead of
        # letting the exception escape as an unrecorded traceback.
        report.error = str(exc)
        _finish(run, RunStatus.FAILED, report)
        return report

    build: EditionBuild = orchestrator.build(
        edition_date=edition_date, deadline=deadline, genres=genres, now=started
    )
    report.deadline_missed = build.deadline_missed

    rendered: dict[str, RenderedSection] = {}
    for outcome in build.genres:
        report.stories_persisted += persist_genre(
            session, edition_date=edition_date, outcome=outcome
        )
        section = renderer.render(outcome)
        rendered[outcome.genre] = section
        report.sections[outcome.genre] = section.status.value

    for feature in persist_weekend_features(session, edition_date=edition_date):
        report.weekend_features.append(feature.kind.value)

    try:
        revision = publish_revision(session, build=build, sections=rendered, published_at=now_utc())
    except PublishError as exc:
        # Nothing publishable. The failure-notice job handles the readers.
        report.error = str(exc)
        _finish(run, RunStatus.FAILED, report)
        return report

    report.published_revision = revision.revision
    _finish(
        run,
        RunStatus.DEADLINE_MISSED if build.deadline_missed else RunStatus.SUCCEEDED,
        report,
    )
    return report


def _finish(run: PipelineRun, status: RunStatus, report: BuildReport) -> None:
    run.status = status
    run.finished_at = now_utc()
    run.detail = {
        "sections": report.sections,
        "stories_persisted": report.stories_persisted,
        "weekend_features": report.weekend_features,
        "published_revision": report.published_revision,
        "error": report.error,
    }


# ------------------------------------------------------------------ wiring


def build_orchestrator(llm: LlmClient, fetcher: Fetcher) -> Orchestrator:
    user_agent = user_agent_for(str(get_settings().base_url))
    collector = Collector(fetcher=fetcher, robots=RobotsPolicy(fetcher, user_agent))
    writer, checker = Writer(llm=llm), FactChecker(llm=llm)

    def verify(pooled: PooledStory, genre: GenreKey) -> VerificationOutcome:
        return write_and_verify(writer=writer, checker=checker, pooled=pooled, genre=genre)

    return Orchestrator(
        collector=collector, ranker=Ranker(llm=llm, collector=collector), verify=verify
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and publish the day's edition.")
    parser.add_argument(
        "--edition-date",
        type=date.fromisoformat,
        default=None,
        help="IST calendar date to build for; defaults to today in IST",
    )
    parser.add_argument(
        "--genre", action="append", dest="genres", default=None, help="limit to these genres"
    )
    parser.add_argument(
        "--deadline-minutes",
        type=int,
        default=None,
        help="override the deadline as minutes from now, for a manual rerun",
    )
    args = parser.parse_args(argv)

    configure_logging(get_settings().log_level)
    edition_date = args.edition_date or edition_date_for(now_utc())
    deadline = (
        now_utc() + timedelta(minutes=args.deadline_minutes)
        if args.deadline_minutes is not None
        else deadline_for(edition_date)
    )

    settings = get_settings()
    user_agent = user_agent_for(str(settings.base_url))

    try:
        with job_lock(JobName.BUILD.value) as acquired:
            if not acquired:
                # The scheduled run is still going. Doing the work twice would
                # publish two revisions of the same edition.
                logger.warning("another build is already running; exiting")
                return 0

            run_id = uuid.uuid4()
            started = now_utc()
            with session_scope() as setup:
                setup.add(
                    PipelineRun(
                        id=run_id,
                        job=JobName.BUILD,
                        edition_date=edition_date,
                        status=RunStatus.RUNNING,
                        started_at=started,
                        deadline_at=deadline,
                    )
                )

            recorder = DatabaseCallRecorder(pipeline_run_id=run_id)
            with Fetcher(user_agent=user_agent) as fetcher, LlmClient(recorder=recorder) as llm:
                orchestrator = build_orchestrator(llm, fetcher)
                with session_scope() as session:
                    report = run_build(
                        session,
                        edition_date=edition_date,
                        deadline=deadline,
                        orchestrator=orchestrator,
                        renderer=SectionRenderer(),
                        genres=args.genres,
                        now=started,
                        run_id=run_id,
                    )
    finally:
        dispose_engine()

    _print(report)
    return 0 if report.succeeded else 1


def _print(report: BuildReport) -> None:
    summary: Mapping[str, object] = {
        "edition_date": report.edition_date.isoformat(),
        "revision": report.published_revision,
        "stories": report.stories_persisted,
        "deadline_missed": report.deadline_missed,
    }
    print(" ".join(f"{key}={value}" for key, value in summary.items()))
    for genre, status in sorted(report.sections.items()):
        print(f"  {genre:12} {status}")
    for feature in report.weekend_features:
        print(f"  weekend: {feature}")
    if report.error:
        print(f"  error: {report.error}")


if __name__ == "__main__":
    sys.exit(main())
