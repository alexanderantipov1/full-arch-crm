"""Ops HTTP routes — PHI-free."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import (
    get_db,
    get_identity_service,
    get_interaction_service,
    get_notification_event_service,
    get_ops_service,
    get_principal_with_tenant,
)
from packages.core.security import Principal
from packages.core.types import PersonUID, TenantId
from packages.identity.service import IdentityService
from packages.integrations.chat.event_service import NotificationEventService
from packages.integrations.chat.events import EVENT_LEAD_CREATED
from packages.interaction.service import InteractionService
from packages.ops.schemas import (
    ConsultationOut,
    FollowupTaskIn,
    FollowupTaskOut,
    LeadIn,
    LeadOut,
    LeadSourceLeadListOut,
    LeadSourceTreeOut,
    OpsPersonSnapshot,
    PersonLocationProfileOut,
)
from packages.ops.service import OpsService
from packages.tenant.service import LocationService

router = APIRouter(prefix="/ops", tags=["ops"])

PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]


async def _location_needles(
    db: AsyncSession, tenant_id: TenantId, location_id: UUID | None
) -> list[str] | None:
    """Resolve a location id into assigned_center soft-match needles.

    Same approximation the PM dashboard uses (ENG-398): Lead rows carry
    free-text ``extra->>'assigned_center'``, so the filter matches the
    location's short_name / name / city as substrings.
    """
    if location_id is None:
        return None
    loc = await LocationService(db).get_location(tenant_id, location_id)
    return [s for s in (loc.short_name, loc.name, loc.city) if s] or None


@router.get("/persons/{person_uid}/snapshot", response_model=OpsPersonSnapshot)
async def ops_snapshot(
    person_uid: UUID,
    principal: PrincipalDep,
    svc: OpsService = Depends(get_ops_service),
) -> OpsPersonSnapshot:
    return await svc.snapshot(principal.require_tenant(), PersonUID(person_uid))


@router.post("/leads", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadIn,
    principal: PrincipalDep,
    svc: OpsService = Depends(get_ops_service),
    events: NotificationEventService = Depends(get_notification_event_service),
    identity: IdentityService = Depends(get_identity_service),
) -> LeadOut:
    # ENG-437 D2: ``ops`` MUST NOT import ``integrations`` (per the
    # packages import matrix), so the flagship ``lead.created`` emit is
    # wired here at the API boundary — which legitimately depends on both
    # services and owns the request transaction (the outbox row and the
    # Lead commit together via ``get_db``).
    tenant_id = principal.require_tenant()
    lead = await svc.create_lead(tenant_id, payload)
    # Event context. ``has_phone`` stays a NON-PII boolean for the
    # missing-phone field-control rule. ENG-460: the messenger is an authorised
    # PHI surface and the rich ``lead.created`` card renders real name + phone,
    # so resolve them HERE at the boundary (mirroring the ingest worker path) —
    # otherwise the full-mode template would render this API-created lead with
    # empty name/phone. The identity read shares the request transaction.
    context: dict[str, object] = {
        "lead": {"source": lead.source},
        "source": lead.source,
    }
    if "phone" in payload.extra or "Phone" in payload.extra:
        context["has_phone"] = bool(
            payload.extra.get("phone") or payload.extra.get("Phone")
        )
    person = await identity.get_person(tenant_id, PersonUID(lead.person_uid))
    if person.display_name:
        context["name"] = person.display_name
    phone = await identity.get_primary_phone(tenant_id, PersonUID(lead.person_uid))
    if phone:
        context["phone"] = phone
    await events.emit(
        tenant_id,
        EVENT_LEAD_CREATED,
        context,
        principal=principal,
        person_uid=lead.person_uid,
    )
    return LeadOut.model_validate(lead)


@router.post("/followups", response_model=FollowupTaskOut, status_code=status.HTTP_201_CREATED)
async def create_followup(
    payload: FollowupTaskIn,
    principal: PrincipalDep,
    svc: OpsService = Depends(get_ops_service),
) -> FollowupTaskOut:
    task = await svc.create_followup(principal.require_tenant(), payload)
    return FollowupTaskOut.model_validate(task)


@router.get("/persons/{person_uid}/followups", response_model=list[FollowupTaskOut])
async def list_followups(
    person_uid: UUID,
    principal: PrincipalDep,
    svc: OpsService = Depends(get_ops_service),
) -> list[FollowupTaskOut]:
    tasks = await svc.list_followups(principal.require_tenant(), PersonUID(person_uid))
    return [FollowupTaskOut.model_validate(t) for t in tasks]


@router.get(
    "/persons/{person_uid}/consultations",
    response_model=list[ConsultationOut],
)
async def list_consultations(
    person_uid: UUID,
    principal: PrincipalDep,
    svc: OpsService = Depends(get_ops_service),
) -> list[ConsultationOut]:
    return await svc.list_consultations_for_person(
        principal.require_tenant(), person_uid
    )


@router.get("/analytics/lead-sources/tree", response_model=LeadSourceTreeOut)
async def lead_source_tree(
    principal: PrincipalDep,
    svc: Annotated[OpsService, Depends(get_ops_service)],
    interaction: Annotated[InteractionService, Depends(get_interaction_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    location_id: Annotated[UUID | None, Query()] = None,
) -> LeadSourceTreeOut:
    """Hierarchical lead-source funnel tree for the DEV explorer (ENG-391).

    Collected cash comes from the interaction domain (per-person net
    Collected) and is attributed to nodes by the ops service — the route
    only wires the two services together.
    """
    tenant_id = principal.require_tenant()
    clean_search = search.strip() if search is not None else None
    collected = await interaction.collected_by_person(tenant_id)
    location_match = await _location_needles(db, tenant_id, location_id)
    return await svc.get_lead_source_tree(
        tenant_id,
        created_from=from_,
        created_to=to,
        search=clean_search or None,
        collected_by_person=collected,
        location_match=location_match,
        location_id=location_id,
    )


@router.get("/analytics/lead-sources/leads", response_model=LeadSourceLeadListOut)
async def lead_source_leads(
    principal: PrincipalDep,
    svc: Annotated[OpsService, Depends(get_ops_service)],
    interaction: Annotated[InteractionService, Depends(get_interaction_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
    channel: Annotated[str | None, Query(max_length=240)] = None,
    source: Annotated[str | None, Query(max_length=240)] = None,
    medium: Annotated[str | None, Query(max_length=240)] = None,
    campaign: Annotated[str | None, Query(max_length=240)] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: Annotated[Literal["created", "collected"], Query()] = "created",
    location_id: Annotated[UUID | None, Query()] = None,
) -> LeadSourceLeadListOut:
    """Drill-down lead list behind one lead-source explorer node.

    At least one of ``channel``/``source`` is required (service-validated).
    ENG-394 adds the virtual channel level; ENG-395 enriches person identity;
    ENG-396 wires per-person Collected cash from the interaction domain.
    """
    tenant_id = principal.require_tenant()
    collected = await interaction.collected_by_person(tenant_id)
    location_match = await _location_needles(db, tenant_id, location_id)
    return await svc.list_leads_for_source_node(
        tenant_id,
        channel=channel,
        source=source,
        medium=medium,
        campaign=campaign,
        created_from=from_,
        created_to=to,
        limit=limit,
        offset=offset,
        collected_by_person=collected,
        sort=sort,
        location_match=location_match,
        location_id=location_id,
    )


@router.get(
    "/persons/{person_uid}/location-profiles",
    response_model=list[PersonLocationProfileOut],
)
async def list_location_profiles(
    person_uid: UUID,
    principal: PrincipalDep,
    svc: OpsService = Depends(get_ops_service),
) -> list[PersonLocationProfileOut]:
    return await svc.list_person_location_profiles_for_person(
        principal.require_tenant(), person_uid
    )
