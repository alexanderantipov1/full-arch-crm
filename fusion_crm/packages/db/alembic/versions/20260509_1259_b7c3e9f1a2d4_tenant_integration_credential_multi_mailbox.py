"""ENG-125 (1/2): multi-mailbox columns + provider expansion on
``tenant.integration_credential``.

Revision ID: b7c3e9f1a2d4
Revises: f4b2c8d9e6a7
Create Date: 2026-05-09 12:59:00.000000+00:00

Adds the columns required to support multiple Google / Microsoft mailboxes
per tenant + the expanded provider list (mirrors the Zod ProviderSchema
on the frontend):

- ``mailbox_email TEXT NULL`` — for ``google_workspace`` / ``microsoft_365``
  the resolved ``me@domain`` from the OAuth grant. Null otherwise.
- ``location_id UUID NULL`` — FK to ``tenant.location.id`` ON DELETE SET NULL.
  Pin a credential to a specific office; null = tenant-wide.
- ``is_default BOOLEAN NOT NULL DEFAULT false`` — partial unique
  ``(tenant_id, provider_kind) WHERE is_default = true``.
- ``tags JSONB NOT NULL DEFAULT '[]'::jsonb`` — operator-set labels;
  GIN-indexed for routing-rule lookup.

The CHECK on ``provider_kind`` is dropped + recreated to admit the
expanded set (``google_workspace``, ``microsoft_365``, ``vapi``, …).

Order matters: column adds come before the provider_kind CHECK swap so
existing rows do not transiently violate the new constraint.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7c3e9f1a2d4"
down_revision: str | None = "f4b2c8d9e6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Mirrors ``packages.tenant.models.PROVIDER_KINDS``. Self-contained per
# alembic discipline (revision files do not import each other).
PROVIDER_KINDS: tuple[str, ...] = (
    "salesforce",
    "hubspot",
    "carestack",
    "open_dental",
    "vapi",
    "twilio",
    "openai",
    "anthropic",
    "elevenlabs",
    "deepgram",
    "google_workspace",
    "microsoft_365",
    "birdeye",
    "podium",
    "google_business",
    "stripe",
    "square",
    "carecredit",
    "sunbit",
    "cherry",
    "google_analytics",
    "meta_pixel",
    "tiktok_pixel",
    "other",
)

# Original ENG-123 set, used by ``downgrade()`` to restore the tighter
# CHECK if this migration is ever rolled back. Tightening on downgrade
# requires the table to contain only rows in this set; the downgrade
# raises if violated, leaving the operator to clean up first.
LEGACY_PROVIDER_KINDS: tuple[str, ...] = (
    "salesforce",
    "hubspot",
    "carestack",
    "open_dental",
    "other",
)


def _check_clause(values: tuple[str, ...]) -> str:
    """Build ``provider_kind IN ('a', 'b', ...)`` for a CHECK constraint."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"provider_kind IN ({quoted})"


def upgrade() -> None:
    # 1. Add the four new columns -----------------------------------
    op.add_column(
        "integration_credential",
        sa.Column("mailbox_email", sa.String(length=320), nullable=True),
        schema="tenant",
    )
    op.add_column(
        "integration_credential",
        sa.Column("location_id", sa.UUID(), nullable=True),
        schema="tenant",
    )
    op.add_column(
        "integration_credential",
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        schema="tenant",
    )
    op.add_column(
        "integration_credential",
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        schema="tenant",
    )

    # 2. FK location_id → tenant.location(id) ON DELETE SET NULL ----
    op.create_foreign_key(
        op.f("fk_integration_credential_location_id_location"),
        "integration_credential",
        "location",
        ["location_id"],
        ["id"],
        source_schema="tenant",
        referent_schema="tenant",
        ondelete="SET NULL",
    )

    # 3. Indexes ----------------------------------------------------
    # Partial UNIQUE: at most one default per tenant+provider.
    op.create_index(
        "uq_integration_credential_default",
        "integration_credential",
        ["tenant_id", "provider_kind"],
        schema="tenant",
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )
    # Mailbox lookup (multi-mailbox isolation hot path).
    op.create_index(
        "ix_integration_credential_mailbox",
        "integration_credential",
        ["tenant_id", "provider_kind", "mailbox_email"],
        schema="tenant",
        postgresql_where=sa.text("mailbox_email IS NOT NULL"),
    )
    # Location-pinned lookup.
    op.create_index(
        "ix_integration_credential_location_id",
        "integration_credential",
        ["location_id"],
        schema="tenant",
        postgresql_where=sa.text("location_id IS NOT NULL"),
    )
    # Tag containment (GIN) for routing-rule queries.
    op.create_index(
        "ix_integration_credential_tags",
        "integration_credential",
        ["tags"],
        schema="tenant",
        postgresql_using="gin",
    )

    # 4. Expand the provider_kind CHECK -----------------------------
    # Drop the legacy CHECK first (added by ENG-123 1/4 with name
    # ``ck_integration_credential_provider_kind`` already pre-prefixed
    # via ``op.f()`` per the SQLAlchemy naming convention). Both
    # drop_constraint and create_check_constraint must also wrap their
    # names in ``op.f()`` so alembic does not re-apply the convention
    # and produce a doubled ``ck_<tbl>_ck_<tbl>_…`` literal that does
    # not match the stored constraint.
    op.drop_constraint(
        op.f("ck_integration_credential_provider_kind"),
        "integration_credential",
        schema="tenant",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_integration_credential_provider_kind"),
        "integration_credential",
        _check_clause(PROVIDER_KINDS),
        schema="tenant",
    )


def downgrade() -> None:
    # 1. Restore the legacy CHECK. If the table contains rows whose
    #    provider_kind is outside ``LEGACY_PROVIDER_KINDS`` this will
    #    fail — the operator must clean up first. We do NOT silently
    #    delete those rows: they are operator-configured credentials.
    op.drop_constraint(
        op.f("ck_integration_credential_provider_kind"),
        "integration_credential",
        schema="tenant",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_integration_credential_provider_kind"),
        "integration_credential",
        _check_clause(LEGACY_PROVIDER_KINDS),
        schema="tenant",
    )

    # 2. Indexes
    op.drop_index(
        "ix_integration_credential_tags",
        table_name="integration_credential",
        schema="tenant",
    )
    op.drop_index(
        "ix_integration_credential_location_id",
        table_name="integration_credential",
        schema="tenant",
    )
    op.drop_index(
        "ix_integration_credential_mailbox",
        table_name="integration_credential",
        schema="tenant",
    )
    op.drop_index(
        "uq_integration_credential_default",
        table_name="integration_credential",
        schema="tenant",
    )

    # 3. FK
    op.drop_constraint(
        op.f("fk_integration_credential_location_id_location"),
        "integration_credential",
        schema="tenant",
        type_="foreignkey",
    )

    # 4. Columns
    op.drop_column("integration_credential", "tags", schema="tenant")
    op.drop_column("integration_credential", "is_default", schema="tenant")
    op.drop_column("integration_credential", "location_id", schema="tenant")
    op.drop_column("integration_credential", "mailbox_email", schema="tenant")
