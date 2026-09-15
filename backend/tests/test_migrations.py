"""Migrations must stay in step with the models, and must not branch."""

from __future__ import annotations

import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.models import Base

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "backend" / "migrations"


def script_directory() -> ScriptDirectory:
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(MIGRATIONS))
    return ScriptDirectory.from_config(config)


def test_there_is_exactly_one_head() -> None:
    assert len(script_directory().get_heads()) == 1


def test_every_model_table_is_created_by_a_migration() -> None:
    created: set[str] = set()
    for path in (MIGRATIONS / "versions").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        created |= set(re.findall(r"op\.create_table\(\s*[\"']([\w]+)[\"']", source))

    missing = set(Base.metadata.tables) - created
    assert missing == set(), f"tables with no migration: {sorted(missing)}"


def test_migrations_do_not_create_unknown_tables() -> None:
    created: set[str] = set()
    for path in (MIGRATIONS / "versions").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        created |= set(re.findall(r"op\.create_table\(\s*[\"']([\w]+)[\"']", source))

    unknown = created - set(Base.metadata.tables)
    assert unknown == set(), f"migrated tables with no model: {sorted(unknown)}"
