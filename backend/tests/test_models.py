"""Schema-level guarantees, asserted against metadata without touching a database.

These check the invariants CLAUDE.md calls non-negotiable — idempotent delivery,
immutable revisions, an unbroken citation chain — rather than restating columns.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Table, UniqueConstraint

from app.config.schemas import GENRE_KEYS
from app.models import Base
from app.models.users import DELIVERY_SLOTS

METADATA = Base.metadata


def table(name: str) -> Table:
    return METADATA.tables[name]


def unique_column_sets(name: str) -> set[frozenset[str]]:
    found = {
        frozenset(c.name for c in constraint.columns)
        for constraint in table(name).constraints
        if isinstance(constraint, UniqueConstraint)
    }
    found |= {
        frozenset(c.name for c in index.columns) for index in table(name).indexes if index.unique
    }
    return found


def check_texts(name: str) -> str:
    return " ".join(
        str(c.sqltext) for c in table(name).constraints if isinstance(c, CheckConstraint)
    )


def test_all_expected_tables_exist() -> None:
    expected = {
        "cities",
        "users",
        "user_genres",
        "followed_keywords",
        "consents",
        "waitlist",
        "user_preferences",
        "tokens",
        "outage_state",
        "sources",
        "articles",
        "article_passages",
        "story_clusters",
        "cluster_articles",
        "stories",
        "story_sentences",
        "sentence_citations",
        "story_tags",
        "fact_checks",
        "corrections",
        "story_withdrawals",
        "images",
        "extras",
        "weather_cache",
        "editions",
        "edition_revisions",
        "edition_sections",
        "deliveries",
        "feedback",
        "pipeline_runs",
        "llm_calls",
        "notice_batches",
    }
    assert expected <= set(METADATA.tables)


def test_delivery_is_idempotent_per_user_day_and_type() -> None:
    assert frozenset({"user_id", "edition_date", "type"}) in unique_column_sets("deliveries")


def test_a_sent_newsletter_must_record_the_revision_it_contained() -> None:
    assert "revision_id IS NOT NULL" in check_texts("deliveries")


def test_one_section_per_genre_per_revision() -> None:
    assert frozenset({"revision_id", "genre"}) in unique_column_sets("edition_sections")


def test_revisions_are_numbered_uniquely_within_an_edition() -> None:
    assert frozenset({"edition_id", "revision"}) in unique_column_sets("edition_revisions")


def test_one_edition_and_one_number_per_day() -> None:
    uniques = unique_column_sets("editions")
    assert frozenset({"edition_date"}) in uniques
    assert frozenset({"edition_number"}) in uniques


def test_feedback_is_one_vote_per_user_per_story() -> None:
    assert frozenset({"user_id", "story_id"}) in unique_column_sets("feedback")


def test_citation_chain_is_unbroken() -> None:
    """A sentence cites a passage; a passage belongs to an article."""
    citation = table("sentence_citations")
    targets = {fk.column.table.name for fk in citation.foreign_keys}
    assert targets == {"story_sentences", "article_passages"}
    # The excerpt is frozen on the citation so the trail survives a purge.
    assert not citation.c.excerpt.nullable

    passages = table("article_passages")
    assert {fk.column.table.name for fk in passages.foreign_keys} == {"articles"}


def test_cited_passages_are_never_orphaned_by_a_delete() -> None:
    fk = next(
        fk
        for fk in table("sentence_citations").foreign_keys
        if fk.column.table.name == "article_passages"
    )
    assert fk.ondelete == "RESTRICT"


def test_deleting_a_user_anonymises_rather_than_erases_history() -> None:
    for name in ("deliveries", "feedback"):
        fk = next(fk for fk in table(name).foreign_keys if fk.column.table.name == "users")
        assert fk.ondelete == "SET NULL", name
        assert table(name).c.user_id.nullable, name


def test_a_source_cannot_be_enabled_without_confirmed_terms() -> None:
    assert "NOT enabled OR terms_confirmed" in check_texts("sources")


def test_only_unsubscribe_tokens_may_be_permanent() -> None:
    assert "unsubscribe" in check_texts("tokens")


def test_token_table_stores_only_hashes() -> None:
    columns = set(table("tokens").c.keys())
    assert "token_hash" in columns
    assert "token" not in columns


def test_delivery_slot_is_constrained_to_the_published_slots() -> None:
    text = check_texts("users")
    assert "06:00" in text and "09:00" in text
    assert DELIVERY_SLOTS[0] == "06:00" and DELIVERY_SLOTS[-1] == "09:00"
    assert len(DELIVERY_SLOTS) == 7


def test_genre_columns_are_constrained_to_the_ten_genres() -> None:
    for name in ("user_genres", "articles", "stories", "story_clusters", "edition_sections"):
        text = check_texts(name)
        assert all(f"'{key}'" in text for key in GENRE_KEYS), name


def test_every_timestamp_column_is_timezone_aware() -> None:
    offenders = [
        f"{t.name}.{c.name}"
        for t in METADATA.tables.values()
        for c in t.columns
        if c.type.__class__.__name__ == "DateTime" and not getattr(c.type, "timezone", False)
    ]
    assert offenders == []


def test_constraint_names_follow_the_naming_convention() -> None:
    unnamed = [
        f"{t.name}.{c.name}"
        for t in METADATA.tables.values()
        for c in t.constraints
        if isinstance(c, CheckConstraint) and c.name is None
    ]
    assert unnamed == []
