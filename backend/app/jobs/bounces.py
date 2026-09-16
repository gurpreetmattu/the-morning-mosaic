"""Bounce processing job — 05:00 IST, before the day's deliveries.

    uv run python -m app.jobs.bounces [--since-days 3]

Marks addresses that permanently failed, so the morning's delivery run does
not spend Gmail's daily quota on mailboxes that no longer exist.

It runs before the build finishes on purpose: a dead address costs quota that
a real reader could have used, and the quota covers every email the project
sends, transactional included.

Only permanent failures count. A full mailbox or a temporary outage reports
4.x.x and is ignored, because unsubscribing a reader over a transient problem
loses them permanently.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import edition_date_for, now_utc
from app.config.settings import get_settings
from app.db.engine import dispose_engine, session_scope
from app.email.bounces import BounceSource, ImapBounceSource, parse_bounce
from app.jobs.locking import job_lock
from app.logging_config import configure_logging
from app.models.enums import JobName, RunStatus, SubscriptionStatus
from app.models.operations import PipelineRun
from app.models.users import User

logger = logging.getLogger(__name__)

# Bounces can lag the send, and reprocessing one is harmless.
DEFAULT_LOOKBACK_DAYS = 3


@dataclass
class BounceReport:
    since: date
    examined: int = 0
    permanent: int = 0
    transient: int = 0
    marked: int = 0
    unknown_addresses: int = 0
    errors: list[str] = field(default_factory=list)


def run_bounces(
    session: Session,
    *,
    source: BounceSource,
    since: date,
    now: datetime | None = None,
) -> BounceReport:
    started = now or now_utc()
    report = BounceReport(since=since)

    run = PipelineRun(
        job=JobName.BOUNCES,
        edition_date=edition_date_for(started),
        status=RunStatus.RUNNING,
        started_at=started,
    )
    session.add(run)
    session.commit()

    try:
        messages = list(source.fetch(since=since))
    except OSError as exc:
        # The mailbox is unreachable. Delivery still runs; it just spends a
        # little quota on addresses we have not learned about yet.
        report.errors.append(f"{type(exc).__name__}: {exc}")
        _finish(run, RunStatus.FAILED, report)
        session.commit()
        return report

    for message in messages:
        bounce = parse_bounce(message)
        if bounce is None:
            continue
        report.examined += 1

        if not bounce.permanent:
            # 4.x.x: the mail system will try again, and so will we.
            report.transient += 1
            continue
        report.permanent += 1

        user = session.scalar(select(User).where(User.email == bounce.address))
        if user is None:
            # A bounce for an address we never had, or one already deleted.
            report.unknown_addresses += 1
            continue
        if user.status is SubscriptionStatus.BOUNCED:
            continue  # already known; reprocessing is a no-op

        user.status = SubscriptionStatus.BOUNCED
        user.status_changed_at = now_utc()
        report.marked += 1

    _finish(run, RunStatus.SUCCEEDED, report)
    session.commit()
    return report


def _finish(run: PipelineRun, status: RunStatus, report: BounceReport) -> None:
    run.status = status
    run.finished_at = now_utc()
    run.detail = {
        "since": report.since.isoformat(),
        "examined": report.examined,
        "permanent": report.permanent,
        "transient": report.transient,
        "marked": report.marked,
        "unknown_addresses": report.unknown_addresses,
        "errors": report.errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mark permanently failed addresses.")
    parser.add_argument("--since-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)
    since = edition_date_for(now_utc()) - timedelta(days=args.since_days)

    source = ImapBounceSource(
        host=settings.imap_host,
        port=settings.imap_port,
        username=str(settings.sender_email),
        password=settings.gmail_app_password.get_secret_value(),
    )

    try:
        with job_lock(JobName.BOUNCES.value) as acquired:
            if not acquired:
                logger.warning("another bounce run is in progress; exiting")
                return 0
            with session_scope() as session:
                report = run_bounces(session, source=source, since=since)
    finally:
        dispose_engine()

    print(
        f"since={report.since} examined={report.examined} permanent={report.permanent} "
        f"transient={report.transient} marked={report.marked} "
        f"unknown={report.unknown_addresses}"
    )
    return 0 if not report.errors else 1
