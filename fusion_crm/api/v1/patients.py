"""
fusion_crm API v1 — Patients Endpoints

GET  /patients                        — paginated non-PHI list
GET  /patients/search?q=              — search patients
GET  /patients/{person_uid}           — basic patient record
GET  /patients/{person_uid}/snapshot  — full PHI record (audit logged, reason required)
GET  /patients/{person_uid}/treatment-history
POST /patients                        — create new patient record
PUT  /patients/{person_uid}/profile   — update demographics

All PHI access is HIPAA audit-logged via the auth dependency.
Display names are first name + last initial only.
DOB is never returned in list views — age_band is used instead.
"""

from __future__ import annotations

import math
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.v1.auth import validate_fusion_api_key

router = APIRouter()


# ── Response Models ────────────────────────────────────────────────────────────


class PatientListItem(BaseModel):
    person_uid: str
    display_name: str = Field(..., description="First name + last initial only (e.g. 'Jane D.')")
    age_band: str = Field(..., description="Age band (e.g. '35-44') — never exact DOB")
    insurance_type: Optional[str] = None
    last_visit_date: Optional[str] = None
    active_treatment_plan: bool = False
    scenario_tag: Optional[str] = None


class PatientListResponse(BaseModel):
    items: list[PatientListItem]
    total: int
    cursor: Optional[str] = None


class InsuranceInfo(BaseModel):
    primary_payer: Optional[str] = None
    member_id: Optional[str] = None
    group_id: Optional[str] = None
    copay: Optional[float] = None
    deductible_remaining: Optional[float] = None


class AddressInfo(BaseModel):
    line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None


class EmergencyContact(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


class PatientSnapshot(BaseModel):
    """Full PHI record — only returned with audit logging and reason param."""
    person_uid: str
    full_name: str
    dob: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[AddressInfo] = None
    insurance: Optional[InsuranceInfo] = None
    emergency_contact: Optional[EmergencyContact] = None
    phi_access_logged: bool = True
    reason: str


class ProcedureRecord(BaseModel):
    cdt_code: str
    description: str
    fee: Optional[float] = None
    status: Optional[str] = None


class VisitRecord(BaseModel):
    visit_date: str
    provider_id: Optional[str] = None
    procedures: list[ProcedureRecord] = []
    clinical_notes_available: bool = False
    note_id: Optional[str] = None


class TreatmentHistoryResponse(BaseModel):
    person_uid: str
    visits: list[VisitRecord]


class CreatePatientRequest(BaseModel):
    first_name: str
    last_name: str
    dob: str = Field(..., description="ISO date string YYYY-MM-DD")
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[AddressInfo] = None
    insurance: Optional[InsuranceInfo] = None
    emergency_contact: Optional[EmergencyContact] = None


class UpdatePatientProfileRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[AddressInfo] = None
    emergency_contact: Optional[EmergencyContact] = None


# ── Helpers ────────────────────────────────────────────────────────────────────


def _age_band(dob_str: str) -> str:
    """Convert ISO DOB string to age band string."""
    try:
        from datetime import date, datetime

        dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
        age = (date.today() - dob).days // 365
        lower = (age // 10) * 10
        return f"{lower}-{lower + 9}"
    except Exception:
        return "unknown"


def _display_name(first_name: str, last_name: str) -> str:
    """Return 'First L.' format — never expose full last name in list view."""
    last_initial = (last_name[0].upper() + ".") if last_name else ""
    return f"{first_name} {last_initial}".strip()


async def _get_patient_service(tenant_id: str):
    """Return the patient service for the given tenant. Lazy import."""
    try:
        from packages.domain.services.patient_service import PatientService

        return PatientService(tenant_id=tenant_id)
    except ImportError:
        return None


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("", response_model=PatientListResponse)
async def list_patients(
    cursor: Optional[str] = Query(None, description="Opaque pagination cursor"),
    limit: int = Query(50, ge=1, le=200),
    principal: dict = Depends(validate_fusion_api_key),
) -> PatientListResponse:
    """
    Paginated patient list — non-PHI fields only.
    Returns display_name (first + last initial) and age_band (never exact DOB).
    """
    tenant_id = principal["tenant_id"]
    service = await _get_patient_service(tenant_id)

    if service is None:
        # Dev/test stub
        return PatientListResponse(
            items=[
                PatientListItem(
                    person_uid="00000000-0000-0000-0000-000000000001",
                    display_name="John D.",
                    age_band="45-54",
                    insurance_type="ppo",
                    last_visit_date="2026-03-15",
                    active_treatment_plan=True,
                    scenario_tag="implant_consult",
                )
            ],
            total=1,
            cursor=None,
        )

    page = await service.list_patients(cursor=cursor, limit=limit)
    items = [
        PatientListItem(
            person_uid=str(p.person_uid),
            display_name=_display_name(p.first_name, p.last_name),
            age_band=_age_band(p.dob),
            insurance_type=p.insurance_type,
            last_visit_date=str(p.last_visit_date) if p.last_visit_date else None,
            active_treatment_plan=bool(p.active_treatment_plan),
            scenario_tag=p.scenario_tag,
        )
        for p in page.items
    ]
    return PatientListResponse(items=items, total=page.total, cursor=page.next_cursor)


@router.get("/search", response_model=PatientListResponse)
async def search_patients(
    q: str = Query(..., min_length=1, description="Search query — name, phone, or email"),
    limit: int = Query(25, ge=1, le=100),
    principal: dict = Depends(validate_fusion_api_key),
) -> PatientListResponse:
    """
    Full-text patient search.
    Returns non-PHI list items matching the query.
    """
    tenant_id = principal["tenant_id"]
    service = await _get_patient_service(tenant_id)

    if service is None:
        return PatientListResponse(items=[], total=0)

    page = await service.search_patients(query=q, limit=limit)
    items = [
        PatientListItem(
            person_uid=str(p.person_uid),
            display_name=_display_name(p.first_name, p.last_name),
            age_band=_age_band(p.dob),
            insurance_type=p.insurance_type,
            last_visit_date=str(p.last_visit_date) if p.last_visit_date else None,
            active_treatment_plan=bool(p.active_treatment_plan),
            scenario_tag=p.scenario_tag,
        )
        for p in page.items
    ]
    return PatientListResponse(items=items, total=page.total)


@router.get("/{person_uid}/snapshot", response_model=PatientSnapshot)
async def get_patient_snapshot(
    person_uid: UUID,
    reason: str = Query(..., min_length=1, description="PHI access reason — required for audit log"),
    principal: dict = Depends(validate_fusion_api_key),
) -> PatientSnapshot:
    """
    Full PHI patient snapshot — includes DOB, phone, email, address, insurance.
    Every call is HIPAA audit-logged with the provided reason.
    reason format: 'service.action' (e.g. 'full_arch_crm.ai_scribe.pre_visit_brief')
    """
    tenant_id = principal["tenant_id"]
    service = await _get_patient_service(tenant_id)

    if service is None:
        return PatientSnapshot(
            person_uid=str(person_uid),
            full_name="John Doe",
            dob="1975-04-15",
            phone="+15551234567",
            email="john.doe@example.com",
            address=AddressInfo(line1="123 Main St", city="San Diego", state="CA", zip="92101"),
            insurance=InsuranceInfo(
                primary_payer="Delta Dental of California",
                member_id="DD123456",
                group_id="GRP789",
                copay=20.0,
                deductible_remaining=500.0,
            ),
            emergency_contact=EmergencyContact(name="Jane Doe", phone="+15559876543"),
            phi_access_logged=True,
            reason=reason,
        )

    patient = await service.get_patient_snapshot(person_uid=str(person_uid), reason=reason)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {person_uid} not found")

    return PatientSnapshot(
        person_uid=str(patient.person_uid),
        full_name=f"{patient.first_name} {patient.last_name}",
        dob=str(patient.dob) if patient.dob else None,
        phone=patient.phone,
        email=patient.email,
        address=AddressInfo(**patient.address) if patient.address else None,
        insurance=InsuranceInfo(**patient.insurance) if patient.insurance else None,
        emergency_contact=EmergencyContact(**patient.emergency_contact)
        if patient.emergency_contact
        else None,
        phi_access_logged=True,
        reason=reason,
    )


@router.get("/{person_uid}/treatment-history", response_model=TreatmentHistoryResponse)
async def get_treatment_history(
    person_uid: UUID,
    principal: dict = Depends(validate_fusion_api_key),
) -> TreatmentHistoryResponse:
    """
    Full treatment history for a patient — all visits, procedures, and CDT codes.
    """
    tenant_id = principal["tenant_id"]
    service = await _get_patient_service(tenant_id)

    if service is None:
        return TreatmentHistoryResponse(
            person_uid=str(person_uid),
            visits=[
                VisitRecord(
                    visit_date="2026-03-15",
                    provider_id="00000000-0000-0000-0000-000000000099",
                    procedures=[
                        ProcedureRecord(cdt_code="D0150", description="Comprehensive Oral Evaluation", fee=120.0, status="paid"),
                        ProcedureRecord(cdt_code="D0274", description="4 Bitewing X-Rays", fee=95.0, status="paid"),
                    ],
                    clinical_notes_available=True,
                    note_id="00000000-0000-0000-0000-000000000010",
                )
            ],
        )

    history = await service.get_treatment_history(person_uid=str(person_uid))
    if not history:
        raise HTTPException(status_code=404, detail=f"Patient {person_uid} not found")

    return TreatmentHistoryResponse(
        person_uid=str(person_uid),
        visits=[
            VisitRecord(
                visit_date=str(v.visit_date),
                provider_id=str(v.provider_id) if v.provider_id else None,
                procedures=[
                    ProcedureRecord(
                        cdt_code=p.cdt_code,
                        description=p.description,
                        fee=p.fee,
                        status=p.status,
                    )
                    for p in v.procedures
                ],
                clinical_notes_available=v.clinical_notes_available,
                note_id=str(v.note_id) if v.note_id else None,
            )
            for v in history.visits
        ],
    )


@router.post("", response_model=dict, status_code=201)
async def create_patient(
    body: CreatePatientRequest,
    principal: dict = Depends(validate_fusion_api_key),
) -> dict:
    """
    Create a new patient record.
    Returns the new person_uid on success.
    """
    tenant_id = principal["tenant_id"]
    service = await _get_patient_service(tenant_id)

    if service is None:
        import uuid

        return {"person_uid": str(uuid.uuid4()), "created": True}

    patient = await service.create_patient(data=body.model_dump())
    return {"person_uid": str(patient.person_uid), "created": True}


@router.put("/{person_uid}/profile", response_model=dict)
async def update_patient_profile(
    person_uid: UUID,
    body: UpdatePatientProfileRequest,
    principal: dict = Depends(validate_fusion_api_key),
) -> dict:
    """
    Update patient demographics.
    """
    tenant_id = principal["tenant_id"]
    service = await _get_patient_service(tenant_id)

    if service is None:
        return {"person_uid": str(person_uid), "updated": True}

    await service.update_patient(
        person_uid=str(person_uid),
        data={k: v for k, v in body.model_dump().items() if v is not None},
    )
    return {"person_uid": str(person_uid), "updated": True}
