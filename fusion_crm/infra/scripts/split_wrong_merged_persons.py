"""Un-merge wrong-merged CareStack persons (ENG-311).

ENG-309 (merged) stopped NEW household-merges via a DOB/SSN hard veto
in :class:`packages.identity.service.IdentityService`. This companion
script cleans the EXISTING population of wrong-merged persons the old
resolver produced -- whole households (parents + children sharing a
phone/email/address/CareStack ``accountId``) collapsed into one
``identity.person.id`` so financial aggregates sum across distinct
humans.

For each ``identity.person`` row that has multiple linked CareStack
patient_ids disagreeing on DOB or SSN, this script groups the pids by
``(dob, ssn)`` and splits the merged person into one Person per bucket:

* Largest bucket stays on the original ``person.id``. Tie-break: the
  bucket containing the lexicographically smallest patient_id stays
  (deterministic across re-runs).
* Each other bucket spawns a new ``Person`` row (clone of the demographic
  fields, dob+ssn from the bucket); its ``identity.source_link`` rows
  are repointed to the new ``person_uid``.

Downstream per-table repoint decisions (Round 2 — adversarial-review
fix). The principle is unchanged: repoint only on an unambiguous
patient_id trace; never guess; count the rest as ``needs_manual_review``.

============================== ============= ============================
table                          repointed?    why
============================== ============= ============================
``identity.source_link``        YES          ``source_id`` IS the
                                             CareStack patient_id.
                                             Direct trace.
``interaction.event`` (rows     YES          ``source_external_id`` IS
``source_kind='patient'``)                   the patient_id. Direct
                                             trace.
``ops.consultation`` (rows      YES (NEW)    ``raw_event_id`` joins
``source_provider='carestack'`` Round 2      ``ingest.raw_event`` where
and ``raw_event_id`` IS NOT                  ``payload->>'patientId'`` is
NULL)                                        the appointment's CareStack
                                             patient_id. Same kind of
                                             clean trace as the two
                                             rows above.
``ops.lead``                    NO           Salesforce-origin object,
                                             usually predates the
                                             CareStack patient pull. No
                                             ``patient_id`` column, no
                                             provider-traceable join.
                                             STAYS on the surviving
                                             person + counted in
                                             ``needs_manual_review``.
``ops.followup_task``           NO           No ``source_provider``,
                                             ``external_id``, or
                                             ``raw_event_id``. No clean
                                             trace from a task back to
                                             a specific CareStack
                                             patient_id. STAYS on the
                                             surviving person + counted
                                             in ``needs_manual_review``.
``ops.person_location_profile`` NO           Aggregate row (one per
                                             ``(tenant, person,
                                             location)`` UNIQUE) that
                                             stores only the LATEST
                                             evidence. The trace is
                                             clean for the row but
                                             moving the row would
                                             orphan the surviving
                                             person's profile at that
                                             location. Operator must
                                             regenerate from CareStack
                                             after the split. STAYS +
                                             counted in
                                             ``needs_manual_review``.
``interaction.event`` (rows     NO           Tasks / non-patient events
``source_provider='carestack'`` ed.          with no patient_id trace.
``source_kind != 'patient'``)                STAYS + counted in
                                             ``needs_manual_review``.
``ops.consultation`` (rows      NO           Defensive bucket: rows
``raw_event_id IS NULL``)                    without a raw_event trace
                                             cannot be attributed.
                                             STAYS + counted in
                                             ``needs_manual_review``.
============================== ============= ============================

Per-person SAVEPOINT. Each candidate person's split runs inside
``async with session.begin_nested():`` so that one failing person rolls
back ONLY that person's writes and the outer ``commit_every`` batch
keeps the prior successes. The per-person failure is logged at warning
with count + uuid only (no PHI) and an ``error_count`` is surfaced in
the run summary.

* Per-split audit row at ``audit.access_log`` with
  ``action='identity.person.split'``. ``extra`` carries ONLY uuids and
  counts -- never dob, ssn, name, or patient_id values.

PersonIdentifier rows (phone / email / external ids) STAY on the
surviving person. The ``(kind, value)`` unique constraint prevents
copying them to two persons; ENG-309's DOB/SSN veto in
``resolve_or_create_from_hint`` is the forward-going guard against
re-merge when CareStack re-pulls a non-surviving patient.

The script is background-only and is NOT wired to HTTP. ``--apply`` is
the only path that writes; ``--dry-run`` is the default and prints the
plan to stdout.

CLI::

    python3 infra/scripts/split_wrong_merged_persons.py \\
        --tenant-id <uuid> \\
        [--apply]                   # default is --dry-run
        [--max-splits 100]
        [--person-uid <uuid>]       # single-target verification
        [--commit-every 50]

Exit codes:
    0  success
    2  invalid tenant / missing required input
    1  uncaught exception (logged before propagation by ``run``)

PHI handling: structured logs carry ONLY counts and uuids. The dry-run
plan printed to stdout carries patient_ids (operator-only CareStack
references) and bucket sizes, but never dob / ssn / name values.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text

from packages.audit.models import AccessLog
from packages.core.logging import configure_logging, get_logger
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.identity.models import Person

log = get_logger("infra.split_wrong_merged_persons")

_DEFAULT_MAX_SPLITS = 100
_DEFAULT_COMMIT_EVERY = 50

_SSN_STRIP = re.compile(r"[\s\-]+")


def _normalise_ssn(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = _SSN_STRIP.sub("", value).strip()
    return cleaned or None


def _default_session_factory() -> Any:
    from packages.db.session import async_session

    return async_session()


# Mirrors ``infra/scripts/audit_identity_merges.py::_AUDIT_SQL`` with an
# additional aggregation of the latest payload's name fields. The split
# script reuses the same selection so the two stay in lock-step.
_AUDIT_SQL = text(
    """
    WITH latest_payload AS (
        SELECT DISTINCT ON (sl.tenant_id, sl.source_id)
            sl.tenant_id,
            sl.person_uid,
            sl.source_id        AS patient_id,
            re.payload          AS payload,
            re.received_at      AS received_at
        FROM identity.source_link AS sl
        JOIN ingest.raw_event   AS re
          ON re.tenant_id   = sl.tenant_id
         AND re.external_id = sl.source_id
         AND re.event_type  = 'carestack.patient.upsert'
        WHERE sl.tenant_id     = :tenant_id
          AND sl.source_system = 'carestack'
          AND sl.source_kind   = 'patient'
          AND sl.source_id IS NOT NULL
        ORDER BY sl.tenant_id, sl.source_id, re.received_at DESC
    )
    SELECT
        person_uid,
        ARRAY_AGG(patient_id ORDER BY patient_id)                          AS patient_ids,
        ARRAY_AGG(payload->>'dob'  ORDER BY patient_id)                    AS dobs,
        ARRAY_AGG(payload->>'ssn'  ORDER BY patient_id)                    AS ssns,
        ARRAY_AGG(payload->>'firstName' ORDER BY patient_id)               AS first_names,
        ARRAY_AGG(payload->>'lastName'  ORDER BY patient_id)               AS last_names
    FROM latest_payload
    GROUP BY person_uid
    HAVING COUNT(*) > 1
    """
)


# Repoint queries. ``person_uid`` is a plain mutable UUID column on every
# table we touch -- documented as such in ``packages/identity/CLAUDE.md``
# (source_link) and ``packages/interaction/CLAUDE.md`` (event). Direct
# UPDATEs are the established mechanic for this kind of identity-housekeeping
# work; no service wrapper exists.
_REPOINT_SOURCE_LINK_SQL = text(
    """
    UPDATE identity.source_link
       SET person_uid = :new_person_uid
     WHERE tenant_id = :tenant_id
       AND source_system = 'carestack'
       AND source_kind = 'patient'
       AND source_id = ANY(:patient_ids)
    """
)

_REPOINT_INTERACTION_EVENT_SQL = text(
    """
    UPDATE interaction.event
       SET person_uid = :new_person_uid
     WHERE tenant_id = :tenant_id
       AND person_uid = :surviving_person_uid
       AND source_provider = 'carestack'
       AND source_kind = 'patient'
       AND source_external_id = ANY(:patient_ids)
    """
)

# Repoint CareStack-derived ``ops.consultation`` rows via the
# ``raw_event_id`` join. Each consultation captured by the appointment
# ingest stores ``raw_event_id`` pointing at the ``carestack.appointment.upsert``
# raw event whose payload carries ``patientId`` (camelCase per CareStack
# sync feed; ``PatientId`` PascalCase is also tolerated by the appointment
# ingest, so we accept both). This is the same kind of clean trace as
# ``interaction.event``'s ``source_external_id``. See the module-level
# per-table table.
_REPOINT_OPS_CONSULTATION_SQL = text(
    """
    UPDATE ops.consultation AS c
       SET person_uid = :new_person_uid
     WHERE c.tenant_id = :tenant_id
       AND c.person_uid = :surviving_person_uid
       AND c.source_provider = 'carestack'
       AND c.raw_event_id IS NOT NULL
       AND EXISTS (
           SELECT 1 FROM ingest.raw_event AS re
            WHERE re.id = c.raw_event_id
              AND re.tenant_id = c.tenant_id
              AND re.event_type = 'carestack.appointment.upsert'
              AND COALESCE(re.payload->>'patientId', re.payload->>'PatientId')
                  = ANY(:patient_ids)
       )
    """
)

# Count of rows that STAY on the surviving person but lack a clean
# patient_id trace (or are aggregate / non-traceable by design). These
# drive a ``needs_manual_review`` counter the operator inspects after
# each batch.
#
# Round 2 (adversarial-review fix): ``ops.consultation`` rows with a
# raw_event trace are no longer counted -- they are repointed by
# ``_REPOINT_OPS_CONSULTATION_SQL`` above. We DO still count any
# ``ops.consultation`` row whose ``raw_event_id IS NULL`` (rare; should
# only happen if the consultation was created outside the appointment
# ingest), plus ``ops.lead`` (no patient_id trace),
# ``ops.followup_task`` (no source columns), and
# ``ops.person_location_profile`` (aggregate row -- moving it would
# orphan the surviving person's profile at the same location).
#
# PHI-safe: the query returns one integer.
_COUNT_NEEDS_MANUAL_REVIEW_SQL = text(
    """
    SELECT
        (SELECT COUNT(*) FROM ops.consultation
          WHERE tenant_id = :tenant_id
            AND person_uid = :surviving_person_uid
            AND source_provider = 'carestack'
            AND raw_event_id IS NULL)
      + (SELECT COUNT(*) FROM ops.lead
          WHERE tenant_id = :tenant_id
            AND person_uid = :surviving_person_uid)
      + (SELECT COUNT(*) FROM interaction.event
          WHERE tenant_id = :tenant_id
            AND person_uid = :surviving_person_uid
            AND source_provider = 'carestack'
            AND (source_kind IS NULL OR source_kind <> 'patient'))
      + (SELECT COUNT(*) FROM ops.person_location_profile
          WHERE tenant_id = :tenant_id
            AND person_uid = :surviving_person_uid
            AND last_evidence_provider = 'carestack')
      + (SELECT COUNT(*) FROM ops.followup_task
          WHERE tenant_id = :tenant_id
            AND person_uid = :surviving_person_uid)
      AS needs_manual_review
    """
)


@dataclass(frozen=True)
class _PidInfo:
    """Per-pid (dob, ssn, name) snapshot taken from the latest CS payload."""

    patient_id: str
    dob: str | None
    ssn: str | None
    given_name: str | None
    family_name: str | None


@dataclass(frozen=True)
class _Bucket:
    """A ``(dob, ssn)``-coherent group of pids belonging to a single human."""

    key: tuple[str | None, str | None]
    pids: list[_PidInfo] = field(default_factory=list)


@dataclass(frozen=True)
class _Candidate:
    """One wrong-merged ``identity.person`` row + its linked pids."""

    person_uid: uuid.UUID
    pids: list[_PidInfo]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Split wrong-merged CareStack persons into one Person per "
            "(dob, ssn) bucket (ENG-311 un-merge)."
        ),
    )
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help=(
            "Default. Print the per-person split plan to stdout; do NOT "
            "write to the database. ``--apply`` overrides."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help=(
            "Explicit opt-in to write. The only path that creates new "
            "Person rows, repoints source_link, and writes audit rows."
        ),
    )
    parser.add_argument(
        "--max-splits",
        type=int,
        default=_DEFAULT_MAX_SPLITS,
        help=(
            "Maximum wrong-merged persons processed in this run (default "
            "100). The real fleet split runs in batches under operator "
            "supervision."
        ),
    )
    parser.add_argument(
        "--person-uid",
        default=None,
        help=(
            "If set, restrict selection to this single ``identity.person.id``. "
            "Use it for Torosyan-shape verification before fleet apply."
        ),
    )
    parser.add_argument(
        "--commit-every",
        type=int,
        default=_DEFAULT_COMMIT_EVERY,
        help="Flush the DB unit-of-work every N persons (default 50).",
    )
    return parser.parse_args(argv)


def _normalise_dob(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _build_candidate(mapping: Any) -> _Candidate | None:
    raw_pids = list(mapping["patient_ids"] or [])
    if not raw_pids:
        return None
    dobs = list(mapping.get("dobs") or [])
    ssns_raw = list(mapping.get("ssns") or [])
    first_names = list(mapping.get("first_names") or [])
    last_names = list(mapping.get("last_names") or [])

    def _at(lst: list[Any], i: int) -> Any:
        return lst[i] if i < len(lst) else None

    person_uid = mapping["person_uid"]
    if isinstance(person_uid, str):
        person_uid = uuid.UUID(person_uid)

    pinfos = [
        _PidInfo(
            patient_id=str(raw_pids[i]),
            dob=_normalise_dob(_at(dobs, i)),
            ssn=_normalise_ssn(_at(ssns_raw, i)),
            given_name=_at(first_names, i),
            family_name=_at(last_names, i),
        )
        for i in range(len(raw_pids))
    ]
    return _Candidate(person_uid=person_uid, pids=pinfos)


def _is_mismatch(candidate: _Candidate) -> bool:
    """Mirrors the ENG-309 veto + ``audit_identity_merges.py`` predicate.

    A merged person is wrong-merged when its linked pids have more than
    one distinct non-null DOB OR more than one distinct non-null SSN. A
    pid with missing dob/ssn does not by itself count as a mismatch (the
    veto only fires when BOTH sides have a value).
    """
    distinct_dob = len({p.dob for p in candidate.pids if p.dob is not None})
    distinct_ssn = len({p.ssn for p in candidate.pids if p.ssn is not None})
    return distinct_dob > 1 or distinct_ssn > 1


def _bucket_pids(pids: list[_PidInfo]) -> list[_Bucket]:
    """Group pids by ``(dob, ssn)`` per the partial-null precedence rule.

    Rules:

    1. Pids with the same ``(dob, ssn)`` always share a bucket.
    2. A pid with dob set + ssn null joins a bucket sharing that dob iff
       exactly one such bucket has a non-null ssn for that dob (e.g.
       Gaiane registered twice -- once with SSN, once without).
       Symmetric for (None, ssn).
    3. NEVER merge two pids with different non-null dobs. The bucket
       structure preserves the ENG-309 veto invariant.
    4. ``(None, None)`` pids stay in their own bucket (we have no
       evidence to attach them to anyone else's bucket).
    """
    # Step 1 -- raw grouping by (dob, ssn).
    raw: dict[tuple[str | None, str | None], list[_PidInfo]] = {}
    for p in pids:
        key = (p.dob, p.ssn)
        raw.setdefault(key, []).append(p)

    # Step 2 -- partial-null merge.
    by_dob: dict[str, set[str | None]] = {}
    by_ssn: dict[str, set[str | None]] = {}
    for dob, ssn in raw:
        if dob is not None:
            by_dob.setdefault(dob, set()).add(ssn)
        if ssn is not None:
            by_ssn.setdefault(ssn, set()).add(dob)

    merged: dict[tuple[str | None, str | None], list[_PidInfo]] = {}
    for (dob, ssn), items in raw.items():
        # (dob, None) merges into (dob, X) if exactly one non-null X exists.
        if dob is not None and ssn is None and dob in by_dob:
            non_null = [s for s in by_dob[dob] if s is not None]
            if len(non_null) == 1:
                merged.setdefault((dob, non_null[0]), []).extend(items)
                continue
        # (None, ssn) merges into (Y, ssn) if exactly one non-null Y exists.
        if ssn is not None and dob is None and ssn in by_ssn:
            non_null = [d for d in by_ssn[ssn] if d is not None]
            if len(non_null) == 1:
                merged.setdefault((non_null[0], ssn), []).extend(items)
                continue
        merged.setdefault((dob, ssn), []).extend(items)

    return [_Bucket(key=k, pids=v) for k, v in merged.items()]


def _pick_surviving(buckets: list[_Bucket]) -> _Bucket:
    """Largest bucket wins. Tie-break: smallest patient_id (lexicographic)."""

    def _sort_key(bucket: _Bucket) -> tuple[int, str]:
        smallest_pid = min(p.patient_id for p in bucket.pids)
        return (-len(bucket.pids), smallest_pid)

    return sorted(buckets, key=_sort_key)[0]


def _format_plan(candidate: _Candidate, buckets: list[_Bucket]) -> str:
    """Operator-facing dry-run output. patient_ids only -- no dob/ssn/name."""
    surviving = _pick_surviving(buckets)
    non_surviving = [b for b in buckets if b is not surviving]
    parts = [
        f"person_uid={candidate.person_uid}",
        f"buckets={len(buckets)}",
        "surviving_pids=" + str(sorted(p.patient_id for p in surviving.pids)),
        f"new_persons={len(non_surviving)}",
    ]
    for idx, bucket in enumerate(non_surviving):
        parts.append(
            f"new[{idx}]_pids=" + str(sorted(p.patient_id for p in bucket.pids))
        )
    return " ".join(parts) + "\n"


def _split_principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"actor": "system:split_wrong_merged_persons"},
    )


async def _select_candidates(
    session: Any,
    tenant_id: TenantId,
    *,
    person_uid_filter: uuid.UUID | None,
) -> list[_Candidate]:
    rows = (await session.execute(_AUDIT_SQL, {"tenant_id": str(tenant_id)})).all()
    out: list[_Candidate] = []
    for row in rows:
        mapping = row._mapping if hasattr(row, "_mapping") else row
        candidate = _build_candidate(mapping)
        if candidate is None:
            continue
        if person_uid_filter is not None and candidate.person_uid != person_uid_filter:
            continue
        if not _is_mismatch(candidate):
            continue
        out.append(candidate)
    return out


async def _create_new_person(
    session: Any,
    *,
    tenant_id: TenantId,
    bucket: _Bucket,
) -> Person:
    """Create a Person row for one non-surviving bucket.

    Demographic fields are cloned from the first pid in the bucket. SSN
    is already digit-only-normalised by ``_normalise_ssn``; DOB is parsed
    from ISO-8601 (``payload->>'dob'`` is a date string in CareStack).
    """
    rep = bucket.pids[0]
    given = rep.given_name
    family = rep.family_name
    display = " ".join(p for p in (given, family) if p) or None
    person = Person(
        tenant_id=tenant_id,
        given_name=given,
        family_name=family,
        display_name=display,
        dob=_parse_iso_date(bucket.key[0]),
        ssn=bucket.key[1],
    )
    session.add(person)
    # Force a flush so ``person.id`` is populated by the database default
    # before downstream UPDATEs reference it.
    await session.flush()
    return person


async def _repoint_source_links(
    session: Any,
    *,
    tenant_id: TenantId,
    patient_ids: list[str],
    new_person_uid: uuid.UUID,
) -> int:
    result = await session.execute(
        _REPOINT_SOURCE_LINK_SQL,
        {
            "tenant_id": str(tenant_id),
            "new_person_uid": str(new_person_uid),
            "patient_ids": patient_ids,
        },
    )
    return int(getattr(result, "rowcount", 0) or 0)


async def _repoint_interaction_events(
    session: Any,
    *,
    tenant_id: TenantId,
    surviving_person_uid: uuid.UUID,
    patient_ids: list[str],
    new_person_uid: uuid.UUID,
) -> int:
    result = await session.execute(
        _REPOINT_INTERACTION_EVENT_SQL,
        {
            "tenant_id": str(tenant_id),
            "surviving_person_uid": str(surviving_person_uid),
            "new_person_uid": str(new_person_uid),
            "patient_ids": patient_ids,
        },
    )
    return int(getattr(result, "rowcount", 0) or 0)


async def _repoint_ops_consultations(
    session: Any,
    *,
    tenant_id: TenantId,
    surviving_person_uid: uuid.UUID,
    patient_ids: list[str],
    new_person_uid: uuid.UUID,
) -> int:
    result = await session.execute(
        _REPOINT_OPS_CONSULTATION_SQL,
        {
            "tenant_id": str(tenant_id),
            "surviving_person_uid": str(surviving_person_uid),
            "new_person_uid": str(new_person_uid),
            "patient_ids": patient_ids,
        },
    )
    return int(getattr(result, "rowcount", 0) or 0)


async def _count_needs_manual_review(
    session: Any,
    *,
    tenant_id: TenantId,
    surviving_person_uid: uuid.UUID,
) -> int:
    result = await session.execute(
        _COUNT_NEEDS_MANUAL_REVIEW_SQL,
        {
            "tenant_id": str(tenant_id),
            "surviving_person_uid": str(surviving_person_uid),
        },
    )
    row = result.first() if hasattr(result, "first") else None
    if row is None:
        return 0
    if hasattr(row, "_mapping") and "needs_manual_review" in row._mapping:
        return int(row._mapping["needs_manual_review"] or 0)
    try:
        return int(row[0] or 0)
    except (TypeError, IndexError, ValueError):
        return 0


def _write_audit_row(
    session: Any,
    *,
    principal: Principal,
    surviving_person_uid: uuid.UUID,
    new_person_uids: list[uuid.UUID],
    bucket_count: int,
    source_links_moved: int,
    interaction_events_moved: int,
    consultations_moved: int,
) -> None:
    extra: dict[str, object] = {
        "surviving_person_uid": str(surviving_person_uid),
        "new_person_uids": [str(u) for u in new_person_uids],
        "bucket_count": bucket_count,
        "source_links_moved": source_links_moved,
        "interaction_events_moved": interaction_events_moved,
        "consultations_moved": consultations_moved,
    }
    entry = AccessLog(
        tenant_id=principal.require_tenant(),
        principal_id=principal.id,
        principal_email=principal.email,
        person_uid=surviving_person_uid,
        action="identity.person.split",
        resource="identity.person",
        reason="eng-311.split_wrong_merged_persons",
        extra=extra,
    )
    session.add(entry)


async def _apply_split(
    session: Any,
    *,
    principal: Principal,
    candidate: _Candidate,
    buckets: list[_Bucket],
) -> tuple[int, int]:
    """Apply a split. Returns (new_persons_created, needs_manual_review)."""
    surviving = _pick_surviving(buckets)
    non_surviving = [b for b in buckets if b is not surviving]

    new_person_uids: list[uuid.UUID] = []
    source_links_moved = 0
    interaction_events_moved = 0
    consultations_moved = 0
    for bucket in non_surviving:
        new_person = await _create_new_person(
            session, tenant_id=principal.require_tenant(), bucket=bucket
        )
        bucket_pids = [p.patient_id for p in bucket.pids]
        source_links_moved += await _repoint_source_links(
            session,
            tenant_id=principal.require_tenant(),
            patient_ids=bucket_pids,
            new_person_uid=new_person.id,
        )
        interaction_events_moved += await _repoint_interaction_events(
            session,
            tenant_id=principal.require_tenant(),
            surviving_person_uid=candidate.person_uid,
            patient_ids=bucket_pids,
            new_person_uid=new_person.id,
        )
        consultations_moved += await _repoint_ops_consultations(
            session,
            tenant_id=principal.require_tenant(),
            surviving_person_uid=candidate.person_uid,
            patient_ids=bucket_pids,
            new_person_uid=new_person.id,
        )
        new_person_uids.append(new_person.id)

    needs_review = await _count_needs_manual_review(
        session,
        tenant_id=principal.require_tenant(),
        surviving_person_uid=candidate.person_uid,
    )

    _write_audit_row(
        session,
        principal=principal,
        surviving_person_uid=candidate.person_uid,
        new_person_uids=new_person_uids,
        bucket_count=len(buckets),
        source_links_moved=source_links_moved,
        interaction_events_moved=interaction_events_moved,
        consultations_moved=consultations_moved,
    )
    return (len(non_surviving), needs_review)


async def main(
    args: argparse.Namespace,
    *,
    session_factory: Callable[[], Any] | None = None,
) -> int:
    """Run the split. Returns a CLI exit code.

    Test hook ``session_factory`` injects a fully mocked unit of work;
    production callers leave it at None.
    """
    try:
        tenant_id = TenantId(UUID(args.tenant_id))
    except (ValueError, TypeError):
        log.error("split.wrong_merged.bad_tenant_id", tenant_id=str(args.tenant_id))
        return 2

    person_uid_filter: uuid.UUID | None = None
    if args.person_uid:
        try:
            person_uid_filter = uuid.UUID(args.person_uid)
        except (ValueError, TypeError):
            log.error("split.wrong_merged.bad_person_uid", person_uid=str(args.person_uid))
            return 2

    apply_writes = bool(args.apply)
    principal = _split_principal(tenant_id)

    session_cm = (
        session_factory() if session_factory is not None else _default_session_factory()
    )
    async with session_cm as session:
        candidates = await _select_candidates(
            session, tenant_id, person_uid_filter=person_uid_filter
        )

        scanned = 0
        split = 0
        new_persons = 0
        skipped = 0
        needs_manual_review = 0
        error_count = 0

        for candidate in candidates[: args.max_splits]:
            scanned += 1
            buckets = _bucket_pids(candidate.pids)
            if len(buckets) <= 1:
                skipped += 1
                continue

            if not apply_writes:
                sys.stdout.write(_format_plan(candidate, buckets))
                continue

            # Per-person SAVEPOINT. One failing person rolls back only
            # that person's writes; persons already completed in this
            # ``commit_every`` batch remain pending in the outer
            # transaction and are committed at the next flush boundary.
            try:
                async with session.begin_nested():
                    new_count, nm_review = await _apply_split(
                        session,
                        principal=principal,
                        candidate=candidate,
                        buckets=buckets,
                    )
            except Exception:
                # Savepoint already rolled back this person's writes.
                # Log uuid + count only (uuid is non-PII; no dob/ssn/name)
                # and continue with the next candidate. ``error_count``
                # is surfaced in the run summary so the operator knows
                # to triage.
                error_count += 1
                log.warning(
                    "split.wrong_merged.person_failed",
                    tenant_id=str(tenant_id),
                    person_uid=str(candidate.person_uid),
                    error_count=error_count,
                )
                continue

            new_persons += new_count
            split += 1
            needs_manual_review += nm_review

            if args.commit_every > 0 and split % args.commit_every == 0:
                await session.commit()

        if apply_writes:
            await session.commit()

        log.info(
            "split.wrong_merged.summary",
            tenant_id=str(tenant_id),
            selector="dob_ssn_mismatch",
            scanned=scanned,
            split=split,
            new_persons=new_persons,
            skipped=skipped,
            needs_manual_review=needs_manual_review,
            error_count=error_count,
            apply=apply_writes,
        )
        return 0


def run(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the exit code instead of calling sys.exit so
    wrapping callers (and tests) can use this directly."""
    configure_logging()
    args = parse_args(argv)
    return asyncio.run(main(args))


__all__ = ["main", "parse_args", "run"]


if __name__ == "__main__":
    sys.exit(run())
