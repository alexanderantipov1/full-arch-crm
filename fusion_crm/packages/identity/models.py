"""Identity models: ``Person``, ``PersonIdentifier``, ``SourceLink``, ``MergeEvent``, ``MatchCandidate``.

A ``Person`` is the single global entity referenced by every other domain via
``person_uid`` (a UUID). ``PersonIdentifier`` records external aliases — phone
numbers, emails, CareStack IDs, Salesforce contact IDs — and is what powers
"resolve person by phone/email" lookups.

``SourceLink`` records the *origin* of a Person row (this person was first
seen in Salesforce as Lead X; later observed again as Lead Y). It is what
provider-pull workers (W1/W2) use to deduplicate across re-pulls.

``MergeEvent`` is an append-only history of person merges (when two rows are
collapsed into one). Reverse merges create new rows; nothing is rewritten.

``MatchCandidate`` is the explicit decision ledger for cross-provider identity
matching (ENG-182). Every auto-link, auto-merge, open ambiguity, rejection,
or supersedure is recorded here so the system can explain why two records
were treated as the same human (or kept apart). It replaces the previous
hidden email/phone reactivation logic baked into individual ingest pipelines.

NOTE: this domain stores NO clinical information.

Every per-tenant table inherits :class:`TenantScopedMixin` (ENG-128) so the
``tenant_id`` column declaration lives in one place. The transitional
``server_default`` from the ENG-123 4/4 migration is dropped by a follow-up
migration once every call site passes ``tenant_id`` explicitly.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import Base
from packages.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "identity"

# Allowed values for SourceLink.source_system / source_kind. Kept here so the
# CHECK constraint and any service-layer validation reference the same list.
SOURCE_SYSTEMS = ("salesforce", "carestack", "twilio", "vapi", "web_form", "manual", "import")
# "account" added by ENG-382: SF Account linked to a person via lead
# conversion (ConvertedAccountId), enabling the Opportunity -> Account
# -> person resolution path.
SOURCE_KINDS = (
    "lead",
    "contact",
    "patient",
    "caller",
    "sms_sender",
    "submitter",
    "account",
)
MERGE_REASONS = ("duplicate_email", "duplicate_phone", "manual", "cross_provider_match")
DEFAULT_SOURCE_INSTANCES: dict[str, str] = {
    "salesforce": "salesforce-main",
    "carestack": "carestack-main",
    "twilio": "twilio-main",
    "vapi": "vapi-main",
    "web_form": "web-form-main",
    "manual": "manual-main",
    "import": "import-main",
}


def default_source_instance(source_system: str) -> str:
    """Return the legacy single-instance slug for a source system."""
    return DEFAULT_SOURCE_INSTANCES.get(source_system, f"{source_system}-main")

# MatchCandidate enums (ENG-182). The Python tuples mirror the DB CHECK
# constraints created by the additive migration; change one, change the other.
MATCH_CANDIDATE_STATUSES = (
    "open",
    "auto_accepted",
    "accepted",
    "rejected",
    "superseded",
)
MATCH_CANDIDATE_ACCEPTED_STATUSES = ("auto_accepted", "accepted")

# Canonical taxonomy for ``MatchCandidate.match_rule`` (ENG-185).
# ``IdentityService.resolve_or_create_from_hint`` writes only these rules; the
# service-layer validator rejects anything else so the ledger stays queryable
# without free-form rule strings.
#
# * ``source_link`` — Tier 0, exact source-instance-scoped source-link
#   recapture. Reserved name; the entry point does NOT write a candidate for
#   this case (no decision was made), but the rule is listed so future audit
#   replays can recognise it.
# * ``email_phone_name`` — Tier 1 best case (email match + phone match +
#   compatible name).
# * ``phone_name`` — Tier 1 (phone match + compatible name).
# * ``email_name`` — Tier 1 (email match + compatible name, no phone
#   conflict).
# * ``email_only_ambiguous`` — Tier 2 open candidate; matched on email but
#   the policy cannot auto-accept (multiple candidates, name conflict, or
#   missing phone confirmation).
# * ``phone_only_ambiguous`` — Tier 2 open candidate; matched on phone but
#   the policy cannot auto-accept.
MATCH_RULES = (
    "source_link",
    "email_phone_name",
    "phone_name",
    "email_name",
    "email_only_ambiguous",
    "phone_only_ambiguous",
)

# ENG-555 (Layer D): the Tier-2 ambiguous rules mark "an incoming record reused
# a shared contact already held by an existing person" — the signal the
# shared-contact-reuse Messenger alert hooks onto. ``phone_only_ambiguous`` →
# phone reuse, ``email_only_ambiguous`` → email reuse.
REUSE_MATCH_RULES = (
    "phone_only_ambiguous",
    "email_only_ambiguous",
)


class Person(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Canonical person record. ``id`` is the global ``person_uid``.

    ENG-309: ``dob`` and ``ssn`` are demographic identity-strength signals
    consumed by :class:`packages.identity.service.IdentityService` as HARD
    VETOES in the resolver (different DOB or different SSN -> never merge,
    no matter how many soft signals overlap). They identify a human; they
    are not clinical attributes (clinical data lives in ``phi.*`` and goes
    through ``PhiService``). See ``packages/identity/CLAUDE.md`` for the
    policy carve-out. Logs / evidence dicts must NEVER carry these values
    -- the resolver reads them as top-level hint/person fields, not as
    evidence-dict entries (``_FORBIDDEN_EVIDENCE_KEYS`` still rejects them
    at the evidence layer).
    """

    __tablename__ = "person"
    __table_args__ = (
        Index("ix_person_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    given_name: Mapped[str | None] = mapped_column(String(120))
    family_name: Mapped[str | None] = mapped_column(String(120))
    display_name: Mapped[str | None] = mapped_column(String(240))
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    # SSN as digit-only normalised string; never log the value. 32-char ceiling
    # accommodates dash-stripped US SSN (9 chars) plus international tax-id
    # variants without forcing an explicit format.
    ssn: Mapped[str | None] = mapped_column(String(32), nullable=True)

    identifiers: Mapped[list[PersonIdentifier]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PersonIdentifier(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """External identifier that resolves to a ``Person``.

    ``kind`` examples: ``phone``, ``email``, ``carestack_patient_id``,
    ``salesforce_contact_id``. ``value`` is normalised (lowercase email,
    E.164 phone) by the service layer before insert.

    Uniqueness (ENG-341): ``(person_id, kind, value)`` is unique (per-person
    idempotency, all kinds). ``(kind, value)`` is globally unique ONLY for
    1:1 kinds — the partial index exempts the shared household contacts
    ``phone`` and ``email``, which multiple persons may share.
    """

    __tablename__ = "person_identifier"
    # ENG-341: phone/email are SHARED household contacts — multiple distinct
    # persons may legitimately hold the same value (spouse, children share one
    # phone). True 1:1 keys (carestack_patient_id, salesforce_contact_id, and
    # any future ssn / CareStack accountId / portal kind) stay globally unique.
    # The old blanket ``uq_person_identifier_kind_value`` is replaced by two
    # guards:
    #   (a) per-person idempotency for ALL kinds — no duplicate identical
    #       ``(person_id, kind, value)`` rows on ONE person, while allowing the
    #       same value across DIFFERENT persons;
    #   (b) a PARTIAL unique index that keeps the global 1:1 guarantee for every
    #       kind EXCEPT the shared contacts (``phone``/``email``). A denylist —
    #       not an allowlist — so a new identifier kind defaults to unique 1:1
    #       with no DDL, matching the "just use a new kind string" convention.
    # The shared denylist mirrors ``service._SHARED_CONTACT_KINDS``; keep both in
    # sync if the shared set ever grows.
    __table_args__ = (
        UniqueConstraint(
            "person_id",
            "kind",
            "value",
            name="uq_person_identifier_person_kind_value",
        ),
        Index(
            "uq_person_identifier_unique_kind_value",
            "kind",
            "value",
            unique=True,
            postgresql_where=sa.text("kind NOT IN ('phone', 'email')"),
        ),
        Index("ix_person_identifier_tenant_id", "tenant_id"),
        Index("ix_person_identifier_value", "value"),
        Index("ix_person_identifier_kind_match_key", "kind", "value_match_key"),
        {"schema": SCHEMA},
    )

    person_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.person.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(320), nullable=False)
    # Canonical comparison key (E.164 phone / lower-cased email / verbatim id),
    # set on write by the repository choke point and backfilled for legacy rows.
    # Matching compares on THIS, not the raw ``value``, so the same number stored
    # in different formats (``2015550123`` vs ``+12015550123``) resolves to one
    # person. Nullable while the backfill runs; the read path keeps a raw-value
    # fallback so there is no correctness gap. See identity-phone-format-dedup.
    value_match_key: Mapped[str | None] = mapped_column(String(320), nullable=True)

    person: Mapped[Person] = relationship(back_populates="identifiers")


class SourceLink(UUIDPrimaryKeyMixin, TenantScopedMixin, Base):
    """External-system origin of a Person.

    Distinct from ``PersonIdentifier``: identifiers are aliases for resolution
    (find a Person by phone or email); source links record provenance (which
    external system first introduced this Person and under what record id).

    ``(tenant_id, source_system, source_instance, source_kind, source_id)`` is
    unique when ``source_id`` is set. A single Person can have multiple source
    links — e.g. a person seen first as a Salesforce Lead, then later linked
    to a CareStack Patient.
    """

    __tablename__ = "source_link"
    __table_args__ = (
        sa.CheckConstraint(
            "source_system IN ('salesforce', 'carestack', 'twilio', 'vapi', "
            "'web_form', 'manual', 'import')",
            name="source_system",
        ),
        sa.CheckConstraint(
            "source_kind IN ('lead', 'contact', 'patient', 'caller', "
            "'sms_sender', 'submitter', 'account')",
            name="source_kind",
        ),
        Index("ix_source_link_person_uid", "person_uid"),
        Index("ix_source_link_tenant_id", "tenant_id"),
        Index("ix_source_link_source", "source_system", "source_instance", "source_kind"),
        Index(
            "uq_source_link_external",
            "tenant_id",
            "source_system",
            "source_instance",
            "source_kind",
            "source_id",
            unique=True,
            postgresql_where=sa.text("source_id IS NOT NULL"),
        ),
        {"schema": SCHEMA},
    )

    person_uid: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.person.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_system: Mapped[str] = mapped_column(String(32), nullable=False)
    source_instance: Mapped[str] = mapped_column(String(96), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(240))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    meta: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )


class MergeEvent(UUIDPrimaryKeyMixin, TenantScopedMixin, Base):
    """Append-only record of a Person merge.

    When two ``Person`` rows are collapsed (e.g. duplicate email surfaced
    across providers and a human or rule decided they are the same human),
    this row records which one survived and which was retired. The retired
    row is NOT deleted — references to ``person_uid`` remain stable.

    Reverse merges create new rows (the previous ``surviving_person_uid``
    becomes the new ``merged_person_uid``). Nothing here is ever updated.
    """

    __tablename__ = "merge_event"
    __table_args__ = (
        sa.CheckConstraint(
            "reason IN ('duplicate_email', 'duplicate_phone', 'manual', "
            "'cross_provider_match')",
            name="reason",
        ),
        sa.CheckConstraint(
            "surviving_person_uid <> merged_person_uid",
            name="distinct_persons",
        ),
        Index("ix_merge_event_tenant_id", "tenant_id"),
        Index("ix_merge_event_surviving", "surviving_person_uid"),
        Index("ix_merge_event_merged", "merged_person_uid"),
        {"schema": SCHEMA},
    )

    surviving_person_uid: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.person.id", ondelete="RESTRICT"),
        nullable=False,
    )
    merged_person_uid: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(48), nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )
    performed_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("actor.actor.id", ondelete="RESTRICT"),
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MatchCandidate(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Explicit decision ledger for cross-provider identity matching (ENG-182).

    One row per matching decision: a hint matched against an existing person,
    or two existing persons proposed as the same human. ``status`` records
    the outcome (``open`` = pending, ``auto_accepted`` / ``accepted`` =
    linked/merged, ``rejected`` = proven wrong, ``superseded`` = replaced by
    a stronger candidate).

    ``hint_id`` is a plain UUID pointer into ``ingest.normalized_person_hint``;
    ``identity`` does NOT import ``ingest``, so the reference is column-only.
    Similarly ``merge_event_id`` is a plain pointer rather than a Python FK
    relationship to keep the model self-contained.

    Tenant-scoped uniqueness:

    * Partial unique on ``(tenant_id, person_pair_key)`` while
      ``status='open' AND person_pair_key IS NOT NULL`` prevents duplicate
      open candidates for the same person pair.
    * Partial unique on ``(tenant_id, hint_id, candidate_person_uid)`` while
      ``status IN ('open', 'auto_accepted', 'accepted') AND hint_id IS NOT NULL``
      prevents the same hint from being linked twice to the same candidate.

    Service-layer rules (see :mod:`packages.identity.service`):

    * ``confidence`` is in ``[0.0, 1.0]`` (also enforced by CHECK).
    * ``source_person_uid`` and ``candidate_person_uid`` must differ when
      both are set (also enforced by CHECK).
    * ``accepted_person_uid`` is populated ONLY for ``auto_accepted`` /
      ``accepted`` statuses (also enforced by CHECK).
    * ``evidence`` and ``conflicts`` carry NO clinical text and NO raw
      provider payloads — only normalized signals (e.g. ``"email_match"``,
      ``"phone_match"``, name compatibility flags).
    """

    __tablename__ = "match_candidate"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('open', 'auto_accepted', 'accepted', 'rejected', 'superseded')",
            name="status",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="confidence_range",
        ),
        sa.CheckConstraint(
            "source_person_uid IS NULL "
            "OR source_person_uid <> candidate_person_uid",
            name="distinct_persons",
        ),
        sa.CheckConstraint(
            "accepted_person_uid IS NULL "
            "OR status IN ('auto_accepted', 'accepted')",
            name="accepted_status",
        ),
        Index("ix_match_candidate_tenant_id", "tenant_id"),
        Index("ix_match_candidate_candidate", "tenant_id", "candidate_person_uid"),
        Index("ix_match_candidate_source_person", "tenant_id", "source_person_uid"),
        Index("ix_match_candidate_hint", "tenant_id", "hint_id"),
        Index("ix_match_candidate_status", "tenant_id", "status", "created_at"),
        Index(
            "uq_match_candidate_open_pair",
            "tenant_id",
            "person_pair_key",
            unique=True,
            postgresql_where=sa.text(
                "status = 'open' AND person_pair_key IS NOT NULL"
            ),
        ),
        Index(
            "uq_match_candidate_hint_candidate_active",
            "tenant_id",
            "hint_id",
            "candidate_person_uid",
            unique=True,
            postgresql_where=sa.text(
                "status IN ('open', 'auto_accepted', 'accepted') "
                "AND hint_id IS NOT NULL"
            ),
        ),
        {"schema": SCHEMA},
    )

    # Plain UUID pointer into ``ingest.normalized_person_hint``. Identity does
    # not import ingest in Python (see cross-package import matrix), so this
    # stays as a bare column rather than a ForeignKey relationship. The DB
    # constraint is intentionally omitted in the migration to keep matching
    # decisions independently writeable when a hint row is purged.
    hint_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    source_person_uid: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.person.id", ondelete="RESTRICT"),
        nullable=True,
    )
    candidate_person_uid: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.person.id", ondelete="RESTRICT"),
        nullable=False,
    )
    accepted_person_uid: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.person.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # Plain pointer to identity.merge_event.id. Set after a merge actually
    # executes; kept as a column-only reference (no SQLAlchemy relationship)
    # so service code is explicit about when it inserts the merge row.
    merge_event_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.merge_event.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    match_rule: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )
    conflicts: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )
    # ``person_pair_key`` is the sorted-UUID pair key when both persons are
    # known. Two UUIDs are 36 chars each plus a separator = 73. Computed by
    # the service before insert; the column stays plain string so the partial
    # unique index can index it directly without a computed column dependency.
    person_pair_key: Mapped[str | None] = mapped_column(String(73))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("actor.actor.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Self-reference: an open candidate later replaced by a stronger one
    # points back to its replacement. ondelete=SET NULL so deleting a
    # replacement does not retroactively reopen the old row.
    superseded_by_match_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.match_candidate.id", ondelete="SET NULL"),
        nullable=True,
    )


def make_person_pair_key(
    person_a: uuid.UUID | None, person_b: uuid.UUID | None
) -> str | None:
    """Return the sorted ``"<uuid>:<uuid>"`` pair key, or ``None``.

    Only meaningful when both persons exist (i.e. an existing-person pair
    candidate); incoming-hint-only candidates return ``None``. Ordering is
    stable across call order so ``(a, b)`` and ``(b, a)`` produce the same
    key and the partial unique constraint catches duplicates.
    """
    if person_a is None or person_b is None:
        return None
    a, b = sorted((str(person_a), str(person_b)))
    return f"{a}:{b}"
