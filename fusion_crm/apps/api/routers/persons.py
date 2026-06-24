"""Persons HTTP routes — staff UI list and detail surfaces.

Both endpoints mirror Zod schemas in ``apps/web/lib/api/schemas/person.ts``
(``PersonListSchema`` for the list, ``PersonDetailSchema`` for the detail).
They reuse the same composer pattern as ``apps/api/routers/dashboard.py``:
identity owns the persons read, ops contributes ``has_lead`` and the Lead
header, phi contributes ``has_consultation``, identity again contributes
the source providers + source links.

No business logic in this file — every cross-domain field is produced by
an existing service. These routes only stitch them into one DTO.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from apps.api.dependencies import (
    get_actor_service,
    get_identity_service,
    get_ingest_service,
    get_interaction_service,
    get_ops_service,
    get_phi_service,
    get_principal_with_tenant,
    get_tenant_service,
)
from packages.actor.service import ActorService
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.core.types import PersonUID, TenantId
from packages.identity.schemas import PersonSummaryOut
from packages.identity.service import IdentityService
from packages.ingest.schemas import (
    CarestackOriginRowOut,
    HouseholdMemberOut,
    PersonPaymentFinancialSummaryOut,
)
from packages.ingest.service import IngestService
from packages.interaction.schemas import (
    ResponsibilityRole,
)
from packages.interaction.service import InteractionService
from packages.ops.models import LeadStatus
from packages.ops.service import OpsService
from packages.phi.service import PhiService
from packages.tenant.service import TenantService

router = APIRouter(prefix="/persons", tags=["persons"])
log = get_logger("api.persons")

_DEFAULT_LIMIT = 100
_MAX_LIMIT = 500
# Source-link rows already represent a confirmed link between an external
# record and a person (the resolver wrote them). Match-candidate confidence
# lives on a separate ledger. For the staff read surface a hard 1.0 keeps
# the Zod contract happy without inventing a number.
_SOURCE_LINK_CONFIRMED_CONFIDENCE = 1.0


class PersonListOut(BaseModel):
    items: list[PersonSummaryOut]
    total: int


class PersonSourceLinkOut(BaseModel):
    """Shape consumed by the Zod ``SourceLinkSchema`` on the frontend."""

    provider: str
    external_id: str
    entity: str
    confidence: float
    provider_url: str | None = None
    first_seen_at: datetime | None = None


class PersonLeadHeaderOut(BaseModel):
    """Slim Lead projection used in the person-detail header card."""

    status: LeadStatus | None
    source: str | None
    created_at: datetime
    updated_at: datetime
    salesforce_status: str | None = None
    salesforce_created_at: datetime | None = None
    company: str | None = None
    campaign: str | None = None
    owner: str | None = None
    treatment_coordinator: str | None = None
    is_reactivation: bool = False


class PersonDetailOut(BaseModel):
    """Mirrors the Zod ``PersonDetailSchema``.

    ``consultations`` and ``timeline`` are returned empty in this revision:
    the detail page fetches consultations via
    ``GET /ops/persons/{uid}/consultations`` separately, and the timeline
    read surface lands with ENG-242 (workflow-ready ingest foundation,
    Task G).

    ``financial_summary`` (ENG-306) is the per-person Billed / Adjustments
    / Paid / Balance block from the latest CareStack payment-summary
    snapshot plus the accounting journal. ``snapshot_received_at=None``
    inside the DTO when patient ids exist but no snapshot has been
    captured yet — the UI uses the latter to render ``"—"`` instead of
    ``"$0"``.
    """

    summary: PersonSummaryOut
    source_links: list[PersonSourceLinkOut]
    lead: PersonLeadHeaderOut | None
    consultations: list[dict[str, object]]
    timeline: list[dict[str, object]]
    financial_summary: PersonPaymentFinancialSummaryOut | None = None
    # ENG-308: per-CareStack-pid origin context — drives "First ingest",
    # "Earliest activity", city/state, provider name, and the multi-link
    # expander on the staff person card.
    carestack_origin: list[CarestackOriginRowOut] = []
    # ENG-310: bidirectional navigational links to OTHER persons sharing
    # a normalised phone or email. Financials and consultations stay
    # separate — the resolver intentionally does NOT merge identities.
    household_members: list[HouseholdMemberOut] = []


class PersonTimelineResponsibleOut(BaseModel):
    """One responsible-actor entry on a timeline node (ENG-418)."""

    actor_id: UUID
    role: ResponsibilityRole
    actor_type: str
    name: str


class TimelineNodeDetailField(BaseModel):
    """One curated label/value pair for a timeline node card."""

    label: str
    value: str


class TimelineNodeDetail(BaseModel):
    """Curated "what actually happened" card, inlined per timeline node.

    The node ``summary`` stays no-PII (verb + provider + id). This card
    is a read-time projection of the verbatim ``ingest.raw_event.payload``
    into human-readable, kind-aware fields — task Type/Subject/Description,
    appointment notes/schedule, treatment estimates — with timestamps
    already rendered in the company timezone. Surfaced under the
    development-phase data visibility posture (root ``CLAUDE.md``); never
    persisted back into ``interaction.event``.
    """

    # Headline (e.g. a Salesforce Task ``Subject`` or appointment note);
    # ``None`` when the payload has no natural title for this kind.
    title: str | None = None
    # Human status label from the source record (e.g. "Completed",
    # "Not Started", "Scheduled") — drives the node status badge.
    status: str | None = None
    # ``True``/``False`` only when the source record models done/not-done
    # (Salesforce Tasks); ``None`` for kinds with no completion semantics
    # (leads, appointments, …).
    is_complete: bool | None = None
    fields: list[TimelineNodeDetailField] = []


class PersonTimelineEntryOut(BaseModel):
    """API-side timeline entry — extends the service DTO with actor names.

    The interaction service emits ``OperationalTimelineEntry`` with only
    ``(actor_id, role)`` tuples (the matrix forbids it from importing
    ``actor``). This DTO is the route's composition: same fields PLUS
    resolved actor display names and the inlined ``detail`` card.
    """

    kind: str
    occurred_at: datetime
    source_provider: str
    source_kind: str | None
    source_external_id: str | None
    # Link to the backing ``ingest.raw_event.id``; ``None`` for derived
    # events with no raw row (e.g. ``call_reference_found``).
    source_event_id: UUID | None = None
    # Curated "what happened" card, inlined so the whole chain is visible
    # at once with no extra round-trips. ``None`` for nodes with no raw
    # row to project.
    detail: TimelineNodeDetail | None = None
    data_class: str
    review_status: str
    summary: str
    projection: dict[str, object] | None = None
    operational_responsibles: list[PersonTimelineResponsibleOut] = []
    clinical_responsibles: list[PersonTimelineResponsibleOut] = []


class PersonTimelineCurrentOwnerOut(BaseModel):
    """Current per-person funnel owner header (ENG-418)."""

    stage: str
    actor_id: UUID | None
    actor_type: str | None
    name: str | None
    source_provider: str
    external_id: str
    opportunity_id: UUID | None = None


class PersonOperationalTimelineOut(BaseModel):
    items: list[PersonTimelineEntryOut]
    total: int
    # ENG-418: the "current owner" of the funnel — Lead owner until an
    # Opportunity exists that is not closed-lost, then the Opportunity
    # owner. ``None`` when the person has neither a Lead nor an
    # Opportunity row yet.
    current_owner: PersonTimelineCurrentOwnerOut | None = None
    # IANA timezone of the company (``tenant.timezone``); the UI renders
    # every timestamp in this zone so "when" is unambiguous.
    timezone: str = "America/Los_Angeles"


# Per-``source_kind`` curation spec: ``(title_key, [(payload_key, label), …])``.
# Keys are the verbatim provider field names (Salesforce = PascalCase,
# CareStack = camel/lowercase). Absent or empty values are dropped at
# render time. A ``source_kind`` not listed here falls back to a generic
# scalar render of the payload (so a new provider object still shows
# "what happened" without a code change — full-fidelity friendly).
_TIMELINE_DETAIL_SPEC: dict[str, tuple[str | None, tuple[tuple[str, str], ...]]] = {
    "salesforce_task": (
        "Subject",
        (
            ("Type", "Type"),
            ("Status", "Status"),
            ("Priority", "Priority"),
            ("ActivityDate", "Activity date"),
            ("CallType", "Call type"),
            ("CallDisposition", "Disposition"),
            ("CallDurationInSeconds", "Call duration (s)"),
            ("Description", "Description"),
            ("CreatedDate", "Created"),
        ),
    ),
    "salesforce_lead": (
        None,
        (
            ("Status", "Status"),
            ("Company", "Company"),
            ("LeadSource", "Lead source"),
            ("Rating", "Rating"),
            ("Industry", "Industry"),
            ("Description", "Description"),
            ("CreatedDate", "Created"),
        ),
    ),
    "carestack_appointment": (
        "notes",
        (
            ("status", "Status"),
            ("startDateTime", "Start"),
            ("duration", "Duration (min)"),
            ("providerIds", "Provider id"),
            ("operatoryId", "Operatory"),
            ("locationId", "Location"),
            ("createdOn", "Created"),
        ),
    ),
    "carestack_treatment_procedure": (
        None,
        (
            ("procedureCodeId", "Procedure code id"),
            ("statusId", "Status id"),
            ("tooth", "Tooth"),
            ("proposedDate", "Proposed"),
            ("dateOfService", "Date of service"),
            ("patientEstimate", "Patient estimate"),
            ("insuranceEstimate", "Insurance estimate"),
        ),
    ),
}

# Generic-fallback ordering hint: show these readable keys first when a
# ``source_kind`` has no explicit spec. Anything else readable follows.
_GENERIC_DETAIL_PREFERRED = (
    "Subject",
    "Name",
    "Type",
    "Status",
    "status",
    "Description",
    "description",
    "notes",
)
# Noise keys never worth showing in a curated card.
_GENERIC_DETAIL_DENY = frozenset({"attributes"})

# Per-``source_kind`` field that carries the record's status, used for the
# node status badge. ``salesforce_task`` additionally drives the
# done/not-done flag (the operator's "is this task executed?" question).
_STATUS_KEY_BY_KIND = {
    "salesforce_task": "Status",
    "salesforce_lead": "Status",
    "carestack_appointment": "status",
}
_TASK_COMPLETE_KINDS = frozenset({"salesforce_task"})

# ISO-8601-ish date/datetime, with optional time and optional offset
# (Salesforce sends "+0000" without a colon; CareStack sends naive local).
_ISO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?(Z|[+-]\d{2}:?\d{2})?$"
)


def _format_company_datetime(text: str, tz: ZoneInfo) -> str | None:
    """Render an ISO date/datetime in the company timezone, else ``None``.

    Rules so "when" is unambiguous to the operator:
      * offset-aware (Salesforce UTC) → convert to the company zone;
      * naive (CareStack local) → assume it is already company-local;
      * date-only → no time/zone, just a readable date.
    Returns ``None`` when ``text`` is not an ISO timestamp (caller keeps
    the original string).
    """
    if not _ISO_RE.match(text):
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    # Date-only: no time component was present.
    if "T" not in text and " " not in text:
        return f"{parsed:%b} {parsed.day}, {parsed.year}"
    local = parsed.astimezone(tz) if parsed.tzinfo else parsed.replace(tzinfo=tz)
    return f"{local:%b} {local.day}, {local.year}, {local:%-I:%M %p %Z}"


def _format_detail_value(value: object, tz: ZoneInfo) -> str | None:
    """Render a payload scalar for display, or ``None`` to drop it.

    Drops ``None``, empty strings, empty lists, and nested
    dicts/objects (curation surfaces scalars; nested structures are out
    of scope for the card). Booleans render as Yes/No; lists of scalars
    join with ", "; ISO timestamps render in the company timezone.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return _format_company_datetime(text, tz) or text
    if isinstance(value, list):
        parts = [
            rendered
            for item in value
            if (rendered := _format_detail_value(item, tz)) is not None
        ]
        return ", ".join(parts) or None
    # dicts / other → not a card field
    return None


def _curate_timeline_node_detail(
    source_kind: str | None,
    payload: dict[str, object],
    tz: ZoneInfo,
) -> TimelineNodeDetail:
    """Project a raw provider payload into a curated card.

    Pure function (no I/O) so it is unit-testable without a DB. Uses the
    per-``source_kind`` spec when known; otherwise renders readable
    top-level scalars generically. Timestamps are rendered in ``tz``.
    """
    # Status badge + done/not-done flag.
    status_key = _STATUS_KEY_BY_KIND.get(source_kind or "")
    status = (
        _format_detail_value(payload.get(status_key), tz)
        if status_key is not None
        else None
    )
    is_complete: bool | None = None
    if source_kind in _TASK_COMPLETE_KINDS:
        is_complete = status == "Completed"

    spec = _TIMELINE_DETAIL_SPEC.get(source_kind or "")
    if spec is not None:
        title_key, field_spec = spec
        title = (
            _format_detail_value(payload.get(title_key), tz)
            if title_key is not None
            else None
        )
        fields: list[TimelineNodeDetailField] = []
        for payload_key, label in field_spec:
            rendered = _format_detail_value(payload.get(payload_key), tz)
            if rendered is not None:
                fields.append(TimelineNodeDetailField(label=label, value=rendered))
        return TimelineNodeDetail(
            title=title, status=status, is_complete=is_complete, fields=fields
        )

    # Generic fallback — readable scalars, preferred keys first.
    ordered_keys = [k for k in _GENERIC_DETAIL_PREFERRED if k in payload]
    ordered_keys += [
        k
        for k in payload
        if k not in _GENERIC_DETAIL_DENY and k not in ordered_keys
    ]
    generic: list[TimelineNodeDetailField] = []
    for key in ordered_keys:
        if key in _GENERIC_DETAIL_DENY:
            continue
        rendered = _format_detail_value(payload.get(key), tz)
        if rendered is not None:
            generic.append(TimelineNodeDetailField(label=key, value=rendered))
    return TimelineNodeDetail(
        title=None, status=status, is_complete=is_complete, fields=generic
    )


def _resolve_company_tz(tz_name: str) -> ZoneInfo:
    """Tenant IANA tz → ``ZoneInfo``, falling back to Pacific on a bad name."""
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("America/Los_Angeles")


@router.get("", response_model=PersonListOut)
async def list_persons(
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    ops: Annotated[OpsService, Depends(get_ops_service)],
    phi: Annotated[PhiService, Depends(get_phi_service)],
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = _DEFAULT_LIMIT,
) -> PersonListOut:
    tenant_id = principal.require_tenant()

    persons = await identity.list_recent(tenant_id, limit)
    person_uids = [p.id for p in persons]
    lead_uids = await ops.has_lead_for(tenant_id, person_uids)
    consultation_uids = await phi.person_uids_with_consultation(tenant_id, person_uids)
    sources_map = await identity.source_providers_for(tenant_id, person_uids)

    items = [
        PersonSummaryOut(
            id=p.id,
            display_name=p.display_name
            or " ".join(s for s in (p.given_name, p.family_name) if s)
            or "Unknown",
            email=next((i.value for i in p.identifiers if i.kind == "email"), None),
            phone=next((i.value for i in p.identifiers if i.kind == "phone"), None),
            has_lead=p.id in lead_uids,
            has_consultation=p.id in consultation_uids,
            last_activity_at=p.updated_at,
            source_providers=sources_map.get(p.id, []),
        )
        for p in persons
    ]

    total = await identity.count_for_tenant(tenant_id)

    return PersonListOut(items=items, total=total)


@router.get(
    "/{person_uid}/operational-timeline",
    response_model=PersonOperationalTimelineOut,
)
async def get_person_operational_timeline(
    person_uid: UUID,
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    interaction: Annotated[InteractionService, Depends(get_interaction_service)],
    ops: Annotated[OpsService, Depends(get_ops_service)],
    actor: Annotated[ActorService, Depends(get_actor_service)],
    ingest: Annotated[IngestService, Depends(get_ingest_service)],
    tenant: Annotated[TenantService, Depends(get_tenant_service)],
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = 200,
) -> PersonOperationalTimelineOut:
    """Per-person operational timeline — funnel chain with responsibles.

    ENG-418: the items carry the operational + clinical actors per entry
    (resolved to ``actor.actor`` display names here) and the envelope
    carries the current-owner header per the Lead-vs-Opportunity hand-off
    rule.

    Each node also inlines its curated ``detail`` card — the verbatim
    ``ingest.raw_event`` projected into human-readable fields with
    timestamps in the company timezone — so the whole chain is visible at
    once with no extra round-trips (development-phase data visibility
    posture, root ``CLAUDE.md``). The no-PII ``summary`` storage rule is
    untouched; ``detail`` is a read-time projection only.
    """
    tenant_id = principal.require_tenant()
    items_raw = await interaction.list_operational_timeline(
        tenant_id,
        person_uid,
        limit=limit,
    )
    total = await interaction.count_for_person(tenant_id, person_uid)

    tenant_row = await tenant.get_tenant(tenant_id)
    company_tz = _resolve_company_tz(tenant_row.timezone)

    # Resolve every referenced actor in ONE batch keyed by id so the
    # composition stays O(N) regardless of timeline length.
    actor_ids: set[UUID] = {
        ref.actor_id for entry in items_raw for ref in entry.responsibles
    }
    actor_by_id = await _resolve_actors_by_id(tenant_id, actor, actor_ids)

    items: list[PersonTimelineEntryOut] = []
    for entry in items_raw:
        operational: list[PersonTimelineResponsibleOut] = []
        clinical: list[PersonTimelineResponsibleOut] = []
        for ref in entry.responsibles:
            actor_row = actor_by_id.get(ref.actor_id)
            if actor_row is None:
                continue
            row = PersonTimelineResponsibleOut(
                actor_id=ref.actor_id,
                role=ref.role,
                actor_type=actor_row.actor_type,
                name=actor_row.name,
            )
            if ref.role == "clinical":
                clinical.append(row)
            else:
                operational.append(row)

        projection_dict: dict[str, object] | None
        if entry.projection is None:
            projection_dict = None
        else:
            projection_dict = entry.projection.model_dump()

        detail = await _build_node_detail(
            tenant_id, ingest, entry.source_event_id, entry.source_kind, company_tz
        )

        items.append(
            PersonTimelineEntryOut(
                kind=entry.kind,
                occurred_at=entry.occurred_at,
                source_provider=entry.source_provider,
                source_kind=entry.source_kind,
                source_external_id=entry.source_external_id,
                source_event_id=entry.source_event_id,
                detail=detail,
                data_class=entry.data_class,
                review_status=entry.review_status,
                summary=entry.summary,
                projection=projection_dict,
                operational_responsibles=operational,
                clinical_responsibles=clinical,
            )
        )

    current_owner_dto = await _resolve_current_owner(tenant_id, ops, actor, person_uid)

    return PersonOperationalTimelineOut(
        items=items,
        total=total,
        current_owner=current_owner_dto,
        timezone=tenant_row.timezone,
    )


async def _build_node_detail(
    tenant_id: TenantId,
    ingest: IngestService,
    source_event_id: UUID | None,
    source_kind: str | None,
    company_tz: ZoneInfo,
) -> TimelineNodeDetail | None:
    """Fetch + curate the raw-event card for one node, or ``None``.

    ``None`` when the node has no backing raw row (derived events) or the
    raw row is missing — the chain still renders, just without a card.
    """
    if source_event_id is None:
        return None
    raw = await ingest.get_raw_event(tenant_id, source_event_id)
    if raw is None:
        return None
    return _curate_timeline_node_detail(source_kind, raw.payload, company_tz)


async def _resolve_actors_by_id(
    tenant_id: TenantId,
    actor: ActorService,
    actor_ids: set[UUID],
):
    """Batch-resolve actor display rows by id.

    Returns a dict keyed by ``actor.id``. Missing rows are dropped so
    the caller can skip the responsibility entry rather than render a
    "Unknown actor" stub — the responsibility row should NEVER reference
    a deleted actor (FK is RESTRICT on ``event_responsibility``).
    """
    out: dict[UUID, object] = {}
    for actor_id in actor_ids:
        try:
            row = await actor.get_actor(tenant_id, actor_id)
        except Exception as exc:
            log.warning(
                "person_actor_resolution_failed",
                tenant_id=str(tenant_id),
                actor_id=str(actor_id),
                error=str(exc),
            )
            continue
        out[actor_id] = row
    return out


async def _resolve_current_owner(
    tenant_id: TenantId,
    ops: OpsService,
    actor: ActorService,
    person_uid: UUID,
) -> PersonTimelineCurrentOwnerOut | None:
    """Compose the current-owner header.

    Resolves the staged owner via ``OpsService.get_current_funnel_owner``
    then attaches a display row via ``ActorService.resolve_actor_from_source``.
    Returns ``None`` only when neither side has a Lead/Opportunity row.
    """
    current = await ops.get_current_funnel_owner(tenant_id, person_uid)
    if current is None:
        return None
    try:
        actor_row = await actor.resolve_actor_from_source(
            tenant_id,
            source_provider=current.source_provider,
            source_instance="salesforce-main",
            external_id=current.external_id,
            name_hint=current.owner_name,
        )
        return PersonTimelineCurrentOwnerOut(
            stage=current.stage,
            actor_id=actor_row.id,
            actor_type=actor_row.actor_type,
            name=actor_row.name,
            source_provider=current.source_provider,
            external_id=current.external_id,
            opportunity_id=current.opportunity_id,
        )
    except Exception:
        # Resolver fails ungracefully shouldn't take the whole route down;
        # emit the raw SF id so the operator still sees who SF thinks
        # owns this person. Logged at WARNING by the resolver itself.
        return PersonTimelineCurrentOwnerOut(
            stage=current.stage,
            actor_id=None,
            actor_type=None,
            name=current.owner_name,
            source_provider=current.source_provider,
            external_id=current.external_id,
            opportunity_id=current.opportunity_id,
        )


@router.get("/{person_uid}", response_model=PersonDetailOut)
async def get_person_detail(
    person_uid: UUID,
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    ops: Annotated[OpsService, Depends(get_ops_service)],
    phi: Annotated[PhiService, Depends(get_phi_service)],
    ingest: Annotated[IngestService, Depends(get_ingest_service)],
) -> PersonDetailOut:
    tenant_id = principal.require_tenant()
    person = await identity.get_person(tenant_id, PersonUID(person_uid))

    lead_uids = await ops.has_lead_for(tenant_id, [person.id])
    consultation_uids = await phi.person_uids_with_consultation(tenant_id, [person.id])
    sources_map = await identity.source_providers_for(tenant_id, [person.id])
    source_links_map = await identity.source_links_for_persons(tenant_id, [person.id])
    lead = await ops.get_lead_for_person(tenant_id, person.id)
    # ENG-306: extract CareStack patient ids from the person's source links
    # and resolve the per-person financial summary in the same round-trip.
    carestack_patient_ids = [
        link.source_id
        for link in source_links_map.get(person.id, [])
        if link.source_system == "carestack"
        and link.source_kind == "patient"
        and link.source_id is not None
    ]
    financial_summary = await ingest.person_payment_financial_summary(
        tenant_id, carestack_patient_ids
    )
    # ENG-308: same patient-id list feeds the origin-context aggregator.
    # One additional round-trip per request; no N+1.
    carestack_origin = await ingest.person_carestack_origin_context(
        tenant_id, carestack_patient_ids
    )
    # ENG-310: household members — siblings sharing a phone/email.
    # Single round-trip; resolver short-circuits when the person has no
    # CareStack patient links.
    household_members = await ingest.person_household_members(
        tenant_id, person.id
    )

    summary = PersonSummaryOut(
        id=person.id,
        display_name=person.display_name
        or " ".join(s for s in (person.given_name, person.family_name) if s)
        or "Unknown",
        email=next((i.value for i in person.identifiers if i.kind == "email"), None),
        phone=next((i.value for i in person.identifiers if i.kind == "phone"), None),
        has_lead=person.id in lead_uids,
        has_consultation=person.id in consultation_uids,
        last_activity_at=person.updated_at,
        source_providers=sources_map.get(person.id, []),
    )

    source_links = [
        PersonSourceLinkOut(
            provider=link.source_system,
            external_id=link.source_id,
            entity=link.source_kind,
            confidence=_SOURCE_LINK_CONFIRMED_CONFIDENCE,
            provider_url=None,
            first_seen_at=link.first_seen_at,
        )
        for link in source_links_map.get(person.id, [])
        if link.source_id is not None
    ]

    lead_header = (
        PersonLeadHeaderOut(
            status=lead.status,
            source=lead.source,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
            salesforce_status=_string_or_none(
                lead.extra.get("lead_status") or lead.extra.get("Status")
            ),
            salesforce_created_at=_datetime_or_none(
                lead.extra.get("sf_created_at") or lead.extra.get("CreatedDate")
            ),
            company=_string_or_none(lead.extra.get("company")),
            campaign=_first_string(
                lead.extra,
                "campaign",
                "campaign_name",
                "campaign_id",
                "Campaign",
                "CampaignName",
                "CampaignId",
                "Campaign__c",
            ),
            owner=_first_string(
                lead.extra,
                "owner",
                "owner_name",
                "owner_id",
                "Owner",
                "OwnerName",
                "OwnerId",
            ),
            treatment_coordinator=_first_string(
                lead.extra,
                "treatment_coordinator",
                "treatment_coordinator_name",
                "tc",
                "tc_name",
                "TC",
                "TC__c",
            ),
            is_reactivation=bool(lead.extra.get("is_reactivation", False)),
        )
        if lead is not None
        else None
    )

    return PersonDetailOut(
        summary=summary,
        source_links=source_links,
        lead=lead_header,
        consultations=[],
        timeline=[],
        financial_summary=financial_summary,
        carestack_origin=carestack_origin,
        household_members=household_members,
    )


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_string(payload: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = _string_or_none(payload.get(key))
        if value is not None:
            return value
    return None


def _datetime_or_none(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = _string_or_none(value)
    if text is None:
        return None
    candidate = text.replace("Z", "+00:00")
    if len(candidate) >= 5 and candidate[-5] in ("+", "-") and candidate[-3] != ":":
        candidate = candidate[:-2] + ":" + candidate[-2:]
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None
