"""ENG-123 (3/4): bootstrap tenant + backfill `tenant_id` everywhere.

Revision ID: e3a1b6c7d4f5
Revises: d2e0f4b5c9a3
Create Date: 2026-05-09 12:02:00.000000+00:00

Inserts the seed `tenant.tenant` row (slug=`fusion-dental-implants`)
with a stable, deterministic UUID so dev / staging / prod environments
end up referencing the same tenant id. Then UPDATEs every per-tenant
table to set `tenant_id` = that uuid for every existing row.

Idempotent on the seed: ON CONFLICT (slug) DO NOTHING ensures re-runs
don't create duplicate tenants. The backfill targets only rows where
`tenant_id IS NULL`, so re-running is a no-op once everything has
already been backfilled.

The deterministic UUID is documented in ADR-0003. It MUST NOT be
changed once any environment has applied this migration — every FK in
every domain table points to it after migration 4/4 promotes the
columns.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e3a1b6c7d4f5"
down_revision: str | None = "d2e0f4b5c9a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Stable bootstrap tenant id. Generated once for the alpha clinic and
# treated as configuration: changing this breaks every backfilled FK
# in every domain table.
BOOTSTRAP_TENANT_ID = "11111111-1111-4111-8111-111111111111"
BOOTSTRAP_TENANT_SLUG = "fusion-dental-implants"
BOOTSTRAP_TENANT_NAME = "Fusion Dental Implants"
BOOTSTRAP_TENANT_TIMEZONE = "America/Los_Angeles"
BOOTSTRAP_TENANT_LOCALE = "en-US"


# (schema, table) — every table that gained `tenant_id` in migration 2/4.
BACKFILL_TABLES: tuple[tuple[str, str], ...] = (
    ("identity", "person"),
    ("identity", "person_identifier"),
    ("identity", "source_link"),
    ("identity", "merge_event"),
    ("ops", "lead"),
    ("ops", "followup_task"),
    ("ops", "account"),
    ("phi", "patient_profile"),
    ("phi", "consultation"),
    ("audit", "access_log"),
    ("ingest", "raw_event"),
    ("actor", "actor"),
    ("actor", "actor_identifier"),
    ("auth", "credential"),
    ("auth", "session"),
    ("auth", "api_key"),
    ("interaction", "event"),
    ("integrations", "integration_account"),
    ("integrations", "object_mapping"),
    ("integrations", "sync_run"),
    ("integrations", "cdc_cursor"),
    ("integrations", "external_entity"),
)


def upgrade() -> None:
    # Seed the tenant row. ON CONFLICT (slug) DO NOTHING makes the
    # statement idempotent — re-runs against an already-seeded DB are
    # safe.
    op.execute(
        f"""
        INSERT INTO tenant.tenant
            (id, slug, name, primary_email, timezone, locale, status,
             created_at, updated_at)
        VALUES
            ('{BOOTSTRAP_TENANT_ID}', '{BOOTSTRAP_TENANT_SLUG}',
             '{BOOTSTRAP_TENANT_NAME}', NULL,
             '{BOOTSTRAP_TENANT_TIMEZONE}', '{BOOTSTRAP_TENANT_LOCALE}',
             'active', now(), now())
        ON CONFLICT (slug) DO NOTHING
        """
    )

    # Backfill every per-tenant table. Targeting `WHERE tenant_id IS NULL`
    # keeps the statement idempotent on re-run after partial application.
    for schema, table in BACKFILL_TABLES:
        op.execute(
            f"UPDATE {schema}.{table} "
            f"SET tenant_id = '{BOOTSTRAP_TENANT_ID}' "
            f"WHERE tenant_id IS NULL"
        )


def downgrade() -> None:
    # Reverse: NULL out `tenant_id` everywhere we backfilled it (so
    # migration 2/4's downgrade can drop the column cleanly), then
    # delete the seed tenant row.
    for schema, table in reversed(BACKFILL_TABLES):
        op.execute(
            f"UPDATE {schema}.{table} "
            f"SET tenant_id = NULL "
            f"WHERE tenant_id = '{BOOTSTRAP_TENANT_ID}'"
        )
    op.execute(
        f"DELETE FROM tenant.tenant WHERE id = '{BOOTSTRAP_TENANT_ID}'"
    )
