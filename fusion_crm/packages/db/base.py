"""Declarative base + naming convention.

A consistent constraint naming convention is required for Alembic to generate
clean migrations and for production DBAs to recognise objects at a glance.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# PostgreSQL constraint naming convention.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata_obj = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Single declarative base shared by every domain.

    Each domain places its tables inside its own PostgreSQL schema
    (e.g. ``identity``, ``ops``, ``phi``). Schemas are created once by
    ``infra/docker/init-schemas.sql``.
    """

    metadata = metadata_obj
