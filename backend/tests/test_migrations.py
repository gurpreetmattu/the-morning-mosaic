"""Migrations must stay in step with the models, and must not branch."""

from __future__ import annotations

import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Enum as SAEnum

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


def test_downgrade_drops_every_enum_type_it_created() -> None:
    """op.drop_table leaves native enum types behind.

    Without an explicit DROP TYPE, a downgrade followed by an upgrade fails
    with "type already exists", so the migration would not be reversible.
    """
    in_models = {
        column.type.name
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, SAEnum) and column.type.name
    }

    dropped: set[str] = set()
    for path in (MIGRATIONS / "versions").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        block = re.search(r"ENUM_TYPES:[^=]*=\s*\((.*?)\)", source, re.DOTALL)
        if block:
            dropped |= set(re.findall(r"[\"']([\w]+)[\"']", block.group(1)))

    missing = in_models - dropped
    assert missing == set(), f"enum types never dropped on downgrade: {sorted(missing)}"
