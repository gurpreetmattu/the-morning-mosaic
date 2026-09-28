"""Game deals (a genre extra) for the gaming genre. No LLM: two calls to
CheapShark's free, keyless API per edition_date, persisted once in `extras`
(genre-scoped, like movie releases and sports scores/fixtures).

**Terms: the cleanest of the extras built this session.** CheapShark is a
free, public, no-signup API — the only requirement is a descriptive
User-Agent (a generic one is explicitly rejected, confirmed live). Their own
business model is driving affiliate traffic through exactly this kind of
third-party display, and their terms page carries no redistribution
restriction the way Twelve Data's, Alpha Vantage's, or TMDB's do. CLAUDE.md
also names CheapShark directly as the example provider for this extra, so —
unlike sports and market data — no provider search was needed.

Deals are ranked by CheapShark's own "Deal Rating" (their composite quality
score), not a score invented here, and deduplicated by title, since the same
game's deal at several stores otherwise crowds out real variety in a 3-item
cap.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now_utc
from app.models.content import Extra
from app.models.enums import ExtraKind
from app.sources.fetch import Fetcher, FetchError

logger = logging.getLogger(__name__)

CHEAPSHARK_DEALS_API = "https://www.cheapshark.com/api/1.0/deals"
CHEAPSHARK_STORES_API = "https://www.cheapshark.com/api/1.0/stores"
CHEAPSHARK_REDIRECT = "https://www.cheapshark.com/redirect"
DEALS_SOURCE = "CheapShark"
DEALS_GENRE = "gaming"
DEALS_LIMIT = 3
FETCH_PAGE_SIZE = 15  # over-fetch before deduping by title, then cap at DEALS_LIMIT

# CheapShark rejects a generic client User-Agent outright ("Missing or
# generic User-Agent header detected"), confirmed live — needs its own
# descriptive override, the same mechanism used for the sports API's WAF.
_HEADERS = {"User-Agent": "TheMorningMosaic/0.1 (+https://github.com; daily newsletter)"}


class DealsFetchError(Exception):
    """The deals could not be fetched or did not parse as expected."""


def fetch_game_deals(fetcher: Fetcher) -> list[dict[str, str]]:
    try:
        response = fetcher.get(
            f"{CHEAPSHARK_DEALS_API}?sortBy=Deal%20Rating&pageSize={FETCH_PAGE_SIZE}",
            headers=_HEADERS,
        )
        raw_deals = response.json()
        stores_response = fetcher.get(CHEAPSHARK_STORES_API, headers=_HEADERS)
        stores = {s["storeID"]: s["storeName"] for s in stores_response.json()}
        if not isinstance(raw_deals, list):
            raise TypeError(f"expected a list of deals, got {type(raw_deals).__name__}")
    except (FetchError, KeyError, TypeError, ValueError) as exc:
        raise DealsFetchError(f"game deals: {exc}") from exc

    deals: list[dict[str, str]] = []
    seen_titles: set[str] = set()
    for item in raw_deals:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        deal_id = item.get("dealID")
        sale_price = item.get("salePrice")
        normal_price = item.get("normalPrice")
        savings = item.get("savings")
        if not (title and deal_id and sale_price and normal_price and savings):
            continue
        if title in seen_titles:
            continue
        seen_titles.add(title)
        try:
            savings_percent = round(float(savings))
        except (TypeError, ValueError):
            continue
        deals.append(
            {
                "title": str(title),
                "sale_price": str(sale_price),
                "normal_price": str(normal_price),
                "savings_percent": str(savings_percent),
                "store": stores.get(str(item.get("storeID")), "a participating store"),
                # CheapShark's dealID is already URL-encoded in the API's
                # own response (confirmed live) — re-encoding it here would
                # double-encode and break the redirect.
                "url": f"{CHEAPSHARK_REDIRECT}?dealID={deal_id}",
            }
        )
        if len(deals) >= DEALS_LIMIT:
            break
    return deals


def _existing(session: Session, *, edition_date: date) -> Extra | None:
    return session.scalar(
        select(Extra).where(
            Extra.edition_date == edition_date,
            Extra.kind == ExtraKind.GAME_DEAL,
            Extra.genre == DEALS_GENRE,
        )
    )


def persist_game_deals(
    session: Session, *, edition_date: date, fetcher: Fetcher, now: datetime | None = None
) -> Extra | None:
    """Fetch and store today's game deals, once per edition_date.

    Never raises — a missing item is acceptable, same posture as every
    other extra.
    """
    if _existing(session, edition_date=edition_date) is not None:
        return None

    try:
        deals = fetch_game_deals(fetcher)
    except DealsFetchError:
        logger.warning("game deals fetch failed", exc_info=True)
        return None
    if not deals:
        return None

    row = Extra(
        edition_date=edition_date,
        kind=ExtraKind.GAME_DEAL,
        genre=DEALS_GENRE,
        payload={"items": deals},
        source_name=DEALS_SOURCE,
        source_url="https://www.cheapshark.com/",
        data_at=now or now_utc(),
    )
    session.add(row)
    session.flush()
    return row


def load_game_deals(session: Session, *, edition_date: date) -> list[dict[str, str]]:
    row = _existing(session, edition_date=edition_date)
    return row.payload["items"] if row is not None else []
