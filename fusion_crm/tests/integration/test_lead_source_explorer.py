"""DB-backed tests for the ENG-391 lead-source explorer aggregations.

Exercises ``OpsRepository.count_lead_funnel_by_source_tree``,
``count_consultation_funnel_by_source_tree``, and
``list_leads_for_source_node`` against a real Postgres test DB on a fresh
tenant (rolled back on teardown). The SQL under test groups by three
coalesced JSONB label expressions and joins consultations to leads via
``person_uid`` — exactly the parts a mocked-repo unit test cannot verify.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.identity.models import Person
from packages.interaction.models import Event
from packages.interaction.repository import InteractionRepository
from packages.ops.models import Consultation, ConsultationStatus, Lead
from packages.ops.repository import OpsRepository
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_MAY = datetime(2026, 5, 10, 12, 0, tzinfo=UTC)
_JUNE = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


async def _seed_person(session: AsyncSession, tenant_id: TenantId) -> Person:
    person = Person(
        tenant_id=tenant_id,
        given_name="Source",
        family_name="Explorer",
        display_name="Source Explorer",
    )
    session.add(person)
    await session.flush()
    return person


async def _seed_lead(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    source: str | None = None,
    extra: dict | None = None,
) -> Lead:
    lead = Lead(
        tenant_id=tenant_id,
        person_uid=person_uid,
        source=source,
        extra=extra or {},
    )
    session.add(lead)
    await session.flush()
    return lead


async def _seed_consultation(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    status: ConsultationStatus,
) -> Consultation:
    consultation = Consultation(
        tenant_id=tenant_id,
        person_uid=person_uid,
        source_provider="carestack",
        source_instance="carestack-test",
        external_id=f"appt-{uuid.uuid4().hex[:12]}",
        scheduled_at=_JUNE,
        status=status,
    )
    session.add(consultation)
    await session.flush()
    return consultation


async def _seed_payment_event(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    kind: str,
    amount: float,
) -> Event:
    event = Event(
        tenant_id=tenant_id,
        person_uid=person_uid,
        kind=kind,
        source_provider="carestack",
        source_event_id=None,
        data_class="billing",
        source_kind="carestack_accounting_transaction",
        source_external_id=f"txn-{uuid.uuid4().hex[:12]}",
        review_status="auto",
        occurred_at=_JUNE,
        summary=f"{kind} test",
        payload={"amount": amount},
    )
    session.add(event)
    await session.flush()
    return event


def _extra(medium: str | None, campaign: str | None, **overrides: object) -> dict:
    extra: dict = {"lead_source": "Google Ads", "sf_created_at": _MAY.isoformat()}
    if medium is not None:
        extra["utm_medium"] = medium
    if campaign is not None:
        extra["utm_campaign"] = campaign
    extra.update(overrides)
    return extra


@pytest.mark.asyncio
async def test_lead_source_tree_groups_and_joins_consultations(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="lead-src-tree")
    repo = OpsRepository(db_session)

    p1 = await _seed_person(db_session, tenant_id)
    p2 = await _seed_person(db_session, tenant_id)
    p3 = await _seed_person(db_session, tenant_id)

    await _seed_lead(
        db_session, tenant_id, person_uid=p1.id, extra=_extra("cpc", "implants-q2")
    )
    await _seed_lead(
        db_session, tenant_id, person_uid=p2.id, extra=_extra("cpc", "implants-q2")
    )
    # No attribution at all → every level lands in the "unknown" bucket.
    await _seed_lead(db_session, tenant_id, person_uid=p3.id)

    await _seed_consultation(
        db_session, tenant_id, person_uid=p1.id, status=ConsultationStatus.SCHEDULED
    )
    await _seed_consultation(
        db_session, tenant_id, person_uid=p1.id, status=ConsultationStatus.COMPLETED
    )
    await _seed_consultation(
        db_session, tenant_id, person_uid=p2.id, status=ConsultationStatus.NO_SHOW
    )

    lead_rows = await repo.count_lead_funnel_by_source_tree(tenant_id)
    assert ("google ads", "cpc", "implants-q2", 2) in lead_rows
    assert ("unknown", "unknown", "unknown", 1) in lead_rows

    consult_rows = await repo.count_consultation_funnel_by_source_tree(
        tenant_id,
        statuses=[
            ConsultationStatus.SCHEDULED.value,
            ConsultationStatus.COMPLETED.value,
        ],
    )
    # NO_SHOW filtered out; scheduled + completed both attach to the node.
    assert ("google ads", "cpc", "implants-q2", "scheduled", 1) in consult_rows
    assert ("google ads", "cpc", "implants-q2", "completed", 1) in consult_rows
    assert all(status != "no_show" for *_rest, status, _count in consult_rows)


@pytest.mark.asyncio
async def test_lead_source_tree_search_and_period_filters(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="lead-src-filter")
    repo = OpsRepository(db_session)

    p1 = await _seed_person(db_session, tenant_id)
    p2 = await _seed_person(db_session, tenant_id)

    # provider-created in May (sf_created_at wins over row created_at).
    await _seed_lead(
        db_session, tenant_id, person_uid=p1.id, extra=_extra("cpc", "implants-q2")
    )
    await _seed_lead(
        db_session,
        tenant_id,
        person_uid=p2.id,
        source="Referral",
        extra={"sf_created_at": _JUNE.isoformat()},
    )

    search_rows = await repo.count_lead_funnel_by_source_tree(tenant_id, search="referr")
    assert [row[0] for row in search_rows] == ["referral"]

    june_rows = await repo.count_lead_funnel_by_source_tree(
        tenant_id, created_from=datetime(2026, 6, 1, tzinfo=UTC)
    )
    assert [row[0] for row in june_rows] == ["referral"]


@pytest.mark.asyncio
async def test_list_leads_for_source_node_matches_bucket_and_paginates(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="lead-src-list")
    repo = OpsRepository(db_session)

    persons = [await _seed_person(db_session, tenant_id) for _ in range(3)]
    for person in persons[:2]:
        await _seed_lead(
            db_session,
            tenant_id,
            person_uid=person.id,
            extra=_extra("cpc", "implants-q2"),
        )
    await _seed_lead(db_session, tenant_id, person_uid=persons[2].id)

    total, leads = await repo.list_leads_for_source_node(
        tenant_id, source="google ads", medium="cpc", campaign="implants-q2"
    )
    assert total == 2
    assert len(leads) == 2

    total_page, page = await repo.list_leads_for_source_node(
        tenant_id, source="google ads", limit=1, offset=1
    )
    assert total_page == 2
    assert len(page) == 1

    # The "unknown" bucket is drillable too.
    unknown_total, unknown_leads = await repo.list_leads_for_source_node(
        tenant_id, source="unknown", medium="unknown", campaign="unknown"
    )
    assert unknown_total == 1
    assert unknown_leads[0].person_uid == persons[2].id


@pytest.mark.asyncio
async def test_collected_cash_per_person_and_node_mapping(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="lead-src-cash")
    ops_repo = OpsRepository(db_session)
    interaction_repo = InteractionRepository(db_session)

    payer = await _seed_person(db_session, tenant_id)
    refunded = await _seed_person(db_session, tenant_id)
    await _seed_lead(
        db_session, tenant_id, person_uid=payer.id, extra=_extra("cpc", "implants-q2")
    )
    await _seed_lead(db_session, tenant_id, person_uid=refunded.id)

    await _seed_payment_event(
        db_session, tenant_id, person_uid=payer.id, kind="payment_recorded", amount=1500.0
    )
    await _seed_payment_event(
        db_session, tenant_id, person_uid=payer.id, kind="payment_recorded", amount=500.0
    )
    # The allocation leg must not contaminate Collected.
    await _seed_payment_event(
        db_session, tenant_id, person_uid=payer.id, kind="payment_applied", amount=1500.0
    )
    await _seed_payment_event(
        db_session, tenant_id, person_uid=refunded.id, kind="payment_recorded", amount=200.0
    )
    await _seed_payment_event(
        db_session, tenant_id, person_uid=refunded.id, kind="payment_refunded", amount=50.0
    )

    collected = await interaction_repo.sum_collected_by_person(tenant_id)
    assert collected[payer.id] == 2000.0
    assert collected[refunded.id] == 150.0

    mapping = await ops_repo.map_persons_to_source_nodes(
        tenant_id, person_uids=list(collected)
    )
    assert ("google ads", "cpc", "implants-q2", payer.id) in mapping
    assert ("unknown", "unknown", "unknown", refunded.id) in mapping


@pytest.mark.asyncio
async def test_last_touch_overrides_and_case_buckets_merge(
    db_session: AsyncSession,
) -> None:
    """ENG-393: last touch wins; 'Facebook'/'facebook' collapse into one node."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="lead-src-touch")
    repo = OpsRepository(db_session)

    returning = await _seed_person(db_session, tenant_id)
    crm_labeled = await _seed_person(db_session, tenant_id)
    utm_labeled = await _seed_person(db_session, tenant_id)
    form_labeled = await _seed_person(db_session, tenant_id)

    # Came from Google first, re-entered via Facebook → belongs to facebook.
    await _seed_lead(
        db_session,
        tenant_id,
        person_uid=returning.id,
        extra={
            "utm_source": "google",
            "utm_medium": "cpc",
            "last_touch_source": "Facebook",
            "last_touch_medium": "paid_social",
        },
    )
    # CRM label "Facebook" (no UTM) and utm_source "facebook" must merge.
    await _seed_lead(
        db_session,
        tenant_id,
        person_uid=crm_labeled.id,
        extra={"hubspot_lead_source": "Facebook"},
    )
    await _seed_lead(
        db_session,
        tenant_id,
        person_uid=utm_labeled.id,
        extra={"utm_source": "facebook", "utm_medium": "cpc"},
    )
    # No UTM at all — only a HubSpot form name mentioning FB (ENG-394).
    await _seed_lead(
        db_session,
        tenant_id,
        person_uid=form_labeled.id,
        extra={
            "hubspot_lead_source": "Dental Implants Lead Capturing Form (FB Pixel Retargeted)"
        },
    )

    rows = await repo.count_lead_funnel_by_source_tree(tenant_id)
    by_source: dict[str, int] = {}
    for source, _medium, _campaign, count in rows:
        by_source[source] = by_source.get(source, 0) + count
    assert by_source == {
        "facebook": 3,
        "dental implants lead capturing form (fb pixel retargeted)": 1,
    }

    # Last-touch medium wins for the returning lead.
    assert ("facebook", "paid_social", "unknown", 1) in rows

    # Drill-down by the lowercased source label finds the three direct ones.
    total, _leads = await repo.list_leads_for_source_node(tenant_id, source="facebook")
    assert total == 3

    # ENG-394: the virtual channel drill catches the fb-named form too.
    channel_total, _ = await repo.list_leads_for_source_node(
        tenant_id, channel="facebook"
    )
    assert channel_total == 4


@pytest.mark.asyncio
async def test_priority_person_uids_float_payers_to_top(
    db_session: AsyncSession,
) -> None:
    """ENG-395 Collected sort: priority ids order the page, rest newest-first."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="lead-src-sort")
    repo = OpsRepository(db_session)

    persons = [await _seed_person(db_session, tenant_id) for _ in range(4)]
    for person in persons:
        await _seed_lead(
            db_session, tenant_id, person_uid=person.id, source="Referral"
        )

    # Caller pre-sorts by cash desc: persons[2] ($900) then persons[0] ($100).
    _, leads = await repo.list_leads_for_source_node(
        tenant_id,
        source="referral",
        priority_person_uids=[persons[2].id, persons[0].id],
    )
    assert [lead.person_uid for lead in leads[:2]] == [persons[2].id, persons[0].id]
    # Non-payers follow.
    assert {lead.person_uid for lead in leads[2:]} == {persons[1].id, persons[3].id}

    # Without the priority list the order is purely newest-first.
    _, default_leads = await repo.list_leads_for_source_node(
        tenant_id, source="referral"
    )
    assert len(default_leads) == 4


@pytest.mark.asyncio
async def test_location_match_scopes_tree_and_drilldown(
    db_session: AsyncSession,
) -> None:
    """ENG-398: assigned_center soft-match scopes every explorer query."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="lead-src-loc")
    repo = OpsRepository(db_session)

    roseville = await _seed_person(db_session, tenant_id)
    auburn = await _seed_person(db_session, tenant_id)
    await _seed_lead(
        db_session,
        tenant_id,
        person_uid=roseville.id,
        extra=_extra("cpc", "implants-q2", assigned_center="FDI - Roseville"),
    )
    await _seed_lead(
        db_session,
        tenant_id,
        person_uid=auburn.id,
        extra=_extra("cpc", "implants-q2", assigned_center="FDI - Auburn"),
    )

    all_rows = await repo.count_lead_funnel_by_source_tree(tenant_id)
    assert ("google ads", "cpc", "implants-q2", 2) in all_rows

    roseville_rows = await repo.count_lead_funnel_by_source_tree(
        tenant_id, location_match=["Roseville"]
    )
    assert ("google ads", "cpc", "implants-q2", 1) in roseville_rows

    total, leads = await repo.list_leads_for_source_node(
        tenant_id, source="google ads", location_match=["Roseville"]
    )
    assert total == 1
    assert leads[0].person_uid == roseville.id

    mapping = await repo.map_persons_to_source_nodes(
        tenant_id,
        person_uids=[roseville.id, auburn.id],
        location_match=["Roseville"],
    )
    assert [row[3] for row in mapping] == [roseville.id]


@pytest.mark.asyncio
async def test_location_match_normalizes_nbsp(db_session: AsyncSession) -> None:
    """SF writes 'El Dorado\xa0Hills' (U+00A0); plain-space needles must match."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="lead-src-nbsp")
    repo = OpsRepository(db_session)

    person = await _seed_person(db_session, tenant_id)
    await _seed_lead(
        db_session,
        tenant_id,
        person_uid=person.id,
        extra=_extra("cpc", "implants-q2", assigned_center="El Dorado\u00a0Hills"),
    )

    rows = await repo.count_lead_funnel_by_source_tree(
        tenant_id, location_match=["El Dorado Hills"]
    )
    assert ("google ads", "cpc", "implants-q2", 1) in rows

    total, _ = await repo.list_leads_for_source_node(
        tenant_id, source="google ads", location_match=["El Dorado Hills"]
    )
    assert total == 1


@pytest.mark.asyncio
async def test_location_scope_includes_consultation_evidence(
    db_session: AsyncSession,
) -> None:
    """ENG-400: a stale-center lead with a consultation at L is in L's scope."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="lead-src-evidence")
    repo = OpsRepository(db_session)
    edh_location = uuid.uuid4()

    stale = await _seed_person(db_session, tenant_id)  # lead says Roseville
    native = await _seed_person(db_session, tenant_id)  # lead says EDH
    elsewhere = await _seed_person(db_session, tenant_id)  # neither

    await _seed_lead(
        db_session, tenant_id, person_uid=stale.id,
        extra=_extra("cpc", "implants-q2", assigned_center="Roseville"),
    )
    await _seed_lead(
        db_session, tenant_id, person_uid=native.id,
        extra=_extra("cpc", "implants-q2", assigned_center="El Dorado Hills"),
    )
    await _seed_lead(
        db_session, tenant_id, person_uid=elsewhere.id,
        extra=_extra("cpc", "implants-q2", assigned_center="Roseville"),
    )

    # Consultation evidence at EDH for the stale-center lead only.
    consultation = await _seed_consultation(
        db_session, tenant_id, person_uid=stale.id, status=ConsultationStatus.SCHEDULED
    )
    consultation.location_id = edh_location
    await db_session.flush()

    rows = await repo.count_lead_funnel_by_source_tree(
        tenant_id,
        location_match=["El Dorado Hills"],
        location_id=edh_location,
    )
    # Both the native EDH lead AND the evidence-matched stale lead are in.
    assert ("google ads", "cpc", "implants-q2", 2) in rows

    total, leads = await repo.list_leads_for_source_node(
        tenant_id,
        source="google ads",
        location_match=["El Dorado Hills"],
        location_id=edh_location,
    )
    assert total == 2
    assert {lead.person_uid for lead in leads} == {stale.id, native.id}


@pytest.mark.asyncio
async def test_person_uids_for_source_node_scopes_payment_queries(
    db_session: AsyncSession,
) -> None:
    """ENG-408: PM Payments resource filter — node → persons → payment scope.

    ``OpsRepository.person_uids_for_source_node`` resolves an explorer node
    (no lead-creation window by design) and the interaction payment queries
    accept the resulting ids as a single array-bound ``person_uids`` filter.
    An empty id list is a real filter that matches nothing.
    """
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="lead-src-pay-scope")
    ops_repo = OpsRepository(db_session)
    interaction_repo = InteractionRepository(db_session)

    fb_payer = await _seed_person(db_session, tenant_id)
    fb_quiet = await _seed_person(db_session, tenant_id)
    google_payer = await _seed_person(db_session, tenant_id)

    await _seed_lead(
        db_session,
        tenant_id,
        person_uid=fb_payer.id,
        extra={"utm_source": "facebook", "utm_medium": "cpc"},
    )
    await _seed_lead(
        db_session,
        tenant_id,
        person_uid=fb_quiet.id,
        extra={"utm_source": "fb"},
    )
    await _seed_lead(
        db_session,
        tenant_id,
        person_uid=google_payer.id,
        extra={"utm_source": "google"},
    )

    await _seed_payment_event(
        db_session, tenant_id, person_uid=fb_payer.id, kind="payment_recorded", amount=500.0
    )
    await _seed_payment_event(
        db_session, tenant_id, person_uid=google_payer.id, kind="payment_recorded", amount=300.0
    )

    # Channel node "facebook" covers both the utm "facebook" and the "fb"
    # alias lead (ENG-394 CASE), regardless of lead age.
    fb_persons = await ops_repo.person_uids_for_source_node(
        tenant_id, channel="facebook"
    )
    assert set(fb_persons) == {fb_payer.id, fb_quiet.id}

    # Source-level node narrows to the exact label bucket.
    exact = await ops_repo.person_uids_for_source_node(
        tenant_id, channel="facebook", source="facebook", medium="cpc"
    )
    assert exact == [fb_payer.id]

    # The payment list/count/summary honour the person scope.
    rows = await interaction_repo.list_payment_events_for_dashboard(
        tenant_id, person_uids=list(fb_persons)
    )
    assert [r.person_uid for r in rows] == [fb_payer.id]
    total = await interaction_repo.count_payment_events_for_dashboard(
        tenant_id, person_uids=list(fb_persons)
    )
    assert total == 1
    summary = await interaction_repo.summarize_payment_events_for_dashboard(
        tenant_id, person_uids=list(fb_persons)
    )
    assert float(str(summary["collected_total"])) == 500.0
    assert summary["payment_count"] == 1
    assert summary["patient_count"] == 1

    # Empty node → empty scope → nothing matches (NOT "no filter").
    assert (
        await interaction_repo.count_payment_events_for_dashboard(
            tenant_id, person_uids=[]
        )
        == 0
    )
    # And None keeps the unscoped behaviour.
    assert (
        await interaction_repo.count_payment_events_for_dashboard(
            tenant_id, person_uids=None
        )
        == 2
    )
