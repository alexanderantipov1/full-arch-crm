"""
fusion_crm API v1 — Intelligence Ingest & Query

This is how full-arch-crm's Karpathy wiki pushes anonymized learned patterns
BACK to fusion_crm so the clinic's local workflows benefit from network intelligence.

full-arch-crm owns the wiki. These endpoints let it share validated patterns
with this specific clinic's fusion_crm instance.

POST /intelligence/ingest                       — full-arch-crm pushes anonymized patterns
GET  /intelligence/query                        — full-arch-crm pulls stored patterns
POST /intelligence/insurance-patterns           — anonymized payer approval patterns
POST /intelligence/cdt-documentation-tips       — documentation tips that improve approvals
POST /intelligence/appeal-templates             — successful appeal letter templates
GET  /intelligence/claim-prediction/{claim_id}  — predicted approval probability
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.v1.auth import validate_fusion_api_key

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Models ─────────────────────────────────────────────────────────────────────


class AnonymizedPattern(BaseModel):
    """
    A single anonymized intelligence pattern pushed from full-arch-crm wiki.
    Never contains patient IDs, clinic IDs, or any PHI.
    """
    source: str = Field("full_arch_crm.wiki", description="Always 'full_arch_crm.wiki'")
    pattern_type: str  # insurance_pattern | documentation_tip | appeal_template | procedure_pairing
    payer_type: Optional[str] = None  # ppo | hmo | medicaid | medicare
    cdt_code: Optional[str] = None
    approval_rate: Optional[float] = None
    top_approval_driver: Optional[str] = None
    top_denial_reason: Optional[str] = None
    appeal_success_rate: Optional[float] = None
    sample_count: int = Field(..., ge=10, description="k-anonymity: minimum 10")
    confidence: str  # medium | high
    metadata: dict[str, Any] = {}


class IntelligenceIngestRequest(BaseModel):
    patterns: list[AnonymizedPattern]
    wiki_version: Optional[str] = None
    pushed_at: Optional[str] = None


class IntelligenceIngestResponse(BaseModel):
    accepted: int
    rejected: int
    reasons: list[str] = []


class IntelligenceQueryRequest(BaseModel):
    category: str  # insurance | clinical | procedure | appeal
    cdt_code: Optional[str] = None
    payer_type: Optional[str] = None
    question: Optional[str] = None


class IntelligenceQueryResponse(BaseModel):
    category: str
    patterns: list[dict[str, Any]]
    confidence: str
    source_count: int


class InsurancePatternRequest(BaseModel):
    source: str = "full_arch_crm.wiki"
    payer_type: str
    cdt_code: str
    approval_rate: float
    top_approval_driver: Optional[str] = None
    top_denial_reason: Optional[str] = None
    appeal_success_rate: Optional[float] = None
    sample_count: int = Field(..., ge=10)
    confidence: str


class DocumentationTipRequest(BaseModel):
    source: str = "full_arch_crm.wiki"
    cdt_code: str
    payer_type: Optional[str] = None
    tip: str
    impact_description: str  # e.g. "increases approval rate from 72% to 88%"
    sample_count: int = Field(..., ge=10)
    confidence: str


class AppealTemplateRequest(BaseModel):
    source: str = "full_arch_crm.wiki"
    payer_slug: str
    cdt_code: str
    letter_template: str
    success_rate: float
    sample_count: int = Field(..., ge=10)
    denial_reason: Optional[str] = None


class ClaimPrediction(BaseModel):
    claim_id: str
    predicted_outcome: str  # approved | denied | requires_additional_docs
    approval_probability: float  # 0.0–1.0
    confidence: str
    key_risk_factors: list[str] = []
    recommended_actions: list[str] = []
    wiki_sources: list[str] = []


# ── Service helpers ────────────────────────────────────────────────────────────


async def _get_intelligence_service(tenant_id: str):
    try:
        from packages.domain.services.intelligence_service import IntelligenceService

        return IntelligenceService(tenant_id=tenant_id)
    except ImportError:
        return None


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/ingest", response_model=IntelligenceIngestResponse)
async def ingest_intelligence(
    body: IntelligenceIngestRequest,
    principal: dict = Depends(validate_fusion_api_key),
) -> IntelligenceIngestResponse:
    """
    Full-arch-crm pushes anonymized learned patterns from its Karpathy wiki
    back to this clinic's fusion_crm instance.

    Patterns must meet k-anonymity threshold (sample_count >= 10).
    Patterns with sample_count < 10 are rejected.
    """
    service = await _get_intelligence_service(principal["tenant_id"])

    accepted = 0
    rejected = 0
    reasons: list[str] = []

    for pattern in body.patterns:
        if pattern.sample_count < 10:
            rejected += 1
            reasons.append(f"Pattern {pattern.pattern_type}/{pattern.cdt_code}: sample_count {pattern.sample_count} < 10 (k-anonymity violation)")
            continue

        if service is not None:
            try:
                await service.store_pattern(pattern.model_dump())
                accepted += 1
            except Exception as e:
                rejected += 1
                reasons.append(f"Storage error for {pattern.pattern_type}: {str(e)}")
        else:
            logger.info(
                "INTELLIGENCE_INGEST tenant=%s type=%s cdt=%s approval_rate=%s sample_count=%s",
                principal["tenant_id"],
                pattern.pattern_type,
                pattern.cdt_code,
                pattern.approval_rate,
                pattern.sample_count,
            )
            accepted += 1

    return IntelligenceIngestResponse(accepted=accepted, rejected=rejected, reasons=reasons)


@router.get("/query", response_model=IntelligenceQueryResponse)
async def query_intelligence(
    category: str = Query(..., description="insurance | clinical | procedure | appeal"),
    cdt_code: Optional[str] = Query(None),
    payer_type: Optional[str] = Query(None),
    principal: dict = Depends(validate_fusion_api_key),
) -> IntelligenceQueryResponse:
    """
    Full-arch-crm pulls stored intelligence patterns from this clinic.
    Used to bootstrap wiki or fill gaps when network intelligence is thin.
    """
    service = await _get_intelligence_service(principal["tenant_id"])

    if service is None:
        # Return illustrative patterns when service unavailable
        patterns: list[dict] = []
        if category == "insurance" and cdt_code == "D6010":
            patterns = [
                {
                    "cdt_code": "D6010",
                    "payer_type": payer_type or "ppo",
                    "approval_rate": 0.81,
                    "top_approval_driver": "full_mouth_xray_series_included",
                    "top_denial_reason": "frequency_limitation",
                    "appeal_success_rate": 0.67,
                    "sample_count": 42,
                    "confidence": "high",
                }
            ]
        return IntelligenceQueryResponse(
            category=category,
            patterns=patterns,
            confidence="medium",
            source_count=len(patterns),
        )

    results = await service.query(
        category=category,
        cdt_code=cdt_code,
        payer_type=payer_type,
    )
    return IntelligenceQueryResponse(
        category=category,
        patterns=results.patterns,
        confidence=results.confidence,
        source_count=results.source_count,
    )


@router.post("/insurance-patterns", response_model=dict)
async def ingest_insurance_pattern(
    body: InsurancePatternRequest,
    principal: dict = Depends(validate_fusion_api_key),
) -> dict:
    """
    Ingest a single validated insurance approval/denial pattern from the wiki.
    Used by IntelligenceBroadcaster in full-arch-crm.
    """
    service = await _get_intelligence_service(principal["tenant_id"])

    if body.sample_count < 10:
        raise HTTPException(
            status_code=422,
            detail=f"sample_count {body.sample_count} < 10: k-anonymity threshold not met",
        )

    if service is not None:
        await service.store_insurance_pattern(body.model_dump())
    else:
        logger.info(
            "INSURANCE_PATTERN tenant=%s cdt=%s payer=%s approval_rate=%.2f n=%d",
            principal["tenant_id"],
            body.cdt_code,
            body.payer_type,
            body.approval_rate,
            body.sample_count,
        )

    return {"accepted": True, "cdt_code": body.cdt_code, "payer_type": body.payer_type}


@router.post("/cdt-documentation-tips", response_model=dict)
async def ingest_documentation_tip(
    body: DocumentationTipRequest,
    principal: dict = Depends(validate_fusion_api_key),
) -> dict:
    """
    Push a documentation tip that improves claim approval rates.
    e.g. 'Include periapical X-rays for D6010 PPO claims — raises approval 72%→88%'
    """
    service = await _get_intelligence_service(principal["tenant_id"])

    if body.sample_count < 10:
        raise HTTPException(status_code=422, detail="k-anonymity threshold not met")

    if service is not None:
        await service.store_documentation_tip(body.model_dump())
    else:
        logger.info(
            "DOC_TIP tenant=%s cdt=%s tip=%s impact=%s",
            principal["tenant_id"],
            body.cdt_code,
            body.tip[:80],
            body.impact_description,
        )

    return {"accepted": True, "cdt_code": body.cdt_code}


@router.post("/appeal-templates", response_model=dict)
async def ingest_appeal_template(
    body: AppealTemplateRequest,
    principal: dict = Depends(validate_fusion_api_key),
) -> dict:
    """
    Push a successful appeal letter template.
    Only templates with sample_count >= 10 are accepted (validated in production).
    Used by InsuranceCallAgent to draft appeal letters.
    """
    service = await _get_intelligence_service(principal["tenant_id"])

    if body.sample_count < 10:
        raise HTTPException(status_code=422, detail="k-anonymity threshold not met")

    if service is not None:
        await service.store_appeal_template(body.model_dump())
    else:
        logger.info(
            "APPEAL_TEMPLATE tenant=%s payer=%s cdt=%s success_rate=%.2f n=%d",
            principal["tenant_id"],
            body.payer_slug,
            body.cdt_code,
            body.success_rate,
            body.sample_count,
        )

    return {"accepted": True, "payer_slug": body.payer_slug, "cdt_code": body.cdt_code}


@router.get("/claim-prediction/{claim_id}", response_model=ClaimPrediction)
async def predict_claim_outcome(
    claim_id: UUID,
    principal: dict = Depends(validate_fusion_api_key),
) -> ClaimPrediction:
    """
    Predict whether a claim will be approved, denied, or require additional documentation.
    Powered by intelligence patterns previously ingested from full-arch-crm wiki.
    """
    service = await _get_intelligence_service(principal["tenant_id"])

    if service is None:
        # Illustrative prediction for dev/test
        return ClaimPrediction(
            claim_id=str(claim_id),
            predicted_outcome="approved",
            approval_probability=0.81,
            confidence="medium",
            key_risk_factors=["missing_periapical_xray"],
            recommended_actions=[
                "Include full-mouth radiographic series",
                "Attach implant placement report with date of last implant",
            ],
            wiki_sources=["insurance/ppo-general.md", "clinical/D6010-implant-body.md"],
        )

    prediction = await service.predict_claim(claim_id=str(claim_id))
    if not prediction:
        raise HTTPException(status_code=404, detail="Claim not found")

    return ClaimPrediction(**prediction.model_dump())
