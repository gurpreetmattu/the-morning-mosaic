"""One story, one genre: the same event pooled by two genres is kept by only one."""

from __future__ import annotations

from datetime import UTC, datetime

from app.agents.crossgenre import ArticleMark, StoryMark, assign_owners
from app.agents.schemas import Corroboration, PooledStory
from app.config.loader import load_genres
from app.config.schemas import GenreKey
from app.sources.schemas import CollectedArticle, Passage

NOW = datetime(2026, 10, 16, 4, 15, tzinfo=UTC)


def story(
    label: str,
    *,
    url: str,
    title: str,
    text: str | None = None,
    canonical: str | None = None,
    rank: int = 1,
) -> PooledStory:
    body = text or f"{label} unique body text " + " ".join(f"{label}{k}" for k in range(12))
    return PooledStory(
        event_label=label,
        articles=[
            CollectedArticle(
                source_key="wire",
                genre="ai",
                url=url,
                canonical_url=canonical,
                title=title,
                published_at=NOW,
                fetched_at=NOW,
                text=body,
                passages=[Passage(ordinal=1, text=body)],
                content_hash=f"h-{label}",
            )
        ],
        corroboration=Corroboration.PRIMARY_OFFICIAL,
        hedged=False,
        score=1.0,
        rank=rank,
    )


def labels(stories: list[PooledStory]) -> list[str]:
    return [s.event_label for s in stories]


ORDER: list[GenreKey] = ["ai", "technology", "india"]

META_AI = story(
    "meta-ai", url="https://a.example/meta-muse", title="Meta releases Muse Spark open model"
)
OTHER_TECH = story("phones", url="https://b.example/phones", title="Budget phones launch this week")


def test_a_shared_article_is_kept_by_the_higher_priority_genre_only() -> None:
    same = story("meta-tech", url="https://a.example/meta-muse", title="Totally different words")

    result = assign_owners({"technology": [same, OTHER_TECH], "ai": [META_AI]}, order=ORDER)

    assert labels(result.kept["ai"]) == ["meta-ai"]
    assert labels(result.kept["technology"]) == ["phones"]
    assert result.dropped == {"technology": ["meta-tech"]}


def test_url_tracking_noise_and_the_canonical_link_still_match() -> None:
    noisy = story(
        "meta-tech",
        url="HTTP://A.example/meta-muse/?utm_source=rss#top",
        title="Something else entirely",
    )
    via_canonical = story(
        "meta-canon",
        url="https://c.example/amp/meta",
        canonical="https://a.example/meta-muse",
        title="Another unrelated headline",
    )

    result = assign_owners(
        {"ai": [META_AI], "technology": [noisy], "india": [via_canonical]}, order=ORDER
    )

    assert result.kept["technology"] == []
    assert result.kept["india"] == []


def test_a_near_identical_headline_from_a_different_outlet_matches() -> None:
    other_outlet = story(
        "meta-tech",
        url="https://z.example/story/991",
        title="Meta releases Muse Spark open model for Macs",
    )

    result = assign_owners({"ai": [META_AI], "technology": [other_outlet]}, order=ORDER)

    assert result.kept["technology"] == []


def test_heavily_overlapping_text_matches_even_with_unrelated_headlines() -> None:
    wire = " ".join(f"word{k}" for k in range(60))
    first = story("one", url="https://a.example/1", title="Alpha bravo", text=wire)
    copy = story("two", url="https://b.example/2", title="Charlie delta", text=wire)

    result = assign_owners({"ai": [first], "technology": [copy]}, order=ORDER)

    assert result.kept["technology"] == []


def test_different_events_in_both_genres_are_all_kept() -> None:
    result = assign_owners({"ai": [META_AI], "technology": [OTHER_TECH]}, order=ORDER)

    assert labels(result.kept["ai"]) == ["meta-ai"]
    assert labels(result.kept["technology"]) == ["phones"]
    assert result.dropped == {}


def test_the_outcome_does_not_depend_on_which_genre_arrived_first() -> None:
    same = story("meta-tech", url="https://a.example/meta-muse", title="Totally different words")
    forward = assign_owners({"ai": [META_AI], "technology": [same]}, order=ORDER)
    backward = assign_owners({"technology": [same], "ai": [META_AI]}, order=ORDER)

    assert labels(forward.kept["ai"]) == labels(backward.kept["ai"]) == ["meta-ai"]
    assert forward.kept["technology"] == backward.kept["technology"] == []


def test_a_genre_missing_from_the_priority_list_comes_last() -> None:
    same = story("meta-sports", url="https://a.example/meta-muse", title="Unrelated sports words")

    result = assign_owners({"sports": [same], "technology": [META_AI]}, order=["technology"])

    assert labels(result.kept["technology"]) == ["meta-ai"]
    assert result.kept["sports"] == []


def test_two_similar_stories_inside_one_genre_are_left_alone() -> None:
    """Within a genre the Ranker already clustered; this step only looks across genres."""
    a = story("a", url="https://a.example/x", title="Same words here today")
    b = story("b", url="https://b.example/y", title="Same words here today")

    result = assign_owners({"ai": [a, b]}, order=ORDER)

    assert labels(result.kept["ai"]) == ["a", "b"]


def test_a_story_already_published_in_another_genre_blocks_a_new_candidate() -> None:
    published = StoryMark(
        genre="ai",
        label="Meta launches Muse",
        articles=(ArticleMark(url="https://a.example/meta-muse", title="Whatever"),),
    )
    candidate = story("meta-tech", url="https://a.example/meta-muse", title="Another title")

    result = assign_owners(
        {"technology": [candidate, OTHER_TECH]}, order=ORDER, published=[published]
    )

    assert labels(result.kept["technology"]) == ["phones"]


def test_a_published_story_in_the_same_genre_is_not_this_steps_concern() -> None:
    published = StoryMark(
        genre="technology",
        label="x",
        articles=(ArticleMark(url="https://a.example/meta-muse", title="Whatever"),),
    )
    candidate = story("meta-tech", url="https://a.example/meta-muse", title="Another title")

    result = assign_owners({"technology": [candidate]}, order=ORDER, published=[published])

    assert labels(result.kept["technology"]) == ["meta-tech"]


def test_the_real_config_gives_every_genre_exactly_one_place_in_the_order() -> None:
    config = load_genres()

    order = config.dedup_order

    assert sorted(order) == sorted(genre.key for genre in config.genres)
    # The specific genre beats the generic ones that cover the same news.
    assert order.index("ai") < order.index("technology") < order.index("india")
