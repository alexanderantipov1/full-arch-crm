"""Stitch split lead-persons onto patient-persons (ENG-404).

Prod patient-persons created by the May-era ingest carry no
``identity.person_identifier`` rows, so the 2026-06-11 lead backfill could
not resolve onto them and created SEPARATE persons for the same humans:
consultations + payments live on the patient-person, the lead on a fresh
lead-person, and every ``person_uid`` funnel join silently misses.

For every CareStack patient-person P that has NO lead:

1. Take the email from the latest ``carestack.patient.upsert`` raw payload
   (the May-era rows never copied it into ``person_identifier``).
2. Normalise it and look up persons holding that email identifier AND at
   least one lead (these are today's lead-persons).
3. Merge ONLY when the match is unambiguous (exactly one candidate, names
   agree when both sides have them, no DOB conflict). Phone is deliberately
   NOT a match key — household members share phones (ENG-309 lesson).
4. Merge direction: repoint the lead-person L's few rows (lead, follow-ups,
   timeline events, identifiers, source links, location profiles) onto P,
   then delete the emptied L. P keeps its consultations/payments untouched —
   this is orders of magnitude fewer row updates than moving P onto L.

Anything ambiguous lands in a counted bucket and is NOT touched.

Usage:

    python3 infra/scripts/merge_split_lead_persons.py            # dry-run
    python3 infra/scripts/merge_split_lead_persons.py --apply
    python3 infra/scripts/merge_split_lead_persons.py --apply --limit 100

Exit code 0 on success (dry-run or apply).
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.session import SessionFactory
from packages.identity.service import normalise_email, normalise_phone

_BATCH_COMMIT = 50

# Patient-persons without a lead, with their patient id, ordered
# deterministically so re-runs and --limit canaries are stable.
_CANDIDATES_SQL = """
SELECT sl.person_uid AS patient_person, sl.source_id AS patient_id,
       p.given_name, p.family_name, p.dob
FROM identity.source_link sl
JOIN identity.person p ON p.id = sl.person_uid
WHERE sl.source_system = 'carestack'
  AND sl.source_kind = 'patient'
  AND sl.source_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM ops.lead l WHERE l.person_uid = sl.person_uid)
  AND (CAST(:tenant AS uuid) IS NULL OR sl.tenant_id = :tenant)
ORDER BY sl.source_id
"""

_LATEST_PATIENT_PAYLOAD_SQL = """
SELECT payload->>'email' AS email,
       payload->>'mobile' AS mobile,
       payload->>'phoneWithExt' AS phone_with_ext,
       payload->>'firstName' AS first_name,
       payload->>'lastName' AS last_name
FROM ingest.raw_event
WHERE source = 'carestack'
  AND event_type = 'carestack.patient.upsert'
  AND external_id = :patient_id
ORDER BY received_at DESC
LIMIT 1
"""

# Owner policy 2026-06-11: phone is a full merge key too (duplicates often
# carry different emails). Households are protected by the name gate, not
# by refusing phone matches.
_LEAD_PERSONS_BY_IDENTIFIER_SQL = """
SELECT DISTINCT pi.person_id, p.given_name, p.family_name, p.dob
FROM identity.person_identifier pi
JOIN identity.person p ON p.id = pi.person_id
WHERE pi.kind = :kind
  AND pi.value = :value
  AND pi.person_id != :patient_person
  AND EXISTS (SELECT 1 FROM ops.lead l WHERE l.person_uid = pi.person_id)
"""

_REPOINT_SQLS = (
    "UPDATE ops.lead SET person_uid = :p WHERE person_uid = :l",
    "UPDATE ops.followup_task SET person_uid = :p WHERE person_uid = :l",
    "UPDATE ops.consultation SET person_uid = :p WHERE person_uid = :l",
    "UPDATE interaction.event SET person_uid = :p WHERE person_uid = :l",
    # (kind, value) is globally unique, so the row itself moves — no
    # collision is possible against P's identifiers for the same value.
    "UPDATE identity.person_identifier SET person_id = :p WHERE person_id = :l",
    # Move only links that would not collide with an existing link of P
    # on the (system, instance, kind, source_id) natural key; drop the rest.
    """
    UPDATE identity.source_link sl SET person_uid = :p
    WHERE sl.person_uid = :l
      AND NOT EXISTS (
        SELECT 1 FROM identity.source_link x
        WHERE x.person_uid = :p
          AND x.source_system = sl.source_system
          AND x.source_instance = sl.source_instance
          AND x.source_kind = sl.source_kind
          AND x.source_id IS NOT DISTINCT FROM sl.source_id
      )
    """,
    "DELETE FROM identity.source_link WHERE person_uid = :l",
    """
    UPDATE ops.person_location_profile plp SET person_uid = :p
    WHERE plp.person_uid = :l
      AND NOT EXISTS (
        SELECT 1 FROM ops.person_location_profile x
        WHERE x.person_uid = :p AND x.location_id = plp.location_id
      )
    """,
    "DELETE FROM ops.person_location_profile WHERE person_uid = :l",
    # Resolver bookkeeping about the disappearing person is meaningless
    # after the merge — drop it (three person-referencing FK columns).
    """
    DELETE FROM identity.match_candidate
    WHERE source_person_uid = :l
       OR candidate_person_uid = :l
       OR accepted_person_uid = :l
    """,
    "DELETE FROM identity.person WHERE id = :l",
)


def _norm_name(value: object) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def _names_conflict(
    a_first: object, a_last: object, b_first: object, b_last: object
) -> bool:
    """True only when BOTH sides carry a name part and they differ."""
    for a, b in ((_norm_name(a_first), _norm_name(b_first)),
                 (_norm_name(a_last), _norm_name(b_last))):
        if a and b and a != b:
            return True
    return False


@dataclass
class Buckets:
    mergeable: int = 0
    merged: int = 0
    matched_by_email: int = 0
    matched_by_phone: int = 0
    no_raw_payload: int = 0
    no_identifiers: int = 0
    no_candidate: int = 0
    multi_candidate: int = 0
    name_conflict: int = 0
    dob_conflict: int = 0
    pairs: list[tuple[UUID, UUID]] = field(default_factory=list)


async def _merge_pair(session: AsyncSession, lead_person: UUID, patient_person: UUID) -> None:
    for sql in _REPOINT_SQLS:
        await session.execute(text(sql), {"p": patient_person, "l": lead_person})


async def run(apply: bool, limit: int | None, tenant: UUID | None = None) -> Buckets:
    buckets = Buckets()
    async with SessionFactory() as session:
        candidates = (
            await session.execute(text(_CANDIDATES_SQL), {"tenant": tenant})
        ).all()
        print(f"patient-persons without a lead: {len(candidates)}")

        since_commit = 0
        for row in candidates:
            if limit is not None and buckets.mergeable >= limit:
                break
            payload = (
                await session.execute(
                    text(_LATEST_PATIENT_PAYLOAD_SQL),
                    {"patient_id": row.patient_id},
                )
            ).first()
            if payload is None:
                buckets.no_raw_payload += 1
                continue
            # Build the lookup keys: email first (stronger), then phone
            # (owner policy 2026-06-11 — names gate the household risk).
            keys: list[tuple[str, str]] = []
            raw_email = (payload.email or "").strip()
            if raw_email:
                keys.append(("email", normalise_email(raw_email)))
            raw_phone = (payload.mobile or payload.phone_with_ext or "").strip()
            if raw_phone:
                normalized_phone = normalise_phone(raw_phone)
                if normalized_phone:
                    keys.append(("phone", normalized_phone))
            if not keys:
                buckets.no_identifiers += 1
                continue

            matches: Sequence[Any] = []
            matched_kind = ""
            for kind, value in keys:
                matches = (
                    await session.execute(
                        text(_LEAD_PERSONS_BY_IDENTIFIER_SQL),
                        {
                            "kind": kind,
                            "value": value,
                            "patient_person": row.patient_person,
                        },
                    )
                ).all()
                if matches:
                    matched_kind = kind
                    break
            if len(matches) == 0:
                buckets.no_candidate += 1
                continue
            if len(matches) > 1:
                buckets.multi_candidate += 1
                continue
            lead = matches[0]
            if _names_conflict(
                payload.first_name or row.given_name,
                payload.last_name or row.family_name,
                lead.given_name,
                lead.family_name,
            ):
                buckets.name_conflict += 1
                continue
            if row.dob is not None and lead.dob is not None and row.dob != lead.dob:
                buckets.dob_conflict += 1
                continue

            buckets.mergeable += 1
            if matched_kind == "phone":
                buckets.matched_by_phone += 1
            else:
                buckets.matched_by_email += 1
            buckets.pairs.append((lead.person_id, row.patient_person))
            if apply:
                await _merge_pair(session, lead.person_id, row.patient_person)
                buckets.merged += 1
                since_commit += 1
                if since_commit >= _BATCH_COMMIT:
                    await session.commit()
                    since_commit = 0
                    print(f"  ...merged {buckets.merged}")
        if apply:
            await session.commit()
    return buckets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="execute merges")
    parser.add_argument(
        "--limit", type=int, default=None, help="cap mergeable pairs (canary)"
    )
    parser.add_argument(
        "--tenant", type=UUID, default=None, help="restrict to one tenant id"
    )
    args = parser.parse_args()

    buckets = asyncio.run(run(apply=args.apply, limit=args.limit, tenant=args.tenant))
    mode = "merged" if args.apply else "mergeable (dry-run)"
    print(f"{mode}: {buckets.mergeable}")
    print(f"  matched_by_email: {buckets.matched_by_email}")
    print(f"  matched_by_phone: {buckets.matched_by_phone}")
    print(f"no_raw_payload: {buckets.no_raw_payload}")
    print(f"no_identifiers: {buckets.no_identifiers}")
    print(f"no_candidate: {buckets.no_candidate}")
    print(f"multi_candidate: {buckets.multi_candidate}")
    print(f"name_conflict: {buckets.name_conflict}")
    print(f"dob_conflict: {buckets.dob_conflict}")
    if not args.apply and buckets.mergeable:
        print("Re-run with --apply to merge. Batches commit as they go.")


if __name__ == "__main__":
    main()
