"""Styling guarantees for the notices and the PDF, alongside the email's own tests."""

from __future__ import annotations

from datetime import date

from app.render import PALETTE
from app.render.notices import failure_notice, paused_notice
from app.render.pdf import PdfSection, edition_html

LINKS = {
    "first_name": "Asha",
    "unsubscribe_url": "https://example.test/unsubscribe/abc",
    "preferences_url": "https://example.test/preferences",
}


def test_notices_use_the_shared_palette_and_keep_their_words() -> None:
    failure = failure_notice(**LINKS)
    paused = paused_notice(**LINKS)

    assert "Good morning Asha" in failure.html
    assert "didn't make it out" in failure.html
    assert "paused these notices" in paused.html
    for notice in (failure, paused):
        assert PALETTE["ink"] in notice.html
        assert "#141414" not in notice.html
        assert "Playfair" not in notice.html


def test_notices_stay_independent_of_everything_external() -> None:
    # CLAUDE.md: no LLM, news data, external images, or build-output dependency.
    for notice in (failure_notice(**LINKS), paused_notice(**LINKS)):
        assert "<img" not in notice.html
        assert "<script" not in notice.html
        assert "https://example.test/unsubscribe/abc" in notice.html


def _html(*, name: str = "Asha", sections: list[PdfSection] | None = None) -> str:
    return edition_html(
        first_name=name,
        edition_date=date(2026, 10, 5),
        edition_number=5,
        sections=sections or [],
    )


def test_the_pdf_cover_carries_the_masthead_details() -> None:
    html = _html()

    assert "The Morning Mosaic" in html
    assert "The morning paper, set to your interests." in html
    assert "Curated for Asha" in html
    assert "Monday, 5 October 2026" in html
    assert "Edition 5" in html
    assert "<script" not in html


def test_the_cover_escapes_the_readers_name() -> None:
    html = _html(name="<b>Asha</b>")

    assert "<b>Asha</b>" not in html
    assert "&lt;b&gt;Asha" in html


def test_pdf_pages_are_a4_and_use_the_email_paper() -> None:
    html = _html()

    assert "size: A4" in html
    assert f"background: {PALETTE['paper_raised']}" in html
    assert "#ffffff" not in html


def test_the_edition_is_one_document_so_genres_flow_without_blank_pages() -> None:
    sections = [
        PdfSection(
            genre="india", title="Across India", blurb="A & B", html="<section>one</section>"
        ),
        PdfSection(genre="ai", title="AI", blurb="Models", html="<section>two</section>"),
    ]
    html = _html(sections=sections)

    assert html.count("<!doctype html>") == 1
    assert "<section>one</section>" in html and "<section>two</section>" in html
    # Only the cover forces a page break; genres follow each other on the page.
    assert html.count("break-after: page") == 1


def test_the_cover_lists_each_genre_linked_to_its_section_and_escaped() -> None:
    html = _html(
        sections=[PdfSection(genre="india", title="Across India", blurb="A & B", html="<p>x</p>")]
    )

    assert "In this edition" in html
    assert 'href="#genre-india"' in html
    assert 'id="genre-india"' in html
    assert "A &amp; B" in html
    assert "target-counter" in html


def test_pdf_pages_let_stories_split_instead_of_leaving_gaps() -> None:
    assert "break-inside: auto !important" in _html()


def test_a_photo_is_kept_on_the_same_page_as_its_credit() -> None:
    html = _html()

    assert "section img + span" in html
    assert "break-before: avoid" in html
