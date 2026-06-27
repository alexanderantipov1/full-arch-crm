"""ENG-440 (Block G): add integrations.agent_action_proposal (agent HITL store).

Revision ID: b69bce1e2195
Revises: 37f5ec4af909
Create Date: 2026-06-15 07:00:00.000000+00:00

Additive only — creates ``integrations.agent_action_proposal``, the durable
store for an agent-proposed action awaiting a human Approve/Reject in chat
(Block G). The chat-side ``AgentActionService`` persists a pending proposal and
posts an interactive card; the human click flows back through the signed
inbound path (Block E) and the worker boundary resolves the decision and, on
approve, executes the bound action (the only executable kind here is an
``enrichment`` annotation).

Constraints/indexes mirror
:class:`packages.integrations.models.AgentActionProposal`:

* ``UniqueConstraint (tenant_id, proposal_ref)`` — the opaque ref placed in
  the button context is unique per tenant so an inbound click matches exactly
  one row.
* ``CHECK status IN ('pending','approved','rejected','executed','failed')`` —
  the proposal lifecycle.
* ``ix_agent_action_proposal_tenant_id`` — tenant-wide scans.

``decided_by_actor_id`` is a DB-level FK to ``actor.actor.id``
(``ON DELETE SET NULL``); ``tenant_id`` FKs ``tenant.tenant.id`` via the mixin.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b69bce1e2195"
down_revision: str | None = "37f5ec4af909"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_action_proposal",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("proposal_ref", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("provider_message_id", sa.String(length=64), nullable=True),
        sa.Column("decided_by_actor_id", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
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
            "status IN ('pending', 'approved', 'rejected', 'executed', 'failed')",
            name=op.f("ck_agent_action_proposal_status"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_agent_action_proposal_decided_by_actor_id_actor"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_agent_action_proposal_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_action_proposal")),
        # NOTE: the UQ name is hand-written rather than wrapped in op.f(). This
        # is intentional and left as-is — the naming convention does not
        # require op.f() for UQ, and editing this already-applied upgrade()
        # would drift the dev DB. (Codex NIT, deliberately skipped.)
        sa.UniqueConstraint(
            "tenant_id",
            "proposal_ref",
            name="uq_agent_action_proposal_tenant_ref",
        ),
        schema="integrations",
    )
    op.create_index(
        "ix_agent_action_proposal_tenant_id",
        "agent_action_proposal",
        ["tenant_id"],
        schema="integrations",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_action_proposal_tenant_id",
        table_name="agent_action_proposal",
        schema="integrations",
    )
    op.drop_table("agent_action_proposal", schema="integrations")
