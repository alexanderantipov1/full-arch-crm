"""Alembic env: uses the SYNC database URL and registers all domain models."""

from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from packages.core.config import get_settings
from packages.db import registry  # noqa: F401  — registers all domain models
from packages.db.base import Base

# Alembic commands run from `packages/db` (locally and in the Cloud Run Job),
# so the root `.env` is not on the cwd-relative path that `Settings` searches.
# Load it explicitly when present. In production the file is absent and env
# vars are injected directly, so this is a no-op.
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
if _ROOT_ENV.exists():
    load_dotenv(_ROOT_ENV)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
sync_url = str(settings.database_url_sync or settings.database_url).replace(
    "+asyncpg", "+psycopg"
)
config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = Base.metadata

# Each domain owns its own PostgreSQL schema. Tell Alembic to track them all.
DOMAIN_SCHEMAS = (
    "identity",
    "ops",
    "phi",
    "audit",
    "ingest",
    # M1 vertical-slice schemas (added 2026-05-01).
    "actor",
    "auth",
    "integrations",
    # Phase 1 slice subset of v0.2 §5 (added 2026-05-05 with ENG-2 / D1).
    "interaction",
    # Multi-tenancy root (added 2026-05-09 with ENG-123 / ADR-0003).
    "tenant",
    # Outreach (added 2026-05-10 with ENG-133 / ADR-0004).
    "outreach",
    # Semantic analytics catalog storage (added 2026-06-02 with ENG-314).
    "insight",
    # Workspace-wide reference data (added 2026-06-13 with ENG-420).
    "catalog",
    # Manual-enrichment store (added 2026-06-15 with ENG-439 / Block F).
    "enrichment",
    # Lead source attribution chain (added 2026-06-15 with ENG-446 / ENG-447).
    "attribution",
    # Ad-spend + campaign metrics from ad platforms (added 2026-06-15).
    "marketing",
    # Operator-approved read-model layer: fact_patient_journey + derived
    # analytics (added 2026-06-18 with ENG-504 / ENG-505). Rebuildable
    # projection, never a source of truth.
    "analytics",
)


def include_name(name: str | None, type_: str, _parent_names: dict) -> bool:
    """Restrict autogenerate to our domain schemas (ignore public, pg_*, etc.)."""
    if type_ == "schema":
        return name in DOMAIN_SCHEMAS
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        include_name=include_name,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
