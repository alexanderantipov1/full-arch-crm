"""End-to-end workflow-ready ingest fixture coverage."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_interaction_service, get_principal_with_tenant
from apps.api.routers import persons as persons_router
from apps.worker.jobs.ingest_scheduled import pull_salesforce_for_tenant
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.identity.models import SourceLink
from packages.identity.service import IdentityService
from packages.ingest.carestack_appointment_service import CareStackAppointmentIngestService
from packages.ingest.sf_event_service import SfEventIngestService
from packages.ingest.sf_lead_service import SfLeadIngestService
from packages.ingest.sf_task_service import SfTaskIngestService
from packages.integrations.models import SyncRun
from packages.interaction.models import Event
from packages.interaction.service import InteractionService
from packages.ops.models import Consultation, FollowupTask, Lead
from packages.ops.service import OpsService
from packages.tenant.credential_service import NoCredentialError
from tests._fixtures.workflow_ready import (
    FakeCareStackClient,
    FakeSfClient,
    assert_forbidden_markers_absent,
    make_carestack_appointment_payload,
    make_sf_event_payload,
    make_sf_lead_payload,
    make_sf_task_payload,
    seed_person_with_identifiers,
    seed_tenant,
    workflow_ready_db_session,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="workflow-ready@example.test",
        tenant_id=tenant_id,
        roles=frozenset({Role.STAFF}),
    )


def _build_app(session: AsyncSession, tenant_id: TenantId) -> FastAPI:
    app = FastAPI()
    app.include_router(persons_router.router)
    app.dependency_overrides[get_principal_with_tenant] = lambda: _principal(tenant_id)
    app.dependency_overrides[get_interaction_service] = lambda: InteractionService(
        session,
        operational_projection_reader=OpsService(session),
    )
    return app


async def _events_for_person(
    session: AsyncSession,
    tenant_id: TenantId,
    person_uid: uuid.UUID,
) -> list[Event]:
    rows = await session.execute(
        select(Event)
        .where(Event.tenant_id == tenant_id)
        .where(Event.person_uid == person_uid)
        .order_by(Event.occurred_at.asc())
    )
    return list(rows.scalars().all())


@asynccontextmanager
async def _worker_session(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield session


@pytest.mark.asyncio
async def test_workflow_ready_ingest_surfaces_safe_operational_timeline(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id)
    suffix = uuid.uuid4().hex[:10]
    sf_lead_id = f"00Q{suffix}"
    cs_patient_id = f"98{suffix[:6]}"
    email = f"workflow-ready-{suffix}@example.test"
    person = await seed_person_with_identifiers(db_session, tenant_id, email=email)
    await IdentityService(db_session).add_source_link(
        tenant_id,
        person.id,
        "carestack",
        "patient",
        cs_patient_id,
    )

    lead_payload = make_sf_lead_payload(
        sf_id=sf_lead_id,
        email=email,
        description="lead free text must remain raw only",
    )
    lead_result = await SfLeadIngestService(
        db_session,
        FakeSfClient(leads=[lead_payload]),
    ).pull_recent(tenant_id, limit=1)

    assert len(lead_result) == 1
    assert lead_result[0].person_uid == person.id
    lead_event = (await _events_for_person(db_session, tenant_id, person.id))[0]
    assert lead_event.kind == "lead_created"
    assert lead_event.source_kind == "salesforce_lead"
    assert lead_event.source_external_id == sf_lead_id
    assert lead_event.projection_ref_type == "ops_lead"
    lead = (
        await db_session.execute(
            select(Lead)
            .where(Lead.tenant_id == tenant_id)
            .where(Lead.person_uid == person.id)
        )
    ).scalar_one()
    assert lead_event.projection_ref_id == lead.id
    source_link = (
        await db_session.execute(
            select(SourceLink)
            .where(SourceLink.tenant_id == tenant_id)
            .where(SourceLink.source_system == "salesforce")
            .where(SourceLink.source_kind == "lead")
            .where(SourceLink.source_id == sf_lead_id)
        )
    ).scalar_one()
    assert source_link.person_uid == person.id

    sf_event_id = f"00U{suffix}"
    await SfEventIngestService(
        db_session,
        FakeSfClient(
            events=[
                make_sf_event_payload(
                    event_id=sf_event_id,
                    who_id=sf_lead_id,
                    description="event free text must remain raw only",
                )
            ]
        ),
    ).import_recent_events(tenant_id, days=7)
    sf_consultation = (
        await db_session.execute(
            select(Consultation)
            .where(Consultation.tenant_id == tenant_id)
            .where(Consultation.source_provider == "salesforce")
            .where(Consultation.external_id == sf_event_id)
        )
    ).scalar_one()
    assert sf_consultation.person_uid == person.id

    cs_appointment_id = f"78{suffix[:6]}"
    await CareStackAppointmentIngestService(
        db_session,
        FakeCareStackClient(
            [
                make_carestack_appointment_payload(
                    appointment_id=cs_appointment_id,
                    patient_id=cs_patient_id,
                    notes="appointment notes must remain raw only",
                )
            ]
        ),
    ).import_recent_appointments(tenant_id, days=7)

    task_id = f"00T{suffix}A"
    await SfTaskIngestService(
        db_session,
        FakeSfClient(
            tasks=[
                make_sf_task_payload(
                    task_id=task_id,
                    who_id=sf_lead_id,
                    subject="Action-oriented follow up text",
                    description="task description must remain raw only",
                )
            ]
        ),
    ).import_recent_tasks(tenant_id, days=7)
    followup = (
        await db_session.execute(
            select(FollowupTask)
            .where(FollowupTask.tenant_id == tenant_id)
            .where(FollowupTask.person_uid == person.id)
        )
    ).scalar_one()
    assert followup.title == "Salesforce follow-up task"
    assert followup.description is None

    call_task_id = f"00T{suffix}B"
    await SfTaskIngestService(
        db_session,
        FakeSfClient(
            tasks=[
                make_sf_task_payload(
                    task_id=call_task_id,
                    who_id=sf_lead_id,
                    subject="Outbound call",
                    status="Completed",
                    last_modified_at="2036-06-05T08:30:00.000+0000",
                    call_type="Outbound",
                    call_duration_seconds=95,
                    call_disposition="Connected",
                    call_object="https://recordings.example.test/calls/abc123",
                    description="call description must remain raw only",
                )
            ]
        ),
    ).import_recent_tasks(tenant_id, days=7)

    events = await _events_for_person(db_session, tenant_id, person.id)
    assert [event.kind for event in events] == [
        "lead_created",
        "consultation_scheduled",
        "consultation_scheduled",
        "task_created",
        "call_logged",
        "call_reference_found",
    ]

    app = _build_app(db_session, tenant_id)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/persons/{person.id}/operational-timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 6
    items = body["items"]
    assert {items[0]["kind"], items[1]["kind"]} == {
        "call_logged",
        "call_reference_found",
    }
    assert [item["kind"] for item in items[2:]] == [
        "task_created",
        "consultation_scheduled",
        "consultation_scheduled",
        "lead_created",
    ]
    assert items[2]["projection"]["type"] == "ops_followup_task"
    assert items[2]["projection"]["status"] == "open"
    assert items[3]["projection"]["type"] == "ops_consultation"
    assert items[4]["projection"]["type"] == "ops_consultation"
    assert items[5]["projection"]["type"] == "ops_lead"
    assert items[5]["projection"]["status"] == "new"

    rendered = response.text
    assert "payload" not in rendered
    assert_forbidden_markers_absent(
        rendered,
        (
            "free text",
            "description must remain raw",
            "notes must remain raw",
            email,
        ),
    )


@pytest.mark.asyncio
async def test_scheduled_salesforce_pull_sync_run_lifecycle_cross_check(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="workflow-ready-sync")

    successful_client = FakeSfClient(
        leads=[
            make_sf_lead_payload(
                sf_id=f"00Q{uuid.uuid4().hex[:10]}",
                email=f"sync-success-{uuid.uuid4().hex[:8]}@example.test",
            )
        ]
    )
    partial_client = FakeSfClient(
        leads=[
            make_sf_lead_payload(
                sf_id=f"00Q{uuid.uuid4().hex[:10]}",
                email=f"sync-partial-{uuid.uuid4().hex[:8]}@example.test",
            )
        ],
        events=[make_sf_event_payload(event_id=f"00U{uuid.uuid4().hex[:10]}", who_id=None)],
    )
    failed_client = FakeSfClient(error=TimeoutError("provider timeout"))
    clients = [successful_client, partial_client, failed_client]

    async def _read_for(
        _tenant_id: TenantId,
        _provider: str,
        kind: str,
    ) -> dict[str, object]:
        if kind == "oauth_token":
            return {"access_token": "token", "instance_url": "https://example.test"}
        if kind == "api_key":
            return {"client_id": "client", "client_secret": "secret"}
        raise NoCredentialError("missing credential", details={"kind": kind})

    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        side_effect=lambda: _worker_session(db_session),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationCredentialService"
    ) as cred_cls, patch(
        "apps.worker.jobs.ingest_scheduled.SfClient.from_credential",
        side_effect=clients,
    ):
        cred_cls.return_value.read_for = AsyncMock(side_effect=_read_for)
        cred_cls.return_value.upsert = AsyncMock()

        success = await pull_salesforce_for_tenant({}, str(tenant_id))
        partial = await pull_salesforce_for_tenant({}, str(tenant_id))
        with pytest.raises(TimeoutError):
            await pull_salesforce_for_tenant({}, str(tenant_id))

    with patch(
        "apps.worker.jobs.ingest_scheduled.async_session",
        side_effect=lambda: _worker_session(db_session),
    ), patch(
        "apps.worker.jobs.ingest_scheduled.IntegrationCredentialService"
    ) as cred_cls:
        cred_cls.return_value.read_for = AsyncMock(
            side_effect=NoCredentialError(
                "no salesforce credential",
                details={"provider": "salesforce"},
            )
        )
        skipped = await pull_salesforce_for_tenant({}, str(tenant_id))

    assert success["leads_imported"] == 1
    assert partial["events"]["skipped_count"] == 1
    assert skipped == {"skipped": "no_credential"}

    runs = (
        await db_session.execute(
            select(SyncRun)
            .where(SyncRun.tenant_id == tenant_id)
            .where(
                SyncRun.sf_object
                == "lead,event,task,opportunity,case,contact,account,opportunity_history"
            )
            .order_by(SyncRun.created_at.asc())
        )
    ).scalars().all()
    by_status = {run.status: run for run in runs}
    assert set(by_status) == {
        "succeeded",
        "partial",
        "failed",
        "skipped_credential",
    }
    assert by_status["succeeded"].records_total == 1
    assert by_status["succeeded"].records_succeeded == 1
    assert by_status["succeeded"].records_failed == 0
    assert by_status["partial"].records_total == 2
    assert by_status["partial"].records_succeeded == 1
    assert by_status["partial"].records_failed == 1
    assert by_status["failed"].records_total == 0
    assert by_status["failed"].records_succeeded == 0
    assert by_status["failed"].records_failed == 1
    assert by_status["skipped_credential"].records_total == 0
    assert by_status["skipped_credential"].records_failed == 0
    assert "provider timeout" in (by_status["failed"].error or "")
