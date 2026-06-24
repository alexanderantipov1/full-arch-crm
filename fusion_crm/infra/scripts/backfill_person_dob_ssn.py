"""Backfill identity.person.dob / identity.person.ssn (ENG-312).

ENG-309 added a HARD VETO in :class:`packages.identity.service.IdentityService`:
two persons whose ``dob`` or ``ssn`` differ never merge, regardless of how
many soft signals overlap. The veto only fires when BOTH sides have a value
-- and today the existing ``identity.person`` population has ``dob`` / ``ssn``
NULL across the board (110042 rows; ENG-311 already split the back-catalogue
of wrong-merged households produced before the veto landed). This script
populates those columns from the latest ``carestack.patient.upsert`` payload
per linked CareStack patient_id so the veto starts firing on subsequent
re-pulls.

For each ``identity.person`` row that has at least one ``identity.source_link``
into ``carestack/patient`` AND (``dob IS NULL`` OR ``ssn IS NULL``):

* Pull the latest CareStack payload per linked patient_id (same DISTINCT-ON
  shape ``infra/scripts/audit_identity_merges.py`` uses).
* Parse each ``(dob, ssn)`` using the same helpers the ingest path uses
  (:func:`packages.ingest.carestack_patient_service._parse_carestack_dob`
  and :func:`._normalize_ssn`).
* If the parsed dobs across pids disagree (>1 distinct non-null value
  excluding the placeholder ``1900-01-01``) OR the ssns disagree, SKIP
  the person and count it under ``needs_manual_review``. Post-ENG-311
  this set should be near-zero -- surfacing it is the point.
* Otherwise pick the single agreed dob and the single agreed ssn:
    * If the only available dob value is the placeholder ``1900-01-01``
      (CareStack's "unknown DOB" sentinel), do NOT write it; count the
      person under ``skipped_placeholder_dob`` and leave ``dob`` NULL.
    * Set ``person.dob`` IFF currently NULL and a real (non-placeholder)
      value is available.
    * Set ``person.ssn`` IFF currently NULL and a digit-only normalised
      value is available.
* Write one ``audit.access_log`` row per updated person with
  ``action='identity.person.demographic_backfill'``. ``extra`` carries
  ``set_dob`` / ``set_ssn`` booleans + ``source_pid_count`` integer ONLY.
  No dob / ssn / name VALUES anywhere -- demographic identity-strength
  signals stay out of logs and audit payloads per the ENG-309 carve-out
  in ``packages/identity/CLAUDE.md``.

Write-once. The script never overwrites a non-null value: it mirrors the
in-resolver :func:`IdentityService._maybe_backfill_demographic` rule so a
later re-run is a strict no-op against an already-populated row.

Per-person SAVEPOINT. Each candidate's writes run inside
``async with session.begin_nested():`` so a single failing person rolls
back ONLY that person; the outer ``commit_every`` batch keeps prior
successes. The error is logged at warning with ``person_uid`` + count
only (no PHI) and ``error_count`` is surfaced in the run summary.

CLI::

    python3 infra/scripts/backfill_person_dob_ssn.py \\
        --tenant-id <uuid> \\
        [--apply]                   # default is --dry-run
        [--max-persons 200]
        [--commit-every 50]
        [--person-uid <uuid>]       # single-target verification

Exit codes:
    0  success (including dry-run + "no candidates")
    2  invalid tenant / invalid --person-uid
    1  uncaught exception (logged before propagation by ``run``)

PHI handling: structured logs carry ONLY counts and uuids. The dry-run
plan printed to stdout carries ``person_uid`` + boolean would-set flags
+ pid count -- never the parsed dob / ssn VALUES. Run summary likewise
counts only.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text

from packages.audit.models import AccessLog
from packages.core.logging import configure_logging, get_logger
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.ingest.carestack_patient_service import (
    _normalize_ssn,
    _parse_carestack_dob,
)

log = get_logger("infra.backfill_person_dob_ssn")

_DEFAULT_MAX_PERSONS = 200
_DEFAULT_COMMIT_EVERY = 50

# CareStack's "unknown DOB" sentinel. Operators have observed it on
# imports that pre-date the Patient Sync DOB requirement; we treat it
# the same as NULL for backfill purposes so the resolver veto is not
# armed with a fake value.
_PLACEHOLDER_DOB = date(1900, 1, 1)


def _default_session_factory() -> Any:
    # ``packages.db.session`` builds the engine at import time via
    # :func:`Settings`. Eager import would prevent ``--help`` from running
    # without env, and would force every unit test to set
    # ``SECRET_KEY`` / ``DATABASE_URL`` / ``REDIS_URL`` just to load this
    # module. Resolve at call time instead.
    from packages.db.session import async_session

    return async_session()


# Selection SQL. One row per candidate person; carries the current
# ``person.dob`` / ``person.ssn`` (so we know what is NULL and what is
# already set), the linked carestack patient_ids, and the latest
# payload's raw ``dob`` / ``ssn`` strings per pid.
#
# The DISTINCT-ON narrows ``ingest.raw_event`` to the most recent
# ``carestack.patient.upsert`` per patient_id; older payloads are
# noise from re-pulls. Join key is ``re.external_id = sl.source_id``
# -- same as ``audit_identity_merges.py`` and ``split_wrong_merged_persons.py``
# (both run in production; their working query is the canonical shape).
_SELECT_CANDIDATES_SQL = text(
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
        p.id                                                              AS person_uid,
        p.dob                                                             AS person_dob,
        p.ssn                                                             AS person_ssn,
        ARRAY_AGG(lp.patient_id ORDER BY lp.patient_id)                   AS patient_ids,
        ARRAY_AGG(lp.payload->>'dob' ORDER BY lp.patient_id)              AS dobs,
        ARRAY_AGG(lp.payload->>'ssn' ORDER BY lp.patient_id)              AS ssns
    FROM identity.person AS p
    JOIN latest_payload  AS lp ON lp.person_uid = p.id
    WHERE p.tenant_id = :tenant_id
      AND (p.dob IS NULL OR p.ssn IS NULL)
    GROUP BY p.id, p.dob, p.ssn
    ORDER BY p.id
    """
)


# Write-once UPDATE. COALESCE preserves any existing non-null value
# even when this script is mistakenly invoked twice with different
# inputs -- DB-level guarantee that mirrors the in-resolver write-once
# semantics (:func:`IdentityService._maybe_backfill_demographic`).
_UPDATE_PERSON_SQL = text(
    """
    UPDATE identity.person
       SET dob = COALESCE(dob, :dob),
           ssn = COALESCE(ssn, :ssn)
     WHERE id = :person_uid
       AND tenant_id = :tenant_id
    """
)


@dataclass(frozen=True)
class _Candidate:
    """One ``identity.person`` row needing dob/ssn backfill."""

    person_uid: uuid.UUID
    person_dob: date | None
    person_ssn: str | None
    patient_ids: list[str]
    dob_strings: list[str | None]
    ssn_strings: list[str | None]


@dataclass(frozen=True)
class _Plan:
    """Computed backfill plan for a single person."""

    # ``set_dob`` / ``set_ssn`` are ``None`` when no usable value was
    # found OR when the person already has a non-null value (write-once).
    set_dob: date | None
    set_ssn: str | None
    # Full-person skip reason: ``mismatch_dob`` or ``mismatch_ssn``
    # (the candidate pids disagree on demographic identity-strength
    # signals). ``None`` when no full-person skip applies.
    skip_reason: str | None
    # The only available dob signal was the placeholder ``1900-01-01``
    # (CareStack "unknown DOB" sentinel). Surfaced as a counter so the
    # operator can re-pull a real DOB. Does NOT block setting ssn.
    placeholder_dob: bool
    source_pid_count: int


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill identity.person.dob / .ssn from the latest CareStack "
            "patient payload per linked patient_id (ENG-312)."
        ),
    )
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help=(
            "Default. Print the per-person plan to stdout; do NOT write "
            "to the database. ``--apply`` overrides."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help=(
            "Explicit opt-in to write. The only path that mutates "
            "identity.person and writes audit rows."
        ),
    )
    parser.add_argument(
        "--max-persons",
        type=int,
        default=_DEFAULT_MAX_PERSONS,
        help=(
            "Maximum candidate persons processed in this run (default "
            "200). The real fleet backfill runs in batches under "
            "operator supervision."
        ),
    )
    parser.add_argument(
        "--commit-every",
        type=int,
        default=_DEFAULT_COMMIT_EVERY,
        help=(
            "Flush the DB unit-of-work every N persons (default 50). "
            "Prevents a single giant transaction across the whole run."
        ),
    )
    parser.add_argument(
        "--person-uid",
        default=None,
        help=(
            "If set, restrict selection to this single ``identity.person.id``. "
            "Use it for spot-verification on a known canary before fleet apply."
        ),
    )
    return parser.parse_args(argv)


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"actor": "system:backfill_person_dob_ssn"},
    )


def _build_candidate(mapping: Any) -> _Candidate | None:
    raw_pids = list(mapping["patient_ids"] or [])
    if not raw_pids:
        return None
    person_uid = mapping["person_uid"]
    if isinstance(person_uid, str):
        person_uid = uuid.UUID(person_uid)
    person_dob_raw = mapping.get("person_dob") if hasattr(mapping, "get") else mapping["person_dob"]
    person_ssn_raw = mapping.get("person_ssn") if hasattr(mapping, "get") else mapping["person_ssn"]
    person_dob: date | None
    if isinstance(person_dob_raw, date):
        person_dob = person_dob_raw
    elif isinstance(person_dob_raw, str) and person_dob_raw:
        person_dob = _parse_carestack_dob(person_dob_raw)
    else:
        person_dob = None
    person_ssn = person_ssn_raw if isinstance(person_ssn_raw, str) and person_ssn_raw else None
    dobs = list(mapping.get("dobs") or [])
    ssns = list(mapping.get("ssns") or [])

    def _at(lst: list[Any], i: int) -> Any:
        return lst[i] if i < len(lst) else None

    return _Candidate(
        person_uid=person_uid,
        person_dob=person_dob,
        person_ssn=person_ssn,
        patient_ids=[str(p) for p in raw_pids],
        dob_strings=[_at(dobs, i) for i in range(len(raw_pids))],
        ssn_strings=[_at(ssns, i) for i in range(len(raw_pids))],
    )


def _compute_plan(candidate: _Candidate) -> _Plan:
    """Per-person decision: what to set / skip / why.

    Decision order mirrors the resolver veto:

    * If the non-null parsed dobs (excluding the placeholder
      ``1900-01-01``) disagree across pids, SKIP -- the candidate
      person was already a wrong-merge before ENG-311 ran, or a
      manual-merge edge case the operator still has to triage.
    * Same for non-null parsed ssns.
    * Otherwise pick the single agreed value. If the only available
      dob signal is the placeholder, skip writing dob (leave NULL +
      surface in the run summary).
    """
    parsed_dobs: set[date] = set()
    saw_placeholder_dob = False
    for raw in candidate.dob_strings:
        parsed = _parse_carestack_dob(raw)
        if parsed is None:
            continue
        if parsed == _PLACEHOLDER_DOB:
            saw_placeholder_dob = True
            continue
        parsed_dobs.add(parsed)

    parsed_ssns: set[str] = set()
    for raw in candidate.ssn_strings:
        norm = _normalize_ssn(raw)
        if norm is None:
            continue
        parsed_ssns.add(norm)

    pid_count = len(candidate.patient_ids)

    if len(parsed_dobs) > 1:
        return _Plan(
            set_dob=None,
            set_ssn=None,
            skip_reason="mismatch_dob",
            placeholder_dob=False,
            source_pid_count=pid_count,
        )
    if len(parsed_ssns) > 1:
        return _Plan(
            set_dob=None,
            set_ssn=None,
            skip_reason="mismatch_ssn",
            placeholder_dob=False,
            source_pid_count=pid_count,
        )

    agreed_dob = next(iter(parsed_dobs), None)
    agreed_ssn = next(iter(parsed_ssns), None)

    # Placeholder-only dob signal: surface the person under
    # ``skipped_placeholder_dob`` so the operator knows the CareStack
    # rows still need a real DOB pulled. Setting ssn is still allowed
    # in this case -- the placeholder applies only to dob.
    placeholder_dob = agreed_dob is None and saw_placeholder_dob

    set_dob = agreed_dob if (agreed_dob is not None and candidate.person_dob is None) else None
    set_ssn = agreed_ssn if (agreed_ssn is not None and candidate.person_ssn is None) else None

    return _Plan(
        set_dob=set_dob,
        set_ssn=set_ssn,
        skip_reason=None,
        placeholder_dob=placeholder_dob,
        source_pid_count=pid_count,
    )


def _format_dry_run_line(candidate: _Candidate, plan: _Plan) -> str:
    """Operator-facing dry-run output. Booleans + counts only -- NO PHI VALUES."""
    parts = [
        f"person_uid={candidate.person_uid}",
        f"source_pid_count={plan.source_pid_count}",
        f"would_set_dob={plan.set_dob is not None}",
        f"would_set_ssn={plan.set_ssn is not None}",
    ]
    if plan.skip_reason is not None:
        parts.append(f"skip_reason={plan.skip_reason}")
    if plan.placeholder_dob:
        parts.append("placeholder_dob=true")
    return " ".join(parts) + "\n"


async def _select_candidates(
    session: Any,
    tenant_id: TenantId,
    *,
    person_uid_filter: uuid.UUID | None,
) -> list[_Candidate]:
    rows = (
        await session.execute(
            _SELECT_CANDIDATES_SQL, {"tenant_id": str(tenant_id)}
        )
    ).all()
    out: list[_Candidate] = []
    for row in rows:
        mapping = row._mapping if hasattr(row, "_mapping") else row
        candidate = _build_candidate(mapping)
        if candidate is None:
            continue
        if person_uid_filter is not None and candidate.person_uid != person_uid_filter:
            continue
        out.append(candidate)
    return out


def _write_audit_row(
    session: Any,
    *,
    principal: Principal,
    candidate: _Candidate,
    plan: _Plan,
) -> None:
    # extra: booleans + counts + uuids only. NEVER the dob / ssn / name
    # values themselves -- those are identity-strength signals that stay
    # out of logs and audit payloads (see ``packages/identity/CLAUDE.md``).
    extra: dict[str, object] = {
        "set_dob": plan.set_dob is not None,
        "set_ssn": plan.set_ssn is not None,
        "source_pid_count": plan.source_pid_count,
    }
    entry = AccessLog(
        tenant_id=principal.require_tenant(),
        principal_id=principal.id,
        principal_email=principal.email,
        person_uid=candidate.person_uid,
        action="identity.person.demographic_backfill",
        resource="identity.person",
        reason="eng-312.backfill_person_dob_ssn",
        extra=extra,
    )
    session.add(entry)


async def _apply_one(
    session: Any,
    *,
    principal: Principal,
    candidate: _Candidate,
    plan: _Plan,
) -> None:
    """Apply a single-person backfill. Caller wraps in SAVEPOINT."""
    await session.execute(
        _UPDATE_PERSON_SQL,
        {
            "tenant_id": str(principal.require_tenant()),
            "person_uid": str(candidate.person_uid),
            "dob": plan.set_dob,
            "ssn": plan.set_ssn,
        },
    )
    _write_audit_row(
        session,
        principal=principal,
        candidate=candidate,
        plan=plan,
    )


async def main(
    args: argparse.Namespace,
    *,
    session_factory: Callable[[], Any] | None = None,
) -> int:
    """Run the backfill once. Returns a CLI exit code.

    Test hook ``session_factory`` injects a fully mocked unit-of-work;
    production callers leave it at None.
    """
    try:
        tenant_id = TenantId(UUID(args.tenant_id))
    except (ValueError, TypeError):
        log.error(
            "backfill.person_dob_ssn.bad_tenant_id", tenant_id=str(args.tenant_id)
        )
        return 2

    person_uid_filter: uuid.UUID | None = None
    if args.person_uid:
        try:
            person_uid_filter = uuid.UUID(args.person_uid)
        except (ValueError, TypeError):
            log.error(
                "backfill.person_dob_ssn.bad_person_uid",
                person_uid=str(args.person_uid),
            )
            return 2

    apply_writes = bool(args.apply)
    principal = _principal(tenant_id)

    session_cm = (
        session_factory() if session_factory is not None else _default_session_factory()
    )
    async with session_cm as session:
        candidates = await _select_candidates(
            session, tenant_id, person_uid_filter=person_uid_filter
        )

        scanned = 0
        updated = 0
        nothing_to_do = 0
        needs_manual_review = 0
        skipped_placeholder_dob = 0
        error_count = 0
        set_dob_count = 0
        set_ssn_count = 0

        for candidate in candidates[: args.max_persons]:
            scanned += 1
            plan = _compute_plan(candidate)

            if plan.skip_reason in ("mismatch_dob", "mismatch_ssn"):
                needs_manual_review += 1
                if not apply_writes:
                    sys.stdout.write(_format_dry_run_line(candidate, plan))
                continue

            # Track placeholder-dob signal independently of whether ssn
            # is still settable: a person with placeholder dob + a real
            # ssn still gets ssn written, but the operator needs to know
            # dob was deliberately left NULL on this person.
            if plan.placeholder_dob:
                skipped_placeholder_dob += 1

            if plan.set_dob is None and plan.set_ssn is None:
                # Nothing to do -- either the person already has both
                # set (write-once), or no usable signal was found.
                nothing_to_do += 1
                if not apply_writes:
                    sys.stdout.write(_format_dry_run_line(candidate, plan))
                continue

            if not apply_writes:
                sys.stdout.write(_format_dry_run_line(candidate, plan))
                continue

            # Per-person SAVEPOINT. One failing person rolls back only
            # this person's writes; persons already completed in this
            # ``commit_every`` batch remain pending in the outer
            # transaction and are committed at the next flush boundary.
            try:
                async with session.begin_nested():
                    await _apply_one(
                        session,
                        principal=principal,
                        candidate=candidate,
                        plan=plan,
                    )
            except Exception:
                # Savepoint already rolled back this person's writes.
                # Log uuid + counts only (no dob / ssn / name) and
                # continue with the next candidate.
                error_count += 1
                log.warning(
                    "backfill.person_dob_ssn.person_failed",
                    tenant_id=str(tenant_id),
                    person_uid=str(candidate.person_uid),
                    error_count=error_count,
                )
                continue

            updated += 1
            if plan.set_dob is not None:
                set_dob_count += 1
            if plan.set_ssn is not None:
                set_ssn_count += 1

            if args.commit_every > 0 and updated % args.commit_every == 0:
                await session.commit()

        if apply_writes:
            await session.commit()

        log.info(
            "backfill.person_dob_ssn.summary",
            tenant_id=str(tenant_id),
            scanned=scanned,
            updated=updated,
            set_dob=set_dob_count,
            set_ssn=set_ssn_count,
            nothing_to_do=nothing_to_do,
            needs_manual_review=needs_manual_review,
            skipped_placeholder_dob=skipped_placeholder_dob,
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
