"""Workflow-ready redaction sweep coverage."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_interaction_service, get_principal_with_tenant
from apps.api.routers import persons as persons_router
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.identity.service import IdentityService
from packages.ingest.models import RawEvent
from packages.ingest.schemas import RawEventIn
from packages.ingest.service import IngestService
from packages.ingest.sf_event_service import SfEventIngestService
from packages.ingest.sf_task_service import SfTaskIngestService
from packages.interaction.models import EVENT_KINDS, Event
from packages.interaction.schemas import EventIn
from packages.interaction.service import InteractionService, summary_for_event
from packages.ops.models import ConsultationStatus
from packages.ops.schemas import ConsultationIn, FollowupTaskIn, LeadIn
from packages.ops.service import OpsService
from tests._fixtures.workflow_ready import (
    FakeSfClient,
    assert_forbidden_markers_absent,
    make_sf_event_payload,
    make_sf_task_payload,
    seed_person_with_identifiers,
    seed_tenant,
    workflow_ready_db_session,
)

_FORBIDDEN = (
    "PHI_MARKER_IMPLANT_PAIN",
    "PHI_MARKER_DIAGNOSIS",
    "PHI_MARKER_MEDICATION",
    "PHI_MARKER_TASK_DESCRIPTION",
    "surrounding free text",
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="workflow-redaction@example.test",
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


def _provider_for_kind(kind: str) -> tuple[str, str]:
    if kind.startswith("consultation_"):
        return "carestack", "carestack_appointment"
    if kind.startswith("task_") or kind.startswith("call_"):
        return "salesforce", "salesforce_task"
    return "salesforce", "salesforce_lead"


@pytest.mark.asyncio
async def test_seeded_event_kinds_keep_raw_payload_out_of_timeline_and_projections(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="workflow-ready-redaction")
    email = f"workflow-redaction-{uuid.uuid4().hex[:8]}@example.test"
    person = await seed_person_with_identifiers(db_session, tenant_id, email=email)
    ingest = IngestService(db_session)
    ops = OpsService(db_session)
    interaction = InteractionService(db_session)

    lead = await ops.create_lead(
        tenant_id,
        LeadIn(person_uid=person.id, source="redaction-sweep", extra={"safe": True}),
    )
    raw_for_consultation = await ingest.capture(
        tenant_id,
        RawEventIn(
            source="carestack",
            event_type="redaction.seed.consultation",
            external_id=f"raw-consultation-{uuid.uuid4().hex[:8]}",
            received_at=datetime.now(UTC),
            payload={"notes": "PHI_MARKER_IMPLANT_PAIN must stay raw"},
        ),
    )
    consultation = (
        await ops.upsert_consultation_from_hint(
            tenant_id,
            ConsultationIn(
                person_uid=person.id,
                source_provider="carestack",
                source_instance="carestack-main",
                external_id=f"redaction-consultation-{uuid.uuid4().hex[:8]}",
                scheduled_at=datetime(2026, 6, 8, 12, 0, tzinfo=UTC),
                duration_minutes=30,
                status=ConsultationStatus.SCHEDULED,
                raw_event_id=raw_for_consultation.id,
            ),
        )
    ).consultation
    followup = await ops.create_followup(
        tenant_id,
        FollowupTaskIn(
            person_uid=person.id,
            title="Salesforce follow-up task",
            description=None,
            due_at=datetime(2026, 6, 9, 12, 0, tzinfo=UTC),
        ),
    )

    projection_by_kind = {
        "lead_created": ("ops_lead", lead.id),
        "lead_updated": ("ops_lead", lead.id),
        "consultation_scheduled": ("ops_consultation", consultation.id),
        "consultation_created": ("ops_consultation", consultation.id),
        "consultation_rescheduled": ("ops_consultation", consultation.id),
        "consultation_cancelled": ("ops_consultation", consultation.id),
        "consultation_completed": ("ops_consultation", consultation.id),
        "consultation_no_show": ("ops_consultation", consultation.id),
        "task_created": ("ops_followup_task", followup.id),
    }

    for index, kind in enumerate(EVENT_KINDS):
        provider, source_kind = _provider_for_kind(kind)
        raw_event = await ingest.capture(
            tenant_id,
            RawEventIn(
                source=provider,
                event_type=f"redaction.seed.{kind}",
                external_id=f"raw-{kind}-{uuid.uuid4().hex[:8]}",
                received_at=datetime.now(UTC),
                payload={
                    "raw_event": "PHI_MARKER_DIAGNOSIS must stay raw",
                    "clinical": "PHI_MARKER_MEDICATION must stay raw",
                },
            ),
        )
        projection_ref_type, projection_ref_id = projection_by_kind.get(
            kind,
            (None, None),
        )
        await interaction.create_event(
            tenant_id,
            EventIn(
                person_uid=person.id,
                kind=kind,
                source_provider=provider,
                source_event_id=raw_event.id,
                data_class=(
                    "call_recording_ref"
                    if kind == "call_reference_found"
                    else "operational"
                ),
                source_kind=source_kind,
                source_external_id=f"{kind}-{index}",
                projection_ref_type=projection_ref_type,
                projection_ref_id=projection_ref_id,
                review_status=(
                    "pending_review" if kind == "call_reference_found" else "auto"
                ),
                occurred_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
                + timedelta(minutes=index),
                summary=summary_for_event(
                    kind=kind,
                    source_provider=provider,
                    source_id=f"{kind}-{index}",
                ),
                payload={"safe_marker": kind},
            ),
        )

    app = _build_app(db_session, tenant_id)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/persons/{person.id}/operational-timeline?limit=50")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(EVENT_KINDS)
    assert {item["kind"] for item in body["items"]} == set(EVENT_KINDS)
    rendered = response.text
    assert "payload" not in rendered
    assert "raw_event" not in rendered
    assert_forbidden_markers_absent(rendered, _FORBIDDEN)

    events = (
        await db_session.execute(
            select(Event)
            .where(Event.tenant_id == tenant_id)
            .where(Event.person_uid == person.id)
        )
    ).scalars().all()
    for event in events:
        assert_forbidden_markers_absent(event.summary, _FORBIDDEN)

    projection_rendered = f"{lead.extra} {lead.notes} {consultation.model_dump()}"
    assert_forbidden_markers_absent(projection_rendered, _FORBIDDEN)


@pytest.mark.asyncio
async def test_provider_descriptions_stay_raw_while_call_reference_is_allowlisted(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="workflow-ready-redaction-provider")
    email = f"workflow-redaction-provider-{uuid.uuid4().hex[:8]}@example.test"
    person = await seed_person_with_identifiers(db_session, tenant_id, email=email)
    sf_lead_id = f"00Q{uuid.uuid4().hex[:10]}"
    await IdentityService(db_session).add_source_link(
        tenant_id,
        person.id,
        "salesforce",
        "lead",
        sf_lead_id,
    )

    zoom_url = "https://fusion.zoom.us/j/987654321"
    sf_event_id = f"00U{uuid.uuid4().hex[:10]}"
    await SfEventIngestService(
        db_session,
        FakeSfClient(
            events=[
                make_sf_event_payload(
                    event_id=sf_event_id,
                    who_id=sf_lead_id,
                    description=(
                        "PHI_MARKER_IMPLANT_PAIN surrounding free text "
                        f"{zoom_url} PHI_MARKER_DIAGNOSIS"
                    ),
                )
            ]
        ),
    ).import_recent_events(tenant_id, days=7)

    task_id = f"00T{uuid.uuid4().hex[:10]}"
    await SfTaskIngestService(
        db_session,
        FakeSfClient(
            tasks=[
                make_sf_task_payload(
                    task_id=task_id,
                    who_id=sf_lead_id,
                    subject="Outbound call with safe classification only",
                    status="Completed",
                    call_type="Outbound",
                    call_object="https://recordings.example.test/calls/task-call-1",
                    description="PHI_MARKER_TASK_DESCRIPTION must stay raw only",
                )
            ]
        ),
    ).import_recent_tasks(tenant_id, days=7)

    raw_events = (
        await db_session.execute(
            select(RawEvent)
            .where(RawEvent.tenant_id == tenant_id)
            .where(RawEvent.external_id.in_([sf_event_id, task_id]))
        )
    ).scalars().all()
    raw_rendered = " ".join(str(raw.payload) for raw in raw_events)
    assert "PHI_MARKER_IMPLANT_PAIN" in raw_rendered
    assert "PHI_MARKER_TASK_DESCRIPTION" in raw_rendered

    events = (
        await db_session.execute(
            select(Event)
            .where(Event.tenant_id == tenant_id)
            .where(Event.person_uid == person.id)
        )
    ).scalars().all()
    rendered_events = " ".join(
        f"{event.kind} {event.summary} {event.payload}" for event in events
    )
    assert zoom_url in rendered_events
    assert "https://recordings.example.test/calls/task-call-1" in rendered_events
    assert_forbidden_markers_absent(rendered_events, _FORBIDDEN)

    zoom_reference = next(
        event
        for event in events
        if event.kind == "call_reference_found"
        and event.source_kind == "salesforce_event"
    )
    assert zoom_reference.payload["url"] == zoom_url
    assert zoom_reference.payload["provider"] == "zoom"
    assert "surrounding free text" not in str(zoom_reference.payload)

    app = _build_app(db_session, tenant_id)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/persons/{person.id}/operational-timeline")

    assert response.status_code == 200
    rendered_timeline = response.text
    assert zoom_url not in rendered_timeline
    assert "https://recordings.example.test/calls/task-call-1" not in rendered_timeline
    assert_forbidden_markers_absent(rendered_timeline, _FORBIDDEN)
