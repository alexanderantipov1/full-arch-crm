"""Marketing data access — no business logic, no commits."""

from __future__ import annotations

from datetime import date
from typing import Any, TypedDict

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import ColumnElement

from packages.core.types import TenantId

from .models import (
    Ad,
    AdCampaign,
    AdMetricDaily,
    AdMetricDailyAd,
    AdSet,
    GaChannelDaily,
    GaMetricDaily,
    GaPageDaily,
    GscQueryDaily,
)


class GscWindowTotals(TypedDict):
    """Typed result of :meth:`MarketingRepository.aggregate_gsc_totals`."""

    clicks: int
    impressions: int
    ctr: float | None
    avg_position: float | None
    distinct_queries: int


class GaEngagementWindowTotals(TypedDict):
    """Typed result of :meth:`MarketingRepository.aggregate_ga_engagement`."""

    engaged_sessions: int | None
    engagement_rate: float | None
    avg_session_duration: float | None
    bounce_rate: float | None
    event_count: int | None


class MarketingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- GSC daily query rows ---

    async def get_gsc_query(
        self,
        tenant_id: TenantId,
        *,
        site_url: str,
        metric_date: date,
        query_hash: str,
    ) -> GscQueryDaily | None:
        stmt = select(GscQueryDaily).where(
            GscQueryDaily.tenant_id == tenant_id,
            GscQueryDaily.site_url == site_url,
            GscQueryDaily.metric_date == metric_date,
            GscQueryDaily.query_hash == query_hash,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_gsc_query(self, row: GscQueryDaily) -> GscQueryDaily:
        self._session.add(row)
        await self._session.flush()
        return row

    # --- GA4 daily metrics ---

    async def get_ga_metric(
        self, tenant_id: TenantId, *, property_id: str, metric_date: date
    ) -> GaMetricDaily | None:
        stmt = select(GaMetricDaily).where(
            GaMetricDaily.tenant_id == tenant_id,
            GaMetricDaily.property_id == property_id,
            GaMetricDaily.metric_date == metric_date,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_ga_metric(self, metric: GaMetricDaily) -> GaMetricDaily:
        self._session.add(metric)
        await self._session.flush()
        return metric

    async def aggregate_ga_daily(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, object]]:
        """GA4 sessions/users/new_users/pageviews/conversions per day.

        Sums across every captured GA4 property for the tenant, one row per
        ``metric_date`` ordered oldest-first so the trend chart reads
        left→right. Feeds the SEO dashboard's GA4 daily trend.
        """
        stmt = (
            select(
                GaMetricDaily.metric_date,
                func.coalesce(func.sum(GaMetricDaily.sessions), 0).label("sessions"),
                func.coalesce(func.sum(GaMetricDaily.total_users), 0).label(
                    "total_users"
                ),
                func.coalesce(func.sum(GaMetricDaily.new_users), 0).label("new_users"),
                func.coalesce(func.sum(GaMetricDaily.screen_page_views), 0).label(
                    "screen_page_views"
                ),
                func.coalesce(func.sum(GaMetricDaily.conversions), 0).label(
                    "conversions"
                ),
            )
            .where(
                GaMetricDaily.tenant_id == tenant_id,
                GaMetricDaily.metric_date >= start_date,
                GaMetricDaily.metric_date <= end_date,
            )
            .group_by(GaMetricDaily.metric_date)
            .order_by(GaMetricDaily.metric_date)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "metric_date": r.metric_date,
                "sessions": int(r.sessions),
                "total_users": int(r.total_users),
                "new_users": int(r.new_users),
                "screen_page_views": int(r.screen_page_views),
                "conversions": float(r.conversions),
            }
            for r in rows
        ]

    async def aggregate_ga_engagement(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
    ) -> GaEngagementWindowTotals:
        """GA4 engagement window rollup (ENG-478).

        ``engaged_sessions`` / ``event_count`` are window sums. The rates are
        session-weighted: ``SUM(rate * sessions) / SUM(sessions)`` over rows
        that actually captured the rate (rows pulled before ENG-478 have NULL
        engagement columns and are excluded from both numerator and the weight
        denominator). Each field is ``None`` when nothing was captured so the
        service surfaces ``"—"`` rather than a fabricated 0.
        """
        # Session weight counted only where the rate is present, so pre-ENG-478
        # rows (NULL rate) neither bias the average nor inflate the weight.
        def _weighted(
            col: InstrumentedAttribute[float | None],
        ) -> tuple[ColumnElement[Any], ColumnElement[Any]]:
            weight = case((col.isnot(None), GaMetricDaily.sessions), else_=0)
            return (
                func.sum(col * GaMetricDaily.sessions),
                func.sum(weight),
            )

        rate_num, rate_w = _weighted(GaMetricDaily.engagement_rate)
        dur_num, dur_w = _weighted(GaMetricDaily.avg_session_duration)
        bounce_num, bounce_w = _weighted(GaMetricDaily.bounce_rate)
        stmt = select(
            func.sum(GaMetricDaily.engaged_sessions).label("engaged_sessions"),
            func.sum(GaMetricDaily.event_count).label("event_count"),
            rate_num.label("rate_num"),
            rate_w.label("rate_w"),
            dur_num.label("dur_num"),
            dur_w.label("dur_w"),
            bounce_num.label("bounce_num"),
            bounce_w.label("bounce_w"),
        ).where(
            GaMetricDaily.tenant_id == tenant_id,
            GaMetricDaily.metric_date >= start_date,
            GaMetricDaily.metric_date <= end_date,
        )
        row = (await self._session.execute(stmt)).one()

        def _ratio(num: object, weight: object) -> float | None:
            if num is None or weight is None:
                return None
            weight_f = float(weight)  # type: ignore[arg-type]
            if weight_f == 0.0:
                return None
            return float(num) / weight_f  # type: ignore[arg-type]

        return {
            "engaged_sessions": (
                int(row.engaged_sessions) if row.engaged_sessions is not None else None
            ),
            "event_count": (
                int(row.event_count) if row.event_count is not None else None
            ),
            "engagement_rate": _ratio(row.rate_num, row.rate_w),
            "avg_session_duration": _ratio(row.dur_num, row.dur_w),
            "bounce_rate": _ratio(row.bounce_num, row.bounce_w),
        }

    async def aggregate_ga_channels(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, object]]:
        """GA4 sessions/users/pageviews/conversions per acquisition channel.

        One row per ``channel`` over the window (summed across properties and
        days), ordered by sessions descending — feeds the organic/paid/direct
        split tile.
        """
        sessions_sum = func.coalesce(func.sum(GaChannelDaily.sessions), 0)
        stmt = (
            select(
                GaChannelDaily.channel,
                sessions_sum.label("sessions"),
                func.coalesce(func.sum(GaChannelDaily.total_users), 0).label(
                    "total_users"
                ),
                func.coalesce(func.sum(GaChannelDaily.new_users), 0).label("new_users"),
                func.coalesce(func.sum(GaChannelDaily.screen_page_views), 0).label(
                    "screen_page_views"
                ),
                func.coalesce(func.sum(GaChannelDaily.conversions), 0).label(
                    "conversions"
                ),
            )
            .where(
                GaChannelDaily.tenant_id == tenant_id,
                GaChannelDaily.metric_date >= start_date,
                GaChannelDaily.metric_date <= end_date,
            )
            .group_by(GaChannelDaily.channel)
            .order_by(sessions_sum.desc(), GaChannelDaily.channel)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "channel": r.channel,
                "sessions": int(r.sessions),
                "total_users": int(r.total_users),
                "new_users": int(r.new_users),
                "screen_page_views": int(r.screen_page_views),
                "conversions": float(r.conversions),
            }
            for r in rows
        ]

    async def aggregate_ga_top_pages(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
        limit: int,
    ) -> list[dict[str, object]]:
        """Top GA4 pages by summed sessions over the window.

        One row per distinct ``page_path`` (summed across properties and days),
        ordered by sessions descending, capped at ``limit`` — feeds the
        top-pages table.
        """
        sessions_sum = func.coalesce(func.sum(GaPageDaily.sessions), 0)
        pageviews_sum = func.coalesce(func.sum(GaPageDaily.screen_page_views), 0)
        stmt = (
            select(
                GaPageDaily.page_path,
                sessions_sum.label("sessions"),
                func.coalesce(func.sum(GaPageDaily.total_users), 0).label(
                    "total_users"
                ),
                func.coalesce(func.sum(GaPageDaily.new_users), 0).label("new_users"),
                pageviews_sum.label("screen_page_views"),
                func.coalesce(func.sum(GaPageDaily.conversions), 0).label(
                    "conversions"
                ),
            )
            .where(
                GaPageDaily.tenant_id == tenant_id,
                GaPageDaily.metric_date >= start_date,
                GaPageDaily.metric_date <= end_date,
            )
            .group_by(GaPageDaily.page_path)
            .order_by(sessions_sum.desc(), pageviews_sum.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "page_path": r.page_path,
                "sessions": int(r.sessions),
                "total_users": int(r.total_users),
                "new_users": int(r.new_users),
                "screen_page_views": int(r.screen_page_views),
                "conversions": float(r.conversions),
            }
            for r in rows
        ]

    # --- GA4 channel rows ---

    async def get_ga_channel(
        self,
        tenant_id: TenantId,
        *,
        property_id: str,
        metric_date: date,
        channel: str,
    ) -> GaChannelDaily | None:
        stmt = select(GaChannelDaily).where(
            GaChannelDaily.tenant_id == tenant_id,
            GaChannelDaily.property_id == property_id,
            GaChannelDaily.metric_date == metric_date,
            GaChannelDaily.channel == channel,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_ga_channel(self, row: GaChannelDaily) -> GaChannelDaily:
        self._session.add(row)
        await self._session.flush()
        return row

    # --- GA4 page rows ---

    async def get_ga_page(
        self,
        tenant_id: TenantId,
        *,
        property_id: str,
        metric_date: date,
        page_hash: str,
    ) -> GaPageDaily | None:
        stmt = select(GaPageDaily).where(
            GaPageDaily.tenant_id == tenant_id,
            GaPageDaily.property_id == property_id,
            GaPageDaily.metric_date == metric_date,
            GaPageDaily.page_hash == page_hash,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_ga_page(self, row: GaPageDaily) -> GaPageDaily:
        self._session.add(row)
        await self._session.flush()
        return row

    async def aggregate_gsc_totals(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
    ) -> GscWindowTotals:
        """GSC window totals: summed clicks/impressions, distinct query count,
        and impression-weighted CTR + average position.

        CTR is ``SUM(clicks) / SUM(impressions)``; position is
        ``SUM(position * impressions) / SUM(impressions)`` — both weighted by
        impressions so a high-volume query dominates the average. Both come
        back ``None`` when the window had zero impressions (the service maps
        that to the dashboard's ``"—"``). ``distinct_queries`` counts distinct
        ``query_hash`` values.
        """
        weighted_position = func.sum(
            GscQueryDaily.position * GscQueryDaily.impressions
        )
        stmt = select(
            func.coalesce(func.sum(GscQueryDaily.clicks), 0).label("clicks"),
            func.coalesce(func.sum(GscQueryDaily.impressions), 0).label("impressions"),
            func.coalesce(weighted_position, 0).label("weighted_position"),
            func.count(func.distinct(GscQueryDaily.query_hash)).label(
                "distinct_queries"
            ),
        ).where(
            GscQueryDaily.tenant_id == tenant_id,
            GscQueryDaily.metric_date >= start_date,
            GscQueryDaily.metric_date <= end_date,
        )
        row = (await self._session.execute(stmt)).one()
        clicks = int(row.clicks)
        impressions = int(row.impressions)
        weighted_pos = float(row.weighted_position)
        return {
            "clicks": clicks,
            "impressions": impressions,
            "ctr": (clicks / impressions) if impressions > 0 else None,
            "avg_position": (weighted_pos / impressions) if impressions > 0 else None,
            "distinct_queries": int(row.distinct_queries),
        }

    async def aggregate_gsc_top_queries(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
        limit: int,
    ) -> list[dict[str, object]]:
        """Top search queries by summed clicks over the window.

        One row per distinct query (collapsed by ``query``: the same query
        across days/sites is summed), ordered by clicks descending. CTR and
        position are impression-weighted per query, ``None`` when the query
        had zero impressions in the window.
        """
        weighted_position = func.sum(GscQueryDaily.position * GscQueryDaily.impressions)
        clicks_sum = func.coalesce(func.sum(GscQueryDaily.clicks), 0)
        impressions_sum = func.coalesce(func.sum(GscQueryDaily.impressions), 0)
        stmt = (
            select(
                GscQueryDaily.query,
                clicks_sum.label("clicks"),
                impressions_sum.label("impressions"),
                func.coalesce(weighted_position, 0).label("weighted_position"),
            )
            .where(
                GscQueryDaily.tenant_id == tenant_id,
                GscQueryDaily.metric_date >= start_date,
                GscQueryDaily.metric_date <= end_date,
            )
            .group_by(GscQueryDaily.query)
            .order_by(clicks_sum.desc(), impressions_sum.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        result: list[dict[str, object]] = []
        for r in rows:
            clicks = int(r.clicks)
            impressions = int(r.impressions)
            weighted_pos = float(r.weighted_position)
            result.append(
                {
                    "query": r.query,
                    "clicks": clicks,
                    "impressions": impressions,
                    "ctr": (clicks / impressions) if impressions > 0 else None,
                    "position": (
                        weighted_pos / impressions if impressions > 0 else None
                    ),
                }
            )
        return result

    # --- campaigns ---

    async def get_campaign(
        self, tenant_id: TenantId, *, provider: str, external_id: str
    ) -> AdCampaign | None:
        stmt = select(AdCampaign).where(
            AdCampaign.tenant_id == tenant_id,
            AdCampaign.provider == provider,
            AdCampaign.external_id == external_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_campaign(self, campaign: AdCampaign) -> AdCampaign:
        self._session.add(campaign)
        await self._session.flush()
        return campaign

    # --- daily metrics ---

    async def get_metric(
        self,
        tenant_id: TenantId,
        *,
        provider: str,
        campaign_external_id: str,
        metric_date: date,
    ) -> AdMetricDaily | None:
        stmt = select(AdMetricDaily).where(
            AdMetricDaily.tenant_id == tenant_id,
            AdMetricDaily.provider == provider,
            AdMetricDaily.campaign_external_id == campaign_external_id,
            AdMetricDaily.metric_date == metric_date,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_metric(self, metric: AdMetricDaily) -> AdMetricDaily:
        self._session.add(metric)
        await self._session.flush()
        return metric

    async def aggregate_daily_by_provider(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
        provider: str | None = None,
    ) -> list[dict[str, object]]:
        """Spend/impressions/clicks/conversions per (metric_date, provider).

        Feeds the marketing dashboard's daily trend chart: one row per day per
        provider, ordered oldest-first so the line/area chart reads left→right.
        """
        stmt = (
            select(
                AdMetricDaily.metric_date,
                AdMetricDaily.provider,
                func.coalesce(func.sum(AdMetricDaily.spend), 0).label("spend"),
                func.coalesce(func.sum(AdMetricDaily.impressions), 0).label(
                    "impressions"
                ),
                func.coalesce(func.sum(AdMetricDaily.clicks), 0).label("clicks"),
                func.coalesce(func.sum(AdMetricDaily.conversions), 0).label(
                    "conversions"
                ),
            )
            .where(
                AdMetricDaily.tenant_id == tenant_id,
                AdMetricDaily.metric_date >= start_date,
                AdMetricDaily.metric_date <= end_date,
            )
            .group_by(AdMetricDaily.metric_date, AdMetricDaily.provider)
            .order_by(AdMetricDaily.metric_date, AdMetricDaily.provider)
        )
        if provider is not None:
            stmt = stmt.where(AdMetricDaily.provider == provider)
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "metric_date": r.metric_date,
                "provider": r.provider,
                "spend": float(r.spend),
                "impressions": int(r.impressions),
                "clicks": int(r.clicks),
                "conversions": float(r.conversions),
            }
            for r in rows
        ]

    async def aggregate_monthly_by_provider(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
        provider: str | None = None,
    ) -> list[dict[str, object]]:
        """Spend/impressions/clicks/conversions per (month, provider).

        Feeds the full-funnel report's monthly spend row (ENG-472): one row
        per calendar month (``"YYYY-MM"``) per provider, ordered oldest-first.
        The month bucket keys off ``metric_date``.
        """
        month = func.to_char(AdMetricDaily.metric_date, "YYYY-MM")
        stmt = (
            select(
                month.label("month"),
                AdMetricDaily.provider,
                func.coalesce(func.sum(AdMetricDaily.spend), 0).label("spend"),
                func.coalesce(func.sum(AdMetricDaily.impressions), 0).label(
                    "impressions"
                ),
                func.coalesce(func.sum(AdMetricDaily.clicks), 0).label("clicks"),
                func.coalesce(func.sum(AdMetricDaily.conversions), 0).label(
                    "conversions"
                ),
            )
            .where(
                AdMetricDaily.tenant_id == tenant_id,
                AdMetricDaily.metric_date >= start_date,
                AdMetricDaily.metric_date <= end_date,
            )
            .group_by(month, AdMetricDaily.provider)
            .order_by(month, AdMetricDaily.provider)
        )
        if provider is not None:
            stmt = stmt.where(AdMetricDaily.provider == provider)
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "month": r.month,
                "provider": r.provider,
                "spend": float(r.spend),
                "impressions": int(r.impressions),
                "clicks": int(r.clicks),
                "conversions": float(r.conversions),
            }
            for r in rows
        ]

    async def aggregate_provider_totals(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
        provider: str | None = None,
    ) -> list[dict[str, object]]:
        """Spend/impressions/clicks/conversions per provider over a window.

        Feeds the marketing dashboard's provider-split tile (Google Ads vs
        Meta Ads vs …). Ordered by spend descending.
        """
        stmt = (
            select(
                AdMetricDaily.provider,
                func.coalesce(func.sum(AdMetricDaily.spend), 0).label("spend"),
                func.coalesce(func.sum(AdMetricDaily.impressions), 0).label(
                    "impressions"
                ),
                func.coalesce(func.sum(AdMetricDaily.clicks), 0).label("clicks"),
                func.coalesce(func.sum(AdMetricDaily.conversions), 0).label(
                    "conversions"
                ),
            )
            .where(
                AdMetricDaily.tenant_id == tenant_id,
                AdMetricDaily.metric_date >= start_date,
                AdMetricDaily.metric_date <= end_date,
            )
            .group_by(AdMetricDaily.provider)
            .order_by(func.sum(AdMetricDaily.spend).desc())
        )
        if provider is not None:
            stmt = stmt.where(AdMetricDaily.provider == provider)
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "provider": r.provider,
                "spend": float(r.spend),
                "impressions": int(r.impressions),
                "clicks": int(r.clicks),
                "conversions": float(r.conversions),
            }
            for r in rows
        ]

    # --- ad sets (ENG-512) ---

    async def get_ad_set(
        self, tenant_id: TenantId, *, provider: str, external_id: str
    ) -> AdSet | None:
        stmt = select(AdSet).where(
            AdSet.tenant_id == tenant_id,
            AdSet.provider == provider,
            AdSet.external_id == external_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_ad_set(self, ad_set: AdSet) -> AdSet:
        self._session.add(ad_set)
        await self._session.flush()
        return ad_set

    # --- ads (ENG-512) ---

    async def get_ad(
        self, tenant_id: TenantId, *, provider: str, external_id: str
    ) -> Ad | None:
        stmt = select(Ad).where(
            Ad.tenant_id == tenant_id,
            Ad.provider == provider,
            Ad.external_id == external_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_ad(self, ad: Ad) -> Ad:
        self._session.add(ad)
        await self._session.flush()
        return ad

    async def list_ads(
        self, tenant_id: TenantId, *, provider: str | None = None
    ) -> list[Ad]:
        """All ad identity rows for the tenant (cost-per-lead bridge)."""
        stmt = select(Ad).where(Ad.tenant_id == tenant_id)
        if provider is not None:
            stmt = stmt.where(Ad.provider == provider)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_campaigns(
        self, tenant_id: TenantId, *, provider: str | None = None
    ) -> list[AdCampaign]:
        """All campaign identity rows for the tenant (cost-per-lead bridge)."""
        stmt = select(AdCampaign).where(AdCampaign.tenant_id == tenant_id)
        if provider is not None:
            stmt = stmt.where(AdCampaign.provider == provider)
        return list((await self._session.execute(stmt)).scalars().all())

    # --- ad-level daily metrics (ENG-512) ---

    async def get_ad_metric(
        self,
        tenant_id: TenantId,
        *,
        provider: str,
        ad_external_id: str,
        metric_date: date,
    ) -> AdMetricDailyAd | None:
        stmt = select(AdMetricDailyAd).where(
            AdMetricDailyAd.tenant_id == tenant_id,
            AdMetricDailyAd.provider == provider,
            AdMetricDailyAd.ad_external_id == ad_external_id,
            AdMetricDailyAd.metric_date == metric_date,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_ad_metric(self, metric: AdMetricDailyAd) -> AdMetricDailyAd:
        self._session.add(metric)
        await self._session.flush()
        return metric

    async def ad_daily_spend(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, object]]:
        """Per-(ad, day) spend over a window for the cost-per-lead allocator.

        One row per ``(ad_external_id, metric_date)`` (summed across providers
        is not needed — an ad id is provider-unique), carrying the parent
        ``campaign_external_id`` so the allocator can roll ad spend up to the
        campaign tier when computing the residual.
        """
        stmt = (
            select(
                AdMetricDailyAd.ad_external_id,
                AdMetricDailyAd.campaign_external_id,
                AdMetricDailyAd.metric_date,
                func.coalesce(func.sum(AdMetricDailyAd.spend), 0).label("spend"),
            )
            .where(
                AdMetricDailyAd.tenant_id == tenant_id,
                AdMetricDailyAd.metric_date >= start_date,
                AdMetricDailyAd.metric_date <= end_date,
            )
            .group_by(
                AdMetricDailyAd.ad_external_id,
                AdMetricDailyAd.campaign_external_id,
                AdMetricDailyAd.metric_date,
            )
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "ad_external_id": r.ad_external_id,
                "campaign_external_id": r.campaign_external_id,
                "metric_date": r.metric_date,
                "spend": float(r.spend),
            }
            for r in rows
        ]

    async def campaign_daily_spend(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, object]]:
        """Per-(campaign, day) spend over a window for the campaign fallback tier.

        Reads the existing campaign-level :class:`AdMetricDaily` — the
        authoritative campaign total — so the allocator's campaign residual
        (campaign spend minus ad-tier allocations) reconciles to it.
        """
        stmt = (
            select(
                AdMetricDaily.campaign_external_id,
                AdMetricDaily.metric_date,
                func.coalesce(func.sum(AdMetricDaily.spend), 0).label("spend"),
            )
            .where(
                AdMetricDaily.tenant_id == tenant_id,
                AdMetricDaily.metric_date >= start_date,
                AdMetricDaily.metric_date <= end_date,
            )
            .group_by(
                AdMetricDaily.campaign_external_id,
                AdMetricDaily.metric_date,
            )
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "campaign_external_id": r.campaign_external_id,
                "metric_date": r.metric_date,
                "spend": float(r.spend),
            }
            for r in rows
        ]

    async def aggregate_spend(
        self,
        tenant_id: TenantId,
        *,
        start_date: date,
        end_date: date,
        provider: str | None = None,
    ) -> list[dict[str, object]]:
        """Spend/impressions/clicks/conversions per campaign over a window.

        Left-joins :class:`AdCampaign` for the human-readable campaign name;
        groups by the metric's natural campaign key so a metric with no
        captured campaign row still appears (name ``None``).
        """
        stmt = (
            select(
                AdMetricDaily.provider,
                AdMetricDaily.campaign_external_id,
                AdCampaign.name.label("campaign_name"),
                func.coalesce(func.sum(AdMetricDaily.spend), 0).label("spend"),
                func.coalesce(func.sum(AdMetricDaily.impressions), 0).label(
                    "impressions"
                ),
                func.coalesce(func.sum(AdMetricDaily.clicks), 0).label("clicks"),
                func.coalesce(func.sum(AdMetricDaily.conversions), 0).label(
                    "conversions"
                ),
            )
            .select_from(AdMetricDaily)
            .outerjoin(
                AdCampaign,
                (AdCampaign.tenant_id == AdMetricDaily.tenant_id)
                & (AdCampaign.provider == AdMetricDaily.provider)
                & (AdCampaign.external_id == AdMetricDaily.campaign_external_id),
            )
            .where(
                AdMetricDaily.tenant_id == tenant_id,
                AdMetricDaily.metric_date >= start_date,
                AdMetricDaily.metric_date <= end_date,
            )
            .group_by(
                AdMetricDaily.provider,
                AdMetricDaily.campaign_external_id,
                AdCampaign.name,
            )
            .order_by(func.sum(AdMetricDaily.spend).desc())
        )
        if provider is not None:
            stmt = stmt.where(AdMetricDaily.provider == provider)
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "provider": r.provider,
                "campaign_external_id": r.campaign_external_id,
                "campaign_name": r.campaign_name,
                "spend": float(r.spend),
                "impressions": int(r.impressions),
                "clicks": int(r.clicks),
                "conversions": float(r.conversions),
            }
            for r in rows
        ]
