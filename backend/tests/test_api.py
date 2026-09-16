"""API routes, with link-scanner safety as the property that matters most."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, time
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.schemas import (
    DraftSentence,
    EditionBuild,
    GenreOutcome,
    VerifiedStory,
    WrittenStory,
)
from app.api.app import create_app
from app.api.deps import db_session
from app.api.deps import settings as settings_dep
from app.api.routes import public
from app.api.routes.archive import is_public
from app.config.settings import Settings
from app.db.persist import persist_genre
from app.db.publish import publish_revision
from app.db.seed import seed_cities, seed_sources
from app.email import tokens
from app.email.sender import Message, Sender, SendOutcome, SendResult
from app.models.content import Story
from app.models.editions import Feedback
from app.models.enums import (
    EditionPreference,
    Frequency,
    SectionStatus,
    SubscriptionStatus,
    TokenPurpose,
    Vote,
)
from app.models.users import Consent, FollowedKeyword, User, UserGenre, WaitlistEntry
from app.render.sections import RenderedSection
from app.sources.schemas import CollectedArticle, Passage

pytestmark = pytest.mark.integration

# Deliberately in the past: the archive publishes an edition only after its
# last delivery slot, and these routes read the real clock.
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
        "admin_email": "admin@example.com",
        "freellmpool_url": "http://127.0.0.1:8080/v1",
        "freellmpool_api_key": "llm-key",
        "token_signing_key": "signing-key-for-tests",
        "app_env": "dev",
        "max_active_subscribers": 400,
    }
    return Settings.model_validate(base | overrides)


class CapturingSender(Sender):
    """Stands in for SMTP, and for the dev allowlist that would suppress it."""

    sent: ClassVar[list[Message]] = []

    def __init__(self, **_: Any) -> None:
        pass

    def send(self, message: Message) -> SendResult:
        CapturingSender.sent.append(message)
        return SendResult(to=message.to, outcome=SendOutcome.SENT, message_id="<id>")


@pytest.fixture
def config() -> dict[str, Settings]:
    """The settings the app sees, so a test can change them mid-flight."""
    return {"settings": settings()}


@pytest.fixture
def client(
    session: Session, config: dict[str, Settings], monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    seed_cities(session)
    seed_sources(session)
    session.flush()

    CapturingSender.sent = []
    monkeypatch.setattr(tokens, "get_settings", settings)
    monkeypatch.setattr(public, "Sender", CapturingSender)
    # Windows are per process, so they would survive between tests.
    public.signup_limiter.reset()
    public.feedback_limiter.reset()

    app = create_app(config["settings"])
    app.dependency_overrides[db_session] = lambda: session
    app.dependency_overrides[settings_dep] = lambda: config["settings"]
    with TestClient(app) as test_client:
        yield test_client


def signup_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "Asha Rao",
        "email": "asha@example.com",
        "city_id": "mumbai",
        "genres": ["india", "business"],
        "delivery_slot": "07:00",
        "frequency": "daily",
        "edition_preference": "mixed",
        "keywords": ["Cricket"],
        "age_confirmed": True,
    }
    return base | overrides


def make_user(
    session: Session,
    email: str = "reader@example.com",
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> User:
    user = User(
        email=email,
        name="Asha Rao",
        city_id="mumbai",
        status=status,
        delivery_slot=time(7, 0),
        frequency=Frequency.DAILY,
        edition_preference=EditionPreference.MIXED,
        age_confirmed=True,
    )
    session.add(user)
    session.flush()
    return user


def publish(session: Session) -> Story:
    """One published edition with a single story, for archive and feedback."""
    article = CollectedArticle(
        source_key="the-hindu",
        genre="india",
        url="https://example.test/corridor",
        title="Corridor",
        published_at=NOW,
        fetched_at=NOW,
        text=BODY,
        passages=[Passage(ordinal=1, text=BODY)],
        content_hash="archive-hash",
    )
    persist_genre(
        session,
        edition_date=EDITION,
        outcome=GenreOutcome(
            genre="india",
            status=SectionStatus.OK,
            stories=[
                VerifiedStory(
                    story=WrittenStory(
                        headline=DraftSentence(text="Corridor cleared", passage_ids=["a1:p1"]),
                        summary=[DraftSentence(text="Ministers approved.", passage_ids=["a1:p1"])],
                    ),
                    articles=[article],
                    pool_rank=1,
                    attempts=1,
                )
            ],
        ),
    )
    publish_revision(
        session,
        build=EditionBuild(edition_date=EDITION, edition_number=5, genres=[]),
        sections={
            "india": RenderedSection(
                genre="india",
                status=SectionStatus.OK,
                html="<p>archive copy</p>",
                plain_text="archive copy",
                story_count=1,
            )
        },
        published_at=NOW,
    )
    story = session.scalars(select(Story)).first()
    assert story is not None
    return story


def feedback_token(story: Story, user: User, vote: Vote = Vote.UP) -> str:
    return tokens.sign(tokens.FEEDBACK, str(story.id), user=str(user.id), vote=vote.value)


def count(session: Session, model: type[Any]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


# ======================================================== link-scanner safety


class TestLinkScannerSafety:
    """Mail security opens every link before the reader ever sees it."""

    def test_opening_an_opt_in_link_confirms_nothing(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session, status=SubscriptionStatus.PENDING)
        raw = tokens.issue(session, user_id=user.id, purpose=TokenPurpose.OPT_IN)

        response = client.get(f"/opt-in/{raw}")

        assert response.status_code == 200
        assert user.status is SubscriptionStatus.PENDING
        # It offers a button that posts back to the same place.
        assert 'method="post"' in response.text

    def test_opening_an_opt_in_link_does_not_consume_the_token(
        self, client: TestClient, session: Session
    ) -> None:
        """A scanner must not burn the reader's single-use confirmation."""
        user = make_user(session, status=SubscriptionStatus.PENDING)
        raw = tokens.issue(session, user_id=user.id, purpose=TokenPurpose.OPT_IN)

        client.get(f"/opt-in/{raw}")

        assert client.post(f"/opt-in/{raw}").status_code == 200
        assert user.status is SubscriptionStatus.ACTIVE

    def test_opening_an_unsubscribe_link_unsubscribes_nobody(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        raw = tokens.ensure_unsubscribe_token(session, user.id)

        response = client.get(f"/unsubscribe/{raw}")

        assert response.status_code == 200
        assert user.status is SubscriptionStatus.ACTIVE

    def test_opening_a_feedback_link_records_no_vote(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        story = publish(session)

        response = client.get(f"/feedback/{feedback_token(story, user)}")

        assert response.status_code == 200
        assert count(session, Feedback) == 0

    def test_the_pages_carry_no_scripts(self, client: TestClient, session: Session) -> None:
        user = make_user(session)
        raw = tokens.ensure_unsubscribe_token(session, user.id)

        response = client.get(f"/unsubscribe/{raw}")

        assert "<script" not in response.text
        assert "default-src 'none'" in response.headers["content-security-policy"]


# ===================================================================== signup


class TestSignup:
    def test_a_valid_signup_creates_a_pending_reader(
        self, client: TestClient, session: Session
    ) -> None:
        response = client.post("/api/signup", json=signup_payload())

        assert response.status_code == 200
        assert response.json()["status"] == "check_your_email"

        user = session.scalar(select(User).where(User.email == "asha@example.com"))
        assert user is not None
        assert user.status is SubscriptionStatus.PENDING

    def test_signing_somebody_else_up_does_not_subscribe_them(
        self, client: TestClient, session: Session
    ) -> None:
        """Double opt-in: nobody becomes active without confirming."""
        client.post("/api/signup", json=signup_payload())
        user = session.scalar(select(User).where(User.email == "asha@example.com"))

        assert user is not None
        assert user.status is not SubscriptionStatus.ACTIVE

    def test_genres_keywords_and_consent_are_recorded(
        self, client: TestClient, session: Session
    ) -> None:
        client.post("/api/signup", json=signup_payload())
        user = session.scalar(select(User).where(User.email == "asha@example.com"))
        assert user is not None

        genres = set(session.scalars(select(UserGenre.genre).where(UserGenre.user_id == user.id)))
        keywords = set(
            session.scalars(
                select(FollowedKeyword.keyword).where(FollowedKeyword.user_id == user.id)
            )
        )
        consent = session.scalar(select(Consent).where(Consent.user_id == user.id))

        assert genres == {"india", "business"}
        assert keywords == {"cricket"}  # the CHECK constraint requires lower case
        assert consent is not None
        assert consent.policy_version == public.CURRENT_POLICY_VERSION

    def test_a_confirmation_email_is_sent(self, client: TestClient) -> None:
        client.post("/api/signup", json=signup_payload())

        assert len(CapturingSender.sent) == 1
        assert "/opt-in/" in CapturingSender.sent[0].text

    def test_the_address_is_stored_lower_cased(self, client: TestClient, session: Session) -> None:
        client.post("/api/signup", json=signup_payload(email="Asha@Example.COM"))

        assert session.scalar(select(User).where(User.email == "asha@example.com")) is not None

    def test_an_existing_address_is_not_revealed(
        self, client: TestClient, session: Session
    ) -> None:
        """The response must not tell a stranger who already subscribes."""
        make_user(session, email="asha@example.com")

        response = client.post("/api/signup", json=signup_payload())

        assert response.status_code == 200
        assert response.json()["status"] == "check_your_email"
        assert count(session, User) == 1
        assert CapturingSender.sent == []

    def test_under_eighteen_is_refused(self, client: TestClient, session: Session) -> None:
        response = client.post("/api/signup", json=signup_payload(age_confirmed=False))

        assert response.status_code == 400
        assert "18" in response.json()["message"]
        assert count(session, User) == 0

    def test_an_unknown_city_is_refused(self, client: TestClient) -> None:
        response = client.post("/api/signup", json=signup_payload(city_id="atlantis"))

        assert response.status_code == 400

    def test_an_off_grid_delivery_slot_is_refused(self, client: TestClient) -> None:
        response = client.post("/api/signup", json=signup_payload(delivery_slot="07:15"))

        assert response.status_code == 400

    def test_an_unknown_genre_is_refused(self, client: TestClient) -> None:
        response = client.post("/api/signup", json=signup_payload(genres=["cooking"]))

        assert response.status_code == 422

    def test_beyond_the_cap_a_signup_is_waitlisted(
        self, client: TestClient, session: Session, config: dict[str, Settings]
    ) -> None:
        """The Gmail quota covers transactional mail too, so the cap is real."""
        make_user(session, email="taken@example.com")
        config["settings"] = settings(max_active_subscribers=1)

        response = client.post("/api/signup", json=signup_payload())

        assert response.json()["status"] == "waitlisted"
        user = session.scalar(select(User).where(User.email == "asha@example.com"))
        assert user is not None
        assert user.status is SubscriptionStatus.WAITLISTED
        assert count(session, WaitlistEntry) == 1
        # No opt-in mail: there is nothing to confirm until a place opens.
        assert CapturingSender.sent == []

    def test_signup_is_rate_limited(self, client: TestClient) -> None:
        codes = [
            client.post(
                "/api/signup", json=signup_payload(email=f"reader{i}@example.com")
            ).status_code
            for i in range(8)
        ]

        assert codes[-1] == 429


# ===================================================================== opt-in


class TestOptIn:
    def test_confirming_activates_the_subscription(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session, status=SubscriptionStatus.PENDING)
        raw = tokens.issue(session, user_id=user.id, purpose=TokenPurpose.OPT_IN)

        response = client.post(f"/opt-in/{raw}")

        assert response.status_code == 200
        assert user.status is SubscriptionStatus.ACTIVE
        assert user.status_changed_at is not None

    def test_a_confirmation_link_works_once(self, client: TestClient, session: Session) -> None:
        user = make_user(session, status=SubscriptionStatus.PENDING)
        raw = tokens.issue(session, user_id=user.id, purpose=TokenPurpose.OPT_IN)

        assert client.post(f"/opt-in/{raw}").status_code == 200
        assert client.post(f"/opt-in/{raw}").status_code == 400

    def test_an_unknown_token_is_refused(self, client: TestClient) -> None:
        assert client.post("/opt-in/not-a-real-token").status_code == 400

    def test_confirming_does_not_revive_an_unsubscribed_reader(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session, status=SubscriptionStatus.UNSUBSCRIBED)
        raw = tokens.issue(session, user_id=user.id, purpose=TokenPurpose.OPT_IN)

        client.post(f"/opt-in/{raw}")

        assert user.status is SubscriptionStatus.UNSUBSCRIBED


# ================================================================ unsubscribe


class TestUnsubscribe:
    def test_posting_unsubscribes_immediately(self, client: TestClient, session: Session) -> None:
        user = make_user(session)
        raw = tokens.ensure_unsubscribe_token(session, user.id)

        response = client.post(f"/unsubscribe/{raw}")

        assert response.status_code == 200
        assert user.status is SubscriptionStatus.UNSUBSCRIBED

    def test_one_click_unsubscribe_needs_no_page(
        self, client: TestClient, session: Session
    ) -> None:
        """RFC 8058: the mail client POSTs directly, with no browser involved."""
        user = make_user(session)
        raw = tokens.ensure_unsubscribe_token(session, user.id)

        response = client.post(
            f"/unsubscribe/{raw}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            content="List-Unsubscribe=One-Click",
        )

        assert response.status_code == 200
        assert user.status is SubscriptionStatus.UNSUBSCRIBED

    def test_unsubscribing_twice_is_not_an_error(
        self, client: TestClient, session: Session
    ) -> None:
        """The link lives in every edition ever sent; it cannot expire or burn."""
        user = make_user(session)
        raw = tokens.ensure_unsubscribe_token(session, user.id)

        assert client.post(f"/unsubscribe/{raw}").status_code == 200
        assert client.post(f"/unsubscribe/{raw}").status_code == 200
        assert user.status is SubscriptionStatus.UNSUBSCRIBED


# =================================================================== feedback


class TestFeedback:
    def test_posting_records_the_vote(self, client: TestClient, session: Session) -> None:
        user = make_user(session)
        story = publish(session)

        response = client.post(f"/feedback/{feedback_token(story, user)}")

        assert response.status_code == 200
        vote = session.scalar(select(Feedback))
        assert vote is not None
        assert vote.vote is Vote.UP

    def test_changing_your_mind_replaces_the_vote(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        story = publish(session)

        client.post(f"/feedback/{feedback_token(story, user, Vote.UP)}")
        client.post(f"/feedback/{feedback_token(story, user, Vote.DOWN)}")

        assert count(session, Feedback) == 1
        vote = session.scalar(select(Feedback))
        assert vote is not None
        assert vote.vote is Vote.DOWN
        # Cleared so the next aggregation run counts the change.
        assert vote.aggregated_at is None

    def test_a_forged_token_is_refused(self, client: TestClient, session: Session) -> None:
        user = make_user(session)
        story = publish(session)
        good = feedback_token(story, user)
        forged = good[:-4] + ("bbbb" if good.endswith("aaaa") else "aaaa")

        assert client.post(f"/feedback/{forged}").status_code == 400
        assert count(session, Feedback) == 0

    def test_a_vote_for_an_unknown_story_is_refused(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        token = tokens.sign(tokens.FEEDBACK, str(uuid.uuid4()), user=str(user.id), vote="up")

        assert client.post(f"/feedback/{token}").status_code == 400

    def test_a_pdf_token_cannot_be_replayed_as_feedback(
        self, client: TestClient, session: Session
    ) -> None:
        user = make_user(session)
        story = publish(session)
        token = tokens.sign(tokens.PDF, str(story.id), user=str(user.id), vote="up")

        assert client.post(f"/feedback/{token}").status_code == 400
        assert count(session, Feedback) == 0


# ==================================================================== archive


class TestArchive:
    def test_an_edition_is_private_until_the_last_slot_has_passed(self) -> None:
        """A reader on the 09:00 slot must not be scooped by the website."""
        day = date(2026, 10, 5)
        before = datetime(2026, 10, 5, 2, 0, tzinfo=UTC)  # 07:30 IST
        after = datetime(2026, 10, 5, 4, 0, tzinfo=UTC)  # 09:30 IST

        assert not is_public(day, now=before)
        assert is_public(day, now=after)

    def test_yesterday_is_public_and_tomorrow_is_not(self) -> None:
        moment = datetime(2026, 10, 5, 2, 0, tzinfo=UTC)

        assert is_public(date(2026, 10, 4), now=moment)
        assert not is_public(date(2026, 10, 6), now=moment)

    def test_a_published_edition_is_readable(self, client: TestClient, session: Session) -> None:
        publish(session)

        response = client.get(f"/api/archive/{EDITION.isoformat()}")

        assert response.status_code == 200
        body = response.json()
        assert body["edition_number"] == 5
        assert body["revision"] == 1
        assert body["sections"][0]["genre"] == "india"
        assert "archive copy" in body["sections"][0]["html"]

    def test_a_day_that_is_not_public_yet_looks_like_one_that_never_existed(
        self, client: TestClient
    ) -> None:
        assert client.get("/api/archive/2099-01-01").status_code == 404

    def test_the_listing_shows_published_editions(
        self, client: TestClient, session: Session
    ) -> None:
        publish(session)

        response = client.get("/api/archive")

        assert response.status_code == 200
        assert [row["edition_date"] for row in response.json()] == [EDITION.isoformat()]


# ===================================================================== basics


def test_security_headers_are_present(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_health_reports_ok(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_the_docs_are_closed_in_prod() -> None:
    prod = create_app(settings(app_env="prod"))

    assert prod.openapi_url is None
    assert prod.docs_url is None


class TestConfig:
    def test_exposes_genres_cities_and_fixed_choices(
        self, client: TestClient, session: Session
    ) -> None:
        response = client.get("/api/config")

        assert response.status_code == 200
        body = response.json()
        genre_keys = {genre["key"] for genre in body["genres"]}
        assert "india" in genre_keys
        assert len(body["genres"]) == 10
        city_ids = {city["id"] for city in body["cities"]}
        assert "mumbai" in city_ids
        assert "06:00:00" in body["delivery_slots"]
        assert body["frequencies"] == ["daily", "weekdays"]
        assert body["edition_preferences"] == ["india", "global", "mixed"]

    def test_an_inactive_city_is_not_listed(self, client: TestClient, session: Session) -> None:
        from app.models.users import City

        mumbai = session.get(City, "mumbai")
        assert mumbai is not None
        mumbai.active = False
        session.flush()

        response = client.get("/api/config")

        assert "mumbai" not in {city["id"] for city in response.json()["cities"]}
