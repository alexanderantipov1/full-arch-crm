"""PhiService — gatekeeper for ALL PHI access.

Every public method:
  1. Checks the calling principal's authorisation (``can_read_phi``).
  2. Records an entry in the audit log (action + person_uid + reason).
  3. Then performs the read or write.

If you need a NEW PHI access path, add a method here. Do NOT bypass.

Every public method takes ``tenant_id: TenantId`` as the first positional
argument after ``self`` (ENG-128). The tenant is resolved at the
boundary from ``Principal.tenant_id`` and forwarded into every read /
write so that PHI rows in tenant A cannot leak to a principal of tenant
B even if the principal somehow held both PHI roles.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.service import AuditService
from packages.core.exceptions import NotFoundError, PHIAccessDeniedError
from packages.core.security import Principal
from packages.core.types import PersonUID, TenantId
from packages.identity.service import IdentityService

from .models import PatientProfile
from .repository import PhiRepository
from .schemas import (
    ConsultationOut,
    PatientProfileIn,
    PatientProfileOut,
    PhiPersonSnapshot,
)


class PhiService:
    """The single, audited entry point into PHI."""

    def __init__(self, session: AsyncSession, principal: Principal) -> None:
        self._session = session
        self._principal = principal
        self._repo = PhiRepository(session)
        self._identity = IdentityService(session)
        self._audit = AuditService(session)

    # --- Authorisation gate ---
    def _ensure_authorised(self, person_uid: PersonUID, action: str) -> None:
        if not self._principal.can_read_phi():
            # Even a denied attempt MUST be auditable.
            # Note: caller is responsible for committing the audit row;
            # we still want the row written even when we raise.
            raise PHIAccessDeniedError(
                f"principal not allowed to {action}",
                details={
                    "person_uid": str(person_uid),
                    "principal_id": str(self._principal.id),
                },
            )

    # --- Snapshots ---
    async def snapshot(
        self,
        tenant_id: TenantId,
        person_uid: PersonUID,
        *,
        reason: str = "phi.snapshot",
    ) -> PhiPersonSnapshot:
        self._ensure_authorised(person_uid, "read PHI snapshot")

        # Confirm the person exists at all (raises NotFoundError otherwise).
        await self._identity.get_person(tenant_id, person_uid)

        profile = await self._repo.get_profile(tenant_id, person_uid)
        consultations = await self._repo.recent_consultations(tenant_id, person_uid)

        await self._audit.record_phi_access(
            principal=self._principal,
            person_uid=person_uid,
            action="phi.snapshot",
            reason=reason,
        )

        return PhiPersonSnapshot(
            person_uid=person_uid,
            profile=PatientProfileOut.model_validate(profile) if profile else None,
            recent_consultations=[ConsultationOut.model_validate(c) for c in consultations],
        )

    # --- Profile management ---
    async def upsert_profile(
        self,
        tenant_id: TenantId,
        payload: PatientProfileIn,
        *,
        reason: str = "phi.profile.upsert",
    ) -> PatientProfile:
        person_uid = PersonUID(payload.person_uid)
        self._ensure_authorised(person_uid, "write PHI profile")
        await self._identity.get_person(tenant_id, person_uid)

        existing = await self._repo.get_profile(tenant_id, person_uid)
        if existing is None:
            existing = PatientProfile(
                tenant_id=tenant_id,
                person_uid=payload.person_uid,
                date_of_birth=payload.date_of_birth,
                sex_at_birth=payload.sex_at_birth,
                allergies=payload.allergies,
                medical_history=payload.medical_history,
            )
            await self._repo.add_profile(existing)
        else:
            existing.date_of_birth = payload.date_of_birth
            existing.sex_at_birth = payload.sex_at_birth
            existing.allergies = payload.allergies
            existing.medical_history = payload.medical_history

        await self._audit.record_phi_access(
            principal=self._principal,
            person_uid=person_uid,
            action="phi.profile.upsert",
            reason=reason,
        )
        return existing

    async def require_profile(
        self, tenant_id: TenantId, person_uid: PersonUID
    ) -> PatientProfile:
        self._ensure_authorised(person_uid, "read PHI profile")
        profile = await self._repo.get_profile(tenant_id, person_uid)
        if profile is None:
            raise NotFoundError(
                "patient profile not found",
                details={"person_uid": str(person_uid)},
            )
        return profile

    # --- Aggregate counts ---

    # Phase 1 / HIPAA-deferred carve-out: aggregate counts do not carry a
    # ``person_uid`` so the per-person :meth:`_ensure_authorised` gate does
    # not apply. The aggregate itself is not PHI (no clinical fields, no
    # patient identity) — only the row count is returned. Per
    # ``feedback_hipaa_runtime_deferred.md`` the runtime gate is deferred;
    # when it lands, replace the no-op below with a tenant-level
    # ``Principal.can_read_phi_aggregates()`` check.
    async def count_consultations_between(
        self, tenant_id: TenantId, start: datetime, end: datetime
    ) -> int:
        """Count rows in ``phi.consultation`` with ``occurred_at ∈ [start, end)``."""
        return await self._repo.count_consultations_between(tenant_id, start, end)

    async def person_uids_with_consultation(
        self, tenant_id: TenantId, person_uids: list[UUID]
    ) -> set[UUID]:
        """Return the subset of ``person_uids`` that have at least one consultation.

        Aggregate / boolean projection only — no clinical content crosses
        the boundary, so the same Phase 1 carve-out applies.
        """
        return await self._repo.person_uids_with_consultation(
            tenant_id, person_uids
        )
