"""Workflow-ready ingest test fixtures.

These helpers intentionally live under ``tests/`` only. Provider payloads
mirror the fields consumed by the ingest services and keep free text out
unless a test explicitly opts into redaction-marker content.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.identity.schemas import PersonIdentifierIn, PersonIn
from packages.identity.service import IdentityService
from packages.tenant.models import Tenant


class FakeSfClient:
    """SOQL fake that returns records based on the requested object."""

    def __init__(
        self,
        *,
        leads: list[dict[str, Any]] | None = None,
        events: list[dict[str, Any]] | None = None,
        tasks: list[dict[str, Any]] | None = None,
        opportunities: list[dict[str, Any]] | None = None,
        cases: list[dict[str, Any]] | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.leads = leads or []
        self.events = events or []
        self.tasks = tasks or []
        self.opportunities = opportunities or []
        self.cases = cases or []
        self.error = error
        self.closed = False
        self.queries: list[str] = []

    async def describe(self, _resource: str) -> dict[str, Any]:
        # Empty describe → dynamic projection falls back to static (ENG-427).
        return {"fields": []}

    async def describe_tooling_fields(self, _resource: str) -> list[dict[str, Any]]:
        return []

    async def soql(self, query: str) -> dict[str, Any]:
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        if " FROM Lead " in f" {query} ":
            records = self.leads
        elif " FROM Event " in f" {query} ":
            records = self.events
        elif " FROM Task " in f" {query} ":
            records = self.tasks
        elif " FROM Opportunity " in f" {query} ":
            records = self.opportunities
        elif " FROM Case " in f" {query} ":
            records = self.cases
        else:
            records = []
        return {"records": records, "totalSize": len(records), "done": True}

    async def close(self) -> None:
        self.closed = True


class FakeCareStackClient:
    """CareStack fake for appointment sync pages."""

    def __init__(self, appointments: list[dict[str, Any]]) -> None:
        self.appointments = appointments

    async def list_appointments_modified_since(
        self,
        _modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]:
        _ = page_size, continue_token
        return {"appointments": self.appointments, "continueToken": None}


@asynccontextmanager
async def workflow_ready_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a real DB session or skip when local DB settings are unavailable."""
    try:
        from packages.db.session import SessionFactory, engine
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"database settings unavailable: {exc}")

    session = SessionFactory()
    try:
        await session.execute(sa.text("SELECT 1"))
    except OperationalError as exc:  # pragma: no cover - environment dependent
        await session.close()
        pytest.skip(f"database unavailable: {exc}")

    try:
        yield session
    finally:
        await session.rollback()
        await session.close()
        await engine.dispose()


async def seed_tenant(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    label: str = "workflow-ready",
) -> Tenant:
    suffix = uuid.uuid4().hex[:12]
    tenant = Tenant(
        id=tenant_id,
        slug=f"{label}-{suffix}",
        name=f"{label} integration tenant",
        primary_email=f"{label}-{suffix}@example.test",
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def seed_person_with_identifiers(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    email: str,
    phone: str = "+15551234567",
    given_name: str = "Workflow",
    family_name: str = "Ready",
) -> Any:
    return await IdentityService(session).create_person(
        tenant_id,
        PersonIn(
            given_name=given_name,
            family_name=family_name,
            display_name=f"{given_name} {family_name}",
            identifiers=[
                PersonIdentifierIn(kind="email", value=email),
                PersonIdentifierIn(kind="phone", value=phone),
            ],
        ),
    )


def make_sf_lead_payload(
    *,
    sf_id: str = "00QWORKFLOWLEAD",
    email: str = "workflow-ready@example.test",
    phone: str = "+15551234567",
    status: str = "Open",
    lead_source: str = "Web",
    created_at: str = "2036-06-01T10:00:00.000+0000",
    last_modified_at: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "Id": sf_id,
        "FirstName": "Workflow",
        "LastName": "Ready",
        "Email": email,
        "Phone": phone,
        "Company": "Fusion Test Fixture",
        "LeadSource": lead_source,
        "Status": status,
        "CreatedDate": created_at,
    }
    if last_modified_at is not None:
        payload["LastModifiedDate"] = last_modified_at
    if description is not None:
        payload["Description"] = description
    return payload


def make_sf_event_payload(
    *,
    event_id: str = "00UWORKFLOWEVENT",
    who_id: str | None = "00QWORKFLOWLEAD",
    scheduled_at: str = "2036-06-02T09:00:00Z",
    end_at: str = "2036-06-02T09:30:00Z",
    subject: str = "Initial consultation",
    event_type: str = "Initial Consultation",
    description: str | None = None,
) -> dict[str, Any]:
    return {
        "Id": event_id,
        "WhoId": who_id,
        "WhatId": "001WORKFLOWACCT",
        "StartDateTime": scheduled_at,
        "EndDateTime": end_at,
        "Subject": subject,
        "Type": event_type,
        "ActivityDate": scheduled_at[:10],
        "LastModifiedDate": "2036-05-30T10:00:00Z",
        "IsAllDayEvent": False,
        "ShowAs": "Busy",
        "Description": description,
    }


def make_carestack_appointment_payload(
    *,
    appointment_id: int | str = 7821,
    patient_id: int | str = 9985,
    scheduled_at: str = "2036-06-03T11:00:00Z",
    duration: int = 45,
    status: str = "Scheduled",
    location_id: int = 10029,
    notes: str | None = None,
) -> dict[str, Any]:
    return {
        "id": appointment_id,
        "patientId": patient_id,
        "startDateTime": scheduled_at,
        "duration": duration,
        "status": status,
        "locationId": location_id,
        "providerIds": [1],
        "providerName": "Fixture Clinician",
        "notes": notes,
        "lastUpdatedOn": "2036-05-31T10:00:00Z",
    }


def make_sf_task_payload(
    *,
    task_id: str = "00TWORKFLOWTASK",
    who_id: str = "00QWORKFLOWLEAD",
    subject: str = "Follow up",
    status: str = "Open",
    priority: str = "Normal",
    activity_date: str = "2036-06-06",
    created_at: str = "2036-06-04T08:00:00.000+0000",
    last_modified_at: str = "2036-06-04T08:30:00.000+0000",
    call_type: str | None = None,
    call_duration_seconds: int | str | None = None,
    call_object: str | None = None,
    call_disposition: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    return {
        "Id": task_id,
        "Subject": subject,
        "Status": status,
        "Priority": priority,
        "ActivityDate": activity_date,
        "CreatedDate": created_at,
        "LastModifiedDate": last_modified_at,
        "WhoId": who_id,
        "WhatId": "001WORKFLOWACCT",
        "OwnerId": "005WORKFLOWOWNER",
        "Type": None,
        "CallType": call_type,
        "CallDurationInSeconds": call_duration_seconds,
        "CallObject": call_object,
        "CallDisposition": call_disposition,
        "Description": description,
    }


def assert_forbidden_markers_absent(rendered: str, markers: tuple[str, ...]) -> None:
    for marker in markers:
        assert marker not in rendered
