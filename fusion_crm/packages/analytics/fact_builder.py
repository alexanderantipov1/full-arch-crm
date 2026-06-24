"""Fact builder — project ``analytics.fact_patient_journey`` (ENG-506).

A read-only composition service that, like :class:`FullFunnelService`, owns NO
SQL: every canonical read goes through the owning domain's service
(``OpsService`` / ``IdentityService`` / ``InteractionService`` /
``AttributionService``), honouring the ``packages/CLAUDE.md`` import matrix. It
writes ONLY to its own schema, ``analytics.fact_patient_journey``, via
:class:`FactPatientJourneyRepository`.

One row per ``person_uid`` over the union of SF-lead persons and CareStack-direct
patients. The projection is idempotent and rebuildable: re-running produces
identical rows; ``field_provenance`` is merged (manual > auto > unresolved), so
a rebuild never clobbers a manually enriched field.

Field mapping (ENG-506, verified):

- ``lead_date`` — person-anchored lead created-at for SF-lead persons
  (``extra.sf_created_at`` ?? ``created_at``); CareStack-direct persons use the
  earliest real activity (``MIN(consult.scheduled_at)`` else
  ``MIN(event.occurred_at)``), NOT the bulk-import date (ENG-481).
- ``source`` — ``ops.lead.source`` (NULL for CareStack-direct: no lead).
- ``consult_scheduled_date`` / ``show_date`` / ``location_id`` —
  ``ops.consultation`` (earliest scheduled / earliest completed / earliest
  consult's location).
- ``treatment_presented_date`` — ``interaction.event`` ``treatment_proposed``.
- ``first_payment_date`` — ``interaction.event`` ``payment_recorded`` /
  ``invoice_created``.
- ``revenue_amount`` / ``collected_amount`` — Net-Collected (ENG-283;
  ``payment_applied`` excluded).
- ``campaign_id`` / ``campaign_name`` / ``vendor_id`` — resolved
  ``attribution.lead_attribution`` (NULL when unresolved).

B1 people dimensions (ENG-509 / ENG-510), resolved to ``actor.actor`` ids with
provenance ``method='auto'`` when a signal exists, else NULL + ``unresolved``:

- ``caller_id`` — SF Lead Owner (``ops.lead.extra.owner_id``) resolved via
  ``ActorService`` (kind ``salesforce_user_id``).
- ``coordinator_id`` — SF Opportunity Owner (``ops.opportunity.extra.owner_id``)
  resolved the same way (the Treatment Coordinator).
- ``doctor_id`` — the clinical actor on the person's earliest clinical event
  (``interaction.event_responsibility`` role=``clinical``; the CareStack
  appointment-provider actor resolved during ingest, ENG-417).

``marketing_cost_allocated`` (ENG-512) is resolved ``method='auto'`` for every
person with a ``lead_date``: the cost-per-lead allocator
(:mod:`packages.analytics.cost_allocation`) splits ad spend (``marketing.ad`` /
``marketing.ad_metric_daily_ad`` / ``marketing.ad_metric_daily``) across the
leads it produced, with the fallback ad → campaign → ``$0``. It is wired only
when a :class:`MarketingService` is provided (the worker boundary); without one
the field stays ``unresolved`` (DB-free unit tests of the other dimensions).
Persons with no ``lead_date`` (cannot time-match spend) also stay ``unresolved``.

B1.3 surgery-stage dimensions (ENG-511), resolved from ``interaction.event``
milestones with provenance ``method='auto'`` when a signal exists, else NULL +
``unresolved``:

- ``treatment_accepted_date`` — earliest ``treatment_accepted`` event
  (CareStack TreatmentPlan ``StatusId=3``; first observed acceptance).
- ``surgery_scheduled_date`` — earliest ``surgery_scheduled`` event
  (implant-surgery treatment procedure ``statusId=2``).
- ``surgery_completed_date`` — earliest ``surgery_completed`` event
  (implant-surgery treatment procedure ``statusId=8``).

B1.5 implant ``case_type`` dimension (ENG-539), CDT-derived with provenance
``method='auto'`` when determinative, else NULL + ``unresolved``:

- ``case_type`` — coarse implant-case label resolved from the CDT codes of the
  person's treatment procedures. ``ingest`` supplies per-patient procedure-code
  ids (raw layer, read-only via ``IngestService``), ``catalog`` resolves them to
  CDT (read-only via ``CatalogService.resolve_procedure_codes``), and the
  in-house resolver (``packages/analytics/case_type.py``) applies a documented
  precedence over each person's CDT set. NULL = non-implant OR non-determinative
  (*unclassified*, surfaced via the ``case_type.needs_review`` log).

Still unresolved (NULL, ``method='unresolved'``): ``first_contact_date``.

Any field may be set by operator enrichment (ENG-513, ``method='manual'``); a
rebuild preserves both the manual value and provenance (manual > auto >
unresolved).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from packages.actor.service import ActorService
from packages.attribution.service import AttributionService
from packages.catalog.service import CatalogService
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.identity.service import IdentityService
from packages.ingest.service import IngestService
from packages.interaction.service import InteractionService
from packages.marketing.service import MarketingService
from packages.ops.service import OpsService

from .case_type import CaseTypeResolution, resolve_case_type
from .cost_allocation import AllocationSummary, AllocLead, allocate
from .fact_repository import ExistingFactRow, FactPatientJourneyRepository
from .provenance import FieldProvenance, auto, merge_provenance, unresolved

logger = get_logger(__name__)

# Sole SF instance slug used across the codebase (mirrors
# ``ingest.responsibility_resolver._SF_INSTANCE`` and the source_link callers).
_SF_INSTANCE = "salesforce-main"

# Sole CareStack instance slug (mirrors the treatment-procedure ingest caller).
_CARESTACK_INSTANCE = "carestack-main"

# Slugifier matching ``attribution.waterfall._slugify`` so a slug of a marketing
# ad/campaign NAME matches the attribution node slug derived from the lead's
# UTM text (the utm=name convention). Pure-digit Meta ids slugify to themselves,
# covering the utm=id convention via the raw external id too.
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("_", value.strip().lower()).strip("_")
    return slug[:160] or "unknown"


def _build_slug_index(
    pairs: Iterable[tuple[str | None, str | None]],
) -> dict[str, str]:
    """Map every candidate slug of a marketing ad/campaign → its external id.

    Registers, per row, the raw ``external_id``, its slug, and the slug of its
    ``name`` — so an attribution node slug derived from either the lead's UTM id
    (utm=id) or UTM text/ad name (utm=name) resolves to the spend key.

    A slug that resolves to **more than one distinct external id** is a collision
    (e.g. two ads whose names slugify identically): it is **ambiguous** and gets
    DROPPED from the index, so a lead carrying that slug resolves to ``None`` →
    UNMATCHED (coverage reduction / ``spend_without_leads``) rather than being
    silently assigned to whichever row happened to win. Mismatches reduce
    coverage, never mis-allocate.
    """
    index: dict[str, str] = {}
    ambiguous: set[str] = set()
    for external_id, name in pairs:
        if not external_id:
            continue
        candidates = [external_id, _slugify(external_id)]
        if name:
            candidates.append(_slugify(name))
        for slug in candidates:
            existing = index.get(slug)
            if existing is not None and existing != external_id:
                ambiguous.add(slug)
            else:
                index[slug] = external_id
    for slug in ambiguous:
        index.pop(slug, None)
    return index

# Fields that still have NO canonical signal — ship NULL with
# method='unresolved' until a later B1.* ticket fills them. caller_id /
# coordinator_id (ENG-509) and doctor_id (ENG-510) are resolved below when a
# signal exists and only fall back to unresolved otherwise.
# ``marketing_cost_allocated`` (ENG-512) and the surgery-stage dates (ENG-511)
# are NOT here — they are auto-resolved below when a signal exists (the
# cost-per-lead allocator / interaction milestones) and only fall back to
# ``unresolved`` per-person otherwise.
_UNRESOLVED_FIELDS: tuple[str, ...] = (
    "first_contact_date",
)

# Fact columns whose value AND provenance the builder must preserve when the
# stored row marks them ``method='manual'`` (operator enrichment, ENG-513).
# A rebuild recomputes the auto value but must NOT overwrite a manual one.
_MANUAL_PRESERVE_FIELDS: frozenset[str] = frozenset(
    {
        "campaign_id",
        "campaign_name",
        "source",
        "vendor_id",
        "case_type",
        "caller_id",
        "coordinator_id",
        "doctor_id",
        "location_id",
        "first_contact_date",
        "consult_scheduled_date",
        "show_date",
        "treatment_presented_date",
        "treatment_accepted_date",
        "surgery_scheduled_date",
        "surgery_completed_date",
        "first_payment_date",
        "revenue_amount",
        "collected_amount",
        "marketing_cost_allocated",
        "lead_date",
    }
)


@dataclass(frozen=True)
class BuildResult:
    """Outcome of a backfill / refresh run.

    ``spend_without_leads`` (ENG-512) surfaces ad/campaign spend that produced no
    attributed leads in the allocated window — visible, never hidden. ``None``
    when no cost allocation ran (no MarketingService wired, or no dated leads).
    """

    persons: int
    rows_written: int
    spend_without_leads: float | None = None


class FactPatientJourneyBuilder:
    """Project ``analytics.fact_patient_journey`` from canonical domains."""

    def __init__(
        self,
        *,
        ops: OpsService,
        identity: IdentityService,
        interaction: InteractionService,
        attribution: AttributionService,
        actor: ActorService,
        ingest: IngestService,
        catalog: CatalogService,
        repo: FactPatientJourneyRepository,
        marketing: MarketingService | None = None,
    ) -> None:
        self._ops = ops
        self._identity = identity
        self._interaction = interaction
        self._attribution = attribution
        self._actor = actor
        # ENG-539 (B1.5): the implant ``case_type`` dimension is derived from the
        # CDT codes of a person's treatment procedures. ``ingest`` supplies the
        # per-patient procedure-code ids (raw layer), ``catalog`` resolves them to
        # CDT — both read-only via their services (no schema/repo access), the
        # analytics read-model doctrine "derive from canonical via services".
        self._ingest = ingest
        self._catalog = catalog
        self._repo = repo
        # Optional so DB-free unit tests of the other dimensions construct the
        # builder without it; the worker boundary always wires it so production
        # rebuilds flip marketing_cost_allocated to ``auto`` (ENG-512).
        self._marketing = marketing

    async def build(
        self,
        tenant_id: TenantId,
        *,
        only_persons: set[UUID] | None = None,
        now: datetime | None = None,
    ) -> BuildResult:
        """Backfill (``only_persons=None``) or incrementally refresh a subset.

        Reads the canonical per-person aggregates once each (full GROUP BY, no
        bound IN), assembles one row per person in the universe, merges
        provenance over any existing row, and upserts. ``only_persons``
        restricts which rows are WRITTEN (incremental refresh of changed
        persons); the canonical reads are still full-table scans (a read-side
        optimisation is a follow-up).
        """
        resolved_now = now or datetime.now(tz=UTC)

        lead_facts = await self._ops.analytics_lead_facts_by_person(tenant_id)
        consult_facts = await self._ops.analytics_consultation_facts_by_person(
            tenant_id
        )
        milestones = await self._interaction.analytics_event_milestones_by_person(
            tenant_id
        )
        surgery_milestones = (
            await self._interaction.analytics_surgery_stage_milestones_by_person(
                tenant_id
            )
        )
        collected = await self._interaction.collected_by_person(tenant_id)
        attribution = await self._attribution.analytics_attribution_by_person(
            tenant_id
        )
        carestack_uids = set(
            await self._identity.full_funnel_carestack_patient_person_uids(tenant_id)
        )
        # CareStack-direct dating inputs (earliest real activity).
        earliest_consult = (
            await self._ops.full_funnel_earliest_consultation_at_by_person(tenant_id)
        )
        earliest_event = await self._interaction.earliest_event_at_by_person(tenant_id)

        # --- B1 people-dimension resolution (ENG-509 / ENG-510) ---
        # caller = SF Lead Owner, coordinator = SF Opportunity Owner (resolved to
        # actors), doctor = CareStack appointment-provider clinical actor.
        caller_by_person, coordinator_by_person = await self._resolve_owner_actors(
            tenant_id
        )
        doctor_by_person = (
            await self._interaction.analytics_clinical_actor_by_person(tenant_id)
        )

        # --- B1.5 implant case_type resolution (ENG-539) ---
        case_type_by_person = await self._resolve_case_type_by_person(tenant_id)

        full_universe: set[UUID] = set()
        full_universe |= lead_facts.keys()
        full_universe |= consult_facts.keys()
        full_universe |= milestones.keys()
        full_universe |= surgery_milestones.keys()
        full_universe |= collected.keys()
        full_universe |= attribution.keys()
        full_universe |= carestack_uids
        full_universe |= caller_by_person.keys()
        full_universe |= coordinator_by_person.keys()
        full_universe |= doctor_by_person.keys()
        full_universe |= case_type_by_person.keys()

        # Lead date for the FULL population (every person, in or out of the
        # incremental write scope). The cost allocator needs this so an ad/day's
        # spend is split across ALL leads attributed to that ad/day — not only
        # the refreshed subset — even when ``only_persons`` narrows the writes
        # (ENG-512 incremental over-allocation fix).
        full_lead_dates: dict[UUID, datetime] = {}
        for person_uid in full_universe:
            lead_date = self._lead_date_for(
                person_uid,
                is_lead=person_uid in lead_facts,
                lead_facts=lead_facts,
                earliest_consult=earliest_consult,
                earliest_event=earliest_event,
            )
            if lead_date is not None:
                full_lead_dates[person_uid] = lead_date

        universe = set(full_universe)
        if only_persons is not None:
            universe &= only_persons

        if not universe:
            logger.info(
                "fact_patient_journey.build.empty",
                tenant_id=str(tenant_id),
                incremental=only_persons is not None,
            )
            return BuildResult(persons=0, rows_written=0)

        existing = await self._repo.existing_for_merge(sorted(universe))

        projected: list[tuple[dict[str, object], dict[str, FieldProvenance]]] = []
        for person_uid in universe:
            row, incoming = self._project_person(
                person_uid,
                is_lead=person_uid in lead_facts,
                lead_facts=lead_facts,
                consult_facts=consult_facts,
                milestones=milestones,
                surgery_milestones=surgery_milestones,
                collected=collected,
                attribution=attribution,
                earliest_consult=earliest_consult,
                earliest_event=earliest_event,
                caller_by_person=caller_by_person,
                coordinator_by_person=coordinator_by_person,
                doctor_by_person=doctor_by_person,
                case_type_by_person=case_type_by_person,
                now=resolved_now,
            )
            projected.append((row, incoming))

        # Cost-per-lead allocation (ENG-512) — a cross-person pass that fills
        # marketing_cost_allocated; needs every row's lead_date first. The full
        # population's lead dates feed the denominators; only in-scope rows are
        # written.
        alloc_summary = await self._apply_cost_allocation(
            tenant_id, projected, full_lead_dates, now=resolved_now
        )

        rows: list[dict[str, object]] = []
        for row, incoming in projected:
            person_uid = row["person_uid"]  # type: ignore[assignment]
            prior = existing.get(person_uid)
            self._preserve_manual_values(row, prior)
            row["field_provenance"] = merge_provenance(
                prior.field_provenance if prior is not None else None, incoming
            )
            rows.append(row)

        written = await self._repo.upsert_many(rows)
        logger.info(
            "fact_patient_journey.build.done",
            tenant_id=str(tenant_id),
            incremental=only_persons is not None,
            persons=len(universe),
            rows_written=written,
        )
        # --- B1.5 review surface (ENG-539) ---
        # Persons with implant procedures but no determinative CDT signal ship
        # case_type=NULL (*unclassified*) and need manual triage. Mirror the
        # ENG-538 catalog drift "needs_review" log: a count + the eligible
        # person_uids (non-PHI ids) so the cohort is never silent. The same set
        # is queryable directly via the per-person resolver aggregate.
        unclassified = sorted(
            str(person_uid)
            for person_uid, resolution in case_type_by_person.items()
            if resolution.has_implant
            and resolution.case_type is None
            and (only_persons is None or person_uid in only_persons)
        )
        if unclassified:
            logger.warning(
                "fact_patient_journey.case_type.needs_review",
                tenant_id=str(tenant_id),
                unclassified_implant_count=len(unclassified),
                person_uids=unclassified,
            )

        return BuildResult(
            persons=len(universe),
            rows_written=written,
            spend_without_leads=(
                alloc_summary.spend_without_leads if alloc_summary is not None else None
            ),
        )

    async def _apply_cost_allocation(
        self,
        tenant_id: TenantId,
        projected: list[tuple[dict[str, object], dict[str, FieldProvenance]]],
        full_lead_dates: Mapping[UUID, datetime],
        *,
        now: datetime,
    ) -> AllocationSummary | None:
        """Fill ``marketing_cost_allocated`` (ENG-512) across the projected rows.

        Bridges each lead's resolved attribution ad/campaign node slug to the
        ``marketing`` spend rows (slug ↔ external id, or slug ↔ slugified name),
        runs the pure :func:`allocate`, and stamps the per-person cost +
        ``auto`` provenance. No-op (returns ``None``) when no MarketingService is
        wired or no in-scope person has a ``lead_date`` to time-match spend
        against. Rows without a ``lead_date`` keep their ``unresolved`` seed.

        ``full_lead_dates`` carries the lead date of EVERY attributed person
        (the full population), not just the in-scope rows in ``projected``. The
        denominators (leads-per-ad/day and per-campaign/day) are computed over
        that full population so an incremental refresh of a subset cannot
        over-allocate an ad/day's spend to the refreshed leads (an ad/day with 2
        leads, refresh of 1 → that 1 still gets ``spend / 2``, not the whole
        spend). Costs are then WRITTEN only for the in-scope ``projected`` rows.
        """
        if self._marketing is None:
            return None

        # Spend window: the days of the IN-SCOPE dated leads (what we refresh).
        # Co-attributed full-population leads share those same days, so this
        # window still captures every lead in each touched (ad/campaign, day).
        in_scope = {row["person_uid"] for row, _incoming in projected}
        in_scope_days = [
            lead_date.date()
            for person_uid, lead_date in full_lead_dates.items()
            if person_uid in in_scope
        ]
        if not in_scope_days:
            return None
        start_date, end_date = min(in_scope_days), max(in_scope_days)

        attr = await self._attribution.analytics_alloc_attribution_by_person(
            tenant_id
        )

        ads = await self._marketing.list_ads(tenant_id)
        campaigns = await self._marketing.list_campaigns(tenant_id)
        ad_slug_to_key = _build_slug_index(
            (a.external_id, a.name) for a in ads
        )
        campaign_slug_to_key = _build_slug_index(
            (c.external_id, c.name) for c in campaigns
        )

        ad_daily = await self._marketing.ad_daily_spend(
            tenant_id, start_date=start_date, end_date=end_date
        )
        campaign_daily = await self._marketing.campaign_daily_spend(
            tenant_id, start_date=start_date, end_date=end_date
        )
        ad_spend = {(r.ad_external_id, r.metric_date): r.spend for r in ad_daily}
        ad_to_campaign = {
            r.ad_external_id: r.campaign_external_id for r in ad_daily
        }
        campaign_spend = {
            (r.campaign_external_id, r.metric_date): r.spend for r in campaign_daily
        }

        # Build the FULL attributed population for the window — every dated lead
        # (in OR out of scope) whose day falls in the loaded spend window — so
        # the per-ad/day and per-campaign/day denominators are complete.
        leads = []
        for person_uid, lead_date in full_lead_dates.items():
            day = lead_date.date()
            if day < start_date or day > end_date:
                continue
            ad_slug, campaign_slug, confidence = attr.get(
                person_uid, (None, None, None)
            )
            leads.append(
                AllocLead(
                    person_uid=person_uid,
                    day=day,
                    ad_key=(
                        ad_slug_to_key.get(ad_slug) if ad_slug is not None else None
                    ),
                    campaign_key=(
                        campaign_slug_to_key.get(campaign_slug)
                        if campaign_slug is not None
                        else None
                    ),
                    confidence=confidence,
                )
            )
        if not leads:
            return None

        result = allocate(
            leads,
            ad_spend=ad_spend,
            campaign_spend=campaign_spend,
            ad_to_campaign=ad_to_campaign,
        )

        by_person = {row["person_uid"]: (row, incoming) for row, incoming in projected}
        for person_uid, cost in result.per_person.items():
            target = by_person.get(person_uid)
            if target is None:
                # Full-population lead outside the write scope: it counted toward
                # the denominator, but its row is not being refreshed this run.
                continue
            row, incoming = target
            # Persist the cent-exact amount verbatim — a second independent round
            # would re-introduce the over-allocation the allocator just removed.
            row["marketing_cost_allocated"] = cost.amount
            incoming["marketing_cost_allocated"] = auto(
                cost.source, confidence=cost.confidence, resolved_at=now
            )

        logger.info(
            "fact_patient_journey.cost_allocation",
            tenant_id=str(tenant_id),
            allocated_total=round(result.summary.allocated_total, 2),
            spend_without_leads=round(result.summary.spend_without_leads, 2),
            ad_covered_leads=result.summary.ad_covered_leads,
            campaign_covered_leads=result.summary.campaign_covered_leads,
            uncovered_leads=result.summary.uncovered_leads,
        )
        return result.summary

    async def _resolve_owner_actors(
        self, tenant_id: TenantId
    ) -> tuple[dict[UUID, UUID], dict[UUID, UUID]]:
        """Resolve caller + coordinator actor ids per person (ENG-509).

        Reads the SF Lead Owner (caller) and Opportunity Owner (coordinator)
        user ids per person from ``ops``, resolves the distinct ids to
        ``actor.actor`` rows ONCE (idempotent create-or-lookup — the
        ``actor_identifier`` of kind ``salesforce_user_id`` is the backfill),
        then maps each person to the resolved actor. Returns
        ``(caller_by_person, coordinator_by_person)``. Owners that do not map
        to an actor are absent (NULL dimension, method=unresolved).
        """
        lead_owner_sf = await self._ops.analytics_lead_owner_by_person(tenant_id)
        opp_owner_sf = await self._ops.analytics_opportunity_owner_by_person(
            tenant_id
        )
        distinct_sf = set(lead_owner_sf.values()) | set(opp_owner_sf.values())
        sf_actor = await self._actor.resolve_actor_ids_from_source(
            tenant_id,
            source_provider="salesforce",
            source_instance=_SF_INSTANCE,
            external_ids=distinct_sf,
        )
        caller_by_person = {
            person_uid: sf_actor[sf_id]
            for person_uid, sf_id in lead_owner_sf.items()
            if sf_id in sf_actor
        }
        coordinator_by_person = {
            person_uid: sf_actor[sf_id]
            for person_uid, sf_id in opp_owner_sf.items()
            if sf_id in sf_actor
        }
        return caller_by_person, coordinator_by_person

    async def _resolve_case_type_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, CaseTypeResolution]:
        """Resolve one implant ``case_type`` per person (ENG-539, B1.5).

        Composition only — no SQL here. Reads the per-patient procedure-code ids
        from ``ingest`` (raw layer), maps ``patientId -> person_uid`` via
        ``identity`` source links, resolves ``procedureCodeId -> CDT`` via
        ``catalog``, then applies the in-house precedence resolver
        (:func:`packages.analytics.case_type.resolve_case_type`) over each
        person's CDT multiset. A person whose CareStack patient id has no source
        link yet, or whose codes don't resolve in the catalog, simply yields no
        entry (case_type stays NULL + ``method='unresolved'``).
        """
        codes_by_patient = (
            await self._ingest.treatment_procedure_code_ids_by_patient(tenant_id)
        )
        if not codes_by_patient:
            return {}

        # patientId -> person_uid via the CareStack patient source links.
        keys = [
            ("carestack", _CARESTACK_INSTANCE, "patient", patient_id)
            for patient_id in codes_by_patient
        ]
        links = await self._identity.source_links_for_external_records(
            tenant_id, keys
        )

        # procedureCodeId -> CDT (reference data) via the catalog resolver.
        all_code_ids = sorted(
            {code for codes in codes_by_patient.values() for code in codes}
        )
        resolved = await self._catalog.resolve_procedure_codes(all_code_ids)

        # Gather each person's implant CDT multiset (one entry per procedure).
        cdts_by_person: dict[UUID, list[str]] = {}
        for patient_id, code_ids in codes_by_patient.items():
            link = links.get(("carestack", _CARESTACK_INSTANCE, "patient", patient_id))
            if link is None:
                continue
            person_uid = link.person_uid
            bucket = cdts_by_person.setdefault(person_uid, [])
            for code_id in code_ids:
                entry = resolved.get(code_id)
                if entry is None:
                    continue
                bucket.append(entry[0])

        return {
            person_uid: resolve_case_type(cdts)
            for person_uid, cdts in cdts_by_person.items()
        }

    @staticmethod
    def _lead_date_for(
        person_uid: UUID,
        *,
        is_lead: bool,
        lead_facts: Mapping[UUID, tuple[datetime, str | None]],
        earliest_consult: Mapping[UUID, datetime],
        earliest_event: Mapping[UUID, datetime],
    ) -> datetime | None:
        """The person's ``lead_date`` — the single source of the dating rule.

        SF-lead persons use the lead created-at; CareStack-direct persons use the
        earliest real activity (never the bulk-import date, ENG-481). Shared by
        :meth:`_project_person` (the written value) and the full-population cost
        allocation pass (the denominator), so the two never drift.
        """
        if is_lead:
            return lead_facts[person_uid][0]
        return earliest_consult.get(person_uid) or earliest_event.get(person_uid)

    @staticmethod
    def _preserve_manual_values(
        row: dict[str, object], prior: ExistingFactRow | None
    ) -> None:
        """Keep operator-set values across a rebuild (ENG-513 precedence).

        For every field the stored row marks ``method='manual'``, overwrite the
        freshly-projected (auto) value with the stored manual value. Provenance
        is preserved separately by :func:`merge_provenance` (manual out-ranks
        auto), so value + provenance stay consistent: manual > auto >
        unresolved.
        """
        if prior is None:
            return
        for field, entry in prior.field_provenance.items():
            if not isinstance(entry, dict) or entry.get("method") != "manual":
                continue
            if field in _MANUAL_PRESERVE_FIELDS:
                row[field] = prior.values.get(field)

    def _project_person(
        self,
        person_uid: UUID,
        *,
        is_lead: bool,
        lead_facts: Mapping[UUID, tuple[datetime, str | None]],
        consult_facts: Mapping[
            UUID, tuple[datetime | None, datetime | None, UUID | None]
        ],
        milestones: Mapping[UUID, tuple[datetime | None, datetime | None]],
        surgery_milestones: Mapping[
            UUID, tuple[datetime | None, datetime | None, datetime | None]
        ],
        collected: Mapping[UUID, float],
        attribution: Mapping[UUID, tuple[UUID | None, str | None, UUID | None]],
        earliest_consult: Mapping[UUID, datetime],
        earliest_event: Mapping[UUID, datetime],
        caller_by_person: Mapping[UUID, UUID],
        coordinator_by_person: Mapping[UUID, UUID],
        doctor_by_person: Mapping[UUID, UUID],
        case_type_by_person: Mapping[UUID, CaseTypeResolution],
        now: datetime,
    ) -> tuple[dict[str, object], dict[str, FieldProvenance]]:
        """Build one fact row + its incoming provenance map."""
        row: dict[str, object] = {"person_uid": person_uid}
        prov: dict[str, FieldProvenance] = {}

        # --- lead_date + source ---
        row["lead_date"] = self._lead_date_for(
            person_uid,
            is_lead=is_lead,
            lead_facts=lead_facts,
            earliest_consult=earliest_consult,
            earliest_event=earliest_event,
        )
        if is_lead:
            row["source"] = lead_facts[person_uid][1]
            prov["lead_date"] = auto("ops.lead.created_at", resolved_at=now)
            prov["source"] = auto("ops.lead.source", resolved_at=now)
        else:
            # CareStack-direct: earliest real activity, never the bulk date.
            row["source"] = None
            prov["lead_date"] = auto(
                "carestack_direct:earliest_activity", resolved_at=now
            )
            prov["source"] = auto("carestack_direct:no_lead", resolved_at=now)

        # --- consultation: scheduled / show / location ---
        consult_scheduled, show, location_id = consult_facts.get(
            person_uid, (None, None, None)
        )
        row["consult_scheduled_date"] = consult_scheduled
        row["show_date"] = show
        row["location_id"] = location_id
        prov["consult_scheduled_date"] = auto(
            "ops.consultation.scheduled_at", resolved_at=now
        )
        prov["show_date"] = auto(
            "ops.consultation.scheduled_at:completed", resolved_at=now
        )
        prov["location_id"] = auto("ops.consultation.location_id", resolved_at=now)

        # --- interaction milestones ---
        treatment_presented, first_payment = milestones.get(person_uid, (None, None))
        row["treatment_presented_date"] = treatment_presented
        row["first_payment_date"] = first_payment
        prov["treatment_presented_date"] = auto(
            "interaction.event:treatment_proposed", resolved_at=now
        )
        prov["first_payment_date"] = auto(
            "interaction.event:payment_recorded|invoice_created", resolved_at=now
        )

        # --- surgery-stage milestones (ENG-511, B1.3) ---
        # treatment_accepted (TreatmentPlan StatusId=3), surgery_scheduled /
        # surgery_completed (implant-surgery procedure statusId 2 / 8). Each is
        # auto-resolved when a milestone event exists, else NULL + unresolved
        # (counted, not dropped). A manual override (ENG-513) wins on rebuild via
        # merge_provenance + _preserve_manual_values.
        treatment_accepted, surgery_scheduled, surgery_completed = (
            surgery_milestones.get(person_uid, (None, None, None))
        )
        if treatment_accepted is not None:
            row["treatment_accepted_date"] = treatment_accepted
            prov["treatment_accepted_date"] = auto(
                "interaction.event:treatment_accepted", resolved_at=now
            )
        else:
            prov["treatment_accepted_date"] = unresolved()

        if surgery_scheduled is not None:
            row["surgery_scheduled_date"] = surgery_scheduled
            prov["surgery_scheduled_date"] = auto(
                "interaction.event:surgery_scheduled", resolved_at=now
            )
        else:
            prov["surgery_scheduled_date"] = unresolved()

        if surgery_completed is not None:
            row["surgery_completed_date"] = surgery_completed
            prov["surgery_completed_date"] = auto(
                "interaction.event:surgery_completed", resolved_at=now
            )
        else:
            prov["surgery_completed_date"] = unresolved()

        # --- money (Net-Collected, ENG-283) ---
        net = collected.get(person_uid)
        row["revenue_amount"] = net
        row["collected_amount"] = net
        prov["revenue_amount"] = auto(
            "interaction:net_collected", confidence=1.0, resolved_at=now
        )
        prov["collected_amount"] = auto(
            "interaction:net_collected", confidence=1.0, resolved_at=now
        )

        # --- attribution (resolved only) ---
        campaign_id, campaign_name, vendor_id = attribution.get(
            person_uid, (None, None, None)
        )
        row["campaign_id"] = campaign_id
        row["campaign_name"] = campaign_name
        row["vendor_id"] = vendor_id
        prov["campaign_id"] = auto("attribution.lead_attribution", resolved_at=now)
        prov["campaign_name"] = auto("attribution.source_node.label", resolved_at=now)
        prov["vendor_id"] = auto("attribution.lead_attribution", resolved_at=now)

        # --- people dimensions: caller / coordinator / doctor (ENG-509/510) ---
        # Resolved to actor ids when a signal exists; NULL + unresolved
        # otherwise (counted, not dropped). A manual override later wins on
        # rebuild via merge_provenance + _preserve_manual_values.
        caller_id = caller_by_person.get(person_uid)
        if caller_id is not None:
            row["caller_id"] = caller_id
            prov["caller_id"] = auto("actor:salesforce_user_id:lead", resolved_at=now)
        else:
            prov["caller_id"] = unresolved()

        coordinator_id = coordinator_by_person.get(person_uid)
        if coordinator_id is not None:
            row["coordinator_id"] = coordinator_id
            prov["coordinator_id"] = auto(
                "actor:salesforce_user_id:opportunity", resolved_at=now
            )
        else:
            prov["coordinator_id"] = unresolved()

        doctor_id = doctor_by_person.get(person_uid)
        if doctor_id is not None:
            row["doctor_id"] = doctor_id
            prov["doctor_id"] = auto(
                "actor:carestack_provider_id:clinical", resolved_at=now
            )
        else:
            prov["doctor_id"] = unresolved()

        # --- implant case_type (ENG-539, B1.5) ---
        # CDT-derived coarse label; auto when the person's implant footprint is
        # determinative, else NULL + unresolved (*unclassified* — non-implant
        # persons and non-determinative implant footprints alike). A manual
        # override (ENG-513) wins on rebuild via merge_provenance +
        # _preserve_manual_values.
        resolution = case_type_by_person.get(person_uid)
        if resolution is not None and resolution.case_type is not None:
            row["case_type"] = resolution.case_type
            prov["case_type"] = auto("analytics.case_type:cdt", resolved_at=now)
        else:
            prov["case_type"] = unresolved()

        # --- fields with no canonical signal yet (later B1.*) ---
        for field in _UNRESOLVED_FIELDS:
            prov[field] = unresolved()

        # marketing_cost_allocated (ENG-512): seed unresolved; the allocation
        # pass flips it to ``auto`` for dated leads (else it stays unresolved).
        prov["marketing_cost_allocated"] = unresolved()

        return row, prov
