"""Audit identity merges for DOB / SSN mismatch (ENG-309).

Operator-triggered, read-only scan. Surfaces any ``identity.person`` row
that has been merged across two or more linked CareStack patient_ids
whose latest ``carestack.patient.upsert`` payload disagrees on DOB or
SSN. These persons are the bug the ENG-309 hard veto prevents going
forward; this script counts and samples the back-catalogue so operators
can size a follow-up un-merge run (ENG-311) before invoking it on prod.

The script NEVER writes to the database -- it is a counting and
sampling tool. The companion ``split_wrong_merged_persons.py`` is
gated behind separate operator approval; this audit's output should
inform whether to run it at all.

CLI:

    python3 infra/scripts/audit_identity_merges.py \\
        --tenant-id <uuid> \\
        [--sample-size 20] \\
        [--dry-run]   # accepted for symmetry; the script never writes

Exit codes:
    0  success (counts emitted)
    1  uncaught exception (logged before propagation by ``run``)

PHI handling: structured logs contain ONLY counts + ``person_uid`` /
``patient_id`` values (non-PHI references). The sample listing on
stdout is gated on ``--sample-size`` and may include DOB / SSN per
patient_id -- this matches the operator-facing inspector carve-out
in :doc:`infra/CLAUDE.md` and ``packages/ingest/CLAUDE.md`` (raw
provider data is operator-visible during reconciliation). NEVER pipe
stdout into a logging pipeline.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import text

from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId

log = get_logger("infra.audit_identity_merges")

_DEFAULT_SAMPLE_SIZE = 20

# Mirrors the resolver-side normaliser
# (``packages.identity.service._normalise_ssn_for_compare``); kept local
# so the script does not import identity service internals.
_SSN_STRIP = re.compile(r"[\s\-]+")


def _normalise_ssn(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = _SSN_STRIP.sub("", value).strip()
    return cleaned or None


def _default_session_factory() -> Any:
    from packages.db.session import async_session

    return async_session()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit identity.person rows merged across mismatched DOB / SSN.",
    )
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID.")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=_DEFAULT_SAMPLE_SIZE,
        help=(
            "Number of wrong-merged persons printed to stdout with their "
            "per-pid (dob, ssn) tuples (default 20)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help=(
            "Accepted for CLI symmetry with other infra scripts. This "
            "audit never writes regardless."
        ),
    )
    return parser.parse_args(argv)


# Latest-payload-per-patient join. Each ``identity.source_link`` for
# carestack/patient is joined to its latest ``ingest.raw_event`` row of
# type ``carestack.patient.upsert`` keyed by (tenant_id, external_id ==
# source_link.source_id). The DISTINCT-ON narrows to the most recent
# payload per patient_id -- earlier raw_event rows for the same patient
# are noise from re-pulls.
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
        ARRAY_AGG(payload->>'ssn'  ORDER BY patient_id)                    AS ssns
    FROM latest_payload
    GROUP BY person_uid
    HAVING COUNT(*) > 1
    """
)


def _count_distinct_non_null(values: list[Any]) -> int:
    seen: set[Any] = set()
    for v in values:
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        seen.add(v)
    return len(seen)


async def main(
    args: argparse.Namespace,
    *,
    session_factory: Callable[[], Any] | None = None,
) -> int:
    """Run the audit. Returns a CLI exit code.

    Test hook ``session_factory`` lets the unit test inject a fully
    mocked unit-of-work; production callers leave it at None.
    """
    tenant_id = TenantId(UUID(args.tenant_id))
    session_cm = session_factory() if session_factory is not None else _default_session_factory()

    async with session_cm as session:
        rows = (
            await session.execute(_AUDIT_SQL, {"tenant_id": str(tenant_id)})
        ).all()

        total_persons = len(rows)
        dob_mismatch_count = 0
        ssn_mismatch_count = 0
        wrong_merged: list[dict[str, Any]] = []

        for row in rows:
            mapping = row._mapping if hasattr(row, "_mapping") else row
            dobs: list[Any] = list(mapping["dobs"] or [])
            ssns_raw: list[Any] = list(mapping["ssns"] or [])
            ssns: list[Any] = [_normalise_ssn(s) for s in ssns_raw]

            distinct_dob = _count_distinct_non_null(dobs)
            distinct_ssn = _count_distinct_non_null(ssns)

            if distinct_dob <= 1 and distinct_ssn <= 1:
                continue

            if distinct_dob > 1:
                dob_mismatch_count += 1
            if distinct_ssn > 1:
                ssn_mismatch_count += 1

            wrong_merged.append(
                {
                    "person_uid": str(mapping["person_uid"]),
                    "patient_ids": [str(p) for p in mapping["patient_ids"]],
                    "dobs": [str(d) if d is not None else None for d in dobs],
                    "ssns": [str(s) if s is not None else None for s in ssns],
                    "distinct_dob": distinct_dob,
                    "distinct_ssn": distinct_ssn,
                }
            )

        log.info(
            "audit.identity_merges.summary",
            tenant_id=str(tenant_id),
            scanned_multi_pid_persons=total_persons,
            wrong_merged_persons=len(wrong_merged),
            dob_mismatch_count=dob_mismatch_count,
            ssn_mismatch_count=ssn_mismatch_count,
            sample_size=args.sample_size,
        )

        # Stdout sample. patient_id, dob, ssn are operator-only context;
        # NEVER call structured log helpers with these values.
        sample_limit = max(0, args.sample_size)
        for record in wrong_merged[:sample_limit]:
            sys.stdout.write(
                "person_uid={person_uid} patient_ids={pids} dobs={dobs} ssns={ssns} "
                "distinct_dob={d_dob} distinct_ssn={d_ssn}\n".format(
                    person_uid=record["person_uid"],
                    pids=record["patient_ids"],
                    dobs=record["dobs"],
                    ssns=record["ssns"],
                    d_dob=record["distinct_dob"],
                    d_ssn=record["distinct_ssn"],
                )
            )

        return 0


def run(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    return asyncio.run(main(args))


__all__ = ["main", "parse_args", "run"]


if __name__ == "__main__":
    sys.exit(run())
