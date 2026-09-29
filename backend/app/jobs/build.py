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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.collector import Collector
from app.agents.fact_checker import FactChecker
from app.agents.image_finder import ImageResult, find_image
from app.agents.orchestrator import Orchestrator
from app.agents.ranker import Ranker
from app.agents.schemas import EditionBuild, PooledStory, VerificationOutcome
from app.agents.verification import write_and_verify
from app.agents.writer import Writer
from app.clock import IST, edition_date_for, now_utc
from app.config.schemas import GenreKey
from app.config.settings import get_settings
from app.db.engine import dispose_engine, session_scope
from app.db.persist import persist_genre_stories, persist_image
from app.db.publish import PublishError, publish_revision
from app.jobs.locking import job_lock
from app.llm.client import LlmClient
from app.llm.langfuse_recorder import build_call_recorder
from app.logging_config import configure_logging
from app.models.enums import JobName, RunStatus
from app.models.operations import PipelineRun
from app.render.sections import RenderedSection, SectionRenderer
from app.render.weekend import persist_weekend_features
from app.services.deals import load_game_deals, persist_game_deals
from app.services.markets import persist_market_strip
from app.services.quotes import persist_daily_extras
from app.services.releases import load_movie_releases, persist_movie_releases
from app.services.sports import load_fixtures, load_scores, persist_sports_extras
from app.sources.fetch import Fetcher, user_agent_for
from app.sources.robots import RobotsPolicy

logger = logging.getLogger(__name__)

# The build starts at 04:15 IST and must be done by 05:30, so the first
# delivery run at 06:00 always has a revision to send.
BUILD_DEADLINE_IST = time(5, 30)

# CLAUDE.md wants an alert on "a sharp drop in verified story counts." There
# is no absolute number that means "wrong" — launch week and a slow news day
# both legitimately produce few stories — so this compares today's count
# against a rolling baseline instead, and only once there is enough baseline
# to compare against. Deliberately conservative on both counts: a real
# Cloud Monitoring alert (see infra/monitoring.tf) means someone gets paged,
# so false positives cost more here than a missed early warning does.
STORY_COUNT_DROP_MIN_HISTORY = 3
STORY_COUNT_DROP_THRESHOLD = 0.5


@dataclass
class BuildReport:
    edition_date: date
    published_revision: int | None = None
    stories_persisted: int = 0
    sections: dict[str, str] = field(default_factory=dict)
    weekend_features: list[str] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    deadline_missed: bool = False
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.published_revision is not None


def deadline_for(edition_date: date, at: time = BUILD_DEADLINE_IST) -> datetime:
    """The hard deadline as a UTC instant, from an IST wall-clock time."""
    return datetime.combine(edition_date, at, tzinfo=IST).astimezone(UTC)


def _recent_story_counts(session: Session, *, before: date, limit: int = 7) -> list[int]:
    """`stories_persisted` from the most recent earlier builds that actually
    ran to completion. Only ever read for the drop check below — never to
    gate publishing, which CLAUDE.md's own quiet-day and failure-isolation
    rules already decide."""
    rows = session.scalars(
        select(PipelineRun)
        .where(
            PipelineRun.job == JobName.BUILD,
            PipelineRun.edition_date < before,
            PipelineRun.status.in_((RunStatus.SUCCEEDED, RunStatus.DEADLINE_MISSED)),
        )
        .order_by(PipelineRun.edition_date.desc())
        .limit(limit)
    ).all()
    return [
        row.detail["stories_persisted"]
        for row in rows
        if row.detail is not None and isinstance(row.detail.get("stories_persisted"), int)
    ]


def _check_story_count_drop(session: Session, *, edition_date: date, today: int) -> None:
    history = _recent_story_counts(session, before=edition_date)
    if len(history) < STORY_COUNT_DROP_MIN_HISTORY:
        return  # not enough baseline yet (e.g. launch week) to mean anything
    baseline = sum(history) / len(history)
    if baseline > 0 and today < STORY_COUNT_DROP_THRESHOLD * baseline:
        logger.warning(
            "verified_story_count_drop edition_date=%s today=%d baseline=%.1f",
            edition_date.isoformat(),
            today,
            baseline,
        )


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
    extras_fetcher: Fetcher | None = None,
    image_finder_llm: LlmClient | None = None,
    unsplash_api_key: str | None = None,
    pexels_api_key: str | None = None,
    tmdb_api_key: str | None = None,
    sports_api_key: str | None = None,
) -> BuildReport:
    """Build and publish one edition. The session is committed by the caller.

    `run_id`, when given, must already exist as a committed `PipelineRun` row
    (see `main()`) — the LLM client's recorder needs that row visible to its
    own, separate session before any `llm_calls` row can reference it via
    foreign key, and every LLM call in this build happens before this
    session touches the database at all. The Image finder's relevance check
    is an LLM call too, so it runs in that same pre-persist phase (right
    after `orchestrator.build()` returns, before the persist loop below) —
    never interleaved with the open write transaction, which is exactly the
    idle-in-transaction shape that has killed a Neon connection here before.
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
    # Ends the transaction that fetching/creating `run` opened, before the
    # real minutes-long LLM phase below (collect, rank, write, verify) touches
    # no database at all. Without this, the session sits idle-in-transaction
    # for that whole phase and Neon kills the connection — found live via a
    # real business-genre build. `run` stays usable after commit
    # (get_sessionmaker's expire_on_commit=False), so `_finish` below needs
    # no re-fetch.
    session.commit()

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
    if report.deadline_missed:
        # Distinct, greppable message text: infra/monitoring.tf's log-based
        # metric matches on this literal, not on the log level alone (a
        # deadline miss is a WARNING, but so are other things this job logs).
        logger.warning(
            "build_deadline_missed edition_date=%s deadline=%s",
            edition_date.isoformat(),
            deadline.isoformat(),
        )

    # One image per genre section, for its top-ranked story only (scope
    # confirmed with the owner — see docs/BACKLOG.md). Computed here, before
    # the persist loop touches the database at all, same as every other LLM
    # call in this build.
    images: dict[str, ImageResult] = {}
    if image_finder_llm is not None and extras_fetcher is not None:
        for outcome in build.genres:
            if not outcome.stories:
                continue
            image = find_image(
                image_finder_llm,
                extras_fetcher,
                story=outcome.stories[0].story,
                unsplash_api_key=unsplash_api_key,
                pexels_api_key=pexels_api_key,
            )
            if image is not None:
                images[outcome.genre] = image

    rendered: dict[str, RenderedSection] = {}
    for outcome in build.genres:
        stories = persist_genre_stories(session, edition_date=edition_date, outcome=outcome)
        report.stories_persisted += len(stories)
        image = images.get(outcome.genre)

        releases: list[dict[str, str]] | None = None
        if extras_fetcher is not None and tmdb_api_key is not None:
            persist_movie_releases(
                session,
                edition_date=edition_date,
                genre=outcome.genre,
                fetcher=extras_fetcher,
                api_key=tmdb_api_key,
                now=started,
            )
            releases = (
                load_movie_releases(session, edition_date=edition_date, genre=outcome.genre) or None
            )
            if releases:
                report.extras.append(f"movie_release:{outcome.genre}")

        scores: list[dict[str, str]] | None = None
        fixtures: list[dict[str, str]] | None = None
        if extras_fetcher is not None and sports_api_key is not None and outcome.genre == "sports":
            for extra in persist_sports_extras(
                session,
                edition_date=edition_date,
                fetcher=extras_fetcher,
                api_key=sports_api_key,
                now=started,
            ):
                report.extras.append(extra.kind.value)
            scores = load_scores(session, edition_date=edition_date) or None
            fixtures = load_fixtures(session, edition_date=edition_date) or None

        game_deals: list[dict[str, str]] | None = None
        if extras_fetcher is not None and outcome.genre == "gaming":
            # No API key: CheapShark is free and keyless.
            persist_game_deals(
                session, edition_date=edition_date, fetcher=extras_fetcher, now=started
            )
            game_deals = load_game_deals(session, edition_date=edition_date) or None
            if game_deals:
                report.extras.append("game_deal")

        section = renderer.render(
            outcome,
            image=image,
            movie_releases=releases,
            scores=scores,
            fixtures=fixtures,
            game_deals=game_deals,
        )
        rendered[outcome.genre] = section
        report.sections[outcome.genre] = section.status.value

        if image is not None and stories:
            persist_image(session, story_id=stories[0].id, result=image)
            report.images.append(outcome.genre)

    _check_story_count_drop(session, edition_date=edition_date, today=report.stories_persisted)

    for feature in persist_weekend_features(session, edition_date=edition_date):
        report.weekend_features.append(feature.kind.value)

    if extras_fetcher is not None:
        for extra in persist_daily_extras(
            session, edition_date=edition_date, fetcher=extras_fetcher, now=started
        ):
            report.extras.append(extra.kind.value)
        market_extra = persist_market_strip(
            session, edition_date=edition_date, fetcher=extras_fetcher, now=started
        )
        if market_extra is not None:
            report.extras.append(market_extra.kind.value)

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

            recorder_bundle = build_call_recorder(run_id, settings=settings)
            try:
                with (
                    Fetcher(user_agent=user_agent) as fetcher,
                    LlmClient(recorder=recorder_bundle.recorder) as llm,
                ):
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
                            extras_fetcher=fetcher,
                            image_finder_llm=llm,
                            unsplash_api_key=(
                                settings.unsplash_access_key.get_secret_value()
                                if settings.unsplash_access_key
                                else None
                            ),
                            pexels_api_key=(
                                settings.pexels_api_key.get_secret_value()
                                if settings.pexels_api_key
                                else None
                            ),
                            tmdb_api_key=(
                                settings.tmdb_api_key.get_secret_value()
                                if settings.tmdb_api_key
                                else None
                            ),
                            sports_api_key=(
                                settings.sports_api_key.get_secret_value()
                                if settings.sports_api_key
                                else None
                            ),
                        )
            finally:
                recorder_bundle.flush()
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
    for extra in report.extras:
        print(f"  extra: {extra}")
    for genre in report.images:
        print(f"  image: {genre}")
    if report.error:
        print(f"  error: {report.error}")


if __name__ == "__main__":
    sys.exit(main())
