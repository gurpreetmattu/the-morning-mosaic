"""The build job: the whole pipeline, against the real database."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, date, datetime, time, timedelta

import httpx
import pytest
import respx
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.agents.image_finder import COMMONS_API, PEXELS_SEARCH_API, UNSPLASH_SEARCH_API
from app.agents.orchestrator import CollectorLike, Orchestrator, VerifyFn
from app.agents.schemas import (
    Corroboration,
    DraftSentence,
    GenreOutcome,
    PooledStory,
    StoryPool,
    VerificationOutcome,
    VerifiedStory,
    WrittenStory,
)
from app.config.loader import load_editions, load_genres
from app.config.schemas import EditionsConfig, GenreKey, ModelsConfig
from app.config.settings import Settings
from app.db.persist import persist_genre
from app.db.seed import seed_sources
from app.jobs.build import BUILD_DEADLINE_IST, BuildReport, deadline_for, run_build
from app.jobs.locking import job_lock, lock_key
from app.llm.client import LlmClient
from app.models.content import Extra, Image, SentenceCitation, Story, WeekendFeature
from app.models.editions import Edition, EditionRevision, EditionSection
from app.models.enums import ExtraKind, JobName, RunStatus, SectionStatus, WeekendFeatureKind
from app.models.operations import PipelineRun
from app.render.sections import SectionRenderer
from app.services.deals import CHEAPSHARK_DEALS_API, CHEAPSHARK_STORES_API
from app.services.markets import FRANKFURTER_API
from app.services.quotes import WIKIPEDIA_ONTHISDAY_API, WIKIQUOTE_API
from app.services.releases import TMDB_UPCOMING_API
from app.services.sports import CRICBUZZ_RECENT_API, CRICBUZZ_UPCOMING_API
from app.sources.fetch import Fetcher
from app.sources.schemas import CollectedArticle, CollectionResult, Passage

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 5, 4, 15, tzinfo=UTC)
DEADLINE = NOW + timedelta(hours=1)
EDITION = date(2026, 10, 5)

BODY = "The cabinet approved the eastern freight corridor on Tuesday, officials said."

QUOTE_URL_PATTERN = re.compile(rf"^{re.escape(WIKIQUOTE_API)}\?.*")
OTD_URL_PATTERN = re.compile(rf"^{re.escape(WIKIPEDIA_ONTHISDAY_API)}/10/05$")
QUOTE_WIKITEXT = (
    "{{Wikiquote:Quote of the day/Template\n"
    "| quote = [[Shakespeare]]'s stage <br /> holds the glass\n"
    "| author = Francis Turner Palgrave\n"
    "}}"
)
ONTHISDAY_PAYLOAD = {
    "selected": [
        {
            "year": 2023,
            "text": "The Sycamore Gap tree was illegally felled.",
            "pages": [{"title": "Sycamore_Gap_tree"}],
        }
    ]
}
MARKET_URL_PATTERN = re.compile(rf"^{re.escape(FRANKFURTER_API)}\?.*")
MARKET_PAYLOAD = {"amount": 1.0, "base": "USD", "date": "2026-10-05", "rates": {"INR": 95.82}}

IMAGE_LLM_GATEWAY = "https://primary.llm.test"
COMMONS_SEARCH_PATTERN = re.compile(rf"^{re.escape(COMMONS_API)}\?action=query&list=search.*")
COMMONS_INFO_PATTERN = re.compile(rf"^{re.escape(COMMONS_API)}\?action=query&titles=.*")
UNSPLASH_PATTERN = re.compile(rf"^{re.escape(UNSPLASH_SEARCH_API)}\?.*")
PEXELS_PATTERN = re.compile(rf"^{re.escape(PEXELS_SEARCH_API)}\?.*")


def image_finder_settings() -> Settings:
    return Settings.model_validate(
        {
            "base_url": "https://mosaic.example.com",
            "database_url": "postgresql://u:p@localhost/db",
            "smtp_host": "smtp.example.com",
            "sender_email": "news@example.com",
            "sender_name": "Example",
            "gmail_app_password": "x",
            "imap_host": "imap.example.com",
            "admin_email": "admin@example.com",
            "llm_gateway_url": IMAGE_LLM_GATEWAY,
            "llm_gateway_api_key": "x",
            "token_signing_key": "x",
        }
    )


def image_finder_models() -> ModelsConfig:
    spec = {"model": "img-1", "temperature": 0.0, "max_output_tokens": 256, "pinned": False}
    return ModelsConfig.model_validate(
        {
            "request_timeout_seconds": 5.0,
            "max_attempts": 1,
            "agents": {
                "orchestrator": spec,
                "ranker": spec,
                "writer": {**spec, "pinned": True},
                "fact_checker": {**spec, "pinned": True},
                "image_finder": spec,
            },
        }
    )


def image_finder_llm() -> LlmClient:
    return LlmClient(
        settings=image_finder_settings(), models=image_finder_models(), sleep=lambda _: None
    )


def mock_image_llm_picks(index: int) -> None:
    respx.post(f"{IMAGE_LLM_GATEWAY}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "c",
                "object": "chat.completion",
                "created": 0,
                "model": "img-1",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": json.dumps({"index": index})},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
    )


def extras_fetcher() -> Fetcher:
    """No real sleeping: a failing test would otherwise pay full backoff."""
    clock = [0.0]
    return Fetcher(
        user_agent="TheMorningMosaic/0.1 (+test)",
        sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        monotonic=lambda: clock[0],
    )


def article(index: int) -> CollectedArticle:
    return CollectedArticle(
        source_key="the-hindu",
        genre="india",
        url=f"https://example.test/story-{index}",
        title=f"Corridor story {index}",
        published_at=NOW,
        fetched_at=NOW,
        text=BODY,
        passages=[Passage(ordinal=1, text=BODY)],
        content_hash=f"hash-{index}",
    )


class FakeCollector:
    def __init__(self, count: int = 3) -> None:
        self.count = count

    def collect(self, genre: GenreKey, *, now: datetime | None = None) -> CollectionResult:
        return CollectionResult(genre=genre, articles=[article(i) for i in range(self.count)])


class FakeRanker:
    def rank(self, collected: CollectionResult, *, now: datetime | None = None) -> StoryPool:
        return StoryPool(
            genre=collected.genre,
            stories=[
                PooledStory(
                    event_label=f"event {index}",
                    articles=[item],
                    corroboration=Corroboration.PRIMARY_OFFICIAL,
                    hedged=False,
                    score=5.0,
                    rank=index + 1,
                )
                for index, item in enumerate(collected.articles)
            ],
        )


def verify_all(pooled: PooledStory, genre: GenreKey) -> VerificationOutcome:
    return VerificationOutcome(
        verified=VerifiedStory(
            story=WrittenStory(
                headline=DraftSentence(
                    text=f"Corridor cleared ({pooled.rank})", passage_ids=["a1:p1"]
                ),
                summary=[DraftSentence(text="Ministers approved the plan.", passage_ids=["a1:p1"])],
                topic_tags=["infrastructure"],
                model="test-model",
                prompt_version="writer-v1",
            ),
            articles=list(pooled.articles),
            pool_rank=pooled.rank,
            attempts=1,
        ),
        attempts=1,
    )


def verify_none(pooled: PooledStory, genre: GenreKey) -> VerificationOutcome:
    return VerificationOutcome(verified=None, attempts=3, reason="unverifiable")


def launch_on(launch: date) -> EditionsConfig:
    payload = load_editions().model_dump()
    payload["launch_date"] = launch
    return EditionsConfig.model_validate(payload)


def orchestrator(
    collector: CollectorLike | None = None, verify: VerifyFn = verify_all
) -> Orchestrator:
    return Orchestrator(
        collector=collector or FakeCollector(),
        ranker=FakeRanker(),
        verify=verify,
        genres=load_genres(),
        editions=launch_on(date(2026, 10, 1)),
        max_workers=1,
        clock=lambda: NOW,
    )


def build(
    session: Session,
    *,
    subject: Orchestrator | None = None,
    genres: list[GenreKey] | None = None,
) -> BuildReport:
    return run_build(
        session,
        edition_date=EDITION,
        deadline=DEADLINE,
        orchestrator=subject or orchestrator(),
        renderer=SectionRenderer(),
        genres=genres or ["india"],
        now=NOW,
    )


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def this_run(session: Session) -> PipelineRun | None:
    """The run this test created.

    Scoped by started_at rather than taking the only row: the database is also
    used by hand, so a real `python -m app.jobs.build` can leave committed runs
    behind.
    """
    return session.scalar(select(PipelineRun).where(PipelineRun.started_at == NOW))


@pytest.fixture(autouse=True)
def _sources(session: Session) -> None:
    seed_sources(session)
    session.flush()


# ------------------------------------------------------------- happy path


def test_a_successful_build_publishes_revision_one(session: Session) -> None:
    report = build(session)

    assert report.succeeded
    assert report.published_revision == 1
    assert report.sections == {"india": "ok"}
    assert report.stories_persisted == 3

    edition = session.scalar(select(Edition))
    assert edition is not None
    assert edition.edition_number == 5  # 2026-10-05, launched 2026-10-01


def test_the_published_section_carries_the_rendered_story(session: Session) -> None:
    build(session)

    stored = session.scalar(select(EditionSection))
    assert stored is not None
    assert stored.status is SectionStatus.OK
    assert "Corridor cleared" in (stored.html or "")
    assert "Corridor cleared" in (stored.plain_text or "")
    assert stored.story_count == 3


def test_the_audit_trail_is_written_alongside_the_revision(session: Session) -> None:
    build(session)

    assert count(session, Story) == 3
    # Every published sentence cites a real passage.
    assert count(session, SentenceCitation) == 6  # 3 stories x (headline + summary)


def test_a_saturday_build_also_persists_weekend_features(session: Session) -> None:
    """A Saturday build must produce that day's own section (as any day does)
    plus the week's longer reads and quiz — built from stories verified on
    the preceding weekdays, already persisted before this build runs."""
    saturday = date(2026, 10, 10)
    for day, genre, rank in [
        (date(2026, 10, 5), "sports", 1),
        (date(2026, 10, 6), "business", 1),
        (date(2026, 10, 7), "technology", 2),
        (date(2026, 10, 8), "ai", 1),
    ]:
        persist_genre(
            session,
            edition_date=day,
            outcome=GenreOutcome(
                genre=genre,  # type: ignore[arg-type]
                status=SectionStatus.OK,
                stories=[
                    VerifiedStory(
                        story=WrittenStory(
                            headline=DraftSentence(text=f"{genre} headline", passage_ids=["a1:p1"]),
                            summary=[
                                DraftSentence(text="It was confirmed.", passage_ids=["a1:p1"])
                            ],
                        ),
                        articles=[
                            CollectedArticle(
                                source_key="the-hindu",
                                genre=genre,  # type: ignore[arg-type]
                                url=f"https://example.test/{genre}",
                                title=f"{genre} story",
                                published_at=datetime.combine(day, NOW.time(), tzinfo=UTC),
                                fetched_at=datetime.combine(day, NOW.time(), tzinfo=UTC),
                                text=BODY,
                                passages=[Passage(ordinal=1, text=BODY)],
                                content_hash=f"hash-{genre}",
                            )
                        ],
                        pool_rank=rank,
                        attempts=1,
                    )
                ],
            ),
        )
    session.commit()

    report = run_build(
        session,
        edition_date=saturday,
        deadline=DEADLINE,
        orchestrator=orchestrator(),
        renderer=SectionRenderer(),
        genres=["india"],
        now=NOW,
    )

    assert report.succeeded
    assert report.sections == {"india": "ok"}
    assert set(report.weekend_features) == {"longer_reads", "quiz"}

    rows = session.scalars(
        select(WeekendFeature).where(WeekendFeature.edition_date == saturday)
    ).all()
    assert {row.kind for row in rows} == {
        WeekendFeatureKind.LONGER_READS,
        WeekendFeatureKind.QUIZ,
    }


@respx.mock
def test_a_build_persists_the_days_quote_on_this_day_and_market_strip(
    session: Session,
) -> None:
    respx.get(QUOTE_URL_PATTERN).mock(
        return_value=httpx.Response(200, json={"parse": {"wikitext": {"*": QUOTE_WIKITEXT}}})
    )
    respx.get(OTD_URL_PATTERN).mock(return_value=httpx.Response(200, json=ONTHISDAY_PAYLOAD))
    respx.get(MARKET_URL_PATTERN).mock(return_value=httpx.Response(200, json=MARKET_PAYLOAD))

    report = run_build(
        session,
        edition_date=EDITION,
        deadline=DEADLINE,
        orchestrator=orchestrator(),
        renderer=SectionRenderer(),
        genres=["india"],
        now=NOW,
        extras_fetcher=extras_fetcher(),
    )

    assert report.succeeded
    assert set(report.extras) == {"quote", "on_this_day", "market"}
    rows = session.scalars(select(Extra).where(Extra.edition_date == EDITION)).all()
    assert {row.kind for row in rows} == {ExtraKind.QUOTE, ExtraKind.ON_THIS_DAY, ExtraKind.MARKET}


def test_a_build_without_an_extras_fetcher_persists_no_extras(session: Session) -> None:
    report = build(session)

    assert report.succeeded
    assert report.extras == []


@respx.mock
def test_a_build_attaches_an_image_to_the_sections_top_story(session: Session) -> None:
    respx.get(QUOTE_URL_PATTERN).mock(
        return_value=httpx.Response(200, json={"parse": {"wikitext": {"*": QUOTE_WIKITEXT}}})
    )
    respx.get(OTD_URL_PATTERN).mock(return_value=httpx.Response(200, json=ONTHISDAY_PAYLOAD))
    respx.get(MARKET_URL_PATTERN).mock(return_value=httpx.Response(200, json=MARKET_PAYLOAD))
    respx.get(COMMONS_SEARCH_PATTERN).mock(
        return_value=httpx.Response(
            200, json={"query": {"search": [{"title": "File:Corridor.jpg"}]}}
        )
    )
    respx.get(COMMONS_INFO_PATTERN).mock(
        return_value=httpx.Response(
            200,
            json={
                "query": {
                    "pages": {
                        "1": {
                            "title": "File:Corridor.jpg",
                            "imageinfo": [
                                {
                                    "url": "https://upload.wikimedia.org/corridor.jpg",
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Corridor.jpg",
                                    "width": 1200,
                                    "height": 800,
                                    "extmetadata": {
                                        "LicenseShortName": {"value": "CC0"},
                                        "Artist": {"value": "Jane Doe"},
                                        "ImageDescription": {"value": "A rail corridor"},
                                    },
                                }
                            ],
                        }
                    }
                }
            },
        )
    )
    respx.get(UNSPLASH_PATTERN).mock(return_value=httpx.Response(200, json={"results": []}))
    respx.get(PEXELS_PATTERN).mock(return_value=httpx.Response(200, json={"photos": []}))
    mock_image_llm_picks(0)

    report = run_build(
        session,
        edition_date=EDITION,
        deadline=DEADLINE,
        orchestrator=orchestrator(),
        renderer=SectionRenderer(),
        genres=["india"],
        now=NOW,
        extras_fetcher=extras_fetcher(),
        image_finder_llm=image_finder_llm(),
        unsplash_api_key="uk",
        pexels_api_key="pk",
    )

    assert report.succeeded
    assert report.images == ["india"]

    top_story = session.scalar(
        select(Story)
        .where(Story.edition_date == EDITION, Story.genre == "india")
        .order_by(Story.pool_rank)
        .limit(1)
    )
    assert top_story is not None
    image = session.scalar(select(Image).where(Image.story_id == top_story.id))
    assert image is not None
    assert image.display_url == "https://upload.wikimedia.org/corridor.jpg"
    assert image.credit == "Jane Doe / Wikimedia Commons (CC0)"

    section = session.scalar(select(EditionSection).where(EditionSection.genre == "india"))
    assert section is not None
    assert "https://upload.wikimedia.org/corridor.jpg" in (section.html or "")


def test_a_build_without_an_image_finder_llm_attaches_no_images(session: Session) -> None:
    report = build(session)

    assert report.succeeded
    assert report.images == []
    assert session.scalar(select(Image)) is None


@respx.mock
def test_a_build_attaches_movie_releases_to_a_bollywood_section(session: Session) -> None:
    respx.get(QUOTE_URL_PATTERN).mock(
        return_value=httpx.Response(200, json={"parse": {"wikitext": {"*": QUOTE_WIKITEXT}}})
    )
    respx.get(OTD_URL_PATTERN).mock(return_value=httpx.Response(200, json=ONTHISDAY_PAYLOAD))
    respx.get(MARKET_URL_PATTERN).mock(return_value=httpx.Response(200, json=MARKET_PAYLOAD))
    respx.get(re.compile(rf"^{re.escape(TMDB_UPCOMING_API)}\?.*")).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Drishyam 3",
                        "release_date": "2026-10-09",
                        "overview": "A family outwits the system once again.",
                    }
                ]
            },
        )
    )

    report = run_build(
        session,
        edition_date=EDITION,
        deadline=DEADLINE,
        orchestrator=orchestrator(),
        renderer=SectionRenderer(),
        genres=["bollywood"],
        now=NOW,
        extras_fetcher=extras_fetcher(),
        tmdb_api_key="tk",
    )

    assert report.succeeded
    assert "movie_release:bollywood" in report.extras

    extra = session.scalar(select(Extra).where(Extra.kind == ExtraKind.MOVIE_RELEASE))
    assert extra is not None
    assert extra.genre == "bollywood"

    section = session.scalar(select(EditionSection).where(EditionSection.genre == "bollywood"))
    assert section is not None
    assert "Drishyam 3" in (section.html or "")
    assert "not endorsed, certified, or otherwise approved by TMDB" in (section.html or "")


def test_a_build_without_a_tmdb_key_attaches_no_movie_releases(session: Session) -> None:
    report = build(session, genres=["bollywood"])

    assert report.succeeded
    assert not any(extra.startswith("movie_release:") for extra in report.extras)
    assert session.scalar(select(Extra).where(Extra.kind == ExtraKind.MOVIE_RELEASE)) is None


@respx.mock
def test_a_build_attaches_scores_and_fixtures_to_a_sports_section(session: Session) -> None:
    respx.get(QUOTE_URL_PATTERN).mock(
        return_value=httpx.Response(200, json={"parse": {"wikitext": {"*": QUOTE_WIKITEXT}}})
    )
    respx.get(OTD_URL_PATTERN).mock(return_value=httpx.Response(200, json=ONTHISDAY_PAYLOAD))
    respx.get(MARKET_URL_PATTERN).mock(return_value=httpx.Response(200, json=MARKET_PAYLOAD))
    recent_payload = {
        "typeMatches": [
            {
                "seriesMatches": [
                    {
                        "seriesAdWrapper": {
                            "matches": [
                                {
                                    "matchInfo": {
                                        "state": "Complete",
                                        "team1": {"teamName": "India"},
                                        "team2": {"teamName": "Pakistan"},
                                        "status": "India won by 4 wickets",
                                        "endDate": "1000",
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    respx.get(re.compile(rf"^{re.escape(CRICBUZZ_RECENT_API)}$")).mock(
        return_value=httpx.Response(200, json=recent_payload)
    )
    respx.get(re.compile(rf"^{re.escape(CRICBUZZ_UPCOMING_API)}$")).mock(
        return_value=httpx.Response(200, json={"typeMatches": []})
    )

    report = run_build(
        session,
        edition_date=EDITION,
        deadline=DEADLINE,
        orchestrator=orchestrator(),
        renderer=SectionRenderer(),
        genres=["sports"],
        now=NOW,
        extras_fetcher=extras_fetcher(),
        sports_api_key="sk",
    )

    assert report.succeeded
    assert "score" in report.extras

    extra = session.scalar(select(Extra).where(Extra.kind == ExtraKind.SCORE))
    assert extra is not None
    assert extra.genre == "sports"

    section = session.scalar(select(EditionSection).where(EditionSection.genre == "sports"))
    assert section is not None
    assert "India won by 4 wickets" in (section.html or "")


def test_a_build_without_a_sports_key_attaches_no_scores(session: Session) -> None:
    report = build(session, genres=["sports"])

    assert report.succeeded
    assert "score" not in report.extras
    assert session.scalar(select(Extra).where(Extra.kind == ExtraKind.SCORE)) is None


@respx.mock
def test_a_build_attaches_game_deals_to_a_gaming_section(session: Session) -> None:
    respx.get(QUOTE_URL_PATTERN).mock(
        return_value=httpx.Response(200, json={"parse": {"wikitext": {"*": QUOTE_WIKITEXT}}})
    )
    respx.get(OTD_URL_PATTERN).mock(return_value=httpx.Response(200, json=ONTHISDAY_PAYLOAD))
    respx.get(MARKET_URL_PATTERN).mock(return_value=httpx.Response(200, json=MARKET_PAYLOAD))
    respx.get(re.compile(rf"^{re.escape(CHEAPSHARK_DEALS_API)}\?.*")).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "title": "Great Game",
                    "dealID": "abc123",
                    "storeID": "1",
                    "salePrice": "9.99",
                    "normalPrice": "19.99",
                    "savings": "50.0",
                }
            ],
        )
    )
    respx.get(re.compile(rf"^{re.escape(CHEAPSHARK_STORES_API)}$")).mock(
        return_value=httpx.Response(200, json=[{"storeID": "1", "storeName": "Steam"}])
    )

    report = run_build(
        session,
        edition_date=EDITION,
        deadline=DEADLINE,
        orchestrator=orchestrator(),
        renderer=SectionRenderer(),
        genres=["gaming"],
        now=NOW,
        extras_fetcher=extras_fetcher(),
    )

    assert report.succeeded
    assert "game_deal" in report.extras

    extra = session.scalar(select(Extra).where(Extra.kind == ExtraKind.GAME_DEAL))
    assert extra is not None
    assert extra.genre == "gaming"

    section = session.scalar(select(EditionSection).where(EditionSection.genre == "gaming"))
    assert section is not None
    assert "Great Game" in (section.html or "")
    assert "50% off (Steam)" in (section.html or "")


def test_a_build_without_an_extras_fetcher_attaches_no_game_deals(session: Session) -> None:
    report = build(session, genres=["gaming"])

    assert report.succeeded
    assert "game_deal" not in report.extras
    assert session.scalar(select(Extra).where(Extra.kind == ExtraKind.GAME_DEAL)) is None


def test_the_run_is_recorded_as_succeeded(session: Session) -> None:
    build(session)

    run = this_run(session)
    assert run is not None
    assert run.job is JobName.BUILD
    assert run.status is RunStatus.SUCCEEDED
    assert run.finished_at is not None
    assert run.detail is not None
    assert run.detail["published_revision"] == 1


# ------------------------------------------------------------- failure


def test_a_build_with_nothing_verifiable_publishes_nothing(session: Session) -> None:
    report = build(session, subject=orchestrator(verify=verify_none))

    assert not report.succeeded
    assert report.error is not None
    assert count(session, Edition) == 0
    assert count(session, EditionRevision) == 0


def test_a_failed_build_is_recorded_as_failed(session: Session) -> None:
    build(session, subject=orchestrator(verify=verify_none))

    run = this_run(session)
    assert run is not None
    assert run.status is RunStatus.FAILED


def test_a_build_before_launch_date_fails_cleanly_instead_of_raising(
    session: Session,
) -> None:
    subject = orchestrator()
    subject._editions = launch_on(EDITION + timedelta(days=1))

    report = build(session, subject=subject)

    assert not report.succeeded
    assert report.error is not None
    assert "precedes launch_date" in report.error
    run = this_run(session)
    assert run is not None
    assert run.status is RunStatus.FAILED


def test_a_quiet_genre_alongside_a_good_one_still_publishes(session: Session) -> None:
    class OnlyIndia(FakeCollector):
        def collect(self, genre: GenreKey, *, now: datetime | None = None) -> CollectionResult:
            if genre != "india":
                return CollectionResult(genre=genre, articles=[])
            return super().collect(genre, now=now)

    report = build(
        session,
        subject=orchestrator(collector=OnlyIndia()),
        genres=["india", "politics"],
    )

    assert report.succeeded
    assert report.sections == {"india": "ok", "politics": "quiet_day"}


# ------------------------------------------------------------- deadline


def test_the_deadline_is_an_ist_wall_clock_time() -> None:
    """05:30 IST is 00:00 UTC the same day."""
    assert deadline_for(date(2026, 10, 5)) == datetime(2026, 10, 5, 0, 0, tzinfo=UTC)
    assert time(5, 30) == BUILD_DEADLINE_IST


def test_a_deadline_miss_is_recorded_without_losing_the_edition(
    session: Session,
) -> None:
    clock_now = [NOW]
    calls = [0]

    def slow_verify(pooled: PooledStory, genre: GenreKey) -> VerificationOutcome:
        calls[0] += 1
        if calls[0] == 2:
            # The clock crosses the deadline; the third candidate never starts.
            clock_now[0] = DEADLINE
        return verify_all(pooled, genre)

    subject = Orchestrator(
        collector=FakeCollector(),
        ranker=FakeRanker(),
        verify=slow_verify,
        genres=load_genres(),
        editions=launch_on(date(2026, 10, 1)),
        max_workers=1,
        clock=lambda: clock_now[0],
    )
    report = build(session, subject=subject)

    assert report.deadline_missed is True
    assert report.succeeded  # two stories verified is enough to publish
    run = this_run(session)
    assert run is not None
    assert run.status is RunStatus.DEADLINE_MISSED


def test_a_deadline_miss_logs_the_greppable_alert_message(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """infra/monitoring.tf's log-based metric matches on this literal text."""
    clock_now = [NOW]
    calls = [0]

    def slow_verify(pooled: PooledStory, genre: GenreKey) -> VerificationOutcome:
        calls[0] += 1
        if calls[0] == 2:
            clock_now[0] = DEADLINE
        return verify_all(pooled, genre)

    subject = Orchestrator(
        collector=FakeCollector(),
        ranker=FakeRanker(),
        verify=slow_verify,
        genres=load_genres(),
        editions=launch_on(date(2026, 10, 1)),
        max_workers=1,
        clock=lambda: clock_now[0],
    )

    with caplog.at_level(logging.WARNING):
        build(session, subject=subject)

    assert "build_deadline_missed" in caplog.text


def test_no_deadline_miss_logs_nothing(session: Session, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        build(session)

    assert "build_deadline_missed" not in caplog.text


# --------------------------------------------------------- story-count drop


def _pipeline_run_with_story_count(
    session: Session, *, edition_date: date, count: int, status: RunStatus = RunStatus.SUCCEEDED
) -> None:
    session.add(
        PipelineRun(
            job=JobName.BUILD,
            edition_date=edition_date,
            status=status,
            started_at=NOW - timedelta(days=1),
            finished_at=NOW - timedelta(days=1),
            detail={"stories_persisted": count},
        )
    )
    session.commit()


def test_a_sharp_drop_against_a_real_baseline_is_logged(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    # A week of healthy prior builds (20 stories each), then today's default
    # india-only test build (3 stories, from `build()`'s own fixture data).
    for days_ago in range(1, 6):
        _pipeline_run_with_story_count(
            session, edition_date=EDITION - timedelta(days=days_ago), count=20
        )

    with caplog.at_level(logging.WARNING):
        build(session)

    assert "verified_story_count_drop" in caplog.text


def test_no_drop_alert_without_enough_history(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    # Only one prior day on record — below STORY_COUNT_DROP_MIN_HISTORY, so
    # this is scored as "not enough baseline yet" rather than a false alarm
    # (this is exactly what would otherwise fire every day of launch week).
    _pipeline_run_with_story_count(session, edition_date=EDITION - timedelta(days=1), count=20)

    with caplog.at_level(logging.WARNING):
        build(session)

    assert "verified_story_count_drop" not in caplog.text


def test_no_drop_alert_when_todays_count_holds_up(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    # A baseline low enough that today's one story is not a "sharp" drop.
    for days_ago in range(1, 4):
        _pipeline_run_with_story_count(
            session, edition_date=EDITION - timedelta(days=days_ago), count=1
        )

    with caplog.at_level(logging.WARNING):
        build(session)

    assert "verified_story_count_drop" not in caplog.text


# --------------------------------------------------------------- locking


def test_the_lock_key_is_stable_and_fits_a_signed_64_bit_int() -> None:
    key = lock_key("build")
    assert key == lock_key("build")
    assert lock_key("build") != lock_key("delivery")
    assert -(2**63) <= key < 2**63


def test_a_second_holder_cannot_take_the_same_job_lock(engine: Engine) -> None:
    """A manual rerun during the scheduled run must not publish twice."""
    with job_lock("test-build-guard", connect=engine.connect) as first:
        assert first is True
        with job_lock("test-build-guard", connect=engine.connect) as second:
            assert second is False


def test_the_lock_is_released_when_the_block_exits(engine: Engine) -> None:
    with job_lock("test-build-release", connect=engine.connect) as first:
        assert first is True
    with job_lock("test-build-release", connect=engine.connect) as again:
        assert again is True
