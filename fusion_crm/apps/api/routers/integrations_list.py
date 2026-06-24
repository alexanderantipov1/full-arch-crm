"""Integrations list endpoint — staff UI provider-card aggregation.

Returns one :class:`IntegrationAccountOut` per provider the platform
supports today. Source of truth is ``tenant.integration_credential``: a
present, active row -> ``connected``; an expired usable row ->
``needs_reconnect``; absent -> ``disconnected``. The list is what the
``/integrations`` page renders so the UI never sees the underlying 409
(missing credential) from per-provider pull routes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db, get_principal_with_tenant
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.integrations.models import IntegrationAccount, SyncRun
from packages.tenant.credential_service import IntegrationCredentialService

router = APIRouter(prefix="/integrations", tags=["integrations"])

_SURFACED_PROVIDERS: tuple[tuple[str, str], ...] = (
    ("salesforce", "oauth_token"),
    ("carestack", "password_grant"),
    # Marketing / SEO providers (ENG-491) — bootstrap ``api_key`` credentials.
    # A present active row flips the card to ``connected``.
    ("google_ads", "api_key"),
    ("meta_ads", "api_key"),
    ("google_analytics", "api_key"),
    ("google_search_console", "api_key"),
)

_DISCONNECTED_NS = uuid.UUID("00000000-fde5-1c0f-5111-deadbeef0001")

IntegrationStatus = Literal[
    "disconnected",
    "connecting",
    "connected",
    "syncing",
    "error",
    "needs_reconnect",
]


class SyncRunSummaryOut(BaseModel):
    id: uuid.UUID
    status: Literal["running", "success", "failed"]
    records_pulled: int
    finished_at: datetime | None


class IntegrationAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    id: uuid.UUID
    provider: str
    status: IntegrationStatus
    display_name: str | None
    last_sync_at: datetime | None = None
    last_sync_summary: SyncRunSummaryOut | None = None
    error_message: str | None = None


class IntegrationListOut(BaseModel):
    items: list[IntegrationAccountOut]


def _disconnected_id(tenant_id: TenantId, provider: str) -> uuid.UUID:
    return uuid.uuid5(_DISCONNECTED_NS, f"{tenant_id}:{provider}")


def _map_sync_status(db_status: str) -> Literal["running", "success", "failed"]:
    if db_status in ("succeeded", "success", "partial"):
        return "success"
    if db_status == "running":
        return "running"
    return "failed"


async def _latest_sync_run(
    db: AsyncSession,
    tenant_id: TenantId,
    provider: str,
) -> SyncRun | None:
    stmt = (
        select(SyncRun)
        .join(IntegrationAccount, IntegrationAccount.id == SyncRun.account_id)
        .where(
            SyncRun.tenant_id == tenant_id,
            IntegrationAccount.provider == provider,
        )
        .order_by(SyncRun.started_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


@router.get("", response_model=IntegrationListOut)
async def list_integrations(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IntegrationListOut:
    tenant_id = principal.require_tenant()
    cred_svc = IntegrationCredentialService(db)

    items: list[IntegrationAccountOut] = []
    for provider, usable_kind in _SURFACED_PROVIDERS:
        rows = await cred_svc.list_for_tenant(tenant_id, provider_kind=provider)
        active = next(
            (
                r
                for r in rows
                if r.status == "active" and r.credential_kind == usable_kind
            ),
            None,
        )

        run = await _latest_sync_run(db, tenant_id, provider)
        sync_at: datetime | None = None
        summary: SyncRunSummaryOut | None = None
        error_msg: str | None = None

        if run is not None:
            sync_at = run.finished_at or run.started_at
            summary = SyncRunSummaryOut(
                id=run.id,
                status=_map_sync_status(run.status),
                records_pulled=run.records_succeeded or 0,
                finished_at=run.finished_at,
            )
            if run.status in ("failed", "skipped_credential"):
                error_msg = run.error or f"Last sync {run.status}"

        if active is None:
            expired = next(
                (
                    r
                    for r in rows
                    if r.status == "expired" and r.credential_kind == usable_kind
                ),
                None,
            )
            if expired is not None:
                items.append(
                    IntegrationAccountOut(
                        id=expired.id,
                        provider=provider,
                        status="needs_reconnect",
                        display_name=expired.display_name,
                        last_sync_at=sync_at,
                        last_sync_summary=summary,
                        error_message=(
                            error_msg
                            or "Reconnect this integration to resume scheduled sync."
                        ),
                    )
                )
                continue

            items.append(
                IntegrationAccountOut(
                    id=_disconnected_id(tenant_id, provider),
                    provider=provider,
                    status="disconnected",
                    display_name=None,
                    last_sync_at=sync_at,
                    last_sync_summary=summary,
                    error_message=error_msg,
                )
            )
            continue

        items.append(
            IntegrationAccountOut(
                id=active.id,
                provider=provider,
                status="connected",
                display_name=active.display_name,
                last_sync_at=sync_at,
                last_sync_summary=summary,
                error_message=error_msg,
            )
        )

    return IntegrationListOut(items=items)
