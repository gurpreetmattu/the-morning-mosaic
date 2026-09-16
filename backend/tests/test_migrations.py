"""Migrations must stay in step with the models, and must not branch."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Enum as SAEnum
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.db.engine import normalise_url
from app.models import Base

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "backend" / "migrations"

TEST_DB_ENV = "TEST_DATABASE_URL"


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


@pytest.mark.integration
def test_the_migration_chain_runs_against_a_real_database() -> None:
    """The other tests in this file are static (source-text) checks; the
    test suite otherwise builds its schema with `Base.metadata.create_all`
    (see conftest.py's `engine` fixture), so nothing ever actually ran
    `alembic upgrade`/`downgrade` until this test. A throwaway database on
    the same server keeps this fully isolated from every other test.
    """
    base_url = os.getenv(TEST_DB_ENV)
    if not base_url:
        pytest.skip(f"{TEST_DB_ENV} is not set")

    server = make_url(base_url)
    admin_engine = create_engine(normalise_url(server.render_as_string(hide_password=False)))
    throwaway = f"alembic_check_{uuid.uuid4().hex[:12]}"
    throwaway_url = server.set(database=throwaway).render_as_string(hide_password=False)

    with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f'CREATE DATABASE "{throwaway}"'))

    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(MIGRATIONS))

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = throwaway_url
    try:
        command.upgrade(config, "head")
        command.downgrade(config, "base")
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{throwaway}"'))
        admin_engine.dispose()
