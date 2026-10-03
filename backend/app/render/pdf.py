"""Per-user PDF assembly. No LLM, and — past the first render — no re-rendering.

CLAUDE.md: "Genre pages rendered once per revision; per-user PDFs assembled
on first download." The two halves are deliberately different operations:

- A genre page comes straight from `EditionSection.html`, the same
  already-verified, already-published bytes every reader of that genre gets
  in the archive and the email. Turning it into a PDF page is pure layout —
  WeasyPrint wraps it in an A4 page and paginates it — so it happens once per
  revision and is cached by (revision, genre).
- Assembling one reader's PDF is concatenation: their personalised cover
  page plus whichever of those already-rendered genre pages they subscribe
  to, in order. Nothing here re-lays-out a genre page per reader, which is
  what makes "on first download" cheap for every download after the first.

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
from io import BytesIO

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
  html, body {{ margin: 0; padding: 0; height: 100%; }}
  body {{ font-family: {serif}; color: {ink}; background: {paper}; }}
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

_SHELL = """<!doctype html>
<html lang="en-IN"><head><meta charset="utf-8"><style>{css}</style></head>
<body>{body}</body></html>"""

_COVER = """<!doctype html>
<html lang="en-IN"><head><meta charset="utf-8"><style>{css}
  .cover {{ height: 100%; border: 2px solid {ink}; background: {paper}; }}
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
  .curated {{ text-align: center; margin-top: 56px; }}
  .curated span {{ display: inline-block; padding: 6px 12px; border: 2px solid {ink};
                   font: bold 12px {sans}; letter-spacing: 0.14em; text-transform: uppercase; }}
</style></head>
<body><div class="cover">
  <div class="dateline">{date_label} &middot; Edition {edition_number}</div>
  <div class="nameplate">
    <h1 class="title"><span class="shadow">{brand}</span><span class="front">{brand}</span></h1>
  </div>
  <p class="tagline">{tagline}</p>
  <div class="curated"><span>Curated for {first_name}</span></div>
</div></body></html>"""


def weasyprint_renderer(html: str) -> bytes:
    """The real renderer. Untested on this machine; see docs/BACKLOG.md."""
    from weasyprint import HTML  # heavy import, touched only for a real render

    pdf_bytes: bytes = HTML(string=html).write_pdf()
    return pdf_bytes


def date_label(edition_date: date) -> str:
    return f"{edition_date:%A}, {edition_date.day} {edition_date:%B} {edition_date.year}"


def cover_html(*, first_name: str, edition_date: date, edition_number: int) -> str:
    return _COVER.format(
        css=_PAGE_CSS,
        ink=PALETTE["ink"],
        ink_soft=PALETTE["ink_soft"],
        paper=PALETTE["paper_raised"],
        press_red=PALETTE["press_red"],
        mono=PALETTE["mono"],
        sans=PALETTE["sans"],
        serif=PALETTE["serif"],
        brand=escape(BRAND),
        tagline=escape(TAGLINE),
        first_name=escape(first_name),
        date_label=escape(date_label(edition_date)),
        edition_number=edition_number,
    )


def page_html(section_html: str) -> str:
    """Wrap an already-rendered, already-trusted section fragment for print.

    Not escaped: `section_html` is our own stored, previously-escaped output
    (see `render/sections.py`), not raw input.
    """
    return _SHELL.format(css=_PAGE_CSS, body=section_html)


def merge_pdfs(parts: Sequence[bytes]) -> bytes:
    """Concatenate whole PDFs, page by page, in order."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for part in parts:
        reader = PdfReader(BytesIO(part))
        for page in reader.pages:
            writer.add_page(page)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@dataclass(frozen=True)
class PdfAssembler:
    render_html: PdfRenderer = field(default=weasyprint_renderer)

    def render_section(self, section_html: str) -> bytes:
        return self.render_html(page_html(section_html))

    def render_cover(self, *, first_name: str, edition_date: date, edition_number: int) -> bytes:
        html = cover_html(
            first_name=first_name, edition_date=edition_date, edition_number=edition_number
        )
        return self.render_html(html)

    def assemble(self, *, cover: bytes, sections: Sequence[bytes]) -> bytes:
        return merge_pdfs([cover, *sections])
