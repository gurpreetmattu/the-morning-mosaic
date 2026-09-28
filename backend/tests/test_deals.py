"""Game deals: two calls to CheapShark (keyless) per edition_date, cached;
a failed or malformed fetch is omitted, never raised. Genre-scoped, like
movie releases and sports scores/fixtures.
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
from app.services.deals import (
    CHEAPSHARK_DEALS_API,
    CHEAPSHARK_STORES_API,
    fetch_game_deals,
    load_game_deals,
    persist_game_deals,
)
from app.sources.fetch import Fetcher

pytestmark = pytest.mark.integration

EDITION = date(2026, 9, 28)
NOW = datetime(2026, 9, 28, 1, 30, tzinfo=UTC)
DEALS_PATTERN = re.compile(rf"^{re.escape(CHEAPSHARK_DEALS_API)}\?.*")
STORES_PATTERN = re.compile(rf"^{re.escape(CHEAPSHARK_STORES_API)}$")

STORES_PAYLOAD = [
    {"storeID": "1", "storeName": "Steam"},
    {"storeID": "11", "storeName": "Humble Store"},
]


def _deal(
    *,
    title: str,
    store_id: str,
    deal_id: str,
    sale: str = "10.00",
    normal: str = "20.00",
    savings: str = "50.0",
) -> dict[str, str]:
    return {
        "title": title,
        "dealID": deal_id,
        "storeID": store_id,
        "salePrice": sale,
        "normalPrice": normal,
        "savings": savings,
    }


def fetcher() -> Fetcher:
    """No real sleeping: a failing test would otherwise pay full backoff."""
    clock = [0.0]
    return Fetcher(
        user_agent="TheMorningMosaic/0.1 (+test)",
        sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        monotonic=lambda: clock[0],
    )


@respx.mock
def test_deals_are_deduped_by_title_and_capped(session: Session) -> None:
    payload = [
        _deal(title="Game A", store_id="1", deal_id="idA1"),
        _deal(title="Game A", store_id="11", deal_id="idA2"),  # duplicate title -> dropped
        _deal(title="Game B", store_id="1", deal_id="idB"),
        _deal(title="Game C", store_id="1", deal_id="idC"),
        _deal(title="Game D", store_id="1", deal_id="idD"),  # beyond the cap of 3
    ]
    respx.get(DEALS_PATTERN).mock(return_value=httpx.Response(200, json=payload))
    respx.get(STORES_PATTERN).mock(return_value=httpx.Response(200, json=STORES_PAYLOAD))

    deals = fetch_game_deals(fetcher())

    assert [d["title"] for d in deals] == ["Game A", "Game B", "Game C"]
    assert deals[0]["store"] == "Steam"
    assert deals[0]["savings_percent"] == "50"


@respx.mock
def test_an_unknown_store_id_gets_a_generic_label(session: Session) -> None:
    respx.get(DEALS_PATTERN).mock(
        return_value=httpx.Response(
            200, json=[_deal(title="Game A", store_id="999", deal_id="id1")]
        )
    )
    respx.get(STORES_PATTERN).mock(return_value=httpx.Response(200, json=STORES_PAYLOAD))

    deals = fetch_game_deals(fetcher())

    assert deals[0]["store"] == "a participating store"


@respx.mock
def test_a_deal_missing_a_required_field_is_skipped(session: Session) -> None:
    incomplete = _deal(title="Game A", store_id="1", deal_id="id1")
    del incomplete["salePrice"]
    respx.get(DEALS_PATTERN).mock(return_value=httpx.Response(200, json=[incomplete]))
    respx.get(STORES_PATTERN).mock(return_value=httpx.Response(200, json=STORES_PAYLOAD))

    deals = fetch_game_deals(fetcher())

    assert deals == []


@respx.mock
def test_a_fresh_fetch_is_persisted(session: Session) -> None:
    respx.get(DEALS_PATTERN).mock(
        return_value=httpx.Response(200, json=[_deal(title="Game A", store_id="1", deal_id="id1")])
    )
    respx.get(STORES_PATTERN).mock(return_value=httpx.Response(200, json=STORES_PAYLOAD))

    row = persist_game_deals(session, edition_date=EDITION, fetcher=fetcher(), now=NOW)

    assert row is not None
    assert row.kind == ExtraKind.GAME_DEAL
    assert row.genre == "gaming"
    assert load_game_deals(session, edition_date=EDITION)[0]["title"] == "Game A"


@respx.mock
def test_a_rerun_does_not_refetch(session: Session) -> None:
    route = respx.get(DEALS_PATTERN).mock(
        return_value=httpx.Response(200, json=[_deal(title="Game A", store_id="1", deal_id="id1")])
    )
    respx.get(STORES_PATTERN).mock(return_value=httpx.Response(200, json=STORES_PAYLOAD))

    persist_game_deals(session, edition_date=EDITION, fetcher=fetcher(), now=NOW)
    second = persist_game_deals(session, edition_date=EDITION, fetcher=fetcher(), now=NOW)

    assert second is None
    assert route.call_count == 1


@respx.mock
def test_a_failed_fetch_is_omitted_instead_of_raising(session: Session) -> None:
    respx.get(DEALS_PATTERN).mock(return_value=httpx.Response(500))
    respx.get(STORES_PATTERN).mock(return_value=httpx.Response(200, json=STORES_PAYLOAD))

    row = persist_game_deals(session, edition_date=EDITION, fetcher=fetcher(), now=NOW)

    assert row is None
    assert load_game_deals(session, edition_date=EDITION) == []
    rows = session.scalars(select(Extra).where(Extra.edition_date == EDITION)).all()
    assert rows == []


@respx.mock
def test_a_malformed_response_is_omitted_instead_of_raising(session: Session) -> None:
    respx.get(DEALS_PATTERN).mock(return_value=httpx.Response(200, json={"unexpected": True}))
    respx.get(STORES_PATTERN).mock(return_value=httpx.Response(200, json=STORES_PAYLOAD))

    row = persist_game_deals(session, edition_date=EDITION, fetcher=fetcher(), now=NOW)

    assert row is None
