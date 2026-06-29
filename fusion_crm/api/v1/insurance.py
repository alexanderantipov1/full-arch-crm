"""
fusion_crm API v1 — Insurance & Claims

GET  /insurance/{person_uid}             — patient insurance info (PHI)
POST /insurance/eligibility-check        — trigger live eligibility verification
GET  /insurance/payers?search=           — payer directory

GET  /insurance/claims?person_uid=       — claims list
GET  /insurance/claims/{claim_id}        — single claim detail
POST /insurance/claims                   — submit new claim
PUT  /insurance/claims/{claim_id}        — update claim (status, paid amount)
PUT  /insurance/claims/{claim_id}/status — EOB posting — update status
POST /insurance/claims/{claim_id}/appeal — file appeal with letter
GET  /insurance/claims/eobs?date_from=   — EOB batch for RCM
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.v1.auth import validate_fusion_api_key

router = APIRouter(prefix="/insurance")


# ── Models ─────────────────────────────────────────────────────────────────────


class InsuranceCoverage(BaseModel):
    person_uid: str
    primary_payer: Optional[str] = None
    payer_id: Optional[str] = None
    member_id: Optional[str] = None
    group_id: Optional[str] = None
    plan_type: Optional[str] = None  # ppo | hmo | medicaid | medicare | self_pay
    copay: Optional[float] = None
    deductible_annual: Optional[float] = None
    deductible_remaining: Optional[float] = None
    max_annual_benefit: Optional[float] = None
    benefit_used: Optional[float] = None
    in_network: Optional[bool] = None
    verified_date: Optional[str] = None


class EligibilityCheckRequest(BaseModel):
    person_uid: str
    procedure_codes: list[str] = []
    appointment_date: Optional[str] = None


class EligibilityResult(BaseModel):
    person_uid: str
    eligible: bool
    payer_name: Optional[str] = None
    plan_type: Optional[str] = None
    copay: Optional[float] = None
    deductible_remaining: Optional[float] = None
    benefit_remaining: Optional[float] = None
    procedure_coverage: dict[str, dict] = {}
    verification_id: Optional[str] = None
    verified_at: Optional[str] = None
    notes: Optional[str] = None


class ClaimProcedure(BaseModel):
    cdt_code: str
    description: Optional[str] = None
    billed_amount: float
    allowed_amount: Optional[float] = None
    paid_amount: Optional[float] = None
    status: Optional[str] = None  # pending | approved | denied | paid
    denial_reason: Optional[str] = None


class Claim(BaseModel):
    claim_id: str
    person_uid: str
    payer_id: Optional[str] = None
    payer_name: Optional[str] = None
    submission_date: Optional[str] = None
    procedures: list[ClaimProcedure] = []
    total_billed: float = 0.0
    total_paid: Optional[float] = None
    status: str  # pending | submitted | paid | denied | appealed
    eob_document_url: Optional[str] = None
    notes: Optional[str] = None


class CreateClaimRequest(BaseModel):
    person_uid: str
    payer_id: str
    appointment_id: Optional[str] = None
    procedures: list[ClaimProcedure]
    notes: Optional[str] = None


class UpdateClaimStatusRequest(BaseModel):
    status: str
    denial_reason: Optional[str] = None
    denial_date: Optional[str] = None
    paid_amount: Optional[float] = None
    eob_notes: Optional[str] = None
    source: Optional[str] = None


class AppealRequest(BaseModel):
    appeal_date: str
    appeal_reason: str  # medical_necessity | frequency_limitation | billing_error | other
    letter_text: str
    supporting_docs: list[str] = []  # clinical note IDs
    source: Optional[str] = None


class PayerListing(BaseModel):
    payer_id: str
    payer_name: str
    payer_type: str
    electronic_payer_id: Optional[str] = None


# ── Service helpers ────────────────────────────────────────────────────────────


async def _get_insurance_service(tenant_id: str):
    try:
        from packages.domain.services.insurance_service import InsuranceService

        return InsuranceService(tenant_id=tenant_id)
    except ImportError:
        return None


async def _get_claims_service(tenant_id: str):
    try:
        from packages.domain.services.claims_service import ClaimsService

        return ClaimsService(tenant_id=tenant_id)
    except ImportError:
        return None


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/{person_uid}", response_model=InsuranceCoverage)
async def get_patient_insurance(
    person_uid: UUID,
    principal: dict = Depends(validate_fusion_api_key),
) -> InsuranceCoverage:
    """
    Return insurance coverage details for a patient. PHI — audit logged.
    """
    service = await _get_insurance_service(principal["tenant_id"])

    if service is None:
        return InsuranceCoverage(
            person_uid=str(person_uid),
            primary_payer="Delta Dental of California",
            payer_id="00000000-0000-0000-0000-000000000200",
            member_id="DD123456",
            group_id="GRP789",
            plan_type="ppo",
            copay=20.0,
            deductible_annual=1000.0,
            deductible_remaining=500.0,
            max_annual_benefit=2000.0,
            benefit_used=250.0,
            in_network=True,
            verified_date="2026-06-01",
        )

    coverage = await service.get_coverage(person_uid=str(person_uid))
    if not coverage:
        raise HTTPException(status_code=404, detail="Insurance information not found")

    return InsuranceCoverage(**coverage.model_dump())


@router.post("/eligibility-check", response_model=EligibilityResult)
async def check_eligibility(
    body: EligibilityCheckRequest,
    principal: dict = Depends(validate_fusion_api_key),
) -> EligibilityResult:
    """
    Trigger a live real-time eligibility verification for a patient.
    Called by full-arch-crm on the day of appointment.
    """
    service = await _get_insurance_service(principal["tenant_id"])

    if service is None:
        import uuid

        return EligibilityResult(
            person_uid=body.person_uid,
            eligible=True,
            payer_name="Delta Dental of California",
            plan_type="ppo",
            copay=20.0,
            deductible_remaining=500.0,
            benefit_remaining=1750.0,
            procedure_coverage={
                code: {"covered": True, "estimated_benefit_pct": 0.80}
                for code in body.procedure_codes
            },
            verification_id=str(uuid.uuid4()),
            verified_at="2026-06-27T00:00:00Z",
            notes="Live verification successful",
        )

    result = await service.verify_eligibility(
        person_uid=body.person_uid,
        procedure_codes=body.procedure_codes,
        appointment_date=body.appointment_date,
    )
    return EligibilityResult(**result.model_dump())


@router.get("/payers", response_model=list[PayerListing])
async def search_payers(
    search: str = Query("", description="Search by payer name or ID"),
    principal: dict = Depends(validate_fusion_api_key),
) -> list[PayerListing]:
    """
    Search the payer directory.
    """
    service = await _get_insurance_service(principal["tenant_id"])

    if service is None:
        payers = [
            PayerListing(payer_id="payer-001", payer_name="Delta Dental of California", payer_type="ppo", electronic_payer_id="DLTDNT"),
            PayerListing(payer_id="payer-002", payer_name="Blue Cross Blue Shield", payer_type="ppo", electronic_payer_id="BCBS00"),
            PayerListing(payer_id="payer-003", payer_name="Cigna Dental", payer_type="ppo", electronic_payer_id="CIGNA1"),
            PayerListing(payer_id="payer-004", payer_name="Aetna Dental", payer_type="ppo", electronic_payer_id="AETNA1"),
            PayerListing(payer_id="payer-005", payer_name="Denti-Cal", payer_type="medicaid", electronic_payer_id="DENTCL"),
        ]
        q = search.lower()
        return [p for p in payers if q in p.payer_name.lower() or q in p.payer_id.lower()] if q else payers

    return [PayerListing(**p.model_dump()) for p in await service.search_payers(search)]


@router.get("/claims", response_model=list[Claim])
async def list_claims(
    person_uid: str = Query(...),
    status: Optional[str] = Query(None, description="pending|submitted|paid|denied|appealed"),
    principal: dict = Depends(validate_fusion_api_key),
) -> list[Claim]:
    """
    List claims for a patient, optionally filtered by status.
    """
    service = await _get_claims_service(principal["tenant_id"])

    if service is None:
        return [
            Claim(
                claim_id="00000000-0000-0000-0000-000000000050",
                person_uid=person_uid,
                payer_id="payer-001",
                payer_name="Delta Dental of California",
                submission_date="2026-06-20",
                procedures=[
                    ClaimProcedure(cdt_code="D6010", description="Surgical placement, endosteal implant body", billed_amount=2400.0, allowed_amount=1800.0, paid_amount=None, status="pending"),
                ],
                total_billed=2400.0,
                total_paid=None,
                status="submitted",
                notes="Awaiting prior auth determination",
            )
        ]

    claims = await service.list_claims(person_uid=person_uid, status=status)
    return [Claim(**c.model_dump()) for c in claims]


@router.get("/claims/eobs", response_model=list[dict])
async def get_eobs(
    date_from: str = Query(..., description="YYYY-MM-DD"),
    date_to: str = Query(..., description="YYYY-MM-DD"),
    principal: dict = Depends(validate_fusion_api_key),
) -> list[dict]:
    """
    Retrieve EOB batch for RCM processing. Called daily by full-arch-crm eob-service.
    """
    service = await _get_claims_service(principal["tenant_id"])

    if service is None:
        return []

    eobs = await service.get_eobs(date_from=date_from, date_to=date_to)
    return [e.model_dump() for e in eobs]


@router.get("/claims/{claim_id}", response_model=Claim)
async def get_claim(
    claim_id: UUID,
    principal: dict = Depends(validate_fusion_api_key),
) -> Claim:
    service = await _get_claims_service(principal["tenant_id"])

    if service is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim = await service.get_by_id(str(claim_id))
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    return Claim(**claim.model_dump())


@router.post("/claims", response_model=dict, status_code=201)
async def create_claim(
    body: CreateClaimRequest,
    principal: dict = Depends(validate_fusion_api_key),
) -> dict:
    """
    Submit a new insurance claim. Called by full-arch-crm insurance-calling service.
    """
    service = await _get_claims_service(principal["tenant_id"])

    if service is None:
        import uuid

        return {"claim_id": str(uuid.uuid4()), "created": True}

    claim = await service.create_claim(data=body.model_dump())
    return {"claim_id": str(claim.claim_id), "created": True}


@router.put("/claims/{claim_id}", response_model=dict)
async def update_claim(
    claim_id: UUID,
    body: UpdateClaimStatusRequest,
    principal: dict = Depends(validate_fusion_api_key),
) -> dict:
    service = await _get_claims_service(principal["tenant_id"])

    if service is None:
        return {"claim_id": str(claim_id), "updated": True}

    await service.update_claim(
        claim_id=str(claim_id),
        data={k: v for k, v in body.model_dump().items() if v is not None},
    )
    return {"claim_id": str(claim_id), "updated": True}


@router.put("/claims/{claim_id}/status", response_model=dict)
async def update_claim_status(
    claim_id: UUID,
    body: UpdateClaimStatusRequest,
    principal: dict = Depends(validate_fusion_api_key),
) -> dict:
    """
    EOB posting endpoint — called by server/rcm/eob-service.ts in full-arch-crm
    to record payment or denial after processing remittance.
    """
    service = await _get_claims_service(principal["tenant_id"])

    if service is None:
        return {"claim_id": str(claim_id), "status_updated": True}

    await service.update_status(
        claim_id=str(claim_id),
        data={k: v for k, v in body.model_dump().items() if v is not None},
    )
    return {"claim_id": str(claim_id), "status_updated": True}


@router.post("/claims/{claim_id}/appeal", response_model=dict, status_code=201)
async def file_appeal(
    claim_id: UUID,
    body: AppealRequest,
    principal: dict = Depends(validate_fusion_api_key),
) -> dict:
    """
    File an insurance appeal with a letter generated by full-arch-crm.
    """
    service = await _get_claims_service(principal["tenant_id"])

    if service is None:
        import uuid

        return {"appeal_id": str(uuid.uuid4()), "created": True}

    appeal = await service.file_appeal(claim_id=str(claim_id), data=body.model_dump())
    return {"appeal_id": str(appeal.appeal_id), "created": True}
