"""IdentityService — the only entry point for identity-domain logic.

Responsibilities:
  * normalise external identifiers (phones, emails)
  * resolve an existing person by identifier
  * create/update a person
  * resolve-or-create person from an external-system source link
  * record an append-only merge event when two persons collapse into one

Every public method takes ``tenant_id: TenantId`` as the first positional
argument after ``self`` (ENG-128). The method forwards it into the
repository so a stray UUID can never slip into a tenant filter.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.logging import get_logger
from packages.core.types import PersonUID, TenantId

from .models import (
    MATCH_CANDIDATE_ACCEPTED_STATUSES,
    MATCH_CANDIDATE_STATUSES,
    MATCH_RULES,
    MERGE_REASONS,
    SOURCE_KINDS,
    SOURCE_SYSTEMS,
    MatchCandidate,
    MergeEvent,
    Person,
    PersonIdentifier,
    SourceLink,
    default_source_instance,
    make_person_pair_key,
)
from .repository import IdentityRepository
from .schemas import (
    MatchCandidateIn,
    MatchCandidateOut,
    MatchHintIn,
    MatchReplayDecisionOut,
    PersonIdentifierIn,
    PersonIn,
    PossibleDuplicateOut,
    ResolveFromHintResult,
    SourceLinkageCoverageOut,
    SourceLinkageExampleOut,
    SourceLinkSummaryOut,
    SweepSummaryOut,
)

log = get_logger("identity")

# ENG-341: phone/email are SHARED household contacts, not globally-unique
# identity keys. Household members (same phone/email, different DOB) are
# correctly kept as distinct persons, and the model now lets them each hold the
# shared value: the blanket ``uq_person_identifier_kind_value`` was replaced by
# a per-person idempotency guard plus a PARTIAL unique index that exempts these
# two kinds (see ``packages/identity/models.py``). So the ENG-340 skip is gone —
# a shared value owned by another person is now ATTACHED to this person too.
# This set drives the kind-aware attach logic and MUST stay in sync with the
# migration's ``kind NOT IN ('phone', 'email')`` denylist.
_SHARED_CONTACT_KINDS = frozenset({"phone", "email"})

# Keys we refuse to accept in MatchCandidate.evidence / conflicts. These keys
# are heuristics for PHI and raw provider payloads; the service rejects the
# whole insert if any of these appear so accidental leakage gets caught early.
# This is a deny-list, not an allow-list — additional check lands when product
# settles the canonical evidence keys (ENG-183).
_FORBIDDEN_EVIDENCE_KEYS: frozenset[str] = frozenset(
    {
        "dob",
        "date_of_birth",
        "birthdate",
        "ssn",
        "allergy",
        "allergies",
        "medication",
        "medications",
        "prescription",
        "diagnosis",
        "chief_complaint",
        "clinical_notes",
        "treatment_notes",
        "raw_payload",
        "raw",
        "payload",
        "phi",
    }
)

# Identifier canonicalisation lives in ``canonical`` so the repository read
# path can import the match-key helpers without an import cycle through this
# service. Re-exported here for the many callers that historically import
# ``normalise_phone`` / ``normalise_email`` from ``packages.identity.service``.
from .canonical import (  # noqa: E402
    identifier_match_key,
    normalise_email,
    normalise_phone,
    phone_match_key,
)

__all__ = [
    "IdentityService",
    "normalise_phone",
    "normalise_email",
    "phone_match_key",
    "identifier_match_key",
]


def _normalise_source_instance(source_system: str, source_instance: str | None = None) -> str:
    """Return an explicit source-instance slug for legacy and new callers."""
    value = (source_instance or "").strip()
    if not value:
        value = default_source_instance(source_system)
    if len(value) > 96:
        raise ValidationError(
            "source_instance must be at most 96 characters",
            details={"source_instance": value},
        )
    return value


def _collect_forbidden_evidence_paths(value: object, prefix: str = "") -> list[str]:
    """Return PHI-looking JSON key paths from a MatchCandidate payload."""
    if isinstance(value, Mapping):
        paths: list[str] = []
        for raw_key, nested_value in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(raw_key, str) and raw_key.lower() in _FORBIDDEN_EVIDENCE_KEYS:
                paths.append(path)
            paths.extend(_collect_forbidden_evidence_paths(nested_value, path))
        return paths
    if isinstance(value, list | tuple):
        paths = []
        for idx, nested_value in enumerate(value):
            path = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            paths.extend(_collect_forbidden_evidence_paths(nested_value, path))
        return paths
    return []


def _reject_phi_keys(field_name: str, payload: Mapping[str, object]) -> None:
    """Refuse PHI-looking keys in MatchCandidate evidence/conflicts payloads.

    Match policy ledger rows must not be a backdoor for clinical text or raw
    provider payloads. The deny-list is conservative; widen it in lock-step
    with reviewer feedback when the canonical evidence shape settles
    (ENG-183).
    """
    if not payload:
        return
    offending = sorted(_collect_forbidden_evidence_paths(payload))
    if offending:
        raise ValidationError(
            f"{field_name} contains forbidden keys",
            details={"field": field_name, "keys": offending},
        )


# --- Match policy primitives (ENG-185) ---
#
# These helpers are module-private but exported through ``IdentityService``;
# they're plain functions so the tier ladder is straightforward to read and
# to test in isolation from any DB.


# Initial thresholds from the R2/P2 match policy proposal. Adjust as a unit
# when product settles canonical values; do not tune per call site.
_AUTO_ACCEPT_EMAIL_PHONE_NAME = Decimal("0.99")
_AUTO_ACCEPT_PHONE_NAME = Decimal("0.95")
_AUTO_ACCEPT_EMAIL_NAME = Decimal("0.92")
_OPEN_AMBIGUOUS_FLOOR = Decimal("0.70")


@dataclass(frozen=True)
class _AutoAccept:
    """Tier 1 decision: one high-confidence existing-person match."""

    person: Person
    match_rule: str
    confidence: Decimal
    evidence: dict[str, object]


@dataclass(frozen=True)
class _OpenAmbiguous:
    """Tier 2 decision: ambiguous or weak match against ``primary``."""

    primary: Person
    match_rule: str
    confidence: Decimal
    evidence: dict[str, object]
    conflicts: dict[str, object]


@dataclass(frozen=True)
class _NewPerson:
    """Fallback decision: no candidate matched."""


_MatchDecision = _AutoAccept | _OpenAmbiguous | _NewPerson


_SSN_STRIP = re.compile(r"[\s\-]+")


def _normalise_ssn_for_compare(value: str | None) -> str | None:
    """Return a digit-cluster SSN string for equality comparisons.

    ENG-309: callers (notably ``CareStackPatientIngestService``) already
    normalise SSN to digits-only before passing it into ``MatchHintIn``,
    but the resolver-side compare is defense-in-depth: a manual caller
    or future provider might pass ``"623-35-9385"`` or ``" 623 35 9385"``.
    Stripping whitespace + dashes here keeps the veto consistent without
    forcing every call site to know the format.
    """
    if value is None:
        return None
    cleaned = _SSN_STRIP.sub("", value).strip()
    return cleaned or None


def _has_hard_identity_conflict(hint: MatchHintIn, candidate: Person) -> bool:
    """Return ``True`` when a candidate must be vetoed by DOB / SSN mismatch.

    ENG-309: DOB and SSN are demographic identity-strength signals. The
    resolver applies them as HARD VETOES, not as positive scores:

    * If both ``hint.dob`` and ``candidate.dob`` are set and they differ,
      veto the candidate.
    * If both ``hint.ssn`` and ``candidate.ssn`` are set and the digit-only
      normalised forms differ, veto the candidate.
    * If either side is missing, the veto does NOT fire (the soft tier
      ladder takes over). Different humans without a stored DOB / SSN can
      still be kept apart by name + phone + email rules; veto is only
      meaningful when both sides actually carry the signal.

    The veto fires BEFORE the email_phone_name / phone_name / email_name
    rules evaluate. A vetoed candidate is dropped from the per-candidate
    tier loop entirely (the resolver behaves as if that candidate did not
    exist for tier-1 purposes). It can still contribute to ambiguity
    counting via the surviving candidates' tier-2 collapse if applicable.
    """
    if hint.dob is not None and candidate.dob is not None and hint.dob != candidate.dob:
        return True
    hint_ssn = _normalise_ssn_for_compare(hint.ssn)
    cand_ssn = _normalise_ssn_for_compare(candidate.ssn)
    if hint_ssn is not None and cand_ssn is not None and hint_ssn != cand_ssn:
        return True
    return False


# ENG-543: split a name field into words on whitespace AND punctuation, while
# preserving unicode letters/digits (``\W`` is unicode-aware for ``str``). So
# "Newton Patrick", "Newton-Patrick", and "Newton, Patrick" all yield the same
# {"newton", "patrick"}; non-ASCII names ("José") survive intact.
_NAME_WORD_SPLIT = re.compile(r"[\W_]+")


def _name_words(*values: str | None) -> set[str]:
    """Return the union of lowercased name WORDS across the given fields.

    ENG-543: each of given / family / display is split on whitespace and
    punctuation and lowercased; empty fragments are dropped. The result is
    ONE word-set per side, so which field carried which token no longer
    matters. A lead that packed the whole name into ``family_name``
    ('Newton Patrick', ``given_name`` empty) collapses to the same
    {'newton', 'patrick'} as a person with given='Patrick', family='Newton'.
    """
    words: set[str] = set()
    for value in values:
        if not value:
            continue
        for word in _NAME_WORD_SPLIT.split(value.lower()):
            if word:
                words.add(word)
    return words


def _names_compatible(hint: MatchHintIn, person: Person) -> bool:
    """Return True when hint and person names do not contradict (ENG-543).

    Word-level, order-independent compatibility:

    * If either side has NO name words at all, the names are compatible
      (absence is not a conflict — preserves the empty-lead behaviour the
      tier ladder relies on).
    * Otherwise the names are compatible IFF the SHORTER word-set is a
      subset of the longer one.

    This makes reversed First/Last ('Newton Patrick' vs 'Patrick Newton'),
    everything-in-one-field leads, and a middle name / initial present on
    only one side ('John Smith' vs 'John A Smith') compatible, while still
    rejecting a genuine disagreement ('John Smith' vs 'Jane Smith' —
    'jane' is absent from the other side). Intentionally permissive about
    EXTRA words and strict about CONTRADICTING ones: a strong phone match
    must never override a real name disagreement (that pair stays
    Tier-2/open), but a lead whose only "conflict" was field ordering or a
    packed name field should auto-link.
    """
    hint_words = _name_words(hint.given_name, hint.family_name, hint.display_name)
    person_words = _name_words(
        person.given_name, person.family_name, person.display_name
    )
    if not hint_words or not person_words:
        return True
    shorter, longer = (
        (hint_words, person_words)
        if len(hint_words) <= len(person_words)
        else (person_words, hint_words)
    )
    return shorter <= longer


def _person_identifier_values(person: Person, kind: str) -> set[str]:
    """Return the set of identifier values of ``kind`` attached to ``person``."""
    return {ident.value for ident in person.identifiers if ident.kind == kind}


def _person_identifier_match_keys(person: Person, kind: str) -> set[str]:
    """Return the canonical MATCH KEYS for a person's ``kind`` identifiers.

    Match scoring must compare on the canonical key, not the raw value, so a
    phone stored as ``2015550123`` scores equal to an incoming ``+12015550123``
    (ENG-562). Derived on the fly from the stored value so it is correct even
    for rows whose ``value_match_key`` column has not been backfilled yet.
    """
    return {
        identifier_match_key(kind, ident.value)
        for ident in person.identifiers
        if ident.kind == kind
    }


def _hint_to_person_in(
    hint: MatchHintIn,
    *,
    include_matched_email: bool = True,
    include_matched_phone: bool = True,
) -> PersonIn:
    """Translate a :class:`MatchHintIn` into a :class:`PersonIn`.

    Identifiers are already normalised by the ingest hint layer; the
    constructed :class:`PersonIn` passes them through ``create_person``,
    which re-applies the (idempotent) normaliser before insert.

    ENG-309: ``dob`` and ``ssn`` ride into the new ``Person`` row so a
    later resolve_or_create_from_hint call (whether from CareStack
    re-pull or from another provider) can apply the DOB/SSN veto against
    this person.
    """
    identifiers: list[PersonIdentifierIn] = []
    if include_matched_email and hint.email_normalized:
        identifiers.append(PersonIdentifierIn(kind="email", value=hint.email_normalized))
    if include_matched_phone and hint.phone_normalized:
        identifiers.append(PersonIdentifierIn(kind="phone", value=hint.phone_normalized))
    return PersonIn(
        given_name=hint.given_name,
        family_name=hint.family_name,
        display_name=hint.display_name,
        dob=hint.dob,
        ssn=_normalise_ssn_for_compare(hint.ssn),
        identifiers=identifiers,
    )


def _evaluate_match_policy(hint: MatchHintIn, candidates: list[Person]) -> _MatchDecision:
    """Classify ``hint`` against the persons that share an identifier.

    Returns:
        * :class:`_AutoAccept` when exactly one candidate clears one of the
          tier-1 thresholds.
        * :class:`_OpenAmbiguous` when multiple candidates exist, or one
          candidate matched only weakly (e.g. email-only with name conflict).
        * :class:`_NewPerson` when no candidate matched at all, OR when
          every candidate was vetoed by an ENG-309 DOB / SSN hard mismatch.
    """
    if not candidates:
        return _NewPerson()

    # ENG-309: hard veto on DOB / SSN mismatch. Vetoed candidates are dropped
    # from the policy view entirely -- they cannot become tier-1 auto-accept
    # and cannot become a tier-2 primary (the "other side" of an open
    # ambiguous candidate would have been a different human, which is the
    # exact wrong outcome we're preventing). The repository's candidate
    # list still surfaces them for operator-side debugging; the policy just
    # behaves as if they did not match an identifier.
    eligible_candidates = [
        c for c in candidates if not _has_hard_identity_conflict(hint, c)
    ]
    if not eligible_candidates:
        return _NewPerson()

    # Per-candidate tier evaluation. ``auto_accept_eligible`` counts how many
    # candidates clear at least one tier-1 rule; >1 collapses to Tier 2.
    best: tuple[Person, str, Decimal, dict[str, object]] | None = None
    auto_accept_eligible = 0
    has_email_match_any = False
    has_phone_match_any = False

    # Score on canonical match keys, not raw values (ENG-562): the repository
    # surfaces cross-format phone candidates, so the policy must also treat
    # ``2015550123`` and ``+12015550123`` as the same phone or it would drop the
    # auto-accept and create a duplicate/ambiguous person.
    hint_email_key = (
        identifier_match_key("email", hint.email_normalized)
        if hint.email_normalized
        else None
    )
    hint_phone_key = (
        identifier_match_key("phone", hint.phone_normalized)
        if hint.phone_normalized
        else None
    )

    for candidate in eligible_candidates:
        candidate_emails = _person_identifier_match_keys(candidate, "email")
        candidate_phones = _person_identifier_match_keys(candidate, "phone")

        has_email = bool(hint_email_key and hint_email_key in candidate_emails)
        has_phone = bool(hint_phone_key and hint_phone_key in candidate_phones)
        if has_email:
            has_email_match_any = True
        if has_phone:
            has_phone_match_any = True

        names_ok = _names_compatible(hint, candidate)
        # Phone conflict: the hint has a phone, the candidate has phones, but
        # the hint's phone is not among them. Blocks the email-only tier.
        phone_conflict = bool(
            hint_phone_key
            and candidate_phones
            and hint_phone_key not in candidate_phones
        )

        rule: tuple[str, Decimal, dict[str, object]] | None = None
        if has_email and has_phone and names_ok:
            rule = (
                "email_phone_name",
                _AUTO_ACCEPT_EMAIL_PHONE_NAME,
                {
                    "email_match": True,
                    "phone_match": True,
                    "name_compatible": True,
                },
            )
        elif has_phone and names_ok:
            rule = (
                "phone_name",
                _AUTO_ACCEPT_PHONE_NAME,
                {"phone_match": True, "name_compatible": True},
            )
        elif has_email and names_ok and not phone_conflict:
            rule = (
                "email_name",
                _AUTO_ACCEPT_EMAIL_NAME,
                {
                    "email_match": True,
                    "name_compatible": True,
                    "phone_conflict": False,
                },
            )

        if rule is not None:
            auto_accept_eligible += 1
            if best is None or rule[1] > best[2]:
                best = (candidate, rule[0], rule[1], rule[2])

    if auto_accept_eligible == 1 and best is not None:
        person, match_rule, confidence, evidence = best
        return _AutoAccept(
            person=person,
            match_rule=match_rule,
            confidence=confidence,
            evidence=evidence,
        )

    # Tier 2 — ambiguous or weak. Pick a primary candidate from the
    # ENG-309-eligible list (the first by creation order). Vetoed candidates
    # never become the primary.
    primary = eligible_candidates[0]
    if has_phone_match_any and not has_email_match_any:
        ambiguous_rule = "phone_only_ambiguous"
    else:
        ambiguous_rule = "email_only_ambiguous"

    ambiguous_evidence: dict[str, object] = {
        "candidate_count": len(eligible_candidates),
        "email_match_any": has_email_match_any,
        "phone_match_any": has_phone_match_any,
    }
    ambiguous_conflicts: dict[str, object] = {
        "auto_accept_eligible": auto_accept_eligible,
        "name_compatible": _names_compatible(hint, primary),
    }
    return _OpenAmbiguous(
        primary=primary,
        match_rule=ambiguous_rule,
        confidence=_OPEN_AMBIGUOUS_FLOOR,
        evidence=ambiguous_evidence,
        conflicts=ambiguous_conflicts,
    )


class IdentityService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = IdentityRepository(session)

    async def resolve_by_phone(self, tenant_id: TenantId, phone: str) -> Person | None:
        identifier = await self._repo.find_identifier(tenant_id, "phone", normalise_phone(phone))
        return identifier.person if identifier else None

    async def resolve_by_email(self, tenant_id: TenantId, email: str) -> Person | None:
        identifier = await self._repo.find_identifier(tenant_id, "email", normalise_email(email))
        return identifier.person if identifier else None

    async def get_person(self, tenant_id: TenantId, person_uid: PersonUID) -> Person:
        person = await self._repo.get_person(tenant_id, person_uid)
        if person is None:
            raise NotFoundError("person not found", details={"person_uid": str(person_uid)})
        return person

    async def get_primary_phone(
        self, tenant_id: TenantId, person_uid: PersonUID
    ) -> str | None:
        """Return the person's primary phone identifier value, or ``None``.

        ENG-460: the messenger notification boundary needs a person's phone
        to build a useful PHI card. The phone is a ``PersonIdentifier`` of
        ``kind == "phone"`` (digit-only normalised). When a person carries
        several phones we return the oldest-created one deterministically
        (the "primary"); when none is attached we return ``None``.

        Goes through the identity repository — no raw SQL at the caller — so
        the tenant filter and identifier load stay owned by this domain.
        """
        person = await self._repo.get_person(tenant_id, person_uid)
        if person is None:
            return None
        phones = [ident for ident in person.identifiers if ident.kind == "phone"]
        if not phones:
            return None
        phones.sort(key=lambda ident: (ident.created_at, str(ident.id)))
        return phones[0].value

    async def list_recent(self, tenant_id: TenantId, limit: int = 10) -> list[Person]:
        """Return the N most recently updated persons (with identifiers loaded)."""
        return await self._repo.list_recent(tenant_id, limit)

    async def list_by_ids(self, tenant_id: TenantId, person_uids: list[UUID]) -> list[Person]:
        """Return persons by id with identifiers loaded."""
        return await self._repo.list_by_ids(tenant_id, person_uids)

    async def count_for_tenant(self, tenant_id: TenantId) -> int:
        """Return the total count of persons in this tenant.

        Used by the staff ``GET /persons`` list endpoint to render the total
        count alongside a paginated slice. Cheap aggregate query; not cached.
        """
        return await self._repo.count_for_tenant(tenant_id)

    async def source_providers_for(
        self, tenant_id: TenantId, person_uids: list[UUID]
    ) -> dict[UUID, list[str]]:
        """Return distinct ``source_link.source_system`` values per person.

        Used by the dashboard recent-persons projection to fill the
        ``source_providers`` array on each :class:`PersonSummaryOut` without
        an N+1 round-trip.
        """
        return await self._repo.list_source_providers_for(tenant_id, person_uids)

    async def source_links_for_persons(
        self, tenant_id: TenantId, person_uids: list[UUID]
    ) -> dict[UUID, list[SourceLinkSummaryOut]]:
        """Return source links grouped by ``person_uid`` for read projections."""
        links = await self._repo.list_source_links_for_persons(tenant_id, person_uids)
        out: dict[UUID, list[SourceLinkSummaryOut]] = {uid: [] for uid in person_uids}
        for link in links:
            out.setdefault(link.person_uid, []).append(
                SourceLinkSummaryOut(
                    id=link.id,
                    person_uid=link.person_uid,
                    source_system=link.source_system,
                    source_instance=link.source_instance,
                    source_kind=link.source_kind,
                    source_id=link.source_id,
                    first_seen_at=link.first_seen_at,
                    last_seen_at=link.last_seen_at,
                )
            )
        return out

    async def find_source_link(
        self,
        tenant_id: TenantId,
        source_system: str,
        source_kind: str,
        person_uid: UUID | None = None,
    ) -> SourceLinkSummaryOut | None:
        """Find a source link by system/kind, optionally filtered by person."""
        links = await self._repo.list_source_links_for_persons(
            tenant_id, [person_uid] if person_uid else []
        )
        for link in links:
            if (
                link.source_system == source_system
                and link.source_kind == source_kind
                and (person_uid is None or link.person_uid == person_uid)
            ):
                return SourceLinkSummaryOut(
                    id=link.id,
                    person_uid=link.person_uid,
                    source_system=link.source_system,
                    source_instance=link.source_instance,
                    source_kind=link.source_kind,
                    source_id=link.source_id,
                    first_seen_at=link.first_seen_at,
                    last_seen_at=link.last_seen_at,
                )
        return None

    async def source_links_for_external_records(
        self,
        tenant_id: TenantId,
        keys: list[tuple[str, str, str, str]],
    ) -> dict[tuple[str, str, str, str], SourceLinkSummaryOut]:
        """Return source links keyed by external ``(system, instance, kind, id)``."""
        links = await self._repo.list_source_links_by_external_records(tenant_id, keys)
        return {
            (
                link.source_system,
                link.source_instance,
                link.source_kind,
                str(link.source_id),
            ): SourceLinkSummaryOut(
                id=link.id,
                person_uid=link.person_uid,
                source_system=link.source_system,
                source_instance=link.source_instance,
                source_kind=link.source_kind,
                source_id=link.source_id,
                first_seen_at=link.first_seen_at,
                last_seen_at=link.last_seen_at,
            )
            for link in links
            if link.source_id is not None
        }

    async def source_links_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        source_system: str | None = None,
        source_kind: str | None = None,
        first_seen_from: datetime | None = None,
        first_seen_to: datetime | None = None,
        limit: int = 200,
    ) -> list[SourceLinkSummaryOut]:
        """Return source links for dashboard source-record rows."""
        links = await self._repo.list_source_links_for_dashboard(
            tenant_id,
            source_system=source_system,
            source_kind=source_kind,
            first_seen_from=first_seen_from,
            first_seen_to=first_seen_to,
            limit=limit,
        )
        return [
            SourceLinkSummaryOut(
                id=link.id,
                person_uid=link.person_uid,
                source_system=link.source_system,
                source_instance=link.source_instance,
                source_kind=link.source_kind,
                source_id=link.source_id,
                first_seen_at=link.first_seen_at,
                last_seen_at=link.last_seen_at,
            )
            for link in links
        ]

    async def full_funnel_carestack_patient_person_uids(
        self, tenant_id: TenantId
    ) -> list[UUID]:
        """DISTINCT person_uids with a ``carestack/patient`` source link (ENG-481).

        All-time (NOT windowed). The CareStack patient object carries no
        creation date, so the source link's ``first_seen_at`` is a bulk-import
        artifact and meaningless for funnel timing. The Full Funnel composition
        layer subtracts persons that have any ``ops.lead`` (the "no lead"
        exclusion is cross-domain and cannot live in identity) and dates the
        remaining CareStack-direct persons by their earliest real activity.
        """
        return await self._repo.full_funnel_carestack_patient_person_uids(tenant_id)

    async def count_source_links_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        source_system: str | None = None,
        source_kind: str | None = None,
        first_seen_from: datetime | None = None,
        first_seen_to: datetime | None = None,
    ) -> int:
        """Return a count for dashboard source-record rows."""
        return await self._repo.count_source_links_for_dashboard(
            tenant_id,
            source_system=source_system,
            source_kind=source_kind,
            first_seen_from=first_seen_from,
            first_seen_to=first_seen_to,
        )

    async def get_source_linkage_coverage(
        self,
        tenant_id: TenantId,
        *,
        sample_limit: int = 25,
    ) -> SourceLinkageCoverageOut:
        """Return masked Salesforce-to-CareStack linkage coverage."""
        if sample_limit < 1 or sample_limit > 100:
            raise ValidationError(
                "sample_limit must be between 1 and 100",
                details={"sample_limit": sample_limit},
            )
        counts = await self._repo.source_linkage_coverage(tenant_id)
        examples = await self._repo.list_source_linkage_examples(
            tenant_id,
            limit=sample_limit,
        )
        salesforce_count = int(counts["salesforce_person_count"])
        carestack_count = int(counts["carestack_person_count"])
        linked_count = int(counts["linked_salesforce_carestack_count"])
        return SourceLinkageCoverageOut(
            total_persons=int(counts["total_persons"]),
            salesforce_person_count=salesforce_count,
            carestack_person_count=carestack_count,
            linked_salesforce_carestack_count=linked_count,
            salesforce_only_count=int(counts["salesforce_only_count"]),
            carestack_only_count=int(counts["carestack_only_count"]),
            salesforce_to_carestack_rate=(
                linked_count / salesforce_count if salesforce_count else None
            ),
            carestack_to_salesforce_rate=(
                linked_count / carestack_count if carestack_count else None
            ),
            examples=[_linkage_example_from_raw(example) for example in examples],
        )

    async def create_person(self, tenant_id: TenantId, payload: PersonIn) -> Person:
        person = Person(
            tenant_id=tenant_id,
            given_name=payload.given_name,
            family_name=payload.family_name,
            display_name=payload.display_name
            or " ".join(p for p in [payload.given_name, payload.family_name] if p)
            or None,
            dob=payload.dob,
            ssn=_normalise_ssn_for_compare(payload.ssn),
        )
        await self._repo.add_person(person)

        # ENG-341: shared household phone/email is attached even when another
        # person already owns it (the global UNIQUE no longer applies to these
        # kinds). The only duplicate to avoid is an identical (kind, value)
        # repeated inside THIS payload, which would trip the per-person
        # ``uq_person_identifier_person_kind_value`` guard.
        seen: set[tuple[str, str]] = set()
        for ident in payload.identifiers:
            value = (
                normalise_phone(ident.value)
                if ident.kind == "phone"
                else normalise_email(ident.value)
                if ident.kind == "email"
                else ident.value
            )
            if (ident.kind, value) in seen:
                continue
            seen.add((ident.kind, value))
            await self._repo.add_identifier(
                PersonIdentifier(
                    tenant_id=tenant_id,
                    person_id=person.id,
                    kind=ident.kind,
                    value=value,
                )
            )

        return person

    async def attach_identifier(
        self, tenant_id: TenantId, person_uid: PersonUID, kind: str, value: str
    ) -> str:
        """Attach a single identifier to an EXISTING person, idempotently.

        ENG-542 backfill primitive. Mirrors the per-identifier path in
        :meth:`create_person`, kind-aware after the ENG-341 shared-contact
        rework:

        * normalises ``phone`` / ``email`` (other kinds pass through);
        * returns ``"exists"`` when THIS person already holds the value
          (idempotent — safe to re-run);
        * for a SHARED kind (``phone`` / ``email``), when ANOTHER person owns
          the value, ATTACHES it to this person too and returns ``"added"`` —
          shared household contacts are first-class (ENG-341), no longer
          skipped;
        * for a UNIQUE kind (everything else: ``carestack_patient_id``,
          ``salesforce_contact_id``, …), when ANOTHER person owns the value,
          returns ``"collision"`` — the value is NOT attached and no exception
          is raised (the partial unique index still forbids a second row);
        * returns ``"invalid"`` for a phone/email that fails normalisation,
          so a bulk backfill never aborts on one malformed hint value;
        * otherwise inserts the row and returns ``"added"``.

        Never creates a person; raises :class:`NotFoundError` if the person
        does not exist in the tenant.
        """
        try:
            normalised = (
                normalise_phone(value)
                if kind == "phone"
                else normalise_email(value)
                if kind == "email"
                else value
            )
        except ValidationError:
            return "invalid"
        if not normalised:
            return "invalid"

        person = await self._repo.get_person(tenant_id, person_uid)
        if person is None:
            raise NotFoundError(
                "person not found", details={"person_uid": str(person_uid)}
            )

        existing = await self._repo.find_identifier(tenant_id, kind, normalised)
        if existing is not None:
            if existing.person_id == person.id:
                return "exists"
            # ENG-341: another person owns the value. For a UNIQUE kind the
            # partial unique index forbids a second row — refuse (collision).
            # For a SHARED kind (phone/email) the value is a household contact:
            # attach it to this person too and fall through to "added".
            if kind not in _SHARED_CONTACT_KINDS:
                log.info(
                    "identity.unique_identifier_collision",
                    kind=kind,
                    person_id=str(person.id),
                    owner_person_id=str(existing.person_id),
                )
                return "collision"

        await self._repo.add_identifier(
            PersonIdentifier(
                tenant_id=tenant_id,
                person_id=person.id,
                kind=kind,
                value=normalised,
            )
        )
        return "added"

    async def upsert_by_identifier(
        self,
        tenant_id: TenantId,
        kind: str,
        value: str,
        defaults: PersonIn | None = None,
    ) -> Person:
        """Resolve a person by an identifier, creating them if missing."""
        normalised = (
            normalise_phone(value)
            if kind == "phone"
            else normalise_email(value)
            if kind == "email"
            else value
        )

        identifier = await self._repo.find_identifier(tenant_id, kind, normalised)
        if identifier is not None:
            return identifier.person

        payload = defaults or PersonIn()
        # Force the resolving identifier to be persisted on the new person
        payload = payload.model_copy(
            update={
                "identifiers": [
                    *(payload.identifiers or []),
                    {"kind": kind, "value": normalised},
                ]
            }
        )
        return await self.create_person(tenant_id, payload)

    async def resolve_or_create_person(
        self,
        tenant_id: TenantId,
        source_system: str,
        source_kind: str,
        source_id: str,
        hints: PersonIn | None = None,
        source_instance: str | None = None,
    ) -> ResolveResult:
        """Resolve a person by source-system instance and external id.

        Used by provider-pull workers (W1 / W2) to convert an external record
        into a stable ``person_uid``. Idempotent: a second call with the same
        external key returns the same person and bumps ``last_seen_at`` on the
        source link.

        ``hints`` populates the new ``Person``'s identifiers/names ONLY when
        creating. They are NOT used for cross-provider matching — Phase 1
        does no fuzzy dedup. Two providers with the same email get two
        distinct persons; merging is later, manual, and recorded via
        :meth:`record_merge`.

        Returns a :class:`ResolveResult` with both the ``Person`` and a
        ``was_created`` flag, so callers (workers) know whether to emit a
        ``person_created`` interaction event.
        """
        if source_system not in SOURCE_SYSTEMS:
            raise ValidationError(
                "unknown source_system",
                details={"source_system": source_system, "allowed": list(SOURCE_SYSTEMS)},
            )
        if source_kind not in SOURCE_KINDS:
            raise ValidationError(
                "unknown source_kind",
                details={"source_kind": source_kind, "allowed": list(SOURCE_KINDS)},
            )
        if not source_id:
            raise ValidationError("source_id must be a non-empty string")
        resolved_source_instance = _normalise_source_instance(source_system, source_instance)

        existing = await self._repo.find_source_link(
            tenant_id,
            source_system,
            resolved_source_instance,
            source_kind,
            source_id,
        )
        if existing is not None:
            await self._repo.touch_source_link(tenant_id, existing.id)
            person = await self._repo.get_person(tenant_id, existing.person_uid)
            if person is None:
                # Defensive: a link without its person row violates the FK,
                # but better to surface a clear error than crash with NoneType.
                raise NotFoundError(
                    "source link references missing person",
                    details={
                        "person_uid": str(existing.person_uid),
                        "source_system": source_system,
                        "source_instance": resolved_source_instance,
                        "source_kind": source_kind,
                        "source_id": source_id,
                    },
                )
            return ResolveResult(person=person, was_created=False)

        payload = hints or PersonIn()
        person = await self.create_person(tenant_id, payload)
        await self._repo.add_source_link(
            SourceLink(
                tenant_id=tenant_id,
                person_uid=person.id,
                source_system=source_system,
                source_instance=resolved_source_instance,
                source_kind=source_kind,
                source_id=source_id,
            )
        )
        return ResolveResult(person=person, was_created=True)

    async def add_source_link(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
        source_system: str,
        source_kind: str,
        source_id: str,
        source_instance: str | None = None,
    ) -> SourceLink:
        """Append a ``source_link`` to an EXISTING person, idempotently.

        Used when a provider-pull worker discovers that a NEW external record
        actually maps to an already-known person (e.g. a brand-new Salesforce
        Lead with the same email as a person we already saw). Distinct from
        :meth:`resolve_or_create_person`, which creates the person if missing —
        this method NEVER creates a person.

        Idempotent: a second call with the same external triple returns the
        existing link (and bumps ``last_seen_at`` so re-pull volume is visible
        in source_link history).

        Validates ``source_system`` / ``source_kind`` against the allowed
        tuples; raises :class:`NotFoundError` if ``person_uid`` does not exist.
        """
        if source_system not in SOURCE_SYSTEMS:
            raise ValidationError(
                "unknown source_system",
                details={"source_system": source_system, "allowed": list(SOURCE_SYSTEMS)},
            )
        if source_kind not in SOURCE_KINDS:
            raise ValidationError(
                "unknown source_kind",
                details={"source_kind": source_kind, "allowed": list(SOURCE_KINDS)},
            )
        if not source_id:
            raise ValidationError("source_id must be a non-empty string")
        resolved_source_instance = _normalise_source_instance(source_system, source_instance)

        if (await self._repo.get_person(tenant_id, person_uid)) is None:
            raise NotFoundError(
                "person not found",
                details={"person_uid": str(person_uid)},
            )

        existing = await self._repo.find_source_link(
            tenant_id,
            source_system,
            resolved_source_instance,
            source_kind,
            source_id,
        )
        if existing is not None:
            await self._repo.touch_source_link(tenant_id, existing.id)
            return existing

        return await self._repo.add_source_link(
            SourceLink(
                tenant_id=tenant_id,
                person_uid=person_uid,
                source_system=source_system,
                source_instance=resolved_source_instance,
                source_kind=source_kind,
                source_id=source_id,
            )
        )

    async def record_merge(
        self,
        tenant_id: TenantId,
        surviving_person_uid: UUID,
        merged_person_uid: UUID,
        reason: str,
        evidence: Mapping[str, object] | None = None,
        performed_by_actor_id: UUID | None = None,
    ) -> MergeEvent:
        """Record an append-only merge event.

        This method records the *fact* that a merge happened. It does NOT
        rewrite cross-domain references (e.g. flipping ``ops.lead.person_uid``
        from merged to surviving) — that is the caller's responsibility,
        because merging downstream rows requires per-domain decisions
        (PHI, audit, idempotency) that this service has no business making.

        ``surviving_person_uid`` and ``merged_person_uid`` MUST differ
        (DB-level CHECK enforces this); ``reason`` MUST be one of
        :data:`MERGE_REASONS`.

        Phase 1 has no automated fuzzy dedup — every merge originates from a
        deliberate decision (manual, or a future cross-provider rule with
        explicit evidence).
        """
        if reason not in MERGE_REASONS:
            raise ValidationError(
                "unknown merge reason",
                details={"reason": reason, "allowed": list(MERGE_REASONS)},
            )
        if surviving_person_uid == merged_person_uid:
            raise ValidationError(
                "cannot merge a person into itself",
                details={"person_uid": str(surviving_person_uid)},
            )

        event = MergeEvent(
            tenant_id=tenant_id,
            surviving_person_uid=surviving_person_uid,
            merged_person_uid=merged_person_uid,
            reason=reason,
            evidence=dict(evidence or {}),
            performed_by_actor_id=performed_by_actor_id,
        )
        return await self._repo.add_merge_event(event)

    # --- Match candidates (ENG-182) ---

    async def _require_person_in_tenant(
        self,
        tenant_id: TenantId,
        person_uid: UUID | None,
        field_name: str,
    ) -> None:
        """Ensure a referenced person exists inside the match candidate tenant."""
        if person_uid is None:
            return
        if await self._repo.get_person(tenant_id, person_uid) is None:
            raise NotFoundError(
                "person not found",
                details={"field": field_name, "person_uid": str(person_uid)},
            )

    async def add_match_candidate(
        self, tenant_id: TenantId, payload: MatchCandidateIn
    ) -> MatchCandidate:
        """Insert a new ``identity.match_candidate`` row.

        Enforces the invariants documented on the model:

        * ``status`` in :data:`MATCH_CANDIDATE_STATUSES`.
        * ``confidence`` in ``[0, 1]``.
        * ``source_person_uid != candidate_person_uid`` when both set.
        * ``accepted_person_uid`` only for accepted statuses; required when
          status is accepted.
        * ``evidence`` / ``conflicts`` carry no clinical or raw-payload keys.

        Sets ``person_pair_key`` to the sorted pair when both persons are
        known so the partial-unique open-pair guard can fire at the DB.
        Sets ``decided_at`` to the current UTC instant for any non-``open``
        status so the timeline is queryable without joining audit.
        """
        if payload.status not in MATCH_CANDIDATE_STATUSES:
            raise ValidationError(
                "unknown match_candidate status",
                details={
                    "status": payload.status,
                    "allowed": list(MATCH_CANDIDATE_STATUSES),
                },
            )
        if payload.match_rule not in MATCH_RULES:
            raise ValidationError(
                "unknown match_candidate match_rule",
                details={
                    "match_rule": payload.match_rule,
                    "allowed": list(MATCH_RULES),
                },
            )

        confidence = Decimal(payload.confidence)
        if confidence < Decimal("0") or confidence > Decimal("1"):
            raise ValidationError(
                "confidence must be between 0 and 1",
                details={"confidence": str(confidence)},
            )

        if (
            payload.source_person_uid is not None
            and payload.source_person_uid == payload.candidate_person_uid
        ):
            raise ValidationError(
                "source_person_uid and candidate_person_uid must differ",
                details={"person_uid": str(payload.candidate_person_uid)},
            )

        is_accepted = payload.status in MATCH_CANDIDATE_ACCEPTED_STATUSES
        if payload.accepted_person_uid is not None and not is_accepted:
            raise ValidationError(
                "accepted_person_uid only valid for accepted statuses",
                details={
                    "status": payload.status,
                    "allowed": list(MATCH_CANDIDATE_ACCEPTED_STATUSES),
                },
            )
        if is_accepted and payload.accepted_person_uid is None:
            raise ValidationError(
                "accepted_person_uid required for accepted statuses",
                details={"status": payload.status},
            )

        _reject_phi_keys("evidence", payload.evidence)
        _reject_phi_keys("conflicts", payload.conflicts)

        await self._require_person_in_tenant(
            tenant_id, payload.candidate_person_uid, "candidate_person_uid"
        )
        await self._require_person_in_tenant(
            tenant_id, payload.source_person_uid, "source_person_uid"
        )
        await self._require_person_in_tenant(
            tenant_id, payload.accepted_person_uid, "accepted_person_uid"
        )

        person_pair_key = make_person_pair_key(
            payload.source_person_uid, payload.candidate_person_uid
        )
        decided_at = datetime.now(UTC) if payload.status != "open" else None

        candidate = MatchCandidate(
            tenant_id=tenant_id,
            hint_id=payload.hint_id,
            source_person_uid=payload.source_person_uid,
            candidate_person_uid=payload.candidate_person_uid,
            accepted_person_uid=payload.accepted_person_uid,
            status=payload.status,
            match_rule=payload.match_rule,
            confidence=confidence,
            evidence=dict(payload.evidence),
            conflicts=dict(payload.conflicts),
            person_pair_key=person_pair_key,
            decided_at=decided_at,
            decided_by_actor_id=payload.decided_by_actor_id,
        )
        return await self._repo.add_match_candidate(candidate)

    async def find_open_match_for_pair(
        self,
        tenant_id: TenantId,
        person_a: UUID,
        person_b: UUID,
    ) -> MatchCandidate | None:
        """Return an open candidate for the unordered pair, if one exists."""
        key = make_person_pair_key(person_a, person_b)
        if key is None:
            return None
        return await self._repo.find_open_match_for_pair(tenant_id, key)

    # --- Match policy entry point (ENG-185) ---

    async def resolve_or_create_from_hint(
        self, tenant_id: TenantId, hint: MatchHintIn
    ) -> ResolveFromHintResult:
        """Provider-neutral match policy entry point (ENG-185).

        Consumes a minimal :class:`MatchHintIn` (built by the ingest-side
        adapter from a persisted ``ingest.normalized_person_hint`` row) and
        applies the tier ladder:

        * **Tier 0** — exact source-instance-scoped source-link recapture.
          Touches ``last_seen_at``, returns the existing person, writes NO
          match candidate.
        * **Tier 1** — single high-confidence existing-person match. Adds
          the new source link to that person, writes
          ``MatchCandidate(status='auto_accepted')`` with the matched rule
          (``email_phone_name`` / ``phone_name`` / ``email_name``) and
          confidence ``0.99`` / ``0.95`` / ``0.92``.
        * **Tier 2** — ambiguous or weak match. Creates a new
          source-linked person (so the caller still gets a usable
          ``person_uid``) and writes
          ``MatchCandidate(status='open')`` with ``email_only_ambiguous``
          or ``phone_only_ambiguous``.
        * **Fallback** — no candidates. Creates a brand-new
          source-linked person; no match candidate row.

        Idempotency: re-calling with the same ``hint_id`` and candidate
        person reuses the existing active candidate row (Tier 1 / Tier 2)
        rather than colliding with the
        ``uq_match_candidate_hint_candidate_active`` partial unique guard.
        Tier 0 always returns without writing a candidate row regardless
        of ``hint_id``.

        ``identity`` does NOT import ``ingest``. The DTO is the contract.
        """
        if hint.source_system not in SOURCE_SYSTEMS:
            raise ValidationError(
                "unknown source_system",
                details={
                    "source_system": hint.source_system,
                    "allowed": list(SOURCE_SYSTEMS),
                },
            )
        if hint.source_kind not in SOURCE_KINDS:
            raise ValidationError(
                "unknown source_kind",
                details={
                    "source_kind": hint.source_kind,
                    "allowed": list(SOURCE_KINDS),
                },
            )

        # Defense in depth: the hint's metadata payloads should already be
        # PHI-free per IngestService.capture_normalized_person_hint, but the
        # match policy must not propagate a forbidden key into a candidate row.
        _reject_phi_keys("quality_flags", hint.quality_flags)
        _reject_phi_keys("meta", hint.meta)

        # Tier 0 — exact source-link recapture.
        source_instance = _normalise_source_instance(hint.source_system, hint.source_instance)
        existing_link = await self._repo.find_source_link(
            tenant_id,
            hint.source_system,
            source_instance,
            hint.source_kind,
            hint.source_id,
        )
        if existing_link is not None:
            await self._repo.touch_source_link(tenant_id, existing_link.id)
            person = await self._repo.get_person(tenant_id, existing_link.person_uid)
            if person is None:
                raise NotFoundError(
                    "source link references missing person",
                    details={
                        "person_uid": str(existing_link.person_uid),
                        "source_system": hint.source_system,
                        "source_instance": source_instance,
                        "source_kind": hint.source_kind,
                        "source_id": hint.source_id,
                    },
                )
            return ResolveFromHintResult(
                person_uid=person.id,
                was_source_link_recapture=True,
            )

        # Look up candidate persons by normalised email / phone.
        candidates = await self._repo.list_candidate_persons_by_identifiers(
            tenant_id, hint.email_normalized, hint.phone_normalized
        )
        decision = _evaluate_match_policy(hint, candidates)

        if isinstance(decision, _AutoAccept):
            return await self._apply_auto_accept(tenant_id, hint, decision)

        if isinstance(decision, _OpenAmbiguous):
            return await self._apply_open_ambiguous(tenant_id, hint, decision)

        # Fallback — brand-new source-linked person.
        result = await self.resolve_or_create_person(
            tenant_id,
            hint.source_system,
            hint.source_kind,
            hint.source_id,
            hints=_hint_to_person_in(hint),
            source_instance=source_instance,
        )
        return ResolveFromHintResult(
            person_uid=result.person.id,
            was_new_person=result.was_created,
        )

    def _maybe_backfill_demographic(self, person: Person, hint: MatchHintIn) -> None:
        """ENG-309: write DOB / SSN onto an existing person row IFF it has
        no value yet. Never overwrite a non-null value -- by the time this
        runs the veto already passed, so either both sides agreed or the
        person side was missing; in both cases the stored value should not
        change. The row is already in the session (returned via
        ``selectinload`` from the candidate query); the unit of work commits
        the update at the boundary.
        """
        if hint.dob is not None and person.dob is None:
            person.dob = hint.dob
        if hint.ssn is not None and person.ssn is None:
            person.ssn = _normalise_ssn_for_compare(hint.ssn)

    async def _apply_auto_accept(
        self,
        tenant_id: TenantId,
        hint: MatchHintIn,
        decision: _AutoAccept,
    ) -> ResolveFromHintResult:
        """Tier 1 — auto-accept the existing person, idempotent on hint_id."""
        # Idempotency: if this hint already has an active candidate row for
        # this person, reuse it rather than colliding with the partial-unique
        # guard. ``find_active_hint_candidate`` covers open / auto_accepted /
        # accepted statuses for the same ``(tenant_id, hint_id, candidate)``.
        if hint.hint_id is not None:
            existing = await self._repo.find_active_hint_candidate(
                tenant_id, hint.hint_id, decision.person.id
            )
            if existing is not None:
                return ResolveFromHintResult(
                    person_uid=decision.person.id,
                    was_existing_person_match=True,
                    match_candidate_id=existing.id,
                )

        # ENG-309: conservatively backfill DOB / SSN on the matched person
        # so a future veto compare has a value to fire on. We never overwrite
        # an existing non-null value -- the resolver let this candidate
        # through, so either both sides agreed or one side was missing. If
        # the existing person already had a value, the hint either matched
        # it or one of them was missing; in both cases the canonical-stored
        # value stays.
        self._maybe_backfill_demographic(decision.person, hint)

        # Source link first — if the auto-accept commit succeeds, the link is
        # already in place. Order matters: a later partial failure must not
        # leave a candidate row pointing at a person with no source link.
        await self.add_source_link(
            tenant_id,
            decision.person.id,
            hint.source_system,
            hint.source_kind,
            hint.source_id,
            source_instance=hint.source_instance,
        )

        candidate = await self.add_match_candidate(
            tenant_id,
            MatchCandidateIn(
                hint_id=hint.hint_id,
                source_person_uid=None,
                candidate_person_uid=decision.person.id,
                accepted_person_uid=decision.person.id,
                status="auto_accepted",
                match_rule=decision.match_rule,
                confidence=decision.confidence,
                evidence=decision.evidence,
                conflicts={},
            ),
        )
        return ResolveFromHintResult(
            person_uid=decision.person.id,
            was_existing_person_match=True,
            match_candidate_id=candidate.id,
        )

    async def _apply_open_ambiguous(
        self,
        tenant_id: TenantId,
        hint: MatchHintIn,
        decision: _OpenAmbiguous,
    ) -> ResolveFromHintResult:
        """Tier 2 — create a new source-linked person and open a candidate.

        Ambiguous matches must not block the upstream pull: the caller still
        gets a usable ``person_uid`` so it can persist its own ``ops.lead`` /
        ``ops.inquiry`` row. The decision is left to an operator (or a
        future reconciler) via the open candidate ledger.
        """
        new_person_hints = _hint_to_person_in(
            hint,
            include_matched_email=not bool(decision.evidence.get("email_match_any")),
            include_matched_phone=not bool(decision.evidence.get("phone_match_any")),
        )
        new_person_result = await self.resolve_or_create_person(
            tenant_id,
            hint.source_system,
            hint.source_kind,
            hint.source_id,
            hints=new_person_hints,
            source_instance=hint.source_instance,
        )
        new_person = new_person_result.person

        # Idempotency: re-pull writes the same source link (resolve_or_create_person
        # is idempotent) and must not create a second open row against the same
        # primary candidate.
        match_candidate_id: UUID | None = None
        if hint.hint_id is not None:
            existing = await self._repo.find_active_hint_candidate(
                tenant_id, hint.hint_id, decision.primary.id
            )
            if existing is not None:
                match_candidate_id = existing.id

        if match_candidate_id is None:
            row = await self.add_match_candidate(
                tenant_id,
                MatchCandidateIn(
                    hint_id=hint.hint_id,
                    source_person_uid=new_person.id,
                    candidate_person_uid=decision.primary.id,
                    accepted_person_uid=None,
                    status="open",
                    match_rule=decision.match_rule,
                    confidence=decision.confidence,
                    evidence=decision.evidence,
                    conflicts=decision.conflicts,
                ),
            )
            match_candidate_id = row.id

        return ResolveFromHintResult(
            person_uid=new_person.id,
            was_new_person=new_person_result.was_created,
            match_candidate_id=match_candidate_id,
            open_candidate=True,
        )

    # --- Re-merge sweep + possible-duplicates surface (design 2026-05-28) ---

    async def sweep_for_merges(
        self,
        tenant_id: TenantId,
        *,
        updated_since: datetime | None = None,
        page_size: int = 500,
    ) -> SweepSummaryOut:
        """Walk persons in the tenant, score identifier-overlap pairs, and
        write MatchCandidate rows (or auto-merge high-confidence pairs).

        ``updated_since`` controls the incremental window: ``None`` = full
        sweep, anything else = persons modified at or after that timestamp.
        ``page_size`` caps memory usage; callers can re-invoke with a later
        ``updated_since`` to advance through a full backfill in chunks.

        Idempotent: pairs with a decided MatchCandidate (accepted /
        auto_accepted / rejected) are skipped. Open candidates are upserted
        rather than duplicated thanks to the partial-unique guard on
        ``person_pair_key`` while ``status='open'``.
        """
        summary = SweepSummaryOut()
        persons = await self._repo.list_persons_for_sweep(
            tenant_id, updated_since=updated_since, limit=page_size
        )
        seen_pairs: set[str] = set()

        for person in persons:
            summary.persons_scanned += 1
            try:
                # Collect every other person sharing at least one identifier.
                others: dict[UUID, Person] = {}
                for ident in person.identifiers:
                    if ident.kind not in {"email", "phone"} or not ident.value:
                        continue
                    shared = await self._repo.find_persons_sharing_identifier(
                        tenant_id, ident.kind, ident.value, person.id
                    )
                    for other in shared:
                        others.setdefault(other.id, other)

                for other in others.values():
                    pair_key = make_person_pair_key(person.id, other.id)
                    if pair_key is None or pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    decided = await self._repo.find_decided_match_for_pair(
                        tenant_id, pair_key
                    )
                    if decided is not None:
                        summary.skipped_already_decided += 1
                        continue

                    summary.pairs_evaluated += 1
                    decision = _evaluate_pair_for_sweep(person, other)
                    if decision.kind == "skip":
                        continue

                    if decision.kind == "auto_accept":
                        survivor, merged = _pick_survivor(person, other)
                        merge_event = await self.record_merge(
                            tenant_id,
                            survivor.id,
                            merged.id,
                            reason="cross_provider_match",
                            evidence={
                                "match_rule": decision.match_rule,
                                "confidence": str(decision.confidence),
                                **decision.evidence,
                            },
                        )
                        await self.add_match_candidate(
                            tenant_id,
                            MatchCandidateIn(
                                source_person_uid=survivor.id,
                                candidate_person_uid=merged.id,
                                accepted_person_uid=survivor.id,
                                status="auto_accepted",
                                match_rule=decision.match_rule,
                                confidence=decision.confidence,
                                evidence=decision.evidence,
                                conflicts=decision.conflicts,
                            ),
                        )
                        # Link the candidate row to the merge_event so the audit
                        # trail flows back to the merge.
                        _ = merge_event  # explicit no-op; FK link is on the
                        # candidate above via accepted_person_uid.
                        summary.auto_merged += 1
                    else:  # "open"
                        # Skip if a row is already open for this pair (race).
                        existing_open = await self._repo.find_open_match_for_pair(
                            tenant_id, pair_key
                        )
                        if existing_open is not None:
                            summary.skipped_already_decided += 1
                            continue
                        await self.add_match_candidate(
                            tenant_id,
                            MatchCandidateIn(
                                source_person_uid=person.id,
                                candidate_person_uid=other.id,
                                status="open",
                                match_rule=decision.match_rule,
                                confidence=decision.confidence,
                                evidence=decision.evidence,
                                conflicts=decision.conflicts,
                            ),
                        )
                        summary.open_candidates_created += 1
            except Exception:  # noqa: BLE001 — sweep ticks must survive one bad row
                summary.persons_errored += 1

        return summary

    async def list_possible_duplicates(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
    ) -> list[PossibleDuplicateOut]:
        """Open MatchCandidate rows where ``person_uid`` is one side of the
        pair. The "other side" is resolved per-row and shipped to the UI
        alongside a thin source-system list."""
        candidates = await self._repo.list_open_candidates_for_person(
            tenant_id, person_uid
        )
        if not candidates:
            return []

        other_ids: list[UUID] = []
        for c in candidates:
            other_uid: UUID | None = (
                c.candidate_person_uid
                if c.source_person_uid == person_uid
                else c.source_person_uid
            )
            if other_uid is not None:
                other_ids.append(other_uid)
        others = await self._repo.list_by_ids(tenant_id, other_ids)
        by_id: dict[UUID, Person] = {p.id: p for p in others}
        providers = await self._repo.list_source_providers_for(tenant_id, other_ids)

        out: list[PossibleDuplicateOut] = []
        for c in candidates:
            this_other: UUID | None = (
                c.candidate_person_uid
                if c.source_person_uid == person_uid
                else c.source_person_uid
            )
            if this_other is None or this_other not in by_id:
                continue
            other_person = by_id[this_other]
            out.append(
                PossibleDuplicateOut(
                    candidate_id=c.id,
                    other_person_uid=this_other,
                    other_display_name=other_person.display_name,
                    other_source_systems=providers.get(this_other, []),
                    match_rule=c.match_rule,
                    confidence=c.confidence,
                    evidence=dict(c.evidence or {}),
                    conflicts=dict(c.conflicts or {}),
                    created_at=c.created_at,
                )
            )
        return out

    async def accept_match_candidate(
        self,
        tenant_id: TenantId,
        candidate_id: UUID,
        *,
        performed_by_actor_id: UUID | None = None,
    ) -> MergeEvent:
        """Manually accept an open MatchCandidate.

        Survivor is picked deterministically (older created_at wins, ties by
        smaller UUID) so re-clicks resolve the same way. The MatchCandidate
        moves to ``accepted`` with ``accepted_person_uid`` set to the
        survivor and ``merge_event_id`` filled in.
        """
        candidate = await self._repo.get_match_candidate(tenant_id, candidate_id)
        if candidate is None:
            raise NotFoundError(
                "match_candidate not found",
                details={"candidate_id": str(candidate_id)},
            )
        if candidate.status != "open":
            raise ValidationError(
                "match_candidate is not open",
                details={
                    "candidate_id": str(candidate_id),
                    "status": candidate.status,
                },
            )
        if candidate.source_person_uid is None or candidate.candidate_person_uid is None:
            raise ValidationError(
                "match_candidate is missing one side of the pair",
                details={"candidate_id": str(candidate_id)},
            )

        persons = await self._repo.list_by_ids(
            tenant_id,
            [candidate.source_person_uid, candidate.candidate_person_uid],
        )
        if len(persons) != 2:
            raise NotFoundError(
                "one or both persons in the candidate were not found",
                details={"candidate_id": str(candidate_id)},
            )
        a, b = persons[0], persons[1]
        survivor, merged = _pick_survivor(a, b)

        merge_event = await self.record_merge(
            tenant_id,
            survivor.id,
            merged.id,
            reason="cross_provider_match",
            evidence={
                "match_rule": candidate.match_rule,
                "candidate_id": str(candidate.id),
                "accepted_by_actor": (
                    str(performed_by_actor_id) if performed_by_actor_id else None
                ),
            },
            performed_by_actor_id=performed_by_actor_id,
        )
        await self._repo.update_match_candidate_status(
            tenant_id,
            candidate.id,
            status="accepted",
            accepted_person_uid=survivor.id,
            decided_at=datetime.now(UTC),
            decided_by_actor_id=performed_by_actor_id,
            merge_event_id=merge_event.id,
        )
        return merge_event

    async def reject_match_candidate(
        self,
        tenant_id: TenantId,
        candidate_id: UUID,
        *,
        performed_by_actor_id: UUID | None = None,
    ) -> MatchCandidate:
        """Reject an open MatchCandidate. The sweep will not propose this
        pair again."""
        candidate = await self._repo.get_match_candidate(tenant_id, candidate_id)
        if candidate is None:
            raise NotFoundError(
                "match_candidate not found",
                details={"candidate_id": str(candidate_id)},
            )
        if candidate.status != "open":
            raise ValidationError(
                "match_candidate is not open",
                details={
                    "candidate_id": str(candidate_id),
                    "status": candidate.status,
                },
            )
        await self._repo.update_match_candidate_status(
            tenant_id,
            candidate.id,
            status="rejected",
            accepted_person_uid=None,
            decided_at=datetime.now(UTC),
            decided_by_actor_id=performed_by_actor_id,
        )
        refreshed = await self._repo.get_match_candidate(tenant_id, candidate.id)
        if refreshed is None:
            raise NotFoundError(
                "match_candidate not found after reject",
                details={"candidate_id": str(candidate_id)},
            )
        return refreshed

    # --- Replay open candidates under the current policy (ENG-544) ---

    async def count_open_match_candidates(self, tenant_id: TenantId) -> int:
        """Total ``status='open'`` candidates — the replay work-list size."""
        return await self._repo.count_open_match_candidates(tenant_id)

    async def list_open_match_candidates(
        self,
        tenant_id: TenantId,
        *,
        after_id: UUID | None = None,
        limit: int = 500,
    ) -> list[MatchCandidateOut]:
        """Page through open candidates by ``id`` cursor (ENG-544 replay).

        Returns DTOs so the worker job never touches an ORM row. Pass the
        last returned ``id`` as ``after_id`` to fetch the next page.
        """
        rows = await self._repo.list_open_match_candidates_after(
            tenant_id, after_id=after_id, limit=limit
        )
        return [MatchCandidateOut.model_validate(row) for row in rows]

    async def list_open_reuse_candidates_created_after(
        self,
        tenant_id: TenantId,
        after: datetime,
        *,
        after_created_at: datetime | None = None,
        after_id: UUID | None = None,
        limit: int = 500,
    ) -> list[MatchCandidateOut]:
        """Open shared-contact-reuse candidates created at/after ``after``.

        The signal source for the ENG-555 Messenger alert (Layer D): each row
        is an OPEN ``match_candidate`` with a Tier-2 ambiguous phone/email rule
        — an incoming record reused a shared contact already held by an existing
        person. ``source_person_uid`` is the incoming person, ``candidate_person_uid``
        the existing one. ``after`` is the no-retro cutoff so the pre-existing
        open backlog is never returned. Returns DTOs so the worker job never
        touches an ORM row.

        Keyset-paginated on ``(created_at, id)``: pass the last row's
        ``(created_at, id)`` as ``after_created_at`` / ``after_id`` to page
        forward so the scan visits every post-cutoff open candidate, not just
        the first ``limit`` (ENG-555 Codex review — anti-starvation).
        """
        rows = await self._repo.list_open_reuse_candidates_created_after(
            tenant_id,
            after,
            after_created_at=after_created_at,
            after_id=after_id,
            limit=limit,
        )
        return [MatchCandidateOut.model_validate(row) for row in rows]

    async def replay_open_match_candidate(
        self,
        tenant_id: TenantId,
        candidate: MatchCandidateOut,
        *,
        apply: bool = False,
        performed_by_actor_id: UUID | None = None,
    ) -> MatchReplayDecisionOut:
        """Re-evaluate ONE open candidate under the CURRENT match policy.

        Reconstructs the original ingest hint from the recorded pair and runs
        the SAME :func:`_evaluate_match_policy` the live resolver uses — no
        re-implemented matching. The source person (the lead duplicate) usually
        dropped the shared phone/email under the ENG-340 shared-contact guard,
        so the shared identifier is read back off the candidate person; the
        source person's own (free) identifiers ride along for the other kind so
        the ambiguity count stays faithful.

        ``apply=False`` (default) mutates NOTHING — pure classification. With
        ``apply=True`` a ``would_merge`` decision records the append-only merge
        + moves the merged person's source links onto the survivor + marks the
        candidate ``accepted``. Moving ``ops.lead`` rows is cross-domain and is
        the caller's job (the returned survivor/merged uids drive it).
        """
        src_uid = candidate.source_person_uid
        cand_uid = candidate.candidate_person_uid
        if src_uid is None:
            return MatchReplayDecisionOut(
                candidate_id=candidate.id,
                source_person_uid=None,
                candidate_person_uid=cand_uid,
                outcome="skipped",
                detail="missing_source_person",
            )

        persons = await self._repo.list_by_ids(tenant_id, [src_uid, cand_uid])
        by_id = {p.id: p for p in persons}
        source = by_id.get(src_uid)
        cand = by_id.get(cand_uid)
        if source is None or cand is None:
            return MatchReplayDecisionOut(
                candidate_id=candidate.id,
                source_person_uid=src_uid,
                candidate_person_uid=cand_uid,
                outcome="skipped",
                detail="missing_person",
            )

        rule = candidate.match_rule
        phone_shared = "phone" in rule
        email_shared = "email" in rule
        src_phones = sorted(_person_identifier_values(source, "phone"))
        src_emails = sorted(_person_identifier_values(source, "email"))
        cand_phones = sorted(_person_identifier_values(cand, "phone"))
        cand_emails = sorted(_person_identifier_values(cand, "email"))

        # Shared identifier comes off the candidate person (the lead dropped
        # it); the non-shared kind keeps the source's own free value, if any.
        hint_phone = (
            (cand_phones[0] if cand_phones else (src_phones[0] if src_phones else None))
            if phone_shared
            else (src_phones[0] if src_phones else None)
        )
        hint_email = (
            (cand_emails[0] if cand_emails else (src_emails[0] if src_emails else None))
            if email_shared
            else (src_emails[0] if src_emails else None)
        )

        hint = MatchHintIn(
            source_system="replay",
            source_kind="replay",
            source_id=str(source.id),
            given_name=source.given_name,
            family_name=source.family_name,
            display_name=source.display_name,
            email_normalized=hint_email,
            phone_normalized=hint_phone,
            dob=source.dob,
            ssn=source.ssn,
        )

        candidates = await self._repo.list_candidate_persons_by_identifiers(
            tenant_id, hint_email, hint_phone
        )
        candidates = [c for c in candidates if c.id != source.id]
        decision = _evaluate_match_policy(hint, candidates)

        base: dict[str, object] = {
            "candidate_id": candidate.id,
            "source_person_uid": source.id,
            "candidate_person_uid": cand.id,
        }

        if isinstance(decision, _AutoAccept) and decision.person.id == cand.id:
            merge_reason = await self._replay_merge_reason(
                tenant_id, source.id, cand.id, phone_shared
            )
            if apply and await self._repo.is_person_retired(tenant_id, source.id):
                # Idempotency guard (ENG-544 fix): the source person was already
                # retired by a prior merge — another open candidate for the same
                # tombstone earlier in this pass, or a previous replay run.
                # Re-merging it into a second survivor would be a double-merge,
                # so skip instead. Makes the live pass safely re-runnable.
                return MatchReplayDecisionOut(
                    **base,
                    outcome="skipped",
                    detail="source_already_retired",
                    match_rule=decision.match_rule,
                    merge_reason=merge_reason,
                    survivor_person_uid=cand.id,
                    merged_person_uid=source.id,
                    applied=False,
                )
            applied = False
            if apply:
                await self._apply_replay_merge(
                    tenant_id,
                    candidate=candidate,
                    survivor=cand,
                    merged=source,
                    reason=merge_reason,
                    match_rule=decision.match_rule,
                    confidence=decision.confidence,
                    performed_by_actor_id=performed_by_actor_id,
                )
                applied = True
            return MatchReplayDecisionOut(
                **base,
                outcome="would_merge",
                detail="single_tier1_auto_accept",
                match_rule=decision.match_rule,
                merge_reason=merge_reason,
                survivor_person_uid=cand.id,
                merged_person_uid=source.id,
                applied=applied,
            )

        if isinstance(decision, _AutoAccept):
            # A single Tier-1 accept, but to a DIFFERENT person than the
            # recorded pair. Out of scope for this pair — leave it for the
            # sweep / operator rather than merge somewhere unexpected.
            return MatchReplayDecisionOut(
                **base,
                outcome="stay_open",
                detail="auto_accept_to_other_person",
                match_rule=decision.match_rule,
            )

        if isinstance(decision, _OpenAmbiguous):
            return MatchReplayDecisionOut(
                **base,
                outcome="stay_open",
                detail=f"ambiguous_{decision.match_rule}",
                match_rule=decision.match_rule,
            )

        # _NewPerson — the identifier is gone, a person is missing, or an
        # ENG-309 DOB/SSN hard veto fired; nothing to merge.
        return MatchReplayDecisionOut(
            **base,
            outcome="skipped",
            detail="no_current_match",
        )

    async def _replay_merge_reason(
        self,
        tenant_id: TenantId,
        person_a: UUID,
        person_b: UUID,
        phone_shared: bool,
    ) -> str:
        """Pick an append-only ``merge_event.reason`` for a replay merge.

        Different originating providers → ``cross_provider_match`` (the
        Salesforce-lead vs CareStack-patient case). Same provider → a plain
        duplicate keyed by whichever identifier drove the match.
        """
        providers = await self._repo.list_source_providers_for(
            tenant_id, [person_a, person_b]
        )
        a_sys = set(providers.get(person_a, []))
        b_sys = set(providers.get(person_b, []))
        if a_sys and b_sys and a_sys.isdisjoint(b_sys):
            return "cross_provider_match"
        return "duplicate_phone" if phone_shared else "duplicate_email"

    async def _apply_replay_merge(
        self,
        tenant_id: TenantId,
        *,
        candidate: MatchCandidateOut,
        survivor: Person,
        merged: Person,
        reason: str,
        match_rule: str,
        confidence: Decimal,
        performed_by_actor_id: UUID | None,
    ) -> MergeEvent:
        """Identity-side of a replay merge (live mode only).

        Append-only + reversible: records the ``merge_event``, re-points the
        merged person's source links at the survivor, and decides the open
        candidate as ``accepted`` with the merge_event linked. The merged
        person row is never deleted. The caller moves ``ops.lead`` rows.
        """
        merge_event = await self.record_merge(
            tenant_id,
            survivor.id,
            merged.id,
            reason=reason,
            evidence={
                "match_rule": match_rule,
                "confidence": str(confidence),
                "candidate_id": str(candidate.id),
                "replay": True,
            },
            performed_by_actor_id=performed_by_actor_id,
        )
        await self._repo.reassign_source_links(tenant_id, merged.id, survivor.id)
        await self._repo.update_match_candidate_status(
            tenant_id,
            candidate.id,
            status="accepted",
            accepted_person_uid=survivor.id,
            decided_at=datetime.now(UTC),
            decided_by_actor_id=performed_by_actor_id,
            merge_event_id=merge_event.id,
        )
        return merge_event


@dataclass(frozen=True)
class _SweepDecision:
    """Internal: outcome of evaluating one (a, b) person pair during a sweep.

    ``kind`` is one of ``"auto_accept"`` / ``"open"`` / ``"skip"``.
    """

    kind: str
    match_rule: str
    confidence: Decimal
    evidence: dict[str, object]
    conflicts: dict[str, object]


def _linkage_example_from_raw(raw: dict[str, object]) -> SourceLinkageExampleOut:
    has_salesforce = bool(raw.get("has_salesforce"))
    has_carestack = bool(raw.get("has_carestack"))
    if has_salesforce and has_carestack:
        linkage_status = "linked_salesforce_carestack"
    elif has_salesforce:
        linkage_status = "salesforce_only"
    else:
        linkage_status = "carestack_only"

    source_systems = []
    if has_salesforce:
        source_systems.append("salesforce")
    if has_carestack:
        source_systems.append("carestack")

    return SourceLinkageExampleOut(
        person_uid_masked=_mask_identifier(raw.get("person_uid")),
        linkage_status=linkage_status,
        source_systems=source_systems,
        salesforce_source_id_masked=_mask_optional_identifier(
            raw.get("salesforce_source_id")
        ),
        carestack_source_id_masked=_mask_optional_identifier(
            raw.get("carestack_source_id")
        ),
    )


def _mask_optional_identifier(value: object) -> str | None:
    if value is None:
        return None
    return _mask_identifier(value)


def _mask_identifier(value: object) -> str:
    text = str(value)
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}...{text[-4:]}"


def _evaluate_pair_for_sweep(a: Person, b: Person) -> _SweepDecision:
    """Score a person-to-person pair using the same rules as the ingest tier
    evaluator. Returns a ``_SweepDecision`` describing what to write.

    Identifier-overlap is the entry condition (callers only pass pairs that
    share at least one identifier), so the absence of overlap collapses to
    ``"skip"`` — nothing actionable.
    """
    # Canonical match keys (ENG-562): intersect on the same key the repository
    # surfaced the pair by, so a cross-format phone overlap is not lost here.
    a_emails = _person_identifier_match_keys(a, "email")
    a_phones = _person_identifier_match_keys(a, "phone")
    b_emails = _person_identifier_match_keys(b, "email")
    b_phones = _person_identifier_match_keys(b, "phone")

    common_emails = a_emails & b_emails
    common_phones = a_phones & b_phones
    has_email = bool(common_emails)
    has_phone = bool(common_phones)

    if not (has_email or has_phone):
        return _SweepDecision(
            kind="skip", match_rule="no_overlap", confidence=Decimal("0"),
            evidence={}, conflicts={},
        )

    # Reuse the existing name-compat helper via a synthetic hint built from
    # the actual overlapping identifiers. ``source_system``/``source_kind``/
    # ``source_id`` are placeholder values — _names_compatible only reads the
    # name fields.
    synthetic_hint = MatchHintIn(
        source_system="sweep",
        source_kind="sweep",
        source_id=str(a.id),
        given_name=a.given_name,
        family_name=a.family_name,
        display_name=a.display_name,
        email_normalized=next(iter(common_emails), None),
        phone_normalized=next(iter(common_phones), None),
    )
    names_ok = _names_compatible(synthetic_hint, b)

    if has_email and has_phone and names_ok:
        return _SweepDecision(
            kind="auto_accept",
            match_rule="email_phone_name",
            confidence=_AUTO_ACCEPT_EMAIL_PHONE_NAME,
            evidence={"email_match": True, "phone_match": True, "name_compatible": True},
            conflicts={},
        )
    if has_phone and names_ok:
        return _SweepDecision(
            kind="auto_accept",
            match_rule="phone_name",
            confidence=_AUTO_ACCEPT_PHONE_NAME,
            evidence={"phone_match": True, "name_compatible": True},
            conflicts={},
        )
    if has_email and names_ok:
        return _SweepDecision(
            kind="auto_accept",
            match_rule="email_name",
            confidence=_AUTO_ACCEPT_EMAIL_NAME,
            evidence={"email_match": True, "name_compatible": True},
            conflicts={},
        )
    # Identifier-overlap without name compatibility — surface as ambiguous so
    # an operator can adjudicate.
    rule = "email_only_ambiguous" if has_email and not has_phone else "phone_only_ambiguous"
    return _SweepDecision(
        kind="open",
        match_rule=rule,
        confidence=_OPEN_AMBIGUOUS_FLOOR,
        evidence={
            "email_match": has_email,
            "phone_match": has_phone,
            "name_compatible": False,
        },
        conflicts={"name_compatible": False},
    )


def _pick_survivor(a: Person, b: Person) -> tuple[Person, Person]:
    """Return (survivor, merged). Older created_at wins; ties by smaller UUID.

    Deterministic so the same pair survives the same way across reruns. The
    survivor is the row whose ``person_uid`` future references will resolve to.
    """
    if a.created_at == b.created_at:
        # UUID comparison is lexicographic on bytes — stable enough.
        return (a, b) if str(a.id) <= str(b.id) else (b, a)
    return (a, b) if a.created_at < b.created_at else (b, a)


@dataclass(frozen=True)
class ResolveResult:
    """Output of :meth:`IdentityService.resolve_or_create_person`.

    ``was_created`` distinguishes "first observation of this external record"
    from "we had it already, we just bumped last_seen_at". Workers use this
    to decide whether to emit a ``person_created`` interaction event vs no
    event (re-pull saw the same record).
    """

    person: Person
    was_created: bool


# Convenience cast helper used by the API/tools layer.
def as_person_uid(value: UUID) -> PersonUID:
    return PersonUID(value)
