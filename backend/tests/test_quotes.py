"""Quote of the day and "On this day": both fetched from public wiki feeds,
no LLM, cached once per edition_date; a failed or malformed fetch is simply
omitted, never raised.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import Extra
from app.models.enums import ExtraKind
from app.render.email import OnThisDay, Quote
from app.services.quotes import (
    WIKIPEDIA_ONTHISDAY_API,
    WIKIQUOTE_API,
    load_on_this_day,
    load_quote,
    persist_daily_extras,
)
from app.sources.fetch import Fetcher

pytestmark = pytest.mark.integration

EDITION = date(2026, 9, 28)
NOW = datetime(2026, 9, 28, 1, 30, tzinfo=UTC)
QUOTE_URL_PATTERN = re.compile(rf"^{re.escape(WIKIQUOTE_API)}\?.*")
OTD_URL_PATTERN = re.compile(rf"^{re.escape(WIKIPEDIA_ONTHISDAY_API)}/09/28$")

QUOTE_WIKITEXT = (
    "{{Wikiquote:Quote of the day/Template\n"
    "| quote = <!-- note --> [[Shakespeare]]'s stage <br /> holds the glass\n"
    "| author = Francis Turner Palgrave\n"
    "}}"
)

ONTHISDAY_PAYLOAD = {
    "selected": [
        {
            "year": 2023,
            "text": "The Sycamore Gap tree was illegally felled.",
            "pages": [{"title": "Sycamore_Gap_tree"}],
        }
    ]
}


def fetcher() -> Fetcher:
    """No real sleeping: a failing test would otherwise pay full backoff."""
    clock = [0.0]
    return Fetcher(
        user_agent="TheMorningMosaic/0.1 (+test)",
        sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        monotonic=lambda: clock[0],
    )


def extras(session: Session) -> list[Extra]:
    return list(session.scalars(select(Extra).where(Extra.edition_date == EDITION)))


@respx.mock
def test_both_extras_are_fetched_and_persisted(session: Session) -> None:
    respx.get(QUOTE_URL_PATTERN).mock(
        return_value=httpx.Response(200, json={"parse": {"wikitext": {"*": QUOTE_WIKITEXT}}})
    )
    respx.get(OTD_URL_PATTERN).mock(return_value=httpx.Response(200, json=ONTHISDAY_PAYLOAD))

    persisted = persist_daily_extras(session, edition_date=EDITION, fetcher=fetcher(), now=NOW)

    assert {row.kind for row in persisted} == {ExtraKind.QUOTE, ExtraKind.ON_THIS_DAY}
    assert {row.kind for row in extras(session)} == {ExtraKind.QUOTE, ExtraKind.ON_THIS_DAY}

    quote = load_quote(session, edition_date=EDITION)
    assert quote == Quote(
        text="Shakespeare's stage holds the glass",
        author="Francis Turner Palgrave",
        source_url="https://en.wikiquote.org/wiki/Wikiquote:Quote_of_the_day/September_28,_2026",
    )

    fact = load_on_this_day(session, edition_date=EDITION)
    assert fact == OnThisDay(
        year=2023,
        text="The Sycamore Gap tree was illegally felled.",
        source_url="https://en.wikipedia.org/wiki/Sycamore_Gap_tree",
    )


@respx.mock
def test_a_rerun_does_not_refetch_an_already_persisted_kind(session: Session) -> None:
    quote_route = respx.get(QUOTE_URL_PATTERN).mock(
        return_value=httpx.Response(200, json={"parse": {"wikitext": {"*": QUOTE_WIKITEXT}}})
    )
    respx.get(OTD_URL_PATTERN).mock(return_value=httpx.Response(200, json=ONTHISDAY_PAYLOAD))

    persist_daily_extras(session, edition_date=EDITION, fetcher=fetcher(), now=NOW)
    second = persist_daily_extras(session, edition_date=EDITION, fetcher=fetcher(), now=NOW)

    assert second == []
    assert quote_route.call_count == 1
    assert len(extras(session)) == 2


@respx.mock
def test_a_failed_quote_fetch_is_omitted_without_blocking_on_this_day(session: Session) -> None:
    respx.get(QUOTE_URL_PATTERN).mock(return_value=httpx.Response(500))
    respx.get(OTD_URL_PATTERN).mock(return_value=httpx.Response(200, json=ONTHISDAY_PAYLOAD))

    persisted = persist_daily_extras(session, edition_date=EDITION, fetcher=fetcher(), now=NOW)

    assert {row.kind for row in persisted} == {ExtraKind.ON_THIS_DAY}
    assert load_quote(session, edition_date=EDITION) is None
    assert load_on_this_day(session, edition_date=EDITION) is not None


@respx.mock
def test_a_malformed_response_is_omitted_instead_of_raising(session: Session) -> None:
    respx.get(QUOTE_URL_PATTERN).mock(
        return_value=httpx.Response(200, json={"parse": {"wikitext": {"*": "no params here"}}})
    )
    respx.get(OTD_URL_PATTERN).mock(return_value=httpx.Response(200, json={"selected": []}))

    persisted = persist_daily_extras(session, edition_date=EDITION, fetcher=fetcher(), now=NOW)

    assert persisted == []
    assert extras(session) == []
