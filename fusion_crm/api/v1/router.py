"""
fusion_crm API v1 — Main Router

Aggregates all sub-routers under /api/v1/.
Mount this router in your FastAPI app:

    from api.v1.router import router as api_v1_router
    app.include_router(api_v1_router)
"""

from fastapi import APIRouter

from api.v1 import appointments, clinical, insurance, intelligence, patients

router = APIRouter(prefix="/api/v1")

router.include_router(patients.router, prefix="/patients", tags=["patients"])
router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
router.include_router(clinical.router, tags=["clinical"])
router.include_router(insurance.router, tags=["insurance"])
router.include_router(intelligence.router, prefix="/intelligence", tags=["intelligence"])

__all__ = ["router"]
