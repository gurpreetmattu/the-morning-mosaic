"""Magic-link login, preferences, and the DPDP export/delete pair."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import time
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.app import create_app
from app.api.deps import db_session
from app.api.deps import settings as settings_dep
from app.api.routes import account
from app.api.session import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from app.config.settings import Settings
from app.db.seed import seed_cities, seed_sources
from app.email import tokens
from app.email.sender import Message, Sender, SendOutcome, SendResult
from app.models.enums import EditionPreference, Frequency, SubscriptionStatus, TokenPurpose
from app.models.users import FollowedKeyword, Token, User, UserGenre

pytestmark = pytest.mark.integration


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
    monkeypatch.setattr(account, "Sender", CapturingSender)
    account.login_limiter.reset(session)

    app = create_app(settings())
    app.dependency_overrides[db_session] = lambda: session
    app.dependency_overrides[settings_dep] = lambda: settings()
    with TestClient(app) as test_client:
        yield test_client


def make_user(session: Session, email: str = "reader@example.com", **overrides: Any) -> User:
    user = User(
        **{
            "email": email,
            "name": "Asha Rao",
            "city_id": "mumbai",
            "status": SubscriptionStatus.ACTIVE,
            "delivery_slot": time(7, 0),
            "frequency": Frequency.DAILY,
            "edition_preference": EditionPreference.MIXED,
            "age_confirmed": True,
            **overrides,
        }
    )
    session.add(user)
    session.flush()
    session.add(UserGenre(user_id=user.id, genre="india"))
    session.flush()
    return user


def sign_in(client: TestClient, session: Session, user: User) -> None:
    """Redeem a magic link so the test client carries session + CSRF cookies."""
    raw = tokens.issue(session, user_id=user.id, purpose=TokenPurpose.MAGIC_LINK)
    response = client.post(f"/login/{raw}")
    assert response.status_code == 200
    assert SESSION_COOKIE in client.cookies
    assert CSRF_COOKIE in client.cookies


def csrf_headers(client: TestClient) -> dict[str, str]:
    return {CSRF_HEADER: client.cookies[CSRF_COOKIE]}


def count(session: Session, model: type[Any]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


# ============================================================== magic link


class TestMagicLink:
    def test_requesting_a_link_for_a_known_address_sends_mail(
        self, client: TestClient, session: Session
    ) -> None:
        make_user(session)

        response = client.post("/api/login", json={"email": "reader@example.com"})

        assert response.status_code == 200
        assert len(CapturingSender.sent) == 1
        assert "/login/" in CapturingSender.sent[0].text

    def test_an_unknown_address_gets_the_same_response_and_no_mail(
        self, client: TestClient
    ) -> None:
        response = client.post("/api/login", json={"email": "nobody@example.com"})

        assert response.status_code == 200
        assert response.json()["status"] == "check_your_email"
        assert CapturingSender.sent == []

    def test_opening_the_link_signs_nobody_in(self, client: TestClient, session: Session) -> None:
        """Link-scanner safety extends to login: a GET must not start a session."""
        user = make_user(session)
        raw = tokens.issue(session, user_id=user.id, purpose=TokenPurpose.MAGIC_LINK)

        response = client.get(f"/login/{raw}")

        assert response.status_code == 200
        assert SESSION_COOKIE not in response.cookies

    def test_posting_signs_in_and_the_link_works_once(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        raw = tokens.issue(session, user_id=user.id, purpose=TokenPurpose.MAGIC_LINK)

        first = client.post(f"/login/{raw}")
        assert first.status_code == 200
        assert SESSION_COOKIE in first.cookies

        assert client.post(f"/login/{raw}").status_code == 400

    def test_an_unknown_token_is_refused(self, client: TestClient) -> None:
        assert client.post("/login/not-a-real-token").status_code == 400

    def test_login_is_rate_limited(self, client: TestClient, session: Session) -> None:
        make_user(session)
        codes = [
            client.post("/api/login", json={"email": "reader@example.com"}).status_code
            for _ in range(8)
        ]
        assert codes[-1] == 429


# ================================================================== session


class TestSession:
    def test_me_requires_a_session(self, client: TestClient) -> None:
        assert client.get("/api/me").status_code == 401

    def test_a_signed_in_reader_can_read_their_profile(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        sign_in(client, session, user)

        response = client.get("/api/me")

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "reader@example.com"
        assert body["genres"] == ["india"]

    def test_a_state_change_without_the_csrf_header_is_refused(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        sign_in(client, session, user)

        response = client.patch("/api/me", json={"name": "New Name"})

        assert response.status_code == 403

    def test_logging_out_clears_the_session(self, client: TestClient, session: Session) -> None:
        user = make_user(session)
        sign_in(client, session, user)

        response = client.post("/api/logout", headers=csrf_headers(client))

        assert response.status_code == 200
        assert client.get("/api/me").status_code == 401

    def test_a_deleted_accounts_session_no_longer_authenticates(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        sign_in(client, session, user)
        client.post("/api/me/delete", headers=csrf_headers(client))

        assert client.get("/api/me").status_code == 401


# =========================================================== preferences


class TestPreferences:
    def test_changing_genres_replaces_the_set(self, client: TestClient, session: Session) -> None:
        user = make_user(session)
        sign_in(client, session, user)

        response = client.patch(
            "/api/me", json={"genres": ["business", "technology"]}, headers=csrf_headers(client)
        )

        assert response.status_code == 200
        assert response.json()["genres"] == ["business", "technology"]
        assert count(session, UserGenre) == 2

    def test_changing_keywords_replaces_the_set(self, client: TestClient, session: Session) -> None:
        user = make_user(session)
        sign_in(client, session, user)

        client.patch("/api/me", json={"keywords": ["Cricket"]}, headers=csrf_headers(client))
        response = client.patch(
            "/api/me", json={"keywords": ["hockey"]}, headers=csrf_headers(client)
        )

        assert response.json()["keywords"] == ["hockey"]
        assert count(session, FollowedKeyword) == 1

    def test_changing_the_delivery_slot(self, client: TestClient, session: Session) -> None:
        user = make_user(session)
        sign_in(client, session, user)

        response = client.patch(
            "/api/me", json={"delivery_slot": "08:30"}, headers=csrf_headers(client)
        )

        assert response.status_code == 200
        assert response.json()["delivery_slot"] == "08:30:00"

    def test_an_off_grid_slot_is_refused(self, client: TestClient, session: Session) -> None:
        user = make_user(session)
        sign_in(client, session, user)

        response = client.patch(
            "/api/me", json={"delivery_slot": "08:15"}, headers=csrf_headers(client)
        )
        assert response.status_code == 400

    def test_an_unknown_city_is_refused(self, client: TestClient, session: Session) -> None:
        user = make_user(session)
        sign_in(client, session, user)

        response = client.patch(
            "/api/me", json={"city_id": "atlantis"}, headers=csrf_headers(client)
        )
        assert response.status_code == 400

    def test_emptying_genres_is_refused(self, client: TestClient, session: Session) -> None:
        """A subscriber with no genres would receive an empty newsletter."""
        user = make_user(session)
        sign_in(client, session, user)

        response = client.patch("/api/me", json={"genres": []}, headers=csrf_headers(client))
        assert response.status_code == 422

    def test_fields_left_out_are_left_unchanged(self, client: TestClient, session: Session) -> None:
        user = make_user(session)
        sign_in(client, session, user)

        response = client.patch("/api/me", json={"name": "Renamed"}, headers=csrf_headers(client))

        assert response.json()["genres"] == ["india"]
        row = session.get(User, user.id)
        assert row is not None
        assert row.delivery_slot == time(7, 0)


# ================================================================ pause


class TestPauseResume:
    def test_pausing_an_active_subscription(self, client: TestClient, session: Session) -> None:
        user = make_user(session)
        sign_in(client, session, user)

        response = client.post("/api/me/pause", headers=csrf_headers(client))

        assert response.status_code == 200
        assert response.json()["status"] == "paused"
        assert user.status is SubscriptionStatus.PAUSED

    def test_resuming_a_paused_subscription(self, client: TestClient, session: Session) -> None:
        user = make_user(session, status=SubscriptionStatus.PAUSED)
        sign_in(client, session, user)

        response = client.post("/api/me/resume", headers=csrf_headers(client))

        assert response.status_code == 200
        assert user.status is SubscriptionStatus.ACTIVE

    def test_pausing_an_unsubscribed_account_is_refused(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session, status=SubscriptionStatus.UNSUBSCRIBED)
        sign_in(client, session, user)

        response = client.post("/api/me/pause", headers=csrf_headers(client))
        assert response.status_code == 400


# =============================================================== DPDP


class TestExportAndDelete:
    def test_export_includes_the_profile_and_genres(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        sign_in(client, session, user)

        response = client.get("/api/me/export")

        assert response.status_code == 200
        body = response.json()
        assert body["profile"]["email"] == "reader@example.com"
        assert body["genres"] == ["india"]

    def test_deleting_clears_personal_data_but_keeps_the_row(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        user_id = user.id
        sign_in(client, session, user)

        response = client.post("/api/me/delete", headers=csrf_headers(client))

        assert response.status_code == 200
        row = session.get(User, user_id)
        assert row is not None
        assert row.anonymised_at is not None
        assert row.name == "Deleted reader"
        assert row.email != "reader@example.com"
        assert row.status is SubscriptionStatus.UNSUBSCRIBED
        assert count(session, UserGenre) == 0

    def test_deletion_revokes_outstanding_tokens(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        tokens.issue(session, user_id=user.id, purpose=TokenPurpose.MAGIC_LINK)
        sign_in(client, session, user)

        client.post("/api/me/delete", headers=csrf_headers(client))

        assert count(session, Token) == 0
