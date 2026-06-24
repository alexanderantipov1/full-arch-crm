"""Ingest models: ``RawEvent``, ``NormalizedPersonHint``.

The principle: capture exactly what an external system sent us — verbatim —
BEFORE any parsing or domain mapping. This way we can replay if our parser
has a bug, and we have a forensic trail for compliance.

``NormalizedPersonHint`` (ENG-185) sits one step *after* capture: per provider
event we extract a small, provider-neutral, NON-PHI signal record (names,
normalised email/phone, source pointers, parser metadata) so the identity
match policy can run uniformly across Salesforce, CareStack, and any future
provider without each pipeline re-implementing reactivation matching. The
table is intentionally not surfaced to dashboards.

The ``tenant_id`` column (ENG-128) is supplied by :class:`TenantScopedMixin`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "ingest"


class RawEvent(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """One row per inbound event from an external system."""

    __tablename__ = "raw_event"
    # ENG-412 person-page perf indexes. Declared here so autogenerate does
    # NOT propose dropping them; the real DDL lives in the hand-written
    # migration (CREATE INDEX CONCURRENTLY in an autocommit block — not
    # expressible via op.create_index). The functional/GIN expressions below
    # MUST stay byte-identical to the query expressions in repository.py
    # (``payload->>'patientId'`` and ``regexp_replace(... ,'\D','','g')``)
    # or PostgreSQL will not pick the index.
    __table_args__ = (
        Index("ix_raw_event_tenant_id", "tenant_id"),
        Index("ix_raw_event_source", "source"),
        Index("ix_raw_event_received_at", "received_at"),
        Index("ix_raw_event_external_id", "external_id"),
        # Dedup "latest per external_id" aggregations → Index-Only Scan.
        Index(
            "ix_raw_event_dedup",
            "tenant_id",
            "source",
            "event_type",
            "external_id",
            "received_at",
        ),
        # payload->>'patientId' IN (...) filters (accounting, origin-context).
        Index(
            "ix_raw_event_patient_id",
            "tenant_id",
            "source",
            "event_type",
            text("(payload ->> 'patientId')"),
        ),
        # Household phone substring (ILIKE '%last7%') over digits-only phone.
        Index(
            "ix_raw_event_cs_patient_mobile_trgm",
            text("regexp_replace(payload ->> 'mobile', '\\D', '', 'g') gin_trgm_ops"),
            postgresql_using="gin",
            postgresql_where=text(
                "source = 'carestack' "
                "AND event_type = 'carestack.patient.upsert'"
            ),
        ),
        Index(
            "ix_raw_event_cs_patient_phone_trgm",
            text(
                "regexp_replace(payload ->> 'phoneWithExt', '\\D', '', 'g') "
                "gin_trgm_ops"
            ),
            postgresql_using="gin",
            postgresql_where=text(
                "source = 'carestack' "
                "AND event_type = 'carestack.patient.upsert'"
            ),
        ),
        Index(
            "ix_raw_event_cs_patient_workphone_trgm",
            text(
                "regexp_replace(payload ->> 'workPhoneWithExt', '\\D', '', 'g') "
                "gin_trgm_ops"
            ),
            postgresql_using="gin",
            postgresql_where=text(
                "source = 'carestack' "
                "AND event_type = 'carestack.patient.upsert'"
            ),
        ),
        # Household email branch (lower(email) = ...) — keeps the OR-filter
        # fully indexable alongside the phone trgm indexes.
        Index(
            "ix_raw_event_cs_patient_email_lower",
            text("lower(payload ->> 'email')"),
            postgresql_where=text(
                "source = 'carestack' "
                "AND event_type = 'carestack.patient.upsert'"
            ),
        ),
        {"schema": SCHEMA},
    )

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(256))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(1024))


class NormalizedPersonHint(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Provider-neutral, non-PHI person hint extracted from a raw event (ENG-185).

    One hint per raw event for this slice — the ``(tenant_id, raw_event_id)``
    unique constraint enforces it. Multi-person extraction from a single
    event lands in a follow-up if a provider needs it.

    The row carries ONLY parser/matching metadata: normalised name parts,
    normalised email/phone, source pointers, optional payload hash, and a
    deterministic ``hint_hash`` over the normalised matching features. The
    ``meta`` and ``quality_flags`` JSONB columns MUST NOT contain clinical
    text or verbatim provider payloads — the service-layer guard rejects a
    deny-list of PHI-looking keys before insert.

    ``person_uid`` and ``source_link_id`` are plain UUID columns. Identity
    is NOT imported in the ingest model layer; the identity service writes
    these pointers back later through ``IngestService`` rather than via a
    Python relationship. The DB-level FKs are omitted on purpose so that a
    hint row can outlive a soft-deleted identity row.
    """

    __tablename__ = "normalized_person_hint"
    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id",
            "raw_event_id",
            name="uq_normalized_person_hint_tenant_raw_event",
        ),
        Index("ix_normalized_person_hint_tenant_id", "tenant_id"),
        Index(
            "ix_normalized_person_hint_source",
            "tenant_id",
            "source_system",
            "source_instance",
            "source_kind",
            "source_id",
        ),
        Index(
            "ix_normalized_person_hint_email",
            "tenant_id",
            "email_normalized",
        ),
        Index(
            "ix_normalized_person_hint_phone",
            "tenant_id",
            "phone_normalized",
        ),
        Index(
            "ix_normalized_person_hint_person_uid",
            "tenant_id",
            "person_uid",
        ),
        {"schema": SCHEMA},
    )

    raw_event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.raw_event.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_system: Mapped[str] = mapped_column(String(32), nullable=False)
    source_instance: Mapped[str] = mapped_column(String(96), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(240))
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    given_name: Mapped[str | None] = mapped_column(String(120))
    family_name: Mapped[str | None] = mapped_column(String(120))
    display_name: Mapped[str | None] = mapped_column(String(240))
    email_normalized: Mapped[str | None] = mapped_column(String(320))
    phone_normalized: Mapped[str | None] = mapped_column(String(32))
    # Plain UUID pointer into ``identity.person``. ingest IS allowed to read
    # identity, but the column intentionally stays a bare UUID so the model
    # has no relationship-level dependency on identity; the service layer
    # writes the pointer after :class:`IdentityService` resolves the match.
    person_uid: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    # Plain UUID pointer into ``identity.source_link``. Same reasoning: the
    # link is created by identity after match acceptance.
    source_link_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    payload_sha256: Mapped[str | None] = mapped_column(String(64))
    hint_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    quality_flags: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )
    meta: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )


class SourceObjectField(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Schema registry for full-fidelity ingestion (ENG-426).

    One row per ``(tenant_id, provider, object_name, field_name)``. This is
    the durable answer to "what fields exist on this source object, and which
    are we capturing" — so a missing or newly-added field is knowable from our
    own store without re-interrogating the source system.

    Populated from a Salesforce ``describe`` (the readable field set) plus the
    Tooling-API field list (the FULL field set, regardless of Field-Level
    Security) for SF, and from the union of observed payload keys for REST
    sources such as CareStack. The ``readable`` flag distinguishes a field the
    integration user can actually read from one that exists on the object but
    is FLS-blocked (SF) — the diff between the two is the admin's remediation
    list.

    Rows are never deleted. A field that disappears from the source is marked
    ``active = False`` (history is preserved, the same way ``raw_event`` is
    immutable evidence). ``meta`` carries provider-specific flags (e.g. SF
    ``custom``, ``queryable``, ``compound``, ``fls_blocked``) without forcing a
    column per provider quirk.

    See ``.agents/strategy/FULL_FIDELITY_INGESTION_DOCTRINE.md`` and the ENG-425
    epic. The registry is tenant-scoped because the readable field set depends
    on the tenant's provider org and integration-user permissions.
    """

    __tablename__ = "source_object_field"
    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "object_name",
            "field_name",
            name="uq_source_object_field_tenant_provider_object_field",
        ),
        Index("ix_source_object_field_tenant_id", "tenant_id"),
        Index(
            "ix_source_object_field_object",
            "tenant_id",
            "provider",
            "object_name",
        ),
        {"schema": SCHEMA},
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    object_name: Mapped[str] = mapped_column(String(128), nullable=False)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[str | None] = mapped_column(String(64))
    # True when the integration user can actually read the field (SF: passes
    # Field-Level Security and is queryable; REST: observed in a payload). A
    # field present on the object but FLS-blocked is stored with readable=False
    # so the FLS-gap report can list it.
    readable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # False once a field stops appearing in the source schema. Rows are kept
    # for history rather than deleted.
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    meta: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )


class CareStackProvider(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """CareStack provider directory (ENG-308).

    Keyed by ``(tenant_id, provider_carestack_id)``. The person card
    resolves ``defaultProviderId`` from the CareStack patient payload
    against this table so the operator sees ``"Dr First Last"`` rather
    than a raw integer.

    The CareStack ``/api/v1.0/providers`` endpoint returns a flat
    unpaginated JSON array; the verbatim entry is preserved in
    ``payload`` so a future column extension does not need a re-pull.
    Provider data is NOT PHI — clinician name + type + active flag are
    operational metadata.
    """

    __tablename__ = "carestack_provider"
    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id",
            "provider_carestack_id",
            name="uq_carestack_provider_tenant_provider_id",
        ),
        Index("ix_carestack_provider_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    provider_carestack_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    middle_name: Mapped[str | None] = mapped_column(String(120))
    short_name: Mapped[str | None] = mapped_column(String(64))
    provider_type: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )
