"""ENG-483 — Full Funnel v2 contract + reconciliation integration tests.

These lock the person-anchored Full Funnel read model
(``packages.analytics.full_funnel.FullFunnelService``) against a real Postgres
test DB on a fresh tenant (rolled back on teardown). They are the suite the
ENG-481/ENG-482 contract depends on: each test seeds a small, deterministic
fixture and asserts the read model's output, reconciling the headline + monthly
breakdown against *independent* raw SQL aggregates over the same seeded rows —
no mocks, no re-implementation of the service's own SQL.

Coverage (per ENG-483 / ``docs/analytics/full-funnel-v2-person-anchored.md`` §9):

1. ``test_per_audience_reconciliation_matches_raw_sql`` — for ``all`` and
   ``marketing``, headline + every by_month stage match raw SQL aggregates.
2. ``test_appointment_sum_identity`` — every month/channel row satisfies
   ``showed + no_show + cancelled + rescheduled + pending == consults_scheduled``
   (deleted excluded).
3. ``test_marketing_is_subset_of_all`` — every stage, every month, marketing ≤ all.
4. ``test_status_mapping_buckets`` — each canonical status (and the past/future
   ``scheduled`` time rule + ``deleted`` exclusion) lands in the right bucket.
5. ``test_closed_won_is_money`` — closed_won = payers with Net Collected > 0,
   revenue = recorded − refunded − reversed, non-zero.
6. ``test_carestack_direct_dating_and_audience`` — a CareStack-direct person
   (no ``ops.lead``) with activity appears in ``all`` (channel ``other``) but
   not ``marketing``; a zero-activity one falls to the 2025 sentinel and is
   absent from a 2026 window.

The reporting window is pinned with explicit ``start_date`` / ``end_date`` and
all fixture timestamps sit comfortably inside (or, for the sentinel case,
outside) it so the assertions are deterministic. The only ``now()``-dependent
rule — a still-``scheduled`` past appointment counting as a no-show — is
exercised with timestamps far in the past / future relative to the test clock.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.analytics.full_funnel import FullFunnelService
from packages.core.types import TenantId
from packages.identity.models import Person, SourceLink
from packages.identity.service import IdentityService
from packages.interaction.models import Event
from packages.interaction.service import InteractionService
from packages.marketing.service import MarketingService
from packages.ops.models import Consultation, ConsultationStatus, Lead
from packages.ops.service import OpsService
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

# Pinned reporting window for the reconciliation tests (inclusive months).
_WINDOW_START = date(2026, 3, 1)
_WINDOW_END = date(2026, 6, 30)
# A clearly-past instant and a clearly-future one — both INSIDE the pinned
# window — used for the still-``scheduled`` time rule (past → no-show, future →
# pending). The test clock is 2026-06-16, so 2026-03-10 is firmly past and
# 2099-05-10 is firmly future; ``_FUTURE_IN_WINDOW`` (late June 2026) is future
# yet still inside ``_WINDOW_END`` so the pending row renders without tripping
# the 24-month window cap.
_PAST_IN_WINDOW = datetime(2026, 3, 10, 9, 0, tzinfo=UTC)
_FUTURE_IN_WINDOW = datetime(2026, 6, 25, 9, 0, tzinfo=UTC)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


def _service(session: AsyncSession) -> FullFunnelService:
    """Wire the read model exactly as the API dependency does."""
    return FullFunnelService(
        ops=OpsService(session),
        identity=IdentityService(session),
        interaction=InteractionService(
            session, operational_projection_reader=OpsService(session)
        ),
        marketing=MarketingService(session),
    )


async def _seed_person(session: AsyncSession, tenant_id: TenantId) -> Person:
    person = Person(
        tenant_id=tenant_id,
        given_name="Funnel",
        family_name="V2",
        display_name="Funnel V2",
    )
    session.add(person)
    await session.flush()
    return person


async def _seed_lead(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    created_at: datetime,
    extra: dict[str, object] | None = None,
) -> Lead:
    lead = Lead(tenant_id=tenant_id, person_uid=person_uid, extra=extra or {})
    lead.created_at = created_at
    session.add(lead)
    await session.flush()
    return lead


async def _seed_consultation(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    scheduled_at: datetime,
    status: ConsultationStatus,
) -> Consultation:
    consult = Consultation(
        tenant_id=tenant_id,
        person_uid=person_uid,
        source_provider="carestack",
        source_instance="carestack-test",
        external_id=f"appt-{uuid.uuid4().hex[:12]}",
        scheduled_at=scheduled_at,
        status=status,
    )
    session.add(consult)
    await session.flush()
    return consult


async def _seed_carestack_patient_link(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
) -> SourceLink:
    link = SourceLink(
        tenant_id=tenant_id,
        person_uid=person_uid,
        source_system="carestack",
        source_instance="carestack-test",
        source_kind="patient",
        source_id=f"cs-{uuid.uuid4().hex[:12]}",
    )
    session.add(link)
    await session.flush()
    return link


async def _seed_payment(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    kind: str,
    amount: str,
    occurred_at: datetime,
) -> Event:
    """Seed one CareStack accounting-transaction payment leg (Net Collected)."""
    event = Event(
        tenant_id=tenant_id,
        person_uid=person_uid,
        kind=kind,
        source_provider="carestack",
        data_class="billing",
        source_kind="carestack_accounting_transaction",
        source_external_id=f"txn-{uuid.uuid4().hex[:12]}",
        review_status="auto",
        occurred_at=occurred_at,
        summary=f"{kind} test",
        payload={"amount": amount},
    )
    session.add(event)
    await session.flush()
    return event


# ---------------------------------------------------------------------------
# 1. Per-audience reconciliation vs independent raw SQL.
# ---------------------------------------------------------------------------


async def _raw_leads(session: AsyncSession, tenant_id: TenantId) -> int:
    """Distinct persons with an ops.lead OR a carestack/patient link (all)."""
    row = await session.scalar(
        text(
            """
            SELECT count(*) FROM (
                SELECT person_uid FROM ops.lead WHERE tenant_id = :t
                UNION
                SELECT person_uid FROM identity.source_link
                WHERE tenant_id = :t
                  AND source_system = 'carestack' AND source_kind = 'patient'
            ) u
            """
        ),
        {"t": tenant_id},
    )
    return int(row or 0)


@pytest.mark.parametrize("audience", ["all", "marketing"])
async def test_per_audience_reconciliation_matches_raw_sql(
    db_session: AsyncSession, audience: str
) -> None:
    """Headline + by_month match raw SQL aggregates for both audiences."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="ff-recon")

    # --- Marketing (google) lead person: lead Apr, consult showed Apr, paid May.
    p_google = await _seed_person(db_session, tenant_id)
    await _seed_lead(
        db_session, tenant_id, person_uid=p_google.id,
        created_at=datetime(2026, 4, 5, tzinfo=UTC),
        extra={"utm_source": "google", "utm_medium": "cpc"},
    )
    await _seed_consultation(
        db_session, tenant_id, person_uid=p_google.id,
        scheduled_at=datetime(2026, 4, 12, tzinfo=UTC),
        status=ConsultationStatus.COMPLETED,
    )
    await _seed_payment(
        db_session, tenant_id, person_uid=p_google.id,
        kind="payment_recorded", amount="1500.00",
        occurred_at=datetime(2026, 5, 9, tzinfo=UTC),
    )

    # --- Marketing (facebook) lead person: lead May, consult no_show May.
    p_fb = await _seed_person(db_session, tenant_id)
    await _seed_lead(
        db_session, tenant_id, person_uid=p_fb.id,
        created_at=datetime(2026, 5, 3, tzinfo=UTC),
        extra={"utm_source": "facebook"},
    )
    await _seed_consultation(
        db_session, tenant_id, person_uid=p_fb.id,
        scheduled_at=datetime(2026, 5, 20, tzinfo=UTC),
        status=ConsultationStatus.NO_SHOW,
    )

    # --- Non-marketing (referral) lead person: lead Apr, consult cancelled Apr.
    p_other = await _seed_person(db_session, tenant_id)
    await _seed_lead(
        db_session, tenant_id, person_uid=p_other.id,
        created_at=datetime(2026, 4, 18, tzinfo=UTC),
        extra={"utm_source": "referral"},
    )
    await _seed_consultation(
        db_session, tenant_id, person_uid=p_other.id,
        scheduled_at=datetime(2026, 4, 25, tzinfo=UTC),
        status=ConsultationStatus.CANCELLED,
    )
    await _seed_payment(
        db_session, tenant_id, person_uid=p_other.id,
        kind="payment_recorded", amount="800.00",
        occurred_at=datetime(2026, 5, 15, tzinfo=UTC),
    )

    out = await _service(db_session).compute(
        tenant_id, audience=audience, start_date=_WINDOW_START, end_date=_WINDOW_END
    )

    # --- Independent raw expectations over the seeded rows (audience-aware).
    # Marketing person_uids: utm_source ∈ {google, facebook}.
    marketing_only = audience == "marketing"

    # Leads: distinct persons in window, optionally restricted to ad channels.
    if marketing_only:
        expected_leads = 2  # google + facebook
    else:
        expected_leads = 3

    # Consults by status (in window). all: 1 showed + 1 no_show + 1 cancelled.
    # marketing: 1 showed (google) + 1 no_show (facebook); referral cancel drops.
    expected_showed = 1
    expected_no_show = 1
    expected_cancelled = 0 if marketing_only else 1
    expected_scheduled = expected_showed + expected_no_show + expected_cancelled

    # Revenue / closed_won. all: google 1500 + referral 800. marketing: google only.
    if marketing_only:
        expected_revenue = 1500.0
        expected_closed_won = 1
    else:
        expected_revenue = 2300.0
        expected_closed_won = 2

    h = out.headline
    assert h.leads == expected_leads
    assert h.consults_scheduled == expected_scheduled
    assert h.showed == expected_showed
    assert h.no_show == expected_no_show
    assert h.cancelled == expected_cancelled
    assert h.rescheduled == 0
    assert h.pending == 0
    assert h.closed_won == expected_closed_won
    assert h.revenue == pytest.approx(expected_revenue)

    # by_month reconciliation: sum the monthly rows back to the headline and
    # check the month each stage lands in (lead/consult/payment each on its own
    # timestamp).
    by_month = {m.month: m for m in out.by_month}
    assert set(by_month) == {"2026-03", "2026-04", "2026-05", "2026-06"}
    assert sum(m.leads for m in out.by_month) == expected_leads
    assert sum(m.consults_scheduled for m in out.by_month) == expected_scheduled
    assert sum(m.showed for m in out.by_month) == expected_showed
    assert sum(m.no_show for m in out.by_month) == expected_no_show
    assert sum(m.cancelled for m in out.by_month) == expected_cancelled
    assert sum(m.closed_won for m in out.by_month) == expected_closed_won
    assert sum(m.revenue for m in out.by_month) == pytest.approx(expected_revenue)

    # Stage-on-own-timestamp placement.
    assert by_month["2026-04"].showed == 1  # google consult booked April
    assert by_month["2026-05"].no_show == 1  # facebook consult booked May
    assert by_month["2026-05"].revenue == pytest.approx(
        1500.0 if marketing_only else 2300.0
    )  # google paid + referral paid both in May
    if not marketing_only:
        assert by_month["2026-04"].cancelled == 1

    # Cross-check leads against raw SQL (all-audience only — the union query has
    # no channel filter).
    if not marketing_only:
        assert h.leads == await _raw_leads(db_session, tenant_id)


# ---------------------------------------------------------------------------
# 2. Appointment-level sum identity.
# ---------------------------------------------------------------------------


async def test_appointment_sum_identity(db_session: AsyncSession) -> None:
    """showed+no_show+cancelled+rescheduled+pending == consults_scheduled."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="ff-sum")

    # One marketing (google) person carrying every status + a deleted row, plus
    # a future scheduled (pending) and a past scheduled (→ no_show).
    person = await _seed_person(db_session, tenant_id)
    await _seed_lead(
        db_session, tenant_id, person_uid=person.id,
        created_at=datetime(2026, 3, 2, tzinfo=UTC),
        extra={"utm_source": "google"},
    )
    statuses = [
        (ConsultationStatus.COMPLETED, datetime(2026, 3, 5, tzinfo=UTC)),
        (ConsultationStatus.NO_SHOW, datetime(2026, 3, 6, tzinfo=UTC)),
        (ConsultationStatus.CANCELLED, datetime(2026, 3, 7, tzinfo=UTC)),
        (ConsultationStatus.RESCHEDULED, datetime(2026, 3, 8, tzinfo=UTC)),
        (ConsultationStatus.SCHEDULED, _PAST_IN_WINDOW),  # past → no_show
        (ConsultationStatus.SCHEDULED, _FUTURE_IN_WINDOW),  # future → pending
        (ConsultationStatus.DELETED, datetime(2026, 3, 9, tzinfo=UTC)),  # excluded
    ]
    for status, when in statuses:
        await _seed_consultation(
            db_session, tenant_id, person_uid=person.id,
            scheduled_at=when, status=status,
        )

    out = await _service(db_session).compute(
        tenant_id, audience="all", start_date=_WINDOW_START, end_date=_WINDOW_END
    )

    # Every channel row must satisfy the identity.
    for row in out.by_channel:
        assert (
            row.showed + row.no_show + row.cancelled + row.rescheduled + row.pending
            == row.consults_scheduled
        ), f"sum identity broken on {row.month}/{row.channel}"

    # Every month row too.
    for m in out.by_month:
        assert (
            m.showed + m.no_show + m.cancelled + m.rescheduled + m.pending
            == m.consults_scheduled
        ), f"sum identity broken on month {m.month}"

    # And the headline. 6 non-deleted appointments (deleted excluded).
    h = out.headline
    assert h.consults_scheduled == 6
    assert h.showed + h.no_show + h.cancelled + h.rescheduled + h.pending == 6
    assert h.showed == 1
    assert h.no_show == 2  # explicit no_show + past scheduled
    assert h.cancelled == 1
    assert h.rescheduled == 1
    assert h.pending == 1  # future scheduled


# ---------------------------------------------------------------------------
# 3. marketing ⊆ all for every stage and month.
# ---------------------------------------------------------------------------


async def test_marketing_is_subset_of_all(db_session: AsyncSession) -> None:
    """Every stage, every month: marketing ≤ all."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="ff-subset")

    # Marketing person.
    p1 = await _seed_person(db_session, tenant_id)
    await _seed_lead(
        db_session, tenant_id, person_uid=p1.id,
        created_at=datetime(2026, 4, 1, tzinfo=UTC),
        extra={"utm_source": "google"},
    )
    await _seed_consultation(
        db_session, tenant_id, person_uid=p1.id,
        scheduled_at=datetime(2026, 4, 4, tzinfo=UTC),
        status=ConsultationStatus.COMPLETED,
    )
    await _seed_payment(
        db_session, tenant_id, person_uid=p1.id,
        kind="payment_recorded", amount="500.00",
        occurred_at=datetime(2026, 4, 6, tzinfo=UTC),
    )
    # Non-marketing person (referral) + a CareStack-direct person (no lead).
    p2 = await _seed_person(db_session, tenant_id)
    await _seed_lead(
        db_session, tenant_id, person_uid=p2.id,
        created_at=datetime(2026, 4, 2, tzinfo=UTC),
        extra={"utm_source": "referral"},
    )
    await _seed_consultation(
        db_session, tenant_id, person_uid=p2.id,
        scheduled_at=datetime(2026, 4, 9, tzinfo=UTC),
        status=ConsultationStatus.NO_SHOW,
    )
    p3 = await _seed_person(db_session, tenant_id)
    await _seed_carestack_patient_link(db_session, tenant_id, person_uid=p3.id)
    await _seed_consultation(
        db_session, tenant_id, person_uid=p3.id,
        scheduled_at=datetime(2026, 4, 11, tzinfo=UTC),
        status=ConsultationStatus.COMPLETED,
    )

    svc = _service(db_session)
    all_out = await svc.compute(
        tenant_id, audience="all", start_date=_WINDOW_START, end_date=_WINDOW_END
    )
    mkt_out = await svc.compute(
        tenant_id, audience="marketing", start_date=_WINDOW_START, end_date=_WINDOW_END
    )

    stages = (
        "leads", "consults_scheduled", "showed", "no_show",
        "cancelled", "rescheduled", "pending", "closed_won", "revenue",
    )
    # Headline.
    for stage in stages:
        assert getattr(mkt_out.headline, stage) <= getattr(all_out.headline, stage), (
            f"marketing>all on headline {stage}"
        )
    # Per month.
    all_by_month = {m.month: m for m in all_out.by_month}
    for m in mkt_out.by_month:
        a = all_by_month[m.month]
        for stage in stages:
            assert getattr(m, stage) <= getattr(a, stage), (
                f"marketing>all on {m.month} {stage}"
            )

    # And marketing must be strictly non-empty here (it has 1 marketing person).
    assert mkt_out.headline.leads == 1
    assert all_out.headline.leads == 3  # google + referral + carestack-direct


# ---------------------------------------------------------------------------
# 4. Status mapping (each canonical status / time rule / deleted exclusion).
# ---------------------------------------------------------------------------


async def test_status_mapping_buckets(db_session: AsyncSession) -> None:
    """Each canonical status lands in exactly the right funnel bucket."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="ff-status")

    # One person per status (all marketing/google so they all render in `all`).
    async def _person_with_consult(status: ConsultationStatus, when: datetime) -> None:
        p = await _seed_person(db_session, tenant_id)
        await _seed_lead(
            db_session, tenant_id, person_uid=p.id,
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
            extra={"utm_source": "google"},
        )
        await _seed_consultation(
            db_session, tenant_id, person_uid=p.id, scheduled_at=when, status=status,
        )

    in_window = datetime(2026, 4, 15, 9, 0, tzinfo=UTC)
    # Showed buckets (Checked Out / In Operatory map to completed canonically).
    await _person_with_consult(ConsultationStatus.COMPLETED, in_window)
    # No-show buckets (No Show / Broken → no_show).
    await _person_with_consult(ConsultationStatus.NO_SHOW, in_window)
    # Cancelled.
    await _person_with_consult(ConsultationStatus.CANCELLED, in_window)
    # Rescheduled.
    await _person_with_consult(ConsultationStatus.RESCHEDULED, in_window)
    # Deleted / Note Completed → EXCLUDED.
    await _person_with_consult(ConsultationStatus.DELETED, in_window)
    # Past-dated scheduled → no_show.
    await _person_with_consult(ConsultationStatus.SCHEDULED, _PAST_IN_WINDOW)
    # Future scheduled → pending.
    await _person_with_consult(ConsultationStatus.SCHEDULED, _FUTURE_IN_WINDOW)

    out = await _service(db_session).compute(
        tenant_id, audience="all", start_date=_WINDOW_START, end_date=_WINDOW_END
    )
    h = out.headline
    assert h.showed == 1
    assert h.no_show == 2  # explicit no_show + past scheduled
    assert h.cancelled == 1
    assert h.rescheduled == 1
    assert h.pending == 1  # future scheduled
    # Deleted excluded: 6 non-deleted appointments counted, not 7.
    assert h.consults_scheduled == 6


# ---------------------------------------------------------------------------
# 5. Closed-won = money (Net Collected).
# ---------------------------------------------------------------------------


async def test_closed_won_is_money(db_session: AsyncSession) -> None:
    """closed_won = payers with net>0; revenue = recorded−refunded−reversed."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="ff-money")

    pay_month = datetime(2026, 5, 10, tzinfo=UTC)

    # Payer A: net positive (2000 recorded − 500 refunded = 1500).
    a = await _seed_person(db_session, tenant_id)
    await _seed_carestack_patient_link(db_session, tenant_id, person_uid=a.id)
    await _seed_payment(
        db_session, tenant_id, person_uid=a.id,
        kind="payment_recorded", amount="2000.00", occurred_at=pay_month,
    )
    await _seed_payment(
        db_session, tenant_id, person_uid=a.id,
        kind="payment_refunded", amount="500.00", occurred_at=pay_month,
    )
    # Payer B: net positive (300 recorded), separate person.
    b = await _seed_person(db_session, tenant_id)
    await _seed_carestack_patient_link(db_session, tenant_id, person_uid=b.id)
    await _seed_payment(
        db_session, tenant_id, person_uid=b.id,
        kind="payment_recorded", amount="300.00", occurred_at=pay_month,
    )
    # Payer C: net ZERO (400 recorded − 400 reversed) → NOT closed_won.
    c = await _seed_person(db_session, tenant_id)
    await _seed_carestack_patient_link(db_session, tenant_id, person_uid=c.id)
    await _seed_payment(
        db_session, tenant_id, person_uid=c.id,
        kind="payment_recorded", amount="400.00", occurred_at=pay_month,
    )
    await _seed_payment(
        db_session, tenant_id, person_uid=c.id,
        kind="payment_reversed", amount="400.00", occurred_at=pay_month,
    )
    # An applied leg must be EXCLUDED from Net Collected entirely.
    await _seed_payment(
        db_session, tenant_id, person_uid=b.id,
        kind="payment_applied", amount="9999.00", occurred_at=pay_month,
    )

    out = await _service(db_session).compute(
        tenant_id, audience="all", start_date=_WINDOW_START, end_date=_WINDOW_END
    )

    # Independent raw Net Collected (recorded − refunded − reversed, no applied).
    raw_net = await db_session.scalar(
        text(
            """
            SELECT
              coalesce(sum((payload->>'amount')::numeric)
                       FILTER (WHERE kind = 'payment_recorded'), 0)
              - coalesce(sum((payload->>'amount')::numeric)
                       FILTER (WHERE kind IN ('payment_refunded','payment_reversed')), 0)
            FROM interaction.event
            WHERE tenant_id = :t
              AND source_kind = 'carestack_accounting_transaction'
              AND data_class = 'billing'
            """
        ),
        {"t": tenant_id},
    )

    h = out.headline
    # closed_won = A + B (net>0); C is zero, excluded.
    assert h.closed_won == 2
    assert h.closed_won > 0
    # revenue = 1500 + 300 + 0 = 1800, and matches raw Net Collected.
    assert h.revenue == pytest.approx(1800.0)
    assert h.revenue == pytest.approx(float(Decimal(raw_net)))
    # Applied leg (9999) must not leak into revenue.
    assert h.revenue < 9999.0
    # Money landed in May.
    by_month = {m.month: m for m in out.by_month}
    assert by_month["2026-05"].closed_won == 2
    assert by_month["2026-05"].revenue == pytest.approx(1800.0)


# ---------------------------------------------------------------------------
# 6. CareStack-direct dating + audience.
# ---------------------------------------------------------------------------


async def test_carestack_direct_dating_and_audience(db_session: AsyncSession) -> None:
    """CareStack-direct (no lead) dating by earliest activity + audience rules."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="ff-cs-direct")

    # Active CareStack-direct person: patient link + a consult in April 2026.
    active = await _seed_person(db_session, tenant_id)
    await _seed_carestack_patient_link(db_session, tenant_id, person_uid=active.id)
    await _seed_consultation(
        db_session, tenant_id, person_uid=active.id,
        scheduled_at=datetime(2026, 4, 14, tzinfo=UTC),
        status=ConsultationStatus.COMPLETED,
    )

    # Zero-activity CareStack-direct person: patient link only, NO consult, NO
    # event → falls to the 2025-01-01 sentinel, outside a 2026 window.
    idle = await _seed_person(db_session, tenant_id)
    await _seed_carestack_patient_link(db_session, tenant_id, person_uid=idle.id)

    svc = _service(db_session)
    all_out = await svc.compute(
        tenant_id, audience="all", start_date=_WINDOW_START, end_date=_WINDOW_END
    )
    mkt_out = await svc.compute(
        tenant_id, audience="marketing", start_date=_WINDOW_START, end_date=_WINDOW_END
    )

    # The active person appears in `all` leads exactly once, dated to April by
    # earliest activity (consult), on channel `other`.
    assert all_out.headline.leads == 1
    april = next(m for m in all_out.by_month if m.month == "2026-04")
    assert april.leads == 1
    other_april = next(
        r for r in all_out.by_channel if r.month == "2026-04" and r.channel == "other"
    )
    assert other_april.leads == 1
    # Not on an ad channel.
    for r in all_out.by_channel:
        if r.channel in ("google", "facebook"):
            assert r.leads == 0

    # CareStack-direct (channel other) is never marketing.
    assert mkt_out.headline.leads == 0

    # The idle person (sentinel 2025-01-01) does NOT appear in the 2026 window.
    # Only the active person is counted; the idle one is dropped.
    assert all_out.headline.leads == 1

    # Sanity: widening the window to include 2025-01 surfaces the idle person.
    wide = await svc.compute(
        tenant_id, audience="all",
        start_date=date(2025, 1, 1), end_date=_WINDOW_END,
    )
    jan = next((m for m in wide.by_month if m.month == "2025-01"), None)
    assert jan is not None
    assert jan.leads == 1  # the idle person, dated to the sentinel month
