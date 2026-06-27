"""Allow 'mattermost' provider_kind on tenant.integration_credential.

ENG-435 (Block B) adds the Mattermost chat adapter. Mattermost bot
credentials live in ``tenant.integration_credential`` under
``provider_kind = 'mattermost'`` (``credential_kind = 'api_key'``), so
the CHECK constraint on ``provider_kind`` must admit the new value.

This migration drops and recreates the named CHECK constraint
``ck_integration_credential_provider_kind`` with the full provider list
plus ``mattermost``. ``downgrade()`` restores the prior (ENG-125) set;
it raises via the DB if any row already uses ``mattermost`` — clean
those up before rolling back.

The constraint NAME is unchanged across this migration (it was created
in the tenant-domain migration and last rewritten by the multi-mailbox
migration b7c3e9f1a2d4); only the value list changes.

Revision id chosen as a fresh 12-hex; ``down_revision`` is the current
head ``a7b8c9d0e1f2`` (the notification outbox/rule migration).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "4fe9f2b9f55a"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "ck_integration_credential_provider_kind"

# The provider set BEFORE this migration — mirrors the multi-mailbox
# migration (b7c3e9f1a2d4) which expanded the ENG-123 set to the ENG-125
# list. Self-contained per alembic discipline (revisions do not import
# each other or the live model).
PRIOR_PROVIDER_KINDS: tuple[str, ...] = (
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

# After this migration: the prior set plus the corporate-chat provider.
NEW_PROVIDER_KINDS: tuple[str, ...] = (*PRIOR_PROVIDER_KINDS, "mattermost")


def _check_clause(values: tuple[str, ...]) -> str:
    """Build ``provider_kind IN ('a', 'b', ...)`` for a CHECK constraint."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"provider_kind IN ({quoted})"


def upgrade() -> None:
    # ``op.f`` marks the name as already-final so the metadata naming
    # convention does not re-prefix it (the constraint was created with
    # this literal name in the tenant-domain migration). The prior
    # multi-mailbox migration uses the same op.f wrapping.
    op.drop_constraint(
        op.f(CONSTRAINT_NAME),
        "integration_credential",
        schema="tenant",
        type_="check",
    )
    op.create_check_constraint(
        op.f(CONSTRAINT_NAME),
        "integration_credential",
        _check_clause(NEW_PROVIDER_KINDS),
        schema="tenant",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f(CONSTRAINT_NAME),
        "integration_credential",
        schema="tenant",
        type_="check",
    )
    op.create_check_constraint(
        op.f(CONSTRAINT_NAME),
        "integration_credential",
        _check_clause(PRIOR_PROVIDER_KINDS),
        schema="tenant",
    )
