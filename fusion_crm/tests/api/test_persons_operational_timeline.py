"""HTTP tests for the person operational timeline read surface."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_actor_service,
    get_ingest_service,
    get_interaction_service,
    get_ops_service,
    get_principal_with_tenant,
    get_tenant_service,
)
from apps.api.routers import persons as persons_router
from apps.api.routers.persons import _curate_timeline_node_detail
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.interaction.schemas import (
    OperationalTimelineEntry,
    OperationalTimelineProjectionSnapshot,
)

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID = uuid.uuid4()
_LEAD_ID = uuid.uuid4()
_CONSULTATION_ID = uuid.uuid4()
_FOLLOWUP_ID = uuid.uuid4()


def _principal() -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="timeline@example.com",
        tenant_id=_TENANT_ID,
        roles=frozenset({Role.STAFF}),
    )


def _build_app(svc: MagicMock, ingest: MagicMock | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(persons_router.router)
    app.dependency_overrides[get_interaction_service] = lambda: svc
    app.dependency_overrides[get_principal_with_tenant] = _principal
    # ENG-418: the timeline route composes OpsService (current-owner) and
    # ActorService (display names); the inline-detail change adds IngestService
    # (raw_event reads) and TenantService (company timezone). Override all so
    # this stays a pure unit test and never opens a real DB connection
    # (otherwise the pooled asyncpg connection leaks across TestClient loops).
    ops = MagicMock()
    ops.get_current_funnel_owner = AsyncMock(return_value=None)
    ops.has_lead_for = AsyncMock(return_value=set())
    app.dependency_overrides[get_ops_service] = lambda: ops
    actor = MagicMock()
    actor.get_actor = AsyncMock(return_value=None)
    actor.resolve_actor_from_source = AsyncMock(return_value=None)
    app.dependency_overrides[get_actor_service] = lambda: actor
    if ingest is None:
        ingest = MagicMock()
        ingest.get_raw_event = AsyncMock(return_value=None)
    app.dependency_overrides[get_ingest_service] = lambda: ingest
    tenant = MagicMock()
    tenant.get_tenant = AsyncMock(
        return_value=SimpleNamespace(timezone="America/Los_Angeles")
    )
    app.dependency_overrides[get_tenant_service] = lambda: tenant
    return app


def test_person_operational_timeline_returns_mixed_ordered_entries() -> None:
    svc = MagicMock()
    svc.list_operational_timeline = AsyncMock(
        return_value=[
            OperationalTimelineEntry(
                kind="call_reference_found",
                occurred_at=datetime(2026, 6, 4, 12, 0, tzinfo=UTC),
                source_provider="salesforce",
                source_kind="salesforce_task",
                source_external_id="https://example.test/call/abc",
                data_class="call_recording_ref",
                review_status="pending_review",
                summary="Call reference found in Salesforce (id=00T-call)",
                projection=None,
            ),
            OperationalTimelineEntry(
                kind="task_created",
                occurred_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
                source_provider="salesforce",
                source_kind="salesforce_task",
                source_external_id="00T-task",
                data_class="operational",
                review_status="auto",
                summary="Task created in Salesforce (id=00T-task)",
                projection=OperationalTimelineProjectionSnapshot(
                    type="ops_followup_task",
                    id=_FOLLOWUP_ID,
                    status="open",
                    due_at=datetime(2026, 6, 5, 12, 0, tzinfo=UTC),
                ),
            ),
            OperationalTimelineEntry(
                kind="consultation_scheduled",
                occurred_at=datetime(2026, 6, 2, 12, 0, tzinfo=UTC),
                source_provider="carestack",
                source_kind="carestack_appointment",
                source_external_id="appt-123",
                data_class="operational",
                review_status="auto",
                summary="Consultation scheduled in CareStack (id=appt-123)",
                projection=OperationalTimelineProjectionSnapshot(
                    type="ops_consultation",
                    id=_CONSULTATION_ID,
                    status="scheduled",
                    scheduled_at=datetime(2026, 6, 6, 12, 0, tzinfo=UTC),
                ),
            ),
            OperationalTimelineEntry(
                kind="lead_created",
                occurred_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
                source_provider="salesforce",
                source_kind="salesforce_lead",
                source_external_id="00Q-lead",
                data_class="operational",
                review_status="auto",
                summary="Lead created from Salesforce (id=00Q-lead)",
                projection=OperationalTimelineProjectionSnapshot(
                    type="ops_lead",
                    id=_LEAD_ID,
                    status="new",
                ),
            ),
        ]
    )
    svc.count_for_person = AsyncMock(return_value=4)
    client = TestClient(_build_app(svc))

    res = client.get(f"/persons/{_PERSON_UID}/operational-timeline?limit=200")

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 4
    assert [item["kind"] for item in body["items"]] == [
        "call_reference_found",
        "task_created",
        "consultation_scheduled",
        "lead_created",
    ]
    assert body["items"][0]["review_status"] == "pending_review"
    assert body["items"][0]["source_external_id"] == "https://example.test/call/abc"
    assert body["items"][1]["projection"]["type"] == "ops_followup_task"
    assert body["items"][1]["projection"]["status"] == "open"
    assert body["items"][1]["projection"]["due_at"].startswith("2026-06-05T12:00:00")
    assert body["items"][2]["projection"]["type"] == "ops_consultation"
    assert body["items"][2]["projection"]["scheduled_at"].startswith("2026-06-06T12:00:00")
    assert body["items"][3]["projection"]["type"] == "ops_lead"
    assert body["items"][3]["projection"]["status"] == "new"
    svc.list_operational_timeline.assert_awaited_once_with(
        _TENANT_ID,
        _PERSON_UID,
        limit=200,
    )
    svc.count_for_person.assert_awaited_once_with(_TENANT_ID, _PERSON_UID)


def test_timeline_summary_stays_no_pii_even_when_detail_carries_it() -> None:
    """The curated ``detail`` may carry PII (dev-phase posture), but the
    stored ``summary`` must remain the no-PII verb+provider+id string, and
    the verbatim provider envelope (the raw ``attributes`` key) is never
    dumped — only curated label/value fields."""
    svc = MagicMock()
    svc.list_operational_timeline = AsyncMock(return_value=[_task_node()])
    svc.count_for_person = AsyncMock(return_value=1)
    ingest = MagicMock()
    ingest.get_raw_event = AsyncMock(
        return_value=_raw_event(
            {
                "Subject": "CALL NOW: Mairul Asim",
                "Description": "Phone: 2098897757 john@example.com",
                "Status": "Not Started",
                "attributes": {"type": "Task"},
            }
        )
    )
    client = TestClient(_build_app(svc, ingest))

    res = client.get(f"/persons/{_PERSON_UID}/operational-timeline")

    assert res.status_code == 200
    body = res.json()
    item = body["items"][0]
    # summary is the no-PII shell, never the patient name / contact.
    assert item["summary"] == "Task created in Salesforce (id=00TVw00000oFTT7MAO)"
    assert "Mairul" not in item["summary"]
    # The raw envelope noise key is never surfaced; only curated fields are.
    assert "attributes" not in res.text
    # The curated detail DOES carry the content (intended, dev-phase posture).
    assert item["detail"]["title"] == "CALL NOW: Mairul Asim"


def test_person_operational_timeline_accepts_limit_boundaries() -> None:
    svc = MagicMock()
    svc.list_operational_timeline = AsyncMock(return_value=[])
    svc.count_for_person = AsyncMock(return_value=0)
    client = TestClient(_build_app(svc))

    assert client.get(f"/persons/{_PERSON_UID}/operational-timeline?limit=1").status_code == 200
    assert client.get(f"/persons/{_PERSON_UID}/operational-timeline?limit=500").status_code == 200

    assert svc.list_operational_timeline.await_args_list[0].kwargs == {"limit": 1}
    assert svc.list_operational_timeline.await_args_list[1].kwargs == {"limit": 500}


def test_person_operational_timeline_rejects_out_of_range_limit() -> None:
    svc = MagicMock()
    svc.list_operational_timeline = AsyncMock(return_value=[])
    svc.count_for_person = AsyncMock(return_value=0)
    client = TestClient(_build_app(svc))

    assert client.get(f"/persons/{_PERSON_UID}/operational-timeline?limit=0").status_code == 422
    assert client.get(f"/persons/{_PERSON_UID}/operational-timeline?limit=501").status_code == 422
    svc.list_operational_timeline.assert_not_awaited()


# --- Curated node detail (raw_event projection, company-tz aware) --------


_TZ = ZoneInfo("America/Los_Angeles")
_RAW_EVENT_ID = uuid.uuid4()


def _task_node(
    *, source_event_id: uuid.UUID | None = _RAW_EVENT_ID
) -> OperationalTimelineEntry:
    return OperationalTimelineEntry(
        kind="task_created",
        occurred_at=datetime(2026, 6, 13, 5, 25, tzinfo=UTC),
        source_provider="salesforce",
        source_kind="salesforce_task",
        source_external_id="00TVw00000oFTT7MAO",
        source_event_id=source_event_id,
        data_class="operational",
        review_status="auto",
        summary="Task created in Salesforce (id=00TVw00000oFTT7MAO)",
        projection=None,
    )


def _raw_event(payload: dict[str, object]) -> MagicMock:
    raw = MagicMock()
    raw.payload = payload
    raw.received_at = datetime(2026, 6, 13, 5, 26, tzinfo=UTC)
    return raw


def test_curate_salesforce_task_title_status_completion_and_tz() -> None:
    payload = {
        "Id": "00TVw00000oFTT7MAO",
        "Type": "Call",
        "OwnerId": "005Vw000009ajRFIAY",
        "Subject": "NEW LEAD — CALL NOW: Mairul Asim",
        "Status": "Completed",
        "Priority": "High",
        "CallType": None,
        "Description": "first one to call wins",
        "ActivityDate": "2026-06-12",
        # SF sends UTC with a "+0000" offset → must convert to Pacific.
        "CreatedDate": "2026-06-13T05:25:59.000+0000",
        "attributes": {"type": "Task"},
    }
    detail = _curate_timeline_node_detail("salesforce_task", payload, _TZ)

    assert detail.title == "NEW LEAD — CALL NOW: Mairul Asim"
    assert detail.status == "Completed"
    assert detail.is_complete is True
    labels = {f.label: f.value for f in detail.fields}
    assert labels["Type"] == "Call"
    assert labels["Description"] == "first one to call wins"
    # Date-only → friendly date; UTC datetime → Pacific with abbreviation.
    assert labels["Activity date"] == "Jun 12, 2026"
    assert labels["Created"] == "Jun 12, 2026, 10:25 PM PDT"
    # Null fields and opaque ids / attributes are never rendered.
    assert "Call type" not in labels
    assert all(f.label != "OwnerId" for f in detail.fields)


def test_curate_task_not_completed_is_flagged_open() -> None:
    detail = _curate_timeline_node_detail(
        "salesforce_task", {"Subject": "x", "Status": "Not Started"}, _TZ
    )
    assert detail.status == "Not Started"
    assert detail.is_complete is False


def test_curate_carestack_appointment_naive_time_stays_local() -> None:
    payload = {
        "id": 11229619,
        "notes": "3:30pm {MK} by LL",
        "status": "Scheduled",
        "duration": 30,
        "providerIds": [26890],
        # CareStack sends naive local time → render as-is, no shift.
        "startDateTime": "2026-07-01T15:30:00",
    }
    detail = _curate_timeline_node_detail("carestack_appointment", payload, _TZ)

    assert detail.title == "3:30pm {MK} by LL"
    assert detail.status == "Scheduled"
    assert detail.is_complete is None  # appointments have no done/not-done flag
    labels = {f.label: f.value for f in detail.fields}
    assert labels["Start"] == "Jul 1, 2026, 3:30 PM PDT"
    assert labels["Provider id"] == "26890"


def test_curate_unknown_kind_falls_back_to_readable_scalars() -> None:
    payload = {
        "Name": "Acme",
        "flag": True,
        "nested": {"a": 1},
        "blank": "",
        "attributes": {"type": "Account"},
    }
    detail = _curate_timeline_node_detail("salesforce_account", payload, _TZ)

    assert detail.title is None
    labels = {f.label: f.value for f in detail.fields}
    assert labels["Name"] == "Acme"
    assert labels["flag"] == "Yes"
    # Nested objects, blank strings and the attributes noise key are dropped.
    assert "nested" not in labels
    assert "blank" not in labels
    assert "attributes" not in labels


def test_timeline_inlines_curated_detail_for_node_with_raw_event() -> None:
    svc = MagicMock()
    svc.list_operational_timeline = AsyncMock(return_value=[_task_node()])
    svc.count_for_person = AsyncMock(return_value=1)
    ingest = MagicMock()
    ingest.get_raw_event = AsyncMock(
        return_value=_raw_event(
            {"Subject": "Call now", "Type": "Call", "Status": "Completed"}
        )
    )
    client = TestClient(_build_app(svc, ingest))

    resp = client.get(f"/persons/{_PERSON_UID}/operational-timeline")

    assert resp.status_code == 200
    body = resp.json()
    assert body["timezone"] == "America/Los_Angeles"
    detail = body["items"][0]["detail"]
    assert detail["title"] == "Call now"
    assert detail["status"] == "Completed"
    assert detail["is_complete"] is True
    assert {"label": "Type", "value": "Call"} in detail["fields"]
    ingest.get_raw_event.assert_awaited_once_with(_TENANT_ID, _RAW_EVENT_ID)


def test_timeline_detail_is_null_when_node_has_no_raw_event() -> None:
    svc = MagicMock()
    svc.list_operational_timeline = AsyncMock(
        return_value=[_task_node(source_event_id=None)]
    )
    svc.count_for_person = AsyncMock(return_value=1)
    ingest = MagicMock()
    ingest.get_raw_event = AsyncMock(return_value=_raw_event({"Subject": "x"}))
    client = TestClient(_build_app(svc, ingest))

    resp = client.get(f"/persons/{_PERSON_UID}/operational-timeline")

    assert resp.status_code == 200
    assert resp.json()["items"][0]["detail"] is None
    # No raw row to fetch → ingest is never touched.
    ingest.get_raw_event.assert_not_awaited()


def test_timeline_detail_is_null_when_raw_event_missing() -> None:
    svc = MagicMock()
    svc.list_operational_timeline = AsyncMock(return_value=[_task_node()])
    svc.count_for_person = AsyncMock(return_value=1)
    ingest = MagicMock()
    ingest.get_raw_event = AsyncMock(return_value=None)
    client = TestClient(_build_app(svc, ingest))

    resp = client.get(f"/persons/{_PERSON_UID}/operational-timeline")

    assert resp.status_code == 200
    assert resp.json()["items"][0]["detail"] is None
