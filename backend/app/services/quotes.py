"""Quote of the day and "On this day" (part of agent 8/Layout's extras). No
LLM: both come from Wikiquote and Wikipedia's own public feeds and are
persisted once per edition_date, in `extras`, the same day every reader's
copy is assembled from — never fetched or re-fetched per reader.

CC BY-SA — both are attributed in the rendered email, with a link back to the
source page, per CLAUDE.md's Data sources section.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from urllib.parse import quote as urlquote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now_utc
from app.models.content import Extra
from app.models.enums import ExtraKind
from app.render.email import OnThisDay, Quote
from app.sources.fetch import Fetcher, FetchError

logger = logging.getLogger(__name__)

WIKIQUOTE_API = "https://en.wikiquote.org/w/api.php"
WIKIQUOTE_SOURCE = "Wikiquote"
WIKIPEDIA_ONTHISDAY_API = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/selected"
WIKIPEDIA_SOURCE = "Wikipedia"

# `| key = value` lines inside a MediaWiki template call. Values are assumed
# to sit on a single line (true of every Quote of the day page checked) —
# a value that genuinely spans lines fails to parse, which is treated as
# "no reliable source today" rather than guessed at.
_PARAM_LINE = re.compile(r"^\|\s*(\w+)\s*=\s*(.*)$", re.MULTILINE)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_BR_TAG = re.compile(r"<br\s*/?>", re.IGNORECASE)
_PIPED_LINK = re.compile(r"\[\[[^\]|]*\|([^\]]+)\]\]")
_PLAIN_LINK = re.compile(r"\[\[([^\]|]+)\]\]")


class ExtraFetchError(Exception):
    """The reading could not be fetched or did not parse as expected."""


def _clean_wikitext(value: str) -> str:
    value = _HTML_COMMENT.sub("", value)
    value = _BR_TAG.sub(" ", value)
    value = _PIPED_LINK.sub(r"\1", value)
    value = _PLAIN_LINK.sub(r"\1", value)
    value = value.replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", value).strip()


def _quote_page_title(edition_date: date) -> str:
    return f"Wikiquote:Quote of the day/{edition_date:%B} {edition_date.day}, {edition_date.year}"


def fetch_quote_of_the_day(fetcher: Fetcher, *, edition_date: date) -> Quote:
    title = _quote_page_title(edition_date)
    url = f"{WIKIQUOTE_API}?action=parse&page={urlquote(title)}&format=json&prop=wikitext"
    try:
        response = fetcher.get(url)
        wikitext = response.json()["parse"]["wikitext"]["*"]
    except (FetchError, KeyError, TypeError) as exc:
        raise ExtraFetchError(f"quote of the day: {exc}") from exc

    params = dict(_PARAM_LINE.findall(wikitext))
    if not params.get("quote") or not params.get("author"):
        raise ExtraFetchError("quote of the day: no quote/author field in the day's page")

    return Quote(
        text=_clean_wikitext(params["quote"]),
        author=_clean_wikitext(params["author"]),
        source_url=f"https://en.wikiquote.org/wiki/{title.replace(' ', '_')}",
    )


def fetch_on_this_day(fetcher: Fetcher, *, edition_date: date) -> OnThisDay:
    url = f"{WIKIPEDIA_ONTHISDAY_API}/{edition_date:%m}/{edition_date:%d}"
    try:
        response = fetcher.get(url)
        selected = response.json()["selected"]
        # The feed's own ordering is curated by significance; the first entry
        # is the one Wikipedia itself leads with.
        first = selected[0]
        year = int(first["year"])
        text = str(first["text"])
        pages = first.get("pages") or []
        page_title = pages[0]["title"] if pages else None
    except (FetchError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise ExtraFetchError(f"on this day: {exc}") from exc

    source_url = (
        f"https://en.wikipedia.org/wiki/{page_title}"
        if page_title
        else "https://en.wikipedia.org/wiki/Portal:Current_events"
    )
    return OnThisDay(year=year, text=text, source_url=source_url)


def _existing(session: Session, *, edition_date: date, kind: ExtraKind) -> Extra | None:
    return session.scalar(
        select(Extra).where(Extra.edition_date == edition_date, Extra.kind == kind)
    )


def persist_daily_extras(
    session: Session, *, edition_date: date, fetcher: Fetcher, now: datetime | None = None
) -> list[Extra]:
    """Fetch and store today's quote and "on this day" fact, once.

    Safe to rerun: a kind already persisted for this edition_date is left
    alone rather than re-fetched — the content does not change during the
    day, and a rerun should not risk losing a morning's good reading to an
    afternoon's transient failure. A kind that fails to fetch is simply
    omitted, same as any other extra with no reliable source today.
    """
    persisted: list[Extra] = []
    stamp = now or now_utc()

    if _existing(session, edition_date=edition_date, kind=ExtraKind.QUOTE) is None:
        try:
            quote = fetch_quote_of_the_day(fetcher, edition_date=edition_date)
        except ExtraFetchError:
            logger.warning("quote of the day fetch failed", exc_info=True)
        else:
            row = Extra(
                edition_date=edition_date,
                kind=ExtraKind.QUOTE,
                payload={"text": quote.text, "author": quote.author},
                source_name=WIKIQUOTE_SOURCE,
                source_url=quote.source_url,
                data_at=stamp,
            )
            session.add(row)
            persisted.append(row)

    if _existing(session, edition_date=edition_date, kind=ExtraKind.ON_THIS_DAY) is None:
        try:
            fact = fetch_on_this_day(fetcher, edition_date=edition_date)
        except ExtraFetchError:
            logger.warning('"on this day" fetch failed', exc_info=True)
        else:
            row = Extra(
                edition_date=edition_date,
                kind=ExtraKind.ON_THIS_DAY,
                payload={"year": fact.year, "text": fact.text},
                source_name=WIKIPEDIA_SOURCE,
                source_url=fact.source_url,
                data_at=stamp,
            )
            session.add(row)
            persisted.append(row)

    session.flush()
    return persisted


def load_quote(session: Session, *, edition_date: date) -> Quote | None:
    row = _existing(session, edition_date=edition_date, kind=ExtraKind.QUOTE)
    if row is None:
        return None
    return Quote(text=row.payload["text"], author=row.payload["author"], source_url=row.source_url)


def load_on_this_day(session: Session, *, edition_date: date) -> OnThisDay | None:
    row = _existing(session, edition_date=edition_date, kind=ExtraKind.ON_THIS_DAY)
    if row is None:
        return None
    return OnThisDay(year=row.payload["year"], text=row.payload["text"], source_url=row.source_url)
