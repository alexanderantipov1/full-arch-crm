"""Ingest HTTP routes — capture inbound webhooks/events verbatim."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from apps.api.dependencies import get_ingest_service, get_principal_with_tenant
from packages.core.exceptions import NotFoundError
from packages.core.security import Principal
from packages.ingest.schemas import RawEventIn, RawEventOut
from packages.ingest.service import IngestService

router = APIRouter(prefix="/ingest", tags=["ingest"])

PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]


@router.post("/events", response_model=RawEventOut, status_code=status.HTTP_202_ACCEPTED)
async def capture_event(
    payload: RawEventIn,
    principal: PrincipalDep,
    svc: IngestService = Depends(get_ingest_service),
) -> RawEventOut:
    event = await svc.capture(principal.require_tenant(), payload)
    return RawEventOut.model_validate(event)


# --- Inspector raw events ----------------------------------------------


class _InspectorEventOut(BaseModel):
    id: UUID
    provider: str
    external_id: str
    kind: str
    fetched_at: datetime
    sync_run_id: UUID | None
    payload: dict[str, object]
    resolved_person_uid: UUID | None


class _InspectorListOut(BaseModel):
    items: list[_InspectorEventOut]
    total: int


@router.get(
    "/dev/inspector/raw-events",
    response_model=_InspectorListOut,
    tags=["dev"],
)
async def list_inspector_raw_events(
    principal: PrincipalDep,
    svc: Annotated[IngestService, Depends(get_ingest_service)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    provider: Annotated[str | None, Query()] = None,
) -> _InspectorListOut:
    tenant_id = principal.require_tenant()
    events = await svc.list_recent_raw_events(
        tenant_id, limit=limit, provider=provider
    )
    total = await svc.count_raw_events(tenant_id, provider=provider)
    return _InspectorListOut(
        items=[
            _InspectorEventOut(
                id=e.id,
                provider=e.source,
                external_id=e.external_id or "",
                kind=e.event_type,
                fetched_at=e.received_at,
                sync_run_id=None,
                payload=e.payload,
                resolved_person_uid=None,
            )
            for e in events
        ],
        total=total,
    )


@router.get(
    "/dev/inspector/raw-events/{event_id}",
    response_model=_InspectorEventOut,
    tags=["dev"],
)
async def get_inspector_raw_event(
    event_id: UUID,
    principal: PrincipalDep,
    svc: Annotated[IngestService, Depends(get_ingest_service)],
) -> _InspectorEventOut:
    """Return one tenant-scoped raw event with its verbatim payload.

    Sibling of :func:`list_inspector_raw_events` — used by the PM Payments
    page drilldown to render the full provider payload behind a payment
    row. Reuses the existing local-dev Inspector carve-out (see
    ``packages/ingest/CLAUDE.md``); the tenant filter on the underlying
    repository ensures one tenant cannot read another tenant's raw event.
    """
    tenant_id = principal.require_tenant()
    event = await svc.get_raw_event(tenant_id, event_id)
    if event is None:
        raise NotFoundError(
            "raw event not found",
            details={"event_id": str(event_id)},
        )
    return _InspectorEventOut(
        id=event.id,
        provider=event.source,
        external_id=event.external_id or "",
        kind=event.event_type,
        fetched_at=event.received_at,
        sync_run_id=None,
        payload=event.payload,
        resolved_person_uid=None,
    )
