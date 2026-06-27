"""ENG-341: phone/email become shared household contacts on person_identifier

Layer A of the household-identity-grouping epic (ENG-552). A phone number or
email is a SHARED household contact — spouse and children legitimately share one
phone — not a globally-unique identity key. True 1:1 keys
(``carestack_patient_id``, ``salesforce_contact_id``, and any future ssn /
CareStack accountId / portal kind held as a ``person_identifier``) stay globally
unique.

This replaces the blanket ``uq_person_identifier_kind_value`` constraint with
two guards:

* ``uq_person_identifier_person_kind_value`` — UNIQUE ``(person_id, kind,
  value)``: per-person idempotency for ALL kinds (no duplicate identical rows on
  one person), while allowing the same value across DIFFERENT persons.
* ``uq_person_identifier_unique_kind_value`` — PARTIAL UNIQUE INDEX on
  ``(kind, value)`` WHERE ``kind NOT IN ('phone', 'email')``: keeps the global
  1:1 guarantee for every kind except the shared contacts.

The non-unique ``ix_person_identifier_value`` lookup index is left in place.

Safety: ``upgrade()`` PRE-CHECKS the existing data and FAILS LOUDLY (with counts
only — never the offending kind / value / person_id, which may be PHI/PII)
before any DDL, so a prod run aborts cleanly instead of a partial migration on a
silent ``CREATE UNIQUE INDEX`` failure. If a check fires, dedup first (see
ENG-541 / ``infra/scripts/merge_phone_duplicate_persons.py``) and re-run.

Downgrade recreates the old blanket constraint. NOTE: this is
irreversible-in-practice once shared phone/email duplicates exist — recreating
``uq_person_identifier_kind_value`` will fail on those rows. That is expected;
a genuine rollback after shared data has been written requires manual dedup
first.

Revision ID: e9a1c7b4d2f3
Revises: 5c46df9990df
Create Date: 2026-06-21 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9a1c7b4d2f3"
down_revision: str | Sequence[str] | None = "5c46df9990df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "identity"
_TABLE = "person_identifier"

_OLD_CONSTRAINT = "uq_person_identifier_kind_value"
_PERSON_GUARD = "uq_person_identifier_person_kind_value"
_UNIQUE_KIND_INDEX = "uq_person_identifier_unique_kind_value"

# Shared household-contact kinds, exempt from the global 1:1 guarantee. MUST
# stay in sync with ``packages.identity.service._SHARED_CONTACT_KINDS`` and the
# model's partial-index ``postgresql_where``.
_SHARED_KINDS = ("phone", "email")

# Count duplicate (kind, value) among UNIQUE (non-shared) kinds — these would
# violate the new partial unique index.
_DUP_UNIQUE_KIND_SQL = sa.text(
    f"""
    SELECT COALESCE(SUM(c.dup_rows), 0) AS total_rows,
           COUNT(*) AS dup_groups
    FROM (
        SELECT COUNT(*) AS dup_rows
        FROM {SCHEMA}.{_TABLE}
        WHERE kind NOT IN ('phone', 'email')
        GROUP BY kind, value
        HAVING COUNT(*) > 1
    ) AS c
    """
)

# Count duplicate (person_id, kind, value) — these would violate the new
# per-person idempotency constraint.
_DUP_PERSON_KIND_SQL = sa.text(
    f"""
    SELECT COALESCE(SUM(c.dup_rows), 0) AS total_rows,
           COUNT(*) AS dup_groups
    FROM (
        SELECT COUNT(*) AS dup_rows
        FROM {SCHEMA}.{_TABLE}
        GROUP BY person_id, kind, value
        HAVING COUNT(*) > 1
    ) AS c
    """
)


def precheck_for_shared_contact_guards(bind: sa.engine.Connection) -> None:
    """Raise ``RuntimeError`` if existing data would violate the new guards.

    Exposed as a module-level function so the migration test can exercise the
    pre-check against seeded violating data without re-running the full DDL.
    Emits COUNTS ONLY — never the offending kind / value / person_id, which may
    be PHI/PII.
    """
    unique_dup = bind.execute(_DUP_UNIQUE_KIND_SQL).one()
    person_dup = bind.execute(_DUP_PERSON_KIND_SQL).one()

    unique_dup_groups = int(unique_dup.dup_groups)
    person_dup_groups = int(person_dup.dup_groups)

    if unique_dup_groups or person_dup_groups:
        raise RuntimeError(
            "ENG-341 migration aborted: identity.person_identifier contains "
            "duplicates that violate the new uniqueness guards. "
            f"unique-kind (kind,value) duplicate groups={unique_dup_groups} "
            f"(rows={int(unique_dup.total_rows)}); "
            f"(person_id,kind,value) duplicate groups={person_dup_groups} "
            f"(rows={int(person_dup.total_rows)}). "
            "Dedup first (see ENG-541 / "
            "infra/scripts/merge_phone_duplicate_persons.py) and re-run. "
            "No values are logged because they may be PHI/PII."
        )


def upgrade() -> None:
    bind = op.get_bind()
    # PRE-CHECK before any DDL so a violating prod DB aborts cleanly.
    precheck_for_shared_contact_guards(bind)

    op.drop_constraint(
        _OLD_CONSTRAINT, _TABLE, schema=SCHEMA, type_="unique"
    )
    op.create_unique_constraint(
        _PERSON_GUARD,
        _TABLE,
        ["person_id", "kind", "value"],
        schema=SCHEMA,
    )
    op.create_index(
        _UNIQUE_KIND_INDEX,
        _TABLE,
        ["kind", "value"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("kind NOT IN ('phone', 'email')"),
    )


def downgrade() -> None:
    # NOTE: irreversible-in-practice once shared phone/email duplicates exist —
    # recreating the blanket unique constraint below will fail on those rows.
    # That is expected; a real rollback after shared data has been written
    # requires manual dedup first.
    op.drop_index(_UNIQUE_KIND_INDEX, table_name=_TABLE, schema=SCHEMA)
    op.drop_constraint(_PERSON_GUARD, _TABLE, schema=SCHEMA, type_="unique")
    op.create_unique_constraint(
        _OLD_CONSTRAINT,
        _TABLE,
        ["kind", "value"],
        schema=SCHEMA,
    )
