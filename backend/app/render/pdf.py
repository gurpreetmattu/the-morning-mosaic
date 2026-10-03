"""Per-user PDF assembly. No LLM, and — past the first render — no re-rendering.

A reader's PDF is one document: their personalised cover, then the
`EditionSection.html` of each genre they subscribe to, in order. Those
sections are the same already-verified, already-published bytes every reader
of that genre gets in the archive and the email; nothing here changes a word.

It is laid out as ONE document, not one PDF per genre merged afterwards, so a
genre can start part-way down the page where the previous one ended instead of
leaving the rest of that page blank. The cost is that a reader's first
download lays out their whole edition rather than concatenating cached genre
pages; the finished PDF is cached per (revision, reader), so every download
after the first is a plain read. The cover's page numbers come from
WeasyPrint's `target-counter`, so they are the real ones, not an estimate.

WeasyPrint needs system libraries (GTK/Pango) this environment does not have
— see docs/BACKLOG.md — so it is imported lazily, only inside the function
that actually calls it, and that function is swappable exactly like
`Sender`'s SMTP transport: callers depend on `PdfRenderer`, a plain
`str -> bytes` callable, not on WeasyPrint itself.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from html import escape

from app.render import PALETTE

BRAND = "The Morning Mosaic"
TAGLINE = "The morning paper, set to your interests."

PdfRenderer = Callable[[str], bytes]

# The page carries the same newsprint tint as the email and the website, so
# the PDF reads as the same publication rather than a different document.
# `paper_raised` is the email's card colour; the section fragments already
# paint it themselves, and the @page background keeps the margins matching.
_PAGE_CSS = (
    """
  @page {{
    size: A4; margin: 22mm 18mm 26mm 18mm; background: {paper};
    @top-left {{ content: "{brand}"; font: 8pt {mono}; color: {ink_muted}; }}
    @bottom-center {{
      content: "Every fact comes from the sources linked beneath each story.";
      font: 8pt {sans}; color: {ink_muted};
    }}
  }}
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: {serif}; color: {ink}; background: {paper}; }}
  /* Section fragments are inline-styled for a 600px email: screen-sized type
     and stories that refuse to split across pages. On A4 that leaves pages
     a third empty, so print overrides both (hence !important). */
  article {{ break-inside: auto !important; page-break-inside: auto !important;
             margin-bottom: 14px !important; padding-bottom: 12px !important; }}
  article h3 {{ font-size: 17px !important; line-height: 1.25 !important;
                break-after: avoid; page-break-after: avoid; }}
  article p {{ font-size: 12.5px !important; line-height: 1.5 !important;
               orphans: 3; widows: 3; }}
  article p:last-child {{ break-before: avoid; }}
  /* "Why this matters" is the bordered paragraph; keep it with the summary. */
  article p[style*="border-left"] {{ break-before: avoid; page-break-before: avoid; }}
  /* A tall hotlinked photo is an unsplittable block: if it does not fit, it and the
     heading kept with it jump to the next page, leaving the previous one part empty. */
  section img {{ width: 100% !important; height: 55mm !important; object-fit: cover; }}
  /* The credit is legally part of the photo: never split them across pages. */
  section img {{ break-after: avoid; page-break-after: avoid; }}
  section img + span {{ break-before: avoid; page-break-before: avoid; }}
  section h2 {{ break-after: avoid; page-break-after: avoid; }}
  section h2 + p {{ break-after: avoid; page-break-after: avoid; }}
"""
).format(
    brand=BRAND,
    mono=PALETTE["mono"].replace("'", ""),
    sans=PALETTE["sans"],
    serif=PALETTE["serif"],
    ink=PALETTE["ink"],
    ink_muted=PALETTE["ink_muted"],
    paper=PALETTE["paper_raised"],
)

_COVER_CSS = """
  .cover {{ height: 245mm; border: 2px solid {ink}; background: {paper};
            break-after: page; page-break-after: always; }}
  .dateline {{ padding: 8px 20px; border-bottom: 1px solid {ink};
               font: 12px {mono}; color: {ink_soft}; }}
  .nameplate {{ text-align: center; padding: 150px 20px 10px; }}
  /* WeasyPrint has no text-shadow, so the email's red offset shadow is a
     second copy of the title, nudged down and right, behind the first. */
  .title {{ position: relative; display: inline-block; font: bold 46px/1.05 {serif};
            letter-spacing: -0.5px; margin: 0; white-space: nowrap; }}
  .title .shadow {{ position: absolute; left: 2px; top: 2px; color: {press_red};
                    white-space: nowrap; }}
  .title .front {{ position: relative; color: {ink}; }}
  .tagline {{ text-align: center; padding: 0 20px 12px; border-bottom: 4px double {ink};
              font: italic 15px {serif}; color: {ink_soft}; margin: 0 20px; }}
  .curated {{ text-align: center; margin-top: 44px; }}
  .curated span {{ display: inline-block; padding: 6px 12px; border: 2px solid {ink};
                   font: bold 12px {sans}; letter-spacing: 0.14em; text-transform: uppercase; }}
  .contents {{ margin: 56px 40px 0; }}
  .contents h2 {{ font: bold 12px {sans}; letter-spacing: 0.14em; text-transform: uppercase;
                  margin: 0 0 8px; padding-bottom: 6px; border-bottom: 1px solid {ink}; }}
  .contents .row {{ display: flex; justify-content: space-between; align-items: baseline;
                    padding: 9px 0; border-bottom: 1px dotted {ink}; }}
  .contents .page {{ color: inherit; text-decoration: none; }}
  .contents .name {{ font: bold 17px {serif}; }}
  .contents .blurb {{ font: italic 12px {serif}; color: {ink_soft}; margin: 2px 0 0; }}
  .contents .page::after {{ content: target-counter(attr(href url), page);
                            font: 14px {mono}; color: {ink_soft}; }}
"""

_COVER_BODY = """<div class="cover">
  <div class="dateline">{date_label} &middot; Edition {edition_number}</div>
  <div class="nameplate">
    <h1 class="title"><span class="shadow">{brand}</span><span class="front">{brand}</span></h1>
  </div>
  <p class="tagline">{tagline}</p>
  <div class="curated"><span>Curated for {first_name}</span></div>
  {contents}
</div>"""

_DOCUMENT = """<!doctype html>
<html lang="en-IN"><head><meta charset="utf-8"><style>{css}{cover_css}</style></head>
<body>{body}</body></html>"""


def weasyprint_renderer(html: str) -> bytes:
    """The real renderer. Verified inside the backend image; see docs/BACKLOG.md."""
    from weasyprint import HTML  # heavy import, touched only for a real render

    pdf_bytes: bytes = HTML(string=html).write_pdf()
    return pdf_bytes


def date_label(edition_date: date) -> str:
    return f"{edition_date:%A}, {edition_date.day} {edition_date:%B} {edition_date.year}"


@dataclass(frozen=True)
class PdfSection:
    """One genre of a reader's edition: its heading data and stored HTML."""

    genre: str
    title: str
    blurb: str
    html: str


def _anchor(genre: str) -> str:
    return f"genre-{genre}"


def _contents_html(sections: Sequence[PdfSection]) -> str:
    if not sections:
        return ""
    rows = "".join(
        f'<div class="row"><div><span class="name">{escape(s.title)}</span>'
        f'<p class="blurb">{escape(s.blurb)}</p></div>'
        f'<a class="page" href="#{escape(_anchor(s.genre))}"></a></div>'
        for s in sections
    )
    return f'<div class="contents"><h2>In this edition</h2>{rows}</div>'


def edition_html(
    *,
    first_name: str,
    edition_date: date,
    edition_number: int,
    sections: Sequence[PdfSection],
) -> str:
    """The whole reader's edition as one HTML document.

    Section HTML is not escaped: it is our own stored, previously-escaped
    output (see `render/sections.py`), not raw input. Everything else here is.
    """
    cover = _COVER_BODY.format(
        date_label=escape(date_label(edition_date)),
        edition_number=edition_number,
        brand=escape(BRAND),
        tagline=escape(TAGLINE),
        first_name=escape(first_name),
        contents=_contents_html(sections),
    )
    body = cover + "".join(f'<div id="{escape(_anchor(s.genre))}">{s.html}</div>' for s in sections)
    cover_css = _COVER_CSS.format(
        ink=PALETTE["ink"],
        ink_soft=PALETTE["ink_soft"],
        paper=PALETTE["paper_raised"],
        press_red=PALETTE["press_red"],
        mono=PALETTE["mono"],
        sans=PALETTE["sans"],
        serif=PALETTE["serif"],
    )
    return _DOCUMENT.format(css=_PAGE_CSS, cover_css=cover_css, body=body)


@dataclass(frozen=True)
class PdfAssembler:
    render_html: PdfRenderer = field(default=weasyprint_renderer)

    def render_edition(
        self,
        *,
        first_name: str,
        edition_date: date,
        edition_number: int,
        sections: Sequence[PdfSection],
    ) -> bytes:
        return self.render_html(
            edition_html(
                first_name=first_name,
                edition_date=edition_date,
                edition_number=edition_number,
                sections=sections,
            )
        )
