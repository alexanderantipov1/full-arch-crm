"""Tenant HTTP routes — multi-tenant configuration surface.

ENG-124: ``POST /tenant/locations/sync-from-carestack`` triggers an
idempotent pull of CareStack locations into ``tenant.location``.

The ``/tenant/credentials/{id}`` mutations (DELETE, set-default, PUT)
wire the operator's Settings → Mailboxes controls to
``IntegrationCredentialService``.

Per ``apps/api/CLAUDE.md`` this router is a thin pass-through — the
business logic lives in service methods.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import (
    CareStackClientFactory,
    get_carestack_client_factory,
    get_db,
    get_location_service,
    get_principal_with_tenant,
    get_tenant_service,
)
from packages.agent_runtime.schemas import AgentRuntimeConnectionCheckOut
from packages.agent_runtime.service import AgentRuntimeService
from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)
from packages.tenant.schemas import (
    CurrentTenantOut,
    ImportSummary,
    IntegrationCredentialBootstrapIn,
    IntegrationCredentialOut,
    IntegrationCredentialUpdate,
    LocationOut,
    SettingIn,
    SettingOut,
    TenantWithRelationsOut,
)
from packages.tenant.service import LocationService, TenantService

router = APIRouter(prefix="/tenant", tags=["tenant"])

log = get_logger("api.tenant")

LocationServiceDep = Annotated[LocationService, Depends(get_location_service)]
TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]
PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]
CareStackFactoryDep = Annotated[CareStackClientFactory, Depends(get_carestack_client_factory)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("/current", response_model=TenantWithRelationsOut)
async def get_current_tenant(
    tenant_svc: TenantServiceDep,
    location_svc: LocationServiceDep,
    principal: PrincipalDep,
) -> TenantWithRelationsOut:
    """Read the request principal's tenant + locations + credentials + settings.

    Phase 1 is single-tenant: the principal is resolved against the
    bootstrap tenant via ``Settings.tenant_default_slug``. Credentials
    are returned as metadata only — encrypted ``payload`` blobs never
    cross the service boundary.
    """
    tenant_id: TenantId = principal.require_tenant()
    tenant = await tenant_svc.get_tenant(tenant_id)
    locations = await location_svc.list_locations(tenant_id)
    credentials = await tenant_svc.list_credentials(tenant_id)
    settings = await tenant_svc.list_settings(tenant_id)
    return TenantWithRelationsOut(
        tenant=CurrentTenantOut.model_validate(tenant),
        locations=[LocationOut.model_validate(loc) for loc in locations],
        integrations=[IntegrationCredentialOut.model_validate(c) for c in credentials],
        settings=[SettingOut.model_validate(s) for s in settings],
    )


class SyncFromCareStackIn(BaseModel):
    """Optional body for the sync route.

    ``tenant_slug`` is accepted for parity with the bootstrap script
    and future multi-tenant routing, but Phase 1 ignores it: the
    tenant comes from the request principal (resolved via
    ``Settings.tenant_default_slug``). When the slug is supplied and
    does not match the resolved tenant the API returns 422.
    """

    model_config = ConfigDict(extra="forbid")

    tenant_slug: str | None = Field(default=None, max_length=64)


class TenantSettingUpdateIn(BaseModel):
    """Update body for one tenant setting key."""

    model_config = ConfigDict(extra="forbid")

    value: dict[str, object]


@router.post("/locations/sync-from-carestack")
async def sync_locations_from_carestack(
    svc: LocationServiceDep,
    tenant_svc: TenantServiceDep,
    principal: PrincipalDep,
    factory: CareStackFactoryDep,
    body: SyncFromCareStackIn | None = None,
) -> ImportSummary:
    """Trigger a sync of locations from CareStack into ``tenant.location``.

    Idempotent. Re-running is safe — only changed columns are written
    and missing locations are deactivated rather than deleted.
    """
    tenant_id: TenantId = principal.require_tenant()
    if body is not None and body.tenant_slug:
        # Defence-in-depth: refuse to operate against the wrong tenant
        # if the caller explicitly named one and it does not match the
        # resolved principal. The tenant resolver is single-tenant in
        # Phase 1, so a mismatch here means a script mis-targeted.
        resolved = await tenant_svc.get_tenant(tenant_id)
        if resolved.slug != body.tenant_slug:
            raise ValidationError(
                "tenant_slug does not match resolved tenant",
                details={
                    "expected": resolved.slug,
                    "supplied": body.tenant_slug,
                },
            )

    client = await factory()
    try:
        return await svc.import_locations_from_carestack(tenant_id, client, principal=principal)
    finally:
        close = getattr(client, "close", None)
        if close is not None:
            await close()


# ------------------------------------------------------------ credentials


@router.put("/settings/{key}", response_model=SettingOut)
async def upsert_setting(
    key: str,
    payload: TenantSettingUpdateIn,
    tenant_svc: TenantServiceDep,
    principal: PrincipalDep,
) -> SettingOut:
    """Upsert one public tenant setting value.

    The setting key is part of the route so clients cannot accidentally change
    a different key from the request body. Settings are general company config;
    secrets still belong only in tenant credentials.
    """
    tenant_id = principal.require_tenant()
    setting = await tenant_svc.upsert_setting(
        tenant_id,
        SettingIn(key=key, value=payload.value),
        principal=principal,
    )
    return SettingOut.model_validate(setting)


@router.get("/credentials", response_model=list[IntegrationCredentialOut])
async def list_credentials(
    principal: PrincipalDep,
    db: DbDep,
    provider_kind: str | None = Query(default=None),
    include_revoked: bool = Query(default=False),
) -> list[IntegrationCredentialOut]:
    """List credential metadata for the current tenant.

    ``payload`` is not part of ``IntegrationCredentialOut`` and never
    leaves the backend.
    """
    tenant_id = principal.require_tenant()
    cred_svc = IntegrationCredentialService(db)
    return await cred_svc.list_for_tenant(
        tenant_id,
        provider_kind=provider_kind,
        include_revoked=include_revoked,
    )


@router.post("/credentials", response_model=IntegrationCredentialOut)
async def upsert_bootstrap_credential(
    payload: IntegrationCredentialBootstrapIn,
    principal: PrincipalDep,
    db: DbDep,
) -> IntegrationCredentialOut:
    """Store operator-entered bootstrap credentials for the current tenant.

    Secrets are accepted only on this write path and are immediately handed
    to ``IntegrationCredentialService`` for encrypted persistence. The
    response is metadata-only.
    """
    tenant_id = principal.require_tenant()
    cred_svc = IntegrationCredentialService(db)
    return await cred_svc.upsert_bootstrap_credentials(
        tenant_id,
        payload,
        principal=principal,
    )


@router.post("/credentials/openai/test", response_model=AgentRuntimeConnectionCheckOut)
async def test_openai_credential(
    principal: PrincipalDep,
    db: DbDep,
) -> AgentRuntimeConnectionCheckOut:
    """Run a safe agent-runtime OpenAI health check for the current tenant."""
    principal.require_tenant()
    return await AgentRuntimeService(db).test_openai_connection(principal)


@router.put("/credentials/{credential_id}", response_model=IntegrationCredentialOut)
async def update_credential(
    credential_id: UUID,
    payload: IntegrationCredentialUpdate,
    principal: PrincipalDep,
    db: DbDep,
) -> IntegrationCredentialOut:
    """Update credential metadata without touching encrypted payload."""
    tenant_id = principal.require_tenant()
    cred_svc = IntegrationCredentialService(db)
    try:
        return await cred_svc.update_metadata(
            credential_id,
            tenant_id=tenant_id,
            payload=payload,
            principal=principal,
        )
    except NoCredentialError as exc:
        raise NotFoundError(
            "credential not found",
            details={"credential_id": str(credential_id)},
        ) from exc


@router.delete("/credentials/{credential_id}", status_code=204)
async def revoke_credential(
    credential_id: UUID,
    principal: PrincipalDep,
    db: DbDep,
) -> Response:
    """Soft-revoke an integration credential.

    Calls ``IntegrationCredentialService.delete`` which flips
    ``status='revoked'`` (or hard-deletes a row that was never active).
    Audit row is written by the service.

    Returns 204 on success. 404 if the credential is not owned by the
    request principal's tenant or never existed — translated from
    :class:`NoCredentialError`.
    """
    tenant_id = principal.require_tenant()
    cred_svc = IntegrationCredentialService(db)
    try:
        await cred_svc.delete(credential_id, tenant_id=tenant_id, principal=principal)
    except NoCredentialError as exc:
        raise NotFoundError(
            "credential not found",
            details={"credential_id": str(credential_id)},
        ) from exc
    log.info(
        "tenant.credential.revoked",
        tenant_id=str(tenant_id),
        credential_id=str(credential_id),
    )
    return Response(status_code=204)


@router.post("/credentials/{credential_id}/set-default")
async def set_default_credential(
    credential_id: UUID,
    principal: PrincipalDep,
    db: DbDep,
) -> IntegrationCredentialOut:
    """Promote a credential to be the tenant default for its provider.

    The service method needs ``provider_kind`` to scope the atomic
    "clear other defaults" sweep, so we resolve it from the row first.
    """
    tenant_id = principal.require_tenant()
    cred_svc = IntegrationCredentialService(db)

    rows = await cred_svc.list_for_tenant(tenant_id, include_revoked=True)
    target = next((r for r in rows if r.id == credential_id), None)
    if target is None:
        raise NotFoundError(
            "credential not found",
            details={"credential_id": str(credential_id)},
        )

    try:
        return await cred_svc.set_default(
            credential_id,
            tenant_id=tenant_id,
            provider_kind=target.provider_kind,
            principal=principal,
        )
    except NoCredentialError as exc:
        raise NotFoundError(
            "credential not found",
            details={"credential_id": str(credential_id)},
        ) from exc
