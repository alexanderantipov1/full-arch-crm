"""DB-backed tests for the ENG-471 SEO dashboard aggregations.

Exercises ``MarketingService.ga_metric_totals`` and ``gsc_query_totals``
(which fan out to ``MarketingRepository.aggregate_ga_daily`` /
``aggregate_gsc_totals`` / ``aggregate_gsc_top_queries``) against a real
Postgres test DB on a fresh tenant (rolled back on teardown). The
impression-weighted CTR/position, distinct query count, and top-query
ordering are exactly the parts a mocked-repo unit test cannot verify.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.marketing.models import (
    GaChannelDaily,
    GaMetricDaily,
    GaPageDaily,
    GscQueryDaily,
)
from packages.marketing.service import MarketingService
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_DAY_1 = date(2026, 6, 1)
_DAY_2 = date(2026, 6, 2)
_OUTSIDE = date(2026, 5, 1)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


async def _seed_ga(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    property_id: str,
    metric_date: date,
    sessions: int,
    total_users: int,
    new_users: int,
    screen_page_views: int,
    conversions: float,
) -> None:
    session.add(
        GaMetricDaily(
            tenant_id=tenant_id,
            property_id=property_id,
            metric_date=metric_date,
            sessions=sessions,
            total_users=total_users,
            new_users=new_users,
            screen_page_views=screen_page_views,
            conversions=conversions,
        )
    )
    await session.flush()


async def _seed_gsc(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    site_url: str,
    metric_date: date,
    query: str,
    clicks: int,
    impressions: int,
    ctr: float,
    position: float,
) -> None:
    session.add(
        GscQueryDaily(
            tenant_id=tenant_id,
            site_url=site_url,
            metric_date=metric_date,
            query=query,
            query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
            clicks=clicks,
            impressions=impressions,
            ctr=ctr,
            position=position,
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_ga_metric_totals_sums_across_properties_and_window(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="seo-ga")

    # Two properties on day 1, one on day 2, plus a row outside the window.
    await _seed_ga(
        db_session, tenant_id, property_id="p1", metric_date=_DAY_1,
        sessions=100, total_users=80, new_users=60, screen_page_views=300,
        conversions=5.0,
    )
    await _seed_ga(
        db_session, tenant_id, property_id="p2", metric_date=_DAY_1,
        sessions=10, total_users=8, new_users=6, screen_page_views=30,
        conversions=1.0,
    )
    await _seed_ga(
        db_session, tenant_id, property_id="p1", metric_date=_DAY_2,
        sessions=50, total_users=40, new_users=30, screen_page_views=150,
        conversions=2.0,
    )
    await _seed_ga(
        db_session, tenant_id, property_id="p1", metric_date=_OUTSIDE,
        sessions=999, total_users=999, new_users=999, screen_page_views=999,
        conversions=99.0,
    )

    totals = await MarketingService(db_session).ga_metric_totals(
        tenant_id, start_date=_DAY_1, end_date=_DAY_2
    )

    # Window totals exclude the out-of-window row.
    assert totals.sessions == 100 + 10 + 50
    assert totals.total_users == 80 + 8 + 40
    assert totals.new_users == 60 + 6 + 30
    assert totals.screen_page_views == 300 + 30 + 150
    assert totals.conversions == pytest.approx(8.0)

    # Daily series: one row per day (properties summed), oldest-first.
    assert [p.metric_date for p in totals.daily] == [_DAY_1, _DAY_2]
    day1 = totals.daily[0]
    assert day1.sessions == 110  # p1 100 + p2 10
    assert day1.screen_page_views == 330
    assert totals.daily[1].sessions == 50


@pytest.mark.asyncio
async def test_gsc_query_totals_weighted_and_distinct(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="seo-gsc")

    # "implants" across two days; "dentist" once; one row outside the window.
    await _seed_gsc(
        db_session, tenant_id, site_url="https://x", metric_date=_DAY_1,
        query="implants", clicks=80, impressions=1000, ctr=0.08, position=2.0,
    )
    await _seed_gsc(
        db_session, tenant_id, site_url="https://x", metric_date=_DAY_2,
        query="implants", clicks=20, impressions=1000, ctr=0.02, position=4.0,
    )
    await _seed_gsc(
        db_session, tenant_id, site_url="https://x", metric_date=_DAY_1,
        query="dentist", clicks=5, impressions=100, ctr=0.05, position=10.0,
    )
    await _seed_gsc(
        db_session, tenant_id, site_url="https://x", metric_date=_OUTSIDE,
        query="implants", clicks=999, impressions=999, ctr=1.0, position=1.0,
    )

    totals = await MarketingService(db_session).gsc_query_totals(
        tenant_id, start_date=_DAY_1, end_date=_DAY_2
    )

    # Window sums exclude the out-of-window row.
    assert totals.clicks == 80 + 20 + 5
    assert totals.impressions == 1000 + 1000 + 100
    # Impression-weighted CTR = SUM(clicks) / SUM(impressions).
    assert totals.ctr == pytest.approx(105 / 2100)
    # Impression-weighted position:
    # (2*1000 + 4*1000 + 10*100) / 2100 = 7000 / 2100.
    assert totals.avg_position == pytest.approx(7000 / 2100)
    # Distinct query_hash count: "implants" + "dentist" = 2.
    assert totals.distinct_queries == 2

    # Top queries by clicks: implants (100) before dentist (5).
    assert [r.query for r in totals.top_queries] == ["implants", "dentist"]
    implants = totals.top_queries[0]
    assert implants.clicks == 100
    assert implants.impressions == 2000
    assert implants.ctr == pytest.approx(100 / 2000)
    # Per-query weighted position: (2*1000 + 4*1000) / 2000 = 3.0.
    assert implants.position == pytest.approx(3.0)


async def _seed_ga_full(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    property_id: str,
    metric_date: date,
    sessions: int,
    engaged_sessions: int | None,
    engagement_rate: float | None,
    avg_session_duration: float | None,
    bounce_rate: float | None,
    event_count: int | None,
) -> None:
    session.add(
        GaMetricDaily(
            tenant_id=tenant_id,
            property_id=property_id,
            metric_date=metric_date,
            sessions=sessions,
            total_users=sessions,
            new_users=0,
            screen_page_views=sessions,
            conversions=0.0,
            engaged_sessions=engaged_sessions,
            engagement_rate=engagement_rate,
            avg_session_duration=avg_session_duration,
            bounce_rate=bounce_rate,
            event_count=event_count,
        )
    )
    await session.flush()


async def _seed_ga_channel(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    property_id: str,
    metric_date: date,
    channel: str,
    sessions: int,
) -> None:
    session.add(
        GaChannelDaily(
            tenant_id=tenant_id,
            property_id=property_id,
            metric_date=metric_date,
            channel=channel,
            sessions=sessions,
            total_users=sessions,
            new_users=0,
            screen_page_views=sessions,
            conversions=0.0,
        )
    )
    await session.flush()


async def _seed_ga_page(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    property_id: str,
    metric_date: date,
    page_path: str,
    sessions: int,
) -> None:
    session.add(
        GaPageDaily(
            tenant_id=tenant_id,
            property_id=property_id,
            metric_date=metric_date,
            page_path=page_path,
            page_hash=hashlib.sha256(page_path.encode("utf-8")).hexdigest(),
            sessions=sessions,
            total_users=sessions,
            new_users=0,
            screen_page_views=sessions * 2,
            conversions=0.0,
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_ga_engagement_session_weighted_and_window(
    db_session: AsyncSession,
) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="ga-engagement")

    # Two in-window days with engagement, one out-of-window day, and one
    # in-window day with NULL engagement (pre-ENG-478 row) that must NOT
    # contribute to the weighted averages or bias the weight denominator.
    await _seed_ga_full(
        db_session, tenant_id, property_id="p1", metric_date=_DAY_1,
        sessions=100, engaged_sessions=60, engagement_rate=0.60,
        avg_session_duration=70.0, bounce_rate=0.40, event_count=500,
    )
    await _seed_ga_full(
        db_session, tenant_id, property_id="p1", metric_date=_DAY_2,
        sessions=300, engaged_sessions=240, engagement_rate=0.80,
        avg_session_duration=90.0, bounce_rate=0.20, event_count=1500,
    )
    await _seed_ga_full(
        db_session, tenant_id, property_id="p1", metric_date=_OUTSIDE,
        sessions=999, engaged_sessions=999, engagement_rate=1.0,
        avg_session_duration=999.0, bounce_rate=0.0, event_count=9999,
    )
    await _seed_ga_full(
        db_session, tenant_id, property_id="p2", metric_date=_DAY_1,
        sessions=50, engaged_sessions=None, engagement_rate=None,
        avg_session_duration=None, bounce_rate=None, event_count=None,
    )

    totals = await MarketingService(db_session).ga_metric_totals(
        tenant_id, start_date=_DAY_1, end_date=_DAY_2
    )
    eng = totals.engagement
    # Sums: engaged_sessions / event_count over the window (NULL ignored).
    assert eng.engaged_sessions == 60 + 240
    assert eng.event_count == 500 + 1500
    # Session-weighted rate: (0.60*100 + 0.80*300) / (100 + 300) = 300/400.
    assert eng.engagement_rate == pytest.approx((0.60 * 100 + 0.80 * 300) / 400)
    # Weighted duration: (70*100 + 90*300) / 400.
    assert eng.avg_session_duration == pytest.approx((70 * 100 + 90 * 300) / 400)
    assert eng.bounce_rate == pytest.approx((0.40 * 100 + 0.20 * 300) / 400)


@pytest.mark.asyncio
async def test_ga_engagement_none_when_uncaptured(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="ga-engagement-null")

    # In-window sessions but all engagement columns NULL → rollup is all None.
    await _seed_ga_full(
        db_session, tenant_id, property_id="p1", metric_date=_DAY_1,
        sessions=100, engaged_sessions=None, engagement_rate=None,
        avg_session_duration=None, bounce_rate=None, event_count=None,
    )
    totals = await MarketingService(db_session).ga_metric_totals(
        tenant_id, start_date=_DAY_1, end_date=_DAY_2
    )
    eng = totals.engagement
    assert eng.engaged_sessions is None
    assert eng.event_count is None
    assert eng.engagement_rate is None
    assert eng.avg_session_duration is None
    assert eng.bounce_rate is None


@pytest.mark.asyncio
async def test_ga_channels_grouped_and_ordered(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="ga-channels")

    # "Paid Search" across two days + properties; "Direct" once; one outside.
    await _seed_ga_channel(
        db_session, tenant_id, property_id="p1", metric_date=_DAY_1,
        channel="Paid Search", sessions=100,
    )
    await _seed_ga_channel(
        db_session, tenant_id, property_id="p2", metric_date=_DAY_1,
        channel="Paid Search", sessions=50,
    )
    await _seed_ga_channel(
        db_session, tenant_id, property_id="p1", metric_date=_DAY_2,
        channel="Direct", sessions=200,
    )
    await _seed_ga_channel(
        db_session, tenant_id, property_id="p1", metric_date=_OUTSIDE,
        channel="Paid Search", sessions=999,
    )

    totals = await MarketingService(db_session).ga_metric_totals(
        tenant_id, start_date=_DAY_1, end_date=_DAY_2
    )
    # Grouped by channel, ordered by sessions desc: Direct(200) > Paid Search(150).
    assert [(c.channel, c.sessions) for c in totals.channels] == [
        ("Direct", 200),
        ("Paid Search", 150),
    ]


@pytest.mark.asyncio
async def test_ga_top_pages_grouped_and_ordered(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="ga-pages")

    await _seed_ga_page(
        db_session, tenant_id, property_id="p1", metric_date=_DAY_1,
        page_path="/implants", sessions=80,
    )
    await _seed_ga_page(
        db_session, tenant_id, property_id="p1", metric_date=_DAY_2,
        page_path="/implants", sessions=20,
    )
    await _seed_ga_page(
        db_session, tenant_id, property_id="p1", metric_date=_DAY_1,
        page_path="/about", sessions=30,
    )
    await _seed_ga_page(
        db_session, tenant_id, property_id="p1", metric_date=_OUTSIDE,
        page_path="/implants", sessions=999,
    )

    totals = await MarketingService(db_session).ga_metric_totals(
        tenant_id, start_date=_DAY_1, end_date=_DAY_2
    )
    # /implants (80+20=100) before /about (30); window excludes the outside row.
    assert [(p.page_path, p.sessions) for p in totals.top_pages] == [
        ("/implants", 100),
        ("/about", 30),
    ]
    # screen_page_views summed: /implants = (80+20)*2 = 200.
    assert totals.top_pages[0].screen_page_views == 200


@pytest.mark.asyncio
async def test_gsc_empty_window_yields_none_ratios(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="seo-gsc-empty")

    totals = await MarketingService(db_session).gsc_query_totals(
        tenant_id, start_date=_DAY_1, end_date=_DAY_2
    )

    # No impressions in the window → ratios are None (UI "—"), not 0.
    assert totals.clicks == 0
    assert totals.impressions == 0
    assert totals.ctr is None
    assert totals.avg_position is None
    assert totals.distinct_queries == 0
    assert totals.top_queries == []
