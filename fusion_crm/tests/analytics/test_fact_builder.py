"""Unit tests for the fact_patient_journey builder logic (ENG-506 + ENG-509/510/513 + ENG-539).

DB-free: the domain services and the fact repository are replaced by light
fakes returning canned per-person maps, so these lock the projection +
provenance logic (lead vs CareStack-direct dating, Net-Collected mapping,
attribution, caller/coordinator/doctor resolution, implant case_type, unresolved
fields, idempotent provenance merge, and manual > auto precedence across a
rebuild) without a Postgres. The real-DB proof is
``tests/integration/test_fact_patient_journey_builder.py``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from packages.analytics.fact_builder import (
    FactPatientJourneyBuilder,
    _build_slug_index,
)
from packages.analytics.fact_repository import ExistingFactRow
from packages.analytics.provenance import FieldProvenance
from packages.core.types import TenantId

_TENANT = TenantId(uuid.uuid4())
_NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)

LEAD_P = uuid.uuid4()  # SF-lead person, full journey
DIRECT_P = uuid.uuid4()  # CareStack-direct (no lead), has activity
EMPTY_P = uuid.uuid4()  # CareStack-direct, zero activity

_LEAD_DATE = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
_CONSULT_AT = datetime(2026, 2, 1, 10, 0, tzinfo=UTC)
_SHOW_AT = datetime(2026, 2, 1, 10, 0, tzinfo=UTC)
_TREATMENT_AT = datetime(2026, 2, 3, 11, 0, tzinfo=UTC)
_PAYMENT_AT = datetime(2026, 2, 10, 12, 0, tzinfo=UTC)
# ENG-511 surgery-stage milestones for LEAD_P.
_ACCEPTED_AT = datetime(2026, 2, 4, 9, 0, tzinfo=UTC)
_SURGERY_SCHEDULED_AT = datetime(2026, 2, 20, 9, 0, tzinfo=UTC)
_SURGERY_COMPLETED_AT = datetime(2026, 3, 15, 9, 0, tzinfo=UTC)
_DIRECT_ACTIVITY = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
_LOCATION = uuid.uuid4()
_CAMPAIGN = uuid.uuid4()
_VENDOR = uuid.uuid4()

# B1 dimension fixtures.
_LEAD_OWNER_SF = "005AAAAAAAAAAAAAAA"  # SF user id -> caller actor
_OPP_OWNER_SF = "005BBBBBBBBBBBBBBB"  # SF user id -> coordinator actor
_CALLER_ACTOR = uuid.uuid4()
_COORDINATOR_ACTOR = uuid.uuid4()
_DOCTOR_ACTOR = uuid.uuid4()

# ENG-539 implant case_type fixtures. LEAD_P has a CareStack patient source link
# whose treatment procedures resolve to D6010 (placement) + D6114 (full-arch) —
# all_on_x wins the precedence. DIRECT_P / EMPTY_P have no implant procedures.
_LEAD_PATIENT_ID = "9001"
_CODE_D6010 = 101
_CODE_D6114 = 102


class _FakeOps:
    async def analytics_lead_facts_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {LEAD_P: (_LEAD_DATE, "google_ads")}

    async def analytics_consultation_facts_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {LEAD_P: (_CONSULT_AT, _SHOW_AT, _LOCATION)}

    async def full_funnel_earliest_consultation_at_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {DIRECT_P: _DIRECT_ACTIVITY}

    async def analytics_lead_owner_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {LEAD_P: _LEAD_OWNER_SF}

    async def analytics_opportunity_owner_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {LEAD_P: _OPP_OWNER_SF}


class _FakeInteraction:
    async def analytics_event_milestones_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {LEAD_P: (_TREATMENT_AT, _PAYMENT_AT)}

    async def analytics_surgery_stage_milestones_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {
            LEAD_P: (_ACCEPTED_AT, _SURGERY_SCHEDULED_AT, _SURGERY_COMPLETED_AT)
        }

    async def collected_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {LEAD_P: 5000.0}

    async def earliest_event_at_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {}

    async def analytics_clinical_actor_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {LEAD_P: _DOCTOR_ACTOR}


class _FakeIdentity:
    async def full_funnel_carestack_patient_person_uids(self, _tenant):  # type: ignore[no-untyped-def]
        return [DIRECT_P, EMPTY_P]

    async def source_links_for_external_records(self, _tenant, keys):  # type: ignore[no-untyped-def]
        out = {}
        for key in keys:
            if key == ("carestack", "carestack-main", "patient", _LEAD_PATIENT_ID):
                out[key] = SimpleNamespace(person_uid=LEAD_P)
        return out


class _FakeIngest:
    async def treatment_procedure_code_ids_by_patient(self, _tenant):  # type: ignore[no-untyped-def]
        return {_LEAD_PATIENT_ID: [_CODE_D6010, _CODE_D6114]}


class _FakeCatalog:
    async def resolve_procedure_codes(self, ids):  # type: ignore[no-untyped-def]
        mapping = {
            _CODE_D6010: ("D6010", "implant placement"),
            _CODE_D6114: ("D6114", "fixed denture, edentulous arch"),
        }
        return {i: mapping[i] for i in ids if i in mapping}


class _FakeAttribution:
    async def analytics_attribution_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {LEAD_P: (_CAMPAIGN, "Spring Implants", _VENDOR)}

    async def analytics_alloc_attribution_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        # LEAD_P resolved to ad "23856" (utm=id convention) under campaign "111".
        return {LEAD_P: ("23856", "111", 0.9)}


# Cost-per-lead allocation fixtures (ENG-512). LEAD_P's lead_date is 2026-01-05.
_ALLOC_DAY = _LEAD_DATE.date()


class _FakeMarketing:
    """Canned marketing spend for the cost-per-lead allocator path."""

    def __init__(
        self,
        *,
        ad_spend: float = 100.0,
        campaign_spend: float = 100.0,
    ) -> None:
        self._ad_spend = ad_spend
        self._campaign_spend = campaign_spend

    async def list_ads(self, _tenant, *, provider=None):  # type: ignore[no-untyped-def]
        return [
            SimpleNamespace(
                provider="meta_ads",
                external_id="23856",
                name="Implant Promo - Video A",
                campaign_external_id="111",
            )
        ]

    async def list_campaigns(self, _tenant, *, provider=None):  # type: ignore[no-untyped-def]
        return [
            SimpleNamespace(
                provider="meta_ads", external_id="111", name="Implants - Roseville"
            )
        ]

    async def ad_daily_spend(self, _tenant, *, start_date, end_date):  # type: ignore[no-untyped-def]
        return [
            SimpleNamespace(
                ad_external_id="23856",
                campaign_external_id="111",
                metric_date=_ALLOC_DAY,
                spend=self._ad_spend,
            )
        ]

    async def campaign_daily_spend(self, _tenant, *, start_date, end_date):  # type: ignore[no-untyped-def]
        return [
            SimpleNamespace(
                campaign_external_id="111",
                metric_date=_ALLOC_DAY,
                spend=self._campaign_spend,
            )
        ]


class _FakeActor:
    """Resolve SF user ids to canned actor ids; records what it was asked."""

    def __init__(self) -> None:
        self.requested: set[str] = set()

    async def resolve_actor_ids_from_source(  # type: ignore[no-untyped-def]
        self, _tenant, *, source_provider, source_instance, external_ids, name_hints=None
    ):
        self.requested |= {e for e in external_ids}
        mapping = {_LEAD_OWNER_SF: _CALLER_ACTOR, _OPP_OWNER_SF: _COORDINATOR_ACTOR}
        return {sf: mapping[sf] for sf in external_ids if sf in mapping}


class _FakeRepo:
    def __init__(self, existing: dict | None = None) -> None:
        self.existing = existing or {}
        self.upserted: list[dict] = []

    async def existing_for_merge(self, person_uids):  # type: ignore[no-untyped-def]
        return {p: self.existing[p] for p in person_uids if p in self.existing}

    async def upsert_many(self, rows):  # type: ignore[no-untyped-def]
        self.upserted = list(rows)
        return len(self.upserted)


def _builder(
    repo: _FakeRepo,
    actor: _FakeActor | None = None,
    *,
    marketing: _FakeMarketing | None = None,
) -> FactPatientJourneyBuilder:
    return FactPatientJourneyBuilder(
        ops=_FakeOps(),  # type: ignore[arg-type]
        identity=_FakeIdentity(),  # type: ignore[arg-type]
        interaction=_FakeInteraction(),  # type: ignore[arg-type]
        attribution=_FakeAttribution(),  # type: ignore[arg-type]
        actor=actor or _FakeActor(),  # type: ignore[arg-type]
        ingest=_FakeIngest(),  # type: ignore[arg-type]
        catalog=_FakeCatalog(),  # type: ignore[arg-type]
        repo=repo,  # type: ignore[arg-type]
        marketing=marketing,  # type: ignore[arg-type]
    )


def _by_person(repo: _FakeRepo) -> dict:
    return {r["person_uid"]: r for r in repo.upserted}


async def test_universe_is_one_row_per_person() -> None:
    repo = _FakeRepo()
    result = await _builder(repo).build(_TENANT, now=_NOW)
    assert result.persons == 3
    assert result.rows_written == 3
    assert set(_by_person(repo)) == {LEAD_P, DIRECT_P, EMPTY_P}


async def test_lead_person_projection() -> None:
    repo = _FakeRepo()
    await _builder(repo).build(_TENANT, now=_NOW)
    row = _by_person(repo)[LEAD_P]
    assert row["lead_date"] == _LEAD_DATE
    assert row["source"] == "google_ads"
    assert row["consult_scheduled_date"] == _CONSULT_AT
    assert row["show_date"] == _SHOW_AT
    assert row["location_id"] == _LOCATION
    assert row["treatment_presented_date"] == _TREATMENT_AT
    assert row["first_payment_date"] == _PAYMENT_AT
    # revenue_amount and collected_amount both map to Net-Collected (ENG-506).
    assert row["revenue_amount"] == 5000.0
    assert row["collected_amount"] == 5000.0
    assert row["campaign_id"] == _CAMPAIGN
    assert row["campaign_name"] == "Spring Implants"
    assert row["vendor_id"] == _VENDOR


async def test_caller_coordinator_doctor_resolved(  # ENG-509 / ENG-510
) -> None:
    repo = _FakeRepo()
    actor = _FakeActor()
    await _builder(repo, actor).build(_TENANT, now=_NOW)
    row = _by_person(repo)[LEAD_P]
    assert row["caller_id"] == _CALLER_ACTOR
    assert row["coordinator_id"] == _COORDINATOR_ACTOR
    assert row["doctor_id"] == _DOCTOR_ACTOR
    prov = row["field_provenance"]
    assert prov["caller_id"]["method"] == "auto"
    assert prov["coordinator_id"]["method"] == "auto"
    assert prov["doctor_id"]["method"] == "auto"
    # Distinct SF owner ids were resolved exactly once (batch backfill).
    assert actor.requested == {_LEAD_OWNER_SF, _OPP_OWNER_SF}


async def test_unresolved_people_dimensions_when_no_signal() -> None:
    # DIRECT_P has no lead/opportunity owner and no clinical actor.
    repo = _FakeRepo()
    await _builder(repo).build(_TENANT, now=_NOW)
    direct = _by_person(repo)[DIRECT_P]
    assert direct.get("caller_id") is None
    assert direct.get("coordinator_id") is None
    assert direct.get("doctor_id") is None
    prov = direct["field_provenance"]
    assert prov["caller_id"]["method"] == "unresolved"
    assert prov["coordinator_id"]["method"] == "unresolved"
    assert prov["doctor_id"]["method"] == "unresolved"


async def test_carestack_direct_dating_uses_earliest_activity() -> None:
    repo = _FakeRepo()
    await _builder(repo).build(_TENANT, now=_NOW)
    direct = _by_person(repo)[DIRECT_P]
    # Dated by earliest activity, NOT a bulk-import date; no lead → null source.
    assert direct["lead_date"] == _DIRECT_ACTIVITY
    assert direct["source"] is None
    assert direct["revenue_amount"] is None


async def test_zero_activity_direct_person_has_null_lead_date() -> None:
    repo = _FakeRepo()
    await _builder(repo).build(_TENANT, now=_NOW)
    empty = _by_person(repo)[EMPTY_P]
    assert empty["lead_date"] is None
    assert empty["consult_scheduled_date"] is None
    assert empty["collected_amount"] is None


async def test_provenance_methods() -> None:
    repo = _FakeRepo()
    await _builder(repo).build(_TENANT, now=_NOW)
    prov = _by_person(repo)[LEAD_P]["field_provenance"]
    # Auto-derived fields.
    assert prov["lead_date"]["method"] == "auto"
    assert prov["revenue_amount"]["method"] == "auto"
    assert prov["campaign_id"]["method"] == "auto"
    # ENG-511: surgery-stage fields auto-resolve when a milestone exists.
    assert prov["treatment_accepted_date"]["method"] == "auto"
    assert prov["surgery_scheduled_date"]["method"] == "auto"
    assert prov["surgery_completed_date"]["method"] == "auto"
    # Fields with no signal yet ship unresolved.
    for field in (
        "first_contact_date",
        "marketing_cost_allocated",
    ):
        assert prov[field]["method"] == "unresolved"


async def test_surgery_stage_milestones_resolved() -> None:  # ENG-511
    repo = _FakeRepo()
    await _builder(repo).build(_TENANT, now=_NOW)
    row = _by_person(repo)[LEAD_P]
    assert row["treatment_accepted_date"] == _ACCEPTED_AT
    assert row["surgery_scheduled_date"] == _SURGERY_SCHEDULED_AT
    assert row["surgery_completed_date"] == _SURGERY_COMPLETED_AT
    prov = row["field_provenance"]
    assert prov["treatment_accepted_date"]["source"] == (
        "interaction.event:treatment_accepted"
    )
    assert prov["surgery_scheduled_date"]["source"] == (
        "interaction.event:surgery_scheduled"
    )
    assert prov["surgery_completed_date"]["source"] == (
        "interaction.event:surgery_completed"
    )


async def test_surgery_stage_unresolved_when_no_signal() -> None:  # ENG-511
    # DIRECT_P has no surgery-stage milestones.
    repo = _FakeRepo()
    await _builder(repo).build(_TENANT, now=_NOW)
    direct = _by_person(repo)[DIRECT_P]
    assert direct.get("treatment_accepted_date") is None
    assert direct.get("surgery_scheduled_date") is None
    assert direct.get("surgery_completed_date") is None
    prov = direct["field_provenance"]
    assert prov["treatment_accepted_date"]["method"] == "unresolved"
    assert prov["surgery_scheduled_date"]["method"] == "unresolved"
    assert prov["surgery_completed_date"]["method"] == "unresolved"


async def test_rebuild_preserves_manual_surgery_date_over_auto() -> None:  # ENG-511/513
    # An operator manually set surgery_completed_date; a rebuild must keep the
    # manual value + provenance even though the auto resolver has its own value.
    manual_date = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
    manual = FieldProvenance(
        source="enrichment:ui", method="manual", confidence=1.0
    ).to_jsonb()
    repo = _FakeRepo(
        existing={
            LEAD_P: ExistingFactRow(
                field_provenance={"surgery_completed_date": manual},
                values={"surgery_completed_date": manual_date},
            )
        }
    )
    await _builder(repo).build(_TENANT, now=_NOW)
    row = _by_person(repo)[LEAD_P]
    # Auto resolver would set _SURGERY_COMPLETED_AT, but manual wins.
    assert row["surgery_completed_date"] == manual_date
    assert row["field_provenance"]["surgery_completed_date"]["method"] == "manual"
    # A sibling surgery field with no manual override still auto-resolves.
    assert row["surgery_scheduled_date"] == _SURGERY_SCHEDULED_AT
    assert row["field_provenance"]["surgery_scheduled_date"]["method"] == "auto"


async def test_rebuild_preserves_manual_provenance() -> None:
    # A prior manual enrichment on caller_id must survive a rebuild.
    manual = FieldProvenance(
        source="staff:enrichment", method="manual", confidence=1.0
    ).to_jsonb()
    repo = _FakeRepo(
        existing={
            LEAD_P: ExistingFactRow(
                field_provenance={"caller_id": manual},
                values={"caller_id": _CALLER_ACTOR},
            )
        }
    )
    await _builder(repo).build(_TENANT, now=_NOW)
    prov = _by_person(repo)[LEAD_P]["field_provenance"]
    assert prov["caller_id"]["method"] == "manual"
    assert prov["caller_id"]["source"] == "staff:enrichment"


async def test_rebuild_preserves_manual_value_over_auto() -> None:  # ENG-513
    # caller_id was set manually to a DIFFERENT actor than the auto resolver
    # would produce; the rebuild must keep the manual VALUE, not just provenance.
    manual_actor = uuid.uuid4()
    manual = FieldProvenance(
        source="enrichment:ui", method="manual", confidence=1.0
    ).to_jsonb()
    repo = _FakeRepo(
        existing={
            LEAD_P: ExistingFactRow(
                field_provenance={"caller_id": manual},
                values={"caller_id": manual_actor},
            )
        }
    )
    await _builder(repo).build(_TENANT, now=_NOW)
    row = _by_person(repo)[LEAD_P]
    # The auto resolver maps LEAD_P -> _CALLER_ACTOR, but manual wins.
    assert row["caller_id"] == manual_actor
    assert row["field_provenance"]["caller_id"]["method"] == "manual"
    # A non-manual field still refreshes to its auto value.
    assert row["coordinator_id"] == _COORDINATOR_ACTOR


async def test_incremental_only_persons_restricts_writes() -> None:
    repo = _FakeRepo()
    result = await _builder(repo).build(_TENANT, only_persons={LEAD_P}, now=_NOW)
    assert result.persons == 1
    assert set(_by_person(repo)) == {LEAD_P}


async def test_idempotent_same_rows_on_rerun() -> None:
    repo1 = _FakeRepo()
    await _builder(repo1).build(_TENANT, now=_NOW)
    repo2 = _FakeRepo()
    await _builder(repo2).build(_TENANT, now=_NOW)
    # Same projected values (ignoring provenance resolved_at which is fixed _NOW).
    assert _by_person(repo1)[LEAD_P]["lead_date"] == _by_person(repo2)[LEAD_P][
        "lead_date"
    ]
    assert _by_person(repo1).keys() == _by_person(repo2).keys()


async def test_case_type_resolved_from_cdt() -> None:  # ENG-539
    # LEAD_P's procedures resolve to D6010 + D6114 → all_on_x wins precedence.
    repo = _FakeRepo()
    await _builder(repo).build(_TENANT, now=_NOW)
    row = _by_person(repo)[LEAD_P]
    assert row["case_type"] == "all_on_x"
    assert row["field_provenance"]["case_type"]["method"] == "auto"
    assert row["field_provenance"]["case_type"]["source"] == "analytics.case_type:cdt"


async def test_case_type_unresolved_when_no_implant() -> None:  # ENG-539
    # DIRECT_P / EMPTY_P have no implant procedures → NULL + unresolved.
    repo = _FakeRepo()
    await _builder(repo).build(_TENANT, now=_NOW)
    for person in (DIRECT_P, EMPTY_P):
        row = _by_person(repo)[person]
        assert row.get("case_type") is None
        assert row["field_provenance"]["case_type"]["method"] == "unresolved"


async def test_rebuild_preserves_manual_case_type_over_auto() -> None:  # ENG-539/513
    # An operator set case_type to a manual-only value the auto resolver can
    # never produce (all_on_4); a rebuild must keep it over the auto all_on_x.
    manual = FieldProvenance(
        source="enrichment:ui", method="manual", confidence=1.0
    ).to_jsonb()
    repo = _FakeRepo(
        existing={
            LEAD_P: ExistingFactRow(
                field_provenance={"case_type": manual},
                values={"case_type": "all_on_4"},
            )
        }
    )
    await _builder(repo).build(_TENANT, now=_NOW)
    row = _by_person(repo)[LEAD_P]
    assert row["case_type"] == "all_on_4"
    assert row["field_provenance"]["case_type"]["method"] == "manual"


@pytest.mark.parametrize("only", [set(), None])
async def test_empty_universe_when_only_persons_empty(only) -> None:  # type: ignore[no-untyped-def]
    # only_persons=set() → nothing written; None → full universe.
    repo = _FakeRepo()
    result = await _builder(repo).build(_TENANT, only_persons=only, now=_NOW)
    if only == set():
        assert result.persons == 0
        assert repo.upserted == []
    else:
        assert result.persons == 3


# --- cost-per-lead allocation (ENG-512) -----------------------------------


async def test_marketing_cost_allocated_auto_when_marketing_wired() -> None:
    # LEAD_P bridges to ad "23856" ($100, sole lead that day) → $100 cost,
    # provenance auto. Persons with no lead_date stay unresolved.
    repo = _FakeRepo()
    result = await _builder(repo, marketing=_FakeMarketing()).build(_TENANT, now=_NOW)
    lead = _by_person(repo)[LEAD_P]
    assert lead["marketing_cost_allocated"] == 100.0
    prov = lead["field_provenance"]["marketing_cost_allocated"]
    assert prov["method"] == "auto"
    assert prov["confidence"] == 0.9
    # EMPTY_P has no lead_date → cannot time-match spend → stays unresolved.
    empty = _by_person(repo)[EMPTY_P]
    assert empty.get("marketing_cost_allocated") is None
    assert (
        empty["field_provenance"]["marketing_cost_allocated"]["method"] == "unresolved"
    )
    # spend fully attributed to the one lead → no spend without leads.
    assert result.spend_without_leads == 0.0


async def test_marketing_cost_unresolved_without_marketing_service() -> None:
    # No MarketingService → allocator no-ops; field stays unresolved (the
    # DB-free default for the other-dimension tests).
    repo = _FakeRepo()
    result = await _builder(repo).build(_TENANT, now=_NOW)
    prov = _by_person(repo)[LEAD_P]["field_provenance"]
    assert prov["marketing_cost_allocated"]["method"] == "unresolved"
    assert result.spend_without_leads is None


async def test_manual_marketing_cost_survives_rebuild() -> None:  # ENG-513
    # A prior manual marketing_cost_allocated must not be clobbered by the auto
    # allocator on rebuild (manual > auto), value AND provenance.
    manual = FieldProvenance(
        source="staff:enrichment", method="manual", confidence=1.0
    ).to_jsonb()
    repo = _FakeRepo(
        existing={
            LEAD_P: ExistingFactRow(
                field_provenance={"marketing_cost_allocated": manual},
                values={"marketing_cost_allocated": 4242.0},
            )
        }
    )
    await _builder(repo, marketing=_FakeMarketing()).build(_TENANT, now=_NOW)
    lead = _by_person(repo)[LEAD_P]
    assert lead["marketing_cost_allocated"] == 4242.0
    prov = lead["field_provenance"]["marketing_cost_allocated"]
    assert prov["method"] == "manual"
    assert prov["source"] == "staff:enrichment"


# --- Blocker 1: incremental refresh must use the full-population denominator


_INCR_P1 = uuid.uuid4()
_INCR_P2 = uuid.uuid4()


class _TwoLeadOps:
    """Two SF-lead persons on the SAME ad/day (so the ad's spend splits 2 ways)."""

    async def analytics_lead_facts_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {_INCR_P1: (_LEAD_DATE, "meta_ads"), _INCR_P2: (_LEAD_DATE, "meta_ads")}

    async def analytics_consultation_facts_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {}

    async def full_funnel_earliest_consultation_at_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {}

    async def analytics_lead_owner_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {}

    async def analytics_opportunity_owner_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {}


class _EmptyInteraction:
    async def analytics_event_milestones_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {}

    async def analytics_surgery_stage_milestones_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {}

    async def collected_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {}

    async def earliest_event_at_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {}

    async def analytics_clinical_actor_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {}


class _EmptyIdentity:
    async def full_funnel_carestack_patient_person_uids(self, _tenant):  # type: ignore[no-untyped-def]
        return []

    async def source_links_for_external_records(self, _tenant, _keys):  # type: ignore[no-untyped-def]
        return {}


class _TwoLeadAttribution:
    async def analytics_attribution_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        return {}

    async def analytics_alloc_attribution_by_person(self, _tenant):  # type: ignore[no-untyped-def]
        # Both leads resolve to the same ad "23856" under campaign "111".
        return {
            _INCR_P1: ("23856", "111", 0.9),
            _INCR_P2: ("23856", "111", 0.9),
        }


async def test_incremental_refresh_denominator_uses_full_population() -> None:
    # Two leads attributed to ad "23856" on the same day ($100 spend). An
    # incremental refresh of ONLY _INCR_P1 must still split across BOTH leads
    # (denominator = full population) → $50, not the whole $100.
    repo = _FakeRepo()
    builder = FactPatientJourneyBuilder(
        ops=_TwoLeadOps(),  # type: ignore[arg-type]
        identity=_EmptyIdentity(),  # type: ignore[arg-type]
        interaction=_EmptyInteraction(),  # type: ignore[arg-type]
        attribution=_TwoLeadAttribution(),  # type: ignore[arg-type]
        actor=_FakeActor(),  # type: ignore[arg-type]
        repo=repo,  # type: ignore[arg-type]
        marketing=_FakeMarketing(),  # type: ignore[arg-type]
        ingest=_FakeIngest(),  # type: ignore[arg-type]
        catalog=_FakeCatalog(),  # type: ignore[arg-type]
    )
    result = await builder.build(_TENANT, only_persons={_INCR_P1}, now=_NOW)
    # Only the in-scope person is written.
    assert set(_by_person(repo)) == {_INCR_P1}
    # ...but its cost is spend / 2 (full denominator), NOT the whole spend.
    assert _by_person(repo)[_INCR_P1]["marketing_cost_allocated"] == 50.0
    assert result.persons == 1


# --- Blocker 3a: slug collisions are ambiguous → unmatched ----------------


def test_build_slug_index_collision_is_ambiguous() -> None:
    # Two ads whose NAMES slugify identically: that name-slug is ambiguous and
    # must be dropped, so a lead carrying it resolves to NEITHER ad's spend.
    index = _build_slug_index([("100", "Promo Video"), ("200", "promo video")])
    # The unique raw ids still resolve to themselves (utm=id convention intact).
    assert index["100"] == "100"
    assert index["200"] == "200"
    # The colliding name slug maps to neither id.
    assert "promo_video" not in index


def test_build_slug_index_non_colliding_names_resolve() -> None:
    index = _build_slug_index([("100", "Promo Video A"), ("200", "Promo Video B")])
    assert index["promo_video_a"] == "100"
    assert index["promo_video_b"] == "200"
