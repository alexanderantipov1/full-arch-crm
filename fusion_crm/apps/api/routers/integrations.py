"""Integrations HTTP routes — Salesforce provider surface.

Three surfaces live here today:

* **Pull / list** (slice 1 of W1, ENG-100): manual button to pull the N
  most recently created SF Leads.
* **OAuth Web Server Flow with PKCE** (ENG-149 / ENG-147 follow-up):
  ``connect/start`` mints the PKCE challenge and authorize URL;
  ``callback`` exchanges the auth code for access + refresh tokens and
  writes them to ``tenant.integration_credential``.
* **Operator actions on the card**: ``sync`` (manual pull alias) and
  ``DELETE /integrations/salesforce`` (revoke credential).

Routes are thin pass-throughs to services per ``apps/api/CLAUDE.md`` —
no business logic here.
"""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, Path, Query, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import (
    get_db,
    get_integration_service,
    get_principal_with_tenant,
    get_salesforce_client,
    get_sf_event_ingest_service,
    get_sf_lead_ingest_service,
    get_sf_task_ingest_service,
)
from packages.core.config import get_settings
from packages.core.exceptions import IntegrationError
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.ingest.schemas import (
    SalesforcePullOut,
    SfEventImportOut,
    SfLeadOut,
    SfTaskImportOut,
)
from packages.ingest.sf_event_service import SfEventIngestService
from packages.ingest.sf_lead_service import SfLeadIngestService
from packages.ingest.sf_task_service import SfTaskIngestService
from packages.integrations.salesforce import SfClient, SfNotConnectedError
from packages.integrations.salesforce.oauth import (
    build_authorize_url,
    exchange_code,
    generate_pkce_pair,
    load_client_config,
    persist_oauth_token,
)
from packages.integrations.service import IntegrationService, ProviderSyncStatus
from packages.tenant.credential_service import IntegrationCredentialService

router = APIRouter(prefix="/integrations/salesforce", tags=["integrations"])

log = get_logger("api.integrations.salesforce")

# Cookie that carries the PKCE verifier between ``connect/start`` and the
# OAuth ``callback``. HTTP-only + ``SameSite=Lax`` is the same shape the
# old Next.js handler used; we set ``secure`` automatically when running
# in production so a stray http:// load can never leak the verifier.
_PKCE_COOKIE = "sf_pkce_verifier"
_PKCE_COOKIE_MAX_AGE = 60 * 10  # 10 minutes — long enough for the consent screen
_PKCE_STATE_COOKIE = "sf_oauth_state"

LimitParam = Annotated[int, Query(ge=1, le=50)]
ServiceDep = Annotated[SfLeadIngestService, Depends(get_sf_lead_ingest_service)]
EventServiceDep = Annotated[
    SfEventIngestService, Depends(get_sf_event_ingest_service)
]
TaskServiceDep = Annotated[
    SfTaskIngestService, Depends(get_sf_task_ingest_service)
]
SalesforceClientDep = Annotated[SfClient, Depends(get_salesforce_client)]
PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]
IntegrationDep = Annotated[IntegrationService, Depends(get_integration_service)]
DaysParam = Annotated[int, Query(ge=1, le=30)]
EventLimitParam = Annotated[int, Query(ge=1, le=500)]
TaskSummaryLimitParam = Annotated[int, Query(ge=1, le=25)]
SfLeadIdPath = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{15,18}$")]


class SalesforceLeadOperationalSummaryOut(BaseModel):
    """Allowlisted live SF Lead fields for operator cards.

    This intentionally excludes raw/free-text provider payloads such as
    ``Description``. The full raw Lead stays behind the explicit ``/raw``
    inspector endpoint.
    """

    sf_lead_id: str
    salesforce_status: str | None = None
    salesforce_created_at: datetime | None = None
    status_last_updated_at: datetime | None = None
    source: str | None = None
    campaign: str | None = None
    owner: str | None = None
    owner_id: str | None = None
    treatment_coordinator: str | None = None
    assigned_center: str | None = None
    appointment_type: str | None = None
    attempt_count: int | None = None
    last_call_by: str | None = None
    unqualified_reason: str | None = None
    call_recording_url: str | None = None
    preferred_call_at: datetime | None = None
    hubspot_contact_id: str | None = None
    hubspot_created_at: datetime | None = None
    hubspot_lead_source: str | None = None
    record_source_detail: str | None = None
    old_lead_owner: str | None = None
    reactivated: bool | None = None
    carestack_id: str | None = None
    carestack_appointment_id: str | None = None
    carestack_status: str | None = None


class SalesforceLeadTaskSummaryOut(BaseModel):
    """Allowlisted Task call/activity row for person operational cards."""

    task_id: str
    task_kind: str
    task_label: str
    call_label: str
    # Concise human action classification (ENG — real-actions panel):
    # ``action_label`` = what was done ("Outbound call", "SMS sent",
    # "Call-now task", "Task"); ``outcome_label`` = how it ended
    # ("Connected", "No answer", "confirmation", "Pending", "Done");
    # ``direction`` ∈ {"inbound","outbound",None}.
    action_label: str
    outcome_label: str | None = None
    direction: str | None = None
    status: str | None = None
    due_date: date | None = None
    is_overdue: bool = False
    occurred_at: datetime | None = None
    owner_id: str | None = None
    agent: str | None = None
    outcome: str | None = None
    duration_label: str | None = None
    duration_seconds: int | None = None
    call_recording_url: str | None = None
    source: str | None = None
    business_unit: str | None = None
    language: str | None = None
    created_label: str | None = None


class SalesforceLeadTaskSummaryListOut(BaseModel):
    items: list[SalesforceLeadTaskSummaryOut]
    total: int


async def _expire_oauth_if_reconnect_required(
    exc: SfNotConnectedError,
    *,
    db: AsyncSession,
    principal: Principal,
) -> None:
    if exc.details.get("action") != "reconnect":
        return

    tenant_id = principal.require_tenant()
    expired_count = await IntegrationCredentialService(db).expire_active_for(
        tenant_id,
        "salesforce",
        "oauth_token",
        principal=principal,
    )
    log.info(
        "sf.oauth.marked_expired",
        tenant_id=str(tenant_id),
        expired_count=expired_count,
    )


def _platform_error_response(exc: IntegrationError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


_URL_RE = re.compile(r"https?://[^\s<>)\"']+")
_SF_TASK_COLUMNS = (
    "Id, Subject, Status, Priority, ActivityDate, CreatedDate, "
    "LastModifiedDate, WhoId, OwnerId, Type, TaskSubtype, CallType, "
    "CallDurationInSeconds, CallObject, CallDisposition, Description"
)
_DESCRIPTION_FIELD_RE = re.compile(
    r"(?im)^\s*(Agent|Outcome|Duration|Source|BU|Language|Created):\s*(.+?)\s*$"
)


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_string(record: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = _string_or_none(record.get(key))
        if value:
            return value
    return None


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _datetime_or_none(value: object) -> datetime | None:
    text = _string_or_none(value)
    if not text:
        return None
    normalised = text.replace("Z", "+00:00")
    if re.search(r"[+-]\d{4}$", normalised):
        normalised = f"{normalised[:-2]}:{normalised[-2:]}"
    try:
        return datetime.fromisoformat(normalised)
    except ValueError:
        return None


def _first_url(*values: object) -> str | None:
    for value in values:
        text = _string_or_none(value)
        if not text:
            continue
        match = _URL_RE.search(text)
        if match:
            return match.group(0).rstrip(".,")
    return None


def _lead_operational_summary(
    sf_lead_id: str,
    record: dict[str, object],
) -> SalesforceLeadOperationalSummaryOut:
    hubspot_source = _string_or_none(record.get("Hubspot_Lead_Source__c"))
    record_source_detail = _string_or_none(record.get("Record_Source_Detail__c"))
    return SalesforceLeadOperationalSummaryOut(
        sf_lead_id=sf_lead_id,
        salesforce_status=_first_string(record, "Status", "Lead_Status__c"),
        salesforce_created_at=_datetime_or_none(record.get("CreatedDate")),
        status_last_updated_at=_datetime_or_none(record.get("Status_Last_Updated__c")),
        source=_first_string(
            record,
            "LeadSource",
            "Hubspot_Lead_Source__c",
            "Record_Source_Detail__c",
            "first_touch_source__c",
            "last_touch_source__c",
            "referral_source__c",
            "utm_source__c",
            "Utm_source_text__c",
        ),
        campaign=_first_string(
            record,
            "CampaignName",
            "CampaignId",
            "Campaign__c",
            "Campaign_Name__c",
            "utm_campaign__c",
            "last_touch_campaign__c",
            "first_touch_campaign__c",
            "campaign__c",
        ),
        owner=_first_string(record, "Lead_Owner__c", "OwnerName", "Owner"),
        owner_id=_string_or_none(record.get("OwnerId")),
        treatment_coordinator=_first_string(
            record,
            "Treatment_Coordinator__c",
            "TreatmentCoordinator__c",
            "TC__c",
            "TC_Name__c",
        ),
        assigned_center=_string_or_none(record.get("Assigned_Center__c")),
        appointment_type=_first_string(
            record,
            "Appointment_Type__c",
            "Consultation_Type__c",
            "Virtual_Consultation__c",
        ),
        attempt_count=_int_or_none(record.get("Attempt_Count_c__c")),
        last_call_by=_first_string(
            record,
            "Last_Call_Display__c",
            "Last_Call_By_Type__c",
            "Last_Call_By_Code__c",
            "Last_Call_By__c",
        ),
        unqualified_reason=_first_string(
            record,
            "Unqualified_Reason__c",
            "Old_Reason_c__c",
        ),
        call_recording_url=_first_url(
            record.get("Call_Recording__c"),
            record.get("Lead_Summary__c"),
        ),
        preferred_call_at=_datetime_or_none(record.get("Preferred_Call_DateTime__c")),
        hubspot_contact_id=_first_string(
            record,
            "HS_Contact_ID__c",
            "Hubspot_Contact_Id__c",
            "HubSpot_Contact_Id__c",
        ),
        hubspot_created_at=_datetime_or_none(record.get("Hubspot_Created_Date__c")),
        hubspot_lead_source=hubspot_source,
        record_source_detail=record_source_detail,
        old_lead_owner=_string_or_none(record.get("old_lead_owner__c")),
        reactivated=_bool_or_none(record.get("Reactivated__c")),
        carestack_id=_first_string(record, "Carestack_ID__c", "CareStack_ID__c"),
        carestack_appointment_id=_string_or_none(
            record.get("CareStack_Appointment_Id__c")
        ),
        carestack_status=_string_or_none(record.get("CareStack_Status__c")),
    )


def _lead_tasks_soql(sf_lead_id: str, limit: int) -> str:
    return (
        f"SELECT {_SF_TASK_COLUMNS} FROM Task "
        f"WHERE WhoId = '{sf_lead_id}' "
        "ORDER BY ActivityDate DESC NULLS LAST, CreatedDate DESC "
        f"LIMIT {limit}"
    )


def _task_operational_summary(record: dict[str, object]) -> SalesforceLeadTaskSummaryOut:
    metadata = _task_description_metadata(record.get("Description"))
    call_url = _first_url(record.get("CallObject")) or _call_recording_url_from_metadata(
        metadata
    )
    duration_seconds = _int_or_none(record.get("CallDurationInSeconds"))
    metadata_duration = metadata.get("duration_seconds")
    if duration_seconds is None and isinstance(metadata_duration, int):
        duration_seconds = metadata_duration
    due_date = _date_or_none(record.get("ActivityDate"))
    task_kind = _task_kind(record)
    task_label = _task_label(record.get("Subject"), task_kind)
    action_label, outcome_label, direction = _classify_action(record, metadata)
    return SalesforceLeadTaskSummaryOut(
        task_id=_string_or_none(record.get("Id")) or "",
        task_kind=task_kind,
        task_label=task_label,
        call_label=task_label,
        action_label=action_label,
        outcome_label=outcome_label,
        direction=direction,
        status=_string_or_none(record.get("Status")),
        due_date=due_date,
        is_overdue=_is_overdue_task(record.get("Status"), due_date),
        occurred_at=_datetime_or_none(
            record.get("LastModifiedDate") or record.get("CreatedDate")
        ),
        owner_id=_string_or_none(record.get("OwnerId")),
        agent=_metadata_string(metadata, "agent"),
        outcome=_metadata_string(metadata, "outcome"),
        duration_label=_metadata_string(metadata, "duration_label"),
        duration_seconds=duration_seconds,
        call_recording_url=call_url,
        source=_metadata_string(metadata, "source"),
        business_unit=_metadata_string(metadata, "business_unit"),
        language=_metadata_string(metadata, "language"),
        created_label=_metadata_string(metadata, "created_label"),
    )


def _task_kind(record: dict[str, object]) -> str:
    subject = _string_or_none(record.get("Subject"))
    subtype = (_string_or_none(record.get("TaskSubtype")) or "").lower()
    # TaskSubtype is the authoritative SF call marker; keep this in sync
    # with ``_classify_action`` so a TaskSubtype=Call row without a
    # CallType/call-like subject is still counted as a call by the UI.
    if (
        subtype == "call"
        or _is_call_task_subject(subject)
        or _string_or_none(record.get("CallType"))
    ):
        return "call"
    return "followup"


def _task_label(subject: object, task_kind: str) -> str:
    text = _string_or_none(subject)
    if text and text.lower().startswith("sofia ai call"):
        return "Sofia AI Call"
    if text and "new lead" in text.lower() and "call now" in text.lower():
        return "New lead call-now task"
    return "Salesforce call" if task_kind == "call" else "Salesforce task"


_CALL_DISPOSITION_MAP = {
    "call connected": "Connected",
    "connected": "Connected",
    "answered": "Connected",
    "missed": "No answer",
    "no answer": "No answer",
    "noanswer": "No answer",
    "no response": "No answer",
    "left voicemail": "Voicemail",
    "voicemail": "Voicemail",
    "vm": "Voicemail",
    "busy": "Busy",
    "wrong number": "Wrong number",
    "wrong #": "Wrong number",
    "not in service": "Bad number",
}


def _call_outcome(disposition: str | None, status: str | None) -> str | None:
    """Human call outcome from CallDisposition, falling back to Status."""
    text = (disposition or "").strip()
    if text:
        return _CALL_DISPOSITION_MAP.get(text.lower(), text.title())
    if (status or "").strip().lower() == "completed":
        return "Completed"
    return None


def _sms_template(subject: str) -> str | None:
    """Pull the SMS template tag — "Outbound SMS SENT (confirmation)" → "confirmation"."""
    match = re.search(r"\(([^)]+)\)", subject)
    return match.group(1).strip() if match else None


def _classify_action(
    record: dict[str, object], metadata: dict[str, object]
) -> tuple[str, str | None, str | None]:
    """Map a SF Task into a concise (action_label, outcome_label, direction).

    Presentation-only. Uses the real SF call signals (TaskSubtype /
    CallType / CallDisposition) plus Subject keywords for SMS and the
    call-now routing task. ``direction`` ∈ {"inbound", "outbound", None}.
    """
    subject = _string_or_none(record.get("Subject")) or ""
    lower = subject.lower()
    call_type = (_string_or_none(record.get("CallType")) or "").lower()
    subtype = (_string_or_none(record.get("TaskSubtype")) or "").lower()
    disposition = _string_or_none(record.get("CallDisposition"))
    status = _string_or_none(record.get("Status"))

    direction: str | None = None
    if call_type in ("inbound", "outbound"):
        direction = call_type
    elif "inbound" in lower or lower.startswith("received"):
        direction = "inbound"
    elif "outbound" in lower:
        direction = "outbound"

    # SMS / text message.
    if "sms" in lower or "text message" in lower:
        label = "SMS reply" if direction == "inbound" else "SMS sent"
        outcome = _sms_template(subject) or _metadata_string(metadata, "outcome")
        return label, outcome, direction

    # Sofia AI automated call.
    if lower.startswith("sofia ai call"):
        return "Sofia AI call", _call_outcome(disposition, status), direction or "outbound"

    # Call-now routing task — a to-do, not a placed call (Subtype=Task).
    if "new lead" in lower and "call now" in lower:
        outcome = "Done" if (status or "").lower() == "completed" else "Pending"
        return "Call-now task", outcome, None

    # A real placed / received call.
    is_call = (
        subtype == "call"
        or call_type in ("inbound", "outbound")
        or disposition is not None
        or _is_call_task_subject(subject)
    )
    if is_call:
        if direction == "inbound":
            label = "Inbound call"
        elif direction == "outbound":
            label = "Outbound call"
        else:
            label = "Call"
        return label, _call_outcome(disposition, status), direction

    # Generic task.
    outcome = "Done" if (status or "").lower() == "completed" else (status or None)
    return "Task", outcome, None


def _is_call_task_subject(subject: str | None) -> bool:
    if subject is None:
        return False
    lower = subject.lower()
    return lower.startswith(("call", "voicemail", "inbound call", "outbound call", "sofia ai call"))


def _is_overdue_task(status: object, due_date: date | None) -> bool:
    if due_date is None:
        return False
    clean_status = (_string_or_none(status) or "").lower()
    if clean_status == "completed":
        return False
    return due_date < date.today()


def _date_or_none(value: object) -> date | None:
    text = _string_or_none(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _metadata_string(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None


def _task_description_metadata(value: object) -> dict[str, object]:
    if not isinstance(value, str) or not value.strip():
        return {}
    out: dict[str, object] = {}
    for match in _DESCRIPTION_FIELD_RE.finditer(value):
        key = match.group(1).lower()
        parsed = match.group(2).strip()
        if not parsed:
            continue
        if key == "agent":
            out["agent"] = parsed
        elif key == "outcome":
            out["outcome"] = parsed
        elif key == "duration":
            out["duration_label"] = parsed
            seconds = _duration_label_seconds(parsed)
            if seconds is not None:
                out["duration_seconds"] = seconds
        elif key == "source":
            out["source"] = parsed
        elif key == "bu":
            out["business_unit"] = parsed
        elif key == "language":
            out["language"] = parsed
        elif key == "created":
            out["created_label"] = parsed
    recording_url = _recording_url_from_description(value)
    if recording_url is not None:
        out["call_recording_url"] = recording_url
    return out


def _call_recording_url_from_metadata(metadata: dict[str, object]) -> str | None:
    return _metadata_string(metadata, "call_recording_url")


def _recording_url_from_description(value: str) -> str | None:
    match = re.search(r"(?im)^\s*Call Recording:\s*(https?://\S+)\s*$", value)
    if match is None:
        return None
    return match.group(1).rstrip(".,")


def _duration_label_seconds(value: str) -> int | None:
    match = re.fullmatch(
        r"(?i)\s*(\d+)\s*(sec|secs|second|seconds|min|mins|minute|minutes)\s*",
        value,
    )
    if match is None:
        return None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    return amount * 60 if unit.startswith("min") else amount


@router.post("/pull-recent")
async def pull_recent(
    svc: ServiceDep,
    principal: PrincipalDep,
    integration_svc: IntegrationDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: LimitParam = 5,
) -> Any:
    """Trigger a one-shot SOQL pull of the N most recent SF Leads.

    Returns the persisted ``SfLeadOut`` items + a count for the UI to display.
    """
    run: Any | None = None
    try:
        run = await integration_svc.open_provider_sync_run(
            principal.require_tenant(),
            provider="salesforce",
            object_scope="lead",
            trigger="manual",
        )
        items = await svc.pull_recent(principal.require_tenant(), limit)
    except SfNotConnectedError as exc:
        if run is not None:
            await integration_svc.close_provider_sync_run(
                principal.require_tenant(),
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope="lead",
                status="skipped_credential",
                records_total=0,
                records_succeeded=0,
                records_failed=0,
                error=exc,
            )
        await _expire_oauth_if_reconnect_required(exc, db=db, principal=principal)
        return _platform_error_response(exc)
    except Exception as exc:
        if run is not None:
            await integration_svc.close_provider_sync_run(
                principal.require_tenant(),
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope="lead",
                status="failed",
                records_total=0,
                records_succeeded=0,
                records_failed=1,
                error=exc,
            )
        raise
    assert run is not None
    await integration_svc.close_provider_sync_run(
        principal.require_tenant(),
        sync_run_id=run.id,
        principal=principal,
        provider="salesforce",
        object_scope="lead",
        status="succeeded",
        records_total=len(items),
        records_succeeded=len(items),
        records_failed=0,
    )
    return {
        "sync_run_id": str(run.id),
        "items": [i.model_dump(mode="json") for i in items],
        "pulled_count": len(items),
    }


@router.post("/import-events", response_model=SfEventImportOut)
async def import_events(
    svc: EventServiceDep,
    principal: PrincipalDep,
    integration_svc: IntegrationDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: DaysParam = 7,
    limit: EventLimitParam = 100,
) -> Any:
    """Capture SF Events via SOQL into ingest + ops.consultation (ENG-220).

    Idempotent — re-running upserts consultation rows rather than
    duplicating them. Events whose ``WhoId`` is not yet linked
    (lead/contact ingest has not run) are counted as skipped; use the
    combined ``/pull`` endpoint to sequence leads first.
    """
    run: Any | None = None
    try:
        run = await integration_svc.open_provider_sync_run(
            principal.require_tenant(),
            provider="salesforce",
            object_scope="event",
            trigger="manual",
        )
        result = await svc.import_recent_events(
            principal.require_tenant(),
            days=days,
            limit=limit,
        )
    except SfNotConnectedError as exc:
        if run is not None:
            await integration_svc.close_provider_sync_run(
                principal.require_tenant(),
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope="event",
                status="skipped_credential",
                records_total=0,
                records_succeeded=0,
                records_failed=0,
                error=exc,
            )
        await _expire_oauth_if_reconnect_required(exc, db=db, principal=principal)
        return _platform_error_response(exc)
    except Exception as exc:
        if run is not None:
            await integration_svc.close_provider_sync_run(
                principal.require_tenant(),
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope="event",
                status="failed",
                records_total=0,
                records_succeeded=0,
                records_failed=1,
                error=exc,
            )
        raise
    assert run is not None
    await integration_svc.close_provider_sync_run(
        principal.require_tenant(),
        sync_run_id=run.id,
        principal=principal,
        provider="salesforce",
        object_scope="event",
        status=_counter_status(
            result.imported_count,
            result.skipped_count,
            result.unchanged_count,
        ),
        records_total=result.queried_count,
        records_succeeded=result.imported_count,
        records_failed=result.skipped_count,
    )
    return result.model_copy(update={"sync_run_id": run.id})


@router.post("/import-tasks", response_model=SfTaskImportOut)
async def import_tasks(
    svc: TaskServiceDep,
    principal: PrincipalDep,
    integration_svc: IntegrationDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: DaysParam = 7,
    limit: EventLimitParam = 100,
) -> Any:
    """Capture SF Tasks into raw_event, ops follow-ups, and timeline events."""
    run: Any | None = None
    try:
        run = await integration_svc.open_provider_sync_run(
            principal.require_tenant(),
            provider="salesforce",
            object_scope="task",
            trigger="manual",
        )
        result = await svc.import_recent_tasks(
            principal.require_tenant(),
            days=days,
            limit=limit,
        )
    except SfNotConnectedError as exc:
        if run is not None:
            await integration_svc.close_provider_sync_run(
                principal.require_tenant(),
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope="task",
                status="skipped_credential",
                records_total=0,
                records_succeeded=0,
                records_failed=0,
                error=exc,
            )
        await _expire_oauth_if_reconnect_required(exc, db=db, principal=principal)
        return _platform_error_response(exc)
    except Exception as exc:
        if run is not None:
            await integration_svc.close_provider_sync_run(
                principal.require_tenant(),
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope="task",
                status="failed",
                records_total=0,
                records_succeeded=0,
                records_failed=1,
                error=exc,
            )
        raise
    assert run is not None
    await integration_svc.close_provider_sync_run(
        principal.require_tenant(),
        sync_run_id=run.id,
        principal=principal,
        provider="salesforce",
        object_scope="task",
        status=_counter_status(
            result.imported_count,
            result.skipped_count,
            result.unchanged_count,
        ),
        records_total=result.queried_count,
        records_succeeded=result.imported_count,
        records_failed=result.skipped_count,
    )
    return result.model_copy(update={"sync_run_id": run.id})


@router.post("/pull", response_model=SalesforcePullOut)
async def pull(
    lead_svc: ServiceDep,
    event_svc: EventServiceDep,
    principal: PrincipalDep,
    integration_svc: IntegrationDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: DaysParam = 7,
    lead_limit: LimitParam = 50,
    event_limit: EventLimitParam = 100,
) -> Any:
    """Combined Salesforce pull — leads first, then events.

    Sequencing matters: events link to persons via the lead/contact
    source_link, which must already exist. The combined endpoint enforces
    this so the operator can trigger a single "Sync" action and get both
    halves wired correctly. Mirrors `/integrations/carestack/pull`.
    """
    tenant_id = principal.require_tenant()
    run: Any | None = None
    try:
        run = await integration_svc.open_provider_sync_run(
            tenant_id,
            provider="salesforce",
            object_scope="lead,event",
            trigger="manual",
        )
        leads = await lead_svc.pull_recent(tenant_id, lead_limit)
        events = await event_svc.import_recent_events(
            tenant_id, days=days, limit=event_limit
        )
    except SfNotConnectedError as exc:
        if run is not None:
            await integration_svc.close_provider_sync_run(
                tenant_id,
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope="lead,event",
                status="skipped_credential",
                records_total=0,
                records_succeeded=0,
                records_failed=0,
                error=exc,
            )
        await _expire_oauth_if_reconnect_required(exc, db=db, principal=principal)
        return _platform_error_response(exc)
    except Exception as exc:
        if run is not None:
            await integration_svc.close_provider_sync_run(
                tenant_id,
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope="lead,event",
                status="failed",
                records_total=0,
                records_succeeded=0,
                records_failed=1,
                error=exc,
            )
        raise
    assert run is not None
    counters = _salesforce_counters(len(leads), events)
    await integration_svc.close_provider_sync_run(
        tenant_id,
        sync_run_id=run.id,
        principal=principal,
        provider="salesforce",
        object_scope="lead,event",
        status=_counter_status(
            counters["succeeded"], counters["failed"], counters["unchanged"]
        ),
        records_total=counters["total"],
        records_succeeded=counters["succeeded"],
        records_failed=counters["failed"],
    )
    return SalesforcePullOut(
        leads_imported=len(leads),
        events=events,
        sync_run_id=run.id,
    )


@router.get("/recent-leads")
async def recent_leads(
    svc: ServiceDep,
    principal: PrincipalDep,
    limit: LimitParam = 5,
) -> dict[str, list[SfLeadOut]]:
    """Read the N most recent SF-origin leads from local Postgres.

    Source of truth = SF; this is the cached view. The frontend renders this
    after a pull-recent mutation completes.
    """
    items = await svc.list_recent(principal.require_tenant(), limit)
    return {"items": items}


@router.get("/lead/{sf_lead_id}/raw")
async def lead_raw(
    sf_lead_id: SfLeadIdPath,
    sf: SalesforceClientDep,
    principal: PrincipalDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Fetch a single Lead from SF with ALL readable fields, NOT persisted.

    Live round-trip to Salesforce on every call. Used by the operator UI to
    show the full ~190-field payload on demand without bloating local DB.
    Returns the SF response as-is (envelope shape mirrors SF sObject Rows).
    """
    try:
        return await sf.get_object("Lead", sf_lead_id)
    except SfNotConnectedError as exc:
        await _expire_oauth_if_reconnect_required(exc, db=db, principal=principal)
        return _platform_error_response(exc)


@router.get("/opportunity/{sf_opportunity_id}/raw")
async def opportunity_raw(
    sf_opportunity_id: SfLeadIdPath,
    sf: SalesforceClientDep,
    principal: PrincipalDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Fetch a single Opportunity from SF with ALL readable fields, NOT persisted.

    Mirrors ``lead_raw``: live round-trip on every call, used to inspect
    attribution custom fields (utm_*, first/last touch) that the scheduled
    Opportunity pull does not project into local storage.
    """
    try:
        return await sf.get_object("Opportunity", sf_opportunity_id)
    except SfNotConnectedError as exc:
        await _expire_oauth_if_reconnect_required(exc, db=db, principal=principal)
        return _platform_error_response(exc)


@router.get(
    "/lead/{sf_lead_id}/operational-summary",
    response_model=SalesforceLeadOperationalSummaryOut,
)
async def lead_operational_summary(
    sf_lead_id: SfLeadIdPath,
    sf: SalesforceClientDep,
    principal: PrincipalDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Fetch one Lead and return only fields safe for the operational card."""
    try:
        record = await sf.get_object("Lead", sf_lead_id)
    except SfNotConnectedError as exc:
        await _expire_oauth_if_reconnect_required(exc, db=db, principal=principal)
        return _platform_error_response(exc)
    return _lead_operational_summary(sf_lead_id, record)


@router.get(
    "/lead/{sf_lead_id}/operational-tasks",
    response_model=SalesforceLeadTaskSummaryListOut,
)
async def lead_operational_tasks(
    sf_lead_id: SfLeadIdPath,
    sf: SalesforceClientDep,
    principal: PrincipalDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: TaskSummaryLimitParam = 10,
) -> Any:
    """Fetch recent Lead Tasks and return only safe call/activity metadata."""
    try:
        body = await sf.soql(_lead_tasks_soql(sf_lead_id, limit))
    except SfNotConnectedError as exc:
        await _expire_oauth_if_reconnect_required(exc, db=db, principal=principal)
        return _platform_error_response(exc)
    records = body.get("records", []) or []
    items = [
        _task_operational_summary(record)
        for record in records
        if isinstance(record, dict)
    ]
    return SalesforceLeadTaskSummaryListOut(items=items, total=len(items))


# ---------------------------------------------------------------- OAuth


@router.post("/connect/start")
async def connect_start(
    response: Response,
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Mint a PKCE pair, set HTTP-only cookies, return the SF authorize URL.

    The frontend (``apps/web/lib/api/hooks/useIntegrations.ts``) opens the
    returned URL in a new window/popup. After the operator approves the
    consent screen, Salesforce redirects back to
    ``GET /integrations/salesforce/callback`` (on the same host) — see
    :func:`oauth_callback`.

    Cookies persist the per-flow PKCE verifier and an opaque state token.
    Both are HTTP-only, ``SameSite=Lax``, ``Secure`` in production. The
    callback verifies the state cookie matches the ``state`` query param
    to neutralise CSRF / cross-flow confusion.
    """
    tenant_id = principal.require_tenant()
    cred_svc = IntegrationCredentialService(db)
    cfg = await load_client_config(cred_svc, tenant_id)

    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(24)
    authorize_url = build_authorize_url(cfg, challenge, state=state)

    secure = get_settings().is_production
    response.set_cookie(
        _PKCE_COOKIE,
        verifier,
        max_age=_PKCE_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )
    response.set_cookie(
        _PKCE_STATE_COOKIE,
        state,
        max_age=_PKCE_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )
    log.info("sf.oauth.connect_start", tenant_id=str(tenant_id))
    return {"kind": "oauth_redirect", "redirect_url": authorize_url}


@router.get("/callback")
async def oauth_callback(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
    pkce_verifier: Annotated[str | None, Cookie(alias=_PKCE_COOKIE)] = None,
    expected_state: Annotated[
        str | None, Cookie(alias=_PKCE_STATE_COOKIE)
    ] = None,
) -> RedirectResponse:
    """Exchange the auth code for tokens and persist to DB.

    Salesforce redirects the operator's browser here after consent. The
    handler validates the state cookie matches, exchanges ``code`` for
    tokens, writes ``(salesforce, oauth_token)`` to
    ``tenant.integration_credential``, and finally redirects back into
    the staff UI at ``/integrations``. Both PKCE cookies are cleared.

    The redirect target is a **relative** path so it always resolves
    against the host that served the OAuth flow. This sidesteps a class
    of bugs we hit on prod where ``OAUTH_REDIRECT_BASE_URL`` was set to
    a local-dev value and operators landed on ``localhost:3000`` after
    SF approve. The frontend reads ``?sf_oauth=connected`` or
    ``?sf_oauth_error=...`` and surfaces a toast either way.
    """
    tenant_id = principal.require_tenant()

    def _redirect_with_error(message: str) -> RedirectResponse:
        log.warning("sf.oauth.callback_error", message=message)
        target = f"/integrations?sf_oauth_error={message}"
        resp = RedirectResponse(target, status_code=302)
        resp.delete_cookie(_PKCE_COOKIE, path="/")
        resp.delete_cookie(_PKCE_STATE_COOKIE, path="/")
        return resp

    if error:
        return _redirect_with_error(error_description or error)
    if not code:
        return _redirect_with_error("missing_code")
    if not pkce_verifier:
        return _redirect_with_error("missing_pkce_cookie")
    if not state or not expected_state or state != expected_state:
        return _redirect_with_error("state_mismatch")

    cred_svc = IntegrationCredentialService(db)
    cfg = await load_client_config(cred_svc, tenant_id)
    try:
        token_response = await exchange_code(
            cfg, code=code, verifier=pkce_verifier
        )
        await persist_oauth_token(
            cred_svc, tenant_id, principal, token_response=token_response
        )
    except IntegrationError as exc:
        return _redirect_with_error(
            f"exchange_failed:{exc.code or 'integration_error'}"
        )

    resp = RedirectResponse(
        "/integrations?sf_oauth=connected", status_code=302
    )
    resp.delete_cookie(_PKCE_COOKIE, path="/")
    resp.delete_cookie(_PKCE_STATE_COOKIE, path="/")
    return resp


@router.post("/sync")
async def manual_sync(
    svc: Annotated[
        SfLeadIngestService, Depends(get_sf_lead_ingest_service)
    ],
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    integration_svc: IntegrationDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """Operator-initiated "Sync now" — runs the standard 5-Lead pull.

    Phase 1: the UI button on the provider card maps to a manual pull
    rather than a streaming sync. The cron-driven full sync arrives with
    the W1 slice-2 worker.
    """
    run: Any | None = None
    try:
        run = await integration_svc.open_provider_sync_run(
            principal.require_tenant(),
            provider="salesforce",
            object_scope="lead",
            trigger="manual",
        )
        items = await svc.pull_recent(principal.require_tenant(), limit=5)
    except SfNotConnectedError as exc:
        if run is not None:
            await integration_svc.close_provider_sync_run(
                principal.require_tenant(),
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope="lead",
                status="skipped_credential",
                records_total=0,
                records_succeeded=0,
                records_failed=0,
                error=exc,
            )
        await _expire_oauth_if_reconnect_required(exc, db=db, principal=principal)
        return _platform_error_response(exc)
    except Exception as exc:
        if run is not None:
            await integration_svc.close_provider_sync_run(
                principal.require_tenant(),
                sync_run_id=run.id,
                principal=principal,
                provider="salesforce",
                object_scope="lead",
                status="failed",
                records_total=0,
                records_succeeded=0,
                records_failed=1,
                error=exc,
            )
        raise
    assert run is not None
    await integration_svc.close_provider_sync_run(
        principal.require_tenant(),
        sync_run_id=run.id,
        principal=principal,
        provider="salesforce",
        object_scope="lead",
        status="succeeded",
        records_total=len(items),
        records_succeeded=len(items),
        records_failed=0,
    )
    return {
        "sync_run_id": str(run.id),
        "records_pulled": len(items),
    }


@router.delete("")
async def disconnect(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Soft-revoke the ``(salesforce, oauth_token)`` credential row.

    The operator clicks **Disconnect** on the provider card. We mark the
    row ``status='revoked'`` (via ``IntegrationCredentialService.delete``)
    rather than hard-deleting so the audit trail survives. The
    ``api_key`` row (app client_id/secret) is left intact — it is the
    bootstrap config, not a user session.

    Returns the placeholder shape the frontend already renders for a
    disconnected provider.
    """
    tenant_id = principal.require_tenant()
    cred_svc = IntegrationCredentialService(db)

    # Soft-revoke EVERY active ``(salesforce, oauth_token)`` row, not just
    # the most recent one. Upsert's "most-recent-active" matcher means a
    # legacy bootstrap row or a duplicate inserted during the historic
    # reconnect loop (before the prompt=consent fix) can leave one
    # active row behind even after the operator clicks Disconnect —
    # the next ``list_integrations`` then keeps reporting "connected"
    # and the operator can never get back to a clean state.
    rows = await cred_svc.list_for_tenant(
        tenant_id, provider_kind="salesforce"
    )
    targets = [
        r
        for r in rows
        if r.credential_kind == "oauth_token" and r.status == "active"
    ]
    for target in targets:
        await cred_svc.delete(target.id, tenant_id=tenant_id, principal=principal)
    log.info(
        "sf.oauth.disconnected",
        tenant_id=str(tenant_id),
        revoked_count=len(targets),
    )

    # Synthesise the same deterministic-disconnected UUID that
    # ``integrations_list`` uses so the frontend Zod parse accepts
    # the envelope and the table can match the row by id.
    # Namespace duplicated locally to avoid an import cycle.
    disconnected_ns = uuid.UUID("00000000-fde5-1c0f-5111-deadbeef0001")
    disconnected_id = uuid.uuid5(disconnected_ns, f"{tenant_id}:salesforce")
    return {
        "id": str(disconnected_id),
        "provider": "salesforce",
        "status": "disconnected",
        "display_name": None,
        "last_sync_at": None,
        "last_sync_summary": None,
        "error_message": None,
    }


def _counter_status(
    records_succeeded: int,
    records_failed: int,
    records_unchanged: int = 0,
) -> ProviderSyncStatus:
    # ENG-389: after the ENG-381/384 change-guard a steady-state run
    # imports nothing (everything is `unchanged`), so a single benign
    # skip must not flip the whole run to `failed` — unchanged rows are
    # proof the pull worked. `failed` is reserved for runs that produced
    # nothing at all; hard exceptions keep their explicit status.
    if records_failed > 0:
        if records_succeeded + records_unchanged > 0:
            return "partial"
        return "failed"
    return "succeeded"


def _salesforce_counters(leads_count: int, events: SfEventImportOut) -> dict[str, int]:
    unchanged = events.unchanged_count
    skipped = events.skipped_count
    if skipped == 0 and events.queried_count > events.imported_count + unchanged:
        skipped = events.queried_count - events.imported_count - unchanged
    return {
        "total": leads_count + events.queried_count,
        "succeeded": leads_count + events.imported_count,
        "failed": skipped,
        "unchanged": unchanged,
    }
