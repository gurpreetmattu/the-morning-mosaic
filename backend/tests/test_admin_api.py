"""The admin dashboard's backend: one allowlisted owner, a few real levers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.schemas import (
    DraftSentence,
    EditionBuild,
    GenreOutcome,
    VerifiedStory,
    WrittenStory,
)
from app.api.admin_session import ADMIN_CSRF_COOKIE, ADMIN_CSRF_HEADER, ADMIN_SESSION_COOKIE
from app.api.app import create_app
from app.api.deps import db_session
from app.api.deps import settings as settings_dep
from app.api.routes import admin as admin_route
from app.clock import now_utc
from app.config.schemas import GenreKey
from app.config.settings import Settings
from app.db.persist import persist_genre
from app.db.publish import publish_revision
from app.db.seed import seed_cities, seed_sources
from app.email import tokens
from app.email.sender import Message, Sender, SendOutcome, SendResult
from app.models.content import Story, StoryWithdrawal
from app.models.editions import Delivery, EditionRevision
from app.models.enums import (
    DeliveryStatus,
    DeliveryType,
    EditionPreference,
    Frequency,
    JobName,
    NoticeBatchStatus,
    RunStatus,
    SectionStatus,
    StoryStatus,
    SubscriptionStatus,
)
from app.models.operations import NoticeBatch, PipelineRun
from app.models.users import User
from app.render.sections import RenderedSection
from app.sources.schemas import CollectedArticle, Passage

pytestmark = pytest.mark.integration

ADMIN_EMAIL = "admin@example.com"
EDITION = date(2026, 9, 10)
NOW = datetime(2026, 9, 10, 4, 0, tzinfo=UTC)
BODY = "The cabinet approved the eastern freight corridor on Tuesday, officials said."


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "base_url": "https://mosaic.example.com",
        "database_url": "postgresql://u:p@localhost/db",
        "smtp_host": "smtp.example.com",
        "sender_email": "news@example.com",
        "sender_name": "The Morning Mosaic",
        "gmail_app_password": "app-password",
        "imap_host": "imap.example.com",
        "admin_email": ADMIN_EMAIL,
        "freellmpool_url": "http://127.0.0.1:8080/v1",
        "freellmpool_api_key": "llm-key",
        "token_signing_key": "signing-key-for-tests",
        "app_env": "dev",
        "max_active_subscribers": 400,
    }
    return Settings.model_validate(base | overrides)


class CapturingSender(Sender):
    sent: ClassVar[list[Message]] = []

    def __init__(self, **_: Any) -> None:
        pass

    def send(self, message: Message) -> SendResult:
        CapturingSender.sent.append(message)
        return SendResult(to=message.to, outcome=SendOutcome.SENT, message_id="<id>")


@pytest.fixture
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    seed_cities(session)
    seed_sources(session)
    session.flush()

    CapturingSender.sent = []
    monkeypatch.setattr(tokens, "get_settings", settings)
    monkeypatch.setattr(admin_route, "Sender", CapturingSender)
    admin_route.admin_login_limiter.reset()

    config = settings()
    app = create_app(config)
    app.dependency_overrides[db_session] = lambda: session
    app.dependency_overrides[settings_dep] = lambda: config
    with TestClient(app) as test_client:
        yield test_client


def sign_in_admin(client: TestClient) -> None:
    raw = tokens.sign(tokens.ADMIN_LOGIN, ADMIN_EMAIL, expires_in=tokens.ADMIN_LOGIN_TTL)
    response = client.post(f"/admin/login/{raw}")
    assert response.status_code == 200, response.text
    assert ADMIN_SESSION_COOKIE in client.cookies
    assert ADMIN_CSRF_COOKIE in client.cookies


def admin_csrf_headers(client: TestClient) -> dict[str, str]:
    return {ADMIN_CSRF_HEADER: client.cookies[ADMIN_CSRF_COOKIE]}


def story(
    genre: GenreKey, url: str, hash_suffix: str, headline: str, pool_rank: int
) -> tuple[CollectedArticle, VerifiedStory]:
    article = CollectedArticle(
        source_key="the-hindu",
        genre=genre,
        url=url,
        title=headline,
        published_at=NOW,
        fetched_at=NOW,
        text=BODY,
        passages=[Passage(ordinal=1, text=BODY)],
        content_hash=f"hash-{hash_suffix}",
    )
    verified = VerifiedStory(
        story=WrittenStory(
            headline=DraftSentence(text=headline, passage_ids=["a1:p1"]),
            summary=[DraftSentence(text="Ministers approved.", passage_ids=["a1:p1"])],
        ),
        articles=[article],
        pool_rank=pool_rank,
        attempts=1,
    )
    return article, verified


def publish_with_stories(session: Session) -> EditionRevision:
    """Two india stories and one business story, fully persisted."""
    _, india_one = story("india", "https://example.test/india-1", "i1", "Corridor cleared", 1)
    _, india_two = story("india", "https://example.test/india-2", "i2", "Budget approved", 2)
    persist_genre(
        session,
        edition_date=EDITION,
        outcome=GenreOutcome(
            genre="india", status=SectionStatus.OK, stories=[india_one, india_two]
        ),
    )
    _, biz_one = story("business", "https://example.test/biz-1", "b1", "Markets steady", 1)
    persist_genre(
        session,
        edition_date=EDITION,
        outcome=GenreOutcome(genre="business", status=SectionStatus.OK, stories=[biz_one]),
    )

    return publish_revision(
        session,
        build=EditionBuild(edition_date=EDITION, edition_number=5, genres=[]),
        sections={
            "india": RenderedSection(
                genre="india",
                status=SectionStatus.OK,
                html="<p>india</p>",
                plain_text="india",
                story_count=2,
            ),
            "business": RenderedSection(
                genre="business",
                status=SectionStatus.OK,
                html="<p>business</p>",
                plain_text="business",
                story_count=1,
            ),
        },
        published_at=NOW,
    )


def make_user(session: Session, email: str = "reader@example.com") -> User:
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
    return user


# ==================================================================== login


class TestAdminLogin:
    def test_requesting_a_link_for_the_admin_address_sends_mail(self, client: TestClient) -> None:
        response = client.post("/admin/api/login", json={"email": ADMIN_EMAIL})

        assert response.status_code == 200
        assert len(CapturingSender.sent) == 1
        assert "/admin/login/" in CapturingSender.sent[0].text

    def test_a_non_admin_address_gets_the_same_response_and_no_mail(
        self, client: TestClient
    ) -> None:
        response = client.post("/admin/api/login", json={"email": "someone@example.com"})

        assert response.status_code == 200
        assert response.json()["status"] == "check_your_email"
        assert CapturingSender.sent == []

    def test_opening_the_link_signs_nobody_in(self, client: TestClient) -> None:
        raw = tokens.sign(tokens.ADMIN_LOGIN, ADMIN_EMAIL, expires_in=tokens.ADMIN_LOGIN_TTL)

        response = client.get(f"/admin/login/{raw}")

        assert response.status_code == 200
        assert ADMIN_SESSION_COOKIE not in response.cookies

    def test_posting_signs_in(self, client: TestClient) -> None:
        sign_in_admin(client)
        assert client.get("/admin/api/me").json() == {"email": ADMIN_EMAIL}

    def test_a_token_for_a_different_address_does_not_sign_in(self, client: TestClient) -> None:
        raw = tokens.sign(
            tokens.ADMIN_LOGIN, "impostor@example.com", expires_in=tokens.ADMIN_LOGIN_TTL
        )

        response = client.post(f"/admin/login/{raw}")

        assert response.status_code == 400
        assert ADMIN_SESSION_COOKIE not in response.cookies

    def test_login_is_rate_limited(self, client: TestClient) -> None:
        codes = [
            client.post("/admin/api/login", json={"email": ADMIN_EMAIL}).status_code
            for _ in range(8)
        ]
        assert codes[-1] == 429

    def test_logging_out_clears_the_session(self, client: TestClient) -> None:
        sign_in_admin(client)

        response = client.post("/admin/api/logout", headers=admin_csrf_headers(client))

        assert response.status_code == 200
        assert client.get("/admin/api/me").status_code == 401


class TestAuthorisation:
    def test_the_dashboard_requires_a_session(self, client: TestClient) -> None:
        assert client.get("/admin/api/runs").status_code == 401
        assert client.get("/admin/api/deliveries/stuck").status_code == 401
        assert client.get("/admin/api/notices").status_code == 401

    def test_writes_require_the_csrf_header(self, client: TestClient, session: Session) -> None:
        sign_in_admin(client)
        session.add(
            NoticeBatch(
                edition_date=EDITION,
                status=NoticeBatchStatus.HELD,
                recipient_count=5,
                expires_at=NOW,
            )
        )
        session.flush()

        response = client.post(f"/admin/api/notices/{EDITION.isoformat()}/approve")
        assert response.status_code == 403

    def test_a_readers_own_session_does_not_authorise_the_dashboard(
        self, client: TestClient, session: Session
    ) -> None:
        """A subscriber's session token must never verify against the admin purpose."""
        user = make_user(session)
        raw = tokens.sign(tokens.ADMIN_LOGIN, user.email, expires_in=tokens.ADMIN_LOGIN_TTL)

        # Even if a reader somehow obtained an admin-purpose token for their
        # own address, it still isn't the allowlisted one.
        assert client.post(f"/admin/login/{raw}").status_code == 400


# ==================================================================== reads


class TestRuns:
    def test_lists_recent_runs_newest_first(self, client: TestClient, session: Session) -> None:
        session.add_all(
            [
                PipelineRun(
                    job=JobName.BUILD,
                    edition_date=EDITION,
                    status=RunStatus.FAILED,
                    started_at=NOW,
                ),
                PipelineRun(
                    job=JobName.DELIVERY,
                    edition_date=EDITION,
                    status=RunStatus.SUCCEEDED,
                    started_at=NOW + timedelta(minutes=5),
                ),
            ]
        )
        session.flush()
        sign_in_admin(client)

        response = client.get("/admin/api/runs", params={"edition_date": EDITION.isoformat()})

        assert response.status_code == 200
        jobs = [row["job"] for row in response.json()]
        assert jobs == ["delivery", "build"]

    def test_filters_by_job(self, client: TestClient, session: Session) -> None:
        session.add(
            PipelineRun(
                job=JobName.BOUNCES,
                edition_date=EDITION,
                status=RunStatus.SUCCEEDED,
                started_at=NOW,
            )
        )
        session.flush()
        sign_in_admin(client)

        response = client.get(
            "/admin/api/runs", params={"job": "bounces", "edition_date": EDITION.isoformat()}
        )

        assert len(response.json()) == 1


class TestStuckDeliveries:
    def test_flags_a_row_stuck_well_past_a_normal_send(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        session.add(
            Delivery(
                user_id=user.id,
                edition_date=EDITION,
                type=DeliveryType.NEWSLETTER,
                status=DeliveryStatus.SENDING,
                claimed_at=now_utc() - timedelta(hours=2),
            )
        )
        session.flush()
        sign_in_admin(client)

        response = client.get("/admin/api/deliveries/stuck")

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_does_not_flag_a_row_still_plausibly_mid_flight(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        session.add(
            Delivery(
                user_id=user.id,
                edition_date=EDITION,
                type=DeliveryType.NEWSLETTER,
                status=DeliveryStatus.SENDING,
                claimed_at=now_utc(),
            )
        )
        session.flush()
        sign_in_admin(client)

        response = client.get(
            "/admin/api/deliveries/stuck",
        )
        assert response.json() == []

    def test_a_sent_row_is_not_flagged(self, client: TestClient, session: Session) -> None:
        user = make_user(session)
        revision = publish_with_stories(session)
        session.add(
            Delivery(
                user_id=user.id,
                edition_date=EDITION,
                type=DeliveryType.NEWSLETTER,
                status=DeliveryStatus.SENT,
                revision_id=revision.id,
                sent_at=NOW,
            )
        )
        session.flush()
        sign_in_admin(client)

        assert client.get("/admin/api/deliveries/stuck").json() == []


# ============================================================ notice batches


class TestNoticeBatches:
    def test_approving_a_held_batch(self, client: TestClient, session: Session) -> None:
        session.add(
            NoticeBatch(
                edition_date=EDITION,
                status=NoticeBatchStatus.HELD,
                recipient_count=90,
                expires_at=NOW,
            )
        )
        session.flush()
        sign_in_admin(client)

        response = client.post(
            f"/admin/api/notices/{EDITION.isoformat()}/approve", headers=admin_csrf_headers(client)
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "approved"
        assert body["decided_by"] == ADMIN_EMAIL

    def test_approving_an_already_sent_batch_is_refused(
        self, client: TestClient, session: Session
    ) -> None:
        session.add(
            NoticeBatch(
                edition_date=EDITION,
                status=NoticeBatchStatus.SENT,
                recipient_count=3,
                expires_at=NOW,
            )
        )
        session.flush()
        sign_in_admin(client)

        response = client.post(
            f"/admin/api/notices/{EDITION.isoformat()}/approve", headers=admin_csrf_headers(client)
        )
        assert response.status_code == 400

    def test_suppressing_a_held_batch(self, client: TestClient, session: Session) -> None:
        session.add(
            NoticeBatch(
                edition_date=EDITION,
                status=NoticeBatchStatus.HELD,
                recipient_count=90,
                expires_at=NOW,
            )
        )
        session.flush()
        sign_in_admin(client)

        response = client.post(
            f"/admin/api/notices/{EDITION.isoformat()}/suppress",
            headers=admin_csrf_headers(client),
        )
        assert response.json()["status"] == "suppressed"

    def test_deciding_a_batch_that_does_not_exist_is_a_404(self, client: TestClient) -> None:
        sign_in_admin(client)

        response = client.post(
            "/admin/api/notices/2099-01-01/approve", headers=admin_csrf_headers(client)
        )
        assert response.status_code == 404


# ================================================================= withdraw


class TestWithdraw:
    def test_withdrawing_a_story_publishes_a_new_revision(
        self, client: TestClient, session: Session
    ) -> None:
        publish_with_stories(session)
        target = session.scalar(select(Story).where(Story.headline == "Corridor cleared"))
        assert target is not None
        sign_in_admin(client)

        response = client.post(
            f"/admin/api/stories/{target.id}/withdraw",
            json={"reason": "factual error found after publication"},
            headers=admin_csrf_headers(client),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["revision"] == 2
        assert body["remaining_stories"] == 1

        session.refresh(target)
        assert target.status is StoryStatus.WITHDRAWN
        assert session.scalar(select(StoryWithdrawal).where(StoryWithdrawal.story_id == target.id))

    def test_the_untouched_genre_is_carried_forward(
        self, client: TestClient, session: Session
    ) -> None:
        from app.models.editions import EditionSection

        publish_with_stories(session)
        target = session.scalar(select(Story).where(Story.headline == "Corridor cleared"))
        assert target is not None
        sign_in_admin(client)

        client.post(
            f"/admin/api/stories/{target.id}/withdraw",
            json={"reason": "duplicate of an earlier story"},
            headers=admin_csrf_headers(client),
        )

        latest = session.scalars(
            select(EditionSection)
            .join(EditionSection.revision)
            .order_by(EditionSection.created_at.desc())
        ).all()
        business_sections = [row for row in latest if row.genre == "business"]
        assert business_sections
        assert business_sections[0].html == "<p>business</p>"

    def test_withdrawing_twice_is_refused(self, client: TestClient, session: Session) -> None:
        publish_with_stories(session)
        target = session.scalar(select(Story).where(Story.headline == "Corridor cleared"))
        assert target is not None
        sign_in_admin(client)

        headers = admin_csrf_headers(client)
        client.post(
            f"/admin/api/stories/{target.id}/withdraw",
            json={"reason": "first"},
            headers=headers,
        )
        response = client.post(
            f"/admin/api/stories/{target.id}/withdraw",
            json={"reason": "second"},
            headers=headers,
        )
        assert response.status_code == 400

    def test_withdrawing_an_unknown_story_is_a_404(self, client: TestClient) -> None:
        sign_in_admin(client)
        response = client.post(
            "/admin/api/stories/00000000-0000-0000-0000-000000000000/withdraw",
            json={"reason": "test"},
            headers=admin_csrf_headers(client),
        )
        assert response.status_code == 404

    def test_an_empty_reason_is_rejected(self, client: TestClient, session: Session) -> None:
        publish_with_stories(session)
        target = session.scalar(select(Story).where(Story.headline == "Corridor cleared"))
        assert target is not None
        sign_in_admin(client)

        response = client.post(
            f"/admin/api/stories/{target.id}/withdraw",
            json={"reason": ""},
            headers=admin_csrf_headers(client),
        )
        assert response.status_code == 422

    def test_withdrawals_are_listed(self, client: TestClient, session: Session) -> None:
        publish_with_stories(session)
        target = session.scalar(select(Story).where(Story.headline == "Corridor cleared"))
        assert target is not None
        sign_in_admin(client)

        client.post(
            f"/admin/api/stories/{target.id}/withdraw",
            json={"reason": "factual error"},
            headers=admin_csrf_headers(client),
        )

        response = client.get("/admin/api/withdrawals")

        assert response.status_code == 200
        assert response.json()[0]["headline"] == "Corridor cleared"
        assert response.json()[0]["reason"] == "factual error"
