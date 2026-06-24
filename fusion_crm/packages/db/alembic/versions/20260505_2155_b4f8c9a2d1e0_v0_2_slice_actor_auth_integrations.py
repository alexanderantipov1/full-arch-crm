"""v0.2 slice: actor + auth (minimal) + integrations (full)

Revision ID: b4f8c9a2d1e0
Revises: af6c4e767923
Create Date: 2026-05-05 21:55:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4f8c9a2d1e0"
down_revision: str | None = "af6c4e767923"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "actor",
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("person_uid", sa.UUID(), nullable=True),
        sa.Column(
            "availability_status",
            sa.String(length=16),
            server_default=sa.text("'available'"),
            nullable=False,
        ),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
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
            "actor_type IN ('human', 'ai', 'system', 'external_service')",
            name=op.f("ck_actor_actor_type"),
        ),
        sa.CheckConstraint(
            "availability_status IN ('available', 'busy', 'offline', 'oncall')",
            name=op.f("ck_actor_availability_status"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'retired')",
            name=op.f("ck_actor_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_actor")),
        schema="actor",
    )
    op.create_index("ix_actor_person_uid", "actor", ["person_uid"], schema="actor")
    op.create_index("ix_actor_role", "actor", ["role"], schema="actor")
    op.create_index("ix_actor_status", "actor", ["status"], schema="actor")
    op.create_index("ix_actor_type", "actor", ["actor_type"], schema="actor")

    op.create_table(
        "integration_account",
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column(
            "company_uid",
            sa.UUID(),
            server_default=sa.text("'00000000-0000-0000-0000-000000000000'::uuid"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'connected'"),
            nullable=False,
        ),
        sa.Column("access_token", sa.LargeBinary(), nullable=True),
        sa.Column("refresh_token", sa.LargeBinary(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
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
            "status IN ('connected', 'disconnected', 'error', 'expired')",
            name=op.f("ck_integration_account_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_account")),
        sa.UniqueConstraint(
            "provider",
            "company_uid",
            name="uq_integration_account_provider_company",
        ),
        schema="integrations",
    )
    op.create_index(
        "ix_integration_account_status",
        "integration_account",
        ["status"],
        schema="integrations",
    )

    op.create_table(
        "actor_identifier",
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=320), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
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
            ["actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_actor_identifier_actor_id_actor"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_actor_identifier")),
        sa.UniqueConstraint("kind", "value", name="uq_actor_identifier_kind_value"),
        schema="actor",
    )
    op.create_index(
        op.f("ix_actor_actor_identifier_actor_id"),
        "actor_identifier",
        ["actor_id"],
        schema="actor",
    )
    op.create_index(
        "ix_actor_identifier_value",
        "actor_identifier",
        ["value"],
        schema="actor",
    )

    op.create_table(
        "api_key",
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("token_prefix", sa.String(length=32), nullable=False),
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_actor_id", sa.UUID(), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
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
            "status IN ('active', 'revoked', 'expired')",
            name=op.f("ck_api_key_status"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_api_key_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_api_key_created_by_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_key")),
        sa.UniqueConstraint("token_hash", name="uq_api_key_token_hash"),
        schema="auth",
    )
    op.create_index("ix_api_key_actor_id", "api_key", ["actor_id"], schema="auth")
    op.create_index("ix_api_key_status", "api_key", ["status"], schema="auth")

    op.create_table(
        "credential",
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("credential_kind", sa.String(length=32), nullable=False),
        sa.Column("secret_hash", sa.Text(), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
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
            "credential_kind IN "
            "('password', 'mfa_totp', 'oauth_external', 'sso_subject', 'webauthn')",
            name=op.f("ck_credential_credential_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked', 'expired')",
            name=op.f("ck_credential_status"),
        ),
        sa.CheckConstraint(
            "subject_type IN ('actor', 'portal_account')",
            name=op.f("ck_credential_subject_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credential")),
        schema="auth",
    )
    op.create_index(
        "ix_credential_status",
        "credential",
        ["status"],
        schema="auth",
    )
    op.create_index(
        "ix_credential_subject",
        "credential",
        ["subject_type", "subject_id"],
        schema="auth",
    )
    op.create_index(
        "uq_credential_subject_kind_active",
        "credential",
        ["subject_type", "subject_id", "credential_kind"],
        unique=True,
        schema="auth",
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "session",
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
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
            "subject_type IN ('actor', 'portal_account')",
            name=op.f("ck_session_subject_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session")),
        sa.UniqueConstraint("token_hash", name="uq_session_token_hash"),
        schema="auth",
    )
    op.create_index(
        "ix_session_expires",
        "session",
        ["expires_at"],
        schema="auth",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_session_subject_active",
        "session",
        ["subject_type", "subject_id"],
        schema="auth",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "cdc_cursor",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(length=255), nullable=False),
        sa.Column("replay_id", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
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
            ["account_id"],
            ["integrations.integration_account.id"],
            name=op.f("fk_cdc_cursor_account_id_integration_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cdc_cursor")),
        sa.UniqueConstraint(
            "account_id",
            "channel",
            name="uq_cdc_cursor_account_channel",
        ),
        schema="integrations",
    )

    op.create_table(
        "external_entity",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("person_uid", sa.UUID(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
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
            ["account_id"],
            ["integrations.integration_account.id"],
            name=op.f("fk_external_entity_account_id_integration_account"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_entity")),
        sa.UniqueConstraint(
            "account_id",
            "object_type",
            "external_id",
            name="uq_external_entity_account_type_extid",
        ),
        schema="integrations",
    )
    op.create_index(
        "ix_external_entity_person_uid",
        "external_entity",
        ["person_uid"],
        schema="integrations",
    )

    op.create_table(
        "object_mapping",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("sf_object", sa.String(length=128), nullable=False),
        sa.Column("our_target", sa.String(length=128), nullable=False),
        sa.Column(
            "field_map",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "direction",
            sa.String(length=16),
            server_default=sa.text("'both'"),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
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
            "direction IN ('pull', 'push', 'both')",
            name=op.f("ck_object_mapping_direction"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["integrations.integration_account.id"],
            name=op.f("fk_object_mapping_account_id_integration_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_object_mapping")),
        sa.UniqueConstraint(
            "account_id",
            "sf_object",
            name="uq_object_mapping_account_object",
        ),
        schema="integrations",
    )
    op.create_index(
        "ix_object_mapping_account_enabled",
        "object_mapping",
        ["account_id", "enabled"],
        schema="integrations",
    )

    op.create_table(
        "sync_run",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("sf_object", sa.String(length=128), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'running'"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "records_total",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "records_succeeded",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "records_failed",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
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
            "direction IN ('pull', 'push', 'cdc', 'webhook')",
            name=op.f("ck_sync_run_direction"),
        ),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'failed', 'partial')",
            name=op.f("ck_sync_run_status"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["integrations.integration_account.id"],
            name=op.f("fk_sync_run_account_id_integration_account"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_run")),
        schema="integrations",
    )
    op.create_index(
        "ix_sync_run_account_started",
        "sync_run",
        ["account_id", "started_at"],
        schema="integrations",
    )
    op.create_index(
        "ix_sync_run_status_started",
        "sync_run",
        ["status", "started_at"],
        schema="integrations",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sync_run_status_started",
        table_name="sync_run",
        schema="integrations",
    )
    op.drop_index(
        "ix_sync_run_account_started",
        table_name="sync_run",
        schema="integrations",
    )
    op.drop_table("sync_run", schema="integrations")
    op.drop_index(
        "ix_object_mapping_account_enabled",
        table_name="object_mapping",
        schema="integrations",
    )
    op.drop_table("object_mapping", schema="integrations")
    op.drop_index(
        "ix_external_entity_person_uid",
        table_name="external_entity",
        schema="integrations",
    )
    op.drop_table("external_entity", schema="integrations")
    op.drop_table("cdc_cursor", schema="integrations")
    op.drop_index("ix_session_subject_active", table_name="session", schema="auth")
    op.drop_index("ix_session_expires", table_name="session", schema="auth")
    op.drop_table("session", schema="auth")
    op.drop_index(
        "uq_credential_subject_kind_active",
        table_name="credential",
        schema="auth",
    )
    op.drop_index("ix_credential_subject", table_name="credential", schema="auth")
    op.drop_index("ix_credential_status", table_name="credential", schema="auth")
    op.drop_table("credential", schema="auth")
    op.drop_index("ix_api_key_status", table_name="api_key", schema="auth")
    op.drop_index("ix_api_key_actor_id", table_name="api_key", schema="auth")
    op.drop_table("api_key", schema="auth")
    op.drop_index(
        "ix_actor_identifier_value",
        table_name="actor_identifier",
        schema="actor",
    )
    op.drop_index(
        op.f("ix_actor_actor_identifier_actor_id"),
        table_name="actor_identifier",
        schema="actor",
    )
    op.drop_table("actor_identifier", schema="actor")
    op.drop_index(
        "ix_integration_account_status",
        table_name="integration_account",
        schema="integrations",
    )
    op.drop_table("integration_account", schema="integrations")
    op.drop_index("ix_actor_type", table_name="actor", schema="actor")
    op.drop_index("ix_actor_status", table_name="actor", schema="actor")
    op.drop_index("ix_actor_role", table_name="actor", schema="actor")
    op.drop_index("ix_actor_person_uid", table_name="actor", schema="actor")
    op.drop_table("actor", schema="actor")
