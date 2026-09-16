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

BRAND = "The Morning Mosaic"
TAGLINE = "India's morning, in the pieces that matter."

PdfRenderer = Callable[[str], bytes]

_PAGE_CSS = """
  @page { size: A4; margin: 22mm 18mm 26mm 18mm; }
  html, body { margin: 0; padding: 0; height: 100%; }
  body { font-family: Georgia, 'Times New Roman', serif; color: #141414; }
"""

_SHELL = """<!doctype html>
<html><head><meta charset="utf-8"><style>{css}</style></head>
<body>{body}</body></html>"""

_COVER = """<!doctype html>
<html><head><meta charset="utf-8"><style>{css}
  .cover {{ display: flex; flex-direction: column; justify-content: center;
            align-items: center; height: 100%; text-align: center; }}
</style></head>
<body><div class="cover">
  <h1 style="font-size:40px;margin:0 0 8px;">{brand}</h1>
  <p style="font-size:16px;color:#5a5a5a;margin:0 0 48px;">{tagline}</p>
  <p style="font-size:20px;margin:0 0 6px;">Curated for {first_name}</p>
  <p style="font-size:15px;color:#5a5a5a;margin:0 0 4px;">{date_label}</p>
  <p style="font-size:13px;color:#8a8a8a;">Edition No. {edition_number}</p>
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
