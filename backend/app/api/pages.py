"""The small HTML pages a reader lands on from an email link.

These exist because of link-scanner safety: the GET behind every emailed link
only renders one of these, and the action happens when the reader presses the
button, which POSTs. A scanner that opens the link sees a page and changes
nothing.

Deliberately script-free and self-contained, which is what lets the response
carry a Content-Security-Policy of `default-src 'none'`.
"""

from __future__ import annotations

from html import escape

from fastapi.responses import HTMLResponse

BRAND = "The Morning Mosaic"

_SHELL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — {brand}</title></head>
<body style="margin:0;padding:0;background:#f4f2ee;font-family:Georgia,serif;">
<div style="max-width:520px;margin:48px auto;padding:32px;background:#fff;">
  <h1 style="margin:0 0 6px;font-size:26px;color:#141414;">{brand}</h1>
  <h2 style="margin:0 0 18px;font-size:18px;font-weight:normal;color:#5a5a5a;">{title}</h2>
  <p style="font-size:15px;line-height:1.6;color:#242424;">{body}</p>
  {action}
</div></body></html>
"""

_FORM = """<form method="post" action="{action}" style="margin:22px 0 0;">
  <button type="submit" style="padding:11px 20px;font-family:Georgia,serif;
    font-size:15px;color:#fff;background:#141414;border:0;cursor:pointer;">
    {label}
  </button>
</form>"""


def page(
    *,
    title: str,
    body: str,
    action: str | None = None,
    label: str = "Confirm",
    status_code: int = 200,
) -> HTMLResponse:
    """Render a page, with an optional button that POSTs to `action`."""
    form = _FORM.format(action=escape(action), label=escape(label)) if action else ""
    return HTMLResponse(
        _SHELL.format(
            brand=escape(BRAND),
            title=escape(title),
            body=escape(body),
            action=form,
        ),
        status_code=status_code,
    )


def confirm(*, title: str, body: str, action: str, label: str) -> HTMLResponse:
    return page(title=title, body=body, action=action, label=label)


def done(*, title: str, body: str) -> HTMLResponse:
    return page(title=title, body=body)


def gone(*, title: str, body: str) -> HTMLResponse:
    """A link that is expired, already used, or not recognised.

    Always 400 and always the same shape, so a scanner or a stranger cannot
    learn from the response whether a token was ever real.
    """
    return page(title=title, body=body, status_code=400)
