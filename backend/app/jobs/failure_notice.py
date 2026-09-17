"""Failure notice job — 09:05 IST, after the last delivery run.

    uv run python -m app.jobs.failure_notice [--edition-date YYYY-MM-DD]

Sends a short, generic apology to readers whose edition did not arrive. It
depends on nothing the build produced, because the day it is needed is
precisely the day the build is broken.

Three rules shape it, all from CLAUDE.md:

- **Never guess that mail was lost.** A reader whose delivery is stuck in
  `sending` may well have received the edition, so they are excluded. An
  apology for something you did receive is worse than silence.
- **An abnormal batch is held, not sent.** If more readers are affected than
  FAILURE_NOTICE_AUTO_LIMIT, the batch waits for a human. A held batch expires
  unsent at 12:00 IST, because a late apology is worse than none.
- **Prolonged outages get one message, not a daily drumbeat.** On the third
  consecutive failed day a reader receives a "paused" note instead, and then
  nothing until an edition actually arrives.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import IST, edition_date_for, now_utc
from app.config.settings import Settings, get_settings
from app.db.engine import dispose_engine, get_sessionmaker
from app.email.sender import Message, Sender, SendError, SendOutcome
from app.email.tokens import ensure_unsubscribe_token
from app.jobs.delivery import claim
from app.jobs.locking import job_lock
from app.logging_config import configure_logging
from app.models.editions import Delivery
from app.models.enums import (
    DeliveryStatus,
    DeliveryType,
    Frequency,
    JobName,
    NoticeBatchStatus,
    RunStatus,
    SubscriptionStatus,
)
from app.models.operations import NoticeBatch, PipelineRun
from app.models.users import OutageState, User
from app.render.notices import RenderedNotice, failure_notice, paused_notice

logger = logging.getLogger(__name__)

# A held batch is abandoned rather than sent late.
BATCH_EXPIRY_IST = time(12, 0)
# Consecutive failed days before a reader gets the one-off "paused" message.
PAUSE_AFTER_DAYS = 3
# If this many sends fail in a row, the mail system is down, not the batch.
CONSECUTIVE_FAILURE_ABORT = 3


@dataclass
class NoticeReport:
    edition_date: date
    eligible: int = 0
    sent: int = 0
    paused_sent: int = 0
    suppressed: int = 0
    failed: int = 0
    status: NoticeBatchStatus | None = None
    reason: str | None = None
    errors: list[str] = field(default_factory=list)


def batch_expiry(edition_date: date) -> datetime:
    return datetime.combine(edition_date, BATCH_EXPIRY_IST, tzinfo=IST).astimezone(UTC)


# ------------------------------------------------------------- who qualifies


def needs_notice(session: Session, user: User, *, edition_date: date) -> bool:
    """True when today's edition demonstrably did not reach this reader."""
    delivery = session.scalars(
        select(Delivery).where(
            Delivery.user_id == user.id,
            Delivery.edition_date == edition_date,
            Delivery.type == DeliveryType.NEWSLETTER,
        )
    ).one_or_none()

    if delivery is None:
        # No attempt at all: the build failed, or every genre came up short.
        return True
    # SENT: arrived. SENDING: unknowable, so assume it arrived. SKIPPED: the
    # dev allowlist, which is not an outage.
    return delivery.status is DeliveryStatus.FAILED


def eligible_readers(session: Session, *, edition_date: date) -> list[User]:
    readers = session.scalars(
        select(User).where(User.status == SubscriptionStatus.ACTIVE).order_by(User.created_at)
    )
    return [
        user
        for user in readers
        if not (user.frequency is Frequency.WEEKDAYS and edition_date.weekday() >= 5)
        and needs_notice(session, user, edition_date=edition_date)
    ]


# ------------------------------------------------------------------ batching


def resolve_batch(
    session: Session,
    *,
    edition_date: date,
    count: int,
    limit: int,
    now: datetime,
) -> NoticeBatch:
    """Create or advance the day's batch, deciding whether it may send."""
    batch = session.scalar(select(NoticeBatch).where(NoticeBatch.edition_date == edition_date))

    if batch is None:
        batch = NoticeBatch(
            edition_date=edition_date,
            status=NoticeBatchStatus.HELD if count > limit else NoticeBatchStatus.APPROVED,
            recipient_count=count,
            expires_at=batch_expiry(edition_date),
        )
        session.add(batch)
        session.flush()
        return batch

    if batch.status is NoticeBatchStatus.HELD and now >= batch.expires_at:
        # Noon has passed. A late apology is worse than none.
        batch.status = NoticeBatchStatus.EXPIRED
        batch.decided_at = now
    return batch


def may_send(batch: NoticeBatch) -> bool:
    return batch.status is NoticeBatchStatus.APPROVED


# -------------------------------------------------------------- outage state


def record_failure(session: Session, user: User, *, edition_date: date) -> OutageState:
    state = session.get(OutageState, user.id)
    if state is None:
        state = OutageState(user_id=user.id, consecutive_failed_days=0)
        session.add(state)
        session.flush()

    # Idempotent: rerunning the job on the same day must not inflate the count.
    if state.last_failed_on != edition_date:
        state.consecutive_failed_days += 1
        state.last_failed_on = edition_date
    return state


def notice_for(
    state: OutageState, *, first_name: str, links: tuple[str, str]
) -> RenderedNotice | None:
    """Which notice this reader should get, or None for silence."""
    unsubscribe_url, preferences_url = links

    if state.consecutive_failed_days < PAUSE_AFTER_DAYS:
        return failure_notice(
            first_name=first_name,
            unsubscribe_url=unsubscribe_url,
            preferences_url=preferences_url,
        )
    if state.paused_notice_sent_on is None:
        return paused_notice(
            first_name=first_name,
            unsubscribe_url=unsubscribe_url,
            preferences_url=preferences_url,
        )
    # Already told them once. Silence until an edition actually arrives.
    return None


# ------------------------------------------------------------------- the run


def run_failure_notices(
    session: Session,
    *,
    edition_date: date,
    sender: Sender,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> NoticeReport:
    config = settings or get_settings()
    moment = now or now_utc()
    report = NoticeReport(edition_date=edition_date)

    run = PipelineRun(
        job=JobName.FAILURE_NOTICE,
        edition_date=edition_date,
        status=RunStatus.RUNNING,
        started_at=moment,
    )
    session.add(run)
    session.commit()

    readers = eligible_readers(session, edition_date=edition_date)
    report.eligible = len(readers)

    batch = resolve_batch(
        session,
        edition_date=edition_date,
        count=len(readers),
        limit=config.failure_notice_auto_limit,
        now=moment,
    )
    report.status = batch.status
    session.commit()

    if not may_send(batch):
        report.reason = {
            NoticeBatchStatus.HELD: "batch held for approval: recipient count looks abnormal",
            NoticeBatchStatus.SUPPRESSED: "batch suppressed by the admin",
            NoticeBatchStatus.EXPIRED: "batch expired unsent at noon",
            NoticeBatchStatus.SENT: "batch already sent",
        }.get(batch.status, "batch is not approved")
        _finish(run, RunStatus.SUCCEEDED, report)
        session.commit()
        return report

    base = str(config.base_url).rstrip("/")
    consecutive_failures = 0

    for user in readers:
        delivery = claim(
            session,
            user_id=user.id,
            edition_date=edition_date,
            delivery_type=DeliveryType.FAILURE_NOTICE,
        )
        if delivery is None:
            continue  # at most one notice per reader per day

        state = record_failure(session, user, edition_date=edition_date)
        unsubscribe = ensure_unsubscribe_token(session, user.id)
        notice = notice_for(
            state,
            first_name=user.name.split()[0] if user.name.strip() else "there",
            links=(f"{base}/unsubscribe/{unsubscribe}", f"{base}/preferences"),
        )
        if notice is None:
            # Already paused. Drop the claim so no row implies a send.
            session.rollback()
            continue

        delivery.status = DeliveryStatus.SENDING
        delivery.claimed_at = now_utc()
        delivery.attempts += 1
        session.commit()

        try:
            result = sender.send(
                Message(
                    to=user.email,
                    subject=notice.subject,
                    html=notice.html,
                    text=notice.text,
                    unsubscribe_url=f"{base}/unsubscribe/{unsubscribe}",
                )
            )
        except SendError as exc:
            delivery.status = DeliveryStatus.FAILED
            delivery.error = str(exc)[:500]
            report.failed += 1
            consecutive_failures += 1
            session.commit()
            if consecutive_failures >= CONSECUTIVE_FAILURE_ABORT:
                # The mail system is down, not this batch. CLAUDE.md: alert the
                # admin and send nothing further.
                report.reason = "aborted: sending appears to be unavailable"
                report.errors.append(type(exc).__name__)
                _finish(run, RunStatus.FAILED, report)
                session.commit()
                return report
            continue

        consecutive_failures = 0
        if result.outcome is SendOutcome.SUPPRESSED:
            delivery.status = DeliveryStatus.SKIPPED
            delivery.error = result.reason
            report.suppressed += 1
        else:
            delivery.status = DeliveryStatus.SENT
            delivery.sent_at = now_utc()
            if state.consecutive_failed_days >= PAUSE_AFTER_DAYS:
                state.paused_notice_sent_on = edition_date
                report.paused_sent += 1
            else:
                report.sent += 1
        session.commit()

    batch.status = NoticeBatchStatus.SENT
    batch.decided_at = now_utc()
    _finish(run, RunStatus.SUCCEEDED, report)
    session.commit()
    return report


def _finish(run: PipelineRun, status: RunStatus, report: NoticeReport) -> None:
    run.status = status
    run.finished_at = now_utc()
    run.detail = {
        "eligible": report.eligible,
        "sent": report.sent,
        "paused_sent": report.paused_sent,
        "suppressed": report.suppressed,
        "failed": report.failed,
        "batch_status": report.status.value if report.status else None,
        "reason": report.reason,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send failure notices for a day.")
    parser.add_argument("--edition-date", type=date.fromisoformat, default=None)
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)
    edition_date = args.edition_date or edition_date_for(now_utc())

    try:
        with job_lock(JobName.FAILURE_NOTICE.value) as acquired:
            if not acquired:
                logger.warning("another failure-notice run is in progress; exiting")
                return 0
            session = get_sessionmaker()()
            try:
                report = run_failure_notices(
                    session,
                    edition_date=edition_date,
                    sender=Sender(settings=settings),
                    settings=settings,
                )
            finally:
                session.close()
    finally:
        dispose_engine()

    print(
        f"edition_date={report.edition_date} eligible={report.eligible} sent={report.sent} "
        f"paused={report.paused_sent} suppressed={report.suppressed} failed={report.failed} "
        f"batch={report.status.value if report.status else '-'}"
    )
    if report.reason:
        print(f"  {report.reason}")
    return 0 if not report.failed else 1


if __name__ == "__main__":
    sys.exit(main())
