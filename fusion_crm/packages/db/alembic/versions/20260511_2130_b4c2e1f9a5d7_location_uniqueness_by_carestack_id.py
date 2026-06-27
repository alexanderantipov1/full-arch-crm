"""ENG-124 fix: relax tenant.location uniqueness from (tenant_id, name) to
(tenant_id, carestack_location_id).

CareStack tenants legitimately ship multiple locations under the same
operator-facing brand name (e.g. two "Fusion Dental Implants" branches
at different addresses). The previous ``uq_location_tenant_id_name``
constraint blocked the second row from sync, causing
``POST /tenant/locations/sync-from-carestack`` to 500 on real data.

After this migration:

* ``uq_location_tenant_id_name`` is gone — name is a display field, not
  an identity field.
* A partial unique index ``uq_location_tenant_id_carestack_id`` on
  ``(tenant_id, (external_ref ->> 'carestack_location_id'))`` enforces
  idempotency for CareStack-driven rows (the only rows that carry
  that key).
* Manual operator-created locations (no ``carestack_location_id`` in
  ``external_ref``) are deduplicated at the service layer through
  ``LocationRepository.find_by_name`` — the partial-WHERE keeps those
  rows out of the unique scope.

Revision ID: b4c2e1f9a5d7
Revises: af5ba42a505b
Create Date: 2026-05-11 21:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c2e1f9a5d7"
down_revision: str | None = "af5ba42a505b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_location_tenant_id_name",
        "location",
        schema="tenant",
        type_="unique",
    )
    op.create_index(
        "uq_location_tenant_id_carestack_id",
        "location",
        ["tenant_id", sa.text("(external_ref ->> 'carestack_location_id')")],
        unique=True,
        schema="tenant",
        postgresql_where=sa.text("external_ref ? 'carestack_location_id'"),
    )


def downgrade() -> None:
    # If duplicate names are present in the table when downgrading,
    # this CREATE will fail — the operator must clean up first. We
    # do NOT silently drop rows.
    op.drop_index(
        "uq_location_tenant_id_carestack_id",
        table_name="location",
        schema="tenant",
        postgresql_where=sa.text("external_ref ? 'carestack_location_id'"),
    )
    op.create_unique_constraint(
        "uq_location_tenant_id_name",
        "location",
        ["tenant_id", "name"],
        schema="tenant",
    )
