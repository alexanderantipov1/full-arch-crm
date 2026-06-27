"""Pydantic schemas for the identity domain (DTOs crossing service boundaries)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import default_source_instance


class PersonIdentifierIn(BaseModel):
    kind: str = Field(..., examples=["phone", "email"])
    value: str = Field(..., min_length=1, max_length=320)


class PersonIdentifierOut(PersonIdentifierIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class PersonIn(BaseModel):
    given_name: str | None = None
    family_name: str | None = None
    display_name: str | None = None
    # ENG-309: dob and ssn are identity-strength demographic signals used by
    # the resolver as HARD VETOES (different DOB / SSN -> never merge). They
    # are NOT clinical data; the identity package owns demographic identity,
    # while phi/* owns clinical attributes. They are seeded on new persons
    # and conservatively backfilled on existing persons (never overwriting a
    # non-null existing value). See packages/identity/CLAUDE.md.
    dob: date | None = None
    ssn: str | None = Field(default=None, max_length=32)
    identifiers: list[PersonIdentifierIn] = Field(default_factory=list)


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    given_name: str | None
    family_name: str | None
    display_name: str | None
    created_at: datetime
    updated_at: datetime
    identifiers: list[PersonIdentifierOut] = Field(default_factory=list)


class ResolveQuery(BaseModel):
    """Look up an existing person by one of their external identifiers."""

    phone: str | None = None
    email: str | None = None


class MatchCandidateIn(BaseModel):
    """Input DTO for :meth:`IdentityService.add_match_candidate` (ENG-182).

    ``evidence`` and ``conflicts`` are JSON-friendly dicts; service-layer
    validation rejects clinical-looking keys or raw provider payloads.
    """

    hint_id: UUID | None = None
    source_person_uid: UUID | None = None
    candidate_person_uid: UUID
    accepted_person_uid: UUID | None = None
    status: str = Field(..., examples=["open", "auto_accepted"])
    match_rule: str = Field(..., min_length=1, max_length=64)
    confidence: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    evidence: dict[str, object] = Field(default_factory=dict)
    conflicts: dict[str, object] = Field(default_factory=dict)
    decided_by_actor_id: UUID | None = None


class MatchCandidateOut(BaseModel):
    """Output DTO mirroring the ORM row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hint_id: UUID | None
    source_person_uid: UUID | None
    candidate_person_uid: UUID
    accepted_person_uid: UUID | None
    merge_event_id: UUID | None
    status: str
    match_rule: str
    confidence: Decimal
    evidence: dict[str, object]
    conflicts: dict[str, object]
    person_pair_key: str | None
    decided_at: datetime | None
    decided_by_actor_id: UUID | None
    superseded_by_match_id: UUID | None
    created_at: datetime
    updated_at: datetime


class SourceLinkSummaryOut(BaseModel):
    """Minimal source-link projection for cross-domain read models."""

    id: UUID
    person_uid: UUID
    source_system: str
    source_instance: str
    source_kind: str
    source_id: str | None
    first_seen_at: datetime
    last_seen_at: datetime


class SourceLinkageExampleOut(BaseModel):
    """Masked source-linkage example for Data Intelligence tooling."""

    person_uid_masked: str
    linkage_status: str
    source_systems: list[str]
    salesforce_source_id_masked: str | None = None
    carestack_source_id_masked: str | None = None


class SourceLinkageCoverageOut(BaseModel):
    """Aggregate source-linkage coverage for Salesforce and CareStack."""

    total_persons: int
    salesforce_person_count: int
    carestack_person_count: int
    linked_salesforce_carestack_count: int
    salesforce_only_count: int
    carestack_only_count: int
    salesforce_to_carestack_rate: float | None
    carestack_to_salesforce_rate: float | None
    examples: list[SourceLinkageExampleOut]


class MatchHintIn(BaseModel):
    """Identity-owned input DTO for :meth:`IdentityService.resolve_or_create_from_hint` (ENG-185).

    The provider-pull adapter (``SfLeadIngestService``, future CareStack
    handler) builds this DTO from the captured ``ingest.normalized_person_hint``
    row and passes it to identity. ``identity`` does not import ``ingest`` —
    this is a thin contract DTO, not a re-export of the hint row, so the
    cross-package import rule (``identity`` cannot reach into ``ingest``)
    stays intact even at the schema layer.

    Fields:

    * ``hint_id`` — pointer back to ``ingest.normalized_person_hint.id`` for
      idempotency / audit. ``None`` is accepted but disables the active
      hint-candidate dedup guard.
    * ``source_system`` / ``source_instance`` / ``source_kind`` /
      ``source_id`` — the external record key. The service uses them for
      Tier 0 source-link recapture and for the source link written on
      Tier 1 / Tier 2 / fallback.
    * ``given_name`` / ``family_name`` / ``display_name`` — non-PHI names
      already extracted by the ingest hint layer.
    * ``email_normalized`` / ``phone_normalized`` — already normalised by
      :class:`IngestService.capture_normalized_person_hint`. ``None`` means
      that identifier was absent or invalid upstream.
    * ``dob`` / ``ssn`` (ENG-309) — opt-in identity-strength signals.
      They are used by the resolver as HARD VETOES (mismatch -> never
      merge); they NEVER score positively in the tier ladder. They are
      never written to ``evidence`` / ``conflicts`` / log values
      (``dob`` and ``ssn`` remain in ``_FORBIDDEN_EVIDENCE_KEYS`` at the
      evidence-dict layer). Callers should pass digit-only normalised SSN
      strings (``"623359385"`` rather than ``"623-35-9385"``); the
      resolver also strips whitespace + dashes defensively before
      comparing.
    * ``quality_flags`` / ``meta`` — opaque parser metadata for downstream
      reasoning. The match policy itself does not consume them, but they
      ride along so future tiers can.
    """

    model_config = ConfigDict(from_attributes=True)

    hint_id: UUID | None = None
    source_system: str = Field(..., min_length=1, max_length=32)
    source_instance: str | None = Field(default=None, max_length=96)
    source_kind: str = Field(..., min_length=1, max_length=32)
    source_id: str = Field(..., min_length=1, max_length=240)
    given_name: str | None = Field(default=None, max_length=120)
    family_name: str | None = Field(default=None, max_length=120)
    display_name: str | None = Field(default=None, max_length=240)
    email_normalized: str | None = Field(default=None, max_length=320)
    phone_normalized: str | None = Field(default=None, max_length=64)
    dob: date | None = None
    ssn: str | None = Field(default=None, max_length=32)
    quality_flags: dict[str, object] = Field(default_factory=dict)
    meta: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def fill_default_source_instance(self) -> Self:
        if self.source_instance is None or self.source_instance.strip() == "":
            self.source_instance = default_source_instance(self.source_system)
        return self


class ResolveFromHintResult(BaseModel):
    """Typed return value of :meth:`IdentityService.resolve_or_create_from_hint` (ENG-185).

    The provider-pull adapter consumes this to decide whether the upstream
    row was a re-pull, a reactivation, an ambiguous match, or a brand-new
    person — without owning the matching policy itself.

    Invariants (enforced by the service, not the DTO):

    * Exactly one of ``was_source_link_recapture`` /
      ``was_existing_person_match`` / ``was_new_person`` is ``True`` for
      Tier 0 / Tier 1 / Tier 2-or-fallback respectively.
    * ``open_candidate`` may be ``True`` only when ``was_new_person`` is
      ``True`` (Tier 2 always creates a new source-linked person).
    * ``match_candidate_id`` is ``None`` for Tier 0 (source-link recapture
      does not write a candidate row); set for Tier 1 and Tier 2.
    """

    model_config = ConfigDict(from_attributes=False)

    person_uid: UUID
    was_new_person: bool = False
    was_existing_person_match: bool = False
    was_source_link_recapture: bool = False
    match_candidate_id: UUID | None = None
    open_candidate: bool = False


class PossibleDuplicateOut(BaseModel):
    """One open MatchCandidate as surfaced on the person card.

    The "other person" is the side of the pair that is NOT the person being
    viewed; the route resolves which side that is and inverts source/candidate
    accordingly before serializing.
    """

    candidate_id: UUID
    other_person_uid: UUID
    other_display_name: str | None = None
    other_source_systems: list[str] = Field(default_factory=list)
    match_rule: str
    confidence: Decimal
    evidence: dict[str, object] = Field(default_factory=dict)
    conflicts: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class SweepSummaryOut(BaseModel):
    """Result envelope for ``IdentityService.sweep_for_merges``."""

    persons_scanned: int = 0
    pairs_evaluated: int = 0
    auto_merged: int = 0
    open_candidates_created: int = 0
    skipped_already_decided: int = 0
    persons_errored: int = 0


class MatchReplayDecisionOut(BaseModel):
    """One open ``identity.match_candidate`` re-evaluated under the CURRENT
    match policy (ENG-544 replay).

    The replay reconstructs the original ingest hint from the recorded pair
    (the source person's names + the shared identifier, which lives on the
    candidate person when the lead dropped it under the ENG-340 shared-contact
    guard) and re-runs :func:`_evaluate_match_policy`. ``outcome`` is one of:

    * ``"would_merge"`` — the current policy yields a single Tier-1 auto-accept
      whose target is exactly the recorded candidate person. ``survivor_person_uid``
      (the existing canonical person) absorbs ``merged_person_uid`` (the lead
      duplicate). In a live pass the service records the merge + moves source
      links; the caller moves ``ops.lead`` rows.
    * ``"stay_open"`` — still ambiguous (multiple Tier-1 candidates, a real name
      disagreement, or a single auto-accept to a DIFFERENT person than the
      recorded pair). Left untouched for the operator / sweep.
    * ``"skipped"`` — no current match at all (the shared identifier is gone, a
      referenced person is missing, or an ENG-309 DOB/SSN veto fired).

    ``detail`` carries a short machine-stable reason code. This DTO identifies
    persons by ``person_uid`` ONLY — no display names. The job/CLI serialises it
    to stdout and runtime artifacts, and the root CLAUDE.md forbids names in
    logs; reviewers map a uid to a human via the markdown report, not here.
    """

    candidate_id: UUID
    source_person_uid: UUID | None
    candidate_person_uid: UUID
    outcome: str
    detail: str
    match_rule: str | None = None
    merge_reason: str | None = None
    survivor_person_uid: UUID | None = None
    merged_person_uid: UUID | None = None
    applied: bool = False


class MatchReplaySummaryOut(BaseModel):
    """Aggregate counts for an ENG-544 replay pass over open candidates."""

    tenant_id: UUID
    dry_run: bool = True
    scanned: int = 0
    would_merge: int = 0
    would_stay_open: int = 0
    skipped: int = 0
    merged_applied: int = 0
    leads_reassigned: int = 0
    samples: list[MatchReplayDecisionOut] = Field(default_factory=list)


class PersonSummaryOut(BaseModel):
    """Listing-grade Person projection used by the dashboard recent-persons
    list and the people-search results.

    Mirrors the Zod ``PersonSummarySchema`` in
    ``apps/web/lib/api/schemas/person.ts``. All cross-domain flags
    (``has_lead``, ``has_consultation``, ``source_providers``) are populated
    at the route layer from sibling services — this DTO is the contract,
    not the producer.
    """

    id: UUID
    display_name: str
    email: str | None = None
    phone: str | None = None
    has_lead: bool = False
    has_consultation: bool = False
    last_activity_at: datetime | None = None
    source_providers: list[str] = Field(default_factory=list)
