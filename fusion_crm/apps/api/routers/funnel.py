"""Funnel analytics HTTP routes (ENG-419).

Five endpoints power the funnel dashboard:

- ``GET /funnel/aggregate`` — per ``(stage × actor × role)`` counts +
  per-stage totals.
- ``GET /funnel/dropoff`` — per-stage drop-off attribution headline
  (people who never advanced past stage S, attributed to the operational
  owner that owned them at S, weighed in $ per decision-log D-W3-3).
- ``GET /funnel/revenue-by-actor`` — net realized payments aggregated
  by actor + role; reuses the PM Payments formula so revenue slices
  reconcile.
- ``GET /funnel/owners`` — distinct actors on responsibility rows for
  the picker.

Routes compose ``InteractionService`` (aggregates) with ``ActorService``
(display names) and ``OpsService`` (Opportunity.amount lookups). No
business logic lives here — the route only stitches DTOs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from apps.api.dependencies import (
    get_actor_service,
    get_interaction_service,
    get_ops_service,
    get_principal_with_tenant,
)
from packages.actor.service import ActorService
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.interaction.schemas import (
    FUNNEL_STAGE_ORDER,
    FunnelStage,
    ResponsibilityRole,
)
from packages.interaction.service import InteractionService
from packages.ops.service import OpsService


def _as_int(value: object) -> int:
    """Coerce a DB row value (statically typed ``object``) to int."""
    return int(value)  # type: ignore[call-overload]


def _as_float(value: object) -> float:
    """Coerce a DB row value (statically typed ``object``) to float."""
    return float(value)  # type: ignore[arg-type]


router = APIRouter(prefix="/funnel", tags=["funnel"])
log = get_logger("api.funnel")

# Ordered axis used by the funnel-stage envelope. Re-exported under the
# old local name for readability; the canonical tuple lives in
# packages.interaction.schemas so the service-side dropoff bucketing
# uses the same axis.
_STAGE_ORDER: tuple[FunnelStage, ...] = FUNNEL_STAGE_ORDER


class FunnelActorOut(BaseModel):
    actor_id: UUID
    actor_type: str
    name: str
    role: ResponsibilityRole


class FunnelStageActorBucketOut(BaseModel):
    actor: FunnelActorOut
    event_count: int
    person_count: int


class FunnelStageAggregateOut(BaseModel):
    stage: FunnelStage
    event_count: int
    person_count: int
    by_actor: list[FunnelStageActorBucketOut]


class FunnelAppliedFiltersOut(BaseModel):
    # ENG-418 fix: emit the field as ``from`` so the Zod FE schema parses
    # (Python keyword forbids the bare ``from`` attribute name). All four
    # funnel routes set ``response_model_by_alias=True`` so FastAPI uses
    # the alias during serialization.
    model_config = ConfigDict(populate_by_name=True)

    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    source_provider: Literal["salesforce", "carestack"] | None = None
    location_id: UUID | None = None
    role: ResponsibilityRole | None = None


class FunnelAggregateOut(BaseModel):
    stages: list[FunnelStageAggregateOut]
    filters: FunnelAppliedFiltersOut


class FunnelDropoffActorBucketOut(BaseModel):
    actor: FunnelActorOut | None
    person_count: int
    dollar_total: float


class FunnelDropoffStageOut(BaseModel):
    stage: FunnelStage
    person_count: int
    dollar_total: float
    by_operational_actor: list[FunnelDropoffActorBucketOut]


class FunnelDropoffOut(BaseModel):
    stages: list[FunnelDropoffStageOut]
    filters: FunnelAppliedFiltersOut


class FunnelRevenueByActorRowOut(BaseModel):
    actor: FunnelActorOut
    collected_total: float
    payment_count: int


class FunnelRevenueByActorOut(BaseModel):
    items: list[FunnelRevenueByActorRowOut]
    filters: FunnelAppliedFiltersOut


class FunnelOwnersOut(BaseModel):
    items: list[FunnelActorOut]


@router.get(
    "/aggregate",
    response_model=FunnelAggregateOut,
    response_model_by_alias=True,
)
async def get_funnel_aggregate(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    interaction: Annotated[InteractionService, Depends(get_interaction_service)],
    actor: Annotated[ActorService, Depends(get_actor_service)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    source_provider: Annotated[
        Literal["salesforce", "carestack"] | None, Query()
    ] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    role: Annotated[ResponsibilityRole | None, Query()] = None,
) -> FunnelAggregateOut:
    """Per-stage funnel counts × responsible actor."""
    tenant_id = principal.require_tenant()
    raw_by_actor = await interaction.funnel_aggregate(
        tenant_id,
        occurred_from=from_,
        occurred_to=to,
        source_provider=source_provider,
        location_id=location_id,
        role=role,
    )
    totals = await interaction.funnel_totals(
        tenant_id,
        occurred_from=from_,
        occurred_to=to,
        source_provider=source_provider,
        location_id=location_id,
    )

    actor_ids = {UUID(str(row["actor_id"])) for row in raw_by_actor}
    actor_lookup = await _resolve_actors(tenant_id, actor, actor_ids)

    by_stage: dict[FunnelStage, list[FunnelStageActorBucketOut]] = {
        stage: [] for stage in _STAGE_ORDER
    }
    for row in raw_by_actor:
        stage = row["stage"]
        if stage not in by_stage:
            continue
        actor_id = UUID(str(row["actor_id"]))
        actor_row = actor_lookup.get(actor_id)
        if actor_row is None:
            continue
        by_stage[stage].append(
            FunnelStageActorBucketOut(
                actor=FunnelActorOut(
                    actor_id=actor_id,
                    actor_type=actor_row["actor_type"],
                    name=actor_row["name"],
                    role=row["role"],
                ),
                event_count=_as_int(row["event_count"]),
                person_count=_as_int(row["person_count"]),
            )
        )

    stages: list[FunnelStageAggregateOut] = []
    for stage in _STAGE_ORDER:
        stage_totals = totals.get(stage, {"event_count": 0, "person_count": 0})
        stages.append(
            FunnelStageAggregateOut(
                stage=stage,
                event_count=int(stage_totals.get("event_count", 0)),
                person_count=int(stage_totals.get("person_count", 0)),
                by_actor=by_stage[stage],
            )
        )

    return FunnelAggregateOut(
        stages=stages,
        filters=FunnelAppliedFiltersOut(
            from_=from_,
            to=to,
            source_provider=source_provider,
            location_id=location_id,
            role=role,
        ),
    )


@router.get(
    "/dropoff",
    response_model=FunnelDropoffOut,
    response_model_by_alias=True,
)
async def get_funnel_dropoff(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    interaction: Annotated[InteractionService, Depends(get_interaction_service)],
    ops: Annotated[OpsService, Depends(get_ops_service)],
    actor: Annotated[ActorService, Depends(get_actor_service)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    source_provider: Annotated[
        Literal["salesforce", "carestack"] | None, Query()
    ] = None,
    location_id: Annotated[UUID | None, Query()] = None,
) -> FunnelDropoffOut:
    """Per-stage drop-off attribution headline.

    Drop-off = persons whose latest funnel event is at stage S (the
    highest stage they ever reached) AND who never advanced past it.
    Attributed to the operational owner that owned them at S.

    The bucketing, $ basis selection, and stage totals live in
    :meth:`InteractionService.compute_funnel_dropoff` (ENG-418 fix):
    this route only fetches the Opportunity.amount lookup (which
    crosses into ``ops``) and resolves actor display names from
    ``ActorService``.
    """
    tenant_id = principal.require_tenant()

    # ops lookup is done route-side because ``packages.interaction``
    # cannot import ``packages.ops`` (matrix). The service consumes the
    # mapping for the non-won stages' $ basis (D-W3-3).
    raw_rows = await interaction.funnel_dropoff_by_person(
        tenant_id,
        occurred_from=from_,
        occurred_to=to,
        source_provider=source_provider,
        location_id=location_id,
    )
    person_uids = [UUID(str(row["person_uid"])) for row in raw_rows]
    opp_amount_by_person = await ops.sum_opportunity_amount_for_persons(
        tenant_id, person_uids
    )

    computed = await interaction.compute_funnel_dropoff(
        tenant_id,
        opp_amount_by_person=opp_amount_by_person,
        occurred_from=from_,
        occurred_to=to,
        source_provider=source_provider,
        location_id=location_id,
    )

    actor_ids = {
        bucket.actor_id
        for stage in computed
        for bucket in stage.by_actor
        if bucket.actor_id is not None
    }
    actor_lookup = await _resolve_actors(tenant_id, actor, actor_ids)

    stages: list[FunnelDropoffStageOut] = []
    for stage in computed:
        actor_rows: list[FunnelDropoffActorBucketOut] = []
        for bucket in stage.by_actor:
            resolved = (
                actor_lookup.get(bucket.actor_id)
                if bucket.actor_id is not None
                else None
            )
            actor_dto = (
                FunnelActorOut(
                    actor_id=bucket.actor_id,
                    actor_type=resolved["actor_type"],
                    name=resolved["name"],
                    role="operational",
                )
                if bucket.actor_id is not None and resolved is not None
                else None
            )
            actor_rows.append(
                FunnelDropoffActorBucketOut(
                    actor=actor_dto,
                    person_count=bucket.person_count,
                    dollar_total=bucket.dollar_total,
                )
            )
        stages.append(
            FunnelDropoffStageOut(
                stage=stage.stage,
                person_count=stage.person_count,
                dollar_total=stage.dollar_total,
                by_operational_actor=actor_rows,
            )
        )

    return FunnelDropoffOut(
        stages=stages,
        filters=FunnelAppliedFiltersOut(
            from_=from_,
            to=to,
            source_provider=source_provider,
            location_id=location_id,
            role=None,
        ),
    )


@router.get(
    "/revenue-by-actor",
    response_model=FunnelRevenueByActorOut,
    response_model_by_alias=True,
)
async def get_funnel_revenue_by_actor(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    interaction: Annotated[InteractionService, Depends(get_interaction_service)],
    actor: Annotated[ActorService, Depends(get_actor_service)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    source_provider: Annotated[
        Literal["salesforce", "carestack"] | None, Query()
    ] = None,
    location_id: Annotated[UUID | None, Query()] = None,
    role: Annotated[ResponsibilityRole | None, Query()] = None,
) -> FunnelRevenueByActorOut:
    """Net realized payment $ attributed to each actor + role."""
    tenant_id = principal.require_tenant()
    rows = await interaction.funnel_revenue_by_actor(
        tenant_id,
        occurred_from=from_,
        occurred_to=to,
        source_provider=source_provider,
        location_id=location_id,
        role=role,
    )
    actor_ids = {UUID(str(row["actor_id"])) for row in rows}
    actor_lookup = await _resolve_actors(tenant_id, actor, actor_ids)

    items: list[FunnelRevenueByActorRowOut] = []
    for row in rows:
        actor_id = UUID(str(row["actor_id"]))
        actor_row = actor_lookup.get(actor_id)
        if actor_row is None:
            continue
        items.append(
            FunnelRevenueByActorRowOut(
                actor=FunnelActorOut(
                    actor_id=actor_id,
                    actor_type=actor_row["actor_type"],
                    name=actor_row["name"],
                    role=row["role"],
                ),
                collected_total=_as_float(row["collected_total"]),
                payment_count=_as_int(row["payment_count"]),
            )
        )
    items.sort(key=lambda r: r.collected_total, reverse=True)

    return FunnelRevenueByActorOut(
        items=items,
        filters=FunnelAppliedFiltersOut(
            from_=from_,
            to=to,
            source_provider=source_provider,
            location_id=location_id,
            role=role,
        ),
    )


@router.get("/owners", response_model=FunnelOwnersOut)
async def get_funnel_owners(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    interaction: Annotated[InteractionService, Depends(get_interaction_service)],
    actor: Annotated[ActorService, Depends(get_actor_service)],
    role: Annotated[ResponsibilityRole | None, Query()] = None,
) -> FunnelOwnersOut:
    """Distinct actors on responsibility rows — drives the FE picker."""
    tenant_id = principal.require_tenant()
    rows = await interaction.funnel_distinct_actors(tenant_id, role=role)
    actor_ids = {UUID(str(row["actor_id"])) for row in rows}
    actor_lookup = await _resolve_actors(tenant_id, actor, actor_ids)

    items: list[FunnelActorOut] = []
    for row in rows:
        actor_id = UUID(str(row["actor_id"]))
        actor_row = actor_lookup.get(actor_id)
        if actor_row is None:
            continue
        items.append(
            FunnelActorOut(
                actor_id=actor_id,
                actor_type=actor_row["actor_type"],
                name=actor_row["name"],
                role=row["role"],
            )
        )
    items.sort(key=lambda r: (r.role, r.name.lower()))
    return FunnelOwnersOut(items=items)


async def _resolve_actors(
    tenant_id: TenantId,
    actor: ActorService,
    actor_ids: set[UUID],
) -> dict[UUID, dict[str, str]]:
    """Batch-resolve actor display names by id (route-side composition)."""
    out: dict[UUID, dict[str, str]] = {}
    for actor_id in actor_ids:
        try:
            row = await actor.get_actor(tenant_id, actor_id)
            out[actor_id] = {"actor_type": row.actor_type, "name": row.name}
        except Exception as exc:
            # Missing actor → caller drops the responsibility bucket
            # rather than surfacing a stale id. RESTRICT on the FK means
            # this should never happen at steady state.
            log.warning(
                "funnel_actor_resolution_failed",
                tenant_id=str(tenant_id),
                actor_id=str(actor_id),
                error=str(exc),
            )
            continue
    return out
