"""The PDF download link: revision-bound content, and two-tier caching.

WeasyPrint cannot run on this machine (no GTK/Pango; see docs/BACKLOG.md), so
every test injects a fake renderer that returns a real one-page PDF built
with pypdf instead of an actual layout of the HTML. That keeps the merge
itself — the part these tests actually exercise — genuine: `pypdf` is pure
Python and runs the same here as anywhere.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, time
from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from sqlalchemy.orm import Session

from app.agents.schemas import EditionBuild
from app.api.app import create_app
from app.api.deps import db_session
from app.api.deps import settings as settings_dep
from app.api.routes import pdf as pdf_route
from app.config.settings import Settings
from app.db.publish import publish_revision
from app.db.seed import seed_cities, seed_sources
from app.email import tokens
from app.models.editions import EditionRevision
from app.models.enums import EditionPreference, Frequency, SectionStatus, SubscriptionStatus
from app.models.users import User, UserGenre
from app.render.sections import RenderedSection

pytestmark = pytest.mark.integration

EDITION = date(2026, 9, 10)
NOW = datetime(2026, 9, 10, 4, 0, tzinfo=UTC)


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "base_url": "https://mosaic.example.com",
        "database_url": "postgresql://u:p@localhost/db",
        "smtp_host": "smtp.example.com",
        "sender_email": "news@example.com",
        "sender_name": "The Morning Mosaic",
        "gmail_app_password": "app-password",
        "imap_host": "imap.example.com",
        "admin_email": "admin@example.com",
        "llmbuffet_url": "http://127.0.0.1:8080/v1",
        "llmbuffet_api_key": "llm-key",
        "token_signing_key": "signing-key-for-tests",
        "app_env": "dev",
        "max_active_subscribers": 400,
    }
    return Settings.model_validate(base | overrides)


def one_page_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class FakeRenderer:
    """Stands in for WeasyPrint: ignores the HTML, returns a real PDF page."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, html: str) -> bytes:
        self.calls.append(html)
        return one_page_pdf()


@pytest.fixture
def fake_renderer(monkeypatch: pytest.MonkeyPatch) -> FakeRenderer:
    renderer = FakeRenderer()
    monkeypatch.setattr(pdf_route, "render_pdf_html", renderer)
    return renderer


@pytest.fixture
def client(
    session: Session, tmp_path: Any, fake_renderer: FakeRenderer, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    seed_cities(session)
    seed_sources(session)
    session.flush()

    monkeypatch.setattr(tokens, "get_settings", settings)

    config = settings(pdf_cache_dir=str(tmp_path))
    app = create_app(config)
    app.dependency_overrides[db_session] = lambda: session
    app.dependency_overrides[settings_dep] = lambda: config
    with TestClient(app) as test_client:
        yield test_client


def make_user(session: Session, email: str = "reader@example.com", *genres: str) -> User:
    user = User(
        email=email,
        name="Asha Rao",
        city_id="mumbai",
        status=SubscriptionStatus.ACTIVE,
        delivery_slot=time(7, 0),
        frequency=Frequency.DAILY,
        edition_preference=EditionPreference.MIXED,
        age_confirmed=True,
    )
    session.add(user)
    session.flush()
    for genre in genres:
        session.add(UserGenre(user_id=user.id, genre=genre))
    session.flush()
    return user


def publish(session: Session, *genres: str, on: date = EDITION) -> EditionRevision:
    """One published revision with a section per genre given.

    Only `EditionSection` rows matter to the PDF route, so this writes those
    directly (as a late update would, carrying unchanged genres forward)
    rather than running the full Writer/Fact-checker persistence pipeline.
    """
    return publish_revision(
        session,
        build=EditionBuild(edition_date=on, edition_number=5, genres=[]),
        sections={
            genre: RenderedSection(
                genre=genre,
                status=SectionStatus.OK,
                html=f"<section><h2>{genre}</h2><p>archive copy</p></section>",
                plain_text="archive copy",
                story_count=1,
            )
            for genre in genres
        },
        published_at=NOW,
    )


def pdf_token(revision: EditionRevision, user: User) -> str:
    return tokens.sign(tokens.PDF, str(revision.id), user=str(user.id))


def page_count(data: bytes) -> int:
    return len(PdfReader(BytesIO(data)).pages)


class TestDownload:
    def test_downloading_returns_a_pdf(self, client: TestClient, session: Session) -> None:
        revision = publish(session, "india", "business")
        user = make_user(session, "asha@example.com", "india", "business")

        response = client.get(f"/pdf/{pdf_token(revision, user)}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        # One page per subscribed genre, plus a cover page.
        assert page_count(response.content) == 3

    def test_only_subscribed_genres_are_included(
        self, client: TestClient, session: Session
    ) -> None:
        revision = publish(session, "india", "business", "sports")
        user = make_user(session, "asha@example.com", "india")

        response = client.get(f"/pdf/{pdf_token(revision, user)}")

        assert page_count(response.content) == 2  # cover + india only

    def test_the_filename_carries_the_edition_date(
        self, client: TestClient, session: Session
    ) -> None:
        revision = publish(session, "india")
        user = make_user(session, "asha@example.com", "india")

        response = client.get(f"/pdf/{pdf_token(revision, user)}")

        assert "2026-09-10" in response.headers["content-disposition"]

    def test_a_reader_with_no_subscribed_genre_in_this_revision_gets_a_page(
        self, client: TestClient, session: Session
    ) -> None:
        revision = publish(session, "india")
        user = make_user(session, "asha@example.com", "sports")

        response = client.get(f"/pdf/{pdf_token(revision, user)}")

        assert response.status_code == 400
        assert "<script" not in response.text

    def test_an_unknown_token_is_refused(self, client: TestClient) -> None:
        response = client.get("/pdf/not-a-real-token")
        assert response.status_code == 400

    def test_a_token_for_an_unknown_revision_is_refused(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session, "asha@example.com", "india")
        token = tokens.sign(tokens.PDF, "00000000-0000-0000-0000-000000000000", user=str(user.id))

        assert client.get(f"/pdf/{token}").status_code == 400

    def test_a_deleted_accounts_link_no_longer_works(
        self, client: TestClient, session: Session
    ) -> None:
        revision = publish(session, "india")
        user = make_user(session, "asha@example.com", "india")
        token = pdf_token(revision, user)
        user.anonymised_at = NOW

        assert client.get(f"/pdf/{token}").status_code == 400

    def test_a_feedback_token_cannot_be_replayed_as_a_pdf_link(
        self, client: TestClient, session: Session
    ) -> None:
        revision = publish(session, "india")
        user = make_user(session, "asha@example.com", "india")
        token = tokens.sign(tokens.FEEDBACK, str(revision.id), user=str(user.id), vote="up")

        assert client.get(f"/pdf/{token}").status_code == 400


class TestCaching:
    def test_a_second_download_does_not_re_render(
        self, client: TestClient, session: Session, fake_renderer: FakeRenderer
    ) -> None:
        revision = publish(session, "india")
        user = make_user(session, "asha@example.com", "india")
        token = pdf_token(revision, user)

        first = client.get(f"/pdf/{token}")
        calls_after_first = len(fake_renderer.calls)
        second = client.get(f"/pdf/{token}")

        assert first.status_code == second.status_code == 200
        assert first.content == second.content
        assert len(fake_renderer.calls) == calls_after_first

    def test_a_shared_genre_page_is_rendered_once_across_readers(
        self, client: TestClient, session: Session, fake_renderer: FakeRenderer
    ) -> None:
        """Genre pages are cached per revision, not per reader."""
        revision = publish(session, "india", "business")
        first_reader = make_user(session, "asha@example.com", "india")
        second_reader = make_user(session, "bala@example.com", "india", "business")

        client.get(f"/pdf/{pdf_token(revision, first_reader)}")
        calls_for_first = len(fake_renderer.calls)
        client.get(f"/pdf/{pdf_token(revision, second_reader)}")

        # The second reader adds one new genre page (business) plus their own
        # cover; "india" is already cached, so it does not render again.
        assert len(fake_renderer.calls) == calls_for_first + 2

    def test_late_content_after_the_link_was_issued_does_not_appear(
        self, client: TestClient, session: Session
    ) -> None:
        """The PDF a reader downloads is the edition they were sent, not a later one."""
        revision = publish(session, "india")
        user = make_user(session, "asha@example.com", "india")
        token = pdf_token(revision, user)

        # A later revision adds a genre this reader also follows.
        session.add(UserGenre(user_id=user.id, genre="business"))
        session.flush()
        publish(session, "india", "business", on=EDITION)

        response = client.get(f"/pdf/{token}")

        # Still bound to the first revision: only "india" appears.
        assert page_count(response.content) == 2
