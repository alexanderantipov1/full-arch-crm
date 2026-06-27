"""Backfill ops.consultation doctor name + source_status (ENG-487).

Two phases, idempotent:

1. **Provider -> actor sync.** For every ``ingest.carestack_provider`` row,
   ensure an ``actor.actor`` + ``actor_identifier`` (kind
   ``carestack_provider_id``) exists with the canonical display name. This is
   what the LIVE appointment ingest resolver (ENG-465) reads, so the forward
   path starts populating ``provider_clinician_name`` for new pulls too.

2. **Consultation backfill.** For every CareStack consultation, re-resolve the
   doctor name from its raw ``providerIds[0]`` via the populated provider
   catalog, and copy the verbatim raw ``status`` into the new ``source_status``
   column. The bucketed ``status`` is left untouched.

Run (against the local stack)::

    PYTHONPATH=$(pwd) .venv/bin/python infra/scripts/backfill_consultation_doctor_status.py \
        --tenant 11111111-1111-4111-8111-111111111111

Add ``--dry-run`` to report counts without writing.
"""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select, update

from packages.actor.service import ActorService
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.ingest.carestack_appointment_service import (
    _first_provider_id,
    _source_status,
)
from packages.ingest.models import CareStackProvider, RawEvent
from packages.ingest.repository import IngestRepository
from packages.ops.models import Consultation

log = get_logger("backfill.consultation_doctor_status")

_SOURCE_INSTANCE = "carestack-main"
_BATCH = 500


async def _sync_providers_to_actors(
    session, tenant_id: TenantId, *, dry_run: bool
) -> int:
    """Phase 1 — ensure an actor exists for every catalog provider."""
    repo = IngestRepository(session)
    rows = (
        await session.execute(
            select(
                CareStackProvider.provider_carestack_id,
                CareStackProvider.provider_type,
            ).where(CareStackProvider.tenant_id == tenant_id)
        )
    ).all()
    ids = [r.provider_carestack_id for r in rows]
    types = {r.provider_carestack_id: r.provider_type for r in rows}
    names = await repo.lookup_provider_names(tenant_id, ids)

    actors = ActorService(session)
    synced = 0
    for pid in ids:
        name = names.get(pid)
        if not name:
            continue
        if dry_run:
            synced += 1
            continue
        await actors.resolve_actor_from_source(
            tenant_id,
            source_provider="carestack",
            source_instance=_SOURCE_INSTANCE,
            external_id=str(pid),
            name_hint=name,
            role_hint=types.get(pid),
        )
        synced += 1
    if not dry_run:
        await session.commit()
    log.info("backfill.providers_synced", tenant_id=str(tenant_id), count=synced)
    return synced


async def _backfill_consultations(
    session, tenant_id: TenantId, *, dry_run: bool
) -> tuple[int, int, int]:
    """Phase 2 — set provider_clinician_name + source_status per consultation."""
    repo = IngestRepository(session)
    # Prefetch the full id -> display-name map once (catalog is tiny).
    all_ids = [
        r.provider_carestack_id
        for r in (
            await session.execute(
                select(CareStackProvider.provider_carestack_id).where(
                    CareStackProvider.tenant_id == tenant_id
                )
            )
        ).all()
    ]
    name_by_id = await repo.lookup_provider_names(tenant_id, all_ids)

    scanned = doctor_set = status_set = 0
    last_id: UUID | None = None
    while True:
        stmt = (
            select(Consultation.id, RawEvent.payload)
            .join(RawEvent, RawEvent.id == Consultation.raw_event_id)
            .where(
                Consultation.tenant_id == tenant_id,
                Consultation.source_provider == "carestack",
            )
            .order_by(Consultation.id)
            .limit(_BATCH)
        )
        if last_id is not None:
            stmt = stmt.where(Consultation.id > last_id)
        batch = (await session.execute(stmt)).all()
        if not batch:
            break
        for cons_id, payload in batch:
            last_id = cons_id
            scanned += 1
            payload = payload or {}
            values: dict[str, object] = {}

            raw_status = _source_status(payload.get("status"))
            if raw_status is not None:
                values["source_status"] = raw_status
                status_set += 1

            pid = _first_provider_id(payload)
            name = name_by_id.get(pid) if pid is not None else None
            if name:
                values["provider_clinician_name"] = name
                doctor_set += 1

            if values and not dry_run:
                await session.execute(
                    update(Consultation)
                    .where(Consultation.id == cons_id)
                    .values(**values)
                )
        if not dry_run:
            await session.commit()
        log.info(
            "backfill.consultations_progress",
            scanned=scanned,
            doctor_set=doctor_set,
            status_set=status_set,
        )
    return scanned, doctor_set, status_set


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True, help="tenant UUID")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    tenant_id = TenantId(UUID(args.tenant))

    async with async_session() as session:
        providers = await _sync_providers_to_actors(
            session, tenant_id, dry_run=args.dry_run
        )
        scanned, doctor_set, status_set = await _backfill_consultations(
            session, tenant_id, dry_run=args.dry_run
        )

    print(
        f"providers_synced={providers} scanned={scanned} "
        f"doctor_set={doctor_set} source_status_set={status_set} "
        f"dry_run={args.dry_run}"
    )


if __name__ == "__main__":
    asyncio.run(main())
