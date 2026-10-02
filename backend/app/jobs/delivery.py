"""Delivery job — every 30 minutes, 06:00 to 09:00 IST.

    uv run python -m app.jobs.delivery [--slot 07:00] [--edition-date ...]

The at-most-once guarantee is the highest-risk invariant in the project, and
it rests on the order of three steps:

1. claim the delivery row with `SELECT ... FOR UPDATE SKIP LOCKED`, so an
   overlapping run steps past a row another run holds rather than blocking on
   it;
2. mark it `sending` and **commit**, so the claim survives this process dying;
3. only then call SMTP.

A row left in `sending` is never retried. If the process is killed between the
SMTP call and the result, we cannot know whether the mail went out, and a
duplicate edition is worse than a missing one. Those rows are counted and left
for review.

Readers whose every genre came up short are skipped rather than sent a
near-empty edition; the 09:05 failure-notice job picks them up.
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.image_finder import ImageResult
from app.clock import edition_date_for, now_utc, to_ist
from app.config.loader import load_editions
from app.config.schemas import EditionsConfig
from app.config.settings import Settings, get_settings
from app.db.engine import dispose_engine, get_sessionmaker
from app.db.publish import latest_revision
from app.email.sender import Message, Sender, SendError, SendOutcome
from app.email.tokens import PDF, ensure_unsubscribe_token, sign
from app.jobs.locking import job_lock
from app.logging_config import configure_logging
from app.models.content import Correction, Image, Story
from app.models.editions import Delivery, Edition, EditionRevision
from app.models.enums import (
    DeliveryStatus,
    DeliveryType,
    Frequency,
    JobName,
    RunStatus,
    SubscriptionStatus,
)
from app.models.operations import PipelineRun
from app.models.users import FollowedKeyword, OutageState, User, UserGenre, UserPreference
from app.render.email import EmailRenderer, Links, SectionExtras, Weather
from app.render.selection import Reader, load_candidates, quiet_genres, select_for_reader
from app.render.weekend import WeekendContent, load_weekend_features
from app.services.deals import load_game_deals
from app.services.markets import load_market_strip
from app.services.quotes import load_on_this_day, load_quote
from app.services.releases import load_movie_releases
from app.services.sports import load_fixtures, load_scores
from app.services.weather import get_weather
from app.sources.fetch import Fetcher, user_agent_for

logger = logging.getLogger(__name__)

# A failed send is retried by later runs, but not forever.
MAX_ATTEMPTS = 3


@dataclass
class DeliveryReport:
    edition_date: date
    slot: time
    revision: int | None = None
    sent: int = 0
    suppressed: int = 0
    failed: int = 0
    already_done: int = 0
    no_content: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def attempted(self) -> int:
        return self.sent + self.suppressed + self.failed


# ------------------------------------------------------------------ who is due


def is_due(user: User, *, slot: time, on: date) -> bool:
    """Whether this reader should receive today's edition in this run.

    Slots at or before the current one count, so a reader missed by an earlier
    run rolls forward rather than losing the day.
    """
    if user.status is not SubscriptionStatus.ACTIVE:
        return False
    if user.frequency is Frequency.WEEKDAYS and on.weekday() >= 5:
        # Weekday-only readers receive neither weekend edition.
        return False
    return user.delivery_slot <= slot


def due_readers(session: Session, *, slot: time, on: date) -> list[User]:
    users = session.scalars(
        select(User).where(User.status == SubscriptionStatus.ACTIVE).order_by(User.created_at)
    )
    return [user for user in users if is_due(user, slot=slot, on=on)]


# --------------------------------------------------------------- the claim


def claim(
    session: Session,
    *,
    user_id: uuid.UUID,
    edition_date: date,
    delivery_type: DeliveryType = DeliveryType.NEWSLETTER,
) -> Delivery | None:
    """Take exclusive ownership of this reader's delivery, or return None.

    None means another run holds it, it already went out, it is stuck in
    `sending`, or it has failed too many times.
    """
    existing = session.scalars(
        select(Delivery)
        .where(
            Delivery.user_id == user_id,
            Delivery.edition_date == edition_date,
            Delivery.type == delivery_type,
        )
        .with_for_update(skip_locked=True)
    ).one_or_none()

    if existing is not None:
        if existing.status in (DeliveryStatus.SENT, DeliveryStatus.SENDING):
            # SENT: done. SENDING: unknowable, so never resent.
            return None
        if existing.attempts >= MAX_ATTEMPTS:
            return None
        return existing

    delivery = Delivery(
        user_id=user_id,
        edition_date=edition_date,
        type=delivery_type,
        status=DeliveryStatus.PENDING,
    )
    session.add(delivery)
    try:
        session.flush()
    except IntegrityError:
        # Another run inserted the same row between the select and the insert.
        session.rollback()
        return None
    return delivery


def clear_outage(session: Session, user_id: uuid.UUID) -> None:
    """Reset the consecutive-failure count after a successful delivery."""
    state = session.get(OutageState, user_id)
    if state is None:
        return
    state.consecutive_failed_days = 0
    state.paused_notice_sent_on = None
    state.last_failed_on = None


# ------------------------------------------------------------ assembling one


def load_reader(session: Session, user: User) -> Reader:
    genres = tuple(
        session.scalars(
            select(UserGenre.genre).where(UserGenre.user_id == user.id).order_by(UserGenre.genre)
        )
    )
    keywords = frozenset(
        session.scalars(select(FollowedKeyword.keyword).where(FollowedKeyword.user_id == user.id))
    )
    scores = {
        (row.genre, row.topic_tag): row.score
        for row in session.scalars(select(UserPreference).where(UserPreference.user_id == user.id))
    }
    return Reader(
        id=user.id,
        first_name=user.name.split()[0] if user.name.strip() else "there",
        genres=genres,  # type: ignore[arg-type]
        keywords=keywords,
        edition_preference=user.edition_preference,
        topic_scores=scores,
    )


def pending_corrections(session: Session, *, edition_date: date) -> list[Correction]:
    """Corrections not yet given their day in an edition, marking them as
    announced for `edition_date` the first time this is called for it.

    "Not yet announced" rather than "announced_on is null": delivery runs
    several times a day, and every run for the same `edition_date` must
    still see a correction it marked earlier that day, or only the reader
    on the very first slot would ever get the note.
    """
    corrections = list(
        session.scalars(
            select(Correction).where(
                or_(Correction.announced_on.is_(None), Correction.announced_on == edition_date)
            )
        )
    )
    for correction in corrections:
        if correction.announced_on is None:
            correction.announced_on = edition_date
    return corrections


def correction_recipients(
    session: Session, corrections: Sequence[Correction], stories: Mapping[uuid.UUID, Story]
) -> dict[uuid.UUID, set[uuid.UUID]]:
    """correction.id -> the set of user ids who were actually sent the
    edition the corrected story first appeared in.

    Approximate on purpose, and the accepted trade-off is documented in
    docs/runbooks/incident-response.md: there is no record of which
    specific stories within an edition a given reader's selection
    included, only that they received *an* edition that day. Genre
    subscription plus a sent delivery for that date over-includes rather
    than risks missing someone.
    """
    recipients: dict[uuid.UUID, set[uuid.UUID]] = {}
    for correction in corrections:
        story = stories.get(correction.story_id)
        if story is None:
            recipients[correction.id] = set()
            continue
        recipients[correction.id] = set(
            session.scalars(
                select(Delivery.user_id).where(
                    Delivery.edition_date == story.edition_date,
                    Delivery.type == DeliveryType.NEWSLETTER,
                    Delivery.status == DeliveryStatus.SENT,
                )
            )
        )
    return recipients


def correction_note_for(
    reader: Reader,
    *,
    corrections: Sequence[Correction],
    recipients: Mapping[uuid.UUID, set[uuid.UUID]],
    stories: Mapping[uuid.UUID, Story],
) -> str | None:
    applicable = [
        correction
        for correction in corrections
        if (story := stories.get(correction.story_id)) is not None
        and story.genre in reader.genres
        and reader.id in recipients.get(correction.id, set())
    ]
    if not applicable:
        return None
    return " ".join(
        f"“{stories[correction.story_id].headline}”: {correction.description}"
        for correction in applicable
    )


def weather_for(
    session: Session,
    *,
    user: User,
    edition_date: date,
    fetcher: Fetcher | None,
    settings: Settings,
    now: datetime,
) -> Weather | None:
    """None whenever weather cannot or should not be fetched: no city on the
    account, no API key configured, or no fetcher running for this job
    (no key -> no fetcher; see `main()`). A missing weather box is cosmetic,
    never a reason to skip or fail a reader's edition.
    """
    api_key = settings.openweathermap_api_key
    if fetcher is None or api_key is None or user.city is None:
        return None
    return get_weather(
        session,
        city=user.city,
        edition_date=edition_date,
        fetcher=fetcher,
        api_key=api_key.get_secret_value(),
        now=now,
    )


def load_section_extras(session: Session, *, edition_date: date, genre: str) -> SectionExtras:
    """Everything about one genre's extras that isn't part of story
    selection — never personalised, so the caller computes this once per
    genre per run (see the cache in `run_delivery`), not once per reader.

    These were previously computed only at build time (`SectionRenderer`,
    for the public archive) and never reached the actual delivered email —
    a real gap, not a design choice; this closes it.
    """
    top_story = session.scalar(
        select(Story)
        .where(Story.edition_date == edition_date, Story.genre == genre)
        .order_by(Story.pool_rank)
        .limit(1)
    )
    image = None
    if top_story is not None:
        row = session.scalar(select(Image).where(Image.story_id == top_story.id))
        if row is not None:
            image = ImageResult(
                provider=row.provider,
                display_url=row.display_url,
                page_url=row.page_url,
                author=row.author,
                license_name=row.license_name,
                license_url=row.license_url,
                width=row.width,
                height=row.height,
                credit=row.credit,
            )

    return SectionExtras(
        image=image,
        movie_releases=load_movie_releases(session, edition_date=edition_date, genre=genre) or None,
        scores=(load_scores(session, edition_date=edition_date) or None)
        if genre == "sports"
        else None,
        fixtures=(load_fixtures(session, edition_date=edition_date) or None)
        if genre == "sports"
        else None,
        game_deals=(load_game_deals(session, edition_date=edition_date) or None)
        if genre == "gaming"
        else None,
    )


def build_links(
    session: Session, *, user: User, revision: EditionRevision, settings: Settings
) -> Links:
    base = str(settings.base_url).rstrip("/")
    unsubscribe = ensure_unsubscribe_token(session, user.id)
    # Bound to the exact revision this email contained, so the PDF a reader
    # downloads is the edition they were sent, not a later one.
    pdf = sign(PDF, str(revision.id), user=str(user.id))

    return Links(
        unsubscribe_url=f"{base}/unsubscribe/{unsubscribe}",
        # Deliberately tokenless: emailing a login token that lives long enough
        # to be useful is a standing risk. The page issues a magic link instead.
        preferences_url=f"{base}/preferences",
        pdf_url=f"{base}/pdf/{pdf}",
    )


# ------------------------------------------------------------------ the run


def run_delivery(
    session: Session,
    *,
    edition_date: date,
    slot: time,
    sender: Sender,
    renderer: EmailRenderer | None = None,
    settings: Settings | None = None,
    editions: EditionsConfig | None = None,
    weather_fetcher: Fetcher | None = None,
    now: datetime | None = None,
) -> DeliveryReport:
    config = settings or get_settings()
    assemble = renderer or EmailRenderer()
    editions_config = editions or load_editions()
    started = now or now_utc()
    report = DeliveryReport(edition_date=edition_date, slot=slot)

    run = PipelineRun(
        job=JobName.DELIVERY,
        edition_date=edition_date,
        status=RunStatus.RUNNING,
        started_at=started,
    )
    session.add(run)
    # Committed before the loop: a reader with no content triggers a rollback,
    # which would otherwise take the run record with it.
    session.commit()

    revision = latest_revision(session, edition_date)
    if revision is None:
        # Nothing published yet. Readers roll to the next run; after 09:00 the
        # failure-notice job takes over.
        report.errors.append("no published revision")
        _finish(run, RunStatus.FAILED, report)
        session.commit()
        return report

    report.revision = revision.revision
    edition = session.get(Edition, revision.edition_id)
    assert edition is not None

    weekend_content = (
        load_weekend_features(session, edition_date=edition_date)
        if edition.is_weekend
        else WeekendContent()
    )
    quote = load_quote(session, edition_date=edition_date)
    on_this_day = load_on_this_day(session, edition_date=edition_date)
    market = load_market_strip(session, edition_date=edition_date)

    corrections = pending_corrections(session, edition_date=edition_date)
    session.commit()
    corrected_stories = {
        story.id: story
        for story in session.scalars(
            select(Story).where(Story.id.in_([c.story_id for c in corrections]))
        )
    }
    recipients = correction_recipients(session, corrections, corrected_stories)

    # Never personalised — the same image/releases/scores/deals for every
    # reader who gets a given genre this edition_date — so computed once per
    # genre across the whole run, not once per reader.
    extras_cache: dict[str, SectionExtras] = {}

    for user in due_readers(session, slot=slot, on=edition_date):
        delivery = claim(session, user_id=user.id, edition_date=edition_date)
        if delivery is None:
            report.already_done += 1
            continue

        reader = load_reader(session, user)
        candidates = load_candidates(session, edition_date=edition_date, genres=reader.genres)
        selected = select_for_reader(candidates, reader)
        if not selected:
            # Every subscribed genre came up short. No near-empty editions.
            report.no_content += 1
            session.rollback()
            continue

        for genre in selected:
            if genre not in extras_cache:
                extras_cache[genre] = load_section_extras(
                    session, edition_date=edition_date, genre=genre
                )
        section_extras = {genre: extras_cache[genre] for genre in selected}

        links = build_links(session, user=user, revision=revision, settings=config)
        weather = weather_for(
            session,
            user=user,
            edition_date=edition_date,
            fetcher=weather_fetcher,
            settings=config,
            now=started,
        )
        special = (
            editions_config.by_key(edition.special_edition_key)
            if edition.special_edition_key
            else None
        )
        email = assemble.render(
            first_name=reader.first_name,
            edition_date=edition_date,
            edition_number=edition.edition_number,
            selected=selected,
            quiet_genres=quiet_genres(reader, selected),
            links=links,
            weather=weather,
            quote=quote,
            on_this_day=on_this_day,
            market=market,
            section_extras=section_extras,
            # Fall back to the raw key if it no longer matches any configured
            # special edition, rather than silently showing nothing.
            special_edition=special.name if special else edition.special_edition_key,
            special_edition_note=special.note if special else None,
            special_edition_accent=special.accent if special else None,
            corrections=correction_note_for(
                reader, corrections=corrections, recipients=recipients, stories=corrected_stories
            ),
            weekend=weekend_content,
        )

        # The claim is committed before SMTP, so a crash cannot lose it.
        delivery.status = DeliveryStatus.SENDING
        delivery.revision_id = revision.id
        delivery.claimed_at = now_utc()
        delivery.attempts += 1
        session.commit()

        try:
            result = sender.send(
                Message(
                    to=user.email,
                    subject=email.subject,
                    html=email.html,
                    text=email.text,
                    unsubscribe_url=links.unsubscribe_url,
                )
            )
        except SendError as exc:
            delivery.status = DeliveryStatus.FAILED
            delivery.error = str(exc)[:500]
            report.failed += 1
            report.errors.append(f"{type(exc).__name__}")
            session.commit()
            continue

        if result.outcome is SendOutcome.SUPPRESSED:
            # Dev guard, not a failure; it must not look like one in the data.
            delivery.status = DeliveryStatus.SKIPPED
            delivery.error = result.reason
            report.suppressed += 1
        else:
            delivery.status = DeliveryStatus.SENT
            delivery.sent_at = now_utc()
            report.sent += 1
            # A delivered edition ends any outage for this reader, so the
            # notice job starts counting again from zero and a paused reader
            # resumes without anyone intervening.
            clear_outage(session, user.id)
        session.commit()

    _finish(run, RunStatus.SUCCEEDED, report)
    session.commit()
    return report


def _finish(run: PipelineRun, status: RunStatus, report: DeliveryReport) -> None:
    run.status = status
    run.finished_at = now_utc()
    run.detail = {
        "slot": report.slot.isoformat(),
        "revision": report.revision,
        "sent": report.sent,
        "suppressed": report.suppressed,
        "failed": report.failed,
        "already_done": report.already_done,
        "no_content": report.no_content,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send the day's edition to due readers.")
    parser.add_argument("--edition-date", type=date.fromisoformat, default=None)
    parser.add_argument(
        "--slot",
        type=time.fromisoformat,
        default=None,
        help="IST delivery slot this run covers; defaults to the current IST time",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)

    edition_date = args.edition_date or edition_date_for(now_utc())
    slot = args.slot or current_ist_slot()

    # No fetcher at all when there is no key, rather than one that would only
    # ever fail: `weather_for` already treats "no fetcher" as "skip weather".
    weather_fetcher = (
        Fetcher(user_agent=user_agent_for(str(settings.base_url)))
        if settings.openweathermap_api_key is not None
        else None
    )
    try:
        with job_lock(JobName.DELIVERY.value) as acquired:
            if not acquired:
                logger.warning("another delivery run is in progress; exiting")
                return 0
            session = get_sessionmaker()()
            try:
                report = run_delivery(
                    session,
                    edition_date=edition_date,
                    slot=slot,
                    sender=Sender(settings=settings),
                    settings=settings,
                    weather_fetcher=weather_fetcher,
                )
            finally:
                session.close()
    finally:
        if weather_fetcher is not None:
            weather_fetcher.close()
        dispose_engine()

    print(
        f"edition_date={report.edition_date} slot={report.slot} revision={report.revision} "
        f"sent={report.sent} suppressed={report.suppressed} failed={report.failed} "
        f"already_done={report.already_done} no_content={report.no_content}"
    )
    return 0 if not report.failed else 1


def current_ist_slot() -> time:
    """The current IST wall-clock time; Cloud Scheduler aligns runs to slots."""
    return to_ist(now_utc()).time().replace(second=0, microsecond=0)


if __name__ == "__main__":
    sys.exit(main())
