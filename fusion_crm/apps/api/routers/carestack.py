"""CareStack HTTP routes — operator-facing read-only inspector surface.

Implements the four endpoints called out in ENG-145 PR-2:

* ``GET /integrations/carestack/recent-patients`` — Patient Sync feed for the
  last N days. Renders the local-dev inspector list.
* ``GET /integrations/carestack/recent-appointments`` — Appointment Sync feed
  for the last N days.
* ``GET /integrations/carestack/patient/{id}/raw`` — single Patient record
  fetched live from CareStack and returned verbatim.
* ``GET /integrations/carestack/appointment/{id}/raw`` — single Appointment
  record fetched live from CareStack and returned verbatim.

Credentials come from ``tenant.integration_credential`` (seeded by the
``tenant_credentials_seed`` migration). No env-fallback path: in
production the migration must have run; in local dev the same seed
runs against the local stack.

PHI carve-out: the returned payloads include patient PHI (DOB, phone,
email, address). They cross the boundary into the staff browser because
the operator is the authorised reader; production deployments rely on
the staff portal's auth gate to keep that audience scoped. These
endpoints MUST NOT be reused by any AI-agent tool.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query

from apps.api.dependencies import (
    CareStackClientFactory,
    get_carestack_appointment_ingest_service,
    get_carestack_client_factory,
    get_carestack_patient_ingest_service,
    get_integration_service,
    get_location_service,
    get_principal_with_tenant,
)
from packages.core.exceptions import IntegrationError
from packages.core.security import Principal
from packages.ingest.carestack_appointment_service import (
    CareStackAppointmentIngestService,
)
from packages.ingest.carestack_patient_service import CareStackPatientIngestService
from packages.ingest.schemas import (
    CareStackAppointmentImportOut,
    CareStackPatientImportOut,
    CareStackPullOut,
)
from packages.integrations.carestack.exceptions import (
    CareStackApiError,
    CareStackNotConnectedError,
)
from packages.integrations.service import IntegrationService, ProviderSyncStatus
from packages.tenant.service import LocationService

router = APIRouter(prefix="/integrations/carestack", tags=["integrations"])

# Operator-tunable knobs. The Phase 1 inspector UI never asks for more
# than 7 days / 100 rows; clamp upstream to keep one round-trip cheap.
# Query alias ``pageSize`` matches the frontend hook in
# ``apps/web/lib/api/hooks/useCareStack.ts``.
DaysParam = Annotated[int, Query(ge=1, le=30, description="modifiedSince offset")]
PageSizeParam = Annotated[
    int, Query(alias="pageSize", ge=1, le=500, description="CareStack pageSize")
]
MaxPagesParam = Annotated[
    int, Query(alias="maxPages", ge=1, le=20, description="CareStack max pages")
]
PatientIdParam = Annotated[
    str,
    Path(description="CareStack patientId — integer or string id as the upstream emits it"),
]
AppointmentIdParam = Annotated[
    str,
    Path(description="CareStack AppointmentId"),
]
IntegrationDep = Annotated[IntegrationService, Depends(get_integration_service)]


async def _open_client(factory: CareStackClientFactory) -> Any:
    """Build the client via the factory; let resolver/credential errors bubble."""
    try:
        return await factory()
    except CareStackNotConnectedError as exc:
        # Translate to the platform's IntegrationError so the middleware
        # emits a 409 envelope with the missing-fields detail.
        raise IntegrationError(
            "carestack not connected",
            details=dict(exc.details) if exc.details else {},
        ) from exc


@router.get("/recent-patients")
async def recent_patients(
    factory: Annotated[CareStackClientFactory, Depends(get_carestack_client_factory)],
    _principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    days: DaysParam = 7,
    page_size: PageSizeParam = 100,
) -> dict[str, object]:
    """Return CareStack patients modified in the last ``days`` days.

    The response wraps the upstream Sync body verbatim under ``data`` —
    the operator UI's ``normalisePatients`` walks the raw envelope
    (CareStack returns ``{"results": [...], "continueToken": "..."}``).
    Field names mirror the frontend hook in
    ``apps/web/lib/api/hooks/useCareStack.ts``: ``modifiedSince``,
    ``pageSize``, ``data``.
    """
    client = await _open_client(factory)
    try:
        since = datetime.now(UTC) - timedelta(days=days)
        body = await client.list_patients_modified_since(since, page_size=page_size)
    except CareStackNotConnectedError as exc:
        raise IntegrationError(
            "carestack not connected",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    except CareStackApiError as exc:
        raise IntegrationError(
            "carestack request failed",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    finally:
        await client.close()

    return {
        "modifiedSince": since.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "pageSize": page_size,
        "data": body,
    }


@router.get("/recent-appointments")
async def recent_appointments(
    factory: Annotated[CareStackClientFactory, Depends(get_carestack_client_factory)],
    _principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    days: DaysParam = 7,
    page_size: PageSizeParam = 100,
) -> dict[str, object]:
    client = await _open_client(factory)
    try:
        since = datetime.now(UTC) - timedelta(days=days)
        body = await client.list_appointments_modified_since(since, page_size=page_size)
    except CareStackNotConnectedError as exc:
        raise IntegrationError(
            "carestack not connected",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    except CareStackApiError as exc:
        raise IntegrationError(
            "carestack request failed",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    finally:
        await client.close()

    return {
        "modifiedSince": since.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "pageSize": page_size,
        "data": body,
    }


@router.post("/import-patients", response_model=CareStackPatientImportOut)
async def import_patients(
    svc: Annotated[
        CareStackPatientIngestService,
        Depends(get_carestack_patient_ingest_service),
    ],
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    integration_svc: IntegrationDep,
    days: DaysParam = 7,
    page_size: PageSizeParam = 100,
    max_pages: MaxPagesParam = 1,
) -> CareStackPatientImportOut:
    """Capture CareStack Patient Sync rows into ingest.raw_event + hints."""
    tenant_id = principal.require_tenant()
    run = await integration_svc.open_provider_sync_run(
        tenant_id,
        provider="carestack",
        object_scope="patient",
        trigger="manual",
    )
    try:
        result = await svc.import_recent_patients(
            tenant_id,
            days=days,
            page_size=page_size,
            max_pages=max_pages,
        )
    except CareStackNotConnectedError as exc:
        await integration_svc.close_provider_sync_run(
            tenant_id,
            sync_run_id=run.id,
            principal=principal,
            provider="carestack",
            object_scope="patient",
            status="skipped_credential",
            records_total=0,
            records_succeeded=0,
            records_failed=0,
            error=exc,
        )
        raise IntegrationError(
            "carestack not connected",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    except CareStackApiError as exc:
        await integration_svc.close_provider_sync_run(
            tenant_id,
            sync_run_id=run.id,
            principal=principal,
            provider="carestack",
            object_scope="patient",
            status="failed",
            records_total=0,
            records_succeeded=0,
            records_failed=1,
            error=exc,
        )
        raise IntegrationError(
            "carestack request failed",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    except Exception as exc:
        await integration_svc.close_provider_sync_run(
            tenant_id,
            sync_run_id=run.id,
            principal=principal,
            provider="carestack",
            object_scope="patient",
            status="failed",
            records_total=0,
            records_succeeded=0,
            records_failed=1,
            error=exc,
        )
        raise
    await integration_svc.close_provider_sync_run(
        tenant_id,
        sync_run_id=run.id,
        principal=principal,
        provider="carestack",
        object_scope="patient",
        status=_counter_status(result.imported_count, result.skipped_count),
        records_total=result.imported_count + result.skipped_count,
        records_succeeded=result.imported_count,
        records_failed=result.skipped_count,
    )
    return result.model_copy(update={"sync_run_id": run.id})


@router.post("/import-appointments", response_model=CareStackAppointmentImportOut)
async def import_appointments(
    svc: Annotated[
        CareStackAppointmentIngestService,
        Depends(get_carestack_appointment_ingest_service),
    ],
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    integration_svc: IntegrationDep,
    days: DaysParam = 7,
    page_size: PageSizeParam = 100,
    max_pages: MaxPagesParam = 1,
) -> CareStackAppointmentImportOut:
    """Capture CareStack Appointment Sync rows into ingest + ops.consultation.

    Idempotent — re-running the endpoint upserts existing consultation rows
    rather than duplicating them. Appointments referencing patients that
    have not been ingested yet are counted as skipped; run
    ``import-patients`` first or use the combined ``pull`` endpoint.
    """
    tenant_id = principal.require_tenant()
    run = await integration_svc.open_provider_sync_run(
        tenant_id,
        provider="carestack",
        object_scope="appointment",
        trigger="manual",
    )
    try:
        result = await svc.import_recent_appointments(
            tenant_id,
            days=days,
            page_size=page_size,
            max_pages=max_pages,
        )
    except CareStackNotConnectedError as exc:
        await integration_svc.close_provider_sync_run(
            tenant_id,
            sync_run_id=run.id,
            principal=principal,
            provider="carestack",
            object_scope="appointment",
            status="skipped_credential",
            records_total=0,
            records_succeeded=0,
            records_failed=0,
            error=exc,
        )
        raise IntegrationError(
            "carestack not connected",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    except CareStackApiError as exc:
        await integration_svc.close_provider_sync_run(
            tenant_id,
            sync_run_id=run.id,
            principal=principal,
            provider="carestack",
            object_scope="appointment",
            status="failed",
            records_total=0,
            records_succeeded=0,
            records_failed=1,
            error=exc,
        )
        raise IntegrationError(
            "carestack request failed",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    except Exception as exc:
        await integration_svc.close_provider_sync_run(
            tenant_id,
            sync_run_id=run.id,
            principal=principal,
            provider="carestack",
            object_scope="appointment",
            status="failed",
            records_total=0,
            records_succeeded=0,
            records_failed=1,
            error=exc,
        )
        raise
    await integration_svc.close_provider_sync_run(
        tenant_id,
        sync_run_id=run.id,
        principal=principal,
        provider="carestack",
        object_scope="appointment",
        status=_counter_status(result.imported_count, result.skipped_count),
        records_total=result.imported_count + result.skipped_count,
        records_succeeded=result.imported_count,
        records_failed=result.skipped_count,
    )
    return result.model_copy(update={"sync_run_id": run.id})


@router.post("/pull", response_model=CareStackPullOut)
async def pull(
    location_svc: Annotated[LocationService, Depends(get_location_service)],
    patient_svc: Annotated[
        CareStackPatientIngestService,
        Depends(get_carestack_patient_ingest_service),
    ],
    appointment_svc: Annotated[
        CareStackAppointmentIngestService,
        Depends(get_carestack_appointment_ingest_service),
    ],
    factory: Annotated[CareStackClientFactory, Depends(get_carestack_client_factory)],
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    integration_svc: IntegrationDep,
    days: DaysParam = 7,
    page_size: PageSizeParam = 100,
    max_pages: MaxPagesParam = 1,
) -> CareStackPullOut:
    """Combined CareStack pull — locations, then patients, then appointments.

    Sequencing matters: appointments link to clinic context via CareStack
    ``locationId`` and to persons via the patient source_link. The combined
    endpoint enforces both prerequisites for a single "Sync" action.
    """
    tenant_id = principal.require_tenant()
    run = await integration_svc.open_provider_sync_run(
        tenant_id,
        provider="carestack",
        object_scope="location,patient,appointment",
        trigger="manual",
    )
    client: Any | None = None
    try:
        client = await _open_client(factory)
        locations = await location_svc.import_locations_from_carestack(
            tenant_id, client, principal=principal
        )
        patients = await patient_svc.import_recent_patients(
            tenant_id,
            days=days,
            page_size=page_size,
            max_pages=max_pages,
        )
        appointments = await appointment_svc.import_recent_appointments(
            tenant_id,
            days=days,
            page_size=page_size,
            max_pages=max_pages,
        )
    except IntegrationError as exc:
        await integration_svc.close_provider_sync_run(
            tenant_id,
            sync_run_id=run.id,
            principal=principal,
            provider="carestack",
            object_scope="location,patient,appointment",
            status="skipped_credential",
            records_total=0,
            records_succeeded=0,
            records_failed=0,
            error=exc,
        )
        raise
    except CareStackNotConnectedError as exc:
        await integration_svc.close_provider_sync_run(
            tenant_id,
            sync_run_id=run.id,
            principal=principal,
            provider="carestack",
            object_scope="location,patient,appointment",
            status="skipped_credential",
            records_total=0,
            records_succeeded=0,
            records_failed=0,
            error=exc,
        )
        raise IntegrationError(
            "carestack not connected",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    except CareStackApiError as exc:
        await integration_svc.close_provider_sync_run(
            tenant_id,
            sync_run_id=run.id,
            principal=principal,
            provider="carestack",
            object_scope="location,patient,appointment",
            status="failed",
            records_total=0,
            records_succeeded=0,
            records_failed=1,
            error=exc,
        )
        raise IntegrationError(
            "carestack request failed",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    except Exception as exc:
        await integration_svc.close_provider_sync_run(
            tenant_id,
            sync_run_id=run.id,
            principal=principal,
            provider="carestack",
            object_scope="location,patient,appointment",
            status="failed",
            records_total=0,
            records_succeeded=0,
            records_failed=1,
            error=exc,
        )
        raise
    finally:
        close = getattr(client, "close", None) if client is not None else None
        if close is not None:
            await close()
    counters = _carestack_counters(locations, patients, appointments)
    await integration_svc.close_provider_sync_run(
        tenant_id,
        sync_run_id=run.id,
        principal=principal,
        provider="carestack",
        object_scope="location,patient,appointment",
        status=_counter_status(counters["succeeded"], counters["failed"]),
        records_total=counters["total"],
        records_succeeded=counters["succeeded"],
        records_failed=counters["failed"],
    )
    return CareStackPullOut(
        locations=locations,
        patients=patients,
        appointments=appointments,
        sync_run_id=run.id,
    )


@router.get("/patient/{patient_id}/raw")
async def patient_raw(
    factory: Annotated[CareStackClientFactory, Depends(get_carestack_client_factory)],
    _principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    patient_id: PatientIdParam,
) -> dict[str, Any]:
    """Live CareStack Patient by id — not persisted, full PHI verbatim."""
    client = await _open_client(factory)
    try:
        return await client.get_patient(patient_id)
    except CareStackNotConnectedError as exc:
        raise IntegrationError(
            "carestack not connected",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    except CareStackApiError as exc:
        raise IntegrationError(
            "carestack request failed",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    finally:
        await client.close()


@router.get("/appointment/{appointment_id}/raw")
async def appointment_raw(
    factory: Annotated[CareStackClientFactory, Depends(get_carestack_client_factory)],
    _principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    appointment_id: AppointmentIdParam,
) -> dict[str, Any]:
    """Live CareStack Appointment by id — not persisted, returned verbatim."""
    client = await _open_client(factory)
    try:
        return await client.get_appointment(appointment_id)
    except CareStackNotConnectedError as exc:
        raise IntegrationError(
            "carestack not connected",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    except CareStackApiError as exc:
        raise IntegrationError(
            "carestack request failed",
            details=dict(exc.details) if exc.details else {},
        ) from exc
    finally:
        await client.close()


def _counter_status(
    records_succeeded: int, records_failed: int
) -> ProviderSyncStatus:
    if records_failed > 0:
        return "partial" if records_succeeded > 0 else "failed"
    return "succeeded"


def _carestack_counters(
    locations: Any,
    patients: CareStackPatientImportOut,
    appointments: CareStackAppointmentImportOut,
) -> dict[str, int]:
    location_total = int(getattr(locations, "total_seen", 0) or 0)
    return {
        "total": location_total
        + patients.imported_count
        + patients.skipped_count
        + appointments.imported_count
        + appointments.skipped_count,
        "succeeded": location_total
        + patients.imported_count
        + appointments.imported_count,
        "failed": patients.skipped_count + appointments.skipped_count,
    }
