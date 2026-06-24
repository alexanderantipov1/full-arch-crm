"""Smoke tests for ``interaction.event`` model — D1 / ENG-2.

DB-level tests (CHECK enforcement, partial UNIQUE collision behaviour)
land alongside the alembic migration when a Postgres test container is
wired in.
"""

from __future__ import annotations

from sqlalchemy import Index, Table

from packages.interaction.models import (
    EVENT_KINDS,
    SCHEMA,
    SOURCE_PROVIDERS,
    Event,
)

_EVENT_TBL: Table = Event.__table__  # type: ignore[assignment]


def test_event_table_metadata() -> None:
    assert Event.__tablename__ == "event"
    assert _EVENT_TBL.schema == SCHEMA

    cols = {c.name for c in _EVENT_TBL.columns}
    expected = {
        "id",
        "tenant_id",
        "person_uid",
        "kind",
        "source_provider",
        "source_event_id",
        "data_class",
        "source_kind",
        "source_external_id",
        "projection_ref_type",
        "projection_ref_id",
        "review_status",
        "occurred_at",
        "summary",
        "payload",
        "created_at",
        "created_by_actor_id",
    }
    assert expected == cols, f"unexpected columns: {cols ^ expected}"


def test_event_check_constraints_present() -> None:
    check_names = {
        c.name
        for c in _EVENT_TBL.constraints
        if isinstance(c.name, str) and c.name.startswith("ck_")
    }
    assert "ck_event_kind" in check_names
    assert "ck_event_source_provider" in check_names
    assert "ck_event_data_class" in check_names
    assert "ck_event_source_kind" in check_names
    assert "ck_event_projection_ref_type" in check_names
    assert "ck_event_review_status" in check_names


def test_event_partial_unique_index() -> None:
    """Partial UNIQUE on (source_provider, source_event_id) WHERE source_event_id IS NOT NULL."""
    indexes: dict[str, Index] = {
        str(idx.name): idx for idx in _EVENT_TBL.indexes if idx.name is not None
    }
    assert "uq_event_source" in indexes
    uq = indexes["uq_event_source"]
    assert uq.unique is True
    assert uq.dialect_options["postgresql"].get("where") is not None
    cols = [c.name for c in uq.columns]
    assert cols == ["source_provider", "source_event_id"]


def test_event_provider_source_kind_partial_unique_index() -> None:
    """ENG-269: cross-pull dedup partial UNIQUE on
    ``(tenant_id, source_provider, source_kind, source_external_id, kind)``
    ``WHERE source_external_id IS NOT NULL``.

    This is the constraint that makes ``InteractionService.create_event``
    idempotent across pulls: a re-pull that would re-insert the same
    provider-object-kind row hits ON CONFLICT DO NOTHING and becomes a
    no-op instead of duplicating the timeline.
    """
    indexes: dict[str, Index] = {
        str(idx.name): idx for idx in _EVENT_TBL.indexes if idx.name is not None
    }
    assert "uq_event_provider_source_kind" in indexes
    uq = indexes["uq_event_provider_source_kind"]
    assert uq.unique is True
    # Must be a partial index — postgres treats NULL source_external_id as
    # "no provider object id" (manual/system rows) and must not collide.
    assert uq.dialect_options["postgresql"].get("where") is not None
    cols = [c.name for c in uq.columns]
    assert cols == [
        "tenant_id",
        "source_provider",
        "source_kind",
        "source_external_id",
        "kind",
    ]


def test_event_timeline_index_present() -> None:
    """The (person_uid, occurred_at) index powers the timeline query."""
    index_names = {idx.name for idx in _EVENT_TBL.indexes}
    assert "ix_event_person_occurred" in index_names

    # Verify column ordering
    timeline_idx = next(idx for idx in _EVENT_TBL.indexes if idx.name == "ix_event_person_occurred")
    assert [c.name for c in timeline_idx.columns] == ["person_uid", "occurred_at"]


def test_event_is_append_only_no_updated_at() -> None:
    """Event is append-only — created_at present, updated_at absent.

    The model deliberately does NOT use TimestampMixin (which would add
    both created_at and updated_at). Mutating an event row is a contract
    violation; if a kind needs to change, a new event supersedes the old.
    """
    cols = {c.name for c in _EVENT_TBL.columns}
    assert "created_at" in cols
    assert "updated_at" not in cols


def test_event_kinds_canonical() -> None:
    """The EVENT_KINDS tuple must contain the Phase 1 verbs.

    These are the verbs CHECK-constrained in the migration. Adding a
    value here without updating the migration's CHECK lets a row past
    the Python validator that the DB will reject.
    """
    assert EVENT_KINDS == (
        "lead_created",
        "lead_updated",
        "consultation_scheduled",
        "consultation_created",
        "consultation_rescheduled",
        "consultation_cancelled",
        "consultation_completed",
        "consultation_no_show",
        "task_created",
        "task_completed",
        "call_logged",
        "call_reference_found",
        "treatment_proposed",
        "treatment_completed",
        "invoice_created",
        "case_opened",
        "case_closed",
        "opportunity_created",
        "opportunity_won",
        "opportunity_lost",
        "opportunity_stage_changed",
        "contact_created",
        "payment_recorded",
        "payment_refunded",
        "payment_reversed",
        "payment_applied",
        "treatment_accepted",
        "surgery_scheduled",
        "surgery_completed",
    )


def test_source_providers_canonical() -> None:
    assert SOURCE_PROVIDERS == ("salesforce", "carestack")


def test_event_carries_tenant_id_column() -> None:
    """Every per-tenant table inherits TenantScopedMixin (ENG-128)."""
    cols = {c.name for c in _EVENT_TBL.columns}
    assert "tenant_id" in cols
