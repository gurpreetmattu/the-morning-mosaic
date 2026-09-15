"""Declarative base, naming conventions, and shared column types.

PostgreSQL is the only target (Neon), so PostgreSQL-specific types are used
directly rather than hidden behind portable variants.

Time policy: every timestamp column is timezone-aware and stored in UTC.
`edition_date` columns are the IST calendar date and are deliberately plain
dates — they are an editorial label, not an instant.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Annotated, Any, ClassVar

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    MetaData,
    String,
    Uuid,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column

from app.config.schemas import GENRE_KEYS

# Deterministic constraint names, so Alembic can always address them by name.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSONB}


def pg_enum[E: enum.Enum](enum_cls: type[E], name: str) -> SAEnum:
    """A native PostgreSQL enum storing member *values*, not member names."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


UuidPk = Annotated[uuid.UUID, mapped_column(Uuid, primary_key=True, default=uuid.uuid4)]

CreatedAt = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False),
]

UpdatedAt = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
]

Instant = Annotated[datetime, mapped_column(DateTime(timezone=True), nullable=False)]
OptionalInstant = Annotated[datetime | None, mapped_column(DateTime(timezone=True), nullable=True)]

# The IST calendar date an edition belongs to.
EditionDate = Annotated[date, mapped_column(Date, nullable=False)]

# Genre keys live in config/genres.yaml; the database refuses anything else, so
# adding a genre is a deliberate migration rather than a stray string.
GenreKeyColumn = Annotated[str, mapped_column(String(32), nullable=False)]


def genre_check(column: str, constraint_name: str) -> CheckConstraint:
    allowed = ", ".join(f"'{key}'" for key in sorted(GENRE_KEYS))
    return CheckConstraint(f"{column} IN ({allowed})", name=constraint_name)
