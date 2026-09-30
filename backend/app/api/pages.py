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

# Colours mirror frontend/design/tokens.json (Morning and Late editions). These
# pages carry a strict CSP: no scripts and no web fonts, so type falls back to
# system serifs and sans. Backlog: generate this block from tokens.json.
_SHELL = """<!doctype html>
<html lang="en-IN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{title} — {brand}</title>
<style>
  :root {{ --paper:#F0E6CB; --raised:#F8F0DC; --ink:#1C1915; --soft:#40382C; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --paper:#1A150F; --raised:#241D15; --ink:#F0E4C8; --soft:#D2C5A8; }}
  }}
  body {{ margin:0; background:var(--paper); color:var(--ink);
    font-family:Georgia,"Times New Roman",serif; }}
  .sheet {{ max-width:520px; margin:40px auto; padding:28px 28px 32px;
    background:var(--raised); border:2px solid var(--ink);
    box-shadow:6px 6px 0 var(--ink); }}
  .dateline {{ margin:0 0 6px; letter-spacing:.14em; text-transform:uppercase;
    font:700 11px/1.2 "Franklin Gothic Medium","Arial Narrow",Arial,sans-serif;
    color:var(--soft); }}
  .brand {{ margin:0; padding-bottom:10px; border-bottom:4px double var(--ink);
    font:700 34px/1 Georgia,"Times New Roman",serif; letter-spacing:-.01em; }}
  h2 {{ margin:18px 0 10px; font-size:22px; font-weight:700; line-height:1.2; }}
  p {{ margin:0; font-size:16px; line-height:1.65; color:var(--soft); }}
  form {{ margin:24px 0 0; }}
  button {{ min-height:48px; padding:10px 22px; border:2px solid var(--ink);
    background:var(--ink); color:var(--paper); box-shadow:3px 3px 0 var(--soft);
    font:700 15px "Franklin Gothic Medium",Arial,sans-serif; letter-spacing:.06em;
    text-transform:uppercase; cursor:pointer; }}
  button:hover {{ transform:translate(-1px,-1px); box-shadow:4px 4px 0 var(--soft); }}
  button:active {{ transform:translate(3px,3px); box-shadow:none; }}
  button:focus-visible {{ outline:3px solid var(--ink); outline-offset:3px; }}
  @media (prefers-reduced-motion: reduce) {{
    button:hover, button:active {{ transform:none; }}
  }}
</style></head>
<body>
<main class="sheet">
  <p class="dateline">Morning Edition</p>
  <h1 class="brand">{brand}</h1>
  <h2>{title}</h2>
  <p>{body}</p>
  {action}
</main></body></html>
"""

_FORM = """<form method="post" action="{action}">
  <button type="submit">{label}</button>
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
