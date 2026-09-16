"""System notices. No LLM, no news data, no build output.

These must render when everything else is broken — that is the entire point of
them — so they take a first name and two links and nothing more. If a notice
template needed today's edition, it could not be sent on the day the edition
failed.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.render.email import BRAND
from app.render.sections import build_environment, text_environment, tidy

FAILURE_SUBJECT = f"{BRAND} — no edition today"
PAUSED_SUBJECT = f"{BRAND} — pausing these notices"


@dataclass(frozen=True)
class RenderedNotice:
    subject: str
    html: str
    text: str


def _render(name: str, subject: str, **context: str) -> RenderedNotice:
    values = {"brand": BRAND, **context}
    return RenderedNotice(
        subject=subject,
        html=build_environment().get_template(f"system/{name}.html.j2").render(**values).strip(),
        text=tidy(text_environment().get_template(f"system/{name}.txt.j2").render(**values)),
    )


def failure_notice(
    *, first_name: str, unsubscribe_url: str, preferences_url: str
) -> RenderedNotice:
    return _render(
        "failure_notice",
        FAILURE_SUBJECT,
        first_name=first_name,
        unsubscribe_url=unsubscribe_url,
        preferences_url=preferences_url,
    )


def paused_notice(*, first_name: str, unsubscribe_url: str, preferences_url: str) -> RenderedNotice:
    return _render(
        "paused_notice",
        PAUSED_SUBJECT,
        first_name=first_name,
        unsubscribe_url=unsubscribe_url,
        preferences_url=preferences_url,
    )
