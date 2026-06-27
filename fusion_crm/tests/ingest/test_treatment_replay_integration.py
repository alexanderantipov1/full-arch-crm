"""Real-PG integration coverage for the ENG-540 treatment-procedure replay.

Exercises ``CareStackTreatmentIngestService.reproject_treatments_from_raw``
against a real PostgreSQL test DB (auto-skips when no DB is configured, like
the rest of the workflow-ready integration suite):

* a historical implant procedure (statusId=2, implant CDT) that a normal
  re-pull would dedup-skip emits ``surgery_scheduled`` on replay;
* the replay is idempotent — a second pass over the same raw_events emits ZERO
  new events (relies on ``create_event_idempotent``);
* a non-implant procedure replays to the generic ``treatment_proposed`` mapping
  and never produces a ``surgery_*`` event.

The replay reads ``ingest.raw_event`` only; catalog codes are seeded directly so
no CareStack client is needed (self-fill stays closed via a no-by-id stub).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import func, select

from packages.catalog.models import ProcedureCode
from packages.core.types import TenantId
from packages.identity.service import IdentityService
from packages.ingest.carestack_treatment_service import (
    CareStackTreatmentIngestService,
)
from packages.ingest.schemas import RawEventIn
from packages.ingest.service import IngestService
from packages.interaction.models import Event
from tests._fixtures.workflow_ready import (
    seed_person_with_identifiers,
    seed_tenant,
    workflow_ready_db_session,
)

_TREATMENT_PROCEDURE_EVENT_TYPE = "carestack.treatment_procedure.upsert"
_PATIENT_ID = "9985"
_IMPLANT_PROCEDURE_ID = "77001"
_NON_IMPLANT_PROCEDURE_ID = "77002"
_IMPLANT_CODE_ID = 117408
_NON_IMPLANT_CODE_ID = 555


class _NoByIdClient:
    """CareStack stub the replay never pulls; no by-id self-fill surface."""

    async def list_treatment_procedures_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]:  # pragma: no cover - must never be called
        raise AssertionError("replay must not pull the CareStack feed")


def _procedure_row(
    *,
    procedure_id: str,
    status_id: int,
    procedure_code_id: int,
) -> dict[str, Any]:
    """A treatment-procedure payload carrying PHI-shaped fields (forensic)."""
    return {
        "id": int(procedure_id),
        "patientId": int(_PATIENT_ID),
        "locationId": 10029,
        "statusId": status_id,
        "procedureCodeId": procedure_code_id,
        "dateOfService": "2026-05-22T14:00:00Z",
        "lastUpdatedOn": "2026-05-22T14:01:00Z",
        # PHI-shaped fields stay in raw only.
        "toothNumber": "14",
        "notes": "must NEVER reach timeline",
    }


async def _seed_catalog(session: Any) -> None:
    session.add(
        ProcedureCode(
            carestack_code_id=_IMPLANT_CODE_ID,
            code="D6010",
            description="Surgical placement of implant body",
        )
    )
    session.add(
        ProcedureCode(
            carestack_code_id=_NON_IMPLANT_CODE_ID,
            code="D0120",
            description="Periodic oral evaluation",
        )
    )
    await session.flush()


async def _replay_once(session: Any, tenant_id: TenantId) -> None:
    """Run one full replay sweep over the captured rows and commit."""
    page = await IngestService(session).list_latest_by_type_paginated(
        tenant_id,
        event_type=_TREATMENT_PROCEDURE_EVENT_TYPE,
        limit=500,
    )
    rows = [(raw_event_id, payload) for raw_event_id, _external_id, payload in page]
    svc = CareStackTreatmentIngestService(
        session=session, carestack_client=_NoByIdClient()
    )
    await svc.reproject_treatments_from_raw(tenant_id, rows=rows)
    await session.commit()


async def _count_events(session: Any, tenant_id: TenantId, person_uid: Any, kind: str) -> int:
    stmt = (
        select(func.count())
        .select_from(Event)
        .where(Event.tenant_id == tenant_id)
        .where(Event.person_uid == person_uid)
        .where(Event.kind == kind)
    )
    return int((await session.execute(stmt)).scalar_one())


@pytest.mark.asyncio
async def test_replay_backfills_surgery_events_and_is_idempotent() -> None:
    tenant_id = TenantId(uuid.uuid4())
    async with workflow_ready_db_session() as session:
        await seed_tenant(session, tenant_id, label="eng540-replay")
        person = await seed_person_with_identifiers(
            session,
            tenant_id,
            email=f"eng540-{uuid.uuid4().hex[:8]}@example.test",
        )
        await IdentityService(session).add_source_link(
            tenant_id,
            person.id,
            source_system="carestack",
            source_kind="patient",
            source_id=_PATIENT_ID,
            source_instance="carestack-main",
        )
        await _seed_catalog(session)

        ingest = IngestService(session)
        # Historical implant surgery (statusId=2) + a non-implant procedure,
        # captured as raw exactly as the OLD ingest logic would have.
        for procedure_id, code_id in (
            (_IMPLANT_PROCEDURE_ID, _IMPLANT_CODE_ID),
            (_NON_IMPLANT_PROCEDURE_ID, _NON_IMPLANT_CODE_ID),
        ):
            await ingest.capture(
                tenant_id,
                RawEventIn(
                    source="carestack",
                    event_type=_TREATMENT_PROCEDURE_EVENT_TYPE,
                    external_id=procedure_id,
                    received_at=datetime.now(UTC),
                    payload=_procedure_row(
                        procedure_id=procedure_id,
                        status_id=2,
                        procedure_code_id=code_id,
                    ),
                ),
            )
        await session.commit()

        # First replay — the implant procedure emits surgery_scheduled.
        await _replay_once(session, tenant_id)

        assert await _count_events(session, tenant_id, person.id, "surgery_scheduled") == 1
        # The non-implant procedure stayed generic — no surgery event for it.
        assert await _count_events(session, tenant_id, person.id, "surgery_completed") == 0
        assert await _count_events(session, tenant_id, person.id, "treatment_proposed") == 1

        # Second replay over the same raw_events emits ZERO new events.
        await _replay_once(session, tenant_id)

        assert await _count_events(session, tenant_id, person.id, "surgery_scheduled") == 1
        assert await _count_events(session, tenant_id, person.id, "treatment_proposed") == 1

        # No surgical PHI leaked into the emitted event payload.
        surgery_event = (
            await session.execute(
                select(Event)
                .where(Event.tenant_id == tenant_id)
                .where(Event.person_uid == person.id)
                .where(Event.kind == "surgery_scheduled")
            )
        ).scalar_one()
        assert surgery_event.payload == {"is_implant_surgery": True}
        assert surgery_event.source_external_id == _IMPLANT_PROCEDURE_ID
