"""Stage-aware funnel-responsibility resolver (ENG-416 + ENG-417).

Given an event the ingest layer is about to emit, returns the list of
``(actor_id, role)`` assignments that should land in
``interaction.event_responsibility``.

## Wiring

`packages/ingest` is NOT allowed to import `packages/actor` directly
(see `packages/CLAUDE.md` cross-package matrix). The resolver therefore
declares :class:`ActorResolverProtocol` and accepts an implementation
by constructor injection — the application boundary (apps/api /
apps/worker job wiring) constructs the real `ActorService` and passes
it in. This mirrors how `SfClientProtocol` is wired today.

## Stage rules (clinic-managers-confirmed ownership model)

- Pre-consult event kinds → operational owner = SF Lead.OwnerId actor.
  Per-touch override: when the ingest caller passes
  ``explicit_owner=ProviderOwnerHint(...)`` (e.g. a SF
  ``Task.OwnerId`` for a Sofia AI vs agent call), THAT actor wins for
  the operational role on that single event — preserves the per-touch
  ownership distinction.
- Consult-onward event kinds → operational owner = covering SF
  Opportunity.OwnerId actor (the Treatment Coordinator). Fallback to
  Lead.OwnerId when no covering Opportunity exists yet.
- Clinical events additionally attach the doctor actor under
  role=clinical, resolved from the CareStack provider id passed by the
  caller. Salesforce ingest never produces clinical actors.

Salesforce is the sole source of operational ownership; CareStack
NEVER contributes a TC actor. The resolver enforces this by only
consulting the SF-derived owner ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from packages.core.types import TenantId
from packages.interaction.schemas import ResponsibilityAssignmentIn, ResponsibilityRole
from packages.ops.service import OpsService

# Event kinds that should attribute to the COVERING OPPORTUNITY OWNER
# (Treatment Coordinator). Anything not in this set attributes to the
# Lead owner instead. See ENG-413 ownership model.
_CONSULT_ONWARD_KINDS = frozenset(
    {
        "consultation_scheduled",
        "consultation_created",
        "consultation_rescheduled",
        "consultation_cancelled",
        "consultation_completed",
        "consultation_no_show",
        "opportunity_created",
        "opportunity_won",
        "opportunity_lost",
        "treatment_proposed",
        "treatment_completed",
        "invoice_created",
        "payment_recorded",
        "payment_applied",
        "payment_refunded",
        "payment_reversed",
    }
)

# Event kinds that also receive a CLINICAL actor (doctor) when the
# caller supplies a provider hint. Per ENG-417 the consult events are
# the primary surface today; treatment events also have a clinical
# actor when CareStack carries the provider on them.
_CLINICAL_EVENT_KINDS = frozenset(
    {
        "consultation_scheduled",
        "consultation_created",
        "consultation_rescheduled",
        "consultation_cancelled",
        "consultation_completed",
        "consultation_no_show",
        "treatment_proposed",
        "treatment_completed",
    }
)


@dataclass(frozen=True, slots=True)
class ProviderOwnerHint:
    """One owner reference resolvable to an ``actor.actor`` via the resolver.

    ``source_provider`` and ``source_instance`` map straight to
    ``ActorService.resolve_actor_from_source`` arguments. ``external_id``
    is the provider-side party id (SF UserId / SF GroupId / CareStack
    provider id / ``sofia_ai``). ``name_hint`` (optional) is used when
    a new actor row must be created on first observation.
    """

    source_provider: str
    source_instance: str
    external_id: str
    name_hint: str | None = None
    role_hint: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedResponsibility:
    """Outcome of a single resolver call.

    ``assignments`` is the list of ``(actor_id, role)`` rows the caller
    should pass to ``interaction.create_event(..., responsibilities=...)``.
    ``covering_opportunity_id`` is set when the resolver looked up a
    covering Opportunity (ENG-417); the consultation-emitting caller
    persists it onto ``ops.consultation.covering_opportunity_id`` via
    ``OpsService.attach_consultation_to_opportunity``.
    """

    assignments: list[ResponsibilityAssignmentIn]
    covering_opportunity_id: UUID | None = None


class ActorResolverProtocol(Protocol):
    """Minimum ``ActorService`` surface used by the resolver.

    Concretely satisfied by ``packages.actor.service.ActorService``;
    declared here so the import matrix stays clean (the concrete class
    is injected by the application layer).
    """

    async def resolve_actor_from_source(
        self,
        tenant_id: TenantId,
        *,
        source_provider: str,
        source_instance: str,
        external_id: str,
        name_hint: str | None = None,
        role_hint: str | None = None,
    ) -> object: ...


class FunnelResponsibilityResolver:
    """Stage-aware resolver — owner attribution per ENG-413 / ENG-416 / ENG-417."""

    def __init__(
        self,
        ops: OpsService,
        actor_resolver: ActorResolverProtocol,
    ) -> None:
        self._ops = ops
        self._actor_resolver = actor_resolver

    async def resolve(
        self,
        tenant_id: TenantId,
        *,
        event_kind: str,
        person_uid: UUID,
        occurred_at: datetime,
        explicit_owner: ProviderOwnerHint | None = None,
        clinical_provider: ProviderOwnerHint | None = None,
    ) -> ResolvedResponsibility:
        """Return responsibility assignments for one about-to-be-emitted event.

        Arguments:
          tenant_id: scoping tenant for the event.
          event_kind: ``interaction.event.kind`` value being emitted.
          person_uid: the canonical person the event is about.
          occurred_at: the timestamp the event is dated against — used
            as the moment to pick the covering Opportunity for consult-
            onward events.
          explicit_owner: caller-supplied operational owner override.
            When provided this WINS over the staged owner (Lead /
            covering Opportunity) — used for per-touch attribution like
            a SF Task with its own OwnerId.
          clinical_provider: caller-supplied clinical provider hint
            (CareStack provider id). Attached as ``role='clinical'`` for
            event kinds in :data:`_CLINICAL_EVENT_KINDS`; ignored
            otherwise. Salesforce ingest must NEVER pass this.
        """
        assignments: list[ResponsibilityAssignmentIn] = []
        covering_opportunity_id: UUID | None = None

        operational_hint = explicit_owner
        if operational_hint is None:
            operational_hint, covering_opportunity_id = await self._infer_operational(
                tenant_id, event_kind, person_uid, occurred_at
            )

        if operational_hint is not None:
            actor = await self._actor_resolver.resolve_actor_from_source(
                tenant_id,
                source_provider=operational_hint.source_provider,
                source_instance=operational_hint.source_instance,
                external_id=operational_hint.external_id,
                name_hint=operational_hint.name_hint,
                role_hint=operational_hint.role_hint,
            )
            actor_id = _actor_id(actor)
            if actor_id is not None:
                assignments.append(
                    ResponsibilityAssignmentIn(
                        actor_id=actor_id,
                        role=_OPERATIONAL,
                    )
                )

        if clinical_provider is not None and event_kind in _CLINICAL_EVENT_KINDS:
            actor = await self._actor_resolver.resolve_actor_from_source(
                tenant_id,
                source_provider=clinical_provider.source_provider,
                source_instance=clinical_provider.source_instance,
                external_id=clinical_provider.external_id,
                name_hint=clinical_provider.name_hint,
                role_hint=clinical_provider.role_hint,
            )
            actor_id = _actor_id(actor)
            if actor_id is not None:
                assignments.append(
                    ResponsibilityAssignmentIn(
                        actor_id=actor_id,
                        role=_CLINICAL,
                    )
                )

        return ResolvedResponsibility(
            assignments=assignments,
            covering_opportunity_id=covering_opportunity_id,
        )

    async def _infer_operational(
        self,
        tenant_id: TenantId,
        event_kind: str,
        person_uid: UUID,
        occurred_at: datetime,
    ) -> tuple[ProviderOwnerHint | None, UUID | None]:
        """Look up the staged operational owner from SF projection state.

        Returns ``(hint, covering_opportunity_id)`` so the consultation
        emitter can persist the link onto ``ops.consultation`` in the
        same UoW. ``covering_opportunity_id`` is ``None`` for pre-
        consult events and for consults that pre-date their first
        Opportunity (walk-ins).
        """
        # Pre-consult kinds: Lead owner is the only source.
        if event_kind not in _CONSULT_ONWARD_KINDS:
            owner_id = await self._ops.get_lead_owner_id(tenant_id, person_uid)
            if owner_id is None:
                return None, None
            return (
                ProviderOwnerHint(
                    source_provider="salesforce",
                    source_instance=_SF_INSTANCE,
                    external_id=owner_id,
                ),
                None,
            )

        # Consult-onward: prefer covering Opportunity.OwnerId; fall back
        # to Lead.OwnerId for walk-ins / pre-Opportunity consults.
        opportunity = await self._ops.find_covering_opportunity(
            tenant_id, person_uid, occurred_at
        )
        if opportunity is not None:
            owner_id = await self._ops.get_opportunity_owner_id(opportunity)
            if owner_id is not None:
                return (
                    ProviderOwnerHint(
                        source_provider="salesforce",
                        source_instance=_SF_INSTANCE,
                        external_id=owner_id,
                    ),
                    opportunity.id,
                )
            # Opportunity exists but has no owner_id — log via caller; we
            # still surface the covering id so the consult can link to it
            # for downstream queries, and we fall through to the Lead
            # fallback for the actor.
            covering_id = opportunity.id
        else:
            covering_id = None

        owner_id = await self._ops.get_lead_owner_id(tenant_id, person_uid)
        if owner_id is None:
            return None, covering_id
        return (
            ProviderOwnerHint(
                source_provider="salesforce",
                source_instance=_SF_INSTANCE,
                external_id=owner_id,
            ),
            covering_id,
        )


# --- internal -------------------------------------------------------------

_OPERATIONAL: ResponsibilityRole = "operational"
_CLINICAL: ResponsibilityRole = "clinical"

# Sole SF instance slug used across the codebase (see
# ``sf_opportunity_service._SF_OPPORTUNITY_SOURCE_INSTANCE`` and
# ``identity.source_link`` callers). When the org runs a sandbox or a
# second prod org the resolver caller will pass an explicit hint
# overriding this; pre-consult inference defaults to the prod slug.
_SF_INSTANCE = "salesforce-main"


def _actor_id(actor: object) -> UUID | None:
    """Defensive ``actor.id`` extraction.

    The ``ActorResolverProtocol`` returns ``object`` so the import
    matrix stays clean. The concrete ``Actor`` ORM row exposes
    ``.id: UUID``; if a future implementation returns a DTO instead,
    this helper isolates the assumption.
    """
    actor_id = getattr(actor, "id", None)
    if isinstance(actor_id, UUID):
        return actor_id
    return None
