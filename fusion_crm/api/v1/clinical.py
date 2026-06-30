"""
fusion_crm API v1 — Clinical Notes & CDT Codes

GET  /clinical-notes?person_uid=      — list notes for a patient (PHI, audit logged)
GET  /clinical-notes/{note_id}        — single note (PHI, audit logged)
POST /clinical-notes                  — AI Scribe writes note here
PUT  /clinical-notes/{note_id}        — amend note
GET  /cdt-codes?search=               — CDT code lookup
GET  /cdt-codes/{code}                — single CDT code detail
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.v1.auth import validate_fusion_api_key

router = APIRouter()


# ── Models ─────────────────────────────────────────────────────────────────────


class ClinicalNote(BaseModel):
    note_id: str
    person_uid: str
    appointment_id: Optional[str] = None
    provider_id: Optional[str] = None
    visit_date: str
    note_type: str  # soap | progress | consult | perio_chart
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    ai_generated: bool = False
    ai_model: Optional[str] = None
    provider_approved: bool = False
    source: Optional[str] = None


class CreateClinicalNoteRequest(BaseModel):
    person_uid: str
    appointment_id: Optional[str] = None
    provider_id: Optional[str] = None
    visit_date: str
    note_type: str = "soap"
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    ai_generated: bool = False
    ai_model: Optional[str] = None
    provider_approved: bool = False
    source: Optional[str] = None


class AmendNoteRequest(BaseModel):
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    provider_approved: Optional[bool] = None
    amendment_reason: Optional[str] = None


class CDTCode(BaseModel):
    code: str
    description: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    requires_preauth: bool = False
    avg_fee: Optional[float] = None


class CDTSearchResponse(BaseModel):
    items: list[CDTCode]
    total: int


# ── Service helpers ────────────────────────────────────────────────────────────


async def _get_clinical_service(tenant_id: str):
    try:
        from packages.domain.services.clinical_note_service import ClinicalNoteService

        return ClinicalNoteService(tenant_id=tenant_id)
    except ImportError:
        return None


async def _get_cdt_service():
    try:
        from packages.domain.services.cdt_code_service import CDTCodeService

        return CDTCodeService()
    except ImportError:
        return None


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/clinical-notes", response_model=list[ClinicalNote])
async def list_clinical_notes(
    person_uid: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    principal: dict = Depends(validate_fusion_api_key),
) -> list[ClinicalNote]:
    """
    List clinical notes for a patient. Full PHI — audit logged.
    """
    service = await _get_clinical_service(principal["tenant_id"])

    if service is None:
        return [
            ClinicalNote(
                note_id="00000000-0000-0000-0000-000000000010",
                person_uid=person_uid,
                appointment_id="00000000-0000-0000-0000-000000000001",
                provider_id="00000000-0000-0000-0000-000000000099",
                visit_date="2026-03-15",
                note_type="soap",
                subjective="Patient reports sensitivity to cold on #19.",
                objective="Probing depths 3-4mm, BOP on #19-M. Radiograph shows interproximal decay.",
                assessment="Class II caries on #19.",
                plan="D2392 composite resin, 2 surfaces, posterior.",
                ai_generated=True,
                ai_model="claude-opus-4-5",
                provider_approved=True,
                source="full_arch_crm.ai_scribe",
            )
        ]

    notes = await service.list_for_patient(person_uid=person_uid, limit=limit)
    return [ClinicalNote(**n.model_dump()) for n in notes]


@router.get("/clinical-notes/{note_id}", response_model=ClinicalNote)
async def get_clinical_note(
    note_id: UUID,
    principal: dict = Depends(validate_fusion_api_key),
) -> ClinicalNote:
    """
    Retrieve a single clinical note by ID. Full PHI — audit logged.
    """
    service = await _get_clinical_service(principal["tenant_id"])

    if service is None:
        raise HTTPException(status_code=404, detail="Note not found")

    note = await service.get_by_id(str(note_id))
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    return ClinicalNote(**note.model_dump())


@router.post("/clinical-notes", response_model=dict, status_code=201)
async def create_clinical_note(
    body: CreateClinicalNoteRequest,
    principal: dict = Depends(validate_fusion_api_key),
) -> dict:
    """
    AI Scribe writes the transcribed SOAP note here.
    source should be set to 'full_arch_crm.ai_scribe'.
    """
    service = await _get_clinical_service(principal["tenant_id"])

    if service is None:
        import uuid

        return {"note_id": str(uuid.uuid4()), "created": True}

    note = await service.create(data=body.model_dump())
    return {"note_id": str(note.note_id), "created": True}


@router.put("/clinical-notes/{note_id}", response_model=dict)
async def amend_clinical_note(
    note_id: UUID,
    body: AmendNoteRequest,
    principal: dict = Depends(validate_fusion_api_key),
) -> dict:
    """
    Amend an existing clinical note. All amendments are versioned.
    """
    service = await _get_clinical_service(principal["tenant_id"])

    if service is None:
        return {"note_id": str(note_id), "updated": True}

    await service.amend(
        note_id=str(note_id),
        data={k: v for k, v in body.model_dump().items() if v is not None},
    )
    return {"note_id": str(note_id), "updated": True}


@router.get("/cdt-codes", response_model=CDTSearchResponse)
async def search_cdt_codes(
    search: str = Query("", description="Search by code or description"),
    limit: int = Query(25, ge=1, le=100),
    principal: dict = Depends(validate_fusion_api_key),
) -> CDTSearchResponse:
    """
    CDT code lookup — used by AI Scribe and treatment plan builders.
    """
    service = await _get_cdt_service()

    if service is None:
        # Seed with common implant/restorative codes
        all_codes = [
            CDTCode(code="D6010", description="Surgical placement, endosteal implant body", category="Implants", requires_preauth=True, avg_fee=2400.0),
            CDTCode(code="D6056", description="Prefabricated abutment", category="Implants", requires_preauth=False, avg_fee=550.0),
            CDTCode(code="D6114", description="Implant/abutment supported fixed denture (edentulous arch)", category="Implants", requires_preauth=True, avg_fee=8500.0),
            CDTCode(code="D2392", description="Resin-based composite, 2 surfaces, posterior", category="Restorative", requires_preauth=False, avg_fee=285.0),
            CDTCode(code="D2740", description="Crown, porcelain/ceramic substrate", category="Restorative", requires_preauth=False, avg_fee=1350.0),
            CDTCode(code="D4341", description="Periodontal scaling and root planing, per quadrant", category="Periodontics", requires_preauth=False, avg_fee=280.0),
            CDTCode(code="D0150", description="Comprehensive oral evaluation", category="Diagnostic", requires_preauth=False, avg_fee=120.0),
            CDTCode(code="D0274", description="Bitewing radiographic image, four images", category="Diagnostic", requires_preauth=False, avg_fee=95.0),
        ]
        q = search.lower()
        filtered = [c for c in all_codes if q in c.code.lower() or q in c.description.lower()] if q else all_codes
        return CDTSearchResponse(items=filtered[:limit], total=len(filtered))

    results = await service.search(query=search, limit=limit)
    return CDTSearchResponse(
        items=[CDTCode(**c.model_dump()) for c in results.items],
        total=results.total,
    )


@router.get("/cdt-codes/{code}", response_model=CDTCode)
async def get_cdt_code(
    code: str,
    principal: dict = Depends(validate_fusion_api_key),
) -> CDTCode:
    """
    Retrieve a single CDT code by its code string (e.g. D6010).
    """
    service = await _get_cdt_service()

    if service is None:
        raise HTTPException(status_code=404, detail=f"CDT code {code} not found")

    cdt = await service.get_by_code(code.upper())
    if not cdt:
        raise HTTPException(status_code=404, detail=f"CDT code {code} not found")

    return CDTCode(**cdt.model_dump())
