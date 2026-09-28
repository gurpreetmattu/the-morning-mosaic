"""Market strip (part of agent 8/Layout's extras). No LLM: one HTTP call to
Frankfurter, persisted once per edition_date in `extras` — never fetched or
re-fetched per reader.

**Scope, and why it's narrower than CLAUDE.md's "market strip" implies:**
CLAUDE.md envisions Nifty/Sensex. Both commercial providers checked for this
(Twelve Data, Alpha Vantage) were read directly, not assumed, and both
explicitly prohibit redistributing quotes to third parties — i.e. putting
them in a newsletter — on their free tiers without a paid add-on (Twelve
Data: a separate "Redistribution Rights Add-On"; Alpha Vantage: its free
license is "personal, non-commercial use" and defines "commercial use" to
include anything that "allows individuals or entities other than User to
access information"). Neither is usable here without paying for that right.

Frankfurter (MIT-licensed, no API key, serving the European Central Bank's
own daily reference rates) is the one source found with an explicit, useable
permission: the ECB's own copyright notice states "users of this website may
make free use of the information obtained directly from it," conditioned
only on accurate reproduction and citing the ECB as the source. That covers
currency rates only — no equity indices, no commodities — so this is
USD/INR alone. Nifty/Sensex/gold stay unbuilt until a provider with
equivalent terms is found or a paid redistribution right is purchased; see
docs/BACKLOG.md.

ECB publishes once per business day (~16:00 CET) and not on weekends or
TARGET holidays; Frankfurter's own "latest" endpoint already returns the
last published business day's rate with its own date on those days, so
CLAUDE.md's "on market holidays and weekends it shows the last close with
its date" falls out of simply showing the API's own returned date — no
custom weekend/holiday handling needed here.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now_utc
from app.models.content import Extra
from app.models.enums import ExtraKind
from app.render.email import MarketStrip
from app.sources.fetch import Fetcher, FetchError

logger = logging.getLogger(__name__)

FRANKFURTER_API = "https://api.frankfurter.dev/v1/latest"
MARKET_SOURCE = "European Central Bank (via Frankfurter)"
MARKET_LABEL = "USD/INR"


class MarketFetchError(Exception):
    """The rate could not be fetched or did not parse as expected."""


def fetch_market_strip(fetcher: Fetcher) -> MarketStrip:
    url = f"{FRANKFURTER_API}?base=USD&symbols=INR"
    try:
        response = fetcher.get(url)
        data = response.json()
        rate = float(data["rates"]["INR"])
        as_of = date.fromisoformat(data["date"])
    except (FetchError, KeyError, TypeError, ValueError) as exc:
        raise MarketFetchError(f"market strip: {exc}") from exc

    return MarketStrip(
        label=MARKET_LABEL,
        rate=rate,
        as_of=as_of,
        source_url="https://www.ecb.europa.eu/stats/policy_and_exchange_rates/"
        "euro_reference_exchange_rates/html/index.en.html",
    )


def _existing(session: Session, *, edition_date: date) -> Extra | None:
    return session.scalar(
        select(Extra).where(Extra.edition_date == edition_date, Extra.kind == ExtraKind.MARKET)
    )


def persist_market_strip(
    session: Session, *, edition_date: date, fetcher: Fetcher, now: datetime | None = None
) -> Extra | None:
    """Fetch and store today's USD/INR rate, once.

    Safe to rerun: an already-persisted rate for this edition_date is left
    alone rather than re-fetched. A failed fetch is simply omitted, same
    posture as every other extra.
    """
    if _existing(session, edition_date=edition_date) is not None:
        return None

    try:
        strip = fetch_market_strip(fetcher)
    except MarketFetchError:
        logger.warning("market strip fetch failed", exc_info=True)
        return None

    row = Extra(
        edition_date=edition_date,
        kind=ExtraKind.MARKET,
        payload={"label": strip.label, "rate": strip.rate, "as_of": strip.as_of.isoformat()},
        source_name=MARKET_SOURCE,
        source_url=strip.source_url,
        data_at=now or now_utc(),
    )
    session.add(row)
    session.flush()
    return row


def load_market_strip(session: Session, *, edition_date: date) -> MarketStrip | None:
    row = _existing(session, edition_date=edition_date)
    if row is None:
        return None
    return MarketStrip(
        label=row.payload["label"],
        rate=row.payload["rate"],
        as_of=date.fromisoformat(row.payload["as_of"]),
        source_url=row.source_url,
    )
