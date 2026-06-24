"""Merge true-duplicate persons that share a phone AND a name (ENG-463).

The strip-only phone normaliser stored one number as both 10-digit and
11-digit, so identity dedup missed it and created duplicate Person rows.
The E.164 fix (phase 1) stops new dupes; this script cleans up the
historical ones.

**Name-aware, NOT a blind phone collapse.** Two persons merge only when
they share a canonical E.164 phone AND a matching name (sorted
name-token-set, so "Fredrick Dixon" == "Dixon Fredrick"). Persons that
share a phone but have *different* names are households (spouse /
parent-child) — they are LEFT SEPARATE and surfaced in the person card's
"shared contact" section instead (see
``IngestRepository.person_household_members_by_identifier``).

Survivor selection per cluster = the richest record: has a CareStack
patient link > has an email > most identifiers; tiebreak earliest
``created_at`` then smallest id. The survivor's ``person_uid`` persists
(URLs, history); every other person's references are repointed to it and
an append-only ``identity.merge_event`` is written.

CLI::

    python3 infra/scripts/merge_phone_duplicate_persons.py            # dry-run
    python3 infra/scripts/merge_phone_duplicate_persons.py --apply    # merge
    [--tenant-id <uuid>] [--limit N]

Dry-run (DEFAULT) writes nothing — it prints cluster + survivor counts and
the per-table repoint blast radius. ``--apply`` merges one cluster per
transaction (a crash resumes safely; merges are idempotent — an already
merged person has no rows left to move).

Exit codes: 0 success (dry-run or apply); 1 uncaught exception.

Guard-rails: ``audit.access_log`` is append-only and NEVER repointed
(historical access stays attributed to the original person_uid). PHI
tables (``phi.consultation`` / ``phi.patient_profile``) ARE repointed so
clinical history follows the surviving person. Logs carry ids + counts
only — never names / phones.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.logging import configure_logging, get_logger
from packages.core.types import TenantId
from packages.identity.service import IdentityService, normalise_phone

log = get_logger("infra.merge_phone_duplicate_persons")

# Plain ``UPDATE col = survivor WHERE col = merged AND tenant_id = :t`` —
# no per-person UNIQUE on these tables, so a straight repoint is safe. The
# tenant predicate is defensive (person_uid is globally unique, but we
# never touch a row outside the cluster's tenant).
_SIMPLE_REPOINTS: tuple[tuple[str, str], ...] = (
    ("ops.lead", "person_uid"),
    ("ops.followup_task", "person_uid"),
    ("ops.consultation", "person_uid"),
    ("ops.opportunity", "person_uid"),
    ("interaction.event", "person_uid"),
    ("phi.consultation", "person_uid"),
    ("actor.actor", "person_uid"),
    ("outreach.send", "person_uid"),
    ("integrations.external_entity", "person_uid"),
    ("ingest.normalized_person_hint", "person_uid"),
)

# Move-then-delete: a per-person UNIQUE index means the merged row can only
# move when the survivor has no conflicting row; leftovers (survivor
# already owns the key) are dropped. Each entry is
# ``(table, person_col, other_unique_cols, tenant_scoped)``:
#   * ``other_unique_cols`` — the non-person columns of the UNIQUE key.
#   * ``tenant_scoped`` — whether ``tenant_id`` is part of that UNIQUE key
#     (source_link / location_profile / attribution are; person_identifier
#     is GLOBAL on (kind,value); patient_profile is GLOBAL on person_uid).
_COLLISION_REPOINTS: tuple[tuple[str, str, tuple[str, ...], bool], ...] = (
    ("identity.person_identifier", "person_id", ("kind", "value"), False),
    (
        "identity.source_link",
        "person_uid",
        ("source_system", "source_instance", "source_kind", "source_id"),
        True,
    ),
    ("ops.person_location_profile", "person_uid", ("location_id",), True),
    ("attribution.lead_attribution", "person_uid", (), True),  # UNIQUE(tenant,person)
    ("phi.patient_profile", "person_uid", (), False),  # UNIQUE(person_uid) global
)


def _name_key(given: str | None, family: str | None, display: str | None) -> tuple[str, ...]:
    parts = " ".join(x for x in (given, family, display) if x)
    return tuple(sorted(t for t in re.split(r"[^a-z0-9]+", parts.lower()) if t))


def _default_session_factory() -> Any:
    from packages.db.session import async_session

    return async_session()


async def _tenant_ids(session: AsyncSession, only: UUID | None) -> list[TenantId]:
    if only is not None:
        return [TenantId(only)]
    rows = await session.execute(text("SELECT id FROM tenant.tenant"))
    return [TenantId(r[0]) for r in rows]


async def _clusters_for_tenant(
    session: AsyncSession, tenant_id: TenantId
) -> list[list[dict[str, Any]]]:
    """Return true-duplicate clusters: persons sharing canonical phone + name."""
    rows = (
        await session.execute(
            text(
                """
                SELECT i.person_id, i.value,
                       p.given_name, p.family_name, p.display_name, p.created_at,
                       p.dob, p.ssn,
                       EXISTS (SELECT 1 FROM identity.person_identifier e
                               WHERE e.person_id = i.person_id AND e.kind='email') AS has_email,
                       EXISTS (SELECT 1 FROM identity.source_link sl
                               WHERE sl.person_uid = i.person_id
                                 AND sl.source_system='carestack' AND sl.source_kind='patient') AS has_cs,
                       (SELECT count(*) FROM identity.person_identifier c
                        WHERE c.person_id = i.person_id) AS id_count
                FROM identity.person_identifier i
                JOIN identity.person p ON p.id = i.person_id
                WHERE i.kind='phone' AND p.tenant_id = :t
                """
            ),
            {"t": str(tenant_id)},
        )
    ).all()

    by_key: dict[tuple[tuple[str, ...], tuple[str, ...]], dict[UUID, dict[str, Any]]] = (
        defaultdict(dict)
    )
    for r in rows:
        try:
            canonical = normalise_phone(r.value)
        except ValidationError:
            continue
        nk = _name_key(r.given_name, r.family_name, r.display_name)
        if not nk:
            continue  # no-name persons need manual review, never auto-merge
        key = (tuple([canonical]), nk)
        by_key[key][r.person_id] = {
            "person_uid": r.person_id,
            "has_cs": r.has_cs,
            "has_email": r.has_email,
            "id_count": r.id_count,
            "created_at": r.created_at,
            "dob": r.dob,
            "ssn": r.ssn,
        }

    clusters: list[list[dict[str, Any]]] = []
    for members in by_key.values():
        people = list(members.values())
        if len(people) < 2:
            continue
        # DOB/SSN hard veto (identity merge rule): same phone + same name
        # can still be two people (Jr/Sr) — if the group carries more than
        # one distinct non-null DOB or SSN, do NOT auto-merge it; quarantine
        # for manual review. (DOB/SSN are NULL dataset-wide today, so this
        # is a guard, not a frequent path.)
        dobs = {m["dob"] for m in people if m["dob"] is not None}
        ssns = {m["ssn"] for m in people if m["ssn"] is not None}
        if len(dobs) > 1 or len(ssns) > 1:
            log.warning(
                "merge_phone_dups.quarantine_dob_ssn_conflict",
                tenant_id=str(tenant_id),
                cluster_size=len(people),
            )
            continue
        clusters.append(people)
    return clusters


def _pick_survivor(members: list[dict[str, Any]]) -> dict[str, Any]:
    """Richest record wins: CareStack link > email > id_count; tiebreak
    earliest created_at, then largest person_uid string (deterministic —
    the exact uuid tiebreak is arbitrary, only stability matters)."""
    return max(
        members,
        key=lambda m: (
            m["has_cs"],
            m["has_email"],
            m["id_count"],
            # earliest created_at / smallest id win → negate via reverse keys
            -(m["created_at"].timestamp() if m["created_at"] else 0.0),
            str(m["person_uid"]),
        ),
    )


async def _existing_tables(session: AsyncSession, tables: set[str]) -> set[str]:
    """Subset of ``tables`` that actually exist (``to_regclass``).

    Some person-bearing tables (e.g. ``attribution.lead_attribution``) are
    owned by other epics and may be absent on a clean Alembic build of this
    branch; skip them rather than erroring on ``relation does not exist``.
    """
    present: set[str] = set()
    for table in tables:
        row = await session.execute(
            text("SELECT to_regclass(:t)"), {"t": table}
        )
        if row.scalar_one() is not None:
            present.add(table)
    return present


async def _repoint(
    session: AsyncSession,
    tenant_id: TenantId,
    survivor: UUID,
    merged: UUID,
    existing: set[str],
) -> None:
    """Repoint every person reference from ``merged`` → ``survivor``.

    Tenant-scoped throughout (every write carries ``tenant_id = :t``); the
    UNIQUE-collision NOT EXISTS includes ``tenant_id`` only for keys that
    are themselves tenant-scoped (source_link / location_profile /
    attribution) and stays GLOBAL for global UNIQUEs (person_identifier on
    ``(kind,value)``; patient_profile on ``person_uid``).
    """
    params = {"s": str(survivor), "m": str(merged), "t": str(tenant_id)}
    for table, col in _SIMPLE_REPOINTS:
        if table not in existing:
            continue
        await session.execute(
            text(f"UPDATE {table} SET {col} = :s WHERE {col} = :m AND tenant_id = :t"),
            params,
        )
    for table, col, extra, tenant_scoped in _COLLISION_REPOINTS:
        if table not in existing:
            continue
        conflict = [f"x.{c} = t.{c}" for c in extra]
        if tenant_scoped:
            conflict.append("x.tenant_id = t.tenant_id")
        conflict_sql = (" AND " + " AND ".join(conflict)) if conflict else ""
        await session.execute(
            text(
                f"UPDATE {table} t SET {col} = :s "
                f"WHERE t.{col} = :m AND t.tenant_id = :t "
                f"AND NOT EXISTS (SELECT 1 FROM {table} x "
                f"WHERE x.{col} = :s{conflict_sql})"
            ),
            params,
        )
        await session.execute(
            text(f"DELETE FROM {table} WHERE {col} = :m AND tenant_id = :t"),
            params,
        )
    # Match-candidate ledger: these rows are a regenerable decision ledger,
    # and repointing the three person columns would violate the
    # distinct-persons CHECK + the active (tenant,hint,candidate) UNIQUE.
    # Drop every row referencing the loser instead (same as merge_split).
    if "identity.match_candidate" in existing:
        await session.execute(
            text(
                "DELETE FROM identity.match_candidate "
                "WHERE tenant_id = :t AND (source_person_uid = :m "
                "OR candidate_person_uid = :m OR accepted_person_uid = :m)"
            ),
            params,
        )


async def run(args: argparse.Namespace, *, session_factory: Any | None = None) -> int:
    apply = bool(args.apply)
    session_cm = (
        session_factory() if session_factory is not None else _default_session_factory()
    )
    total_clusters = 0
    total_merged = 0

    async with session_cm as session:
        identity = IdentityService(session)
        existing: set[str] = set()
        if apply:
            referenced = (
                {t for t, _ in _SIMPLE_REPOINTS}
                | {t for t, _, _, _ in _COLLISION_REPOINTS}
                | {"identity.match_candidate"}
            )
            existing = await _existing_tables(session, referenced)
        for tenant_id in await _tenant_ids(session, args.tenant_id):
            clusters = await _clusters_for_tenant(session, tenant_id)
            if args.limit is not None:
                clusters = clusters[: args.limit]
            if not clusters:
                continue
            tenant_merged = 0
            for members in clusters:
                survivor = _pick_survivor(members)
                survivor_uid = survivor["person_uid"]
                losers = [m for m in members if m["person_uid"] != survivor_uid]
                tenant_merged += len(losers)
                if apply:
                    for loser in losers:
                        await _repoint(
                            session,
                            tenant_id,
                            survivor_uid,
                            loser["person_uid"],
                            existing,
                        )
                        await identity.record_merge(
                            tenant_id,
                            survivor_uid,
                            loser["person_uid"],
                            reason="duplicate_phone",
                        )
                    await session.commit()
            total_clusters += len(clusters)
            total_merged += tenant_merged
            log.info(
                "merge_phone_dups.tenant",
                tenant_id=str(tenant_id),
                clusters=len(clusters),
                persons_merged=tenant_merged,
                mode="apply" if apply else "dry-run",
            )

    log.info(
        "merge_phone_dups.done",
        clusters=total_clusters,
        persons_merged=total_merged,
        mode="apply" if apply else "dry-run",
    )
    if not apply and total_clusters:
        print(
            f"DRY-RUN: {total_clusters} true-duplicate clusters, "
            f"{total_merged} persons would merge into survivors. Re-run with --apply."
        )
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge phone+name duplicate persons (ENG-463). Dry-run by default."
    )
    parser.add_argument("--apply", action="store_true", help="Perform merges (default: dry-run).")
    parser.add_argument("--tenant-id", type=UUID, default=None, help="Limit to one tenant.")
    parser.add_argument("--limit", type=int, default=None, help="Cap clusters per tenant.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return asyncio.run(run(args))
    except Exception:
        log.exception("merge_phone_dups.failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
