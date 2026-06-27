"""ENG-123 (1/4): create tenant domain tables.

Revision ID: c1f9d3a4b8e2
Revises: 4ba791c47185
Create Date: 2026-05-09 12:00:00.000000+00:00

Per ADR-0003 (docs/decisions/ADR-0003-tenant-domain-multi-tenancy.md).

Creates four tables in the `tenant` schema: tenant, location,
integration_credential, setting. The `tenant` schema itself is created
by `infra/docker/init-schemas.sql` on a fresh dev volume; on existing
environments the schema must exist before this migration runs.

This migration ONLY creates the new tables. The next three migrations
(ENG-123 2/4, 3/4, 4/4) add `tenant_id` columns to existing domain
tables, seed the bootstrap tenant + backfill, and finally promote the
columns to NOT NULL + FK.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1f9d3a4b8e2"
down_revision: str | None = "4ba791c47185"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # tenant.tenant ---------------------------------------------------
    op.create_table(
        "tenant",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("primary_email", sa.String(length=320), nullable=True),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default=sa.text("'America/Los_Angeles'"),
            nullable=False,
        ),
        sa.Column(
            "locale",
            sa.String(length=16),
            server_default=sa.text("'en-US'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'archived')",
            name=op.f("ck_tenant_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant")),
        sa.UniqueConstraint("slug", name="uq_tenant_slug"),
        schema="tenant",
    )
    op.create_index("ix_tenant_status", "tenant", ["status"], schema="tenant")

    # tenant.location -------------------------------------------------
    op.create_table(
        "location",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "external_ref",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("short_name", sa.String(length=64), nullable=True),
        sa.Column("address_line1", sa.String(length=240), nullable=True),
        sa.Column("address_line2", sa.String(length=240), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=True),
        sa.Column("zip", sa.String(length=32), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("timezone_override", sa.String(length=64), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_location_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_location")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_location_tenant_id_name"),
        schema="tenant",
    )
    op.create_index(
        "ix_location_tenant_id",
        "location",
        ["tenant_id"],
        schema="tenant",
    )
    op.create_index(
        "ix_location_active",
        "location",
        ["tenant_id"],
        schema="tenant",
        postgresql_where=sa.text("is_active = true"),
    )

    # tenant.integration_credential ----------------------------------
    op.create_table(
        "integration_credential",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("provider_kind", sa.String(length=32), nullable=False),
        sa.Column("credential_kind", sa.String(length=32), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=240), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider_kind IN "
            "('salesforce', 'hubspot', 'carestack', 'open_dental', 'other')",
            name=op.f("ck_integration_credential_provider_kind"),
        ),
        sa.CheckConstraint(
            "credential_kind IN "
            "('oauth_token', 'api_key', 'password_grant', 'webhook_secret')",
            name=op.f("ck_integration_credential_credential_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'revoked')",
            name=op.f("ck_integration_credential_status"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_integration_credential_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_credential")),
        schema="tenant",
    )
    op.create_index(
        "ix_integration_credential_tenant_id",
        "integration_credential",
        ["tenant_id"],
        schema="tenant",
    )
    op.create_index(
        "ix_integration_credential_active",
        "integration_credential",
        ["tenant_id", "provider_kind"],
        schema="tenant",
        postgresql_where=sa.text("status = 'active'"),
    )

    # tenant.setting --------------------------------------------------
    op.create_table(
        "setting",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column(
            "value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_setting_tenant_id_tenant"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tenant_id", "key", name="pk_setting"),
        schema="tenant",
    )
    op.create_index(
        "ix_setting_tenant_id",
        "setting",
        ["tenant_id"],
        schema="tenant",
    )


def downgrade() -> None:
    op.drop_index("ix_setting_tenant_id", table_name="setting", schema="tenant")
    op.drop_table("setting", schema="tenant")

    op.drop_index(
        "ix_integration_credential_active",
        table_name="integration_credential",
        schema="tenant",
    )
    op.drop_index(
        "ix_integration_credential_tenant_id",
        table_name="integration_credential",
        schema="tenant",
    )
    op.drop_table("integration_credential", schema="tenant")

    op.drop_index("ix_location_active", table_name="location", schema="tenant")
    op.drop_index("ix_location_tenant_id", table_name="location", schema="tenant")
    op.drop_table("location", schema="tenant")

    op.drop_index("ix_tenant_status", table_name="tenant", schema="tenant")
    op.drop_table("tenant", schema="tenant")
