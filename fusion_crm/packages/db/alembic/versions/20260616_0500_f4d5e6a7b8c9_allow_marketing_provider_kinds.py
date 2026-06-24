"""Allow marketing/SEO provider_kinds on tenant.integration_credential.

ENG-489 (epic ENG-488) adds per-tenant credentials for the marketing /
SEO ad platforms. Their credential payloads live in
``tenant.integration_credential`` under
``provider_kind in ('google_ads', 'meta_ads', 'google_search_console')``
(``credential_kind = 'api_key'``), so the CHECK constraint on
``provider_kind`` must admit the three new values.
``google_analytics`` already existed (ENG-125) and is left unchanged.

This migration drops and recreates the named CHECK constraint
``ck_integration_credential_provider_kind`` with the full provider list
plus the three marketing values. ``downgrade()`` restores the prior
(ENG-435 / mattermost) set; it raises via the DB if any row already uses
one of the new values — clean those up before rolling back.

The constraint NAME is unchanged across this migration (created in the
tenant-domain migration, last rewritten by the mattermost migration
4fe9f2b9f55a); only the value list changes. Additive only — no data
change, existing rows unaffected.

``down_revision`` is the current head ``f1a2b3c4d5e6`` (the Full Funnel v2
consultation source/status migration, ENG-481). Re-pointed from the
marketing GSC migration ``e3c4d5f6a7b8`` when ENG-481 merged ahead of this
branch, to keep a single linear Alembic head. This migration is additive
(a CHECK-constraint rewrite) and order-independent w.r.t. the funnel
migration, so re-parenting is safe.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f4d5e6a7b8c9"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "ck_integration_credential_provider_kind"

# The provider set BEFORE this migration — the ENG-435 list (ENG-125 set
# plus 'mattermost'). Self-contained per alembic discipline (revisions do
# not import each other or the live model).
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
    "mattermost",
    "other",
)

# After this migration: the prior set plus the marketing / SEO platforms.
# Inserted before the 'other' catch-all to mirror the live model ordering.
NEW_PROVIDER_KINDS: tuple[str, ...] = (
    *PRIOR_PROVIDER_KINDS[:-1],
    "google_ads",
    "meta_ads",
    "google_search_console",
    "other",
)


def _check_clause(values: tuple[str, ...]) -> str:
    """Build ``provider_kind IN ('a', 'b', ...)`` for a CHECK constraint."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"provider_kind IN ({quoted})"


def upgrade() -> None:
    # ``op.f`` marks the name as already-final so the metadata naming
    # convention does not re-prefix it (the constraint was created with
    # this literal name in the tenant-domain migration). The prior
    # mattermost migration uses the same op.f wrapping.
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
