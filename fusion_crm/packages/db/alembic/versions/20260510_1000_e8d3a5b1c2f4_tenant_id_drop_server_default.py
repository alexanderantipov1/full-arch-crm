"""ENG-128: drop the transitional ``tenant_id`` server_default.

Revision ID: e8d3a5b1c2f4
Revises: a8c5e7d2f4b9
Create Date: 2026-05-10 10:00:00.000000+00:00

Closes the loop on the ENG-123 4/4 transitional safety net. That migration
set ``tenant_id`` to NOT NULL on every per-tenant table while attaching a
``server_default`` of the bootstrap tenant id, so existing INSERTs that did
not yet pass ``tenant_id`` explicitly kept working in single-tenant Phase 1.

After the ENG-128 repository-signature sweep every INSERT explicitly passes
``tenant_id`` from the principal (API), worker job kwargs (cron), or tool
context (MCP). The default is therefore safety-net-only and we drop it so
that an accidentally unscoped INSERT fails NOT NULL loudly instead of
silently writing the row into the bootstrap tenant.

The column itself stays NOT NULL with the FK to ``tenant.tenant.id`` —
this migration only drops the DEFAULT clause.

Mirror table list with ENG-123 4/4 (``20260509_1203_f4b2c8d9e6a7``); the
order does not matter for ALTER COLUMN DROP DEFAULT because the
operations are independent.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8d3a5b1c2f4"
down_revision: str | None = "a8c5e7d2f4b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Bootstrap tenant id duplicated here from migration ENG-123 4/4 so the
# downgrade path can re-apply the safety-net default without importing
# the older migration file (Alembic revisions must be self-contained —
# the previous migration may be renamed / archived in a later cleanup).
BOOTSTRAP_TENANT_ID = "11111111-1111-4111-8111-111111111111"


# Same set as ENG-123 4/4 (``20260509_1203_f4b2c8d9e6a7``). Order is preserved
# for readability — ALTER COLUMN DROP DEFAULT operations are independent so
# there is no ordering requirement at the DDL level.
TABLES: tuple[tuple[str, str], ...] = (
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
    for schema, table in TABLES:
        op.alter_column(
            table,
            "tenant_id",
            server_default=None,
            schema=schema,
        )


def downgrade() -> None:
    """Re-apply the transitional bootstrap default on every per-tenant table.

    The downgrade restores the safety net so a partial-rollback environment
    (running the new app pre-sweep against a downgraded DB) keeps working
    until the ENG-128 sweep is re-applied. Idempotent.
    """
    for schema, table in TABLES:
        op.alter_column(
            table,
            "tenant_id",
            server_default=sa.text(f"'{BOOTSTRAP_TENANT_ID}'::uuid"),
            schema=schema,
        )
